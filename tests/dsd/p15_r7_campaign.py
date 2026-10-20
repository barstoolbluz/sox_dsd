#!/usr/bin/env python3
"""Bounded, deterministic, resumable R7 exact mathematical proof fleet.

Historical jobs are an immutable namespace, not evidence of mathematical PASS.
For each selected canonical job, verify an existing R7 witness or run the
candidate proof producer with its own atomic checkpoint. Write a crash-safe
aggregate progress report for audit; the report is never a PASS authority.
No subprocess, physical benchmark, production DSP edit or third-party math.
"""
from __future__ import annotations
import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import time

from p15_full_band_campaign import canonical_plan,digest
from p15_r6_witness import RECEIPTS,_atomic
from p15_r7_witness import produce,verify,SCHEMA,R7_FILES,HERE
from p15_src_bound_operator import sha_file
from p15_r6_exact_composite import ExactRefusal

BASE=Path(__file__).resolve().parents[2]
DEFAULT_OUT=BASE/'tests/dsd/results/P15_R7_EXACT_COMPOSITE_2026-10-19'


def campaign(output:Path,*,cell='*',mode='*',start=0,max_jobs=10,
             run_seconds=60.,job_seconds=14.,leaf_seconds=4.,
             leaves=24,firs=400,check_existing=True):
    plan=canonical_plan(1000)
    if (len(plan)!=11516 or max_jobs<=0 or start<0 or
        run_seconds<=0 or job_seconds<=0 or leaf_seconds<=0):
        raise ExactRefusal('invalid canonical worklist or resource limits')
    selected=[j for j in plan if fnmatchcase(j['cell_id'],cell)
              and fnmatchcase(j['mode'],mode)]
    chosen=selected[start:start+max_jobs]
    output.mkdir(parents=True,exist_ok=True)
    if output.is_symlink():raise ExactRefusal('proof output is a symbolic link')
    journal=output/'R7_CAMPAIGN_PROGRESS.json'
    report=dict(schema='P15/R7/aggregate-unqualified-progress/1',
        original_canonical_jobs=len(plan),selection=dict(cell=cell,mode=mode,start=start,
            max_jobs=max_jobs,run_seconds=run_seconds,job_seconds=job_seconds),
        prover_sha256={n:sha_file(HERE/n) for n in R7_FILES},
        run_dispositions=[])
    started=time.monotonic()
    for job in chosen:
        if time.monotonic()-started>=run_seconds:break
        ident=digest(job)
        original=RECEIPTS/(ident+'.json')
        target=output/(ident+'.r7.json')
        checkpoint=output/(ident+'.open.json')
        elapsed=time.monotonic()-started
        try:
            if target.exists():
                if not check_existing:
                    # Skipping an existing proof is NOT mathematical checking.
                    result=dict(status='PRESENT-NOT-RECHECKED')
                else:
                    result=verify(json.loads(target.read_text()))
            else:
                result=produce(original,target,checkpoint,resume=checkpoint.exists(),
                    leaf_limit=leaves,per_leaf_fir=firs,per_leaf_seconds=leaf_seconds,
                    total_seconds=min(job_seconds,max(.01,run_seconds-elapsed)))
            status=result['status']
            row=dict(job=ident,cell=job['cell_id'],mode=job['mode'],
                     hz=[job['lo'],job['hi']],status=status,
                     canonical_original_sha256=sha_file(original),
                     proof_sha256=sha_file(target) if target.exists() else None,
                     proof_checked_now=bool(target.exists() and status=='PASS-LOCAL-R7-INDEPENDENT'),
                     outstanding_subdivisions=result.get('pending_count'),
                     last_reason=result.get('reason',''))
        except (ExactRefusal,ValueError,KeyError,TypeError,OSError) as exc:
            row=dict(job=ident,cell=job['cell_id'],mode=job['mode'],
                hz=[job['lo'],job['hi']],status='REFUSED',reason=str(exc))
        report['run_dispositions'].append(row)
        _atomic(journal,report,replace=True)
    report['selected_count']=len(selected)
    report['processed_count']=len(report['run_dispositions'])
    report['verified_pass_in_this_run']=sum(x['status']=='PASS-LOCAL-R7-INDEPENDENT'
               for x in report['run_dispositions'])
    report['unqualified_remaining_global']=len(plan)-report['verified_pass_in_this_run']
    # This is a deliberately RUN-LOCAL count, never a claim about proofs
    # previously verified in other processes or campaigns.
    _atomic(journal,report,replace=True)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=DEFAULT_OUT)
    ap.add_argument('--cell',default='*')
    ap.add_argument('--mode',choices=('pass','stop','*'),default='*')
    ap.add_argument('--start',type=int,default=0)
    ap.add_argument('--max-jobs',type=int,default=10)
    ap.add_argument('--run-seconds',type=float,default=60.)
    ap.add_argument('--job-seconds',type=float,default=14.)
    ap.add_argument('--leaf-seconds',type=float,default=4.)
    ap.add_argument('--max-leaves',type=int,default=24)
    ap.add_argument('--fir-budget',type=int,default=400)
    ap.add_argument('--no-reverify-existing',action='store_true',
        help='Label existing jobs PRESENT-NOT-RECHECKED, never PASS')
    args=ap.parse_args()
    report=campaign(args.output,cell=args.cell,mode=args.mode,start=args.start,
        max_jobs=args.max_jobs,run_seconds=args.run_seconds,job_seconds=args.job_seconds,
        leaf_seconds=args.leaf_seconds,leaves=args.max_leaves,firs=args.fir_budget,
        check_existing=not args.no_reverify_existing)
    print(json.dumps(dict(processed=report['processed_count'],
        selected=report['selected_count'],passed=report['verified_pass_in_this_run'],
        statuses=[(x['cell'],x['mode'],x['hz'],x['status'])
                  for x in report['run_dispositions']]),sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
