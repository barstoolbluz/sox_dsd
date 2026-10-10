#!/usr/bin/env python3
"""DSD numerical contract entry point, initially P00 measurement scaffolding.

Do not certify a DSD algorithm from legacy design-time filter feasibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import platform
import subprocess
import sys
import time
import wave

from reference import metrology, writer

ROOT = pathlib.Path(__file__).resolve().parents[2]


def self_checks() -> list[dict]:
    import numpy as np
    tests = []
    def test(name, fn):
        try:
            detail = fn()
            tests.append(dict(name=name, status='pass', detail=detail))
        except Exception as exc:
            tests.append(dict(name=name, status='fail', error=f'{type(exc).__name__}: {exc}'))

    def units():
        assert abs(metrology.band_dbfs(.5)) < 1e-12
        assert abs(metrology.band_dbfs(.125) + 6.02059991328) < 1e-10
        assert abs(metrology.snr_db(.5, .005) - 20) < 1e-12
        assert metrology.band_dbfs(0) == -math.inf
        return dict(sine_power_dbfs=metrology.band_dbfs(.5), quarter_sine_power_dbfs=metrology.band_dbfs(.125))
    test('normalized_power_dbfs_and_snr', units)

    def fit():
        rate, n, hz = 88200, 8820, 1000
        y = .17 + .25 * np.sin(2 * np.pi * hz * np.arange(n) / rate + .3)
        r = metrology.tone_fit(y, rate, hz)
        assert abs(r['peak_amplitude'] - .25) < 2e-12
        assert abs(r['dc'] - .17) < 2e-12
        assert abs(r['phase_rad'] - .3) < 2e-12
        assert float(np.max(np.abs(r['residual']))) < 2e-12
        return dict(fit_amplitude=r['peak_amplitude'], phase=r['phase_rad'], residual_peak=float(np.max(np.abs(r['residual']))))
    test('independent_analytic_tone_fit', fit)

    def window():
        w, enbw = metrology.blackman_harris4(4096)
        assert abs(enbw - 2.0043529382) < .00002
        assert abs(float(np.mean(w)) - .35875) < 1e-10
        noise = np.zeros(4096)
        assert metrology.baseband_residual_power(noise, 88200)['power'] == 0
        return dict(enbw_bins=enbw)
    test('window_coefficients_enbw', window)

    def source():
        rows = []
        for rate in (88200, 352800, 705600):
            path = ROOT / 'tests/dsd/fixtures' / f'pcm_sine_{rate}.wav'
            with wave.open(str(path), 'rb') as f:
                assert f.getframerate() == rate and f.getnchannels() == 1
                assert f.getsampwidth() == 2 and f.getnframes() == 4096
            rows.append(dict(rate_hz=rate, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return rows
    test('synthetic_pcm_sources', source)
    return tests


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', default='P00')
    ap.add_argument('--results', type=pathlib.Path, default=ROOT/'tests/dsd/results/P00/numeric')
    ap.add_argument('--prepare-analysis-v1', action='store_true', help='emit the immutable-design request, never claim generated coefficients')
    ap.add_argument('--sox', type=pathlib.Path, default=ROOT/'src/sox_ng')
    args = ap.parse_args()
    if args.phase not in ['P' + str(i).zfill(2) for i in range(19)]:
        ap.error('unknown phase')
    args.results.mkdir(parents=True, exist_ok=True)
    passed = self_checks()
    native_commands = []
    if int(args.phase[1:]) >= 1:
        from run import Runner
        observer = Runner(args)
        try:
            native = writer.cross_format(observer)
            passed.append(dict(name='P01_native_program_bits_and_completed_frame_counts',
                               status='pass', detail=native))
        except Exception as exc:
            passed.append(dict(name='P01_native_program_bits_and_completed_frame_counts',
                               status='fail', error=f'{type(exc).__name__}: {exc}'))
        native_commands = observer.commands
    p06_results = []
    if int(args.phase[1:]) >= 6:
        p06_steps = [
            ('P06_independent_coefficients_and_composites',
             [sys.executable, str(ROOT/'tests/dsd/certify_filters.py'),
              '--results', str(args.results)], 'filter-certificate.json'),
            ('P06_high_precision_finite_stream_oracle',
             [sys.executable, str(ROOT/'tests/dsd/test_decode.py'),
              '--unit', str(ROOT/'test/dsd_test_decode'),
              '--results', str(args.results/'scalar')], 'scalar/oracle.json'),
        ]
        for name, command, evidence in p06_steps:
            try:
                proc = subprocess.run(command, capture_output=True, text=True,
                                      cwd=ROOT, timeout=300)
                detail = dict(exit=proc.returncode,stdout=proc.stdout,
                              stderr=proc.stderr,evidence=evidence)
                p06_results.append(dict(name=name, status='pass' if proc.returncode==0 else 'fail',detail=detail))
            except (subprocess.TimeoutExpired,OSError) as exc:
                p06_results.append(dict(name=name,status='fail',error=str(exc)))
        passed.extend(p06_results)
    # P09 has an immutable, independently synthesized analysis reference.
    # Its self-tests must pass before running any candidate comparisons.
    p09_runs = []
    if int(args.phase[1:]) >= 9:
        base = ROOT / 'tests/dsd/reference/analysis-v1'
        tasks = [
            ('P09_frozen_analysis_selftests',
             [sys.executable, str(base/'verify.py'), '--results', str(args.results)],
             'analysis-v1-selftest.json'),
            ('P09_scalar_candidate_analysis_v1',
             [sys.executable, str(base/'measure_candidates.py'),
              '--unit', str(ROOT/'test/dsd_test_p09'),
              '--results', str(args.results/'candidate')],
             'candidate/candidate-analysis-v1.json'),
        ]
        for name, command, evidence in tasks:
            if name.endswith('analysis_v1') and any(r['status'] != 'pass' for r in p09_runs):
                p09_runs.append(dict(name=name, status='fail',
                                     reason='frozen analysis selftest failed; candidate measurement withheld'))
                continue
            try:
                proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1800)
                p09_runs.append(dict(name=name, status='pass' if proc.returncode==0 else 'fail',
                                     detail=dict(exit=proc.returncode,evidence=evidence,
                                                 stdout=proc.stdout,stderr=proc.stderr)))
            except (subprocess.TimeoutExpired,OSError) as exc:
                p09_runs.append(dict(name=name,status='fail',error=str(exc)))
        passed.extend(p09_runs)
    analysis_procedures = (dict(metrology.ANALYSIS_V1) if int(args.phase[1:]) < 9 else
             dict(reference='tests/dsd/reference/analysis-v1/manifest.json',
                  frozen_sha256=hashlib.sha256((ROOT/'tests/dsd/reference/analysis-v1/SHA256SUMS.txt').read_bytes()).hexdigest(),
                  verification='tests/dsd/reference/analysis-v1/verify.py',
                  scoring='tests/dsd/reference/analysis-v1/analyze.py'))
    result = dict(schema='dsd-numerical-results/1', phase=args.phase,
                  executed_command=sys.argv, utc_timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  python=platform.python_version(),
                  procedures=analysis_procedures,
                  source_fixture_catalog=str(ROOT/'tests/dsd/fixtures/manifest.json'),
                  unit_tests=passed,
                  native_commands=native_commands,
                  independent_analysis=(dict(status='frozen-selftests-passed',candidate_qualification='INCOMPLETE; P10 qualification and soak unrun')
                    if int(args.phase[1:])>=9 and p09_runs and all(r['status']=='pass' for r in p09_runs) else
                    dict(status='unrun-or-failed',reason='P09 analysis gate incomplete or failed')), 
                  filters_evidence=(dict(status='P06_certified_final_hex',
                      path='src/dsd_coeffs.h',
                      certificate='numeric/filter-certificate.json',
                      manifest='tests/dsd/reference/p06_coefficients.json',
                      sha256=hashlib.sha256((ROOT/'src/dsd_coeffs.h').read_bytes()).hexdigest())
                    if int(args.phase[1:])>=6 else dict(status='prior_design_evidence_only',
                       path='docs/dsd/evidence/filter_feasibility.json',
                       sha256=hashlib.sha256((ROOT/'docs/dsd/evidence/filter_feasibility.json').read_bytes()).hexdigest())),
                  quality_measurements=([dict(status='analytic-scalar-unqualified',
                    path='numeric/candidate/candidate-analysis-v1.json')] if int(args.phase[1:]) >= 9 else []),
                  summary=dict(passed=sum(x['status']=='pass' for x in passed),
                               failed=sum(x['status']=='fail' for x in passed),
                               unrun_gates=(['P10 full production PCM interpolation/filter qualification',
                                            'P10 30-minute per-rate and one-hour ISA soaks',
                                            'real-world independent DSD corpus'] if int(args.phase[1:])>=9 else
                                           ['analysis-v1 coefficient generation/certification' if int(args.phase[1:])<6
                                             else 'P09 analysis-v1 audio corpus qualification',
                                            'independent DSD quality measurements'])))
    report_path=args.results/'measure.json'
    if report_path.exists():
        old=report_path.read_bytes()
        try:
            previous=json.loads(old)
            if previous.get('summary',{}).get('failed',0):
                backup=report_path.with_name('measure-failed-'+hashlib.sha256(old).hexdigest()[:16]+'.json')
                if not backup.exists():backup.write_bytes(old)
        except ValueError:
            pass
    temp=report_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temp.replace(report_path)
    if args.prepare_analysis_v1:
        (args.results/'analysis-v1-request.json').write_text(
            json.dumps(metrology.ANALYSIS_V1, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'schema':result['schema'], 'summary':result['summary'],
                      'result_path':str(args.results/'measure.json')}))
    return int(result['summary']['failed'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
