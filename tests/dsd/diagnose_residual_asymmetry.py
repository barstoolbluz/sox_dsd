#!/usr/bin/env python3
"""Reproduce the P19/P20 residual and identify its frequency and source-precision limits.

Diagnostic only: this is not an independent audio oracle or production qualification.
The frozen 32-bit source is tested unchanged; a separately labeled F64 source
removes its quantization to estimate the diagnostic's practical noise floor.
No historical artifacts are modified. Requires the built test/dsd_test_p10.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from scipy.signal import upfirdn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/dsd'))
import p10_corpus
import p20_audio_compare

SAMPLE_HZ = 176400
CLOCKS = {'dsd512': 22579200, 'dsd1024': 45158400}
BANDS_HZ = ((0, 20000), (20000, 40000), (40000, 60000), (60000, 88200))
ORIGINAL = {
    'dsd512': ROOT / 'tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/verify/audio-compare.json',
    'dsd1024': ROOT / 'tests/dsd/results/P19_DSD1024_CORRECTION/audio-v1-v2-comparison.json',
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reference_source():
    case = next(c for c in p10_corpus.holdout_cases(11289600) if c['name'] == 'tone-997--6')
    raw, description = p10_corpus.stimulus(case)
    n = int(description['frames'])
    assert n == round(1.6 * SAMPLE_HZ)
    # Use the frozen corpus generator's exact operation ordering before rounding.
    # Reassociation changes up to 73 source int32 words on this fixture.
    t = np.arange(n, dtype=np.float64) / SAMPLE_HZ
    high_precision = (10.0 ** (-6.0 / 20.0)) * np.sin(2.0 * np.pi * 997.0 * t)
    taper = int(round(case['taper_seconds'] * SAMPLE_HZ))
    t = np.arange(taper, dtype=np.float64) / taper
    ramp = t * t * t * (10 + t * (-15 + 6 * t))
    high_precision[:taper] *= ramp
    high_precision[-taper:] *= ramp[::-1]
    roundtrip = np.rint(high_precision * (2**31 - 1)).astype('<i4')
    if sha256(roundtrip.tobytes()) != description['source_i32le_sha256']:
        raise RuntimeError('F64 control is not the exact prequantization source')
    return case, raw, description, high_precision.astype('<f8').tobytes()


def dbfs_equivalent(rms: float) -> float:
    # Match P19/P20's sine-equivalent convention, not AES17 dBFS for white noise.
    return float(20.0 * np.log10(max(float(rms) * math.sqrt(2.0), 1e-300)))


def residual_and_bands(y: np.ndarray):
    start, stop = int(.4 * SAMPLE_HZ), int(1.2 * SAMPLE_HZ)
    window = y[start:stop]
    n = np.arange(start, stop, dtype=np.float64)
    theta = (2.0 * np.pi * 997.0 / SAMPLE_HZ) * n
    basis = np.column_stack([np.sin(theta), np.cos(theta), np.ones(n.size)])
    fitted = np.linalg.lstsq(basis, window, rcond=None)[0]
    residual = window - basis @ fitted
    spectrum = np.fft.rfft(residual)
    freq = np.fft.rfftfreq(residual.size, 1.0 / SAMPLE_HZ)
    weights = np.full(spectrum.size, 2.0, dtype=np.float64)
    weights[0] = 1.0
    if residual.size % 2 == 0:
        weights[-1] = 1.0
    power = (np.abs(spectrum) ** 2) * weights / residual.size ** 2
    bands = {}
    for low, high in BANDS_HZ:
        select = (freq >= low) & (freq < high if high < SAMPLE_HZ / 2 else freq <= high)
        rms = math.sqrt(float(np.sum(power[select], dtype=np.float64)))
        bands[f'{low}-{high}Hz'] = {'rms': rms, 'dbfs_rms_equivalent': dbfs_equivalent(rms)}
    total = float(np.mean(residual * residual, dtype=np.float64))
    if not math.isclose(float(np.sum(power)), total, rel_tol=2e-10, abs_tol=1e-28):
        raise RuntimeError('Parseval verification failed')
    return {'residual_rms': math.sqrt(total), 'residual_dbfs_rms_equivalent': dbfs_equivalent(math.sqrt(total)),
            'fundamental_peak': float(np.hypot(*fitted[:2])),
            'dc': float(fitted[2]), 'bands': bands}


def render(binary: Path, root_temp: Path, src_path: Path, clock_name: str, version: str,
           halfband: np.ndarray, mastering: np.ndarray):
    rate = CLOCKS[clock_name]
    suffix = f'{clock_name}-{version}'
    packed, monitor = root_temp / (suffix + '.packed'), root_temp / (suffix + '.monitor.json')
    cmd = [str(binary), '--render', str(SAMPLE_HZ), str(rate),
           f'encode.mastering.{version}.{clock_name}', '.5', 'training',
           str(src_path), str(packed), str(monitor)]
    process = subprocess.run(cmd, cwd=ROOT, env={'LSX_DSD_SDM_KERNEL': 'scalar'},
                             capture_output=True, timeout=180, check=False)
    if process.returncode:
        raise RuntimeError(f'{suffix} render failed: {process.returncode}: '
                           + process.stderr.decode('utf-8', errors='replace')[-1200:])
    status = json.loads(monitor.read_text())
    if status['failure'] or status['nonfinite_states'] or status['committed_native_frames'] != round(1.6 * rate):
        raise RuntimeError(f'{suffix} failed its complete-frame and finite-state checks: {status}')
    hash_bits = sha256(packed.read_bytes())
    data = np.unpackbits(np.fromfile(packed, dtype=np.uint8), bitorder='big')
    pcm = (data.astype(np.float64) * 2.0) - 1.0
    del data
    num_stages = (rate // SAMPLE_HZ).bit_length() - 1
    for stage in range(num_stages):
        pcm = upfirdn(mastering if stage == num_stages - 1 else halfband, pcm, up=1, down=2)
    measurement = residual_and_bands(pcm)
    packed.unlink()
    monitor.unlink()
    return {'packed_sha256': hash_bits, 'native_frames': status['committed_native_frames'],
            'spectrum': measurement}


def check_reference(reproduced, clock_name, version):
    record = json.loads(ORIGINAL[clock_name].read_text())['versions'][version]
    if reproduced['packed_sha256'] != record['encoded_sha256']:
        raise RuntimeError(f'{clock_name}/{version} packed digest changed; refusing comparison')
    reported = record['diagnostic']['residual_dbfs_rms']
    actual = reproduced['spectrum']['residual_dbfs_rms_equivalent']
    if abs(actual - reported) > 0.001:
        raise RuntimeError(f'{clock_name}/{version} reproduction mismatch: {actual} vs {reported}')


def run(mode: str):
    binary = ROOT / 'test/dsd_test_p10'
    if not binary.is_file():
        raise RuntimeError('Build test/dsd_test_p10 before running this diagnostic')
    _, raw, source, exact = reference_source()
    if sha256(raw) != 'b8e8d07fa56c346147850c32e1faeead2ef3aab0dbd681435083176a8a52cd4d':
        raise RuntimeError('Frozen P19/P20 source digest changed')
    original = np.frombuffer(raw, dtype='<f8')
    target = np.frombuffer(exact, dtype='<f8')
    start, stop = int(.4 * SAMPLE_HZ), int(1.2 * SAMPLE_HZ)
    floor_rms = math.sqrt(float(np.mean(((original[start:stop] - target[start:stop]) / 2.) ** 2)))
    halfband = p20_audio_compare.coefficients('halfband')
    mastering = p20_audio_compare.coefficients('master64_256')
    result = {'schema': 'DSD-residual-asymmetry-diagnostic/2',
              'comparison_only': True, 'candidate_qualified': False,
              'reference_source_sha256': sha256(raw),
              'double_source_sha256': sha256(exact),
              'reference_coeff_sha256': p20_audio_compare.file_sha(p20_audio_compare.COEFF),
              'source_quantization_after_half_gain': {'rms': floor_rms,
                         'dbfs_rms_equivalent': dbfs_equivalent(floor_rms)},
              'analysis_window_seconds': [0.4, 1.2], 'pcm_sample_hz': SAMPLE_HZ,
              'spectrum_method': 'unwindowed Parseval rFFT of sin/cos/DC-fitted residual; contiguous disjoint bands',
              'sources': {}}
    with tempfile.TemporaryDirectory(prefix='dsd-asymmetry-') as scratch:
        tmp = Path(scratch)
        for precision, src in [('int32_equivalent', raw), ('unquantized_f64', exact)]:
            if mode != 'both' and precision != mode:
                continue
            src_path = tmp / (precision + '.f64le')
            src_path.write_bytes(src)
            result['sources'][precision] = {}
            for clock_name in ('dsd512', 'dsd1024'):
                result['sources'][precision][clock_name] = {}
                for version in ('v1', 'v2'):
                    measurement = render(binary, tmp, src_path, clock_name, version, halfband, mastering)
                    if precision == 'int32_equivalent':
                        check_reference(measurement, clock_name, version)
                    result['sources'][precision][clock_name][version] = measurement
                    print(precision, clock_name, version,
                          measurement['spectrum']['residual_dbfs_rms_equivalent'], flush=True)
    return result


def publish_write_once(path: Path, payload: bytes):
    """Atomically publish immutable evidence, allowing an identical replay."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.',
                                     suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise RuntimeError('Refusing to overwrite differing diagnostic evidence; use a new path')
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, type=Path, help='new write-once JSON path')
    parser.add_argument('--source', choices=('both', 'int32_equivalent', 'unquantized_f64'), default='both')
    args = parser.parse_args()
    try:
        results = run(args.source)
        payload = (json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        publish_write_once(args.results, payload)
        print('DIAGNOSTIC ONLY', args.results)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('RESIDUAL DIAGNOSTIC FAILED:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
