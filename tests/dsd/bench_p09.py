#!/usr/bin/env python3
"""P09 diagnostic footprint, monitor delta, legacy normal/trellis preservation.

Never represents the shared-host timings as a qualified 5% speed gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import struct
import subprocess
import tempfile
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def command_run(argv):
    start=time.perf_counter()
    p=subprocess.run([str(x) for x in argv],cwd=ROOT,capture_output=True,text=True,timeout=120)
    return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr,
                wall_seconds=time.perf_counter()-start)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--unit',type=Path,required=True)
    ap.add_argument('--baseline-sox',type=Path,required=True)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    rates=(2822400,5644800,11289600)
    measured=[]
    for rate in rates:
        for mode in ('none','monitor'):
            for warm in range(2+7):
                profile=f'encode.mastering.v1.dsd{rate//44100}'
                proc=command_run([args.unit,'--state-bench',profile,rate,1000000,mode])
                if proc['exit']:raise RuntimeError(proc['stderr'])
                row=json.loads(proc['stdout']);row['warmup']=warm<2
                measured.append(row)
    for rate in rates:
        # The optional monitor must not influence the modulator's decisions.
        assert len({r['ones'] for r in measured if r['rate']==rate}) == 1
        by={mode:[r['cpu_seconds'] for r in measured if r['rate']==rate and r['monitor']==(mode=='monitor') and not r['warmup']]
            for mode in ('none','monitor')}
        print(f'scalar rate={rate} monitor-off={statistics.median(by["none"]):.4f}s '
              f'on={statistics.median(by["monitor"]):.4f}s overhead={statistics.median(by["monitor"])/statistics.median(by["none"]):.2f}x')
    legacy=[]
    # Equivalent 1-bit SDM effect explicit normal and trellis controls on both
    # binaries. Byte identity is required; CPU timings are diagnostic here.
    with tempfile.TemporaryDirectory(dir='/dev/shm' if Path('/dev/shm').exists() else None) as temp:
        directory=Path(temp)
        n=1310720
        i=np.arange(n,dtype=np.float64)
        x=(np.sin(2*np.pi*997*i/2822400)*.7*(2**31-1)).astype('<i4')
        source=directory/'source.raw';source.write_bytes(x.tobytes())
        for trellis in (False,True):
            controls=['sdm','-f','clans-4']+(['-t','3','-n','4','-l','100'] if trellis else [])
            times={'baseline':[],'candidate':[]}
            hashes=[]
            rng=random.Random(9909 + int(trellis))
            for rep in range(2+7):
                arms=['baseline','candidate'];rng.shuffle(arms)
                items={}
                for arm in arms:
                    binary=args.baseline_sox if arm=='baseline' else args.sox
                    out=directory/f'{arm}.raw'
                    cmd=[binary,'-D','-t','raw','-r','2822400','-c','1','-b','32',
                         '-e','signed-integer','-L',source,'-t','raw','-r','2822400',
                         '-c','1','-b','32','-e','signed-integer','-L',out]+controls
                    run=command_run(cmd)
                    if run['exit']:raise RuntimeError(f'{arm} {trellis} exit {run["exit"]}: {run["stderr"]}')
                    digest=hashlib.sha256(out.read_bytes()).hexdigest()
                    items[arm]=digest
                    if rep>=2:times[arm].append(run['wall_seconds'])
                if items['baseline']!=items['candidate']:
                    raise RuntimeError(f'legacy trellis={trellis} bytes changed!')
                hashes.append(items['candidate'])
            legacy.append(dict(trellis=trellis,profile='clans-4',native_rate_hz=2822400,
                               input_frames=n,baseline_output_identical=True,
                               all_run_sha256=hashes,
                               baseline_median_wall_seconds=statistics.median(times['baseline']),
                               candidate_median_wall_seconds=statistics.median(times['candidate']),
                               timing_verdict='diagnostic-only; host noise > 2%'))
    output=dict(schema='P09/footprint-and-legacy-controls/1',
                host_noise_admissibility='failed: see ../host-noise.txt',
                state_runs=measured,legacy_controls=legacy,
                note='normal monitoring is opt-in; neither P09 scalar API nor diagnostics changes legacy effect dispatch')
    (args.results/'low-level-bench.json').write_text(json.dumps(output,sort_keys=True,indent=2)+'\n')
    for result in legacy:
        print('legacy',result['trellis'],'byte-identical',result['baseline_output_identical'],
              'median ratios',result['candidate_median_wall_seconds']/result['baseline_median_wall_seconds'])

if __name__=='__main__':main()
