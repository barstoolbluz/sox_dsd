#!/usr/bin/env python3
"""P09 scalar candidate comparison under the pre-frozen analysis-v1 ONLY.

This is an analytic native-rate recurrence probe, not the P10 interpolator,
source-bandwidth filter, or mastering stability/soak qualification. Outputs
are compared on the same reference waveform within each native rate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from analyze import decode_packed, measure, steady_segment, manifest

HERE=Path(__file__).resolve().parent


def confirm_lock():
    for line in (HERE/'SHA256SUMS.txt').read_text().splitlines():
        digest, name=line.split('  ',1)
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('analysis-v1 freeze hash mismatch: '+name)


def corpus_identity(frequency, peak_dbfs, rate, duration):
    config=dict(schema='P09/analytic-scalar-stimulus/1',native_rate_hz=rate,
                frequency_hz=frequency, source_peak_dbfs=peak_dbfs,
                modulator_reference_scale=.5,duration_seconds=duration,
                recurrence_input='0.5*10**(source_dbfs/20)*sin(2*pi*hz*n/native_rate)',
                interpolation='none: P09-only analytic input, not release qualification')
    identity=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return config, identity


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--unit',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--duration',type=float,default=1.6)
    ap.add_argument('--cases',choices=('standard','quick'),default='standard')
    args=ap.parse_args()
    confirm_lock()
    if args.duration < 1.51:ap.error('requires >=1.51 s for 250ms trim plus full second')
    args.results.mkdir(parents=True,exist_ok=True)
    ids={'legacy':'encode.legacy.v1', 'sdm-8':'encode.mastering.v1',
         'sdm-6':'encode.diagnostic.sdm6.v1',
         'clans-8':'encode.diagnostic.clans8.v1'}
    profiles=list(ids) if args.cases=='standard' else ['legacy','sdm-8']
    case_definitions=[('training',997.,-6.)]
    if args.cases=='standard':case_definitions += [('holdout',1000.,-20.)]
    locksha=hashlib.sha256((HERE/'SHA256SUMS.txt').read_bytes()).hexdigest()
    report=dict(schema='P09/analytic-probe-analysis-v1/1',analysis='analysis-v1',
                freeze_sha256=locksha,manifest_sha256=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),
                qualification='NOT QUALIFIED; analytic input bypasses production interpolation/prefilter',
                cases=[],rankings=[], errors=[])
    for rate in (2822400,5644800,11289600):
        for label,hz,db in case_definitions:
            for name in profiles:
                ident=f'dsd{rate//44100}'
                profile=ids[name]+'.'+ident
                config,source_sha=corpus_identity(hz,db,rate,args.duration)
                try:
                    with tempfile.TemporaryDirectory() as temp:
                        bits=Path(temp)/'audio.bits'
                        cmd=[str(args.unit),'--render',profile,str(rate),str(hz),str(db),
                             str(args.duration),str(bits)]
                        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
                        if proc.returncode!=0:
                            raise RuntimeError(f'probe returned {proc.returncode}: {proc.stderr[:1000]}')
                        produced=json.loads(proc.stdout)
                        bitsha=hashlib.sha256(bits.read_bytes()).hexdigest()
                        decoded=decode_packed(bits,produced['frames'],rate)
                        window,trim=steady_segment(decoded,rate)
                        # Exactly 1 second, coherent cycles for both frozen frequencies.
                        expected=.5*10**(db/20)
                        analysis=measure(window,hz,expected,window='rectangular')
                        rec=dict(kind=label,candidate=name,profile_id=profile,rate_hz=rate,
                                 source_config=config,source_identity_sha256=source_sha,
                                 bits_sha256=bitsha,metrology_trim=trim,
                                 recurrence_monitor=produced,measurement=analysis,
                                 status='measured-unqualified')
                        report['cases'].append(rec)
                        print('measured',label,rate,name,'analysis-v1 residual',
                              round(analysis['residual_band_dbfs'],3),flush=True)
                except Exception as exc:
                    report['errors'].append(dict(rate=rate,case=label,profile=profile,error=repr(exc)))
                finally:
                    (args.results/'candidate-analysis-v1.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
            candidates=[r for r in report['cases'] if r['rate_hz']==rate and r['kind']==label]
            if len(candidates)==len(profiles):
                ranked=sorted(candidates,key=lambda x:x['measurement']['residual_band_power'])
                report['rankings'].append(dict(rate_hz=rate,kind=label,
                   metric='20-20000Hz THD+N residual power under frozen analysis-v1, low to high',
                   order=[r['candidate'] for r in ranked],
                   caution='P09 analytic-input diagnostic; NOT a P10 quality/stability/qualification conclusion'))
    report['passed']=len(report['cases']);report['failed']=len(report['errors'])
    (args.results/'candidate-analysis-v1.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(dict(measured=report['passed'],failed=report['failed'],rankings=len(report['rankings']))))
    return 0 if not report['errors'] else 1

if __name__=='__main__':raise SystemExit(main())
