#!/usr/bin/env python3
"""Source-bound audit of prepared-host P19 DSD1024 v2 corrected SDM soaks.

A run shorter than the original P17 one-hour obligation is a smoke test only.
A raw report without its matching execution receipt is NOT a PASS.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import os

ROOT=Path(__file__).resolve().parents[2]
GUARDS=ROOT/'tests/dsd/reference/p19_dsd1024_v2_guard.json'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def atomic(path,record):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(tmp,path)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--rate',type=int,default=45158400,choices=(45158400,))
    a.add_argument('--seconds',type=int,required=True)
    a.add_argument('--prefix',type=Path,required=True)
    a.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    a.add_argument('--results',type=Path,required=True)
    a.add_argument('--execution-receipt',type=Path,default=None)
    a.add_argument('--require-sustained',action='store_true')
    args=a.parse_args()
    if args.seconds<1 or args.seconds>86400:a.error('invalid duration')
    report=Path(str(args.prefix)+'-result.json')
    if not report.is_file():a.error('soak raw result absent')
    if not GUARDS.is_file():a.error('frozen P19 guards absent')
    if not args.unit.is_file():a.error('test binary not built')
    raw=json.loads(report.read_text());guard=json.loads(GUARDS.read_text())
    bounds=guard['bounds']
    expected=args.rate*args.seconds
    execution_path=args.execution_receipt or Path(str(args.prefix)+'-execution.json')
    execution=json.loads(execution_path.read_text()) if execution_path.is_file() else None
    mode='original-v1' if raw.get('mode')=='soak' else (
        'nominal-v2' if raw.get('mode')=='soak-nominal-v2' else None)
    execution_pass=(execution is not None and mode is not None and
        execution.get('schema')=='P19/prepared-host-soak-execution/1' and
        execution.get('executable_sha256')==sha(args.unit) and
        execution.get('source_sha256')==sha(ROOT/'tests/dsd/test_p10.c') and
        execution.get('runner_sha256')==sha(ROOT/'tests/dsd/p19_soak_run.py') and
        execution.get('raw_report_sha256')==sha(report) and
        execution.get('profile')=='encode.mastering.v2.dsd1024' and
        execution.get('candidate_sha256')==sha(ROOT/'src/sdm_p19_candidates.h') and
        execution.get('frozen_guard_sha256')==sha(GUARDS) and
        execution.get('exit_code')==0 and execution.get('seconds')==args.seconds and
        execution.get('rate_hz')==args.rate and execution.get('mode')==mode and
        execution.get('command')==[str(args.unit.resolve()),
            '--soak-dsd1024-v2' if mode=='original-v1' else '--soak-nominal-dsd1024-v2',
            str(args.rate),str(args.seconds),str(execution.get('segment_seconds')),
            str(args.prefix.resolve())])
    state=raw.get('max_abs_state') or []
    utilization=[x/b for x,b in zip(state,bounds)]
    passed=(execution_pass and raw.get('profile')=='encode.mastering.v2.dsd1024' and
        raw.get('source_hz')==176400 and
        raw.get('native_hz')==args.rate and raw.get('status')==3 and
        raw.get('failure')==0 and raw.get('input_frames')==args.seconds*176400 and
        raw.get('committed_native_frames')==expected and
        raw.get('processed_native_frames')==expected and
        raw.get('monitor_overloads_nominal_half')==0 and
        raw.get('nonfinite_states')==0 and raw.get('first_bad_frame') is None and
        raw.get('windows28')==max(0,expected-27) and
        raw.get('excursions28')==0 and
        7<=raw.get('min_ones28',-1)<=raw.get('max_ones28',99)<=22 and
        0<=raw.get('peak',float('inf'))<=.5+1./(2**31-1) and
        len(state)==8 and all(math.isfinite(x) and 0<=x<b
                              for x,b in zip(state,bounds)))
    snapshots=sorted(args.prefix.parent.glob(args.prefix.name+'-*.state'))
    final=Path(str(args.prefix)+'-final.state')
    if not final.is_file() or Path(str(args.prefix)+'-failure.state').exists():passed=False
    if execution_pass and final.is_file():
        segment=execution['segment_seconds']
        if len(snapshots)!=args.seconds//segment+1 or execution['final_snapshot_sha256']!=sha(final):
            passed=False
    sustained=args.seconds>=3600
    host_complete=bool(execution_pass and execution.get('host_before',{}).get('cpu_model') and
                       execution.get('host_before',{}).get('affinity_cpu_ids'))
    record=dict(schema='P19/DSD1024-v2-guarded-soak-assessment/1',
        status=('PASS_SOAK_INPUT_GATE' if passed and sustained else
                'PASS_SHORT_SMOKE_ONLY' if passed else
                'UNVERIFIED_EXECUTION' if not execution_pass else 'FAIL'),
        qualified=False,rate_hz=args.rate,seconds=args.seconds,
        expected_native_frames=expected,guard_bounds=bounds,
        max_abs_state=state,guard_utilization=utilization,
        maximum_guard_utilization=max(utilization,default=None),
        frozen_p19_guard_sha256=sha(GUARDS),raw_report_sha256=sha(report),
        sample_executable_sha256=sha(args.unit),
        execution_receipt_sha256=sha(execution_path) if execution_path.is_file() else None,
        execution_verified=execution_pass,host_identity_recorded=host_complete,mode=mode,
        snapshot_sha256={p.name:sha(p) for p in snapshots},
        final_snapshot_present=final.is_file(),
        raw=dict(status=raw.get('status'),failure=raw.get('failure'),
            nonfinite=raw.get('nonfinite_states'),
            overloads=raw.get('monitor_overloads_nominal_half'),
            first_bad_frame=raw.get('first_bad_frame'),windows28=raw.get('windows28'),
            min_ones28=raw.get('min_ones28'),max_ones28=raw.get('max_ones28'),
            longest_run=raw.get('longest_run')),
        machine_provenance='Operator supplies independent CPU model, ISA, build flags, governor, affinity, frequency, thermal and interference data',
        limits='one deterministic program, not independent media or multi-ISA certification')
    atomic(args.results,record)
    print(record['status'],'rate',args.rate,'max_util',record['maximum_guard_utilization'])
    return 0 if passed and (sustained or not args.require_sustained) else 1
if __name__=='__main__':raise SystemExit(main())
