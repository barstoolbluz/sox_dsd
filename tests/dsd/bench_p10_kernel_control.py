#!/usr/bin/env python3
"""Paired P09/P10 timing of the UNCHANGED P09 scalar probe and stimulus.

Use the existing benchmark's noise/interval rule. This measures normal-kernel
regression separately from the new composite's mandatory guard cost.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import subprocess
from bench_read_p02 import summarize
from soak_p10 import atomic,sha
from p10_corpus import RATES
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/dsd_test_p09')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--cpu',type=int,default=0)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    path=args.results/'kernel-control.json'
    config=dict(baseline_sha256=sha(args.baseline),candidate_sha256=sha(args.candidate),
        cpu=args.cpu,pairs=15,warmups=2,samples=1000000,seed=20261009)
    report=dict(schema='P10/paired-original-normal-kernel/1',config=config,
        status='INCOMPLETE',rows=[],summaries={},qualified=False,
        comparability='same unmodified test_p09.c probe, LUT, exact-rate profile, sample count and monitor mode')
    if path.exists():
        prior=json.loads(path.read_text())
        if prior['config']!=config:raise RuntimeError('preserve prior evidence; benchmark configuration changed')
        report=prior
    rng=random.Random(config['seed'])
    for rate in RATES:
        for mode in ('none','monitor'):
            case=f'{rate}-{mode}'
            for pair in range(config['warmups']+config['pairs']):
                arms=['baseline','candidate'];rng.shuffle(arms)
                for arm in arms:
                    if any(r['case']==case and r['pair']==pair and r['arm']==arm for r in report['rows']):continue
                    exe=args.baseline if arm=='baseline' else args.candidate
                    cmd=['taskset','-c',str(args.cpu),str(exe.resolve()),'--state-bench',
                        f'encode.mastering.v1.dsd{rate//44100}',str(rate),str(config['samples']),mode]
                    p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
                    row=dict(case=case,pair=pair,arm=arm,warmup=pair<config['warmups'],
                        exit_code=p.returncode,command=cmd[:3]+['<P09-probe>' if arm=='baseline' else 'test/dsd_test_p09']+cmd[4:],stderr=p.stderr)
                    if p.returncode==0:row['measurement']=json.loads(p.stdout)
                    report['rows'].append(row);atomic(path,report)
                    if p.returncode:raise RuntimeError(p.stderr)
            rows=[r for r in report['rows'] if r['case']==case]
            if len({r['measurement']['ones'] for r in rows})!=1:
                raise RuntimeError('baseline/candidate stimulus decisions do not have matching population counts')
            times={arm:[r['measurement']['cpu_seconds'] for r in sorted(rows,key=lambda r:r['pair'])
                if r['arm']==arm and not r['warmup']] for arm in ('baseline','candidate')}
            report['summaries'][case]=summarize(times['baseline'],times['candidate'],0x502)
            print(case,report['summaries'][case]['regression_percent'],report['summaries'][case]['status'],flush=True)
            atomic(path,report)
    statuses={v['status'] for v in report['summaries'].values()}
    report['status']='FAIL' if 'fail-regression' in statuses else 'INCONCLUSIVE' if any(s.startswith('inconclusive') for s in statuses) else 'PASS'
    report['caveat']='Population counts check stimulus/monitor comparability; native-bit determinism and audio qualification have separate tests.'
    atomic(path,report)
    return 1 if report['status']=='FAIL' else 2 if report['status']=='INCONCLUSIVE' else 0


if __name__=='__main__':raise SystemExit(main())
