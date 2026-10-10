#!/usr/bin/env python3
"""Run or inspect continuous P10 composite soaks, preserving failed evidence.

A resume replays from the origin and byte-checks every saved continuation
state. It does not join fresh encoders or pretend to deserialize opaque SRC
state. Failed original cases stay failed; attenuation is a new corpus version.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RATES = (2822400, 5644800, 11289600)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def configuration(native, seconds=1800, segment=60, fixture='original-v1'):
    if fixture not in ('original-v1', 'nominal-v2'):
        raise ValueError('unknown P10 soak fixture')
    config = dict(schema='P10/continuous-soak/1', native_hz=native,
        source_hz=88200 if native == RATES[0] else 176400,
        seconds=seconds, segment_seconds=segment, reference_scale=.5,
        generator='test_p10.c:soak_source; int32 graph-equivalent',
        minute_sequence=['silence', 'DC +0.7', 'DC -0.7',
            '53/997/5501/17011 Hz multitone, each peak 0.15',
            'SplitMix64-indexed uniform noise, peak 0.7', '1000 Hz tone, peak 0.8'],
        sequence_repeats=True, edge_ramp_seconds=.1,
        resets_between_segments=False,
        resume='deterministic prefix replay with byte-checked saved SDM/monitor states',
        qualification=False)
    if fixture == 'nominal-v2':
        config.update(generator='test_p10.c:soak_source_version; int32 graph-equivalent',
            fixture_version='nominal-v2')
        config['minute_sequence'][4] = 'SplitMix64-indexed uniform noise, peak 0.45'
    return config


def inspect(results, seconds=1800, segment=60, fixture='original-v1', unit=None):
    unit = ROOT/'test/dsd_test_p10' if unit is None else Path(unit)
    profiles = []
    for native in RATES:
        config = configuration(native, seconds, segment, fixture)
        prefix = results / f'soak-{native}'
        path = Path(str(prefix) + '-result.json')
        row = dict(configuration=config, status='UNRUN', evidence=path.name)
        if path.exists():
            report = json.loads(path.read_text())
            expected = seconds * native
            good = (report.get('failure') == 0 and
                    report.get('mode') == ('soak-nominal-v2' if fixture == 'nominal-v2' else 'soak') and
                    report.get('committed_native_frames') == expected and
                    report.get('input_frames') == seconds * config['source_hz'])
            execution_path = Path(str(prefix) + '-execution.json')
            if execution_path.exists():
                execution = json.loads(execution_path.read_text())
                good = good and execution['exit_code'] == 0
                row['execution'] = execution
            elif good:
                good = False
                row['missing_execution_record'] = True
            if fixture == 'nominal-v2':
                # A nominal PASS is a fully admitted *soak*, never an activation
                # certificate. Verify identity, complete count and monitoring.
                from math import isfinite
                bound_manifest = json.loads((ROOT/'tests/dsd/reference/p10_guards.json').read_text())
                bounds = bound_manifest['profiles'][str(native)]['bounds']
                maxima = report.get('max_abs_state', [])
                snapshots = list(results.glob(f'soak-{native}-*.state'))
                failure_state = Path(str(prefix) + '-failure.state')
                final_state = Path(str(prefix) + '-final.state')
                config_path = Path(str(prefix) + '-configuration.json')
                criteria = dict(
                    original_configuration=config_path.exists() and
                        json.loads(config_path.read_text()) == config,
                    exact_native_duration=report.get('processed_native_frames') == expected and
                        report.get('committed_native_frames') == expected,
                    clean_terminal_status=report.get('status') == 3 and
                        report.get('failure') == 0 and report.get('first_bad_frame') is None,
                    admitted_peak=isfinite(report.get('peak',float('inf'))) and
                        0 <= report.get('peak',float('inf')) <= .5+1./(2**31-1),
                    stable_state=report.get('nonfinite_states') == 0 and
                        len(maxima)==8 and all(isinstance(v,(float,int)) and
                        isfinite(v) and 0 <= v <= b for v,b in zip(maxima,bounds)),
                    complete_window_monitor=report.get('windows28') == max(0,expected-27),
                    complete_snapshots=len(snapshots) == seconds//segment+1 and
                        final_state.is_file() and not failure_state.exists(),
                    source_and_native_identity=report.get('source_hz') == config['source_hz'] and
                        report.get('native_hz') == native,
                    observed_half_guard=report.get('monitor_overloads_nominal_half') == 0,
                    release_sequence=seconds == 1800 and segment == 60,
                )
                if native == RATES[0]:
                    criteria['dsd64_28bit_population'] = (report.get('excursions28') == 0 and
                        report.get('min_ones28',0) >= 4 and report.get('max_ones28',29) <= 24)
                if 'execution' in row:
                    ex = row['execution']
                    criteria['reproducible_binary'] = (ex.get('fixture') == fixture and
                        ex.get('binary_sha256') == sha(unit) and
                        ex.get('source_generator_sha256') == sha(ROOT/'tests/dsd/test_p10.c'))
                row['admission_checks'] = criteria
                good = good and all(criteria.values())
            row.update(status='PASS' if good else 'FAIL', raw=report,
                evidence_sha256=sha(path),
                completed_audio_seconds=report['committed_native_frames'] / native,
                first_bad_audio_seconds=(None if report.get('first_bad_frame') is None
                    else report['first_bad_frame'] / native),
                snapshots=[dict(file=p.name, sha256=sha(p))
                    for p in sorted(results.glob(f'soak-{native}-*.state'))])
            if report.get('failure') == 2:
                row['failure_class'] = 'interpolation-envelope overload; no limiter or rescue'
            if native == RATES[0]:
                row['prefix_windows28_pass'] = report.get('excursions28') == 0
            row['state_bound_crossed'] = report.get('failure') == 4
        profiles.append(row)
    status = ('FAIL' if any(p['status'] == 'FAIL' for p in profiles) else
        'PASS' if all(p['status'] == 'PASS' for p in profiles) else 'UNRUN')
    result = dict(schema='P10/soak-summary/1', fixture_version=fixture, status=status, qualified=False,
        profiles=profiles, limitation='A rejected prefix is not a completed 30-minute soak. '
        'A clean DSD64 prefix is not a guarantee over the unprocessed suffix.',
        representative_hardware_hour_per_profile_isa='UNRUN')
    atomic(results / 'soak.json', result)
    return result


def run(args):
    args.results.mkdir(parents=True, exist_ok=True)
    for native in RATES:
        prefix = args.results / f'soak-{native}'
        config = configuration(native, args.seconds, args.segment_seconds, args.fixture)
        config_path = Path(str(prefix) + '-configuration.json')
        if config_path.exists() and json.loads(config_path.read_text()) != config:
            raise ValueError('resume configuration differs; use a new result directory')
        if not config_path.exists():
            atomic(config_path, config)
        result_path = Path(str(prefix) + '-result.json')
        if result_path.exists() and not args.replay:
            print(native, 'retaining completed or failed evidence; --replay verifies prefix')
            continue
        # Preserve prior failure bytes, including CPU timing, before a replay.
        if result_path.exists():
            old = result_path.read_bytes()
            saved = result_path.with_name(result_path.stem + '-original-' + sha(result_path)[:16] + '.json')
            if not saved.exists():
                saved.write_bytes(old)
        soak_command = '--soak-nominal-v2' if args.fixture == 'nominal-v2' else '--soak'
        command = [str(args.unit.resolve()), soak_command, str(native), str(args.seconds),
            str(args.segment_seconds), str(prefix.resolve())]
        with Path(str(prefix) + '-execution.log').open('w') as log:
            proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                timeout=args.timeout)
        atomic(Path(str(prefix) + '-execution.json'), dict(exit_code=proc.returncode,
            command=['test/dsd_test_p10', soak_command, str(native), str(args.seconds),
                str(args.segment_seconds), f'<results>/soak-{native}'],
            binary_sha256=sha(args.unit), architecture=platform.machine(),
            replay=args.replay, fixture=args.fixture,
            source_generator_sha256=sha(ROOT/'tests/dsd/test_p10.c')))
        inspect(args.results, args.seconds, args.segment_seconds, args.fixture, args.unit)
        print(native, 'exit', proc.returncode, flush=True)
    report = inspect(args.results, args.seconds, args.segment_seconds, args.fixture, args.unit)
    return 1 if report['status'] == 'FAIL' else 2 if report['status'] == 'UNRUN' else 0


def replay_test(args):
    """Exercise interruption, unchanged replay and refusal of mismatched states."""
    with tempfile.TemporaryDirectory(prefix='p10-replay-') as work:
        prefix = Path(work) / 'trial'
        command = [str(args.unit.resolve()), '--soak', '2822400', '5', '1', str(prefix)]
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first_line = child.stdout.readline()
        if 'segment=1' not in first_line:
            child.kill(); child.communicate()
            raise AssertionError('no committed segment before interruption')
        child.terminate(); child.communicate(timeout=10)
        states = {p.name: p.read_bytes() for p in Path(work).glob('*.state')}
        if not states:
            raise AssertionError('interruption left no snapshot')
        resumed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if resumed.returncode:
            raise AssertionError(resumed.stderr)
        for name, value in states.items():
            if (Path(work)/name).read_bytes() != value:
                raise AssertionError('replay changed an existing committed state')
        final_path = Path(str(prefix) + '-final.state')
        expected_final = sha(final_path)
        replayed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if replayed.returncode or sha(final_path) != expected_final:
            raise AssertionError('complete replay is not deterministic')
        victim = sorted(Path(work).glob('*-0001.state'))[0]
        bad = victim.read_bytes() + b'intentional-test-mismatch\n'
        victim.write_bytes(bad)
        mismatch = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if not mismatch.returncode or victim.read_bytes() != bad or not Path(str(victim)+'.tmp').exists():
            raise AssertionError('replay mismatch did not fail with both states retained')
        row = dict(schema='P10/soak-replay-test/1', status='PASS',
            interrupted_snapshots=len(states), final_state_sha256=expected_final,
            mismatch_exit=mismatch.returncode, source_generator_sha256=sha(ROOT/'tests/dsd/test_p10.c'),
            cases=['interrupted-prefix replay', 'complete replay', 'mismatch refuses replacement'])
        atomic(args.results/'replay-test.json', row)
        print(json.dumps(row, sort_keys=True))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit', type=Path, default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--seconds', type=int, default=1800)
    ap.add_argument('--segment-seconds', type=int, default=60)
    ap.add_argument('--timeout', type=float, default=14400)
    ap.add_argument('--replay', action='store_true')
    ap.add_argument('--fixture', choices=('original-v1', 'nominal-v2'), default='original-v1')
    ap.add_argument('--inspect', action='store_true')
    ap.add_argument('--test-replay', action='store_true')
    args = ap.parse_args()
    if not 0 < args.segment_seconds <= args.seconds <= 86400:
        ap.error('require 0 < segment <= duration <= 86400 seconds')
    if args.test_replay:
        return replay_test(args)
    if args.inspect:
        report = inspect(args.results, args.seconds, args.segment_seconds, args.fixture, args.unit)
        print(json.dumps(dict(status=report['status'], qualified=False)))
        return 1 if report['status'] == 'FAIL' else 2 if report['status'] == 'UNRUN' else 0
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
