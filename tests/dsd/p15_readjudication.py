#!/usr/bin/env python3
"""Independent, fail-closed P15 R2 receipt inspection; never activates release.

The archived measurements remain immutable. This tool examines existing bytes,
records bounded dispositions and writes a NEW deterministic JSON file. Successful
inspection is not equivalent to qualification or to authorizing P16.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

import numpy as np

from p15_matrix_receipt_review import review as inspect_matrix
from soak_p10 import configuration

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'tests/dsd/results'
R2 = RESULTS / 'P15_matrix_metrology_R2_2026-10-14'
PER_PROFILE = RESULTS / 'P15_dsd256_2x_per_profile_2026-10-15'
SOAKS = RESULTS / 'P15_soaks_every_profile_isa_2026-10-13'
AMENDMENT = ROOT / 'docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md'
DESIGN = ROOT / 'docs/dsd/DSD_DESIGN.md'
RATES = (2822400, 5644800, 11289600)
TIERS = ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')
RATE_TARGETS = (176400, 352800)
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
HEX16 = re.compile(r'[0-9a-f]{16}\Z')


class EvidenceError(ValueError):
    """Supplied evidence or supported claim failed independent checks."""


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise EvidenceError(reason)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fd:
        for chunk in iter(lambda: fd.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check_state(file: Path) -> dict:
    """Inspect complete serialized state shape, counters, and numerical finiteness.

    This does not replay the corresponding hour of audio; those native samples
    and the exact original test executable are not in the source archive.
    """
    lines = file.read_text(encoding='ascii').splitlines()
    need(len(lines) == 39 and lines[0] == 'P10-continuation-v1',
         'unexpected P10 state version/shape: ' + file.name)
    pairs = [line.split('=', 1) for line in lines[1:]]
    need(all(len(pair) == 2 for pair in pairs), 'invalid state key/value')
    d = dict(pairs)
    expected = {'input', 'native', 'bits_fnv64', 'bank', 'previous',
                'history', 'ones', 'history_bits', 'run', 'last',
                'windows', 'excursions', 'longest', 'peak'}
    expected.update(f'state{channel}_{i}' for channel in (0, 1) for i in range(8))
    expected.update(f'maximum{i}' for i in range(8))
    need(len(d) == 38 and set(d) == expected, 'duplicate/missing state fields')
    integers = ('input', 'native', 'bank', 'history', 'ones', 'history_bits',
                'run', 'last', 'windows', 'excursions', 'longest')
    out = {}
    for k in integers:
        try:
            out[k] = int(d[k], 10)
        except ValueError as e:
            raise EvidenceError('nondecimal state counter: ' + k) from e
        need(out[k] >= 0, 'negative state counter: ' + k)
    need(HEX16.fullmatch(d['bits_fnv64']) is not None, 'malformed state trajectory hash')
    need(out['history_bits'] == 28 and 0 <= out['ones'] <= 28 and
         out['last'] in (0, 1), 'invalid monitor/chronology shape')
    floats = ('previous', 'peak', *(f'state{j}_{i}' for j in (0, 1) for i in range(8)),
              *(f'maximum{i}' for i in range(8)))
    for k in floats:
        try:
            v = float.fromhex(d[k])
        except ValueError as e:
            raise EvidenceError('invalid binary64 continuation value: ' + k) from e
        need(math.isfinite(v), 'nonfinite continuation state: ' + k)
        out[k] = v
    return out


def inspect_soak_run(folder: Path, native: int, guards: dict) -> dict:
    ident = f'soak-{native}'
    report_file = folder / (ident + '-result.json')
    exec_file = folder / (ident + '-execution.json')
    conf_file = folder / (ident + '-configuration.json')
    report, execution, config = map(read_json, (report_file, exec_file, conf_file))
    expected = configuration(native, seconds=3600, segment=60, fixture='nominal-v2')
    need(config == expected, 'soak configuration inconsistent: ' + folder.name + '/' + ident)
    need(report.get('schema') == 'P10/candidate-render/1' and
         report.get('profile') == f'encode.mastering.v1.dsd{native // 44100}' and
         report.get('qualification') == 'UNQUALIFIED' and
         report.get('mode') == 'soak-nominal-v2' and
         report.get('status') == 3 and report.get('failure') == 0 and
         report.get('first_bad_frame') is None and
         report.get('native_hz') == native and
         report.get('source_hz') == expected['source_hz'],
         'soak profile/status/identity differs: ' + folder.name + '/' + ident)
    need(all(report.get(k) == v for k, v in (
         ('input_frames', 3600 * expected['source_hz']),
         ('processed_native_frames', 3600 * native),
         ('committed_native_frames', 3600 * native),
         ('windows28', 3600 * native - 27),
         ('nonfinite_states', 0),
         ('monitor_overloads_nominal_half', 0))),
         'soak counts or monitor differ: ' + folder.name + '/' + ident)
    need(isinstance(report.get('peak'), (int, float)) and
         math.isfinite(report['peak']) and 0 <= report['peak'] <= .5 + 1.0 / (2**31-1),
         'soak peak outside admission envelope: ' + folder.name)
    maxima = report.get('max_abs_state')
    bounds = guards['profiles'][str(native)]['bounds']
    need(isinstance(maxima, list) and len(maxima) == len(bounds) == 8 and
         all(isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x <= y
             for x, y in zip(maxima, bounds)), 'soak state guard violated')
    if native == RATES[0]:
        need(report.get('excursions28') == 0 and
             4 <= report.get('min_ones28', -1) <= report.get('max_ones28', 99) <= 24,
             'DSD64 28-bit population violation')
    expected_cmd = ['test/dsd_test_p10', '--soak-nominal-v2', str(native),
                    '3600', '60', f'<results>/{ident}']
    need(execution.get('exit_code') == 0 and execution.get('fixture') == 'nominal-v2'
         and execution.get('command') == expected_cmd and
         execution.get('architecture') == 'x86_64' and
         HEX64.fullmatch(str(execution.get('binary_sha256', ''))) and
         execution.get('source_generator_sha256') == sha(ROOT / 'tests/dsd/test_p10.c'),
         'soak executable/source/command receipt invalid')
    paths = sorted(folder.glob(ident + '-*.state'))
    wanted = [folder / f'{ident}-{i:04}.state' for i in range(1, 61)] + [
        folder / (ident + '-final.state')]
    need(set(paths) == set(wanted), 'soak continuation snapshot count/names invalid')
    previous_in = previous_native = -1
    inventory = hashlib.sha256()
    for i, path in enumerate(wanted):
        s = check_state(path)
        need(s['input'] >= previous_in and s['native'] >= previous_native and
             s['input'] <= report['input_frames'] + 4096 and
             s['native'] <= report['processed_native_frames'],
             'soak continuation frames not monotone/bounded')
        if i < 60:
            need(abs(s['input'] - (i + 1) * 60 * expected['source_hz']) <= 4096,
                 'soak segment not one minute of source input')
        else:
            need(s['input'] == report['input_frames'] and
                 s['native'] == report['processed_native_frames'] and
                 s['windows'] == report['windows28'] and
                 s['excursions'] == report['excursions28'] and
                 s['longest'] == report['longest_run'] and
                 all(s[f'maximum{j}'] == maxima[j] for j in range(8)),
                 'soak final state does not agree with terminal report')
        previous_in, previous_native = s['input'], s['native']
        inventory.update(path.name.encode('ascii') + b'\x00' + sha(path).encode('ascii') + b'\n')
    need(not (folder / (ident + '-failure.state')).exists(), 'soak failure state retained')
    return {'profile_native_hz': native, 'tier': folder.name,
            'completed_seconds': 3600, 'snapshots_verified': len(wanted),
            'snapshots_inventory_sha256': inventory.hexdigest(),
            'execution_receipt_sha256': sha(exec_file),
            'source_generator_sha256': execution['source_generator_sha256'],
            'harness_unqualified_is_activation_label_not_numerical_failure': True}


def inspect_soaks() -> dict:
    guards = read_json(ROOT / 'tests/dsd/reference/p10_guards.json')
    need({p.name for p in SOAKS.iterdir() if p.is_dir()} == set(TIERS),
         'unknown or missing soak family')
    runs = [inspect_soak_run(SOAKS / tier, rate, guards)
            for tier in TIERS for rate in RATES]
    need(len(runs) == 15 and sum(r['snapshots_verified'] for r in runs) == 915,
         'soak run/state inventory incomplete')
    return dict(disposition='PASS-SCOPED', run_count=15,
                continuation_states_verified=915, execution_receipts_verified=15,
                audio_seconds_per_run=3600,
                scope='PCM-to-DSD current P15 mastering profile/SDM family long-duration monitored runs',
                caveat='Serialized states and report cross-checks passed; physical host and executable remain operator-supplied provenance, not independently re-executed here. No decode-side one-hour soak is imposed by section 10.5.',
                runs=runs)


DSD256_PROFILES = ('mastering', 'decode.mastering.v2.dsd256')


def checked_per_profile_arm(row: dict, label: str) -> np.ndarray:
    """Timing arm of the per-profile receipt, which carries no `mad` field."""
    receipt = row[label]
    samples = receipt.get('repetitions')
    need(isinstance(samples, list) and len(samples) == 15 and
         all(type(t) in (float, int) and math.isfinite(t) and t > 0 for t in samples),
         'DSD256 per-profile arm lacks 15 finite timing repetitions: ' + label)
    values = np.asarray(samples, dtype=np.float64)
    need(math.isclose(float(np.median(values)), receipt['median'], rel_tol=1e-12) and
         math.isclose(float((np.max(values) - np.min(values)) / receipt['median'] * 100.0),
                      receipt['spread_pct'], rel_tol=1e-8, abs_tol=1e-8),
         'DSD256 per-profile timing summary not reproduced: ' + label)
    return values


def inspect_control_match(data: dict | None = None) -> dict:
    """The spectral half: is the staged control actually bandwidth-matched?

    R2's control was asserted matched from its command line and was not. This
    reads the independent comparison of the two transfers on a shared native
    file. Nothing here is taken on the producer's word: the declared verdict
    is recomputed from the recorded per-band differences.
    """
    data = read_json(PER_PROFILE / 'dsd256-control-match.json') if data is None else data
    need(data.get('schema') == 'P15/dsd256-control-bandwidth-match/1',
         'DSD256 control-match receipt shape wrong')
    # One channel, not the timing run's six: a filter's transfer does not
    # depend on channel count, and the probe signal must be broadband, which
    # the six-tone timing fixture is not.
    need(all(HEX64.fullmatch(v) for v in data['executables'].values()) and
         HEX64.fullmatch(data['fixture']['native_sha256']) and
         HEX64.fullmatch(data['fixture']['source_sha256']) and
         data['fixture']['channels'] == 1 and
         'noise' in data['fixture'].get('probe', '') and
         data['fixture']['native_hz'] == 11289600,
         'DSD256 control-match fixture/build digest binding missing')
    need(set(data['rows']) == set(DSD256_PROFILES),
         'DSD256 control-match does not cover both profiles')
    limit = data['agreement_limit_db']
    need(isinstance(limit, (int, float)) and 0 < limit <= 1.0,
         'DSD256 control-match agreement limit is not a stated tight bound')
    cells = {}
    for profile, row in data['rows'].items():
        passband = row['effective_passband_hz']
        need(row['profile_id'] and passband >= 20000,
             'DSD256 control-match profile identity or passband missing: ' + profile)
        need(set(row['rates']) == {str(x) for x in RATE_TARGETS},
             'DSD256 control-match rate grid differs: ' + profile)
        for rate, cell in row['rates'].items():
            # Recompute the verdict rather than trust the recorded boolean.
            need(cell['passband_hz'] == passband and cell['agreement_limit_db'] == limit,
                 'DSD256 control-match cell disagrees with its profile: ' + profile)
            need(cell['compared_bins'] >= 16,
                 'DSD256 control-match compared too few bins: ' + profile + ' ' + rate)
            # The transition exclusion is a stated rule, not an adjustable
            # dial: cap it here so a later widening cannot quietly turn a
            # mismatch into a match.
            excluded = cell['transition_excluded_fraction']
            need(0 <= excluded <= 0.05,
                 'DSD256 control-match excludes more than the stated 5%% transition: '
                 + profile + ' ' + rate)
            lo_hz, hi_hz = cell['comparison_band_hz']
            need(lo_hz <= 1000 and
                 math.isclose(hi_hz, passband * (1 - excluded), rel_tol=1e-6, abs_tol=1.0),
                 'DSD256 control-match comparison band is not the stated passband rule: '
                 + profile + ' ' + rate)
            recomputed = cell['max_abs_difference_db'] <= limit
            need(recomputed is bool(cell['matched']),
                 'DSD256 control-match verdict not reproducible: ' + profile + ' ' + rate)
            need(recomputed, 'DSD256 staged control is NOT bandwidth-matched to the '
                 'decoder: %s at %s, max difference %.3f dB exceeds %.3f dB'
                 % (profile, rate, cell['max_abs_difference_db'], limit))
            cells['%s@%s' % (profile, rate)] = dict(
                passband_hz=passband,
                comparison_band_hz=cell['comparison_band_hz'],
                max_abs_difference_db=cell['max_abs_difference_db'],
                max_abs_difference_at_hz=cell['max_abs_difference_at_hz'],
                compared_bins=cell['compared_bins'],
                # Ungated. The two filters' transitions differ, most visibly
                # on v2 at its 66 kHz edge; recorded so that is not lost.
                full_passband_max_abs_difference_db=cell[
                    'full_passband_max_abs_difference_db'],
                full_passband_max_abs_difference_at_hz=cell[
                    'full_passband_max_abs_difference_at_hz'])
    need(data['status'] == 'MATCHED', 'DSD256 control-match status is not MATCHED')
    need(data.get('selftest_mismatch_hz') is None,
         'DSD256 control-match receipt is a self-test run, not evidence')
    return dict(disposition='CONTROL-BANDWIDTH-MATCH-VERIFIED',
                agreement_limit_db=limit, cells=cells,
                executables=data['executables'],
                probe_signal=data['probe_signal'],
                scope=data['scope'])


def inspect_per_profile_benchmark(data: dict | None = None,
                                  match: dict | None = None) -> dict:
    """The DSD256 2x arm, matched per profile to that profile's own passband.

    Supersedes inspect_benchmark, which reads the R2 receipt and hard-asserts
    its 20 kHz staged sinc. That receipt is preserved and still reviewed; this
    reads the per-profile receipt that replaced it, and refuses to call the
    control matched without the separate spectral verification above.
    """
    data = read_json(PER_PROFILE / 'dsd256-2x.json') if data is None else data
    need(data.get('schema') == 'P15/dsd256-2x-reference-target/2' and
         data.get('qualified') is False and
         data.get('target') == 2.0 and data.get('repetitions') == 15 and
         data.get('warmups', 0) >= 1 and
         data.get('bootstrap', {}).get('iterations', 0) >= 1000,
         'DSD256 per-profile receipt shape/activation wrong')
    need(data['bootstrap'].get('method') == 'independent bootstrap of median ratio',
         'DSD256 per-profile CI method differs')
    need(data.get('pinned_cpu') is not None and data['host'].get('cpu_model') and
         data['host'].get('governor') and data['host'].get('microcode'),
         'DSD256 per-profile prepared host identity missing')
    need(all(HEX64.fullmatch(v) for v in data['executables'].values()) and
         HEX64.fullmatch(data['fixture']['native_sha256']) and
         HEX64.fullmatch(data['fixture']['source_sha256']) and
         data['fixture']['channels'] == 6 and
         data['fixture']['native_hz'] == 11289600,
         'DSD256 per-profile fixture/build digest binding missing')
    need(set(data['rows']) == set(DSD256_PROFILES),
         'DSD256 per-profile receipt does not cover both profiles')

    verified = inspect_control_match() if match is None else match
    need(verified['disposition'] == 'CONTROL-BANDWIDTH-MATCH-VERIFIED',
         'DSD256 control match not verified; the comparator claim stands unsupported')
    # The two receipts use different fixtures on purpose: the transfer probe
    # needs broadband content and one channel, the timing run needs the
    # six-channel realism. They bind through the build instead.
    need(verified['executables'] == data['executables'],
         'DSD256 timing and control-match receipts were produced by different builds')

    rows = {}
    for profile in DSD256_PROFILES:
        row = data['rows'][profile]
        passband = row['effective_passband_hz']
        need(row['profile_id'] and passband >= 20000,
             'DSD256 per-profile identity or passband missing: ' + profile)
        need(set(row['rates']) == {str(x) for x in RATE_TARGETS},
             'DSD256 per-profile rate grid differs: ' + profile)
        for rate in RATE_TARGETS:
            cell = row['rates'][str(rate)]
            candidate = checked_per_profile_arm(cell, 'decoder')
            direct = checked_per_profile_arm(cell, 'legacy_direct')
            staged = checked_per_profile_arm(cell, 'legacy_staged_matched')
            staged_args = cell['legacy_staged_matched']['command']
            direct_args = cell['legacy_direct']['command']
            candidate_args = cell['decoder']['command']
            need('dsdpcm' in candidate_args and '-l' in candidate_args and
                 candidate_args[-1] == str(rate) and
                 direct_args[-2:] == ['rate', '-v'],
                 'unexpected DSD256 per-profile output rate/command chain')
            # The cutoff must be this profile's own declared passband, taken
            # from the binary. The three earlier errors on this gate were all
            # a wrong number here, so it is checked against the receipt's
            # queried value rather than against any constant.
            need(staged_args[-4:-2] == ['sinc', '-%d' % passband] and
                 staged_args[-2:] == ['rate', '-v'],
                 'DSD256 staged control is not cut at this profile\'s own passband: '
                 + profile)
            need('%s@%s' % (profile, rate) in verified['cells'],
                 'DSD256 timed cell has no spectral match verification: ' + profile)
            for key, legacy in (('legacy_direct', direct),
                                ('legacy_staged_matched', staged)):
                reported = cell['speedup_vs_' + key]
                point = float(np.median(legacy) / np.median(candidate))
                need(math.isclose(point, reported['point'], rel_tol=1e-12) and
                     reported['ci95'][0] <= point <= reported['ci95'][1] and
                     reported['ci95'][0] > 2.0 and
                     reported['meets_2x_at_ci_lower_bound'] is True,
                     'DSD256 per-profile median/CI inconsistent with samples: ' + key)
                # Independent bootstrap from the saved repetitions, not from
                # the reported interval.
                rng = np.random.default_rng(data['bootstrap']['seed'])
                count = data['bootstrap']['iterations']
                rep = rng.integers(0, 15, size=(count, 15))
                b_legacy = np.median(legacy[rep], axis=1)
                rep = rng.integers(0, 15, size=(count, 15))
                b_candidate = np.median(candidate[rep], axis=1)
                lo, hi = np.quantile(b_legacy / b_candidate, [0.025, 0.975])
                need(lo > 2.0 and
                     abs(float(lo) - reported['ci95'][0]) < 0.03 and
                     abs(float(hi) - reported['ci95'][1]) < 0.03,
                     'DSD256 per-profile bootstrap bound not reproducible: ' + key)
            rows['%s@%s' % (profile, rate)] = dict(
                profile_id=row['profile_id'], output_hz=rate,
                matched_control_passband_hz=passband,
                repetitions_per_arm=15,
                direct_reference_median_speedup=round(
                    float(np.median(direct) / np.median(candidate)), 6),
                direct_reference_reported_ci95=cell['speedup_vs_legacy_direct']['ci95'],
                matched_control_reported_ci95=cell[
                    'speedup_vs_legacy_staged_matched']['ci95'],
                matched_control_verified_spectrally=True)
    return dict(disposition='DIRECT-2X-AND-MATCHED-COMPARATOR-MEASURED',
                timed_direct_2x_observation='PASS-SCOPED',
                timed_matched_control_observation='PASS-SCOPED',
                control_bandwidth_match=verified['disposition'],
                control_agreement_limit_db=verified['agreement_limit_db'],
                # 2 profiles x 2 output rates = 4 cells, each timed against
                # both the direct and the matched control.
                cells_measured=len(rows),
                comparisons_meeting_2x_at_ci_lower_bound=2 * len(rows),
                cells=rows,
                supersedes=('tests/dsd/results/P15_matrix_metrology_R2_2026-10-14/'
                            'dsd256-2x.json, whose 20 kHz staged sinc matched the '
                            'passband of neither profile'),
                scope=('a timed throughput observation on one prepared host with a '
                       'spectrally verified comparator; it is not an audio quality '
                       'result, does not qualify v2, and authorises no promotion'))


def checked_arm(row: dict, label: str) -> np.ndarray:
    receipt = row[label]
    samples = receipt.get('repetitions')
    need(isinstance(samples, list) and len(samples) == 15 and
         all(type(t) in (float, int) and math.isfinite(t) and t > 0 for t in samples),
         'DSD256 lacks 15 finite timing repetitions: ' + label)
    values = np.asarray(samples, dtype=np.float64)
    need(math.isclose(float(np.median(values)), receipt['median'], rel_tol=1e-12) and
         math.isclose(float(np.median(abs(values - receipt['median']))),
                      receipt['mad'], rel_tol=1e-8, abs_tol=1e-10) and
         math.isclose(float((np.max(values) - np.min(values)) / receipt['median'] * 100.0),
                      receipt['spread_pct'], rel_tol=1e-8, abs_tol=1e-8),
         'DSD256 timing summary not reproduced: ' + label)
    argv = receipt.get('command', [])
    need(isinstance(argv, list) and all(isinstance(x, str) for x in argv) and
         any(str(x).endswith('sox_ng') for x in argv),
         'DSD256 command receipt missing/invalid: ' + label)
    need(type(receipt.get('clock_busy_samples')) is int and
         receipt['clock_busy_samples'] > 0 and
         type(receipt.get('clock_mhz_median')) in (float, int) and
         receipt['clock_mhz_median'] > 0,
         'DSD256 missing clock observations: ' + label)
    return values


def inspect_benchmark(data: dict | None = None) -> dict:
    data = read_json(R2 / 'dsd256-2x.json') if data is None else data
    need(data.get('schema') == 'P15/dsd256-2x-reference-target/2' and
         data.get('qualified') is False and
         data.get('target') == 2.0 and data.get('repetitions') == 15 and
         data.get('warmups', 0) >= 1 and data.get('bootstrap', {}).get('iterations', 0) >= 1000,
         'DSD256 receipt shape/activation wrong')
    need(data['bootstrap'].get('method') == 'independent bootstrap of median ratio',
         'DSD256 CI method differs')
    need(set(data['rows']) == {str(x) for x in RATE_TARGETS}, 'DSD256 rate grid differs')
    need(data.get('pinned_cpu') is not None and data['host'].get('cpu_model') and
         data['host'].get('governor') and data['host'].get('microcode'),
         'DSD256 prepared host identity missing')
    need(all(HEX64.fullmatch(v) for v in data['executables'].values()) and
         HEX64.fullmatch(data['fixture']['native_sha256']) and
         HEX64.fullmatch(data['fixture']['source_sha256']) and
         data['fixture']['channels'] == 6 and
         data['fixture']['native_hz'] == 11289600,
         'DSD256 fixture/build digest binding missing')
    # The production mastering profile for DSD256 is defined in section 6.1
    # and src/dsd.c as P=40kHz, S=80kHz; an output below 352.8kHz does not
    # reduce P. Do not infer a matched transfer from quiet >20kHz fixture bins.
    mastering_pass = 40000
    rows = {}
    for rate in RATE_TARGETS:
        row = data['rows'][str(rate)]
        candidate = checked_arm(row, 'decoder')
        direct = checked_arm(row, 'legacy_direct')
        staged = checked_arm(row, 'legacy_staged_matched')
        candidate_args = row['decoder']['command']
        direct_args = row['legacy_direct']['command']
        staged_args = row['legacy_staged_matched']['command']
        need('dsdpcm' in candidate_args and '-l' in candidate_args and
             candidate_args[-1] == str(rate) and
             direct_args[-2:] == ['rate', '-v'],
             'unexpected DSD256 output rate/command chain')
        # A negative SoX sinc cutoff of -20000 is a low-pass near 20kHz, not
        # the 40kHz guaranteed passband of decode.mastering.v1.dsd256.
        # Even if another syntactic cutoff is used in future, independent
        # spectral verification must precede calling the control matched.
        need(staged_args[-7:] == ['rate', '-v', '88200', 'sinc', '-20000', 'rate', '-v'],
             'unreviewed staged-reference method: re-adjudicate')
        for key, legacy in (('legacy_direct', direct),
                            ('legacy_staged_matched', staged)):
            reported = row['speedup_vs_' + key]
            point = float(np.median(legacy) / np.median(candidate))
            need(math.isclose(point, reported['point'], rel_tol=1e-12) and
                 reported['ci95'][0] <= point <= reported['ci95'][1] and
                 reported['ci95'][0] > 2.0 and reported['meets_2x_at_ci_lower_bound'] is True,
                 'DSD256 claimed median/CI is inconsistent with timing samples: '+key)
            # Independently bootstrap from saved repetitions, *not* from
            # reported CI. Percentile points vary slightly with bootstrap
            # ordering, so compare at a tolerance much smaller than 2x margin.
            rng = np.random.default_rng(data['bootstrap']['seed'])
            count = data['bootstrap']['iterations']
            rep = rng.integers(0, 15, size=(count, 15))
            b_legacy = np.median(legacy[rep], axis=1)
            rep = rng.integers(0, 15, size=(count, 15))
            b_candidate = np.median(candidate[rep], axis=1)
            lo, hi = np.quantile(b_legacy / b_candidate, [0.025, 0.975])
            need(lo > 2.0 and
                 abs(float(lo)-reported['ci95'][0]) < 0.03 and
                 abs(float(hi)-reported['ci95'][1]) < 0.03,
                 'DSD256 bootstrap confidence bound not reproducible: '+key)
        rows[str(rate)] = dict(
            output_hz=rate, repetitions_per_arm=15,
            direct_reference_median_speedup=round(float(np.median(direct) / np.median(candidate)), 6),
            direct_reference_reported_ci95=row['speedup_vs_legacy_direct']['ci95'],
            narrower_legacy_control_reported_ci95=row['speedup_vs_legacy_staged_matched']['ci95'],
            production_mastering_guaranteed_passband_hz=mastering_pass,
            recorded_staged_sinc_lowpass_hz=20000,
            actual_bandwidth_matched_control_verified=False)
    return dict(disposition='OPEN-CONTROL-NOT-BANDWIDTH-MATCHED',
                timed_direct_2x_observation='PASS-SCOPED',
                timed_staged_lowpass_observation='PASS-AS-MEASUREMENT-NOT-MATCHED-CONTROL',
                output_rates=rows,
                why_open='The 20 kHz staged sinc narrows the legacy transfer below the DSD256 mastering 40 kHz passband. One quiet test fixture and comparable RMS cannot verify passband equivalence or pre-decimation alias rejection.',
                next_evidence='Re-run only the properly bandwidth-matched staged legacy comparator, verify its transfer including passband and alias folding against the 40 kHz/80 kHz production mastering profile, and retain 15 timed repetitions with input/build binding. Preserve existing R2 measurements.')


def inspect_amendment() -> dict:
    design = DESIGN.read_text(encoding='utf-8')
    text = AMENDMENT.read_text(encoding='utf-8')
    marker = 'P15 first-release Intel AVX-512 feature-scoped amendment (2026-10-14)'
    need(marker in design and 'Intel AVX-512' in text and
         'UNRUN' in text and 'automatic' in text and 'physical' in text,
         'formal feature-scoped Intel decision not present in design and ledger')
    return dict(disposition='EXEMPT-FOR-CONSERVATIVE-P15-POLICY-ONLY',
                physical_test_execution='UNRUN',
                amendment='docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md',
                restriction='No Intel-specific AVX-512 performance, verified physical compatibility, cross-vendor parity, or automatic preference claim; restored as a blocking gate if any such claim/policy is proposed.')


def inspect_all() -> dict:
    paths = [R2 / tier for tier in ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')]
    matrix = inspect_matrix(paths)
    need(matrix['full_local_observation_coverage'] and not matrix['release_gate_closed'] and
         matrix['scalar_full_duration_cells'] == 54 and
         matrix['forced_isa_full_duration_jobs'] == 216 and
         matrix['selected_detailed_isa_jobs'] == 96,
         'independent matrix evidence verification incomplete')
    soaks = inspect_soaks()
    benchmark = inspect_benchmark()
    intel = inspect_amendment()
    gates = [
      dict(id='P15-full-3x9x2-numerical-release-matrix', status='OPEN',
           evidence='P15_matrix_metrology_R2_2026-10-14',
           scope='Raw measurement coverage confirmed; composite full spectral extrema, coherent alias/image sum, and like-for-like SRC numerical acceptance proof absent.'),
      dict(id='P15-physical-Intel-AVX512-performance', status='UNRUN-SCOPE-EXEMPT',
           evidence='docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md',
           scope='Conservative no-Intel-specific-preference first-release only; measurement never passed.'),
      dict(id='P15-physical-older-AVX-performance', status='PASS-SCOPED',
           evidence='P15_avx1_physical_2026-10-13',
           scope='Earlier independent closeout; physical AVX1-only kernel evidence only.'),
      dict(id='P15-2x-six-channel-DSD256-controlled-reference-target', status='OPEN',
           evidence='P15_matrix_metrology_R2_2026-10-14/dsd256-2x.json',
           scope='15 raw repetitions verify >2x relative to direct reference; claimed 20kHz staged comparator is not bandwidth-matched to 40kHz mastering.'),
      dict(id='P15-current-full-release-soaks-every-profile-ISA', status='PASS-SCOPED',
           evidence='P15_soaks_every_profile_isa_2026-10-13',
           scope='15 clean encoder profile/SDM family one-hour soaks, 915 verified states and 15 receipts. Not a decode soak.'),
      dict(id='P15-current-independent-codec-and-hardware-corpus', status='PASS-SCOPED',
           evidence='P15_corpus_independent_material_2026-10-13',
           scope='Earlier accepted independent software material only; no physical DAC/player qualification.')]
    need(sum(g['status'] == 'OPEN' for g in gates) == 2,
         'release gate count incongruent')
    return dict(schema='P15/re-adjudication/1', authority='docs/dsd/DSD_DESIGN.md',
                prior_closeout='docs/dsd/handoffs/P15_CLOSEOUT_ADJUDICATION_2026-10-14.md',
                release_status='BLOCKED', qualified=False,
                default_promotion_authorized=False, p16_authorized=False,
                required_open_gates=[g['id'] for g in gates if g['status'] == 'OPEN'],
                gates=gates, matrix_coverage={k: matrix[k] for k in (
                    'full_local_observation_coverage','scalar_full_duration_cells',
                    'forced_isa_full_duration_jobs','selected_detailed_isa_jobs',
                    'src_raw_verified_full_duration_cells','graph_raw_verified_full_duration_cells',
                    'source_reference_sha256','worklist_sha256')},
                soaks=soaks, benchmark=benchmark, intel=intel,
                src_envelope='Product-level spectral limits are already fixed by DSD_DESIGN 6.1/10.4; no universal sample epsilon against a different-filter SRC. Section 8.6 requires an independent like-for-like SRC numerical bound declared before comparison.',
                historical_receipts_edited=False,
                unsupported_claims=['Intel AVX-512 physical performance/compatibility',
                                    'complete composite SRC qualification',
                                    'bandwidth-matched DSD256 speedup',
                                    'physical device compatibility',
                                    'production mastering qualification',
                                    'automatic ISA preference changes'])


def write_new(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if path.exists():
        need(path.read_bytes() == content,
             'existing result differs; do not silently overwrite prior adjudication')
        return
    fd, scratch = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # Refuse a concurrent winner, including a changed result.
        try:
            os.link(scratch, path)
        except FileExistsError:
            need(path.read_bytes() == content, 'concurrent adjudication differs')
    finally:
        if os.path.exists(scratch):
            os.unlink(scratch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-release', action='store_true',
                        help='exit 2 while release is blocked; 0 otherwise')
    args = parser.parse_args()
    try:
        result = inspect_all()
        write_new(args.output, result)
        print(json.dumps({'release_status': result['release_status'],
                          'required_open_gates': result['required_open_gates'],
                          'soak_states_checked': result['soaks']['continuation_states_verified']},
                         sort_keys=True))
        return 2 if args.require_release and result['release_status'] != 'QUALIFIED' else 0
    except (EvidenceError, ValueError, OSError, KeyError, TypeError, OverflowError) as e:
        print('P15 re-adjudication INVALID EVIDENCE: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
