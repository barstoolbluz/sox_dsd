#!/usr/bin/env python3
"""Reprove OLD subdivision geometry under the CURRENT R7 mathematical method.

Old proof bounds and PASS assertions are untrusted. Exact leaf endpoints are
merely scheduling hints. Every leaf is recomputed, canonical coverage and
source hashes checked, then a fresh independent verifier replay is required.
Never overwrite the old candidate: use a distinct --output path.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from p15_r7_witness import (binding_for,engine_for,_leaves_checked,verify,SCHEMA,
    RECEIPTS,_atomic)
from p15_r6_exact_composite import ExactRefusal,Split,frac,exact_json


def regenerate(old_path:Path,new_path:Path):
    raw=json.loads(old_path.read_text())
    if raw.get('schema')!=SCHEMA or type(raw.get('binding')) is not dict:
        raise ExactRefusal('unrecognized old subdivision hints')
    r6=raw['binding'].get('r6_source_and_method')
    if type(r6) is not dict:raise ExactRefusal('missing historical source binder')
    name=r6.get('original_receipt_name','')
    if type(name) is not str or '/' in name or '\\' in name or not name.endswith('.json'):
        raise ExactRefusal('unsafe hint source path')
    job,op,binding=binding_for(RECEIPTS/name)
    if raw.get('job')!=job:raise ExactRefusal('old hint job no longer canonical')
    if (type(raw.get('leaves')) is not list or
        not 1<=len(raw['leaves'])<=100000):raise ExactRefusal('empty hint geometry')
    e=engine_for(job,op)
    rows=[]
    for leaf in raw['leaves']:
        if type(leaf) is not dict or set(leaf)!={'lo','hi','bounds'}:
            raise ExactRefusal('bad hint leaf geometry')
        a,b=frac(leaf['lo']),frac(leaf['hi'])
        result=e.leaf(a,b,job['mode'],job['source_s'])
        if isinstance(result,Split) or not result['safe']:
            raise ExactRefusal('hint subdivision no longer sufficient for R7')
        rows.append(dict(lo=str(a),hi=str(b),
            bounds=exact_json({k:v for k,v in result.items() if k!='safe'})))
    candidate=dict(schema=SCHEMA,job=job,binding=binding,leaves=rows)
    candidate['independent_check']=_leaves_checked(candidate,require_summary=False)
    _atomic(new_path,candidate)
    return verify(candidate)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--old',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    print(json.dumps(regenerate(args.old,args.output),indent=2))
