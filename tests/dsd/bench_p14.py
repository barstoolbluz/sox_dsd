#!/usr/bin/env python3
"""P14 observer overhead micro-benchmark; never qualifies ISA preferences.

All four arms transcode exactly the same native source without changing DSP.
Wall-clock ratios only characterize THIS development host/workload. Frozen
original source and output sha256s detect intrusive observational changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import statistics
import subprocess
import tempfile
import time

from reference import fixtures


def run(sox,argv,timeout):
    start=time.monotonic_ns()
    try:
        p=subprocess.run([str(sox),*map(str,argv)],stdin=subprocess.DEVNULL,
                         capture_output=True,text=True,timeout=timeout,
                         env={**os.environ,'OMP_NUM_THREADS':'1'})
        return dict(exit=p.returncode,elapsed_ns=time.monotonic_ns()-start,
                    stderr_tail=p.stderr[-500:])
    except (OSError,subprocess.TimeoutExpired) as e:
        return dict(exit=None,elapsed_ns=time.monotonic_ns()-start,error=str(e))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=pathlib.Path,required=True)
    ap.add_argument('--results',type=pathlib.Path,required=True)
    ap.add_argument('--seconds',type=float,default=.2)
    ap.add_argument('--repetitions',type=int,default=3)
    ap.add_argument('--warmups',type=int,default=1)
    ap.add_argument('--timeout',type=int,default=120)
    args=ap.parse_args()
    if not (0.02<=args.seconds<=10) or not (1<=args.repetitions<=100) or not (0<=args.warmups<=20):
        ap.error('invalid P14 benchmark budget')
    args.results.mkdir(parents=True,exist_ok=True)
    frames=int(2822400*args.seconds)//8*8
    with tempfile.TemporaryDirectory(prefix='p14-bench-') as td:
        path=pathlib.Path(td)
        inp=path/'in.dsf'
        timeline=fixtures.bits(frames,2,'69')
        inp.write_bytes(fixtures.make_dsf(timeline))
        arms=[('native_no_observer',[],[]),
              ('native_basic_report',['--dsd-report'],[]),
              ('native_dsdstat_basic',['--dsd-report'],['dsdstat']),
              ('native_dsdstat_full_analysis',['--dsd-report'],['dsdstat','-a'])]
        rows=[]
        for name,opts,fx in arms:
            out=path/(name+'.dsf');rpt=path/(name+'.json')
            cmd=['--dsd-mode','native']
            if opts:cmd.extend(['--dsd-report',str(rpt)])
            cmd.extend(['-D',str(inp),str(out),*fx])
            timings=[];warm=[]
            for n in range(args.warmups+args.repetitions):
                if out.exists():out.unlink()
                if rpt.exists():rpt.unlink()
                result=run(args.sox,cmd,args.timeout)
                result['sample']=n if n>=args.warmups else None
                if result['exit']==0:
                    result['audio_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
                    if opts:
                        data=json.loads(rpt.read_text())
                        if data.get('status')!='complete':result['exit']=2
                (warm if n<args.warmups else timings).append(result)
                if result['exit']!=0:break
            record=dict(name=name,command=['sox',*('REPORT_PATH' if x==str(rpt) else
                 'AUDIO_INPUT' if x==str(inp) else
                 'AUDIO_OUTPUT' if x==str(out) else x for x in cmd)],
                 warmups=warm,timed=timings,
                 status='PASS' if len(timings)==args.repetitions and all(x['exit']==0 for x in warm+timings) else 'FAIL')
            good=[x['elapsed_ns']/1e9 for x in timings if x['exit']==0]
            record['median_seconds']=statistics.median(good) if good else None
            record['input_logical_frames']=str(frames)
            rows.append(record)
            print(record['status'],name,record['median_seconds'],flush=True)
        baselines=[r['median_seconds'] for r in rows if r['name']=='native_no_observer']
        baseline=baselines[0] if baselines else None
        for r in rows:
            r['relative_wall_overhead_ratio']=r['median_seconds']/baseline if r['median_seconds'] is not None and baseline else None
        output_hashes=[x['audio_sha256'] for row in rows for x in row['timed'] if x.get('audio_sha256')]
        identical=len(set(output_hashes))==1
        done=all(r['status']=='PASS' for r in rows) and identical
        result=dict(schema='sox.dsd.P14.bench.v1',
                    context=dict(platform=platform.machine(),os=platform.system(),
                        cpu_model=next((line.split(':',1)[-1].strip() for line in
                            pathlib.Path('/proc/cpuinfo').read_text(errors='replace').splitlines()
                            if line.startswith('model name')),None)
                            if pathlib.Path('/proc/cpuinfo').exists() else None,
                        virtualized='undetermined',
                        source_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),
                        workload='native stereo DSD64 passthrough; same input and output',
                        duration_seconds=frames/2822400,OS_sched_affinity_recorded=False,
                        note='short development host measurement only, not physical dispatch qualification'),
                    arms=rows,source_audio_equal=identical,
                    automatic_fir='inherited SSE2 when available',
                    automatic_sdm='inherited scalar',
                    physical_silicon_qualification='OPEN',status='PASS' if done else 'FAIL')
        (args.results/'p14-overhead.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
        return 0 if done else 1


if __name__=='__main__':
    raise SystemExit(main())
