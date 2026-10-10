#!/usr/bin/env python3
"""P10 scalar/monitor/guard and 1/2/6-channel full-composite measurements.

Short-stream timings are diagnostic. The unchanged-path 5% gate is a separate
P09/P10 paired test, admitted only below 2% noise and decided by its interval.
No coefficient, interpolation, or required guard changes for a speed headline.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import tempfile
import time
from p10_corpus import RATES
from test_p10 import wav
from bench import host_info
from soak_p10 import atomic, sha
ROOT=Path(__file__).resolve().parents[2]


def performance_summary(directory):
    cases={}; missing=[]; errors=[]
    for mode in ('legacy','auto'):
        path=directory/f'paired-{mode}'/'bench-read.json'
        if not path.exists():missing.append(mode);continue
        report=json.loads(path.read_text())
        errors.extend(report.get('errors',[]))
        expected={f'{fmt}-{ch}ch-{op}-{size}' for fmt in ('dsf','dff')
            for ch in (2,6) for op in (('null','repack') if mode=='legacy' else ('repack',))
            for size in ('small','large')}
        if set(report.get('summaries',{}))!=expected or report.get('pairs',0)<15 or report.get('warmups',0)<1:
            errors.append(mode+': incomplete comparative matrix or repetition count')
        cases[mode]=dict(evidence=f'paired-{mode}/bench-read.json',sha256=sha(path),
            baseline_sha256=report['baseline_sha256'],candidate_sha256=report['candidate_sha256'],
            status=report['status'],pinned_cpu=report['pinned_cpu'],pairs=report['pairs'],
            workloads=report['summaries'])
    kernel_path=directory/'kernel/kernel-control.json'
    kernel=json.loads(kernel_path.read_text()) if kernel_path.exists() else {'status':'UNRUN'}
    if kernel['status']=='UNRUN':missing.append('P09/P10 normal-kernel control')
    elif kernel['status']=='FAIL':errors.append('normal-kernel control failed')
    workload_values=[v for c in cases.values() for v in c['workloads'].values()]
    noisy=kernel['status']=='INCONCLUSIVE' or any(v.get('status','').startswith('inconclusive') for v in workload_values)
    failed=bool(errors) or any(v.get('status')=='fail-regression' for v in workload_values)
    status='FAIL' if failed else 'UNRUN' if missing else 'INCONCLUSIVE' if noisy else 'PASS'
    # A prepared-host probe is an additional prerequisite, never overridden by
    # individually convenient workload point estimates.
    probe=directory/'host-noise.txt'
    if status=='PASS' and (not probe.exists() or 'too noisy' in probe.read_text()):
        status='INCONCLUSIVE'
    result=dict(schema='P10/paired-throughput/1',status=status,qualified=False,
        gate='maximum 5% slowdown; noise below 2%; 95% paired interval wholly <= 1.05',
        cases=cases,missing=missing,errors=errors,
        normal_kernel_control=dict(status=kernel['status'],evidence='kernel/kernel-control.json',
            sha256=sha(kernel_path) if kernel_path.exists() else None),
        dff_6ch_repack_small={mode:c['workloads'].get('dff-6ch-repack-small') for mode,c in cases.items()},
        attribution='No read implementation changed in P10. No timing movement is attributed from these noisy observations.',
        host_probe='host-noise.txt',host_status='host-status.txt')
    atomic(directory/'summary.json',result)
    return result


def execute(command, timing):
    start=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    wrapped=['/usr/bin/time','-f','%M','-o',str(timing)]+list(map(str,command))
    proc=subprocess.run(wrapped,cwd=ROOT,capture_output=True,text=True,timeout=180,
        env={**os.environ,'OMP_NUM_THREADS':'2','LC_ALL':'C'})
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(exit_code=proc.returncode,wall_seconds=time.perf_counter()-start,
        cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        max_rss_kib=int(timing.read_text().strip().splitlines()[-1]),
        stdout=proc.stdout,stderr=proc.stderr)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=.125)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--cpu',type=int,default=None)
    ap.add_argument('--summarize-performance',type=Path)
    args=ap.parse_args()
    if args.summarize_performance:
        report=performance_summary(args.summarize_performance)
        print(json.dumps(dict(status=report['status'])))
        return 1 if report['status']=='FAIL' else 0 if report['status']=='PASS' else 2
    if not 0<args.seconds<=60 or args.repetitions<15 or args.warmups<1:
        ap.error('positive duration <=60, at least 15 repetitions and one warmup required')
    args.results.mkdir(parents=True,exist_ok=True)
    context=host_info();context.pop('hostname',None)
    context['kernel']='scalar sdm-8; binary64 SRC and working-rate scalar FIR'
    context['omp_num_threads']=2
    config=dict(seconds=args.seconds,repetitions=args.repetitions,warmups=args.warmups,
        unit_sha256=sha(args.unit),candidate_sha256=sha(args.candidate),cpu=args.cpu)
    path=args.results/'composite-bench.json'
    report=dict(schema='P10/composite-benchmark/1',config=config,context=context,
        kernel_runs=[],whole_composite=[],qualified=False,
        timing_scope='short-stream diagnostic including process startup and tmpfs I/O; not long-stream physical-host qualification')
    if path.exists():
        old=json.loads(path.read_text())
        if old['config']!=config:raise RuntimeError('benchmark configuration differs; use a new results directory')
        report=old
    prefix=['taskset','-c',str(args.cpu)] if args.cpu is not None else []
    for native in RATES:
        for mode in ('none','monitor','guard'):
            for rep in range(args.warmups+args.repetitions):
                if any(r['native_hz']==native and r['mode']==mode and r['iteration']==rep for r in report['kernel_runs']):continue
                command=prefix+[str(args.unit.resolve()),'--state-bench',str(native),'1000000',mode]
                proc=subprocess.run(command,capture_output=True,text=True,timeout=60)
                if proc.returncode:raise RuntimeError(proc.stderr)
                row=json.loads(proc.stdout);row.update(iteration=rep,warmup=rep<args.warmups,
                    command=['test/dsd_test_p10','--state-bench',str(native),'1000000',mode],exit_code=0)
                report['kernel_runs'].append(row);atomic(path,report)
        hashes={r['bits_fnv64'] for r in report['kernel_runs'] if r['native_hz']==native}
        if len(hashes)!=1:raise RuntimeError('monitor/guard changed native decisions')
    with tempfile.TemporaryDirectory(prefix='p10-composite-bench-',dir='/dev/shm') as work:
        tmp=Path(work);timing=tmp/'timing.txt'
        for native in RATES:
            source_rate=88200 if native==RATES[0] else 176400
            for channels in (1,2,6):
                source=tmp/'source.wav';wav(source,source_rate,channels,
                    frames=round(args.seconds*source_rate),peak=.3)
                for threads in ('--single-threaded','--multi-threaded'):
                    key=f'{native}-{channels}-{threads}'
                    row=next((r for r in report['whole_composite'] if r['id']==key),None)
                    if row is None:
                        row=dict(id=key,native_hz=native,source_hz=source_rate,channels=channels,
                            threads=threads,source_sha256=sha(source),runs=[],profile=f'encode.mastering.v1.dsd{native//44100}')
                        report['whole_composite'].append(row)
                    # Multiple worker threads need more than one admitted CPU.
                    available=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else []
                    affinity=[args.cpu] if args.cpu is not None else available
                    if threads=='--multi-threaded' and args.cpu is not None:
                        affinity=[args.cpu]+[v for v in available if v!=args.cpu][:1]
                    whole_prefix=['taskset','-c',','.join(map(str,affinity))] if args.cpu is not None else []
                    row['affinity']=affinity
                    for rep in range(len(row['runs']),args.warmups+args.repetitions):
                        destination=tmp/'out.dsf'
                        command=whole_prefix+[str(args.candidate.resolve()),'--dsd-mode','auto','-D',threads]
                        if channels==6:command+=['--dsd-layout','FL,FR,FC,LFE,BL,BR']
                        command+=[str(source),'-r',str(native),str(destination)]
                        measured=execute(command,timing)
                        measured['stderr']=measured['stderr'].replace(str(tmp),'<fixture>')
                        measured.update(iteration=rep,warmup=rep<args.warmups,
                            command=[x.replace(str(args.candidate.resolve()),'test/sox_p10_candidate').replace(str(tmp),'<fixture>') for x in command])
                        if measured['exit_code']==0:
                            measured['output_sha256']=sha(destination)
                            measured['realtime_factor']=measured['wall_seconds']/args.seconds
                            measured['audio_seconds_per_wall_second']=args.seconds/measured['wall_seconds']
                            measured['native_frames_per_second_per_channel']=native*args.seconds/measured['wall_seconds']
                            measured['aggregate_native_bits_per_second']=channels*native*args.seconds/measured['wall_seconds']
                        row['runs'].append(measured);atomic(path,report)
                        if measured['exit_code']:raise RuntimeError(measured['stderr'])
                    row['median_cpu_seconds']=statistics.median(r['cpu_seconds'] for r in row['runs'] if not r['warmup'])
                    row['median_realtime_factor']=statistics.median(r['realtime_factor'] for r in row['runs'] if not r['warmup'])
                    print(key,'RTF',row['median_realtime_factor'],flush=True)
            atomic(path,report)
    report['kernel_summary']=[]
    for native in RATES:
        times={m:statistics.median(r['cpu_seconds'] for r in report['kernel_runs']
            if r['native_hz']==native and r['mode']==m and not r['warmup']) for m in ('none','monitor','guard')}
        report['kernel_summary'].append(dict(native_hz=native,median_cpu_seconds=times,
            monitor_overhead_ratio=times['monitor']/times['none'],
            guard_and_monitor_overhead_ratio=times['guard']/times['none']))
    report['status']='PASS-DIAGNOSTIC-ONLY'
    atomic(path,report)
    print(json.dumps(dict(status=report['status'],kernel_runs=len(report['kernel_runs']),whole_cases=len(report['whole_composite']))))
    return 0


if __name__=='__main__':raise SystemExit(main())
