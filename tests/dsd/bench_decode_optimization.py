#!/usr/bin/env python3
"""Paired production-CLI comparison using the inherited measurement primitives.

Every candidate is interleaved with the baseline, with retained commands,
wall/CPU observations, hashes and partial atomic receipts. No timing thresholds
are used as a correctness oracle. Requires an existing compiled source tree.
"""
from __future__ import annotations
import argparse, json, os, random, resource, statistics, sys, time, wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
from profile_decode import atomic_json, host, make_fixture, run_bounded, sha256

def summary(xs):
    m=statistics.median(xs)
    return dict(median=m,mad=statistics.median(abs(x-m) for x in xs),min=min(xs),max=max(xs))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--variants',nargs='+',required=True,help='name=executable')
    ap.add_argument('--tiers',nargs='+',default=['sse2'])
    ap.add_argument('--native-rate',type=int,choices=[2822400,5644800,11289600],default=2822400)
    ap.add_argument('--pcm-rate',type=int,default=88200)
    ap.add_argument('--channels',type=int,choices=[1,2,6],default=2)
    ap.add_argument('--seconds',type=float,default=2.)
    ap.add_argument('--profile',choices=['mastering','wideband'],default='mastering')
    ap.add_argument('--threads',type=int,choices=[1,2],default=1)
    ap.add_argument('--report',action='store_true')
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--cpu',type=int,default=1)
    ap.add_argument('--buffer',type=int,default=8192)
    args=ap.parse_args()
    variants={n:Path(p).resolve() for n,p in (v.split('=',1) for v in args.variants)}
    if 'baseline' not in variants or len(variants)!=len(args.variants):ap.error('unique variants including baseline required')
    variants={'baseline':variants['baseline'],**{n:p for n,p in variants.items() if n!='baseline'}}
    if args.repetitions<15 or args.warmups<1 or not 0.02<=args.seconds<=60:ap.error('>=15 repetitions, >=1 warmup; 0.02..60 seconds required')
    if any(not p.is_file() for p in variants.values()):ap.error('missing executable')
    if args.results.exists():ap.error('refusing existing evidence directory')
    if args.cpu not in os.sched_getaffinity(0):ap.error('CPU not available')
    os.sched_setaffinity(0,{args.cpu} if args.threads==1 else {args.cpu,args.cpu+1})
    dest=args.results.resolve();dest.mkdir(parents=True)
    fixture=dest/'fixture.dsf';frames=round(args.seconds*args.native_rate)
    make_fixture(fixture,args.native_rate,args.channels,frames)
    report=dict(schema='DSD/decode-optimization-paired/1',status='RUNNING',host=host(),
        config={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(args).items()},
        qualification='Exploratory measurements; physical-hardware qualification is not asserted',
        executable_sha256={n:sha256(p) for n,p in variants.items()},
        fixture=dict(sha256=sha256(fixture),native_frames=frames,audio_seconds=frames/args.native_rate,
            kind='seeded native bits, performance stimulus, not music qualification'),
        seed=0xD5D2027,preflight={},raw=[],summary={},comparisons={},errors=[])
    output=dest/'paired.json'
    def save():atomic_json(output,report)
    save()
    rng=random.Random(report['seed'])
    def convert(name,tier,label,diagnostic=False):
        directory=dest/label;directory.mkdir(parents=True)
        target=directory/'out.wav';rss=directory/'rss.txt'
        env=dict(os.environ,SOX_OPTS='',OMP_NUM_THREADS=str(args.threads),LC_ALL='C',
            SOX_DSD_KERNEL_FIR=tier,SOX_DSD_KERNEL_SDM='not-used',
            LSX_DSD_FIR_KERNEL='not-used',LSX_DSD_SDM_KERNEL='not-used')
        env.pop('GMON_OUT_PREFIX',None)
        cmd=[str(variants[name]),'--dsd-mode','auto','--dsd-decode',args.profile,'-D','--buffer',str(args.buffer)]
        cmd+=['--single-threaded' if args.threads==1 else '--multi-threaded']
        if args.report or diagnostic:cmd+=['--dsd-report',str(directory/'conversion.json')]
        cmd += [str(fixture),'-r',str(args.pcm_rate),'-e','signed-integer','-b','32',str(target)]
        wrapper=['/usr/bin/time','-f','%M','-o',str(rss)]
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter_ns()
        with (directory/'stdout.txt').open('w') as out,(directory/'stderr.txt').open('w') as err:
            rc,timed_out=run_bounded(wrapper+cmd,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=180.)
        wall=(time.perf_counter_ns()-start)*1e-9;after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row=dict(variant=name,tier=tier,label=label,command=wrapper+cmd,exit=rc,timed_out=timed_out,
            wall_seconds=wall,cpu_seconds=(after.ru_utime-before.ru_utime)+(after.ru_stime-before.ru_stime))
        atomic_json(directory/'invocation.json',row)
        if rc or timed_out:raise RuntimeError(f'{name}/{tier}: exit {rc}, timeout {timed_out}; {directory}')
        row.update(output_sha256=sha256(target),output_bytes=target.stat().st_size,max_rss_kib=int(rss.read_text()))
        if diagnostic:
            facts=json.loads((directory/'conversion.json').read_text())
            assert facts['status']=='complete'
            decoders=facts['processing']['decoder']
            assert decoders and all(d['fir_kernel_actual']==tier for d in decoders)
            with wave.open(str(target),'rb') as wav:
                assert wav.getnchannels()==args.channels and wav.getsampwidth()==4
                audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i4').astype(np.int64)
            row['frames']=len(audio)//args.channels
            assert row['frames']==(frames*args.pcm_rate+args.native_rate//2)//args.native_rate
        else:audio=None
        target.unlink()
        return row,audio
    try:
        for tier in args.tiers:
            reference=None
            for name in variants:
                row,audio=convert(name,tier,f'preflight/{tier}/{name}',True)
                if name=='baseline':reference=audio
                elif reference is not None:
                    assert audio.shape==reference.shape
                    row['max_baseline_int32_lsb']=int(np.max(np.abs(audio-reference))) if len(audio) else 0
                    if name!='fir-sse2-reduced':assert row['max_baseline_int32_lsb']==0
                    else:assert row['max_baseline_int32_lsb']<=1
                report['preflight'][f'{name}/{tier}']=row;save()
        for warmup,count in ((True,args.warmups),(False,args.repetitions)):
            for repeat in range(count):
                order=[(name,tier) for tier in args.tiers for name in variants];rng.shuffle(order)
                for name,tier in order:
                    row,_=convert(name,tier,f'{"warmup" if warmup else "timing"}/{repeat:03d}-{tier}-{name}')
                    assert row['output_sha256']==report['preflight'][f'{name}/{tier}']['output_sha256']
                    row.update(repeat=repeat,warmup=warmup)
                    report['raw'].append(row);save()
        for tier in args.tiers:
            base={r['repeat']:r for r in report['raw'] if r['tier']==tier and r['variant']=='baseline' and not r['warmup']}
            for name in variants:
                rows=[r for r in report['raw'] if r['tier']==tier and r['variant']==name and not r['warmup']]
                report['summary'][f'{name}/{tier}']={k:summary([r[k] for r in rows]) for k in ['wall_seconds','cpu_seconds','max_rss_kib']}
                report['summary'][f'{name}/{tier}']['real_time_factor']=statistics.median(r['wall_seconds'] for r in rows)/(frames/args.native_rate)
                ratios=[r['cpu_seconds']/base[r['repeat']]['cpu_seconds'] for r in rows]
                boot=sorted(statistics.median(rng.choices(ratios,k=len(ratios))) for _ in range(2000))
                report['comparisons'][f'{name}/{tier}']=dict(paired_cpu_ratio=summary(ratios),median_ratio_ci95=[boot[50],boot[1949]],
                    median_wall_ratio=report['summary'][f'{name}/{tier}']['wall_seconds']['median']/report['summary'][f'baseline/{tier}']['wall_seconds']['median'])
        report['status']='PASS'
    except (Exception,KeyboardInterrupt) as e:
        report['errors'].append(f'{type(e).__name__}: {e}');report['status']='INCOMPLETE'
    save();print(report['status'],output,flush=True)
    for k,v in report['comparisons'].items():print(k,round(v['paired_cpu_ratio']['median'],4),v['median_ratio_ci95'],flush=True)
    return int(report['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
