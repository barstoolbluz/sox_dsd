#!/usr/bin/env python3
"""Paired P07 graph decoder vs P08 pre-combiner six-channel adapter.

The comparison is legitimate only for single-input merge, which forces P08's
adapter without changing the decoded audio.  P07 runs explicit dsdpcm, P08
uses a private per-input decoder.  Both must produce exactly the same signed
32-bit interleaved samples.  Timing data are diagnostic; the 5% *native-path*
P07/P08 gate is separately recorded in bench-read-auto/bench-read.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import resource
import subprocess
import tempfile
import time

from bench_read_p02 import dff_bytes, summarize


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(sox: Path, inp: Path, out: Path, *, adapter: bool, cpu: int | None):
    args = (['taskset', '-c', str(cpu)] if cpu is not None else [])
    args += [str(sox),'--dsd-mode','auto','--dsd-layout-loss','warn','-D']
    if adapter:
        args += ['--combine=merge']
    args += [str(inp),'-r','88200','-t','raw','-e','signed-integer','-b','32',str(out)]
    if not adapter:
        args += ['dsdpcm']
    out.unlink(missing_ok=True)
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    start=time.perf_counter()
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    elapsed=time.perf_counter()-start
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'argv':args,'exit':p.returncode,'wall_seconds':elapsed,
            'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
            'stderr':p.stderr.decode(errors='replace')[-2000:],
            'output_bytes':out.stat().st_size if out.exists() else 0,
            'output_sha256':digest(out) if out.exists() else None}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--baseline-sox',type=Path,required=True)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=1048576)
    ap.add_argument('--pairs',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--cpu',type=int,default=None)
    ap.add_argument('--working-directory',type=Path,default=Path('/dev/shm'))
    a=ap.parse_args()
    if a.frames%8 or a.pairs<15 or a.warmups<1:
        ap.error('frames must be byte-aligned; require >=15 pairs, >=1 warmup')
    a.results.mkdir(parents=True,exist_ok=True)
    baseline=a.baseline_sox.resolve()
    candidate=a.sox.resolve()
    rng=random.Random(0x508)
    timings={'baseline':[],'candidate':[]}
    records=[]
    errors=[]
    expected=None
    with tempfile.TemporaryDirectory(prefix='sox-p08-adapter-',dir=a.working_directory) as d:
        t=Path(d)
        inp=t/'source-6ch.dff'
        inp.write_bytes(dff_bytes(6,a.frames))
        variants=['baseline','candidate']*a.warmups
        for _ in range(a.pairs):
            variants.extend(('candidate','baseline') if rng.randrange(2)
                            else ('baseline','candidate'))
        for i,arm in enumerate(variants):
            measured=i>=a.warmups*2
            out=t/'decoded.raw'
            record=invoke(candidate if arm=='candidate' else baseline,
                          inp,out,adapter=arm=='candidate',cpu=a.cpu)
            record.update(arm=arm,measured=measured,run_index=i)
            if record['exit'] or not record['output_sha256']:
                errors.append(f'{arm}: conversion failed (exit {record["exit"]})')
            elif expected is None:
                expected=(record['output_sha256'],record['output_bytes'])
            elif (record['output_sha256'],record['output_bytes'])!=expected:
                errors.append(f'{arm}: output hash or size differs from the reference')
            if measured and not errors:
                timings[arm].append(record['cpu_seconds'])
            records.append(record)
    paired=len(timings['baseline'])==len(timings['candidate'])==a.pairs
    score=summarize(timings['baseline'],timings['candidate'],seed=0x508) if paired else None
    data={'schema':'sox.dsd.P08.adapter_benchmark.v1',
          'purpose':'P07 explicit graph decoder versus P08 single-input merge adapter: byte-identical six-channel PCM',
          'comparison_kind':'same output; different insertion point',
          'gate':'informational, not the P07-to-P08 native transcode throughput gate',
          'baseline_sox':str(baseline),'candidate_sox':str(candidate),
          'workdir':str(a.working_directory),'cpu':a.cpu,
          'native_frames':a.frames,'native_channels':6,
          'pairs':a.pairs,'warmups':a.warmups,'input_format':'DFF/DSD64',
          'result':score,'output_reference':expected,'errors':errors,
          'measurements':records}
    (a.results/'adapter.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print('P08 adapter: pairs=%d, errors=%d, %s' % (
        a.pairs,len(errors),
        'ratio=%.4f, status=%s' %(score['median_ratio'],score['status']) if score else 'incomplete'))
    return 0 if not errors and paired else 1

if __name__=='__main__':
    raise SystemExit(main())
