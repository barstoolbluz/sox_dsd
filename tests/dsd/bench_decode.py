#!/usr/bin/env python3
"""P06 scalar-kernel and front-end development benchmark, no ISA claims.

All reported commands are repository-relative; release 5% performance
qualification needs a prepared host and a paired unchanged-path baseline.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import platform
import statistics
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[2]
RATES={'64':2822400,'128':5644800,'256':11289600}


def run(command,executable):
    proc=subprocess.run([str(executable)]+command[1:],cwd=ROOT,capture_output=True,text=True,timeout=180)
    record={'argv':command,'exit':proc.returncode,'stdout':proc.stdout.strip(),'stderr':proc.stderr.strip()}
    if proc.returncode:
        raise RuntimeError(f'benchmark failed {command}: {proc.returncode} {proc.stderr}')
    record['values']=[json.loads(line) for line in proc.stdout.splitlines()]
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unit',type=pathlib.Path,default=ROOT/'test/dsd_test_decode')
    p.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P06/bench/scalar')
    p.add_argument('--seconds',type=float,default=.06)
    p.add_argument('--repetitions',type=int,default=3)
    args=p.parse_args()
    if not args.unit.is_file() or not (.001<=args.seconds<=60) or not (1<=args.repetitions<=30):
        p.error('invalid benchmark binary, duration or repetitions')
    args.results.mkdir(parents=True,exist_ok=True)
    result={'schema':'sox-ng/p06-bench/1',
            'method':'compiled C99 scalar measured with C clock() CPU seconds',
            'limitations':'development performance/memory observation only; not an admissible 5% regression qualification; no SIMD',
            'cpu':platform.processor() or platform.machine(),
            'kernel_calls':[], 'frontend_cases':[], 'commands':[],
            'profile_seconds':args.seconds,'repetitions':args.repetitions}
    outfile=args.results/'scalar-bench.json'
    try:
        for count in (1000000,):
            command=['test/dsd_test_decode','--bench-kernels',str(count)]
            record=run(command,args.unit)
            result['commands'].append(record)
            result['kernel_calls'].extend(record['values'])
            outfile.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        for native,name in RATES.items():
            for profile in ('master','wide'):
                for channels in (1,2,6):
                    ident=profile+native
                    frames=int(args.seconds*name)
                    # Warm up CPU/memory alloc once per variant, then timed repetitions.
                    command=['test/dsd_test_decode','--bench',ident,str(channels),str(frames)]
                    runs=[]
                    for sample in range(args.repetitions+1):
                        record=run(command,args.unit)
                        result['commands'].append(record)
                        if sample:runs.append(record['values'][0])
                        outfile.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
                    measurements=[r['frames_per_cpu_second'] for r in runs]
                    result['frontend_cases'].append(dict(profile=ident,channels=channels,
                         frames=frames,intermediate_hz=runs[0]['intermediate_hz'],
                         owned_bytes=runs[0]['owned_bytes'],stage_taps=runs[0]['stage_taps'],
                         frames_per_cpu_second_median=statistics.median(measurements),
                         frames_per_cpu_second_min=min(measurements),
                         frames_per_cpu_second_max=max(measurements),
                         development_samples=runs))
                    outfile.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        result['summary']={'kernel_banks':len(result['kernel_calls']),
                           'frontend_cases':len(result['frontend_cases']),'failed':0,
                           'status':'pass-development-only'}
    finally:
        outfile.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('P06 development scalar benchmark:',len(result['frontend_cases']),
          'front-end configurations,',len(result['kernel_calls']),'bank kernels, all executed')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
