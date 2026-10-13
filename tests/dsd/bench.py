#!/usr/bin/env python3
"""P00 legacy baseline bench: native repack and direct ultra-quality decode.

The default development profile uses short files and one timed repetition;
it is a *measurement*, not a reliable dispatch/throughput qualification.
`--profile full --repetitions 15` enables the full output-rate matrix and
repeated timings but still does not certify silicon outside this host.
Every result retains the actual command, durations, exit, compiler and host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import sys
import statistics
import subprocess
import tempfile
import time

from reference import fixtures

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_SHA = hashlib.sha256((ROOT/'src/sox_ng.c').read_bytes()).hexdigest()


def atomic_json(file: pathlib.Path, value):
    file.parent.mkdir(parents=True,exist_ok=True)
    temp=file.with_name(file.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    temp.replace(file)


def host_info():
    cpuinfo = pathlib.Path('/proc/cpuinfo')
    text = cpuinfo.read_text(errors='replace') if cpuinfo.exists() else ''
    def field(name):
        m = re.search(r'^'+re.escape(name)+r'\s*:\s*(.*)$',text,re.M)
        return m.group(1).strip() if m else None
    governors = pathlib.Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
    return dict(architecture=platform.machine(),os=platform.platform(),
                hostname=platform.node(),cpu_model=field('model name'),
                cpu_microcode=field('microcode'),
                cpu_flags=(field('flags') or '').split(),
                affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                governor=governors.read_text().strip() if governors.is_file() else None,
                compiler=(subprocess.run(['cc','--version'],capture_output=True,text=True).stdout.splitlines() or ['unknown'])[0],
                build_flags='CFLAGS=-O2 -g; static; libltdl disabled; configured optional codecs listed in build/configure.log',
                thread_count=1, omp_num_threads=1, io_included=True,
                kernel='legacy (no P00 ISA dispatch change)',
                measurement_limit='virtualized or shared host timings are nonportable; default short-profile startup dominates')


def parse_time(file):
    try:
        s=file.read_text().strip().split()
        if len(s)!=4: return None
        return dict(time_wall_seconds=float(s[0]),cpu_user_seconds=float(s[1]),
                    cpu_system_seconds=float(s[2]),max_rss_kib=int(s[3]))
    except (OSError,ValueError):
        return None


def run_command(command, timelog, timeout):
    t0=time.perf_counter()
    env=os.environ.copy(); env.update(OMP_NUM_THREADS='1',LC_ALL='C')
    wrapper=['/usr/bin/time','-f','%e %U %S %M','-o',str(timelog)] if pathlib.Path('/usr/bin/time').is_file() else []
    try:
        p=subprocess.run(wrapper+list(map(str,command)),cwd=ROOT,env=env,
                         capture_output=True,text=True,timeout=timeout)
        rc=p.returncode; so=p.stdout; se=p.stderr; error=None
    except subprocess.TimeoutExpired as exc:
        rc=None;so='';se='';error=f'timeout after {timeout} seconds: {exc}'
    wall=time.perf_counter()-t0
    return dict(command=list(map(str,command)),executed_command=wrapper+list(map(str,command)),
                cwd=str(ROOT),env_overrides={'OMP_NUM_THREADS':'1','LC_ALL':'C'},
                exit=rc,stdout=so,stderr=se,error=error,wall_seconds=wall,
                process_time=parse_time(timelog))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', default='P00', choices=[f'P{i:02}' for i in range(19)])
    ap.add_argument('--results', type=pathlib.Path,default=ROOT/'tests/dsd/results/P00/bench')
    ap.add_argument('--sox',type=pathlib.Path,default=ROOT/'src/sox_ng')
    ap.add_argument('--profile',choices=['development','full'],default='development')
    ap.add_argument('--duration',type=float,default=0.006,
                    help='source seconds (default 0.006; intentionally short P00 development run)')
    ap.add_argument('--repetitions',type=int,default=1)
    ap.add_argument('--warmups',type=int,default=0,help='untimed warm-ups before each case')
    ap.add_argument('--timeout',type=float,default=180)
    ap.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None)
    ap.add_argument('--resume',action='store_true',help='keep previously completed cases only if configuration hashes match')
    args=ap.parse_args()
    if not (0 < args.duration <= 3600) or not (1 <= args.repetitions <= 1000) or not (0 <= args.warmups <= 1000) or args.timeout <= 0:
        ap.error('duration/repetitions/timeout out of range')
    if not args.sox.is_file():ap.error('sox binary does not exist')
    args.sox = args.sox.resolve()
    args.results = args.results.resolve()
    args.results.mkdir(parents=True,exist_ok=True)
    digest = hashlib.sha256(args.sox.read_bytes()).hexdigest()
    matrix = (352800,705600) if args.profile == 'development' else (88200,176400,352800,705600)
    native_targets = ['native-dsf'] + (['native-dff'] if int(args.phase[1:]) >= 1 else [])
    context=host_info()
    host_hash=hashlib.sha256(json.dumps({k: context.get(k) for k in ('architecture','os','hostname','cpu_model','cpu_microcode','cpu_flags','affinity','governor')},sort_keys=True).encode()).hexdigest()
    config = dict(phase=args.phase, profile=args.profile, duration=args.duration,
                  repetitions=args.repetitions, warmups=args.warmups, timeout=args.timeout,
                  host_fingerprint_sha256=host_hash, sox_binary=str(args.sox),sox_sha256=digest,
                  source_code_sha256=SOURCE_SHA,source_fixture_seed=fixtures.SEED,
                  output_pcm_rates_hz=list(matrix),rates_hz=list(fixtures.RATES),channels=[1,2,6])
    config_key=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    outfile=args.results/'bench.json'
    report=dict(schema='dsd-benchmarks/1',config=config,config_sha256=config_key,
                context=context,commands=[],planned_cases=[],
                completed_cases=[],unrun_gates=[],
                distinction='host-specific P00 baseline; no speedup or numerical quality acceptance')
    for rate in fixtures.RATES:
        for ch in (1,2,6):
            for dest in (native_targets+[f'pcm-{r}' for r in matrix]):
                report['planned_cases'].append(f'{rate}Hz_{ch}ch_{dest}')
    if args.resume and outfile.exists():
        previous=json.loads(outfile.read_text())
        if previous['config_sha256'] != config_key:
            ap.error('resume configuration/source binary hash differs; refuse to merge benchmark samples')
        report=previous
    else:
        if outfile.exists():
            old=outfile.read_bytes()
            try:
                previous=json.loads(old)
                if previous.get('summary',{}).get('status')=='incomplete' or any(
                        x.get('exit') not in (0,) for x in previous.get('commands',[])):
                    archive=outfile.with_name('bench-incomplete-'+hashlib.sha256(old).hexdigest()[:16]+'.json')
                    if not archive.exists():archive.write_bytes(old)
            except (ValueError,KeyError):
                pass
        atomic_json(outfile,report)
    done={case['id']:case for case in report['completed_cases']}

    # Inputs and outputs are temporary. Commands refer to the actual files used.
    # Save fixture hashes/frames so results remain auditable once temp files go.
    with tempfile.TemporaryDirectory(prefix='dsd-bench-') as d:
        working=pathlib.Path(d)
        for rate in fixtures.RATES:
            for ch in (1,2,6):
                frames=max(8,int(args.duration*rate)//8*8)
                timeline=fixtures.bits(frames,ch,'distinct')
                source=working/f'in-{rate}-{ch}.dsf'
                source.write_bytes(fixtures.make_dsf(timeline,rate))
                audio_seconds=frames/rate
                for target in native_targets+[f'pcm-{r}' for r in matrix]:
                    ident=f'{rate}Hz_{ch}ch_{target}'
                    if args.resume and ident in done and len(done[ident]['runs'])==args.repetitions and all(r['exit']==0 for r in done[ident]['runs']):
                        continue
                    suffix = {'native-dsf': '.dsf', 'native-dff': '.dff'}.get(target, '.wav')
                    output=working/(ident+suffix)
                    if target in native_targets:
                        command=[args.sox,'-D',source,output]
                        output_rate=rate
                        workload='native dsd to dsd transcode'
                    else:
                        output_rate=int(target[4:])
                        command=[args.sox,'-D',source,'-r',str(output_rate),
                                 '-e','floating-point','-b','64',output,'rate','-v']
                        workload='direct legacy ultra-quality decode (not bandwidth matched)'
                    rec=done.get(ident) if args.resume else None
                    if rec is None:
                        rec=dict(id=ident,workload=workload,input_format='DSF',
                             input_rate_hz=rate,output_rate_hz=output_rate,
                             channels=ch,native_frames_per_channel=frames,
                             audio_seconds=audio_seconds,
                             source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             source_chronology_sha256=fixtures.chronology_sha256(timeline),
                             runs=[],warmup_runs=[])
                    rec.setdefault('warmup_runs',[])
                    for warm in range(len(rec['warmup_runs']),args.warmups):
                        timing_file=working/'elapsed.txt'
                        if timing_file.exists():timing_file.unlink()
                        sample=run_command(command,timing_file,args.timeout)
                        sample['warmup']=warm
                        rec['warmup_runs'].append(sample)
                        report['commands'].append(dict(case_id=ident,warmup=warm,
                             command=sample['command'],exit=sample['exit'],wall_seconds=sample['wall_seconds']))
                        # Warm-up evidence survives interruption, separately from timed runs.
                        if ident not in done:
                            report['completed_cases'].append(rec)
                            done[ident]=rec
                        atomic_json(outfile,report)
                        if sample['exit']!=0:break
                    if any(sample['exit']!=0 for sample in rec['warmup_runs']):
                        continue
                    for rep in range(len(rec['runs']),args.repetitions):
                        timing_file=working/'elapsed.txt'
                        if timing_file.exists():timing_file.unlink()
                        sample=run_command(command,timing_file,args.timeout)
                        sample['repetition']=rep
                        sample['input_bytes']=source.stat().st_size
                        sample['output_bytes']=output.stat().st_size if output.exists() else None
                        if sample['exit']==0:
                            sample['output_sha256']=hashlib.sha256(output.read_bytes()).hexdigest()
                            sample['rtf_wall_seconds_per_audio_second']=sample['wall_seconds']/audio_seconds
                            sample['realtime_speed_audio_seconds_per_wall_second']=audio_seconds/sample['wall_seconds']
                            sample['native_frames_per_second_per_channel']=frames/sample['wall_seconds']
                            sample['aggregate_native_bits_per_second']=frames*ch/sample['wall_seconds']
                            perf=sample['process_time']
                            sample['cpu_seconds']=(perf['cpu_user_seconds']+perf['cpu_system_seconds']) if perf else None
                        rec['runs'].append(sample)
                        report['commands'].append(dict(case_id=ident,repetition=rep,command=sample['command'],
                             exit=sample['exit'],wall_seconds=sample['wall_seconds']))
                        # Crash/interrupt proof: persist each repetition including failures.
                        replaced=False
                        for i,x in enumerate(report['completed_cases']):
                            if x['id']==ident:
                                report['completed_cases'][i]=rec
                                replaced=True
                                break
                        if not replaced:report['completed_cases'].append(rec)
                        atomic_json(outfile,report)
                        print(f'{"PASS" if sample["exit"]==0 else "FAIL"} {ident} repetition {rep+1}/{args.repetitions}, wall={sample["wall_seconds"]:.4f}s',flush=True)
                        if sample['exit']!=0:break
                    wall_values=[r['wall_seconds'] for r in rec['runs'] if r['exit']==0]
                    if wall_values:
                        rec['wall_median_seconds']=statistics.median(wall_values)
                        rec['wall_range_seconds']=[min(wall_values),max(wall_values)]
                    atomic_json(outfile,report)

    completed={x['id']:x for x in report['completed_cases']}
    missing=[name for name in report['planned_cases'] if name not in completed or
             len(completed[name]['runs'])!=args.repetitions or
             len(completed[name].get('warmup_runs',[]))!=args.warmups or any(r['exit']!=0 for r in completed[name]['runs'])]
    report['unrun_gates']=[]
    if args.profile=='development':
        report['unrun_gates'] += ["full 88.2/176.4 kHz decode rate matrix (use --profile full)",
                                  '15 repetitions/warmups and controlled-frequency benchmark qualification',
                                  'staged bandwidth-matched control (future DSP phases)',
                                  'physical AVX-only/Intel/AMD ISA hardware matrix (later phases)']
    if missing: report['unrun_gates'].append('failed or unfinished benchmark case ids: '+', '.join(missing))
    report['summary']=dict(successful_cases=len(report['planned_cases'])-len(missing),
                           planned_cases=len(report['planned_cases']),failed_or_incomplete=missing,
                           status='pass-development-only' if not missing else 'incomplete')
    if int(args.phase[1:]) >= 6:
        scalar_command = [sys.executable, str(ROOT/'tests/dsd/bench_decode.py'),
            '--unit', str(ROOT/'test/dsd_test_decode'), '--results',
            str(args.results/'scalar')]
        scalar = subprocess.run(scalar_command, cwd=ROOT, capture_output=True,
                                text=True,timeout=300)
        report['p06_scalar_benchmark'] = dict(exit=scalar.returncode,
            stdout=scalar.stdout,stderr=scalar.stderr,
            evidence='scalar/scalar-bench.json',
            status='pass-development-only' if scalar.returncode==0 else 'fail')
        if scalar.returncode:
            report['summary']['status']='incomplete'
            missing.append('P06 scalar benchmark failed')
    if args.phase=='P10':
        command=[sys.executable,str(ROOT/'tests/dsd/bench_p10.py'),
            '--results',str(args.results/'composite')]
        if args.cpu is not None:command+=['--cpu',str(args.cpu)]
        cp=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=3600)
        report['p10_composite_benchmark']=dict(exit=cp.returncode,stdout=cp.stdout,stderr=cp.stderr,
            evidence='composite/composite-bench.json',qualified=False)
        if cp.returncode:missing.append('P10 composite benchmark failed or incomplete')
        from bench_p10 import performance_summary
        perf=performance_summary(args.results.parent/'performance')
        report['p10_paired_throughput']=dict(status=perf['status'],evidence='../performance/summary.json')
        report['summary']['p10_throughput_qualification']=perf['status']
    if args.phase in ('P14','P15'):
        command=[sys.executable,str(ROOT/'tests/dsd/bench_p14.py'),
                 '--sox',str(args.sox), '--results',str(args.results/'observer-overhead')]
        try:
            cp=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=1000)
            report['p14_observer_overhead']=dict(exit=cp.returncode,status='PASS' if cp.returncode==0 else 'FAIL',
                stdout=cp.stdout,stderr=cp.stderr,evidence='observer-overhead/p14-overhead.json',
                qualification='development-only; P13 physical silicon remains OPEN')
            if cp.returncode:
                missing.append('P14 basic/full observational overhead or audio integrity failed')
                report['summary']['status']='incomplete'
        except (OSError,subprocess.TimeoutExpired) as error:
            report['p14_observer_overhead']=dict(status='FAIL',error=str(error))
            missing.append('P14 observational overhead unrun or timed out')
            report['summary']['status']='incomplete'
        atomic_json(outfile,report)
    if args.phase in ('P13','P15'):
        # P00's generic benchmark remains a regression measurement, not the
        # P13 ISA comparison. Run the required guarded AVX2/AVX-512F matrix
        # separately, retaining its own 15-repeat raw readings and exits.
        matrix_command=[sys.executable,str(ROOT/'tests/dsd/bench_p13_matrix.py'),
            '--results',str(args.results/'p13-avx512-vs-avx2'),
            '--repetitions','15','--full-matrix']
        try:
            matrix=subprocess.run(matrix_command,cwd=ROOT,capture_output=True,
                text=True,timeout=7200)
            report['p13_avx512_vs_avx2']=dict(exit=matrix.returncode,
                evidence='p13-avx512-vs-avx2/benchmark-matrix.json',
                stdout_tail=matrix.stdout[-3000:],stderr_tail=matrix.stderr[-1500:])
            if matrix.returncode:
                missing.append('P13 AVX2/AVX-512F comparison incomplete or failed')
        except (subprocess.TimeoutExpired,OSError) as exc:
            report['p13_avx512_vs_avx2']=dict(exit=None,error=str(exc),
                evidence='p13-avx512-vs-avx2/benchmark-matrix.json')
            missing.append('P13 AVX2/AVX-512F comparison unrun or timed out')
        if missing: report['summary']['status']='incomplete'
        atomic_json(outfile,report)
    atomic_json(outfile,report)
    print(json.dumps(dict(summary=report['summary'], path=str(outfile))))
    if missing:return 1
    if args.phase=='P10' and report['p10_paired_throughput']['status']!='PASS':return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
