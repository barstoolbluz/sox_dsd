#!/usr/bin/env python3
"""Exploratory P15-R3 v1/v2 decoder cost, NOT the bandwidth-matched release gate.

All commands are real six-channel conversions with two warmups and at least
15 raw repetitions per arm. V1 and V2 differ in bandwidth, so their timing
ratio is *not* a validated legacy or bandwidth-matched comparator; a physical
controlled P15/10.7 experiment remains separately mandatory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import tempfile
import time

from reference import fixtures

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def cpu_metadata():
    info={'system':platform.system(),'machine':platform.machine(),
          'python':platform.python_version(),'uname':platform.uname()._asdict(),
          'cpu_count':os.cpu_count()}
    if hasattr(os,'sched_getaffinity'):
        info['allowed_cpu_ids']=sorted(os.sched_getaffinity(0))
    for name,path in [('model','/proc/cpuinfo'),('governor','/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')]:
        try:
            text=Path(path).read_text()
            info[name]=next((l.strip() for l in text.splitlines() if 'model name' in l), '') if name=='model' else text.strip()
        except OSError:info[name]=None
    return info


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--native-frames',type=int,default=1128960)
    args=ap.parse_args()
    if args.repetitions<15:ap.error('minimum 15 repetitions per arm')
    exe=args.sox.resolve()
    args.results.mkdir(parents=True,exist_ok=True)
    dest=args.results/'local-unmatched-development-benchmark.json'
    obj={'schema':'sox-ng/p15-r3-unmatched-development-timing/1',
         'status':'DEVELOPMENT_ONLY_NOT_10_7', 'release_status':'BLOCKED',
         'purpose':'Track new v2 decode cost relative to old v1 on this host, not a bandwidth-matched reference comparator',
         'limitations':'v1 has a different guaranteed passband; no matched staged-legacy transfer, no independent silicon qualification, no CI acceptance',
         'source_revision':'source archive without Git',
         'binary_sha256':sha(exe),'environment':cpu_metadata(),
         'fixture':{},'cases':[]}
    def save():dest.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
    with tempfile.TemporaryDirectory(prefix='p15r3-bench-') as scratch:
        t=Path(scratch);source=t/'in.dsf';out=t/'out.wav'
        timeline=fixtures.bits(args.native_frames,6,pattern='69')
        source.write_bytes(fixtures.make_dsf(timeline,11289600))
        obj['fixture']=dict(channels=6,native_hz=11289600,native_frames=args.native_frames,
            audio_seconds=args.native_frames/11289600,source_sha256=sha(source))
        save()
        for target in (176400,352800):
            for version in ('v1','v2'):
                ident=f'decode.mastering.{version}.dsd256'
                cmd=[str(exe),'--dsd-mode','auto','--dsd-decode',ident,'-D',
                    str(source),'-r',str(target),'-e','signed-integer','-b','32',str(out)]
                runs=[];audio_hash=None
                for rep in range(-2,args.repetitions):
                    before=resource.getrusage(resource.RUSAGE_CHILDREN)
                    start=time.perf_counter()
                    p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,timeout=100,env={**os.environ,
                            'SOX_OPTS':'','OMP_NUM_THREADS':'1','LC_ALL':'C'})
                    wall=time.perf_counter()-start
                    after=resource.getrusage(resource.RUSAGE_CHILDREN)
                    if p.returncode:raise RuntimeError(f'{ident} output {target}: {p.returncode}: {p.stderr[-500:]}')
                    current=sha(out)
                    if audio_hash is not None and current!=audio_hash:
                        raise AssertionError('nondeterministic output within same profile/rate')
                    audio_hash=current
                    if rep>=0:
                        runs.append(dict(repetition=rep,wall_seconds=wall,
                            process_user_cpu_seconds=after.ru_utime-before.ru_utime,
                            process_system_cpu_seconds=after.ru_stime-before.ru_stime,
                            child_peak_rss_kb=after.ru_maxrss))
                row=dict(profile_id=ident,output_pcm_hz=target,commands_with_actual_paths='sox_ng --dsd-mode auto --dsd-decode '+ident+' -D in.dsf -r '+str(target)+' -e signed-integer -b 32 out.wav',
                    warmups=2, repetitions=args.repetitions,per_repetition=runs,
                    observed_median_wall_seconds=statistics.median(v['wall_seconds'] for v in runs),
                    output_sha256=audio_hash)
                obj['cases'].append(row);save()
    print('P15-R3 exploratory v1/v2 development timing complete',len(obj['cases']),'arms',dest)
    return 0

if __name__=='__main__':raise SystemExit(main())
