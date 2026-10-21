#!/usr/bin/env python3
"""P16 paired packed/expanded end-to-end benchmark, native256 + simulated512/1024.

The 512/1024 tests are *only* descriptor/transport bit oracles, not decoder
runs, SRC checks, or authorization to write high-rate media. Small developer
measurements quantify a mechanism; CPU speedups are host/workload dependent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
CLOCKS=(22579200,45158400)


def atomic(path, value):
    temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
    temp.replace(path)


def sha(data): return hashlib.sha256(data).hexdigest()


def run(command, packed, output_dir, key, timeout):
    stamp=output_dir/(key+'.time')
    env=os.environ.copy()
    env.update(SOX_OPTS='',OMP_NUM_THREADS='1',LC_ALL='C')
    if packed: env['SOX_DSD_PACKED_INPUT']='1'
    else:env.pop('SOX_DSD_PACKED_INPUT',None)
    wrapper=['/usr/bin/time','-f','%e %U %S %M','-o',str(stamp)] \
        if Path('/usr/bin/time').is_file() else []
    t=time.perf_counter()
    cp=subprocess.run(wrapper+[str(x) for x in command],cwd=ROOT,env=env,
        stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
    elapsed=time.perf_counter()-t
    time_fields=stamp.read_text().strip().split() if stamp.is_file() else []
    stats=dict(wall_seconds=float(time_fields[0]),cpu_user_seconds=float(time_fields[1]),
               cpu_system_seconds=float(time_fields[2]),peak_rss_kib=int(time_fields[3])) \
        if len(time_fields)==4 else None
    if stats is not None:
        stats['cpu_seconds']=stats['cpu_user_seconds']+stats['cpu_system_seconds']
    return dict(command=[str(x) for x in command],packed=packed,exit=cp.returncode,
        sha256=sha(cp.stdout),pcm_bytes=len(cp.stdout),
        raw_stderr=cp.stderr.decode(errors='replace')[-1000:],
        process_time=stats,outer_wall_seconds=elapsed)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,default=ROOT/'src/sox')
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p16')
    ap.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P16/bench/packed-input')
    ap.add_argument('--duration',type=float,default=.5)
    ap.add_argument('--repetitions',type=int,default=3)
    ap.add_argument('--timeout',type=int,default=180)
    args=ap.parse_args()
    if not 0.005<=args.duration<=5 or not 1<=args.repetitions<=20 or not 1<=args.timeout<=1200:
        ap.error('invalid duration/repetitions/timeout')
    args.sox=args.sox.resolve();args.unit=args.unit.resolve()
    for p in (args.sox,args.unit):
        if not p.is_file():ap.error(f'missing binary: {p}')
    args.results.mkdir(parents=True,exist_ok=True)
    outfile=args.results/'paired.json'
    report=dict(schema='P16/paired/1',configuration=dict(duration=args.duration,
        repetitions=args.repetitions,sox_sha256=sha(args.sox.read_bytes()),
        unit_sha256=sha(args.unit.read_bytes()),build_host=platform.platform(),
        hostname=platform.node(),machine=platform.machine(),
        cpu_model=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                        if line.startswith('model name')),None) if Path('/proc/cpuinfo').is_file() else None),
        observations=[],simulated=[],unrun_gates=[
            'Physical DSD512/DSD1024 decoder/SRC/writer not implemented or authorized',
            'Dedicated isolated physical CPU multi-host performance qualification not run'],
        methodology='two file formats at DSD256; matched expanded/packed output and time/RSS; rates 512/1024 only bit-address simulation')
    def update():
        rows=report['observations']+report['simulated']
        report['verdict']='PASS' if rows and all(r.get('status')=='PASS' for r in rows) else 'FAIL'
        atomic(outfile,report)
    with tempfile.TemporaryDirectory(prefix='sox-p16-bench-') as root:
        d=Path(root)
        for rate in (11289600,):
            frames=int(rate*args.duration)//8*8
            for ext in ('dsf','dff'):
                path=d/f'bench-{rate}.{ext}'
                fixture=[str(args.unit),'fixture',str(path),str(rate),'2',str(frames)]
                cp=subprocess.run(fixture,cwd=ROOT,capture_output=True,text=True,timeout=300)
                if cp.returncode:
                    report['observations'].append(dict(name=f'{rate}-{ext}',status='FAIL',
                        fixture=fixture,exit=cp.returncode,stderr=cp.stderr[-2000:]))
                    update();continue
                sample_bytes=frames*2*4
                native_bytes=((frames+7)//8)*2
                # File I/O already reads packed bytes in BOTH variants;
                # these figures are the bytes crossing the reader->DSP API,
                # not physical disk-traffic reductions.
                case=dict(name=f'{rate}-{ext}',status='PASS',rate_hz=rate,
                    channels=2,frames=frames,file_bytes=path.stat().st_size,
                    interstage_bytes_expanded=sample_bytes,interstage_bytes_packed=native_bytes,
                    interstage_payload_traffic_reduction_ratio=sample_bytes/native_bytes,
                    trials=[])
                for trial in range(args.repetitions):
                    command=[str(args.sox),'--dsd-mode','auto','--combine=merge',
                        '--dsd-layout-loss','warn','--dsd-decode',
                        'decode.mastering.v2.dsd256','-D',str(path),'-r','88200',
                        '-t','raw','-e','signed-integer','-b','32','-']
                    # Alternating order mitigates some source-cache bias; does
                    # not make an uncontrolled/shared host suitable for sign-off.
                    order=(True,False) if trial%2 else (False,True)
                    runs={}
                    for ispacked in order:
                        runname=('packed' if ispacked else 'expanded')+str(trial)
                        try: rr=run(command,ispacked,d,runname,args.timeout)
                        except (OSError,subprocess.TimeoutExpired) as e:
                            rr=dict(exit=None,error=str(e),packed=ispacked)
                        runs['packed' if ispacked else 'expanded']=rr
                    a=runs['expanded'];b=runs['packed']
                    correct=(a.get('exit')==0 and b.get('exit')==0 and
                             a.get('sha256')==b.get('sha256') and
                             a.get('pcm_bytes')==b.get('pcm_bytes') and
                             a.get('pcm_bytes',0)>0)
                    case['trials'].append(dict(order=['packed' if x else 'expanded' for x in order],
                        expanded=a,packed=b,status='PASS' if correct else 'FAIL'))
                    if not correct:case['status']='FAIL'
                    report['observations']=[r for r in report['observations'] if r['name']!=case['name']]+[case]
                    update()
                stats=[(t['expanded'].get('process_time'),t['packed'].get('process_time'))
                       for t in case['trials'] if t['status']=='PASS']
                if len(stats)==args.repetitions and all(x and y for x,y in stats):
                    e=statistics.median(x['cpu_seconds'] for x,y in stats)
                    p=statistics.median(y['cpu_seconds'] for x,y in stats)
                    case['median_cpu_expanded_seconds']=e
                    case['median_cpu_packed_seconds']=p
                    case['paired_median_cpu_ratio_expanded_over_packed']=(e/p if p else None)
                    case['median_maxrss_expanded_kib']=statistics.median(x['peak_rss_kib'] for x,y in stats)
                    case['median_maxrss_packed_kib']=statistics.median(y['peak_rss_kib'] for x,y in stats)
                update()
        for rate in CLOCKS:
            frames=int(rate*min(args.duration,.25))
            cmd=[str(args.unit),'simulate',str(rate),str(frames)]
            try:
                r=run(cmd,False,d,f'sim-{rate}',args.timeout)
                # Here stdout is a summary string, not audio. The checked C
                # simulation exits nonzero on any mismatched physical bit.
                result=dict(name=f'simulated-{rate}',status='PASS' if r['exit']==0 else 'FAIL',
                            logical_native_hz=rate,frames=frames,channels=2,
                            packed_payload_bytes=((frames+7)//8)*2,
                            expanded_equivalent_bytes=frames*2*4,
                            theoretical_interstage_ratio=(frames*2*4)/(((frames+7)//8)*2),
                            transport_validation=r,decoder_enabled=False,writer_enabled=False)
            except (OSError,subprocess.TimeoutExpired) as e:
                result=dict(name=f'simulated-{rate}',status='FAIL',error=str(e))
            report['simulated'].append(result);update()
    print(json.dumps(dict(verdict=report.get('verdict'),
        cases=[(r['name'],r['status']) for r in report['observations']+report['simulated']],
        result_path=str(outfile))))
    return int(report['verdict']!='PASS')


if __name__=='__main__':
    raise SystemExit(main())
