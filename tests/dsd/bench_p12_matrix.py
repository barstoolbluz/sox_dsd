#!/usr/bin/env python3
"""P12 host-bound, recorded four-tier guarded kernel and end-to-end matrix.

Default: fifteen randomized timed repeats plus warmups; DSD64/128/256
stereo full conversions, mono DSD64 and 6-channel DSD256 control cases.
The normal SDM guard and monitor are on. No dispatch preference is changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
TIERS=['scalar','sse2','avx1','avx2']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--repetitions',type=int,default=15)
    ap.add_argument('--kernel-frames',type=int,default=350000)
    ap.add_argument('--decode-seconds',type=float,default=.08)
    ap.add_argument('--encode-seconds',type=float,default=.04)
    ap.add_argument('--include-multichannel',action='store_true')
    a=ap.parse_args()
    if a.repetitions<15:ap.error('P12 performance evidence requires >=15 timed repetitions')
    output=a.results/'benchmark-matrix.json'
    report=dict(schema='P12/benchmark-matrix/1',host=platform.platform(),
        machine=platform.machine(),cpu_features='recorded per-object ISA audit',
        executable_sha256={p:sha(ROOT/p) for p in ('src/sox_ng','test/sox_p10_candidate',
                              'test/dsd_test_p11')},
        config=dict(repetitions=a.repetitions,kernel_frames=a.kernel_frames,
            decode_seconds=a.decode_seconds,encode_seconds=a.encode_seconds,
            tiers=TIERS,include_multichannel=a.include_multichannel),
        runs=[],errors=[],unrun=[],comparison={},
        warning='Host timings only, not evidence for a universal dispatch policy')
    suites=[('kernel',[sys.executable,'tests/dsd/bench_p11.py','--phase','P12',
          '--unit','test/dsd_test_p11','--results',str(a.results/'kernel'),
          '--repetitions',str(a.repetitions),'--frames',str(a.kernel_frames),
          '--tiers',*TIERS],a.results/'kernel/kernel-timing.json')]
    cases=[(rate,2) for rate in (2822400,5644800,11289600)]
    if a.include_multichannel:cases.extend([(2822400,1),(11289600,6)])
    for rate,channels in cases:
        case=f'dsd{rate//44100}-{channels}ch'
        path=a.results/case
        cmd=[sys.executable,'tests/dsd/bench_p11_e2e.py','--phase','P12',
             '--native-rate',str(rate),'--channels',str(channels),
             '--sox','src/sox_ng','--candidate','test/sox_p10_candidate',
             '--results',str(path),'--repetitions',str(a.repetitions),
             '--warmups','2','--decode-seconds',str(a.decode_seconds),
             '--encode-seconds',str(a.encode_seconds),'--tiers',*TIERS]
        suites.append((case,cmd,path/'forced-cli-timing.json'))
    atomic(output,report)
    for name,cmd,artifact in suites:
        try:
            cp=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=1800,
                              env=dict(os.environ,OMP_NUM_THREADS='1',SOX_OPTS=''))
            row=dict(name=name,command=cmd,exit=cp.returncode,evidence=str(artifact.relative_to(a.results)),
                 stdout=cp.stdout[-2000:],stderr=cp.stderr[-1000:])
            if artifact.is_file():
                actual=json.loads(artifact.read_text())
                row['status']=actual['status']
                if name=='kernel':
                    report['comparison']['kernel']={
                        mode:{tier:dict(median_cpu_ns_per_frame=v['median_cpu_ns_per_frame'],
                           speedup_over_scalar=v.get('speedup_over_scalar'))
                           for tier,v in data.items()}
                        for mode,data in actual['summary'].items()}
                else:
                    report['comparison'][name]={family:{tier:dict(
                        median_wall_seconds=v['median_wall_seconds'],
                        median_cpu_seconds=v.get('median_cpu_seconds'),
                        max_rss_kib=v.get('max_rss_kib'))
                        for tier,v in data.items()}
                        for family,data in actual['summary'].items()}
            if cp.returncode:
                report['errors'].append(dict(name=name,exit=cp.returncode,detail=cp.stderr[-300:]))
            report['runs'].append(row)
        except Exception as exc:
            report['errors'].append(dict(name=name,error=repr(exc)))
        atomic(output,report)
        print(name,report['runs'][-1].get('status','FAIL') if report['runs'] and report['runs'][-1]['name']==name else 'FAIL',flush=True)
    report['status']='PASS' if not report['errors'] and len(report['runs'])==len(suites) else 'FAIL'
    atomic(output,report)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
