#!/usr/bin/env python3
"""CPU and wall-clock comparison of 1.1.1 and 1.1.2 on this same host.

Same source data and native bitstream for both versions. Default decoder rate
changed by design, so also compare decode at an identical explicit PCM rate.
Elapsed and CPU times are observations, not deterministic performance proofs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import tempfile
import time
import wave
import numpy as np

SOURCE_HZ = 705600
NATIVE_HZ = {256:11289600,512:22579200,1024:45158400}
OLD_INTERNAL = 176400
NEW_INTERNAL = {256:352800,512:352800,1024:705600}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def wav_input(path, duration):
    n=round(SOURCE_HZ*duration)
    t=np.arange(n,dtype=np.float64)/SOURCE_HZ
    # In-range, continuous dual tone, high-frequency content above old 40 kHz.
    samples=.08*np.sin(2*np.pi*1411*t)+.055*np.sin(2*np.pi*52111*t)
    frames=np.rint(samples*(2**31-1)).astype('<i4')
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1)
        f.setframerate(SOURCE_HZ)
        f.setsampwidth(4)
        f.writeframes(frames.tobytes())
    return n

def invoke(sox,argv):
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    start=time.perf_counter_ns()
    cmd=[str(sox),*map(str,argv)]
    p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
       stderr=subprocess.PIPE,text=True,timeout=300,
       env={**os.environ,'SOX_OPTS':'','OMP_NUM_THREADS':'1'})
    elapsed=(time.perf_counter_ns()-start)/1e9
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if p.returncode != 0:
        raise RuntimeError(f'{cmd}: {p.returncode}: {p.stderr[-1400:]}')
    return dict(wall_s=elapsed,cpu_user_s=after.ru_utime-before.ru_utime,
                cpu_system_s=after.ru_stime-before.ru_stime,
                cpu_total_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-sox',required=True,type=Path)
    p.add_argument('--sox',required=True,type=Path)
    p.add_argument('--duration',type=float,default=.5)
    p.add_argument('--repetitions',type=int,default=5)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not (.05 <= a.duration <= 10) or not (2 <= a.repetitions <= 30):
        p.error('require 0.05<=duration<=10 and 2<=repetitions<=30')
    binaries={x:p.resolve() for x,p in [('baseline',a.baseline_sox),('candidate',a.sox)]}
    records=[]
    with tempfile.TemporaryDirectory(prefix='dsd112-bench-') as d:
        t=Path(d)
        inp=t/'dual-tone.wav'; n=wav_input(inp,a.duration)
        source_sha=sha(inp)
        for rate,hz in NATIVE_HZ.items():
            reference=t/f'{rate}-reference.dsf'
            invoke(binaries['baseline'],['-D',inp,'-r',hz,reference])
            # warmup each rate and path before timing; remove output on each run.
            for name,binary in binaries.items():
                for task,out_hz in [('encode',None),('decode-default',None),('decode-common',OLD_INTERNAL)]:
                    ext='dsf' if task=='encode' else 'f64'
                    target=t/f'{rate}-{name}-{task}.{ext}'
                    args=(['-D',inp,'-r',hz,target] if task=='encode' else
                           ['--dsd-layout-loss','warn','-D',reference,'-t','f64',
                            *(['-r',out_hz] if out_hz else []),target])
                    invoke(binary,args)
            # Alternating candidate/baseline order reduces thermal/drift bias.
            for rep in range(a.repetitions):
                order=['baseline','candidate'] if rep%2==0 else ['candidate','baseline']
                for task,out_hz in [('encode',None),('decode-default',None),('decode-common',OLD_INTERNAL)]:
                    for name in order:
                        ext='dsf' if task=='encode' else 'f64'
                        target=t/f'{rate}-{name}-{task}.{ext}'
                        args=(['-D',inp,'-r',hz,target] if task=='encode' else
                              ['--dsd-layout-loss','warn','-D',reference,'-t','f64',
                               *(['-r',out_hz] if out_hz else []),target])
                        measured=invoke(binaries[name],args)
                        measured.update(rate=f'DSD{rate}',native_hz=hz,build=name,
                            task=task,rep=rep,bytes_written=target.stat().st_size,
                            pcm_rate_hz=(None if task=='encode' else
                                (out_hz or (OLD_INTERNAL if name=='baseline' else NEW_INTERNAL[rate]))))
                        records.append(measured)
        grouped={}
        for rate in NATIVE_HZ:
            for task in ['encode','decode-default','decode-common']:
                value={}
                for name in binaries:
                    matched=[v for v in records if v['rate']==f'DSD{rate}' and v['task']==task and v['build']==name]
                    value[name]=dict(median_cpu_total_s=statistics.median(r['cpu_total_s'] for r in matched),
                         median_wall_s=statistics.median(r['wall_s'] for r in matched),
                         measured_pcm_rate_hz=matched[0]['pcm_rate_hz'],
                         bytes_written=matched[0]['bytes_written'])
                value['cpu_change_pct']=100*(value['candidate']['median_cpu_total_s']/value['baseline']['median_cpu_total_s']-1)
                value['comparison_scope']=('Default decoded PCM rates differ, so CPU and output size both change.' if task=='decode-default' else 'Same source, native clock and requested output PCM rate.')
                grouped[f'DSD{rate}/{task}']=value
    data=dict(schema='sox-dsd/1.1.2/performance/1',description=__doc__,
        host=dict(platform=platform.platform(),uname=list(platform.uname()),cpu_count=os.cpu_count(),
                  system_load=os.getloadavg()),
        build_parameters='both versions built ./configure --disable-shared --without-libltdl, CFLAGS=-O2 -g, make -j8',
        duration_seconds=a.duration,pcm_source_rate_hz=SOURCE_HZ,pcm_frames=n,
        pcm_sha256=source_sha,
        binaries={v:dict(path=str(binaries[v]),sha256=sha(binaries[v])) for v in binaries},
        repetitions=a.repetitions,raw=records,summary=grouped,
        limitations='CPU microbenchmark from one host and one synthetic input; noisy under concurrent load. No music-corpus or multi-ISA performance claim.')
    # save source hash before temporary files are deleted
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n')
    for key,v in grouped.items():
        print(f"{key:26s} {v['cpu_change_pct']:+7.1f}% CPU (baseline {v['baseline']['median_cpu_total_s']:.4f}s; result {v['candidate']['median_cpu_total_s']:.4f}s)")

if __name__=='__main__':
    main()
