#!/usr/bin/env python3
"""P17 bounded, paired high-rate internal DSP benchmark (NOT a certificate).

No native high-rate files or writers are created. A private test binary exercises
real reconstruction and candidate composite PCM->SDM DSP. Every pair is checked
for bit-identical PCM before a speed ratio is reported. Long runs (up to 130
source-audio seconds) are accepted, but the default is a cheap development
probe. Timings on shared/virtual hosts are NOT high-rate performance signoff.
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
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
RATES=(22579200,45158400)


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def atomic_json(path:Path,record:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(record,f,sort_keys=True,indent=2,allow_nan=False)
        f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def invoke(command:list[str],env:dict[str,str],timeout:float,clock_file:Path)->dict:
    if clock_file.is_file():clock_file.unlink()
    timer=['/usr/bin/time','-f','%e %U %S %M','-o',str(clock_file)] \
        if Path('/usr/bin/time').is_file() else []
    started=time.perf_counter()
    try:
        p=subprocess.run(timer+command,cwd=ROOT,env=env,
                         capture_output=True,text=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        return dict(command=command,status='FAIL',exit_code=None,error=str(exc),
                    outer_wall_seconds=time.perf_counter()-started)
    wall=time.perf_counter()-started
    stats=clock_file.read_text().split() if clock_file.is_file() else []
    usage=(dict(wall_seconds=float(stats[0]),user_seconds=float(stats[1]),
                system_seconds=float(stats[2]),peak_rss_kib=int(stats[3]))
           if len(stats)==4 else None)
    try:info=json.loads(p.stdout)
    except json.JSONDecodeError:info=None
    ok=p.returncode==0 and isinstance(info,dict) and info.get('status')=='PASS'
    return dict(command=command,exit_code=p.returncode,
                status='PASS' if ok else 'FAIL',result=info,
                stdout_tail=p.stdout[-1000:],stderr_tail=p.stderr[-1000:],
                process_usage=usage,outer_wall_seconds=wall)


def median(trials:list[dict],side:str,attr:str)->float|None:
    series=[]
    for trial in trials:
        usage=trial[side].get('process_usage')
        if usage is None:return None
        series.append(usage[attr])
    return statistics.median(series) if series else None


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p17')
    ap.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17/bench/highrate')
    ap.add_argument('--duration',type=float,default=.08,
                    help='source audio seconds; accepts 0.001 through 130, unlike the old P16 5-s cap')
    ap.add_argument('--repetitions',type=int,default=3)
    ap.add_argument('--warmups',type=int,default=1)
    ap.add_argument('--timeout',type=int,default=1800)
    ap.add_argument('--rates',type=int,nargs='+',default=list(RATES))
    ap.add_argument('--profiles',type=int,nargs='+',default=[0,1])
    ap.add_argument('--channels',type=int,nargs='+',default=[1,2,6])
    ap.add_argument('--no-encode',action='store_true')
    ap.add_argument('--encoding-tier',default='scalar',choices=['scalar','sse2','avx1','avx2','avx512'])
    args=ap.parse_args()
    if not (.001<=args.duration<=130. and 1<=args.repetitions<=30 and
            0<=args.warmups<=10 and 1<=args.timeout<=7200 and
            all(r in RATES for r in args.rates) and args.rates and
            all(p in (0,1) for p in args.profiles) and args.profiles and
            all(c in (1,2,6) for c in args.channels) and args.channels):
        ap.error('invalid duration, rate, profile, channel or run bounds')
    binary=args.unit.resolve()
    if not binary.is_file():ap.error(f'missing built private P17 binary {binary}')
    outfile=args.results/'paired.json'
    host=dict(platform=platform.platform(),machine=platform.machine(),node=platform.node(),
        python=platform.python_version(),
        cpu_model=next((s.split(':',1)[1].strip() for s in
           Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),None)
           if Path('/proc/cpuinfo').is_file() else None)
    record=dict(schema='P17/highrate-internal-paired-benchmark/1',host=host,
        binary_sha256=sha(binary),configuration=dict(duration_seconds=args.duration,
          repetitions=args.repetitions,warmups=args.warmups,timeout_seconds=args.timeout,
          encoder_sdm_tier=args.encoding_tier),cases=[],encoders=[],
        status='IN_PROGRESS',qualified=False,writer_enabled=False,
        methodology='process-level paired/interleaved alternating order, checked bit equality; /usr/bin/time wall CPU RSS when available',
        unrun_gates=['physical calibrated hardware, reference DSD512/1024 media and transports',
                     'multi-host full-duration thermal/sustained qualification',
                     'end-to-end SDM encoder profiling isolated from SRC and FIR'])
    args.results.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(LC_ALL='C',OMP_NUM_THREADS='1')
    # Do not inherit forced ISA overrides: decoder pairing must be matched.
    for name in ('SOX_DSD_KERNEL_FIR','SOX_DSD_KERNEL_SDM','SOX_DSD_PACKED_INPUT'):
        env.pop(name,None)
    with tempfile.TemporaryDirectory(prefix='p17-perf-') as td:
        timer=Path(td)/'clock.txt'
        for rate in args.rates:
          for profile in args.profiles:
            for channels in args.channels:
              name=f'R{rate}-P{profile}-C{channels}'
              row=dict(id=name,rate_hz=rate,profile='wideband' if profile else 'mastering',
                       channels=channels,source_audio_seconds=args.duration,
                       samples_per_channel=int(rate*args.duration),warmups=[],trials=[],
                       status='IN_PROGRESS')
              record['cases'].append(row);atomic_json(outfile,record)
              for trial in range(args.warmups+args.repetitions):
                order=(1,0) if trial%2 else (0,1)
                pairs={}
                for packed in order:
                  command=[str(binary),'bench',str(rate),str(profile),str(channels),
                      str(packed),repr(args.duration)]
                  pairs['packed' if packed else 'expanded']=invoke(command,env,args.timeout,timer)
                a,b=pairs['expanded'],pairs['packed']
                ar,br=a.get('result') or {},b.get('result') or {}
                matched=a['status']=='PASS' and b['status']=='PASS' and \
                    ar.get('pcm_digest_fnv64')==br.get('pcm_digest_fnv64') and \
                    ar.get('pcm_frames')==br.get('pcm_frames') and \
                    ar.get('frames')==br.get('frames') and ar.get('pcm_frames',0)>0
                result=dict(index=trial if trial<args.warmups else trial-args.warmups,
                            order=['packed' if v else 'expanded' for v in order],
                            expanded=a,packed=b,match=matched,
                            status='PASS' if matched else 'FAIL')
                (row['warmups'] if trial<args.warmups else row['trials']).append(result)
                atomic_json(outfile,record)
                if not matched:row['status']='FAIL';break
              if row['status']!='FAIL':
                row['status']='PASS'
                trials=row['trials']
                # The /usr/bin/time wall field has only 0.01 s resolution.
                # For short internal DSP measurements prefer the test engine's
                # CLOCK_MONOTONIC timing, which excludes process startup.
                a=statistics.median(t['expanded']['result']['wall_seconds'] for t in trials)
                b=statistics.median(t['packed']['result']['wall_seconds'] for t in trials)
                row['median_expanded_dsp_wall_seconds']=a
                row['median_packed_dsp_wall_seconds']=b
                row['packed_dsp_speedup_ratio']=a/b if a and b and b>0 else None
                row['median_expanded_peak_rss_kib']=median(trials,'expanded','peak_rss_kib')
                row['median_packed_peak_rss_kib']=median(trials,'packed','peak_rss_kib')
                ar=trials[0]['expanded']['result'];br=trials[0]['packed']['result']
                row['interstage_payload_bytes_expanded']=ar['input_payload_bytes']
                row['interstage_payload_bytes_packed']=br['input_payload_bytes']
                row['interstage_bytes_ratio_expanded_over_packed']=ar['input_payload_bytes']/br['input_payload_bytes']
                row['traffic_scope']='logical reader-to-DSP payload, not measured DRAM or disk traffic'
              atomic_json(outfile,record)
        if not args.no_encode:
          env['SOX_DSD_KERNEL_SDM']=args.encoding_tier
          for rate in args.rates:
            row=dict(id=f'encode-{rate}-{args.encoding_tier}',rate_hz=rate,
                     experimental=True,warmups=[],trials=[],status='IN_PROGRESS')
            record['encoders'].append(row);atomic_json(outfile,record)
            for index in range(args.warmups+args.repetitions):
              command=[str(binary),'bench-encode',str(rate),repr(args.duration)]
              run=invoke(command,env,args.timeout,timer)
              (row['warmups'] if index<args.warmups else row['trials']).append(run)
              atomic_json(outfile,record)
              if run['status']!='PASS':row['status']='FAIL';break
            if row['status']!='FAIL':
              digests={x['result']['native_digest_fnv64'] for x in row['trials']}
              digests.update(x['result']['native_digest_fnv64'] for x in row['warmups'])
              row['status']='PASS' if len(digests)==1 else 'FAIL'
              rows=[x['process_usage'] for x in row['trials'] if x['process_usage']]
              row['median_process_wall_seconds']=statistics.median(x['wall_seconds'] for x in rows) if rows else None
              row['median_peak_rss_kib']=statistics.median(x['peak_rss_kib'] for x in rows) if rows else None
              internal=statistics.median(x['result']['wall_seconds'] for x in row['trials'])
              row['median_composite_dsp_wall_seconds']=internal
              row['native_frames_per_second']=row['trials'][0]['result']['native_frames']/internal if internal>0 else None
              row['native_digest_fnv64']=next(iter(digests)) if len(digests)==1 else None
            atomic_json(outfile,record)
    good=bool(record['cases']) and all(x['status']=='PASS' for x in record['cases']+record['encoders'])
    record['status']='PASS_DEVELOPMENT_TESTS_UNQUALIFIED' if good else 'FAIL'
    atomic_json(outfile,record)
    print(json.dumps(dict(status=record['status'],decode_cases=len(record['cases']),
       encode_cases=len(record['encoders']),result=str(outfile)),sort_keys=True))
    return 0 if good else 1

if __name__=='__main__':raise SystemExit(main())
