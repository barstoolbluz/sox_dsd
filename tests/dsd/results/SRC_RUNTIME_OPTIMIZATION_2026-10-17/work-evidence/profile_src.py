#!/usr/bin/env python3
"""Local baseline attribution, using the repository's existing sampler parser."""
import json, os, resource, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT=Path('/workspace/scratch/4dd8292178b8/sox_ng')
sys.path.insert(0,str(ROOT/'tests/dsd'))
from profile_decode import atomic_json, host, sha256, parse_flat_profile
BUILD=ROOT.parent/'build-baseline'
DEST=ROOT.parent/'work-evidence/src-profiles'
DEST.mkdir(exist_ok=True)
os.sched_setaffinity(0,{0})
cases=[('384k-44k-v',384000,44100,'-v',90),
       ('352k-44k-v',352800,44100,'-v',90),
       ('384k-48k-m',384000,48000,'-m',90),
       ('44k-48k-v',44100,48000,'-v',300),
       ('48k-44k-l',48000,44100,'-l',300),
       ('48k-384k-v',48000,384000,'-v',60)]
record={'schema':'src-optimization/baseline-attribution/1','host':host(),
        'binary_sha256':sha256(BUILD/'sox_dsd_profile'),
        'qualification':'local virtual-machine source attribution; no physical gate',
        'cases':[]}
atomic_json(DEST/'profiles.json',record)
for name,ir,orr,q,seconds in cases:
    case=DEST/name;case.mkdir(exist_ok=True)
    source=case/'input.s32'; target=case/'output.s32'
    rng=np.random.default_rng(0x50515)
    remaining=ir*seconds*2
    with source.open('wb') as f:
        while remaining:
            count=min(1<<18,remaining)
            (rng.integers(-(1<<30),1<<30,size=count,dtype=np.int32)>>2).astype('<i4').tofile(f)
            remaining-=count
    cmd=[str(BUILD/'sox_dsd_profile'),'-D','-V4','-t','s32','-L','-r',str(ir),'-c','2',str(source),
         '-t','s32','-L','-r',str(orr),str(target),'rate',q,str(orr)]
    env=dict(os.environ,SOX_OPTS='',LC_ALL='C',OMP_NUM_THREADS='1',GMON_OUT_PREFIX=str(case/'gmon'))
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
    with (case/'stderr.txt').open('wb') as err:
        result=subprocess.run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=err,timeout=180)
    wall=time.perf_counter()-start; after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if result.returncode:raise RuntimeError((name,result.returncode))
    gmon=list(case.glob('gmon.*'))
    gcmd=['gprof','-b','-p',str(BUILD/'sox_dsd_profile'),*map(str,gmon)]
    flat=subprocess.check_output(gcmd,text=True);(case/'gprof.txt').write_text(flat)
    parsed=parse_flat_profile(flat)
    row=dict(name=name,input_hz=ir,output_hz=orr,quality=q,channels=2,audio_seconds=seconds,
             command=cmd,profile_command=gcmd,environment={k:env[k] for k in ['SOX_OPTS','LC_ALL','OMP_NUM_THREADS','GMON_OUT_PREFIX']},
             input_sha256=sha256(source),output_sha256=sha256(target),wall_seconds=wall,
             cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,profile=parsed)
    record['cases'].append(row);atomic_json(DEST/'profiles.json',record)
    source.unlink();target.unlink()
    print(name,'cpu',round(row['cpu_seconds'],3),'top',[(r['symbol'],r['sampled_percent']) for r in parsed['functions'][:8]],flush=True)
