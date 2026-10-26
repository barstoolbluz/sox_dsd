#!/usr/bin/env python3
"""Randomized paired baseline/candidate normal-SDM timing at 512 frames.

No outlier removal. A pair consists of adjacent baseline/candidate invocations,
with randomized AB/BA order; profile/tier pair order is randomized each round.
CPU-time ratios, median paired reduction, bootstrap intervals and all raw rows
are retained. Results are host-specific, not a portable ISA preference claim.
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

RATES = (2822400, 5644800, 11289600, 22579200, 45158400)
PRODUCTION = [(f'encode.mastering.v{2 if i>2 else 1}.dsd{64<<i}', r)
              for i,r in enumerate(RATES)]
ALL_PROFILES = ([(f'encode.legacy.v1.dsd{64<<i}',r) for i,r in enumerate(RATES[:3])]
                + [(f'encode.mastering.v1.dsd{64<<i}',r) for i,r in enumerate(RATES)]
                + [(f'encode.mastering.v2.dsd{64<<i}',r) for i,r in enumerate(RATES) if i>2]
                + [(f'encode.diagnostic.{kind}.v1.dsd{64<<i}',r)
                   for kind in ('sdm6','clans8') for i,r in enumerate(RATES[:3])])
TIERS = ['scalar','sse2','avx1','avx2','avx512','auto']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def interval(values,seed=20261026):
    rng=random.Random(seed)
    draws=sorted(statistics.median(rng.choices(values,k=len(values))) for _ in range(10000))
    return [draws[249],draws[9749]]


def summarize(report):
    summary={}
    for profile,rate in report['config']['profiles']:
        by_tier={}
        for tier in report['config']['tiers']:
            rows=[p for p in report['pairs'] if p['profile']==profile and p['tier']==tier]
            if not rows:
                continue
            before=[p['baseline']['cpu_ns_per_frame'] for p in rows]
            after=[p['candidate']['cpu_ns_per_frame'] for p in rows]
            reductions=[100.*(1.-a/b) for a,b in zip(after,before)]
            by_tier[tier]={'pairs':len(rows),
                'baseline_median_cpu_ns_per_frame':statistics.median(before),
                'candidate_median_cpu_ns_per_frame':statistics.median(after),
                'median_paired_cpu_reduction_percent':statistics.median(reductions),
                'paired_bootstrap_95_percent':interval(reductions),
                'faster_pairs':sum(a<b for a,b in zip(after,before))}
        scalar=by_tier.get('scalar')
        if scalar:
            for row in by_tier.values():
                row['speedup_vs_baseline_scalar']=scalar['baseline_median_cpu_ns_per_frame']/row['candidate_median_cpu_ns_per_frame']
        summary[profile]=by_tier
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=5000000)
    ap.add_argument('--block',type=int,default=512)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=1)
    ap.add_argument('--tiers',nargs='+',choices=TIERS,default=TIERS)
    ap.add_argument('--profiles',choices=['production','all'],default='production')
    ap.add_argument('--profile-ids',nargs='+',
                    help='Restrict the selected profile set to these exact registered IDs')
    ap.add_argument('--rates',type=int,nargs='+',choices=RATES,default=list(RATES))
    ap.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)))
    ap.add_argument('--seed',type=int,default=20261026)
    args=ap.parse_args()
    if not 16384<=args.frames<=200000000 or not 1<=args.block<=16384 or not 1<=args.repetitions<=100:
        ap.error('frames, block or repetitions outside supported range')
    if len(args.tiers)!=len(set(args.tiers)):
        ap.error('duplicate tiers')
    os.sched_setaffinity(0,{args.cpu})
    bins={'baseline':args.baseline.resolve(),'candidate':args.candidate.resolve()}
    profiles=[p for p in (PRODUCTION if args.profiles=='production' else ALL_PROFILES) if p[1] in args.rates]
    if args.profile_ids:
        requested=set(args.profile_ids)
        if len(requested)!=len(args.profile_ids) or not requested <= {p[0] for p in profiles}:
            ap.error('duplicate or unavailable profile ID in the selected profile/rate set')
        profiles=[p for p in profiles if p[0] in requested]
    report={'schema':'sdm-register/paired-kernel/1','host':platform.platform(),
        'cpuinfo':Path('/proc/cpuinfo').read_text(),
        'binaries':{k:{'path':str(p),'sha256':sha(p)} for k,p in bins.items()},
        'config':{'frames':args.frames,'block':args.block,'repetitions':args.repetitions,
                  'warmups':args.warmups,'tiers':args.tiers,'profiles':profiles,
                  'cpu_affinity':[args.cpu],'random_seed':args.seed,
                  'guards_and_monitor':True},'warmups':[],'pairs':[],
        'summary':{},'errors':[],'status':'RUNNING'}
    rng=random.Random(args.seed)
    references={}
    def run(label,profile,rate,tier):
        cmd=[str(bins[label]),tier,profile,str(rate),str(args.frames),str(args.block)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if p.returncode:
            raise RuntimeError(f'{label}/{profile}/{tier} exit={p.returncode}: {p.stderr[-2000:]}')
        row=json.loads(p.stdout)
        assert row['requested_tier']==tier and row['profile']==profile and row['rate']==rate
        assert row['frames']==args.frames and row['block']==args.block
        assert row['guards_active'] and row['monitor_active'] and row['cpu_seconds']>0
        digest=(row['sample_checksum'],row['state_monitor_hash'])
        if profile in references and references[profile]!=digest:
            raise RuntimeError(f'{label}/{profile}/{tier}: final state/monitor or sample checksum differs')
        references[profile]=digest
        return row
    atomic(args.output,report)
    try:
        # Establish the unchanged baseline scalar checksum before timing SIMD.
        for profile,rate in profiles:
            report['warmups'].append({'binary':'baseline',**run('baseline',profile,rate,'scalar')})
        for _ in range(args.warmups):
            jobs=[(p,r,t,l) for p,r in profiles for t in args.tiers for l in bins]
            rng.shuffle(jobs)
            for profile,rate,tier,label in jobs:
                report['warmups'].append({'binary':label,**run(label,profile,rate,tier)})
        atomic(args.output,report)
        for rep in range(args.repetitions):
            jobs=[(p,r,t) for p,r in profiles for t in args.tiers]
            rng.shuffle(jobs)
            for profile,rate,tier in jobs:
                order=list(bins);rng.shuffle(order)
                pair={'round':rep,'profile':profile,'rate':rate,'tier':tier,'order':order}
                for label in order:
                    pair[label]=run(label,profile,rate,tier)
                report['pairs'].append(pair)
                atomic(args.output,report)
            print(f'completed paired kernel round {rep+1}/{args.repetitions}',flush=True)
    except Exception as exc:
        report['errors'].append(str(exc))
    report['summary']=summarize(report)
    report['status']='FAIL' if report['errors'] else 'PASS'
    atomic(args.output,report)
    for profile,rows in report['summary'].items():
        print(profile,[(tier,round(r['candidate_median_cpu_ns_per_frame'],2),
                        round(r['median_paired_cpu_reduction_percent'],2)) for tier,r in rows.items()])
    print(report['status'],args.output)
    return bool(report['errors'])


if __name__=='__main__':
    raise SystemExit(main())
