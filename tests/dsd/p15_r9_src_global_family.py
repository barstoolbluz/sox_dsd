#!/usr/bin/env python3
"""Source-bound uniform SRC alias bounds for every DSD256/mastering_v2 rate.

A verified common native-domain stop envelope B and, for each rate, a
frequency-independent operator norm C give source-stop transfer <= B*C.
This is a proof for every output frequency, *not* numerical sampling.

Only the exact R6/R7/R8 coefficient/trigonometric primitives can grant PASS.
The historical campaign PASS flags never enter numerical acceptance.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import math

from p15_full_band_campaign import canonical_plan,digest
from p15_r7_witness import binding_for
from p15_r6_witness import RECEIPTS
from p15_r6_exact_composite import ExactComposite,ExactRefusal
from p15_r8_dyadic_engine import ceil_dyadic
from p15_r9_uniform_stop import NATIVE_TARGET,SCHEMA as NATIVE_SCHEMA,verify as verify_native

HERE=Path(__file__).resolve().parent
SCHEMA='P15/R9/independent-family-uniform-src/1'
PROFILE='decode.mastering.v2.dsd256'
STOP_LIMIT=F(1,10**8)


def digest_file(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stage_global_alias_cap(e,i):
    """Global sum over every reverse branch of stage i, with no omissions.

    For L/M, the reverse stage has exactly M high-rate input-frequency
    branches. If M=1, coefficient L1/L bounds the only branch. If M=2,
    2*(L1/L) bounds both (or the proved halfband complementary-pair
    identity is tighter). For odd M=2p+1, the nearest branch has gain <=
    L1/L, and the other 2p terms can be charged in pairs to minimum
    distances (k-1/2)*Fout for 1<=k<=p. An order-2/4/6 FIR
    finite-difference bound at that distance (where sin increases until
    normalized Nyquist) is sound for all larger magnitudes. Hence the
    sum of the 2p+1 terms is bounded by the sum below for all f.

    All coefficient norms, difference moments and sin lower bounds are
    exact rational/outward constructions. Final reporting rounds UP.
    """
    s=e.stages[i]
    if s.L<1 or s.M<1 or s.input_hz<=0 or s.output_hz!=F(s.input_hz*s.L,s.M):
        raise ExactRefusal('unrecognized SRC stage clock')
    n=e.l1(i)
    if s.M==1:
        return ceil_dyadic(n),{'kind':'one-branch-L1','M':s.M}
    if s.M==2:
        hb=e.halfband_cap(i) if s.L==1 else None
        c=min(2*n,hb[0]) if hb is not None else 2*n
        return ceil_dyadic(c),{'kind':'complementary-halfband' if hb is not None else 'two-branch-L1','M':s.M}
    if s.M%2==0 or s.M>511:
        raise ExactRefusal('unreviewed non-binary SRC stage multiplicity')
    half=(s.M-1)//2
    cap=ceil_dyadic(n)
    terms=[]
    for k in range(1,half+1):
        distance=F(2*k-1,2)*s.output_hz
        qlo=distance/F(s.input_hz*s.L)
        if not F(0)<qlo<=F(1,2):
            raise ExactRefusal('branch distance beyond monotone finite-difference domain')
        diff=e._difference_upper(i,qlo,qlo)
        if diff is None or diff<0:raise ExactRefusal('difference majorant unproved')
        term=ceil_dyadic(min(n,diff))
        cap+=2*term
        terms.append([k,str(term)])
    return ceil_dyadic(cap),{'kind':'odd-branch-exact-difference','M':s.M,'terms':terms}


def all_profile_cells():
    rows={}
    for r in canonical_plan(1000):
        if r['profile']==PROFILE:
            rows.setdefault(r['cell_id'],[]).append(r)
    if len(rows)!=8:raise ExactRefusal('expected exactly eight v2 DSD256 SRC-active cells')
    for name,r in rows.items():
        if len(set((x['mode'],x['lo'],x['hi']) for x in r))!=len(r):
            raise ExactRefusal('duplicate canonical interval: '+name)
        if not any(x['mode']=='stop' for x in r):raise ExactRefusal('cell missing stop worklist')
    return dict(sorted(rows.items()))


def family_src_proofs(*,native_status='CANDIDATE_UNREPLAYED',native_certificate_hash=None):
    proof=[];total=0
    for cell,rows in all_profile_cells().items():
        job,op,binding=binding_for(RECEIPTS/(digest(rows[0])+'.json'))
        if (job['profile'],job['cell_id'])!=(PROFILE,cell):
            raise ExactRefusal('operator rebound to incorrect cell')
        e=ExactComposite(PROFILE,op,max_evaluations=0)
        if e.native!=11289600 or e.R!=176400 or len(e.stages)-len(op.stages)!=6:
            raise ExactRefusal('native profile/topology differs from qualified global native theorem')
        caps=[];contributions=[];prod=F(1)
        for i in range(6,len(e.stages)):
            cap,desc=stage_global_alias_cap(e,i)
            caps.append([i,str(cap),desc]);prod=ceil_dyadic(prod*cap)
        if not caps:raise ExactRefusal('not an SRC-active cell')
        stopjobs=sum(r['mode']=='stop' for r in rows)
        composite=ceil_dyadic(NATIVE_TARGET*prod)
        ok=composite<STOP_LIMIT
        if ok and native_status=='PASS':total+=stopjobs
        proof.append({'cell_id':cell,'target_hz':op.output_hz,
                      'canonical_stop_jobs':stopjobs,
                      'source_binding':binding,
                      'stage_caps':caps,
                      'src_global_upper':str(prod),
                      'composite_stop_upper':str(composite),
                      'uniform_inequality_pass':ok,
                      'mathematically_qualified':bool(ok and native_status=='PASS')})
    return {'schema':SCHEMA,'native_proof_status':native_status,
            'native_certificate_sha256':native_certificate_hash,
            'native_group_upper':str(NATIVE_TARGET),
            'accepted_stop_limit':str(STOP_LIMIT),
            'qualified_canonical_stop_jobs':total,
            'cells':proof,
            'method_sha256':{p:digest_file(HERE/p) for p in ('p15_r9_src_global_family.py','p15_r9_uniform_stop.py','p15_r6_exact_composite.py','p15_r7_fast_fir.py','p15_r5_exact_trig.py','p15_src_stagewise_alias_proof.py')}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-certificate',required=True,type=Path)
    p.add_argument('--src-only',action='store_true',help='Only candidate SRC bounds; native proof remains UNREPLAYED')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if not args.native_certificate.is_file():raise ExactRefusal('native certificate missing')
    native_hash=digest_file(args.native_certificate)
    native_status='CANDIDATE_UNREPLAYED'
    if not args.src_only:
        result=verify_native(args.native_certificate)
        if result.get('status')!='PASS' or result['native_cover_leaves']!=179:
            raise ExactRefusal('native theorem did not independently verify')
        native_status='PASS'
    proof=family_src_proofs(native_status=native_status,native_certificate_hash=native_hash)
    # atomic output, no inadvertent truncated PASS
    from p15_r9_uniform_stop import atomic
    atomic(args.out,proof)
    print(json.dumps({'native_status':native_status,'qualified_stop_jobs':proof['qualified_canonical_stop_jobs'],
         'cells':[(r['cell_id'],r['canonical_stop_jobs'],r['uniform_inequality_pass'],float(F(r['src_global_upper']))) for r in proof['cells']]},indent=2),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
