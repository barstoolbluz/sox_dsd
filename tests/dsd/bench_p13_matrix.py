#!/usr/bin/env python3
"""P13 host-scoped AVX2 versus AVX-512F performance suite.

Unqualified VM results never promote an ISA. Record Intel and AMD physical
host gaps explicitly. Raw readings, dispersion, and exit codes are retained.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
TIERS=('avx2','avx512')


def atomic(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--kernel-frames',type=int,default=180000)
    ap.add_argument('--short-seconds',type=float,default=.04)
    ap.add_argument('--long-seconds',type=float,default=.30)
    ap.add_argument('--full-matrix',action='store_true',help='also run multithread + long cases')
    a=ap.parse_args()
    if a.repetitions<15:ap.error('P13 requires at least 15 timed samples')
    report=dict(schema='P13/benchmark-matrix/1',host=dict(platform=platform.platform(),
        machine=platform.machine(),cpu_model=next((l.split(':',1)[1].strip() for l in
           Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'unknown'),
        virtualization='CPUID is virtualized or unknown; not independent vendor hardware certification',
        compiler=subprocess.run(['cc','--version'],capture_output=True,text=True).stdout.splitlines()[0],
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                       ('src/dsd_kernels_avx512.c','src/dsd_kernels_avx2.c','src/dsd_dispatch.c')},
        config=dict(repetitions=a.repetitions,kernel_frames=a.kernel_frames,
                    short_seconds=a.short_seconds,long_seconds=a.long_seconds,
                    full_matrix=a.full_matrix,tiers=TIERS),
        runs=[],comparisons=[],errors=[],unrun=[
            'Physical Intel AVX-512F host: not independently available in this environment',
            'Physical AMD AVX-512F host: not independently available in this environment',
            'Physical microarchitecture-specific default preference: unqualified'],
        note='CPU penalties require full-conversion comparisons; policy remains unchanged')
    suites=[('kernel', [sys.executable,'tests/dsd/bench_p11.py',
        '--unit','test/dsd_test_p11','--phase','P13','--results',str(a.results/'kernel'),
        '--repetitions',str(a.repetitions),'--frames',str(a.kernel_frames),
        '--tiers',*TIERS],a.results/'kernel/kernel-timing.json')]
    # Three rates/representative channel counts, short-file overhead first.
    cases=[(2822400,1,1,a.short_seconds),(5644800,2,1,a.short_seconds),
           (11289600,6,1,a.short_seconds)]
    if a.full_matrix:
        cases.extend([(2822400,1,2,a.long_seconds),(5644800,2,2,a.long_seconds),
                      (11289600,6,2,a.long_seconds)])
    for rate,ch,threads,seconds in cases:
        name=f'dsd{rate//44100}-{ch}ch-{threads}threads-'+('long' if seconds==a.long_seconds and a.full_matrix else 'short')
        path=a.results/name
        cmd=[sys.executable,'tests/dsd/bench_p11_e2e.py','--phase','P13',
           '--results',str(path),'--native-rate',str(rate),'--channels',str(ch),
           '--threads',str(threads),'--decode-seconds',str(seconds),
           '--encode-seconds',str(max(.02,seconds/2)),
           '--repetitions',str(a.repetitions),'--warmups','2','--tiers',*TIERS]
        suites.append((name,cmd,path/'forced-cli-timing.json'))
    output=a.results/'benchmark-matrix.json'
    atomic(output,report)
    for name,cmd,result in suites:
        try:
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=1800,
                env=dict(os.environ,OMP_NUM_THREADS='1',SOX_OPTS=''))
            row=dict(name=name,command=[s.replace(str(ROOT),'<tree>') for s in cmd],
                     exit=p.returncode,artifact=str(result.relative_to(a.results)),
                     stdout_tail=p.stdout[-1400:],stderr_tail=p.stderr[-1400:])
            if result.is_file():
                raw=json.loads(result.read_text())
                row['status']=raw['status']
                for mode,summary in raw['summary'].items():
                    if not all(t in summary for t in TIERS):continue
                    k='median_cpu_ns_per_frame' if name=='kernel' else 'median_wall_seconds'
                    avx2=summary['avx2'][k]
                    avx512=summary['avx512'][k]
                    speedup=avx2/avx512 if avx512>0 else None
                    med_mad=summary['avx512'].get('mad_cpu_ns_per_frame' if name=='kernel' else 'mad_wall_seconds')
                    report['comparisons'].append(dict(suite=name,family=mode,
                        metric=k,avx2_median=avx2,avx512_median=avx512,
                        speedup_avx512_over_avx2=speedup,
                        avx512_mad=med_mad,
                        dispatch_policy='unchanged: no physical-vendor qualification'))
            else:row['status']='FAIL'
            if p.returncode or row['status']!='PASS':
                report['errors'].append(dict(name=name,exit=p.returncode,status=row['status']))
            report['runs'].append(row)
        except Exception as exc:
            report['errors'].append(dict(name=name,error=repr(exc)))
            report['runs'].append(dict(name=name,status='FAIL',error=repr(exc)))
        atomic(output,report)
        print('P13 bench',name,report['runs'][-1]['status'],flush=True)
    report['status']='PASS' if not report['errors'] else 'FAIL'
    atomic(output,report)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
