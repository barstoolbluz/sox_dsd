#!/usr/bin/env python3
"""P15 R9: source-bound uniform native-stop x SRC-alias theorem.

Target: DSD256 mastering_v2 / 384000 Hz source-stop spectral requirement.
No historical PASS assertion or binary64 diagnostic controls admission.
This module uses the previously qualified exact rational R5/R6/R7/R8
primitives, source captures, and source-to-operator bindings.
"""
from __future__ import annotations
import argparse
import hashlib
import heapq
import itertools
import json
import math
import os
import tempfile
from fractions import Fraction as F
from pathlib import Path

from p15_r8_highrate_witness import canonical_context
from p15_r8_dyadic_engine import ceil_dyadic
from p15_r7_fast_fir import certify_fir_auto
from p15_r6_exact_composite import ExactComposite,ExactRefusal
from p15_full_band_campaign import canonical_plan
from p15_src_stagewise_continuum import PROFILE_BANDS

HERE=Path(__file__).resolve().parent
CELL='dsd256.mastering_v2.pcm384000'
SCHEMA='P15/R9/uniform-native-stop-factor/1'
NATIVE_TARGET=F(13,10**10) # strictly less than 1.3e-9
LAST_STAGE_CAP=F(1001,1000)
MAX_BINS=1000
MAX_STEPS_PER_BIN=1500


def sha256_bytes(data):return hashlib.sha256(data).hexdigest()

def source_context():
    job,op,binding=canonical_context()
    if job['cell_id']!=CELL or job['profile']!='decode.mastering.v2.dsd256':
        raise ExactRefusal('not the source-bound high-rate v2 target')
    e=ExactComposite(job['profile'],op,max_evaluations=0)
    stages=e.stages;native=e.native;R=e.R;S=PROFILE_BANDS[job['profile']][1]
    if (native,R,S,op.output_hz)!=(11289600,176400,80000,384000):
        raise ExactRefusal('unexpected actual source identity / clocks')
    if len(stages)!=8 or len(op.stages)!=2:
        raise ExactRefusal('unexpected stage count')
    for i,s in enumerate(stages):
        if i<6 and (s.L,s.M)!=(1,2):raise ExactRefusal('native topology changed')
    s6,s7=stages[6:]
    if (s6.L,s6.M,s7.L,s7.M)!=(2,1,160,147):
        raise ExactRefusal('SRC topology changed')
    if (s6.output_hz,s7.input_hz,s7.output_hz)!=(352800,352800,384000):
        raise ExactRefusal('SRC clocks changed')
    if any(not isinstance(v,float) or not math.isfinite(v)
           for s in stages for _,v in s.taps):
        raise ExactRefusal('nonfinite / nonbinary64 tap')
    return job,op,binding,e


def method_identity():
    source=('p15_r9_uniform_stop.py','p15_r8_dyadic_engine.py',
            'p15_r7_fast_fir.py','p15_r7_engine.py',
            'p15_r5_exact_trig.py','p15_r5_integer_spectral.py',
            'p15_r6_exact_composite.py','p15_r6_exact_policy.py',
            'p15_src_stagewise_alias_proof.py','p15_src_complete_aliases.py',
            'p15_src_capture_matrix.py','p15_src_bound_operator.py')
    return {s:sha256_bytes((HERE/s).read_bytes()) for s in source}


def fdist(q:F):
    # Distance to the nearest integer in [0,1/2], exact for negative rationals.
    nearest=(q+F(1,2)).numerator//(q+F(1,2)).denominator
    return abs(q-nearest)


def folded_range(lo:F,hi:F,clock:int):
    """Range of dist(t/clock,Z) over entire closed input interval."""
    if not isinstance(lo,F) or not isinstance(hi,F) or not lo<=hi or clock<=0:
        raise ExactRefusal('invalid folded interval')
    a,b=lo/clock,hi/clock
    l,h=min(fdist(a),fdist(b)),max(fdist(a),fdist(b))
    # Interior integer minima.
    n=a.numerator//a.denominator+1
    if n<=b:l=F(0)
    # Interior half-integer maxima.
    m=(a+F(1,2)).numerator//(a+F(1,2)).denominator
    if F(m)-F(1,2)<a:m+=1
    if F(m)-F(1,2)<=b:h=F(1,2)
    if not F(0)<=l<=h<=F(1,2):raise ExactRefusal('invalid folded result')
    return l,h


def prove_native_global_caps(e,*,last_leaves=None,max_nodes=400):
    """Prove five halfband caps and last FIR <1.001 for every f in [0,1/2]."""
    caps=[]
    for i in range(5):
        q=e._odd_halfband(i)
        if q is None:raise ExactRefusal('native halfband identity missing')
        pair=e.halfband_cap(i)
        if not pair or not F(1)<=pair[0]<F(1001,1000):
            raise ExactRefusal('halfband full-domain cap failed')
        caps.append(pair[0])
    # The final FIR is not a halfband. Prove its full-domain L-infinity bound.
    if last_leaves is None:
        todo=[(F(0),F(1,2))];accepted=[];count=0
        while todo:
            if count>=max_nodes:raise ExactRefusal('global native FIR budget OPEN')
            a,b=todo.pop();count+=1
            cert=certify_fir_auto(e.stages[5].taps,a,b,order=8)
            if cert.upper()<LAST_STAGE_CAP:accepted.append([str(a),str(b)])
            else:
                m=(a+b)/2
                if not a<m<b:raise ExactRefusal('global native FIR cannot split')
                todo.extend(((a,m),(m,b)))
    else:
        accepted=last_leaves
        if not isinstance(accepted,list) or len(accepted)>max_nodes or not accepted:
            raise ExactRefusal('invalid supplied native FIR cover')
        intervals=[]
        for item in accepted:
            if not isinstance(item,list) or len(item)!=2:
                raise ExactRefusal('invalid native FIR leaf')
            a,b=F(item[0]),F(item[1]);
            if not F(0)<=a<b<=F(1,2):raise ExactRefusal('native FIR bad leaf')
            if certify_fir_auto(e.stages[5].taps,a,b,order=8).upper()>=LAST_STAGE_CAP:
                raise ExactRefusal('native FIR upper inequality false')
            intervals.append((a,b))
        intervals.sort()
        cursor=F(0)
        for a,b in intervals:
            if a!=cursor:raise ExactRefusal('native FIR global-cover gap or overlap')
            cursor=b
        if cursor!=F(1,2):raise ExactRefusal('native FIR unproved endpoint')
    caps.append(LAST_STAGE_CAP)
    return tuple(caps),accepted


def prove_src_global_cap(e):
    """An exact frequency-INDEPENDENT bound for SRC alias transfer L1.

    At 384 kHz output, 147 inverse rational branches are k=-73..73
    throughout the open positive Nyquist band; endpoint inherits the limit.
    H2[k] <= min(normL1, exact order-(2,4,6) difference bound at
    fmin=(|k|-1/2)*384000). Prior stage is M=1, bounded by normL1.
    """
    a,b=e.stages[6:]
    if (a.L,a.M,b.L,b.M)!=(2,1,160,147):raise ExactRefusal('unproved SRC topology')
    n=e.l1(7);total=ceil_dyadic(n);terms=[]
    for k in range(1,74):
        minimum=F(2*k-1,2)*b.output_hz
        qlo=minimum/F(b.input_hz*b.L)
        if not F(0)<qlo<=F(1,2):raise ExactRefusal('bad SRC branch floor')
        d=e._difference_upper(7,qlo,qlo)
        if d is None:raise ExactRefusal('source FIR finite difference unavailable')
        upper=ceil_dyadic(min(n,d))
        total+=2*upper
        terms.append([k,str(ceil_dyadic(upper))])
    result=ceil_dyadic(e.l1(6))*total
    if result>=F(7153,1000):raise ExactRefusal('global SRC factor no longer small')
    if result*NATIVE_TARGET>=F(1,10**8):
        raise ExactRefusal('global theorem does not discharge 1e-8')
    return result,terms


def ordered_stages(e,k,a,b):
    """Non-authoritative heuristic; affects work order, never the inequality."""
    m=(a+b)/2+k*e.R
    s=e.stages[:6];rows=[]
    for j,stage in enumerate(s):
        f=float(fdist(m/stage.input_hz))
        est=sum(w*math.cos(2*math.pi*index*f) for index,w in stage.taps)
        rows.append((abs(est),j))
    return tuple(j for _,j in sorted(rows))


def family_ks(e,a,b):
    if not F(0)<=a<b<=F(e.R,2):raise ExactRefusal('outside native folded domain')
    S=PROFILE_BANDS[e.profile][1]
    if a<S<b:raise ExactRefusal('must split source-stop edge exactly')
    K=e.native//e.R
    if e.native%e.R or K%2 or K!=64:
        raise ExactRefusal('unapproved native harmonic lattice')
    # The k=0 source harmonic is in the source stop set only for x>=S;
    # the x=S endpoint is assigned to the RIGHT (stop-bearing) interval.
    return tuple(k for k in range(-K//2,K//2) if k!=0 or a>=S)


def stage_upper(e,stage_index,k,a,b):
    s=e.stages[stage_index]
    lo,hi=folded_range(a+k*e.R,b+k*e.R,s.input_hz)
    return certify_fir_auto(s.taps,lo,hi,order=8).upper()/s.L


def native_candidate(e,caps,a,b,*,target=NATIVE_TARGET,max_steps=MAX_STEPS_PER_BIN):
    ks=family_ks(e,a,b)
    class Leaf:
        __slots__=('k','bounds','order','cursor','upper','used')
        def __init__(self,k):
            self.k=k;self.bounds=list(caps);self.order=ordered_stages(e,k,a,b)
            self.cursor=0;self.used=[];self.upper=math.prod(self.bounds)
    heap=[];ticker=itertools.count();total=F(0);leaves=[]
    for k in ks:
        l=Leaf(k);leaves.append(l);total+=l.upper
        heapq.heappush(heap,(-l.upper,next(ticker),l))
    steps=0
    while total>=target and heap and steps<max_steps:
        _,_,leaf=heapq.heappop(heap)
        if leaf.cursor>=6:continue
        j=leaf.order[leaf.cursor];leaf.cursor+=1
        new_stage=min(leaf.bounds[j],stage_upper(e,j,leaf.k,a,b))
        new=leaf.upper*new_stage/leaf.bounds[j]
        if new>leaf.upper:raise ExactRefusal('refinement increased valid bound')
        total-=leaf.upper-new
        leaf.bounds[j]=new_stage;leaf.upper=new;leaf.used.append(j);steps+=1
        if leaf.cursor<6:heapq.heappush(heap,(-leaf.upper,next(ticker),leaf))
    if not total<target:return None
    return {'lo':str(a),'hi':str(b),
            'stages':[[l.k,l.used] for l in leaves],
            'native_upper':str(ceil_dyadic(total)),
            'calls':steps}


def verify_native_leaf(e,caps,leaf):
    if not isinstance(leaf,dict) or set(leaf)!=set(('lo','hi','stages','native_upper','calls')):
        raise ExactRefusal('bad native leaf shape')
    a,b=F(leaf['lo']),F(leaf['hi']);ks=family_ks(e,a,b)
    if type(leaf['stages']) is not list or len(leaf['stages'])!=len(ks):
        raise ExactRefusal('missing native source family')
    total=F(0);calls=0
    for expected,pair in zip(ks,leaf['stages']):
        if not isinstance(pair,list) or len(pair)!=2 or pair[0]!=expected:
            raise ExactRefusal('reordered or missing harmonic')
        _,stages=pair
        if not isinstance(stages,list) or len(set(stages))!=len(stages) or any(type(j) is not int or not 0<=j<6 for j in stages):
            raise ExactRefusal('invalid refined stage selection')
        factors=list(caps)
        for j in stages:
            factors[j]=min(factors[j],stage_upper(e,j,expected,a,b));calls+=1
        upper=math.prod(factors)
        total+=upper
    if leaf['calls']!=calls:raise ExactRefusal('FIR computation receipt mismatch')
    reported=F(leaf['native_upper'])
    if total>reported or reported>=NATIVE_TARGET:
        raise ExactRefusal('reported upper is not conservative or too loose')
    return total


def atomic(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(body,sort_keys=True,indent=2)+'\n').encode()
    fd,tmp=tempfile.mkstemp(prefix='.r9-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def theorem_context():
    job,op,binding,e=source_context()
    caps,last=prove_native_global_caps(e)
    src,src_terms=prove_src_global_cap(e)
    rows=[r for r in canonical_plan(1000) if r['cell_id']==CELL and r['mode']=='stop']
    if len(rows)!=192:raise ExactRefusal('unexpected canonical stop worklist')
    return e,dict(schema=SCHEMA,source_binding=binding,method=method_identity(),
        cell=CELL,source_stop_hz=80000,intermediate_hz=176400,
        output_hz=384000,canonical_stop_jobs=192,
        source_native_hz=11289600,halfband_caps=[str(x) for x in caps[:5]],
        last_native_global_upper=str(caps[-1]),last_native_cover=last,
        src_global_upper=str(src),src_high_image_bounds=src_terms,
        native_group_target=str(NATIVE_TARGET),
        original_acceptance_upper='1/100000000')


def _check_header(actual,verified):
    for k,v in verified.items():
        if actual.get(k)!=v:raise ExactRefusal('unverified source/method/theorem header: '+k)


def produce(out:Path,*,width=500,max_leaves=None,depth_limit=12):
    if type(width) is not int or not 10<=width<=2000 or max_leaves is not None and max_leaves<1:
        raise ExactRefusal('invalid partition bounds')
    e,header=theorem_context();R=e.R;S=80000
    leaves=[];pending=[]
    for start,end in ((F(0),F(S)),(F(S),F(R,2))):
        p=start
        while p<end:
            stop=min(end,p+width)
            pending.append((p,stop,0));p=stop
    if out.exists():
        saved=json.loads(out.read_text())
        _check_header(saved,header)
        if saved.get('status') not in ('OPEN','CANDIDATE'):
            raise ExactRefusal('completed sealed evidence is immutable')
        leaves=saved.get('leaves',[])
        pending=[(F(a),F(b),int(d)) for a,b,d in saved.get('pending',[])]
        if any(not isinstance(x,dict) for x in leaves):raise ExactRefusal('invalid checkpoint')
        if not pending:raise ExactRefusal('unexpected empty resume queue')
    count=0
    while pending and (max_leaves is None or count<max_leaves):
        a,b,depth=pending.pop(0)
        candidate=native_candidate(e,tuple(F(z) for z in header['halfband_caps'])+(F(header['last_native_global_upper']),),a,b)
        if candidate is None:
            if depth>=depth_limit or b-a<F(1,1024):
                pending.insert(0,(a,b,depth))
                body=dict(header,status='OPEN',leaves=leaves,pending=[[str(x),str(y),d] for x,y,d in pending],reason='finite proof refinement budget exhausted')
                atomic(out,body);return dict(status='OPEN',saved=len(leaves),failed=[str(a),str(b)])
            m=(a+b)/2
            pending[:0]=[(a,m,depth+1),(m,b,depth+1)]
            continue
        leaves.append(candidate);count+=1
        body=dict(header,status='OPEN' if pending else 'CANDIDATE',leaves=leaves,
            pending=[[str(x),str(y),d] for x,y,d in pending])
        atomic(out,body)
        if count%10==0:
            print('R9 PROGRESS',len(leaves),'covered-through',str(b),'pending',len(pending),flush=True)
    return dict(status='CANDIDATE' if not pending else 'OPEN',leaves=len(leaves),
        pending=len(pending))


def verify(path:Path):
    e,header=theorem_context();raw=json.loads(path.read_text())
    _check_header(raw,header)
    if raw.get('status')!='CANDIDATE' or raw.get('pending')!=[]:
        raise ExactRefusal('incomplete certificate')
    leaves=raw.get('leaves')
    if not isinstance(leaves,list) or not leaves or len(leaves)>10000:
        raise ExactRefusal('missing or excessive native domain leaves')
    cursor=F(0);count=0;native_max=F(0)
    for leaf in leaves:
        a,b=F(leaf['lo']),F(leaf['hi'])
        if a!=cursor:raise ExactRefusal('gap or overlap in native continuum')
        if a<80000<b:raise ExactRefusal('stop edge must be exact branch boundary')
        u=verify_native_leaf(e,tuple(F(z) for z in header['halfband_caps'])+(F(header['last_native_global_upper']),),leaf)
        native_max=max(native_max,u)
        cursor=b;count+=1
        if count%10==0:print('R9 REPLAY',count,'covered-through',str(cursor),flush=True)
    if cursor!=F(e.R,2):raise ExactRefusal('native continuum incomplete')
    if F(header['src_global_upper'])*NATIVE_TARGET>=F(1,10**8):
        raise ExactRefusal('complete-source-stop acceptance inequality not established')
    return dict(status='PASS',cell=CELL,scope='all output frequencies and source-stop harmonics',
         certified_canonical_stop_jobs=192,domain=['0',str(cursor)],
         native_source_stop_upper=str(ceil_dyadic(native_max)),
         universal_src_upper=header['src_global_upper'],
         bound_on_all_native_stop_coherent_transfers=str(ceil_dyadic(F(header['src_global_upper'])*NATIVE_TARGET)),
         native_cover_leaves=count,source_binding=header['source_binding'],method=header['method'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    a=p.add_mutually_exclusive_group(required=True);a.add_argument('--produce',type=Path);a.add_argument('--verify',type=Path)
    p.add_argument('--width',type=int,default=500)
    p.add_argument('--max-leaves',type=int)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    result=produce(args.produce,width=args.width,max_leaves=args.max_leaves) if args.produce else verify(args.verify)
    if args.out:atomic(args.out,result)
    print(json.dumps(result,sort_keys=True,indent=2),flush=True)
    return 0 if result['status'] in ('CANDIDATE','PASS') else 2
if __name__=='__main__':raise SystemExit(main())
