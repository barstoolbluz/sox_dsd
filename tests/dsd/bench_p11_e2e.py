#!/usr/bin/env python3
"""P11 full-graph timing: ISA-forced native decode and P10 candidate encode.

Uses 15 randomized repeats and two warmups per tier. Output hashes within a
single forced tier must not change. Cross-ISA SDM hashes are NOT an oracle.
Host wall timings include open/close and I/O, are not silicon preference data.
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
import tempfile
import time
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
from reference import fixtures


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--sox',type=Path,default=ROOT/'src/sox_ng')
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--decode-seconds',type=float,default=.5)
    ap.add_argument('--encode-seconds',type=float,default=.125)
    ap.add_argument('--phase',default='P11')
    ap.add_argument('--tiers',nargs='+',default=['scalar','sse2','avx1'])
    ap.add_argument('--native-rate',type=int,choices=[2822400,5644800,11289600],default=2822400)
    ap.add_argument('--channels',type=int,choices=[1,2,6],default=2)
    ap.add_argument('--pcm-rate',type=int,choices=[88200,176400,352800,705600],default=88200)
    a=ap.parse_args()
    if not (1<=a.repetitions<=100 and 0<=a.warmups<=100 and
            .02<=a.decode_seconds<=30. and .02<=a.encode_seconds<=30.):
        ap.error('out of range benchmark parameters')
    output=a.results/'forced-cli-timing.json'
    cpuinfo=(Path('/proc/cpuinfo').read_text(errors='replace') if Path('/proc/cpuinfo').is_file() else '')
    cpu_model=next((line.split(':',1)[1].strip() for line in cpuinfo.splitlines()
        if line.startswith('model name')),None)
    report=dict(schema=f'{a.phase}/end-to-end-timing/1',
      platform=platform.platform(),machine=platform.machine(),cpu_model=cpu_model,
      cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
      compiler=subprocess.run(['cc','--version'],capture_output=True,text=True).stdout.splitlines()[0],
      source_identity=dict(sox_sha256=sha(a.sox),candidate_sha256=sha(a.candidate)),
      config=dict(repetitions=a.repetitions,warmups=a.warmups,
                  decode_seconds=a.decode_seconds,encode_seconds=a.encode_seconds,
                  DSD_rate=a.native_rate,PCM_rate=a.pcm_rate,channels=a.channels,
                  threads='single',sox_buffer_bytes=8192,random_seed=11),
      measurements=[],warmups=[],summary={},errors=[],
      note='Host wall time includes CLI startup and output file I/O; no ISA preference inferred')
    r=random.Random(11)
    with tempfile.TemporaryDirectory(prefix='p11-e2e-') as tmp:
        d=Path(tmp)
        dsd=d/'fixture.dsf'
        nbits=max(32,int(a.decode_seconds*a.native_rate)//32*32)
        dsd.write_bytes(fixtures.make_dsf(fixtures.bits(nbits,a.channels),a.native_rate))
        pcm=d/'fixture.wav'
        nr=max(64,int(a.encode_seconds*a.pcm_rate))
        phase=np.arange(nr,dtype=np.float64)/a.pcm_rate
        audio=np.column_stack([.13*np.sin(2*np.pi*(997+53*c)*phase+.35*c)
                               for c in range(a.channels)])
        with wave.open(str(pcm),'wb') as f:
            f.setnchannels(a.channels);f.setframerate(a.pcm_rate);f.setsampwidth(4)
            f.writeframes(np.rint(audio*(2**31-1)).astype('<i4').tobytes())
        report['source_identity'].update(native_sha256=sha(dsd),pcm_sha256=sha(pcm),
                                         native_frames=nbits,pcm_frames=nr)
        for family in ('decode','encode'):
            available=a.tiers
            def timed(tier,index,warmup):
                target=d/(f'out-{family}-{tier}.'+('wav' if family=='decode' else 'dsf'))
                if family=='decode':
                    argv=[a.sox,'--dsd-mode','auto','-D','--buffer','8192',
                          '--single-threaded',dsd,'-r',str(a.pcm_rate),
                          '-e','signed-integer','-b','32',target]
                else:
                    argv=[a.candidate,'--dsd-mode','auto','--dsd-layout-loss','warn',
                          *(['--dsd-layout','FL,FR,FC,LFE,BL,BR'] if a.channels==6 else []),
                          '-D','--buffer','8192','--single-threaded',
                          pcm,'-r',str(a.native_rate),target]
                env=dict(os.environ,OMP_NUM_THREADS='1',SOX_OPTS='',
                         LSX_DSD_FIR_KERNEL='avx2',LSX_DSD_SDM_KERNEL='avx2')
                env['SOX_DSD_KERNEL_FIR']=tier if family=='decode' else 'not-a-fir-kernel'
                env['SOX_DSD_KERNEL_SDM']=tier if family=='encode' else 'not-an-sdm-kernel'
                # /usr/bin/time captures per-process CPU and peak RSS. Its
                # small invocation overhead is included equally in wall time.
                timefile=d/'process-time.txt'
                wrapper=['/usr/bin/time','-f','%U %S %M','-o',str(timefile)] \
                    if Path('/usr/bin/time').is_file() else []
                t0=time.perf_counter_ns()
                cp=subprocess.run(wrapper+list(map(str,argv)),env=env,cwd=ROOT,
                                  capture_output=True,text=True,timeout=120)
                elapsed=(time.perf_counter_ns()-t0)/1e9
                cpu={}
                if wrapper and timefile.is_file():
                    parts=timefile.read_text().split()
                    if len(parts)==3:
                        cpu=dict(cpu_user_seconds=float(parts[0]),
                                 cpu_system_seconds=float(parts[1]),
                                 max_rss_kib=int(parts[2]))
                if cp.returncode or not target.is_file():
                    raise RuntimeError(f'{family}/{tier} exit={cp.returncode}: {cp.stderr[-300:]}')
                result=dict(family=family,tier=tier,repeat=index,warmup=warmup,
                           wall_seconds=elapsed,output_bytes=target.stat().st_size,
                           sha256=sha(target),exit=cp.returncode,**cpu)
                target.unlink()
                return result
            for tier in available:
                for warm in range(a.warmups):
                    try:report['warmups'].append(timed(tier,warm,True))
                    except Exception as exc:report['errors'].append(dict(family=family,tier=tier,warmup=warm,error=str(exc)))
                atomic(output,report)
            for repeat in range(a.repetitions):
                order=available[:]
                r.shuffle(order)
                for tier in order:
                    try:report['measurements'].append(timed(tier,repeat,False))
                    except Exception as exc:report['errors'].append(dict(family=family,tier=tier,repeat=repeat,error=str(exc)))
                    atomic(output,report)
            report['summary'][family]={}
            for tier in available:
                rows=[v for v in report['measurements'] if v['family']==family and v['tier']==tier]
                if len(rows)!=a.repetitions:
                    report['errors'].append(dict(family=family,tier=tier,reason='missing repetitions'))
                    continue
                digests={v['sha256'] for v in rows}
                if len(digests)!=1:
                    report['errors'].append(dict(family=family,tier=tier,reason='output changed across repetitions'))
                wall=[v['wall_seconds'] for v in rows]
                median=statistics.median(wall)
                report['summary'][family][tier]=dict(
                    median_wall_seconds=median,
                    mad_wall_seconds=statistics.median(abs(x-median) for x in wall),
                    min_wall_seconds=min(wall),max_wall_seconds=max(wall),
                    median_over_audio_duration=median/(a.decode_seconds if family=='decode' else a.encode_seconds),
                    samples=len(rows),output_sha256=rows[0]['sha256'],
                    median_cpu_seconds=statistics.median(
                      r.get('cpu_user_seconds',0)+r.get('cpu_system_seconds',0) for r in rows),
                    max_rss_kib=max(r.get('max_rss_kib',0) for r in rows))
            atomic(output,report)
    report['status']='PASS' if not report['errors'] else 'FAIL'
    atomic(output,report)
    for family,rows in report['summary'].items():
        print(a.phase,'E2E',family,[(tier,round(r['median_wall_seconds'],5)) for tier,r in rows.items()])
    print(a.phase,'E2E',report['status'])
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
