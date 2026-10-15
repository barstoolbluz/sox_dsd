#!/usr/bin/env python3
"""Bounded real-production SRC holdouts for P15-R3; NOT composite qualification.

Reuses the independently written P15 physical SRC tone probe.  The resulting
sampled observations do not certify all coherent spectra or SRC arithmetic.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from p15_src_spectral import evaluate

CASES = ((88200,48000,22800),
         (176400,96000,45600),
         (176400,88200,41895),
         (176400,352800,66000))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=32768)
    args=ap.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    rows=[]
    for src,out,p in CASES:
        x=evaluate(args.probe,src,out,p,frames=args.frames)
        x['rate_case']=dict(intermediate_hz=src,pcm_hz=out,effective_pass_hz=p)
        rows.append(x)
        print('P15-R3 SRC sampled holdout',src,'=>',out,'status',x['status'],
              'passed',x['passed'],'checks',x['checks'],flush=True)
    good=all(c['passed'] for c in rows)
    report=dict(schema='sox-ng/p15-r3-src-sampled-holdouts/1',
        status='SAMPLED_PASS' if good else 'SAMPLED_FAIL',
        release_status='BLOCKED',
        scope='production P07 SRC only; four real ratios; static sampled spectral tones/images',
        limitations='does not certify full continuous composite FIR+SRC extrema, coherent aliases, or like-for-like binary64 arithmetic; first-release gates remain OPEN',
        cases=rows)
    (args.results/'src-sampled-holdouts.json').write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return 0 if good else 1

if __name__=='__main__':raise SystemExit(main())
