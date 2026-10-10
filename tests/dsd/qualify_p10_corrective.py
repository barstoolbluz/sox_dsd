#!/usr/bin/env python3
"""Audit P10 corrective evidence without conflating nominal-soak and release gates.

An INCOMPLETE verdict exits 2; a measured failure exits 1. Neither promotes a
profile or overwrites the original P10 certificate. Missing tests are UNRUN.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from verify_p10_corrective import classify

ROOT = Path(__file__).resolve().parents[2]
NATIVES = (2822400, 5644800, 11289600)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def make_gate(label, test, *, details=None, evidence=None):
    return dict(status='PASS' if test else 'FAIL', evidence=evidence, details=details)


def verify(base, unit=None):
    tests = ROOT/'tests/dsd'
    prior = tests/'results/P10'
    gates = {}
    problems = []
    source_sha = sha(tests/'test_p10.c')
    lock_sha = sha(tests/'reference/analysis-v1/SHA256SUMS.txt')
    frozen = read(tests/'reference/p10_profiles.json')
    gates['no_promotion'] = make_gate('no_promotion', frozen.get('qualified') is False and
        all(not p.get('qualified',p.get('qualification',False)) for p in frozen['profiles']),
        evidence='tests/dsd/reference/p10_profiles.json')
    stage_path = base/'stage-audit/classification.json'
    stage = read(stage_path)
    measurement_count = len(stage['findings'])
    # A cached summary is not evidence of the raw files currently on disk.
    # Recompute without rewriting the historical classification receipt.
    try:
        measured_stage = classify(base/'stage-audit')
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
        measured_stage = None
    stages_ok = (stage == measured_stage and stage['status']=='PASS' and
        not stage['failures'] and measurement_count == 12)
    for native in NATIVES:
        values = [r for r in stage['findings'] if r['native_hz']==native]
        dc = [r for r in values if r['kind']=='dc']
        noise = [r for r in values if r['kind']=='noise-classification']
        stages_ok &= len(dc)==3 and len(noise)==1
        stages_ok &= all(r['status']=='PASS' and len(r['stage_gain'])==4 and
            all(math.isfinite(g) and abs(g-1.)<1e-6 for g in r['stage_gain'][:3]) and
            r['stage_gain'][3]==.5 for r in dc)
        stages_ok &= all(r['original_exit']==4 and r['original_error']==2 and
            r['original_scaled_peak']>.5 and r['nominal_scaled_peak']<.5 and
            r['attenuated_original_scaled_peak']<.5 and r['observed_nominal_headroom_db']>0
            for r in noise)
    gates['stage_unity_scaling_and_distribution'] = make_gate('stage',stages_ok,
        details='9 steady-DC paths, 3 directly measured noise modes per native rate',
        evidence='stage-audit/classification.json')
    original = read(base/'original-overload/verification.json')
    old_ok = (original['status']=='PASS' and len(original['profiles'])==3 and
        {p['native_hz'] for p in original['profiles']} == set(NATIVES))
    for p in original['profiles']:
        native = p['native_hz']
        old_path = prior/f'soak/soak-{native}-result.json'
        new_path = base/f'original-overload/soak-{native}-result.json'
        left,right=read(old_path),read(new_path)
        old_ok &= ({k:v for k,v in left.items() if k!='cpu_seconds'} ==
            {k:v for k,v in right.items() if k!='cpu_seconds'} and
            p['identical_fields'] is True and
            left['first_bad_frame']==right['first_bad_frame']==p['first_bad_frame'] and
            left['failure']==right['failure']==2 and
            left['failure_value']==right['failure_value']==p['failure_value'] and
            len(p['snapshots'])>=1 and
            all(x['identical'] is True and x['old_sha256']==x['new_sha256'] and
                sha(prior/'soak'/x['name'])==sha(base/'original-overload'/x['name']) for x in p['snapshots']))
    gates['original_expected_overload_replay'] = make_gate('old',old_ok,
        details='Original unattenuated stimulus still fails at the identical frame, state and value',
        evidence='original-overload/verification.json')
    bit = read(base/'bit-equivalence/bit-equivalence.json')
    rows = read(prior/'numeric/qualification.json')['rows']
    bit_ok = (bit['status']=='PASS' and len(rows)==len(bit['rows'])==183 and
        bit['original_evidence_sha256']==sha(prior/'numeric/qualification.json') and
        bit['source_generator_sha256']==source_sha and
        bit['frozen_analysis_lock_sha256']==lock_sha)
    bit_ok &= all(z['status']=='PASS' and z['name']==p['name'] and
        z['expected_bits_sha256']==z['actual_bits_sha256']==p['bits_sha256'] and
        z['actual_exit_code']==z['expected_exit_code']==p['exit_code'] and
        not z['mismatches'] and
        z['observed_native_frames']==z['inherited_native_frames'] for z,p in zip(bit['rows'],rows))
    if unit is not None:
        bit_ok &= bit['executable_sha256']==sha(unit)
    gates['inherited_numeric_183_bit_identical'] = make_gate('bits',bit_ok,
        details='All inherited analysis-v1 numerical identities confirmed with corrected executable; no reanalysis claimed',
        evidence='bit-equivalence/bit-equivalence.json')
    numeric = read(prior/'numeric/qualification.json')
    required_numeric = ('complete_numeric_coverage','dsd64_windows28','expected_overload',
        'heldout_state_bounds','lowlevel_spurs','nominal_pipeline',
        'residual_comparison','second_reconstruction')
    gate_ok = all(numeric['gates'][k]['status']=='PASS' for k in required_numeric)
    gates['inherited_analysis_v1'] = make_gate('analysis',gate_ok,
        details='Includes DSD64 35.9084-dB residual improvement, no material per-case regressions',
        evidence='../P10/numeric/qualification.json')
    impl = read(base/'regression/implementation.json')
    runner = read(base/'regression/run.json')
    cli=read(base/'cli/cli.json')
    core=read(base/'unit/core.json')
    gates['regressions_and_candidate_cli'] = make_gate('regressions',
        impl['status']=='PASS' and runner['verdict']=='pass' and
        runner['counts']=={'pass':36,'fail':0,'skip':0,'xfail':0,'xpass':0} and
        cli['summary']['fail']==0 and cli['summary']['pass']>=63 and
        core['assertions']>=105474 and core['failures']==0,
        details='make check and make check-dsd executed separately; 36 regression, 63 CLI, 105474 core assertions',
        evidence='regression, cli/cli.json, unit/core.json')
    nominal = read(tests/'reference/p10_soak_nominal_v2.json')
    soak_path = base/'nominal-v2/soak/soak.json'
    if soak_path.exists():
        soak = read(soak_path)
        soak_ok = (soak['status']=='PASS' and soak['fixture_version']=='nominal-v2' and
            soak['qualified'] is False and len(soak['profiles'])==3 and
            {p['configuration']['native_hz'] for p in soak['profiles']} == set(NATIVES))
        bounds = read(tests/'reference/p10_guards.json')['profiles']
        seconds = nominal['duration_seconds']
        stage_execution = read(base/'stage-audit/execution.json')
        for p in soak['profiles']:
            native=p['configuration']['native_hz']
            report_path = base/f'nominal-v2/soak/soak-{native}-result.json'
            report = read(report_path)
            execution = read(base/f'nominal-v2/soak/soak-{native}-execution.json')
            configuration = read(base/f'nominal-v2/soak/soak-{native}-configuration.json')
            expected_snapshots = {f'soak-{native}-{i:04d}.state' for i in range(1,31)}
            expected_snapshots.add(f'soak-{native}-final.state')
            maxima = report.get('max_abs_state', [])
            limits = bounds.get(str(native), {}).get('bounds', [])
            ok = (p['status']=='PASS' and all(p['admission_checks'].values()) and
                p['evidence_sha256']==sha(report_path) and p['raw']==report and
                p['execution']==execution and p['configuration']==configuration and
                configuration['seconds']==seconds and configuration['segment_seconds']==60 and
                configuration['fixture_version']=='nominal-v2' and
                execution['exit_code']==0 and execution.get('fixture')=='nominal-v2' and
                execution['source_generator_sha256']==source_sha and
                execution['binary_sha256']==bit['executable_sha256']==stage_execution['executable_sha256'] and
                report['status']==3 and report['first_bad_frame'] is None and
                report['mode']=='soak-nominal-v2' and report['native_hz']==native and
                report['source_hz']==configuration['source_hz'] and
                report['input_frames']==seconds*configuration['source_hz'] and
                len(maxima)==len(limits)==8 and all(math.isfinite(v) and 0<=v<=b for v,b in zip(maxima,limits)) and
                {x['file'] for x in p['snapshots']}==expected_snapshots and
                report['processed_native_frames']==native*nominal['duration_seconds'] and
                report['committed_native_frames']==native*nominal['duration_seconds'] and
                report['failure']==0 and math.isfinite(report['peak']) and 0<=report['peak']<=.5+1./(2**31-1) and
                report['windows28']==native*nominal['duration_seconds']-27 and
                report['nonfinite_states']==0 and report['monitor_overloads_nominal_half']==0 and
                len(p['snapshots'])==31 and
                all(sha(base/'nominal-v2/soak'/s['file'])==s['sha256'] for s in p['snapshots']))
            if native==NATIVES[0]:ok &= report['excursions28']==0 and report['min_ones28']>=4 and report['max_ones28']<=24
            soak_ok &= ok
        gates['nominal_30min_all_rates'] = make_gate('soak',soak_ok,
            details='One uninterrupted 1800-s encoder per rate, all 30 snapshot states and final output checked',
            evidence='nominal-v2/soak/soak.json')
    else:
        gates['nominal_30min_all_rates'] = dict(status='UNRUN',evidence='nominal-v2/soak/soak.json')
    prepared=read(prior/'bench-read-prepared-host-2026-10-09/bench-read.json')
    # The original measured revision is not this corrective binary; retain it
    # as inherited performance evidence rather than a fresh controlled-host gate.
    bench_ok=prepared['status']=='pass' and not prepared['host_unqualified'] and not prepared['errors'] and len(prepared['summaries'])==16 and all(p['status']=='pass' for p in prepared['summaries'].values())
    gates['inherited_prepared_host_read_repack'] = make_gate('inherited_bench',bench_ok,
        details='P09 vs P10 read/repack only; not a new encoder/observer benchmark',
        evidence='../P10/bench-read-prepared-host-2026-10-09/bench-read.json')
    # These are mandatory release gates, never implied by a 30-minute nominal
    # synthetic soak or a previous version's read/repack benchmark.
    gates['representative_hardware_1hour_per_profile_isa'] = dict(status='UNRUN',
        reason='No one-hour per-rate/ISA representative-hardware traces supplied or executed')
    gates['independent_realworld_corpus'] = dict(status='UNRUN',
        reason='Independent real-world recordings not supplied; synthetic qualification stimuli are not independent recordings')
    # Frozen identities must never be presented as positively qualified.
    if any(p['status']=='FAIL' for p in gates.values()): status='FAIL'
    elif any(p['status']=='UNRUN' for p in gates.values()):status='INCOMPLETE'
    else: status='PASS'
    return dict(schema='P10/corrective-qualification/1', status=status, qualified=False,
        promotion='BLOCKED', altered_admission_policy=False,
        assessment='reviewer correct: fixture classification subject to executable gain audit, now supported',
        original_noise_class='EXPECTED_INTERPOLATION_OVERLOAD',
        performance_scope='Inherited P10 prepared-host read/repack gate passed; no corrective full-composite controlled-host remeasurement',
        nominal_noise_fixture='p10-soak-nominal-v2',
        retained_original_evidence=True, gates=gates,
        remaining_release_gates=[k for k,v in gates.items() if v['status']!='PASS'],
        operational_disposition='P10 continuation; no default promotion and no P11 handoff')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P10_corrective')
    p.add_argument('--unit',type=Path,help='Optional rebuilt binary: verify current bit-equivalence executable identity')
    a=p.parse_args()
    result=verify(a.results,a.unit)
    path=a.results/'qualification.json';path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n');tmp.replace(path)
    print(json.dumps(dict(status=result['status'],qualified=False,
        pass_count=sum(g['status']=='PASS' for g in result['gates'].values()),
        unrun=result['remaining_release_gates']),sort_keys=True))
    return {'PASS':0,'FAIL':1,'INCOMPLETE':2}[result['status']]

if __name__=='__main__':raise SystemExit(main())
