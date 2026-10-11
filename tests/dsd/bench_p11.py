#!/usr/bin/env python3
"""P11 runnable, 15-repeat, guarded FIR/SDM per-tier CPU benchmark.

This is host-specific evidence, not a dispatch preference or AVX1-only proof.
FIR streaming calls and four-lane block calls are distinguished. Every SDM
kernel executes bounds, overload, finite-state and monitor accounting.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
MODES=('fir-single','fir-block','sdm')
TIERS=('scalar','sse2','avx1')


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
    temp.replace(path)


def host():
    cpuinfo=Path('/proc/cpuinfo')
    t=cpuinfo.read_text(errors='replace') if cpuinfo.is_file() else ''
    model=next((line.split(':',1)[1].strip() for line in t.splitlines()
                if line.startswith('model name')),None)
    cc=subprocess.run(['cc','--version'],capture_output=True,text=True,check=False).stdout
    return dict(platform=platform.platform(),machine=platform.machine(),
                cpu_model=model,compiler=cc.splitlines()[0] if cc else None,
                affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                shared_or_virtualized='unknown; throughput is only valid for this measured host',
                timer='C clock(): process CPU seconds (excludes fixture setup and ISA selection)',
                threads=1)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p11')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=1000000)
    ap.add_argument('--repetitions',type=int,default=15)
    a=ap.parse_args()
    if not 16384<=a.frames<=40000000 or not 1<=a.repetitions<=1000:
        ap.error('out-of-range frames or repetitions')
    a.unit=a.unit.resolve()
    if not a.unit.is_file():ap.error('missing unit executable')
    sources=('src/dsd_dispatch.c','src/dsd_kernels_scalar.c',
             'src/dsd_kernels_sse2.c','src/dsd_kernels_avx1.c',
             'tests/dsd/test_p11.c')
    report=dict(schema='P11/kernel-timing/1',host=host(),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        executable_sha256=hashlib.sha256(a.unit.read_bytes()).hexdigest(),
        config=dict(frames=a.frames,repetitions=a.repetitions,modes=MODES,tiers=TIERS,
                    random_seed=11,guards_and_monitors_active_for_sdm=True),
        raw=[],summary={},errors=[],unrun=[],
        qualification='CPU timing on current host only; not ISA-wide preference evidence')
    output=a.results/'kernel-timing.json'
    r=random.Random(11)
    for mode in MODES:
        # Warm-up each tier without contaminating timed repeats.
        available=[]
        for tier in TIERS:
            cmd=[str(a.unit),'--bench',tier,mode,str(a.frames)]
            p=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT,timeout=120)
            if p.returncode==2:
                report['unrun'].append(dict(mode=mode,tier=tier,reason=p.stderr.strip()))
            elif p.returncode:
                report['errors'].append(dict(mode=mode,tier=tier,kind='warmup',
                                             exit=p.returncode,stderr=p.stderr[-500:]))
            else:available.append(tier)
        atomic(output,report)
        for rep in range(a.repetitions):
            order=available[:]
            r.shuffle(order)
            for tier in order:
                cmd=[str(a.unit),'--bench',tier,mode,str(a.frames)]
                try:
                    p=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT,timeout=120)
                    if p.returncode:raise RuntimeError(f'exit={p.returncode}: {p.stderr[-500:]}')
                    row=json.loads(p.stdout)
                    if row['tier']!=tier or row['mode']!=mode or row['frames']!=a.frames:
                        raise ValueError('result identity mismatch')
                    if not 0<row['cpu_ns_per_frame']<1e6:raise ValueError('invalid rate')
                    report['raw'].append(dict(**row,round=rep,exit=0))
                except (ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
                    report['errors'].append(dict(mode=mode,tier=tier,round=rep,
                                                error=str(exc)))
                atomic(output,report)
        report['summary'][mode]={}
        for tier in available:
            rows=[v for v in report['raw'] if v['tier']==tier and v['mode']==mode]
            if len(rows)!=a.repetitions:continue
            checksums={v['checksum'] for v in rows}
            if len(checksums)>1:
                report['errors'].append(dict(mode=mode,tier=tier,
                                            kind='nondeterministic checksum'))
            measured=[v['cpu_ns_per_frame'] for v in rows]
            median=statistics.median(measured)
            report['summary'][mode][tier]=dict(median_cpu_ns_per_frame=median,
                min_cpu_ns_per_frame=min(measured),
                max_cpu_ns_per_frame=max(measured),
                mad_cpu_ns_per_frame=statistics.median(abs(x-median) for x in measured),
                samples=len(measured),checksum=rows[0]['checksum'])
        atomic(output,report)
    for mode in MODES:
        scalar=report['summary'][mode].get('scalar')
        if scalar:
            for tier in TIERS[1:]:
                candidate=report['summary'][mode].get(tier)
                if candidate:
                    candidate['speedup_over_scalar']=scalar['median_cpu_ns_per_frame']/candidate['median_cpu_ns_per_frame']
    report['status']='PASS' if not report['errors'] and not report['unrun'] else (
        'INCOMPLETE' if report['unrun'] and not report['errors'] else 'FAIL')
    atomic(output,report)
    for mode in MODES:
        print('P11',mode,[(tier,round(row['median_cpu_ns_per_frame'],2))
              for tier,row in report['summary'][mode].items()],flush=True)
    print('P11 benchmark',report['status'],'repetitions',a.repetitions)
    return 0 if report['status']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
