#!/usr/bin/env python3
"""R7 independently replayed canonical continuous-frequency spectral proofs.

Every PASS requires independently regenerating each bound, checking complete
exact-rational frequency coverage, source fingerprints and stage topology, and
comparing the actual results to the immutable certificate. Producers only
supply subdivisions as hints; no historical aggregate PASS is trusted.

For CPU-bounded exploratory production only, SIGALRM interrupts Python-level
FIR and alias work between safe operations. The accepted bounds in a proof
have no dependence on clock timing or on the solver's choice of subdivisions.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from fractions import Fraction as F
import json
from pathlib import Path
import signal
import sys
import threading
import time

from p15_r6_exact_composite import ExactRefusal,Split,frac,exact_json
from p15_r6_witness import (input_binding,RECEIPTS,code_hashes,
    _atomic,check_proof as r6_check_proof)
from p15_r7_engine import FastComposite
from p15_r5_integer_spectral import IntervalRefusal
from p15_r5_exact_trig import TrigRefusal
from p15_src_bound_operator import sha_file

HERE=Path(__file__).resolve().parent
R7_FILES=('p15_r7_fast_fir.py','p15_r7_engine.py','p15_r7_witness.py')
SCHEMA='P15/R7/source-bound-fast-integer-composite/1'
CHECKPOINT_SCHEMA='P15/R7/atomic-candidate-checkpoint/1'

class BudgetTimeout(TimeoutError):pass

def binding_for(path):
    job,op,base=input_binding(path)
    extra={x:sha_file(HERE/x) for x in R7_FILES}
    return job,op,dict(r6_source_and_method=base,r7_method_sources=extra)

@contextmanager
def guard(seconds):
    """Interrupt pure-Python speculative work; do not promise a C hard timeout."""
    if seconds is None:
        yield;return
    if (not hasattr(signal,'setitimer') or not hasattr(signal,'SIGALRM') or
        threading.current_thread() is not threading.main_thread() or seconds<=0):
        raise ExactRefusal('bounded single-thread SIGALRM unavailable')
    prev=signal.getsignal(signal.SIGALRM)
    prevtimer=signal.getitimer(signal.ITIMER_REAL)
    started=time.monotonic()
    def expired(_sig,_frame):raise BudgetTimeout('wall-clock leaf deadline exhausted')
    signal.signal(signal.SIGALRM,expired)
    try:
        signal.setitimer(signal.ITIMER_REAL,seconds,0)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,prev)
        if prevtimer[0]>0:
            elapsed=time.monotonic()-started
            signal.setitimer(signal.ITIMER_REAL,max(1e-6,prevtimer[0]-elapsed),prevtimer[1])


def engine_for(job,op,limit=10**9):
    return FastComposite(job['profile'],op,max_evaluations=limit)


def _leaves_checked(proof,*,require_summary):
    if not isinstance(proof,dict) or proof.get('schema')!=SCHEMA:
        raise ExactRefusal('unrecognized R7 source-bound certificate')
    binding=proof.get('binding')
    if type(binding) is not dict or type(binding.get('r6_source_and_method')) is not dict:
        raise ExactRefusal('missing R7 source and method fingerprints')
    name=binding['r6_source_and_method'].get('original_receipt_name','')
    if not isinstance(name,str) or '/' in name or '\\' in name or not name.endswith('.json'):
        raise ExactRefusal('noncanonical historical receipt path')
    job,op,expected=binding_for(RECEIPTS/name)
    if binding!=expected or proof.get('job')!=job:
        raise ExactRefusal('R7 receipt, source, operator or verifier method binding changed')
    leaves=proof.get('leaves')
    if type(leaves) is not list or not leaves or len(leaves)>100000:
        raise ExactRefusal('empty/oversized R7 mathematical certificate')
    start,end=frac(job['lo']),frac(job['hi'])
    positioned=[]
    for row in leaves:
        if type(row) is not dict or set(row)!={'lo','hi','bounds'}:
            raise ExactRefusal('malformed witness leaf fields')
        if not isinstance(row['bounds'],dict):raise ExactRefusal('missing interval bound evidence')
        lo,hi=frac(row['lo']),frac(row['hi'])
        if not (start<=lo<hi<=end) or str(lo)!=row['lo'] or str(hi)!=row['hi']:
            raise ExactRefusal('invalid exact frequency endpoint')
        positioned.append((lo,hi,row))
    positioned.sort(key=lambda x:(x[0],x[1]))
    previous=start
    for lo,hi,_ in positioned:
        if lo!=previous:raise ExactRefusal('gap/overlap in canonical frequency cover')
        previous=hi
    if previous!=end:raise ExactRefusal('missing final canonical frequency endpoint')
    e=engine_for(job,op)
    max_unwanted=F(0);min_wanted=None
    for lo,hi,row in positioned:
        output=e.leaf(lo,hi,job['mode'],job['source_s'])
        if isinstance(output,Split) or not output['safe']:
            raise ExactRefusal('replayed leaf has unproved transition/acceptance inequality')
        proofbound=exact_json({k:v for k,v in output.items() if k!='safe'})
        if proofbound!=row['bounds']:
            raise ExactRefusal('false or altered exact composite bound')
        upper=output.get('coherent_alias_upper',output.get('source_stop_upper'))
        max_unwanted=max(max_unwanted,upper)
        if job['mode']=='pass':
            w=output['wanted_lower']
            min_wanted=w if min_wanted is None else min(min_wanted,w)
    result=dict(status='PASS-LOCAL-R7-INDEPENDENT',qualified_release=False,
                leaves=len(positioned),max_composite_unwanted_exact=str(max_unwanted),
                min_wanted_exact=str(min_wanted) if min_wanted is not None else None,
                independently_recomputed_FIRs=e.evaluations,
                stage_alias_frontier_expansions=e.alias_frontier)
    if require_summary and result!=proof.get('independent_check'):
        raise ExactRefusal('R7 summary cannot be reproduced independently')
    return result


def verify(proof):return _leaves_checked(proof,require_summary=True)


def reprove_r6(old:Path,new:Path):
    raw=json.loads(old.read_text())
    # The R6 certificate is checked before its leaf geometry can be reused.
    r6_check_proof(raw)
    original=RECEIPTS/raw['binding']['original_receipt_name']
    job,op,binding=binding_for(original)
    if raw.get('job')!=job:raise ExactRefusal('R6 historical job mismatch')
    e=engine_for(job,op)
    rows=[]
    for old_leaf in raw['leaves']:
        a,b=frac(old_leaf['lo']),frac(old_leaf['hi'])
        ans=e.leaf(a,b,job['mode'],job['source_s'])
        if isinstance(ans,Split) or not ans['safe']:
            raise ExactRefusal('old R6 subdivision insufficient for R7 math')
        rows.append(dict(lo=str(a),hi=str(b),
                         bounds=exact_json({k:v for k,v in ans.items() if k!='safe'})))
    candidate=dict(schema=SCHEMA,binding=binding,job=job,leaves=rows)
    candidate['independent_check']=_leaves_checked(candidate,require_summary=False)
    _atomic(new,candidate)
    return verify(candidate)


def _state(job,binding,pending,rows,*,reason='',visits=0,evals=0):
    return dict(schema=CHECKPOINT_SCHEMA,status='OPEN',
        qualified_release=False,job=job,binding=binding,
        pending=[[str(a),str(b)] for a,b in pending],leaves=rows,
        latest_reason=reason,segment_visits=visits,stage_fir_evaluations=evals)


def produce(original:Path,proof_path:Path,checkpoint:Path,*,resume=False,
            leaf_limit=16,per_leaf_fir=200,per_leaf_seconds=20.,
            total_seconds=100.,minimum_width=F(1,1<<20)):
    if leaf_limit<1 or per_leaf_fir<1 or total_seconds<=0 or per_leaf_seconds<=0 or minimum_width<=0:
        raise ExactRefusal('invalid resource ceilings')
    job,op,binding=binding_for(original)
    start,end=frac(job['lo']),frac(job['hi'])
    pending=[(start,end)];rows=[];visits=0
    if resume and checkpoint.exists():
        data=json.loads(checkpoint.read_text())
        if (data.get('schema')!=CHECKPOINT_SCHEMA or
            data.get('binding')!=binding or data.get('job')!=job or
            data.get('status')!='OPEN'):
            raise ExactRefusal('stale/mutated mathematical checkpoint')
        pending=[(frac(a),frac(b)) for a,b in data['pending']]
        rows=data['leaves']
        if not pending:raise ExactRefusal('nonfinal OPEN checkpoint has empty pending set')
    e=engine_for(job,op)
    started=time.monotonic();reason=''
    while pending and visits<leaf_limit and time.monotonic()-started<total_seconds:
        a,b=pending[-1]
        visits+=1
        e.max_evaluations=e.evaluations+per_leaf_fir
        try:
            remaining=total_seconds-(time.monotonic()-started)
            with guard(min(per_leaf_seconds,max(0.001,remaining))):
                result=e.leaf(a,b,job['mode'],job['source_s'])
        except (BudgetTimeout,ExactRefusal,IntervalRefusal,TrigRefusal) as exc:
            reason=str(exc)
            if (isinstance(exc,ExactRefusal) and
                'evaluation budget exhausted' not in reason):
                break  # structural safety failure, NEVER hide by subdivision
            if b-a<=minimum_width:break
            # Splitting cannot justify PASS by itself; failed work is discarded.
            m=(a+b)/2
            pending[-1:]=[(a,m),(m,b)]
        else:
            if isinstance(result,Split):
                if not a<result.at<b:raise ExactRefusal('invalid split witness')
                pending[-1:]=[(a,result.at),(result.at,b)]
            elif result['safe']:
                rows.append(dict(lo=str(a),hi=str(b),
                    bounds=exact_json({k:v for k,v in result.items() if k!='safe'})))
                pending.pop()
            elif b-a>minimum_width:
                m=(a+b)/2
                pending[-1:]=[(a,m),(m,b)]
            else:
                reason='policy cannot be established at allowed minimum width'
                break
        # Durable at every completed/split leaf; external interruption will
        # at worst repeat one leaf, never accept unverified work.
        _atomic(checkpoint,_state(job,binding,pending,rows,
            reason=reason,visits=visits,evals=e.evaluations),replace=True)
    if pending:
        if not reason:reason='bounded producer resource limit reached'
        state=_state(job,binding,pending,rows,reason=reason,
                     visits=visits,evals=e.evaluations)
        _atomic(checkpoint,state,replace=True)
        return dict(status='OPEN',job=job['cell_id'],mode=job['mode'],
                    pending_count=len(pending),accepted_leaves=len(rows),
                    visits=visits,FIRs=e.evaluations,reason=reason)
    draft=dict(schema=SCHEMA,binding=binding,job=job,leaves=rows)
    # Fully independent replay before publication, with its own new engine.
    draft['independent_check']=_leaves_checked(draft,require_summary=False)
    _atomic(proof_path,draft)
    if checkpoint.exists():
        # A finalized checkpoint is not a PASS source. It may remain on disk.
        _atomic(checkpoint,{**_state(job,binding,[],rows,
            reason='certified proof published'), 'status':'PROOF-PUBLISHED'},replace=True)
    return verify(draft)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    gr=ap.add_mutually_exclusive_group(required=True)
    gr.add_argument('--verify',type=Path)
    gr.add_argument('--original-receipt',type=Path)
    gr.add_argument('--import-r6',type=Path)
    ap.add_argument('--proof',type=Path)
    ap.add_argument('--checkpoint',type=Path)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--max-leaves',type=int,default=16)
    ap.add_argument('--fir-budget',type=int,default=200)
    ap.add_argument('--leaf-seconds',type=float,default=20.)
    ap.add_argument('--total-seconds',type=float,default=100.)
    args=ap.parse_args()
    try:
        if args.verify:
            result=verify(json.loads(args.verify.read_text()))
        elif args.import_r6:
            if not args.proof:raise ExactRefusal('missing --proof destination')
            result=reprove_r6(args.import_r6,args.proof)
        else:
            if not args.proof or not args.checkpoint:
                raise ExactRefusal('missing --proof or --checkpoint')
            result=produce(args.original_receipt,args.proof,args.checkpoint,
                resume=args.resume,leaf_limit=args.max_leaves,
                per_leaf_fir=args.fir_budget,per_leaf_seconds=args.leaf_seconds,
                total_seconds=args.total_seconds)
        print(json.dumps(exact_json(result),indent=2,sort_keys=True))
        return 0 if result['status']=='PASS-LOCAL-R7-INDEPENDENT' else 2
    except (ExactRefusal,BudgetTimeout,IntervalRefusal,TrigRefusal,OSError,
            ValueError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='REFUSED',reason=str(exc)),sort_keys=True),
              file=sys.stderr)
        return 3

if __name__=='__main__':raise SystemExit(main())
