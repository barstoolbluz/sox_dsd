#!/usr/bin/env python3
"""Independent P15-R3 FIR/cascade certificate against production C99 hex words.

Reuses the separately authored P06 high-precision extremum/coherent-image
certifier, NOT the P15-R3 coefficient generator. The composite SRC numerical
qualification remains a separate mandatory, currently open gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
from certify_filters import (load_coefficients, validate_banks,
                             validate_composites)

ROOT=Path(__file__).resolve().parents[2]
META=ROOT/'tests/dsd/reference/p15_r3_coefficients.json'
HEADER=ROOT/'src/dsd_coeffs_v2.h'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--grid',type=int,default=8192)
    args=ap.parse_args()
    meta=json.loads(META.read_text())
    code=HEADER.read_text()
    banks=load_coefficients()  # loads v1 halfband only for the new cascade
    for name,details in meta['banks'].items():
        match=re.search(r'\blsx_dsd_coeff_'+re.escape(name)+r'\[(\d+)\]\s*=\s*\{(.*?)\};',code,re.S)
        if match is None:
            raise AssertionError('missing independent v2 header bank '+name)
        h=np.array([float.fromhex(w.strip()) for w in match.group(2).split(',') if w.strip()],dtype=np.float64)
        if len(h)!=int(match.group(1)) or len(h)!=details['length']:
            raise AssertionError(name+' length mismatch')
        actual=hashlib.sha256(('\n'.join(v.hex() for v in h)+'\n').encode('ascii')).hexdigest()
        if actual!=details['rounded_hex_sha256']:
            raise AssertionError(name+' coefficient identity mismatch')
        banks[name]=h
    for ident,p in meta['profiles'].items():
        expected={'decode.mastering.v2.dsd64':(2822400,88200,25000,40000),
                  'decode.mastering.v2.dsd128':(5644800,176400,48000,60000),
                  'decode.mastering.v2.dsd256':(11289600,176400,66000,80000)}[ident]
        if tuple(p[k] for k in ('native_hz','intermediate_hz','pass_hz','stop_hz'))!=expected:
            raise AssertionError(ident+' product policy mismatch')
        D=p['factor']; names=p['stage_banks'];G=sum((len(banks[name])-1)//2*(1<<j) for j,name in enumerate(names))
        if p['native_hz']!=D*p['intermediate_hz'] or G!=p['delay_native_frames'] or \
                [((G>>j)&1) for j in range(len(names))]!=p['stage_phases'] or \
                G%D!=p['phase_native_frames'] or G//D!=p['discard_output_frames']:
            raise AssertionError(ident+' phase/delay mismatch')
    start=time.monotonic()
    new_names=list(meta['banks'])
    bank_meta={'banks':meta['banks']}
    measured=validate_banks({k:banks[k] for k in new_names},bank_meta)
    composite=validate_composites(banks,meta,args.grid)
    report=dict(schema='sox-ng/p15-r3-fir-certificate/1',source='C99 v2 header bytes, not generator output',
        method='independent P06 derivative-bracketed high-precision bank extrema, composite adaptive localized extrema, full coherent image-sum',
        limitations='numerical extrema evidence, not exhaustive interval arithmetic; full production fractional SRC separately required',
        profile_activation='CANDIDATE_ONLY; FIRST_RELEASE_BLOCKED',elapsed_seconds=time.monotonic()-start,
        banks=measured,profiles=composite,
        summary=dict(banks_passed=sum(v['passes'] for v in measured.values()),
                     profiles_passed=sum(v['passes'] for v in composite.values()),
                     bank_count=len(measured),profile_count=len(composite)))
    args.results.mkdir(parents=True,exist_ok=True)
    out=args.results/'fir-certificate.json'
    out.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print('P15-R3 independent FIR certificate:',report['summary'],'seconds',round(report['elapsed_seconds'],2))
    for ident,x in composite.items():
        print(ident,'pass',x['pass_ripple_db'],'stop',x['stop_max_db'],'alias',x['coherent_alias_sum_db'])
    return 0

if __name__=='__main__':raise SystemExit(main())
