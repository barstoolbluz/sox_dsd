#!/usr/bin/env python3
"""P112: measured shipped mastering paths including the final private PCM SRC.

Numerical rejection uses the *linear* production FIR, P07 SRC and the P10
read-only encoder stage observer. Actual SDM-8 file roundtrips are reported
separately; their quantization noise is never treated as a transfer function.
The SRC scan is sampled, not a proof of a continuous worst-case bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np

DSD = Path(__file__).resolve().parents[1]
ROOT = DSD.parents[1]
sys.path[:0] = [str(DSD / name) for name in
                ('checks', 'support', 'qualification', 'phases')]

from certify_filters import load_coefficients, hp_composite
from current_mastering_112 import read_current_mastering
from p15_src_bound_operator import load_snapshot, sha_file
from test_passband_112 import call, projected_tone, stimulus, SOURCE_RATE
import test_p07_composite as p07
from test_p17_numeric import composed_taps

# Three amended mastering profiles; no alias or versioned selector is introduced.
TONES = {256: 50000, 512: 72000, 1024: 110000}
SRC_LENGTH_SECONDS = 2   # Middle full second is coherent at every 100-Hz scan point.
P07_NATIVE_FRAMES = 1 << 20
P17_NATIVE_FRAMES = 32769
PASS_TOLERANCE_DB = 0.0001     # DSD_DESIGN.md 6.1, also P112 FIR qualification
REJECTION_DB = -160.0         # DSD_DESIGN.md 6.1
P07_INTERIOR_TOLERANCE = 2e-9  # Existing P07 independent-composite comparator


def run_raw(binary, *args, input_bytes=None):
    command = [str(binary.resolve()), *map(str, args)]
    cp = subprocess.run(command, input=input_bytes, capture_output=True, timeout=180)
    if cp.returncode:
        raise AssertionError(f'{command}: rc={cp.returncode}: '
                             + cp.stderr.decode(errors='replace')[-600:])
    return cp.stdout


def db(amplitude):
    return 20 * math.log10(max(float(amplitude), 1e-300))


def tone_projection(data: bytes, output_hz: int, input_tone: int):
    samples = np.frombuffer(data, dtype='<f8')
    expected = SRC_LENGTH_SECONDS * output_hz
    assert samples.size == expected and np.all(np.isfinite(samples)), (samples.size, expected)
    mid = samples[expected // 4:3 * expected // 4]
    folded = abs((input_tone + output_hz // 2) % output_hz - output_hz // 2)
    # Coherent projection: exactly one second, every stimulus is a multiple of
    # 100 Hz. Frequencies are above zero and below the *output* Nyquist.
    assert 0 < folded < output_hz / 2 and input_tone % 100 == 0
    indices = np.arange(expected // 4, 3 * expected // 4, dtype=np.float64)
    phasor = np.exp((-2j * np.pi * folded / output_hz) * indices)
    amplitude = 2 * abs(np.dot(mid, phasor)) / mid.size
    rms = float(np.sqrt(np.mean(mid * mid)))
    # The projection measures the predicted folded frequency only. The RMS
    # equivalent also detects *other* images, whose presence a single-bin
    # projection could hide (especially for rational-rate conversion).
    all_output_db = db(rms / (.5 / math.sqrt(2.)))
    coherent_db = db(amplitude / .5)
    return dict(input_frequency_hz=input_tone, folded_output_hz=folded,
                observed_gain_db=coherent_db,
                all_output_rms_equivalent_gain_db=all_output_db,
                conservative_alias_gain_db=max(coherent_db, all_output_db),
                projected_amplitude=float(amplitude), steady_rms=rms)


def src_case(unit, R, F, freq):
    actual = run_raw(unit, '--tone', R, F, R * SRC_LENGTH_SECONDS, freq)
    row = tone_projection(actual, F, freq)
    row['output_sha256'] = hashlib.sha256(actual).hexdigest()
    return row


def frequency_grid(R, F, max_pass, profile_stop_edges):
    """Sample pass / complete SRC rejection interval at 100-Hz harmonics.

    Stop begins at F/2, and extends to the input Nyquist R/2. The exact
    Nyquist endpoint is excluded: a sine there becomes zero or ambiguous.
    Edge-adjacent points and the full interior are included. This is a
    numerical *sample*, never called a global extrema certificate.
    """
    pass_edge = int(min(max_pass, .475 * min(R, F)) // 100) * 100
    assert pass_edge >= 1000 and R > F
    pass_freqs = sorted({int(x // 100) * 100 for x in np.linspace(1000, pass_edge, 25)})
    stop_start = F // 2
    stop_end = R // 2
    stop_freqs = sorted({stop_start + n for n in (100, 200, 500, 1000, 2000, 5000)
                         if stop_start + n < stop_end}
                        | {int(x // 100) * 100 for x in
                           np.linspace(stop_start + 100, stop_end - 100, 35)})
    stop_freqs = sorted(set(stop_freqs) | {s for s in profile_stop_edges if F / 2 < s < R / 2})
    assert all(0 < f < F / 2 for f in pass_freqs)
    assert all(F / 2 < f < R / 2 for f in stop_freqs)
    return pass_freqs, stop_freqs


def capture_source_src(exporter, R, F, folder):
    """Capture P15's actual runtime-design stage coefficients, source-bound.

    P15's historical source_identity() lists the retired dsd_coeffs_v2.h;
    that certificate must not be silently extended to 1.1.2. Bind a fresh
    P112 receipt to the concrete files this exporter uses instead.
    """
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / 'stage-snapshot.json'
    run_raw(exporter, R, F, snapshot)
    op = load_snapshot(snapshot)  # Also verifies captured FFT4G packed bins.
    assert (op.input_hz, op.output_hz) == (R, F)
    sources = ('src/rate.c', 'src/rate_internal.h', 'src/rate_filters.h',
               'src/rate_half_fir.h', 'src/rate_poly_fir.h',
               'src/rate_poly_fir0.h', 'src/dft_filter.c', 'src/fft4g.c',
               'tests/dsd/native/test_p15_src_stage_export.c')
    binding = dict(schema='P112/source-bound-private-SRC-stages/1',
                   profile='source-captured coefficient/clock identity, NOT a certificate',
                   input_hz=R, output_hz=F, stage_count=len(op.stages),
                   snapshot_sha256=sha_file(snapshot),
                   exporter_sha256=sha_file(exporter),
                   source_sha256={name:sha_file(ROOT / name) for name in sources})
    (folder / 'operator-binding.json').write_text(json.dumps(binding, sort_keys=True, indent=2) + '\n')
    return binding, op


def native_oracle(p17_unit, native, meta, banks):
    """P17's long-double direct convolution, independently of the C kernel."""
    N = P17_NATIVE_FRAMES
    rng = np.random.default_rng(0x1122026 + native)
    bits = rng.integers(0, 2, N, dtype=np.uint8)
    out = run_raw(p17_unit, 'export', native, 0, 1, N, input_bytes=bits.tobytes())
    got = np.frombuffer(out, dtype='<f8')
    D, G = meta['factor'], meta['delay_native_frames']
    assert got.size == (N + D - 1) // D
    taps, bound = composed_taps(banks, meta['stage_banks'])
    assert taps.size == 2 * G + 1
    indices = sorted({0, 1, 2, 3, got.size // 2, got.size - 4,
                      got.size - 3, got.size - 2, got.size - 1})
    errors = []
    tap_idx = np.arange(taps.size, dtype=np.int64)
    for n in indices:
        ix = G + n * D - tap_idx
        selected = (ix >= 0) & (ix < N)
        vals = (2 * bits[ix[selected]].astype(np.int16) - 1).astype(np.longdouble)
        reference = float(np.sum(vals * taps[selected].astype(np.longdouble), dtype=np.longdouble))
        errors.append(abs(reference - float(got[n])))
    assert max(errors) <= bound, (native, max(errors), bound)
    return dict(native_hz=native, output_hz=meta['intermediate_hz'],
                finite_samples=len(indices), largest_error=max(errors),
                p17_independent_fir_bound=bound,
                output_sha256=hashlib.sha256(out).hexdigest())


def composite_oracle(p07_unit, native, meta, banks, output):
    """P07's independent full finite convolution and separate 180-dB SRC.

    P07's endpoints are not identical for distinct FIR window designs. The
    inherited 2e-9 *interior* tolerance applies here; report all endpoints
    without silently extending the old .0085 endpoint tolerance to these
    higher-clock fixtures, where it is not a numerical transfer contract.
    """
    N = P07_NATIVE_FRAMES
    actual = run_raw(p07_unit, '--dsd', native, output, 0, N)
    got = np.frombuffer(actual, dtype='<f8')
    expected = (N * output + native // 2) // native
    assert got.size == expected
    p07.N = N
    independent = p07.reference('mastering-112', meta, output, banks)[:expected]
    assert len(independent) == expected
    error = np.abs(got - independent)
    edge = max(64, got.size // 10)
    interior = error[edge:-edge]
    assert interior.size and np.isfinite(error).all()
    inside = float(np.max(interior))
    assert inside <= P07_INTERIOR_TOLERANCE, (native, output, inside)
    return dict(native_hz=native, output_hz=output, output_frames=expected,
                p07_independent_interior_abs_max=inside,
                p07_independent_full_endpoint_abs_max=float(np.max(error)),
                p07_interior_limit_abs=P07_INTERIOR_TOLERANCE,
                endpoint_policy='measured diagnostic; distinct SRC window designs; '
                                'historical P07 .0085 endpoint tolerance is not reassigned',
                output_sha256=hashlib.sha256(actual).hexdigest())


def encoder_stages(unit, native, tone, source=SOURCE_RATE):
    # Existing read-only P10 observer; the narrow test-only tone fixture was
    # added without changing the production encoder or observer hook.
    raw = run_raw(unit, '--stage-probe', native, source, f'tone:{tone}', '.08')
    record = json.loads(raw)
    assert record['status'] == 3 and record['failure'] == 0, record
    stage = record['stages']
    needed = ('source', 'R_SRC', 'R_prefilter', 'native_SRC', 'scaled_modulator_input')
    assert all(stage[x]['steady_count'] > 1000 and stage[x]['steady_rms'] > 0
               for x in needed)
    rms = {name:stage[name]['steady_rms'] for name in needed}
    src_gain = db(rms['R_SRC'] / rms['source'])
    fir_gain = db(rms['R_prefilter'] / rms['R_SRC'])
    linear_gain = db(rms['native_SRC'] / rms['source'])
    scale = rms['scaled_modulator_input'] / rms['native_SRC']
    assert abs(scale - .5) <= 1e-12, scale
    return dict(native_hz=native, source_hz=source, input_tone_hz=tone,
                source_src_gain_db=src_gain, production_fir_gain_db=fir_gain,
                linear_through_native_src_gain_db=linear_gain,
                modulator_reference_scale=scale, stage_rms=rms,
                observer_receipt_sha256=hashlib.sha256(raw).hexdigest(),
                statement='RMS ratio of coherent safe-level tone at read-only linear '
                          'handoffs before nonlinear SDM-8; no output DSD noise used')


def cli_roundtrips(sox, root, rates):
    rows = []
    for rate, meta in rates.items():
        tone = TONES[rate]
        inp = root / f'{rate}-{tone}.wav'
        stimulus(inp, tone, 'wide')
        dsd = root / f'{rate}-{tone}.dsf'
        call(sox, '-D', inp, '-r', meta['native_hz'], dsd)
        for F in (meta['intermediate_hz'], 176400, 192000):
            target = root / f'{rate}-{tone}-{F}.f64'
            call(sox, '--dsd-layout-loss', 'warn', '-D', dsd, '-t', 'f64', '-r', F, target)
            alias = abs((tone + F // 2) % F - F // 2)
            amp, frames = projected_tone(target, F, alias)
            # P112's established survival threshold applies where both
            # native mastering and final PCM output can preserve the tone.
            if tone < min(meta['pass_hz'], .475 * F):
                assert amp >= .03, (rate, F, amp)
            rows.append(dict(dsd=rate, input_tone_hz=tone, output_hz=F,
                             folded_hz=alias, decoded_tone_projection=float(amp),
                             frames=frames, output_sha256=sha_file(target),
                             verdict='nonlinear SDM-8 integration diagnostic, '
                                     'not a filter stopband certificate'))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('sox', 'p07-unit', 'p10-unit', 'p17-unit', 'stage-exporter'):
        p.add_argument('--' + field, type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--snapshots', type=Path,
                   help='Optional copy of the exact production SRC stage capture receipts')
    a = p.parse_args()
    for field in ('sox', 'p07_unit', 'p10_unit', 'p17_unit', 'stage_exporter'):
        assert getattr(a, field).is_file(), f'not built: {field}'
    current, amended = read_current_mastering()
    banks = load_coefficients()
    banks.update(amended)
    meta = {}
    for rate, tone in TONES.items():
        m = current[f'dsd{rate}']
        meta[rate] = dict(m, stage_banks=['halfband']*(m['stages']-1)
                          + ['master112_' + m['bank']])
        assert m['pass_hz'] > tone
    fir_points, p17_cases, p07_cases, encoder_cases = [], [], [], []
    src_scans, src_snapshots = [], []
    with tempfile.TemporaryDirectory(prefix='p112-complete-') as tmp:
        base = Path(tmp)
        for rate, m in meta.items():
            tone = TONES[rate]
            native = m['native_hz']
            h = float(abs(hp_composite(banks, m['stage_banks'], native, tone)))
            assert abs(db(h)) <= PASS_TOLERANCE_DB
            fir_points.append(dict(dsd=rate, tone_hz=tone,
                                   linear_decoder_frontend_gain_db=db(h),
                                   full_native_cascade_banks=m['stage_banks']))
            if rate in (512, 1024):
                p17_cases.append(native_oracle(a.p17_unit, native, m, banks))
            for F in sorted({m['intermediate_hz'], 176400, 192000}):
                p07_cases.append(composite_oracle(a.p07_unit, native, m, banks, F))
            for f, kind in ((tone, 'pass'), (m['stop_hz'] + 5000, 'stop')):
                obs = encoder_stages(a.p10_unit, native, f)
                if kind == 'pass':
                    assert abs(obs['source_src_gain_db']) <= PASS_TOLERANCE_DB
                    assert abs(obs['production_fir_gain_db']) <= PASS_TOLERANCE_DB
                    assert abs(obs['linear_through_native_src_gain_db']) <= PASS_TOLERANCE_DB
                else:
                    assert obs['production_fir_gain_db'] <= REJECTION_DB
                obs['band'] = kind
                encoder_cases.append(obs)

        max_pass = {352800: 88200, 705600: 120000}
        for R in (352800, 705600):
            for F in (176400, 192000):
                pair = f'{R}-{F}'
                folder = base / pair
                binding, op = capture_source_src(a.stage_exporter, R, F, folder)
                assert (op.input_hz, op.output_hz) == (R, F)
                src_snapshots.append(dict(input_hz=R, output_hz=F,
                    captured_stages=len(op.stages),
                    stage_kinds=[s.kind for s in op.stages],
                    snapshot_sha256=binding['snapshot_sha256'],
                    exporter_sha256=binding['exporter_sha256'],
                    source_sha256=binding['source_sha256']))
                if a.snapshots:
                    dest = a.snapshots / pair
                    dest.mkdir(parents=True, exist_ok=True)
                    for name in ('stage-snapshot.json', 'operator-binding.json'):
                        shutil.copyfile(folder / name, dest / name)
                passes, stops = frequency_grid(R, F, max_pass[R],
                    [m['stop_hz'] for m in meta.values() if m['intermediate_hz'] == R])
                pass_rows = [src_case(a.p07_unit, R, F, f) for f in passes]
                stop_rows = [src_case(a.p07_unit, R, F, f) for f in stops]
                bad_pass = max(pass_rows, key=lambda x:abs(x['observed_gain_db']))
                worst_stop = max(stop_rows, key=lambda x:x['conservative_alias_gain_db'])
                assert abs(bad_pass['observed_gain_db']) <= PASS_TOLERANCE_DB, (R, F, bad_pass)
                assert worst_stop['conservative_alias_gain_db'] <= REJECTION_DB, (R, F, worst_stop)
                src_scans.append(dict(input_hz=R, output_hz=F,
                    promised_pass_hz=min(max_pass[R], .475 * min(R, F)),
                    final_pcm_nyquist_hz=F / 2, input_nyquist_hz=R / 2,
                    sampled_pass_max_abs_db=abs(bad_pass['observed_gain_db']),
                    sampled_pass_worst=bad_pass,
                    sampled_stop_worst_db=worst_stop['conservative_alias_gain_db'],
                    sampled_stop_worst=worst_stop,
                    pass_points=pass_rows, stop_points=stop_rows,
                    sampled_not_global_bound=True))
        explicit, stop_edges = [], []
        for rate, m in meta.items():
            tone = TONES[rate]
            fir = next(x['linear_decoder_frontend_gain_db'] for x in fir_points if x['dsd'] == rate)
            for F in sorted({m['intermediate_hz'], 176400, 192000}):
                src = (dict(observed_gain_db=0., folded_output_hz=tone)
                       if F == m['intermediate_hz'] else src_case(a.p07_unit, m['intermediate_hz'], F, tone))
                result = fir + src['observed_gain_db']
                conservative = fir + src.get('conservative_alias_gain_db', 0.)
                should_pass = tone < min(m['pass_hz'], .475 * F)
                if should_pass:
                    assert abs(result) <= PASS_TOLERANCE_DB, (rate, F, result)
                else:
                    assert conservative <= REJECTION_DB, (rate, F, conservative)
                explicit.append(dict(dsd=rate, input_tone_hz=tone,
                    intermediate_hz=m['intermediate_hz'], output_hz=F,
                    folded_output_hz=src['folded_output_hz'],
                    decoder_linear_fir_db=fir, final_production_src_db=src['observed_gain_db'],
                    observed_composite_linear_transfer_db=result,
                    conservative_all_output_alias_db=conservative,
                    expected='passband' if should_pass else 'final-SRC alias rejection',
                    requirement_db=PASS_TOLERANCE_DB if should_pass else REJECTION_DB))
                # Measure every *specified* new mastering stop edge through
                # the same complete FIR/SRC path. The FIR independently
                # qualifies the entire stopband, not only these edge points.
                edge = m['stop_hz']
                edge_fir = db(abs(hp_composite(banks, m['stage_banks'], m['native_hz'], edge)))
                edge_src = (0. if F == m['intermediate_hz'] else
                            src_case(a.p07_unit, m['intermediate_hz'], F, edge)
                            ['conservative_alias_gain_db'])
                assert edge_fir + edge_src <= REJECTION_DB
                stop_edges.append(dict(dsd=rate, decoder_stop_edge_hz=edge,
                    output_hz=F, production_fir_stop_edge_db=edge_fir,
                    production_src_all_output_gain_db=edge_src,
                    conservative_composite_stop_edge_db=edge_fir+edge_src))
        cli = cli_roundtrips(a.sox, base, meta)

    result = dict(schema='sox-dsd/1.1.2/full-path-qualification/1',
        status='PASS_SAMPLED_NUMERICAL_AND_FINITE_ORACLES',
        source='shipped P112 hex FIRs, production P07 binary64 SRC, '
               'source-bound P15 SRC design-stage capture, P17 scalar frontend, '
               'P10 read-only pre-SDM observer, and actual SoX DSD/PCM CLI',
        threshold_source='docs/dsd/DSD_DESIGN.md 6.1; P07 inherited 2e-9 interior comparator',
        thresholds=dict(passband_abs_db=PASS_TOLERANCE_DB,
                        sampled_rejection_max_db=REJECTION_DB,
                        p07_interior_abs=P07_INTERIOR_TOLERANCE),
        limitation='SRC and complete output-ratio scans are sampled; '
                   'source-bound stage captures pin the actual SRC design, '
                   'but neither sample search nor the nonlinear SDM result '
                   'is a continuum or floating-point roundoff proof',
        fir_points=fir_points, p17_native_oracle=p17_cases,
        p07_full_composite=p07_cases, encoder_read_only_stages=encoder_cases,
        src_source_bound_snapshots=src_snapshots,
        src_frequency_scans=src_scans,
        composite_linear_tones=explicit,
        composite_stop_edges=stop_edges,
        nonlinear_cli_roundtrips=cli,
        summary=dict(profiles=len(meta), full_composite_cases=len(p07_cases),
                     p17_frontends=len(p17_cases), encoder_stage_cases=len(encoder_cases),
                     src_ratios=len(src_scans), scanned_src_tones=sum(
                         len(x['pass_points'])+len(x['stop_points']) for x in src_scans),
                     composed_linear_tones=len(explicit),
                     composite_stop_edges=len(stop_edges), cli_roundtrips=len(cli)))
    a.results.parent.mkdir(parents=True, exist_ok=True)
    tmp_out=a.results.with_suffix('.tmp')
    tmp_out.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp_out.replace(a.results)
    print(json.dumps(result['summary'], sort_keys=True))
    for row in explicit:
        print('DSD', row['dsd'], '->', row['output_hz'],
              row['expected'], f'{row["observed_composite_linear_transfer_db"]:.2f} dB')


if __name__ == '__main__':
    main()
