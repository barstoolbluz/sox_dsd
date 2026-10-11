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
    a=ap.parse_args()
    if not (1<=a.repetitions<=100 and 0<=a.warmups<=100 and
            .02<=a.decode_seconds<=30. and .02<=a.encode_seconds<=30.):
        ap.error('out of range benchmark parameters')
    output=a.results/'forced-cli-timing.json'
    report=dict(schema='P11/end-to-end-timing/1',
      platform=platform.platform(),machine=platform.machine(),
      source_identity=dict(sox_sha256=sha(a.sox),candidate_sha256=sha(a.candidate)),
      config=dict(repetitions=a.repetitions,warmups=a.warmups,
                  decode_seconds=a.decode_seconds,encode_seconds=a.encode_seconds,
                  DSD_rate=2822400,PCM_rate=88200,channels=2,
                  threads='single',sox_buffer_bytes=8192,random_seed=11),
      measurements=[],warmups=[],summary={},errors=[],
      note='Host wall time includes CLI startup and output file I/O; no ISA preference inferred')
    r=random.Random(11)
    with tempfile.TemporaryDirectory(prefix='p11-e2e-') as tmp:
        d=Path(tmp)
        dsd=d/'fixture.dsf'
        nbits=max(32,int(a.decode_seconds*2822400)//32*32)
        dsd.write_bytes(fixtures.make_dsf(fixtures.bits(nbits,2),2822400))
        pcm=d/'fixture.wav'
        nr=max(64,int(a.encode_seconds*88200))
        phase=np.arange(nr,dtype=np.float64)/88200.
        audio=np.column_stack((.17*np.sin(2*np.pi*997*phase),
                               .13*np.sin(2*np.pi*791*phase+.35)))
        with wave.open(str(pcm),'wb') as f:
            f.setnchannels(2);f.setframerate(88200);f.setsampwidth(4)
            f.writeframes(np.rint(audio*(2**31-1)).astype('<i4').tobytes())
        report['source_identity'].update(native_sha256=sha(dsd),pcm_sha256=sha(pcm),
                                         native_frames=nbits,pcm_frames=nr)
        for family in ('decode','encode'):
            available=['scalar','sse2','avx1']
            def timed(tier,index,warmup):
                target=d/(f'out-{family}-{tier}.'+('wav' if family=='decode' else 'dsf'))
                if family=='decode':
                    argv=[a.sox,'--dsd-mode','auto','-D','--buffer','8192',
                          '--single-threaded',dsd,'-r','88200',
                          '-e','signed-integer','-b','32',target]
                else:
                    argv=[a.candidate,'--dsd-mode','auto','--dsd-layout-loss','warn',
                          '-D','--buffer','8192','--single-threaded',
                          pcm,'-r','2822400',target]
                env=dict(os.environ,OMP_NUM_THREADS='1',SOX_OPTS='',
                         LSX_DSD_FIR_KERNEL='avx2',LSX_DSD_SDM_KERNEL='avx2')
                env['SOX_DSD_KERNEL_FIR']=tier if family=='decode' else 'not-a-fir-kernel'
                env['SOX_DSD_KERNEL_SDM']=tier if family=='encode' else 'not-an-sdm-kernel'
                t0=time.perf_counter_ns()
                cp=subprocess.run(list(map(str,argv)),env=env,cwd=ROOT,
                                  capture_output=True,text=True,timeout=120)
                elapsed=(time.perf_counter_ns()-t0)/1e9
                if cp.returncode or not target.is_file():
                    raise RuntimeError(f'{family}/{tier} exit={cp.returncode}: {cp.stderr[-300:]}')
                result=dict(family=family,tier=tier,repeat=index,warmup=warmup,
                           wall_seconds=elapsed,output_bytes=target.stat().st_size,
                           sha256=sha(target),exit=cp.returncode)
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
                    samples=len(rows),output_sha256=rows[0]['sha256'])
            atomic(output,report)
    report['status']='PASS' if not report['errors'] else 'FAIL'
    atomic(output,report)
    for family,rows in report['summary'].items():
        print('P11 E2E',family,[(tier,round(r['median_wall_seconds'],5)) for tier,r in rows.items()])
    print('P11 E2E',report['status'])
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
