#!/usr/bin/env python3
"""Proof-carrying R6 ideal-composite subset checker, fail closed.

Producer may search subdivisions; verifier receives explicit exact-rational
leaves, reconstructs stage/alias mathematics without trusting reported bounds,
and requires the leaves to cover one exact canonical source-bound job.
No original P15 receipt is ever overwritten or upgraded by this command.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from p15_r6_exact_composite import ExactComposite,ExactRefusal,Split,frac,exact_json
from p15_r5_integer_spectral import IntervalRefusal
from p15_r5_exact_trig import TrigRefusal
from p15_src_bound_operator import source_identity,sha_file,load_snapshot
from p15_src_capture_matrix import DEFAULT as STAGES,verify_pair
from p15_full_band_campaign import canonical_plan,digest
from p15_historical_campaign_binding import historical_bindings
from p15_current_closeout import REBOUND, _reviewed_rebind_admission, _admitted_revision

ROOT=Path(__file__).resolve().parents[2]
RECEIPTS=ROOT/'tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/receipts'
MODULES=('p15_r6_exact_composite.py','p15_r6_exact_policy.py','p15_r5_exact_trig.py',
         'p15_r5_integer_spectral.py','p15_r6_witness.py','p15_src_stagewise_alias_proof.py',
         'p15_src_bound_operator.py','p15_src_capture_matrix.py','p15_src_complete_aliases.py')
PROFILE_BANDS={
    'master64':(20000,40000),'master128':(30000,60000),'master256':(40000,80000),
    'wide64':(35280,44100),'wide128':(70560,88200),'wide256':(141120,176400),
    'decode.mastering.v2.dsd64':(25000,40000),
    'decode.mastering.v2.dsd128':(48000,60000),
    'decode.mastering.v2.dsd256':(66000,80000)
}


def code_hashes(*, historical=False):
    folder=Path(__file__).parent
    hashes={name:sha_file(folder/name) for name in MODULES}
    if historical:
        # Historical mathematical receipts name the *original*, P00-pinned
        # verifier method. Rebinding logic was added later: never rewrite the
        # source identity of the historical R6 method by using our new hash.
        rel='tests/dsd/p15_r6_witness.py'
        revisions,audit=_reviewed_rebind_admission()
        row=revisions[rel]
        _admitted_revision(rel,row['historical_sha256'],
                           row['current_sha256'],revisions,audit)
        hashes['p15_r6_witness.py']=row['historical_sha256']
    return hashes


def canonical_receipt(path:Path):
    if not path.is_file() or path.parent.resolve()!=RECEIPTS.resolve():
        raise ExactRefusal('original receipt must be in immutable campaign inventory')
    record=json.loads(path.read_text())
    job=record.get('job')
    if job is None or job not in canonical_plan(1000) or path.stem!=digest(job):
        raise ExactRefusal('receipt job not in complete canonical frequency worklist')
    if record.get('certificate',{}).get('status') not in (
            'PASS-LOCAL-BAND','PASS-LOCAL-STOP-SOURCE'):
        raise ExactRefusal('historical receipt not a local PASS candidate')
    if job['profile'] not in PROFILE_BANDS:
        raise ExactRefusal('unsupported profile')
    expected_mode='PASS-LOCAL-BAND' if job['mode']=='pass' else 'PASS-LOCAL-STOP-SOURCE'
    if record['certificate']['status']!=expected_mode:
        raise ExactRefusal('candidate mode/status conflict')
    P,S=PROFILE_BANDS[job['profile']]
    if (job['source_s']!=S or frac(job['effective_p'])!=
        min(F(P),F(475,1000)*min(job['intermediate_hz'],job['output_hz']))):
        raise ExactRefusal('source profile/adapt limits mismatch')
    return job


def input_binding(path):
    job=canonical_receipt(path)
    R,Fout=job['intermediate_hz'],job['output_hz']
    stages=STAGES/f'{R}-{Fout}'
    _raw,op=verify_pair(stages,R,Fout)
    raw=json.loads(path.read_text())
    # The certified-2026-10-18 receipts are immutable historical inputs.
    # Read their exact pre-rebind source and binding through independently
    # admitted P00 preimages; still verify the *current* C stage bytes via
    # verify_pair above. This does not grant current-source proof reuse.
    historical=historical_bindings()
    if raw.get('binding')!=historical:
        raise ExactRefusal('historical receipt does not match admitted source lineage')
    archived=ROOT/REBOUND/'preimages'/(
        'tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/'
        f'{R}-{Fout}/operator-binding.json')
    return job,op,dict(
        schema='P15/R6/exact-source-and-prover-binding/1',
        source=historical['source'],design=historical['design'],
        capture_stage=sha_file(stages/'stage-snapshot.json'),
        capture_binding=sha_file(archived),
        original_receipt_name=path.name,original_receipt_sha256=sha_file(path),
        exact_method_sources=code_hashes(historical=True))


def new_engine(job,op,max_fir_evals):
    return ExactComposite(job['profile'],op,max_evaluations=max_fir_evals)


def check_proof(proof):
    """The only PASS authority: replay every claimed leaf and full cover."""
    if proof.get('schema')!='P15/R6/source-bound-integer-composite/1':
        raise ExactRefusal('unrecognized proof schema')
    binding=proof.get('binding')
    if not isinstance(binding,dict):raise ExactRefusal('binding absent')
    receipt=RECEIPTS/binding.get('original_receipt_name','')
    job,op,current=input_binding(receipt)
    if binding!=current or proof.get('job')!=job:
        raise ExactRefusal('proof source, method, receipt, or job identity mutated')
    raw=proof.get('leaves')
    if type(raw) is not list or not raw or len(raw)>100000:
        raise ExactRefusal('missing or oversized leaf witness')
    start=frac(job['lo']);end=frac(job['hi'])
    rows=[]
    for leaf in raw:
        if type(leaf) is not dict or set(leaf)!={'lo','hi','bounds'}:
            raise ExactRefusal('malformed leaf')
        a=frac(leaf['lo']);b=frac(leaf['hi'])
        if not (start<=a<=b<=end) or str(a)!=leaf['lo'] or str(b)!=leaf['hi']:
            raise ExactRefusal('noncanonical/outside exact-rational leaf endpoints')
        rows.append((a,b,leaf))
    rows.sort(key=lambda x:(x[0],x[1]))
    cursor=start
    for a,b,leaf in rows:
        if a!=cursor:raise ExactRefusal('missing or overlapping source frequency interval')
        cursor=b
        if a==b and start!=end:raise ExactRefusal('degenerate interval cannot cover a band')
    if cursor!=end:raise ExactRefusal('proof did not cover final endpoint')
    engine=new_engine(job,op,max_fir_evals=10**9)
    maxima=[];minima=[];evals=0
    for a,b,leaf in rows:
        result=engine.leaf(a,b,job['mode'],job['source_s'])
        if isinstance(result,Split):
            raise ExactRefusal('unresolved exact stage branch transition')
        if not result['safe']:
            raise ExactRefusal('one supplied leaf exceeds a normative policy bound')
        actual=exact_json({k:v for k,v in result.items() if k!='safe'})
        if leaf['bounds']!=actual:
            raise ExactRefusal('reported bound differs from independent exact recomputation')
        maxima.append(result.get('source_stop_upper',result.get('coherent_alias_upper')))
        if job['mode']=='pass':
            minima.append(result['wanted_lower'])
        evals=engine.evaluations
    result=dict(status='PASS-LOCAL-R6-INDEPENDENT',qualified_release=False,
                leaves=len(rows),max_composite_unwanted_exact=str(max(maxima)),
                min_wanted_exact=str(min(minima)) if minima else None,
                independently_recomputed_FIRs=evals,
                stage_alias_frontier_expansions=engine.alias_frontier)
    if result!=proof.get('independent_check'):
        raise ExactRefusal('summary differs from independently replayed proof')
    return result


def _atomic(path,content,*,replace=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(content,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if path.is_symlink():raise ExactRefusal('will not follow output symlink')
    if path.is_file() and not replace:
        if path.read_bytes()!=data:raise ExactRefusal('existing proof differs; refusing overwrite')
        return
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.p15-r6-')
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if replace:
            os.replace(name,path)
        else:
            try:os.link(name,path)
            except FileExistsError:
                if path.is_symlink() or path.read_bytes()!=data:
                    raise ExactRefusal('concurrent proof publication conflict')
        dir_fd=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(dir_fd)
        finally:os.close(dir_fd)
    finally:
        if os.path.exists(name):os.unlink(name)


def run_producer(original,output,checkpoint,*,max_leaf_visits=16,
                 max_fir_evals=120,deadline_seconds=50,resume=False):
    job,op,binding=input_binding(original)
    if binding['source']!=source_identity():
        raise ExactRefusal('historical receipt is replay-only; new proof requires current-source inputs')
    lo=frac(job['lo']);hi=frac(job['hi'])
    pending=[(lo,hi)];accepted=[];visited=0
    if resume and checkpoint.exists():
        past=json.loads(checkpoint.read_text())
        if (past.get('schema')!='P15/R6/incomplete-progress/1' or
                past.get('binding')!=binding or past.get('job')!=job or
                past.get('status')!='OPEN'):
            raise ExactRefusal('checkpoint/method binding changed')
        pending=[(frac(x),frac(y)) for x,y in past['pending']]
        accepted=past['leaves']
        # The producer treats resumed leaves only as candidate hints; only
        # a full independent replay can publish a PASS proof below.
    engine=new_engine(job,op,max_fir_evals)
    started=time.monotonic();reason=''
    while pending:
        if visited>=max_leaf_visits or time.monotonic()-started>=deadline_seconds:
            reason='bounded producer work limit reached';break
        a,b=pending.pop();visited+=1
        try:
            result=engine.leaf(a,b,job['mode'],job['source_s'])
        except (ExactRefusal,IntervalRefusal,TrigRefusal) as exc:
            pending.append((a,b));reason=str(exc);break
        if isinstance(result,Split):
            m=result.at
            if not a<m<b:raise ExactRefusal('nonstrict exact branch split')
            pending.extend(((a,m),(m,b)))
        elif result['safe']:
            accepted.append(dict(lo=str(a),hi=str(b),
                                 bounds=exact_json({k:v for k,v in result.items() if k!='safe'})))
        elif a==b:
            pending.append((a,b));reason='unresolved singleton';break
        else:
            m=(a+b)/2;pending.extend(((a,m),(m,b)))
    if pending:
        partial=dict(schema='P15/R6/incomplete-progress/1',status='OPEN',
                     qualified_release=False,binding=binding,job=job,
                     pending=[[str(a),str(b)] for a,b in pending],leaves=accepted,
                     latest_reason=reason,stage_FIR_evaluations=engine.evaluations,
                     latest_segments_visited=visited)
        _atomic(checkpoint,partial,replace=True)
        return partial
    draft=dict(schema='P15/R6/source-bound-integer-composite/1',
               binding=binding,job=job,leaves=accepted)
    # Compute and validate the entire proof in a fresh engine. An unverified
    # restored checkpoint must NEVER be published as independent PASS.
    check=check_proof({**draft,'independent_check':check_summary_candidate(draft)})
    draft['independent_check']=check
    _atomic(output,draft)
    return check


def check_summary_candidate(draft):
    # Independent pass of the complete output; necessary after resume. The
    # caller supplies only the retained mathematical leaves and bindings.
    binding=draft['binding'];job,op,_=input_binding(RECEIPTS/binding['original_receipt_name'])
    engine=new_engine(job,op,max_fir_evals=10**9)
    aliases=[];wanted=[]
    for row in sorted(draft['leaves'],key=lambda e:(frac(e['lo']),frac(e['hi']))):
        out=engine.leaf(frac(row['lo']),frac(row['hi']),job['mode'],job['source_s'])
        if isinstance(out,Split) or not out['safe']:
            raise ExactRefusal('candidate leaf no longer valid under exact arithmetic')
        aliases.append(out.get('source_stop_upper',out.get('coherent_alias_upper')))
        if job['mode']=='pass':wanted.append(out['wanted_lower'])
    return dict(status='PASS-LOCAL-R6-INDEPENDENT',qualified_release=False,
                leaves=len(draft['leaves']),max_composite_unwanted_exact=str(max(aliases)),
                min_wanted_exact=str(min(wanted)) if wanted else None,
                independently_recomputed_FIRs=engine.evaluations,
                stage_alias_frontier_expansions=engine.alias_frontier)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--original-receipt',type=Path)
    g.add_argument('--verify',type=Path)
    ap.add_argument('--proof',type=Path)
    ap.add_argument('--checkpoint',type=Path)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--max-leaf-visits',type=int,default=16)
    ap.add_argument('--max-fir-evals',type=int,default=120)
    ap.add_argument('--deadline-seconds',type=float,default=50)
    args=ap.parse_args()
    try:
        if args.verify:
            result=check_proof(json.loads(args.verify.read_text()))
        else:
            if not args.proof or not args.checkpoint or args.max_leaf_visits<1 or args.max_fir_evals<1 or args.deadline_seconds<=0:
                raise ExactRefusal('producer needs bounded budgets/proof/checkpoint paths')
            result=run_producer(args.original_receipt,args.proof,args.checkpoint,
                     max_leaf_visits=args.max_leaf_visits,max_fir_evals=args.max_fir_evals,
                     deadline_seconds=args.deadline_seconds,resume=args.resume)
        print(json.dumps(exact_json(result),indent=2,sort_keys=True))
        return 0 if result['status']=='PASS-LOCAL-R6-INDEPENDENT' else 2
    except (ExactRefusal,ValueError,KeyError,TypeError,OSError,TrigRefusal) as e:
        print(json.dumps(dict(status='REFUSED',reason=str(e)),sort_keys=True),file=sys.stderr)
        return 3

if __name__=='__main__':raise SystemExit(main())
