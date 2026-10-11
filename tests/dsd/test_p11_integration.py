#!/usr/bin/env python3
"""P11 real CLI forced-ISA decoder/encoder integration and invariance.

Tests all supported tiers on actual application graphs, buffer/thread
scheduling and strict rejected force hooks. Does not equate raw one-bit hashes
across different SDM kernels: spectral equivalence is a separate frozen gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
from reference import fixtures, verify


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    p=path.with_suffix('.tmp')
    p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
    p.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,default=ROOT/'src/sox_ng')
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    tiers=('scalar','sse2','avx1')
    a.results.mkdir(parents=True,exist_ok=True)
    output=a.results/'forced-isa-cli.json'
    report=dict(schema='P11/CLI/1',cases=[],checks=[],errors=[],unrun=[],
      qualifications='Real production decoder and uninstalled P10 candidate only; P15 release activation unchanged')
    with tempfile.TemporaryDirectory(prefix='p11-cli-') as temp:
        t=Path(temp)
        source=t/'independent-stereo.dsf'
        frames=282240
        source.write_bytes(fixtures.make_dsf(fixtures.bits(frames,2),2822400))
        pcm=t/'stereo-pcm.wav'
        with wave.open(str(pcm),'wb') as w:
            w.setnchannels(2);w.setsampwidth(4);w.setframerate(88200)
            rate=88200;n=4096
            data=np.arange(n,dtype=np.float64)
            samples=np.column_stack((.21*np.sin(2*np.pi*997*data/rate),
                                    .17*np.sin(2*np.pi*791*data/rate+.2)))
            w.writeframes(np.rint(samples*(2**31-1)).astype('<i4').tobytes())
        source_info=dict(DSF_file_sha256=digest(source),PCM_file_sha256=digest(pcm),
                         native_frames=frames,pcm_frames=n,channels=2)
        report['sources']=source_info
        def clean(s):return str(s).replace(str(ROOT),'<tree>').replace(str(t),'<fixture>')
        def invoke(which,tier,size,thread,active='normal'):
            dst=t/(f'{which}-{tier}-{size}-{thread}-{active}.'+('wav' if which=='decode' else 'dsf'))
            # The intentionally invalid unused family override must NOT affect
            # the context of the active family.
            env=dict(os.environ,OMP_NUM_THREADS='2',
                     SOX_DSD_KERNEL_FIR=tier if which=='decode' else 'not-a-fir-kernel',
                     SOX_DSD_KERNEL_SDM=tier if which=='encode' else 'not-an-sdm-kernel',
                     LSX_DSD_FIR_KERNEL='avx2',LSX_DSD_SDM_KERNEL='avx2',SOX_OPTS='')
            if which=='decode':
                argv=[a.sox,'--dsd-mode','auto','-D','--buffer',str(size),thread,
                      source,'-r','88200','-e','signed-integer','-b','32',dst]
            else:
                argv=[a.candidate,'--dsd-mode','auto','--dsd-layout-loss','warn',
                      '-D','--buffer',str(size),thread,pcm,'-r','2822400',dst]
            proc=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,
                                capture_output=True,text=True,timeout=120)
            row=dict(family=which,tier=tier,buffer_bytes=size,thread=thread,
                     executed_command=[clean(x) for x in argv],
                     env_overrides={k:env[k] for k in ('SOX_DSD_KERNEL_FIR','SOX_DSD_KERNEL_SDM','LSX_DSD_FIR_KERNEL','LSX_DSD_SDM_KERNEL','OMP_NUM_THREADS')},
                     exit=proc.returncode,stderr_tail=clean(proc.stderr[-700:]))
            if active=='normal':
                if proc.returncode!=0 or not dst.is_file():
                    raise RuntimeError(f'{which}/{tier}/{size}/{thread}: {row["exit"]} {row["stderr_tail"]}')
                row['sha256']=digest(dst)
                if which=='decode':
                    with wave.open(str(dst),'rb') as f:
                        if f.getframerate()!=88200 or f.getnchannels()!=2 or f.getsampwidth()!=4:
                            raise ValueError('decoded WAV format mismatch')
                        row['frames']=f.getnframes()
                        row['raw_pcm']=np.frombuffer(f.readframes(f.getnframes()),dtype='<i4').copy()
                    if row['frames']!=(frames+31)//32:
                        raise ValueError(f'expected native /32 frames, got {row["frames"]}')
                else:
                    decoded=verify.decode_dsf(dst.read_bytes())
                    row['frames']=decoded['frames']
                    if row['frames']!=n*32 or decoded['channels']!=2:
                        raise ValueError('encoder graph native count mismatch')
                return row
            if not proc.returncode or dst.exists():
                raise RuntimeError(f'invalid forced tier unexpectedly succeeded or retained output: {row}')
            return row

        for family in ('decode','encode'):
            baselines={}
            for tier in tiers:
                rows=[]
                for size,thread in ((32,'--single-threaded'),(257,'--single-threaded'),
                                    (8192,'--single-threaded'),(8192,'--multi-threaded')):
                    try:
                        row=invoke(family,tier,size,thread)
                        rows.append(row)
                        # Do not preserve raw PCM as megabytes of JSON.
                        pcm_values=row.pop('raw_pcm',None)
                        if pcm_values is not None:
                            row['pcm_samples']=int(pcm_values.size)
                            if tier=='scalar' and size==32 and thread=='--single-threaded':
                                baselines['pcm']=pcm_values
                            if 'pcm' in baselines:
                                delta=int(np.max(np.abs(pcm_values.astype(np.int64)-baselines['pcm'].astype(np.int64))))
                                row['max_graph_lsb_delta_from_scalar']=delta
                                if delta>1:raise ValueError(f'PCM graph >one-LSB difference {delta}')
                        report['cases'].append(row)
                        atomic(output,report)
                    except Exception as exc:
                        report['errors'].append(dict(family=family,tier=tier,buffer=size,thread=thread,error=clean(exc)))
                        atomic(output,report)
                hashes={x['sha256'] for x in rows}
                good=len(rows)==4 and len(hashes)==1
                report['checks'].append(dict(name=f'{family}-{tier}-buffer-thread-byte-invariance',
                                            status='PASS' if good else 'FAIL',case_count=len(rows)))
                atomic(output,report)
            for bad in ('avx2','unsupported'):
                try:
                    row=invoke(family,bad,257,'--single-threaded',active='invalid')
                    report['cases'].append(row)
                    report['checks'].append(dict(name=f'{family}-forced-{bad}-rejected',status='PASS'))
                except Exception as exc:
                    report['errors'].append(dict(family=family,tier=bad,error=clean(exc)))
                atomic(output,report)
        # Neither context exists in a lossless native pass-through. Both
        # unknown public overrides must be inert, not preflight errors.
        dst=t/'native-with-inactive-overrides.dsf'
        env=dict(os.environ,SOX_OPTS='',SOX_DSD_KERNEL_FIR='invalid-fir',
                 SOX_DSD_KERNEL_SDM='invalid-sdm',
                 LSX_DSD_FIR_KERNEL='avx2',LSX_DSD_SDM_KERNEL='avx2')
        cmd=[a.sox,'--dsd-mode','native','-D',source,dst]
        cp=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=120)
        row=dict(family='native-only',tier='both-inactive',exit=cp.returncode,
                 command=[clean(x) for x in cmd],stderr_tail=clean(cp.stderr[-700:]))
        report['cases'].append(row)
        try:
            if cp.returncode or not dst.is_file():
                raise RuntimeError(f'native passthrough rejected inactive overrides: {row}')
            d=verify.decode_dsf(dst.read_bytes())
            if d['frames']!=frames or d['channels']!=2:
                raise AssertionError('native pass-through changed the frame count/layout')
            row['sha256']=digest(dst)
            report['checks'].append(dict(name='native-both-families-inactive',status='PASS'))
        except Exception as exc:
            report['errors'].append(dict(family='native-only',error=clean(exc)))
        atomic(output,report)
    report['status']='PASS' if not report['errors'] and all(x['status']=='PASS' for x in report['checks']) else 'FAIL'
    atomic(output,report)
    for item in report['checks']:
        print('P11 CLI',item['name'],item['status'],flush=True)
    print('P11 forced end-to-end',report['status'],len(report['cases']),'executions',flush=True)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
