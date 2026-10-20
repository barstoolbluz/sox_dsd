#!/usr/bin/env python3
"""R9 exact-rational whole-frequency SRC caps closing all v2/DSD256 stop cells.

Three captured stage filters are certified over complete, compact intervals.
One whole-stage certificate is reusable for every output frequency. The two
M=1 stages use an absolute FIR envelope. The M=2 stage is bounded by the sum
of its complementary aliases. The remaining stages use separately justified
coefficient norms / finite-difference uniform majorants.

A witness is a set of subdivision HINTS; the verifier recomputes exact bounds
from source-bound coefficients and never accepts historical PASS assertions.
"""
from __future__ import annotations
from fractions import Fraction as F
from pathlib import Path
import argparse,hashlib,json

from p15_full_band_campaign import canonical_plan,digest
from p15_r7_witness import binding_for
from p15_r6_witness import RECEIPTS
from p15_r6_exact_composite import ExactComposite,ExactRefusal
from p15_r7_fast_fir import certify_fir_auto
from p15_r8_dyadic_engine import ceil_dyadic
from p15_r9_uniform_stop import verify as verify_native,atomic,NATIVE_TARGET
from p15_r9_src_global_family import (stage_global_alias_cap,all_profile_cells,
                                       STOP_LIMIT)

HERE=Path(__file__).resolve().parent
SCHEMA='P15/R9/whole-src-stage-frequency-envelope/1'
RESULT_SCHEMA='P15/R9/all-v2-dsd256-source-stop-acceptance/1'
REQUIRED={
 'dsd256.mastering_v2.pcm48000':(6,F(101,100),'single'),
 'dsd256.mastering_v2.pcm96000':(7,F(11,10),'paired'),
 'dsd256.mastering_v2.pcm192000':(6,F(101,100),'single')
}

def hash_bytes(b):return hashlib.sha256(b).hexdigest()
def hash_file(p):return hash_bytes(Path(p).read_bytes())

def method_hashes():
    names=('p15_r9_src_strong.py','p15_r9_uniform_stop.py','p15_r9_src_global_family.py',
           'p15_r7_fast_fir.py','p15_r7_engine.py','p15_r5_exact_trig.py',
           'p15_r5_integer_spectral.py','p15_r6_exact_composite.py',
           'p15_src_stagewise_alias_proof.py','p15_src_bound_operator.py')
    return {p:hash_file(HERE/p) for p in names}


def get_stage(name):
    if name not in REQUIRED:raise ExactRefusal('unreviewed rate for sharpened SRC cap')
    r=next((r for r in canonical_plan(1000) if r['cell_id']==name),None)
    if r is None:raise ExactRefusal('unbound SRC rate')
    job,op,binding=binding_for(RECEIPTS/(digest(r)+'.json'))
    if job['cell_id']!=name or job['profile']!='decode.mastering.v2.dsd256':
        raise ExactRefusal('SRC rate profile/source binding mismatch')
    e=ExactComposite(job['profile'],op,max_evaluations=0)
    ix,cap,mode=REQUIRED[name]
    s=e.stages[ix]
    if ix<6 or ix>=len(e.stages) or not s.taps:
        raise ExactRefusal('missing required SRC stage')
    if mode=='single' and s.M!=1 or mode=='paired' and (s.M,s.L)!=(2,1):
        raise ExactRefusal('unexpected source SRC stage topology')
    # Explicit tap position + IEEE binary64 coefficient identity, canonical bytes.
    taps_digest=hash_bytes(('\n'.join(f'{k} {F.from_float(v)}' for k,v in s.taps)+'\n').encode())
    return e,ix,cap,mode,binding,taps_digest


def trusted_header(name):
    e,ix,cap,mode,binding,dig=get_stage(name)
    return {'schema':SCHEMA,'cell':name,'stage_index':ix,
        'stage_topology':[e.stages[ix].L,e.stages[ix].M,e.stages[ix].input_hz,str(e.stages[ix].output_hz)],
        'source_binding':binding,'exact_tap_sha256':dig,'mode':mode,
        'target_cap':str(cap),'method':method_hashes()}


def bound_on_leaf(s,mode,a,b):
    if not F(0)<=a<b<=F(1,4 if mode=='paired' else 2):
        raise ExactRefusal('invalid stage frequency proof leaf')
    h=certify_fir_auto(s.taps,a,b,order=8).upper()/s.L
    if mode=='paired':
        # |H(q+1/2)|=|H(1/2-q)| for REAL FIR and integer tap indices.
        # This exactly accounts for both M=2 reverse aliases.
        h+=certify_fir_auto(s.taps,F(1,2)-b,F(1,2)-a,order=8).upper()/s.L
    return ceil_dyadic(h)


def produce_one(name,output:Path,*,max_nodes=4096):
    e,ix,cap,mode,binding,dig=get_stage(name);header=trusted_header(name)
    end=F(1,4 if mode=='paired' else 2)
    todo=[(F(0),end)]; accepted=[];seen=0
    if output.exists():
        raw=json.loads(output.read_text());
        for k,v in header.items():
            if raw.get(k)!=v:raise ExactRefusal('unbound stage proof checkpoint: '+k)
        if raw.get('status') not in ('OPEN','CANDIDATE'):
            raise ExactRefusal('sealed stage proof is immutable')
        if raw['status']=='CANDIDATE':return {'cell':name,'status':'CANDIDATE','leaves':len(raw['leaves'])}
        todo=[(F(a),F(b)) for a,b in raw['pending']]
        accepted=raw['leaves'];seen=raw['visited']
    while todo:
        if seen>=max_nodes:
            atomic(output,dict(header,status='OPEN',pending=[[str(a),str(b)] for a,b in todo],
                               leaves=accepted,visited=seen,reason='finite adaptive budget'))
            return {'cell':name,'status':'OPEN','accepted':len(accepted),'visited':seen}
        a,b=todo.pop();seen+=1
        upper=bound_on_leaf(e.stages[ix],mode,a,b)
        if upper<cap:
            accepted.append([str(a),str(b)])
        else:
            m=(a+b)/2
            if m in (a,b):raise ExactRefusal('stage proof cannot refine')
            todo.extend(((a,m),(m,b)))
        if seen%20==0:
            atomic(output,dict(header,status='OPEN',pending=[[str(a),str(b)] for a,b in todo],
                               leaves=accepted,visited=seen))
    atomic(output,dict(header,status='CANDIDATE',pending=[],leaves=accepted,visited=seen))
    return {'cell':name,'status':'CANDIDATE','leaves':len(accepted),'visited':seen}


def verify_one(name,source:Path):
    e,ix,cap,mode,binding,dig=get_stage(name);header=trusted_header(name)
    data=json.loads(source.read_text())
    if not isinstance(data,dict):raise ExactRefusal('stage witness not a record')
    for k,v in header.items():
        if data.get(k)!=v:raise ExactRefusal('stage witness header identity mismatch: '+k)
    if data.get('status')!='CANDIDATE' or data.get('pending')!=[]:
        raise ExactRefusal('stage witness not complete')
    leaves=data.get('leaves')
    if not isinstance(leaves,list) or not 1<=len(leaves)<=4096:
        raise ExactRefusal('stage witness missing or oversized')
    positioned=[]
    for pair in leaves:
        if not isinstance(pair,list) or len(pair)!=2:raise ExactRefusal('bad stage leaf')
        a,b=F(pair[0]),F(pair[1])
        if str(a)!=pair[0] or str(b)!=pair[1]:raise ExactRefusal('noncanonical endpoint')
        if not F(0)<=a<b:raise ExactRefusal('bad stage interval')
        positioned.append((a,b))
    positioned.sort()
    cursor=F(0);worst=F(0)
    for a,b in positioned:
        if a!=cursor:raise ExactRefusal('gap or overlap in SRC stage continuum')
        upper=bound_on_leaf(e.stages[ix],mode,a,b)
        if not upper<cap:raise ExactRefusal('SRC stage claimed cap not proven')
        worst=max(worst,upper);cursor=b
    if cursor!=F(1,4 if mode=='paired' else 2):
        raise ExactRefusal('SRC stage missing high endpoint')
    return {'cell':name,'result':'PASS','stage_index':ix,'mode':mode,
            'frequency_domain':['0',str(cursor)],'cover_leaves':len(positioned),
            'upper':str(cap),'max_verified_local_bound':str(worst),
            'source_binding':binding,'stage_taps_sha256':dig,'method_sha256':header['method']}


def prove_all(stages:dict[str,Path],native:Path,*,native_replay=True):
    if set(stages)!=set(REQUIRED):raise ExactRefusal('stage proof set incomplete')
    stage_results={n:verify_one(n,stages[n]) for n in sorted(stages)}
    if native_replay:
        native_result=verify_native(native)
        if native_result.get('status')!='PASS':raise ExactRefusal('native all-band replay failed')
        native_status='PASS'
    else:
        native_status='UNREPLAYED'
    cells=[];count=0
    for name,rows in all_profile_cells().items():
        job,op,binding=binding_for(RECEIPTS/(digest(rows[0])+'.json'))
        e=ExactComposite(job['profile'],op,max_evaluations=0)
        if e.native!=11289600 or e.R!=176400 or len(e.stages)-len(op.stages)!=6:
            raise ExactRefusal('unrecognized native SRC topology')
        total=F(1);factors=[]
        for i in range(6,len(e.stages)):
            if name in REQUIRED and i==REQUIRED[name][0]:
                # Bound proven over complete normalized frequency domain.
                c=REQUIRED[name][1];method='independent-whole-band-stage'
            else:
                c,desc=stage_global_alias_cap(e,i);method=desc['kind']
            total=ceil_dyadic(total*c)
            factors.append([i,str(c),method])
        upper=ceil_dyadic(total*NATIVE_TARGET)
        stopjobs=sum(x['mode']=='stop' for x in rows)
        if not upper<STOP_LIMIT:
            raise ExactRefusal('operator failed source-stop threshold: '+name)
        if native_status=='PASS':count+=stopjobs
        cells.append(dict(cell=name,output_hz=op.output_hz,canonical_source_stop_jobs=stopjobs,
                          stage_caps=factors,src_upper=str(total),
                          composite_source_stop_upper=str(upper),
                          source_binding=binding,
                          verified=bool(native_status=='PASS')))
    return {'schema':RESULT_SCHEMA,'native_status':native_status,
            'native_certificate_sha256':hash_file(native),
            'stage_witness_sha256':{n:hash_file(stages[n]) for n in sorted(stages)},
            'verified_stage_proofs':stage_results,
            'method':method_hashes(),
            'total_source_stop_jobs_proven':count,'cells':cells,
            'global_stop_bound_requirement':str(STOP_LIMIT),
            'native_group_bound':str(NATIVE_TARGET)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--produce',choices=sorted(REQUIRED))
    g.add_argument('--verify-stages',action='store_true')
    g.add_argument('--prove-all',action='store_true')
    ap.add_argument('--witness-dir',required=True,type=Path)
    ap.add_argument('--native-certificate',type=Path)
    ap.add_argument('--src-only',action='store_true',help='Output only a conditional result, not a qualified PASS')
    ap.add_argument('--max-nodes',type=int,default=4096)
    ap.add_argument('--out',type=Path)
    x=ap.parse_args();wd=x.witness_dir;wd.mkdir(parents=True,exist_ok=True)
    stage_files={n:wd/(n+'.json') for n in REQUIRED}
    if x.produce:
        result=produce_one(x.produce,stage_files[x.produce],max_nodes=x.max_nodes)
    elif x.verify_stages:
        result={'status':'PASS','stage_proofs':[verify_one(n,stage_files[n]) for n in sorted(REQUIRED)]}
    else:
        if x.native_certificate is None:raise ExactRefusal('native continuum proof is required')
        result=prove_all(stage_files,x.native_certificate,native_replay=not x.src_only)
    if x.out:atomic(x.out,result)
    print(json.dumps(result if x.produce else {'status':result.get('status',result.get('native_status')),
         'cells':len(result.get('cells',result.get('stage_proofs',[]))),
         'certified_jobs':result.get('total_source_stop_jobs_proven'),
         'source_stop_bounds':[(r['cell'],r['canonical_source_stop_jobs'],
                str(float(F(r['composite_source_stop_upper'])))) for r in result.get('cells',[])]},indent=2),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
