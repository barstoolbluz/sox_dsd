#!/usr/bin/env python3
"""R8 targeted source-bound 384-kHz certificate producer and independent replayer.

Self-contained add-on to verified cc399928+R6+R7 source. Uses outward dyadic
stage enclosures, all reverse alias paths, conservative stage bounds, and exact
rational leaf partitions. Never reads prior PASS values for proof admission.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import os
import sys
import tempfile

from p15_full_band_campaign import canonical_plan,digest
from p15_r6_witness import RECEIPTS
from p15_r7_witness import binding_for
from p15_r8_dyadic_engine import DyadicComposite
from p15_r6_exact_composite import Split,ExactRefusal,exact_json

HERE=Path(__file__).resolve().parent
SOURCE_FILES=('p15_r8_dyadic_engine.py','p15_r8_highrate_witness.py')
SCHEMA='P15/R8/qualified-dyadic-source-bound-composite/1'
CELL='dsd256.mastering_v2.pcm384000'

def module_hashes():
    return {k:hashlib.sha256((HERE/k).read_bytes()).hexdigest() for k in SOURCE_FILES}

def canonical_context():
    rows=[x for x in canonical_plan(1000) if x['cell_id']==CELL and x['mode']=='pass' and x['lo']=='0']
    if len(rows)!=1 or rows[0]['hi']!='1000':raise ExactRefusal('canonical source window does not match')
    row=rows[0];original=RECEIPTS/(digest(row)+'.json')
    if not original.is_file():raise ExactRefusal('missing original canonical receipt')
    job,op,binding=binding_for(original)
    if job!=row:raise ExactRefusal('original job mismatch')
    return row,op,dict(base=binding,source=module_hashes())

def atomic(path:Path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(payload,sort_keys=True,indent=2).encode('utf-8')+b'\n'
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.r8-',suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def evaluate(a:F,b:F,job,op,*,firs=2000):
    e=DyadicComposite(job['profile'],op,max_evaluations=firs)
    out=e.leaf(a,b,job['mode'],job['source_s'])
    if isinstance(out,Split):return dict(status='SPLIT',at=str(out.at))
    if not out['safe']:return dict(status='OPEN',reason='original spectral inequality was not proved')
    return dict(status='PASS',bound=exact_json({k:v for k,v in out.items() if k!='safe'}),
                fir_evaluations=e.evaluations,alias_frontier=e.alias_frontier)

def produce(out:Path,*,step=100,max_segments=None):
    if not 1<=step<=1000 or 1000%step:raise ExactRefusal('step must divide 1000')
    job,op,binding=canonical_context()
    completed=[];cursor=F(0)
    if out.exists():
        data=json.loads(out.read_text())
        if data.get('schema')!=SCHEMA or data.get('job')!=job or data.get('binding')!=binding:
            raise ExactRefusal('stale or mutated R8 checkpoint')
        completed=data.get('leaves',[])
        for p in completed:
            a,b=F(p['lo']),F(p['hi'])
            if a!=cursor or b<=a:raise ExactRefusal('invalid resumable leaf partition')
            cursor=b
    queued=[]
    for i in range(0,1000,step):
        a=F(i);b=F(i+step)
        if b<=cursor:continue
        if a<cursor:raise ExactRefusal('checkpoint is not aligned with canonical partitions')
        queued.append((a,b))
    while queued and (max_segments is None or len(completed)<max_segments):
        a,b=queued.pop(0)
        if a!=cursor:raise ExactRefusal('gap or overlap in producer')
        result=evaluate(a,b,job,op)
        if result['status']=='SPLIT':
            m=F(result['at'])
            if not a<m<b:raise ExactRefusal('noninterior branch split')
            queued[:0]=[(a,m),(m,b)]
            continue
        if result['status']!='PASS':
            atomic(out,dict(schema=SCHEMA,status='OPEN',job=job,binding=binding,leaves=completed,
                        pending=[[str(a),str(b)]]+[[str(x),str(y)] for x,y in queued],reason=result))
            return dict(status='OPEN',completed=len(completed),next=[str(a),str(b)])
        completed.append(dict(lo=str(a),hi=str(b),bound=result['bound']))
        cursor=b
        atomic(out,dict(schema=SCHEMA,status='CANDIDATE',job=job,binding=binding,leaves=completed))
        print('ACCEPTED',str(a),str(b),'FIRs',result['fir_evaluations'],flush=True)
    state='CANDIDATE' if cursor==1000 else 'OPEN'
    atomic(out,dict(schema=SCHEMA,status=state,job=job,binding=binding,leaves=completed))
    return dict(status=state,leaves=len(completed),covered_until=str(cursor))

def verify(path:Path):
    job,op,binding=canonical_context()
    raw=json.loads(path.read_text())
    if raw.get('schema')!=SCHEMA or raw.get('binding')!=binding or raw.get('job')!=job:
        raise ExactRefusal('source, method or canonical job binding mismatch')
    if raw.get('status')!='CANDIDATE':raise ExactRefusal('incomplete candidate or unexpected state')
    leaves=raw.get('leaves')
    if type(leaves)!=list or not leaves or len(leaves)>10000:raise ExactRefusal('invalid number of leaves')
    cursor=F(0);rechecked=0
    for item in leaves:
        if type(item)!=dict or set(item)!=set(('lo','hi','bound')):raise ExactRefusal('malformed leaf')
        if item['lo']!=str(cursor):raise ExactRefusal('frequency gap/overlap')
        a=F(item['lo']);b=F(item['hi'])
        if not a<b<=1000:raise ExactRefusal('invalid interval')
        found=evaluate(a,b,job,op)
        if found['status']!='PASS' or found['bound']!=item['bound']:
            raise ExactRefusal('independent mathematics or saved bound disagreement')
        cursor=b;rechecked+=1
        print('VERIFIED',str(a),str(b),flush=True)
    if cursor!=F(1000):raise ExactRefusal('missing coverage')
    return dict(status='PASS',replayed_intervals=rechecked,complete_canonical_band=[0,1000],
                source_cell=CELL,binding=binding)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    actions=ap.add_mutually_exclusive_group(required=True)
    actions.add_argument('--produce',type=Path)
    actions.add_argument('--verify',type=Path)
    ap.add_argument('--step',type=int,default=100)
    ap.add_argument('--max-segments',type=int)
    args=ap.parse_args()
    result=(produce(args.produce,step=args.step,max_segments=args.max_segments)
            if args.produce else verify(args.verify))
    print(json.dumps(result,sort_keys=True,indent=2),flush=True)
    return 0 if result['status'] in ('PASS','CANDIDATE') else 2
if __name__=='__main__':sys.exit(main())
