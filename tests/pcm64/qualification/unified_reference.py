#!/usr/bin/env python3
"""Independent finite-stream witness for the Phase 08 unified decoder.

The expected values are computed from the pinned C coefficient *data*, not the
C FIR, decoder API, CLI, planner, rate converter, or SIMD kernels. A separate
linear-convolution implementation handles causal zero extension and physical
DSD chronology. Run only at the native intermediate PCM rate, so the unproved
post-decimator SRC bound is not silently included in this witness.

This finite corpus is *not* an accepted reference under owner decision D13.
D16's new-reference sign-off and the universal P3 proof remain OPEN.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests/pcm64'))
sys.path.insert(0, str(ROOT / 'tests/dsd/reference'))
from decode import parse_wav
import fixtures

# This hash is of the immutable v1 coefficient manifest at 595d401, not of a
# value regenerated from a candidate binary. Its acceptance remains subject to D13.
COEFFICIENT_MANIFEST_SHA256 = '853c3e4c1902124513d99706a40a08c9b33363f7e18810ec41a955ab0b598d17'
PROFILES = ('mastering', 'wideband')
RATES = (fixtures.DSD64, 2 * fixtures.DSD64)
PATTERNS = ('random', 'distinct', 'zeros', 'ones', '69')
U = 2.0 ** -53


def demand(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def banks() -> dict[str, np.ndarray]:
    source = ROOT / 'src/dsd_coeffs.h'
    demand(hashlib.sha256(source.read_bytes()).hexdigest() == COEFFICIENT_MANIFEST_SHA256,
           'unapproved change to unified decoder coefficient manifest (D13)')
    entries = re.findall(r'static const double lsx_dsd_coeff_(\w+)\[(\d+)\] = \{(.*?)\};',
                         source.read_text(), re.S)
    result = {}
    for name, size, initializer in entries:
        tokens = re.findall(r'[-+]?0x[0-9a-fA-F.]+p[-+]?\d+', initializer)
        demand(len(tokens) == int(size), f'coefficient count mismatch for {name}')
        # Python.fromhex consumes the same exact binary64 coefficients as C.
        result[name] = np.array([float.fromhex(v) for v in tokens], dtype=np.longdouble)
    demand(set(result) == {'halfband', 'master64_256', 'master128', 'wideband'},
           'unexpected unified decoder bank set')
    return result


def independent_reconstruction(bits: bytes, rate: int, profile: str,
                               coeff: dict[str, np.ndarray]):
    """Causal high-precision full convolution, without a production FIR call."""
    tail = ('wideband' if profile == 'wideband' else
            'master64_256' if rate == fixtures.DSD64 else 'master128')
    stages = [coeff['halfband']] * 4 + [coeff[tail]]
    # Independent group-delay expression: sum of each symmetric FIR midpoint,
    # expressed in original native-bit clock units.
    delay = sum((len(h) // 2) * (1 << stage) for stage, h in enumerate(stages))
    factor = 1 << len(stages)
    frames = (len(bits) + factor // 2) // factor
    native = np.frombuffer(bits, dtype=np.uint8)
    demand(np.all(native <= 1), 'nonbinary physical bit chronology')
    # Explicit future zero extension, including enough frames for all final
    # centered outputs. Padding never invents physical DSD bits.
    samples = np.pad(native.astype(np.longdouble) * 2 - 1,
                     (0, 4 * delay + 3 * factor), mode='constant')
    # A priori arithmetic envelope: each convolution has at most L products
    # and L-1 additions. The conservative 2*L+4 gamma also covers the
    # production's center-pair organization. Conditioned on IEEE RN,
    # gradual underflow, no exceptional nonfinite values, no FTZ/DAZ.
    max_abs, error_envelope = 1., 0.
    for stage, h in enumerate(stages):
        L = len(h)
        h_l1 = float(np.sum(np.abs(h), dtype=np.longdouble))
        gamma = ((2 * L + 4) * U) / (1 - (2 * L + 4) * U)
        error_envelope = (h_l1 * error_envelope +
                          gamma * h_l1 * max_abs + L * 2.0 ** -1022)
        max_abs *= h_l1
        # Alternative arithmetic and scheduling: linear convolution followed
        # by parity decimation, not mirrored rings or centered coefficient pairs.
        samples = np.convolve(samples, h, mode='full')[:len(samples)]
        samples = samples[(delay >> stage) & 1::2]
    expected = samples[delay // factor:delay // factor + frames]
    demand(len(expected) == frames, 'independent zero-extension/count error')
    # Include independent long-double evaluation error conservatively. This
    # test does not pretend to discharge the full-source-SRC P2/P3 proof.
    tolerance = 4 * error_envelope
    return expected.astype(np.float64), tolerance, delay


def run(sox: Path, results: Path):
    coeff = banks()
    results.mkdir(parents=True, exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix='phase08-independent-') as scratch:
        work = Path(scratch)
        for rate in RATES:
            for profile in PROFILES:
                for n, pattern, channels in ((1, 'ones', 1), (7, '69', 2),
                                             (31, 'distinct', 1), (33, 'random', 2),
                                             (257, 'zeros', 2), (1025, 'ones', 2),
                                             (8193, 'random', 2), (32769, 'distinct', 2)):
                    binary = fixtures.bits(n, channels, pattern)
                    src = work / 'physical.dsf'
                    dst = work / 'actual.wav'
                    src.write_bytes(fixtures.make_dsf(binary, rate))
                    hz = rate // 32
                    for backend in ('scalar', 'auto'):
                        cmd = [str(sox), '--precision', '64', '--decode',
                               f'decode.{profile}.dsd{rate // 44100}',
                               '--dsd-level', 'preserve', '--dsd-bandwidth', 'strict',
                               str(src), '-b', '64', '-e', 'floating-point',
                               '-r', str(hz), str(dst)]
                        env = dict(os.environ, SOX_DSD_KERNEL_FIR=backend)
                        cp = subprocess.run(cmd, capture_output=True, env=env, timeout=40)
                        demand(cp.returncode == 0,
                               f'{profile}/{rate}/{backend}: {cp.stderr[-400:]!r}')
                        frames = (n + 16) // 32
                        payload, _ = parse_wav(dst, frames, channels, hz)
                        actual = np.frombuffer(payload, dtype='<f8').reshape(frames, channels)
                        comparisons = []
                        for channel, bits in enumerate(binary):
                            ideal, tolerance, delay = independent_reconstruction(
                                bits, rate, profile, coeff)
                            observed = actual[:, channel]
                            difference = float(np.max(np.abs(observed - ideal))) if frames else 0.
                            demand(np.isfinite(observed).all() and difference <= tolerance,
                                   f'independent DSD mismatch {rate}/{profile}/{backend}/'
                                   f'{pattern}/ch{channel}: {difference} > {tolerance}')
                            comparisons.append({'channel': channel, 'absolute_error_max': difference,
                                                'conditional_envelope': tolerance,
                                                'delay_native_frames': delay})
                        cases.append({'native_hz': rate, 'pcm_hz': hz, 'profile': profile,
                                      'backend': backend, 'native_frames': n,
                                      'pcm_frames': frames, 'channels': channels,
                                      'pattern': pattern, 'samples': comparisons,
                                      'physical_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                                      'actual_words_sha256': hashlib.sha256(payload).hexdigest()})
    # An independent regression self-test must detect changed chronology.
    arbitrary, _, _ = independent_reconstruction(fixtures.bits(8193, 1, 'random')[0],
                                                   fixtures.DSD64, 'mastering', coeff)
    demand(np.max(np.abs(arbitrary[1:] - arbitrary[:-1])) > 1e-5,
           'phase-shift negative control cannot detect a one-frame error')
    return {'schema': 'phase08-unified-independent/1',
            'status': 'PASS_FINITE_WITNESSES_ONLY',
            'd16_reference_approval': 'OPEN',
            'd11_p3_universal_bound': 'OPEN',
            'coefficient_manifest_sha256': COEFFICIENT_MANIFEST_SHA256,
            'numeric_method': 'long-double full convolution of pinned exact binary64 taps, half-open parity decimation',
            'bound_basis': 'per-stage gamma(2*taps+4) L1 propagation, IEEE round-to-nearest, gradual underflow',
            'scope': 'native DSD64/128 to intermediate rate only; no output SRC',
            'longdouble_mantissa_bits': int(np.finfo(np.longdouble).nmant) + 1,
            'cases': cases, 'case_count': len(cases)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    try:
        record = run(args.sox.resolve(), args.results)
    except Exception as exc:
        record = {'status': 'FAIL', 'error': str(exc),
                  'd16_reference_approval': 'OPEN'}
    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / 'unified-reference.json').write_text(
        json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(f"{record['status']} unified decoder independent witness: "
          f"{record.get('case_count', 0)} cases")
    if record['status'] == 'FAIL':
        print(record['error'], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
