#!/usr/bin/env python3
"""P07 explicit decoder timing/memory, WITHOUT a fabricated staged baseline.

The separate inherited P06-hotfix->P07 regression measurement lives in
bench_p06_hotfix.py. This file measures absolute explicit-decode performance
and explicitly records unrun controls unavailable in this phase tree.
No host-unsafe paths or environment-specific temp names are written to JSON.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
from reference import fixtures

WORKLOADS=(('master64_to_705600',2822400,'mastering',705600),
           ('wide256_to_705600',11289600,'wideband',705600))

def one(sox:Path, inp:Path, out:Path, buffer:int, timefile:Path):
    env={**os.environ,'OMP_NUM_THREADS':'1','LC_ALL':'C'}
    command=[str(sox),'--buffer',str(buffer),'-D',str(inp),str(out),
             'dsdpcm','-p',PROFILE,str(RATE)]
    cp=subprocess.run(['/usr/bin/time','-f','%e %U %S %M','-o',str(timefile),*command],
                      capture_output=True,text=True,env=env,timeout=180)
    record=dict(exit_code=cp.returncode)
    if cp.returncode:
        record['diagnostic']=cp.stderr[-250:]
    try:
        a,b,c,d=timefile.read_text().split()
        record.update(wall_seconds=float(a),cpu_seconds=float(b)+float(c),
                      max_rss_kib=int(d))
    except (OSError,ValueError):record['timing_unavailable']=True
    if cp.returncode==0 and out.exists():
        record['pcm_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
    return record

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',required=True,type=Path)
    ap.add_argument('--results',required=True,type=Path)
    ap.add_argument('--frames',type=int,default=1048576)
    ap.add_argument('--repetitions',type=int,default=5)
    args=ap.parse_args()
    if args.frames<=0 or args.frames%8 or not 1<=args.repetitions<=30:
        ap.error('frames must be positive and a multiple of 8; reps 1..30')
    sox=args.sox.resolve()
    if not Path('/usr/bin/time').is_file():
        print('UNRUN P07 explicit-decode timing/memory: /usr/bin/time absent')
        return 2
    allrows=[]
    with tempfile.TemporaryDirectory(prefix='p07bench-') as td:
        t=Path(td)
        for name,native,profile,rate in WORKLOADS:
            global PROFILE,RATE
            PROFILE,RATE=profile,rate
            inp=t/(name+'.dsf')
            inp.write_bytes(fixtures.make_dsf(fixtures.bits(args.frames,1,'distinct'),rate=native))
            cases=[]
            for buffer in (4096,32):
                out=t/'out.wav'
                measures=[]
                for rep in range(args.repetitions+1):
                    if out.exists():out.unlink()
                    r=one(sox,inp,out,buffer,t/'time.txt')
                    if rep:measures.append(r)
                    if r['exit_code']!=0:
                        print('FAIL',name,buffer,rep,r,flush=True)
                        break
                success=all(x['exit_code']==0 for x in measures) and len(measures)==args.repetitions
                digest={r.get('pcm_sha256') for r in measures}
                cases.append(dict(buffer_samples=buffer,
                            status='measured' if success and len(digest)==1 else 'failed',
                            repetitions=measures,
                            median_cpu_seconds=(statistics.median(r['cpu_seconds'] for r in measures)
                            if success else None),
                            median_max_rss_kib=(statistics.median(r['max_rss_kib'] for r in measures)
                            if success else None)))
            same=bool(cases[0]['repetitions'] and cases[1]['repetitions'] and
                      {r.get('pcm_sha256') for c in cases for r in c['repetitions'] if r['exit_code']==0}
                      and len({r.get('pcm_sha256') for c in cases for r in c['repetitions'] if r['exit_code']==0})==1)
            allrows.append(dict(name=name,profile=profile,native_hz=native,
                           output_hz=rate,channels=1,native_frames=args.frames,
                           source_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),
                           output_equivalent_across_buffers=same,cases=cases))
    completed=all(r['output_equivalent_across_buffers'] and
                  all(c['status']=='measured' for c in r['cases']) for r in allrows)
    report=dict(schema='sox.dsd.p07.explicit-decode-benchmark.v1',
        status='absolute-throughput-measured-not-gate-certified' if completed else 'failed',
        baseline='P06-hotfix',
        baseline_exclusion='P06 has no executable dsdpcm or matched staged composite',
        direct_control=dict(status='unrun',reason='no independent bandwidth-matched direct DSD decoder available'),
        staged_control=dict(status='unrun',reason='no independent bandwidth-matched staged CLI decoder available'),
        host_qualification='unprepared, timing noise above 2% admissibility limit',
        measurements=allrows)
    args.results.mkdir(parents=True,exist_ok=True)
    path=args.results/'explicit-decode.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)
    print(json.dumps({'status':report['status'],
                      'median_results':[(r['name'],[(c['buffer_samples'],c['median_cpu_seconds'],c['median_max_rss_kib']) for c in r['cases']]) for r in allrows]},indent=2))
    return 0 if completed else 1

if __name__=='__main__':raise SystemExit(main())
