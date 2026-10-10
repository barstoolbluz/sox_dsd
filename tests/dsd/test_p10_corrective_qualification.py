#!/usr/bin/env python3
"""Adversarial validation of the P10 corrective evidence collector.

Simulates stale, altered, missing and contradictory evidence without writing to
frozen P10 records. A nominal soak alone must never mint a release certificate.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from qualify_p10_corrective import verify,ROOT,sha


def probe(base, modification, expected_gate, expected_status):
    with tempfile.TemporaryDirectory(prefix='p10-corrective-test-') as tmp:
        dest=Path(tmp)/'evidence';shutil.copytree(base,dest)
        modification(dest)
        observed=verify(dest)
        assert observed['status']==expected_status, (expected_gate,observed['status'])
        assert observed['gates'][expected_gate]['status']=='FAIL', (expected_gate,observed['gates'][expected_gate])
        assert not observed['qualified'] and observed['promotion']=='BLOCKED'


def change_json(path, edits):
    data=json.loads(path.read_text()); edits(data)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,
        default=ROOT/'tests/dsd/results/P10_corrective')
    args=ap.parse_args()
    initial=verify(args.results)
    assert initial['status']=='INCOMPLETE' and initial['qualified'] is False
    assert len(initial['remaining_release_gates'])==2
    assert all(initial['gates'][k]['status']=='PASS' for k in (
        'stage_unity_scaling_and_distribution','nominal_30min_all_rates',
        'original_expected_overload_replay','inherited_numeric_183_bit_identical'))
    checks=[]
    def trial(name,mutation,gate):
        probe(args.results,mutation,gate,'FAIL');checks.append(name)
    def alter_stage(d):
        def tamper(obj):
            next(p for p in obj['findings'] if p['kind']=='dc')['stage_gain'][0]=1.1
        change_json(d/'stage-audit/classification.json',tamper)
    trial('gain deviation does not pass on stale PASS receipt',alter_stage,'stage_unity_scaling_and_distribution')
    def alter_bit(d):
        change_json(d/'bit-equivalence/bit-equivalence.json',
            lambda x:x['rows'][1].update(actual_bits_sha256='0'*64))
    trial('altered native-bit hash cannot pass',alter_bit,'inherited_numeric_183_bit_identical')
    def alter_orig(d):
        change_json(d/'original-overload/soak-2822400-result.json',
            lambda x:x.update(first_bad_frame=x['first_bad_frame']+1))
    trial('altered original failure frame cannot pass',alter_orig,'original_expected_overload_replay')
    def alter_nominal(d):
        change_json(d/'nominal-v2/soak/soak-11289600-result.json',
            lambda x:x.update(committed_native_frames=x['committed_native_frames']-1))
    trial('one missing native frame cannot pass',alter_nominal,'nominal_30min_all_rates')
    def alter_snapshot(d):
        with (d/'nominal-v2/soak/soak-5644800-0015.state').open('ab') as f:f.write(b'tampered\n')
    trial('tampered snapshot cannot pass',alter_snapshot,'nominal_30min_all_rates')
    def alter_nominal_certificate(d):
        change_json(d/'nominal-v2/soak/soak.json',lambda x:x.update(qualified=True))
    trial('soak cannot declare itself qualified',alter_nominal_certificate,'nominal_30min_all_rates')
    def stale_stage(d):
        change_json(d/'stage-audit/2822400-48000-dc.json',
            lambda x:x['stages']['R_SRC'].update(steady_mean=1.1*x['stages']['R_SRC']['steady_mean']))
    trial('raw stage gain change invalidates cached classification',stale_stage,'stage_unity_scaling_and_distribution')
    def missing_stage(d):
        (d/'stage-audit/2822400-48000-dc.json').unlink()
    trial('missing raw stage cannot pass its cached summary',missing_stage,'stage_unity_scaling_and_distribution')
    def missing_stage_receipt(d):
        change_json(d/'stage-audit/execution.json',lambda x:x['probes'].pop())
    trial('stage execution must account for every required probe',missing_stage_receipt,'stage_unity_scaling_and_distribution')
    def changed_histogram(d):
        path=d/'stage-audit/2822400-48000-dc.json'
        change_json(path,lambda x:x['stages']['source']['abs_bins_0p01'].__setitem__(0,1))
        def update_hash(x):
            next(r for r in x['probes'] if r['name']=='2822400-48000-dc')['sha256']=sha(path)
        change_json(d/'stage-audit/execution.json',update_hash)
    trial('distribution counts must match observed sample counts',changed_histogram,'stage_unity_scaling_and_distribution')
    def duplicate_original_rate(d):
        change_json(d/'original-overload/verification.json',lambda x:x.update(profiles=[x['profiles'][0]]*3))
    trial('three original entries must cover three distinct native rates',duplicate_original_rate,'original_expected_overload_replay')
    def duplicate_nominal_rate(d):
        change_json(d/'nominal-v2/soak/soak.json',lambda x:x.update(profiles=[x['profiles'][0]]*3))
    trial('three nominal entries must cover three distinct native rates',duplicate_nominal_rate,'nominal_30min_all_rates')
    def stale_nominal_state(d):
        change_json(d/'nominal-v2/soak/soak-2822400-result.json',lambda x:x['max_abs_state'].__setitem__(0,1e100))
    trial('raw soak measurements must match their audited summary',stale_nominal_state,'nominal_30min_all_rates')
    def coherent_bad_state(d):
        path=d/'nominal-v2/soak/soak-2822400-result.json'
        change_json(path,lambda x:x['max_abs_state'].__setitem__(0,1e100))
        def update_summary(x):
            p=next(p for p in x['profiles'] if p['configuration']['native_hz']==2822400)
            p['raw']=json.loads(path.read_text());p['evidence_sha256']=sha(path)
        change_json(d/'nominal-v2/soak/soak.json',update_summary)
    trial('claimed stable state must satisfy the actual frozen bounds',coherent_bad_state,'nominal_30min_all_rates')
    def missing_fixture(d):
        path=d/'nominal-v2/soak/soak-2822400-execution.json'
        change_json(path,lambda x:x.pop('fixture'))
        def update_summary(x):
            next(p for p in x['profiles'] if p['configuration']['native_hz']==2822400)['execution']=json.loads(path.read_text())
        change_json(d/'nominal-v2/soak/soak.json',update_summary)
    trial('nominal receipt must identify its fixture',missing_fixture,'nominal_30min_all_rates')
    print(json.dumps(dict(schema='P10/corrective-adversarial-tests/1',status='PASS',
        cases=len(checks)+1,tests=['all gates correctly fail closed']+checks,
        release_status='INCOMPLETE',promotion='BLOCKED'),sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
