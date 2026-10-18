#!/usr/bin/env python3
"""Replay exact P15 continuum intervals against immutable second-pass baseline.

Each variant is a separate fresh process with an identical timer and recording
contract. Outputs are independent immutable JSON documents keyed by inputs.
Do NOT read new results as full-band certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import time

BASE=Path(__file__).resolve().parent
RESULTS=BASE/'results/P15_prover_third_pass_2026-10-18'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',choices=('second_pass','third_pass'),required=True)
    p.add_argument('--profile',required=True)
    p.add_argument('--input-hz',type=int,required=True)
    p.add_argument('--output-hz',type=int,required=True)
    p.add_argument('--lo',required=True)
    p.add_argument('--hi',required=True)
    p.add_argument('--mode',choices=('pass','stop'),default='pass')
    p.add_argument('--seconds',type=float,default=60)
    p.add_argument('--max-nodes',type=int,default=128)
    p.add_argument('--max-paths',type=int,default=20000)
    p.add_argument('--directory',type=Path,default=RESULTS/'benchmarks')
    a=p.parse_args()
    if not (0<a.seconds<=3600 and a.max_nodes>=1 and 1<=a.max_paths<=100000):
        raise ValueError('invalid resource budget')
    if a.variant=='second_pass':sys.path.insert(0,str(RESULTS/'second_pass_code'))
    else:sys.path.insert(0,str(BASE))
    if str(BASE) not in sys.path:sys.path.insert(1,str(BASE))
    import p15_src_stagewise_continuum as stagewise
    if a.variant=='second_pass' and Path(stagewise.__file__).resolve().parent!=(RESULTS/'second_pass_code').resolve():
        raise RuntimeError('second-pass baseline module not independently isolated')
    if a.variant=='third_pass' and Path(stagewise.__file__).resolve().parent!=BASE.resolve():
        raise RuntimeError('third-pass module not loaded from submitted tree')
    from p15_src_capture_matrix import verify_pair, DEFAULT
    from p15_src_bound_operator import source_identity
    code_sha=hashlib.sha256(Path(stagewise.__file__).read_bytes()).hexdigest()
    import p15_src_interval_recurrence
    fir_sha=hashlib.sha256(Path(p15_src_interval_recurrence.__file__).read_bytes()).hexdigest()
    inputs=dict(profile=a.profile,input_hz=a.input_hz,output_hz=a.output_hz,
        lo=a.lo,hi=a.hi,mode=a.mode,seconds=a.seconds,max_nodes=a.max_nodes,
        max_paths=a.max_paths,variant=a.variant,code_sha256=code_sha,fir_sha256=fir_sha)
    key=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    a.directory.mkdir(parents=True,exist_ok=True)
    target=a.directory/(key+'.json')
    if target.exists():
        found=json.loads(target.read_text())
        if found['inputs']!=inputs:raise RuntimeError('benchmark receipt identity conflict')
        print('SKIP',target,found['result']['status'],found['elapsed_s'],flush=True)
        return
    _,op=verify_pair(DEFAULT/f'{a.input_hz}-{a.output_hz}',a.input_hz,a.output_hz)
    previous=signal.getsignal(signal.SIGALRM)
    def expiration(_s,_f):raise TimeoutError('benchmark interval budget exhausted')
    started=time.perf_counter()
    signal.signal(signal.SIGALRM,expiration)
    try:
        signal.setitimer(signal.ITIMER_REAL,a.seconds,0.05)
        try:
            result=stagewise.certificate(a.profile,op,a.lo,a.hi,mode=a.mode,
                             max_nodes=a.max_nodes,max_paths=a.max_paths)
        except TimeoutError:
            result=dict(status='OPEN',reason='benchmark_interval_seconds_exhausted',qualified_release=False)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    elapsed=time.perf_counter()-started
    doc=dict(schema='P15/third-pass-benchmark/1',inputs=inputs,
        source_sha256=source_identity(),result=result,elapsed_s=elapsed,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        machine=dict(python=sys.version.split()[0],platform=platform.platform()),
        scope='Ideal source-bound FIR continuum LOCAL proof only; not a release certificate')
    content=(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    staging=a.directory/('.'+key+'.'+str(os.getpid()))
    with staging.open('xb') as f:
        f.write(content);f.flush();os.fsync(f.fileno())
    try:os.link(staging,target)
    except FileExistsError:
        if target.read_bytes()!=content:raise RuntimeError('immutable benchmark conflict')
    finally:staging.unlink()
    print(a.variant,a.profile,a.input_hz,a.output_hz,a.lo,a.hi,
          result['status'],result.get('reason',''),round(elapsed,3),'s',target,flush=True)

if __name__=='__main__':main()
