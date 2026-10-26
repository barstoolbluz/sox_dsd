#!/usr/bin/env python3
"""Complete stereo PCM-to-DSF conversions, randomized paired timing and hashes.

Includes process startup, conversion and output I/O. Every output must equal
the unchanged baseline scalar whole-file SHA-256 for its sample rate. Per-child
CPU time uses getrusage rather than /usr/bin/time's two-decimal text rounding.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import struct
import subprocess
import tempfile
import time
import wave

RATES=(2822400,5644800,11289600,22579200,45158400)
TIERS=['scalar','sse2','avx1','avx2','avx512','auto']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def interval(values):
    rng=random.Random(20261026)
    draws=sorted(statistics.median(rng.choices(values,k=len(values))) for _ in range(10000))
    return [draws[249],draws[9749]]


def summarize(report):
    summary={}
    for rate in report['config']['rates']:
        by_tier={}
        for tier in report['config']['tiers']:
            rows=[p for p in report['pairs'] if p['rate']==rate and p['tier']==tier]
            if not rows:
                continue
            row={'pairs':len(rows)}
            for metric in ('cpu_seconds','wall_seconds'):
                before=[p['baseline'][metric] for p in rows]
                after=[p['candidate'][metric] for p in rows]
                reductions=[100.*(1.-a/b) for a,b in zip(after,before)]
                row[metric]={'baseline_median':statistics.median(before),
                    'candidate_median':statistics.median(after),
                    'median_paired_reduction_percent':statistics.median(reductions),
                    'paired_bootstrap_95_percent':interval(reductions),
                    'faster_pairs':sum(a<b for a,b in zip(after,before))}
            by_tier[tier]=row
        scalar=by_tier.get('scalar')
        if scalar:
            for row in by_tier.values():
                for metric in ('cpu_seconds','wall_seconds'):
                    row[metric]['speedup_vs_baseline_scalar']=scalar[metric]['baseline_median']/row[metric]['candidate_median']
        summary[str(rate)]=by_tier
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=1)
    ap.add_argument('--seconds',type=float,default=.25)
    ap.add_argument('--pcm-rate',type=int,default=176400)
    ap.add_argument('--tiers',nargs='+',choices=TIERS,default=TIERS)
    ap.add_argument('--rates',type=int,nargs='+',choices=RATES,default=list(RATES))
    ap.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)))
    ap.add_argument('--seed',type=int,default=20261026)
    args=ap.parse_args()
    if not 1<=args.repetitions<=100 or not .01<=args.seconds<=30 or not 0<=args.warmups<=10:
        ap.error('invalid repetitions/duration/warmups')
    if args.pcm_rate not in (88200,176400,352800,705600) or len(args.tiers)!=len(set(args.tiers)):
        ap.error('invalid PCM rate or duplicate tiers')
    os.sched_setaffinity(0,{args.cpu})
    bins={'baseline':args.baseline.resolve(),'candidate':args.candidate.resolve()}
    report={'schema':'sdm-register/paired-e2e/1','host':platform.platform(),
        'binaries':{k:{'path':str(p),'sha256':sha(p)} for k,p in bins.items()},
        'config':{'rates':args.rates,'tiers':args.tiers,'repetitions':args.repetitions,
            'warmups':args.warmups,'pcm_rate':args.pcm_rate,'seconds':args.seconds,
            'channels':2,'cpu_affinity':[args.cpu],'buffer_bytes':8192,
            'threads':1,'random_seed':args.seed,'fir_tier':'auto',
            'timer':'getrusage RUSAGE_CHILDREN delta, and perf_counter wall time'},
        'cli_arguments':['--dsd-mode','auto','--dsd-layout-loss','warn','-D',
                         '--single-threaded','--buffer','8192','SOURCE.wav','-r','RATE','OUTPUT.dsf'],
        'scalar_oracle_sha256':{},'warmups':[],'pairs':[],'errors':[],
        'summary':{},'status':'RUNNING'}
    rng=random.Random(args.seed)
    atomic(args.output,report)
    try:
        with tempfile.TemporaryDirectory(prefix='sdm-paired-e2e-') as tmp:
            folder=Path(tmp)
            inp=folder/'source.wav'
            count=round(args.pcm_rate*args.seconds)
            with wave.open(str(inp),'wb') as w:
                w.setnchannels(2);w.setsampwidth(4);w.setframerate(args.pcm_rate)
                w.writeframes(b''.join(struct.pack('<ii',
                    round(.1*math.sin(2.*math.pi*997*i/args.pcm_rate)*(2**31-1)),
                    round(.08*math.sin(2.*math.pi*1371*i/args.pcm_rate+.3)*(2**31-1)))
                    for i in range(count)))
            report['fixture']={'sha256':sha(inp),'bytes':inp.stat().st_size,'frames':count}
            monitor_oracles={}
            def run(label,rate,tier,diagnostic=False):
                out=folder/'output.dsf'
                env=dict(os.environ,OMP_NUM_THREADS='1',SOX_OPTS='',
                         SOX_DSD_KERNEL_SDM=tier,SOX_DSD_KERNEL_FIR='auto')
                env.pop('LSX_DSD_SDM_KERNEL',None)
                env.pop('LSX_DSD_FIR_KERNEL',None)
                cmd=[str(bins[label]),'--dsd-mode','auto','--dsd-layout-loss','warn',
                     '-D','--single-threaded','--buffer','8192',str(inp),'-r',str(rate),str(out)]
                diagnostic_path=folder/'conversion-report.json'
                if diagnostic:
                    cmd[1:1]=['--dsd-report',str(diagnostic_path)]
                c0=resource.getrusage(resource.RUSAGE_CHILDREN);w0=time.perf_counter_ns()
                p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180)
                wall=(time.perf_counter_ns()-w0)*1e-9;c1=resource.getrusage(resource.RUSAGE_CHILDREN)
                if p.returncode:
                    raise RuntimeError(f'{label}/{rate}/{tier} exit={p.returncode}: {p.stderr[-2000:]}')
                cpu=(c1.ru_utime-c0.ru_utime)+(c1.ru_stime-c0.ru_stime)
                digest=sha(out)
                if str(rate) in report['scalar_oracle_sha256']:
                    if digest!=report['scalar_oracle_sha256'][str(rate)]:
                        raise RuntimeError(f'whole DSF mismatch: {label}/{rate}/{tier}')
                else:
                    assert label=='baseline' and tier=='scalar'
                    report['scalar_oracle_sha256'][str(rate)]=digest
                result={'binary':label,'rate':rate,'tier':tier,'cpu_seconds':cpu,
                    'cpu_user_seconds':c1.ru_utime-c0.ru_utime,
                    'cpu_system_seconds':c1.ru_stime-c0.ru_stime,'wall_seconds':wall,
                    'sha256':digest,'bytes':out.stat().st_size,'stderr':p.stderr,'exit':p.returncode}
                if diagnostic:
                    conversion=json.loads(diagnostic_path.read_text())
                    if conversion['status']!='complete' or conversion['output']['actual_rate_hz']!=rate:
                        raise RuntimeError(f'incomplete/wrong-rate production conversion: {label}/{rate}/{tier}')
                    encoders=conversion['processing']['encoder']
                    expected=f'encode.mastering.v{2 if rate>11289600 else 1}.dsd{rate//44100}'
                    if len(encoders)!=2 or any(e['profile_id']!=expected or e['failure_code'] for e in encoders):
                        raise RuntimeError(f'wrong/failed production profile: {label}/{rate}/{tier}')
                    if tier!='auto' and any(e['sdm_kernel_actual']!=tier for e in encoders):
                        raise RuntimeError(f'forced tier was not executed: {label}/{rate}/{tier}')
                    signature=[{k:v for k,v in e.items() if k!='sdm_kernel_actual'} for e in encoders]
                    if rate in monitor_oracles and signature!=monitor_oracles[rate]:
                        raise RuntimeError(f'pipeline monitor/report differs from scalar: {label}/{rate}/{tier}')
                    monitor_oracles[rate]=signature
                    result['production_encoders']=encoders
                    diagnostic_path.unlink()
                out.unlink()
                return result
            for rate in args.rates:
                report['warmups'].append(run('baseline',rate,'scalar',True))
            for _ in range(args.warmups):
                jobs=[(rate,tier,label) for rate in args.rates for tier in args.tiers for label in bins]
                rng.shuffle(jobs)
                for rate,tier,label in jobs:
                    report['warmups'].append(run(label,rate,tier,True))
            atomic(args.output,report)
            for rep in range(args.repetitions):
                jobs=[(rate,tier) for rate in args.rates for tier in args.tiers]
                rng.shuffle(jobs)
                for rate,tier in jobs:
                    order=list(bins);rng.shuffle(order)
                    pair={'round':rep,'rate':rate,'tier':tier,'order':order}
                    for label in order:
                        pair[label]=run(label,rate,tier)
                    report['pairs'].append(pair)
                    atomic(args.output,report)
                print(f'completed paired full-conversion round {rep+1}/{args.repetitions}',flush=True)
    except Exception as exc:
        report['errors'].append(str(exc))
    report['summary']=summarize(report)
    report['status']='FAIL' if report['errors'] else 'PASS'
    atomic(args.output,report)
    for rate,rows in report['summary'].items():
        print(rate,[(t,round(r['cpu_seconds']['candidate_median'],5),
                     round(r['cpu_seconds']['median_paired_reduction_percent'],2)) for t,r in rows.items()])
    print(report['status'],args.output)
    return bool(report['errors'])


if __name__=='__main__':
    raise SystemExit(main())
