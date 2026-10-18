#!/usr/bin/env python3
"""Warm, same-host performance of first-pass vs cached exact derivative weights.

Choose --variant per clean process. The first-pass source is copied byte-for-
byte from the prior signed delivery archive in the evidence baseline folder.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import os
import platform
import resource
import statistics
import sys
import time

BASE=Path(__file__).resolve().parent
OUT=BASE/'results/P15_prover_second_pass_2026-10-18'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--variant',choices=('first_pass','second_pass'),required=True)
    ap.add_argument('--repeats',type=int,default=3)
    args=ap.parse_args()
    if not 1<=args.repeats<=20:raise ValueError('invalid repeats')
    sys.path.insert(0,str(OUT/'first_pass_code') if args.variant=='first_pass' else str(BASE))
    if str(BASE) not in sys.path:sys.path.insert(1,str(BASE))
    from p15_src_fixed_interval import fixed_symmetric_magnitude_bounds
    from p15_src_stagewise_alias_proof import make_src_stages,make_native_stages
    from p15_src_capture_matrix import verify_pair,DEFAULT
    from p15_src_continuum_bounds import TrigPoly
    from p15_src_bound_operator import sha_file
    import p15_src_fixed_interval
    digest=sha_file(Path(p15_src_fixed_interval.__file__))
    dest=OUT/f'FIR_WARM_{args.variant}_{args.repeats}.json'
    if dest.exists():
        doc=json.loads(dest.read_text())
        if doc['fixed_code_sha256']!=digest:raise RuntimeError('baseline identity conflict')
        print('SKIP',dest);return
    _,a=verify_pair(DEFAULT/'176400-48000',176400,48000)
    _,b=verify_pair(DEFAULT/'88200-192000',88200,192000)
    stages={}
    for s in make_native_stages('master128')+make_src_stages(a)+make_src_stages(b):
        stages.setdefault(len(s.taps),s)
    lo=Fraction(1374,10000);hi=lo+Fraction(1,10000000)
    results=[]
    for length in (57,153,720,1005,1845,4160):
        poly=TrigPoly(stages[length].taps,Fraction(0))
        fixed_symmetric_magnitude_bounds(poly,lo,hi)
        samples=[]
        for _ in range(args.repeats):
            t=time.perf_counter()
            result=fixed_symmetric_magnitude_bounds(poly,lo,hi)
            samples.append(time.perf_counter()-t)
        results.append(dict(taps=length,timings_seconds=samples,
            median_seconds=statistics.median(samples),
            lower=float(result[0].a),upper=float(result[1].b)))
        print(args.variant,length,results[-1]['median_seconds'],flush=True)
    doc=dict(schema='P15/rigorous-FIR-second-pass-warm/1',variant=args.variant,
        fixed_code_sha256=digest,repeats=args.repeats,
        normalized_interval=[str(lo),str(hi)],results=results,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        python=platform.python_version(),
        limitation='Warm arithmetic-only benchmark; never a spectral release certificate')
    raw=(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    import tempfile
    fd,tmp=tempfile.mkstemp(prefix='.fir-bench-',dir=OUT)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.link(tmp,dest)
    finally:os.unlink(tmp)
if __name__=='__main__':main()
