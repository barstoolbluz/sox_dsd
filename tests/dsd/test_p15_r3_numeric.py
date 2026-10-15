#!/usr/bin/env python3
"""Independent v2 FIR finite-boundary/ISA regression via public F64 decoder.

Direct longdouble composition of exact C hex words is independent of the
production ring and scalar accumulation order. Existing section 8.6 FIR
roundoff bound is applied ONLY where the SRC is bypassed. Fractional SRC
comparisons are empirical observations, NOT new SRC acceptance tolerances.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from reference import fixtures

ROOT=Path(__file__).resolve().parents[2]
V2=ROOT/'src/dsd_coeffs_v2.h'
V1=ROOT/'src/dsd_coeffs.h'
META=ROOT/'tests/dsd/reference/p15_r3_coefficients.json'


def bank_from_header(header,name):
    m=re.search(r'\blsx_dsd_coeff_'+re.escape(name)+r'\[(\d+)\]\s*=\s*\{(.*?)\};',
                header.read_text(),re.S)
    if not m:raise AssertionError('missing C99 bank '+name)
    values=np.array([np.longdouble(float.fromhex(t.strip())) for t in m.group(2).split(',') if t.strip()],dtype=np.longdouble)
    if len(values)!=int(m.group(1)) or not np.array_equal(values,values[::-1]):
        raise AssertionError('bad length or symmetry for '+name)
    return values


def equivalent_fir(names):
    acc=np.array([1],dtype=np.longdouble)
    norm=1.0;sum_taps=0
    for j,name in enumerate(names):
        b=bank_from_header(V1 if name=='halfband' else V2,name)
        norm*=float(np.sum(np.abs(b),dtype=np.longdouble));sum_taps+=len(b)
        stage=np.zeros((len(b)-1)*(1<<j)+1,dtype=np.longdouble)
        stage[::(1<<j)]=b
        acc=np.convolve(acc,stage)
    bound=16*np.finfo(float).eps*sum_taps*norm
    return acc,bound


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    executable=args.probe.resolve()
    if not executable.is_file():ap.error('probe binary missing')
    meta=json.loads(META.read_text())
    rows=[]
    args.results.mkdir(parents=True,exist_ok=True)
    result_file=args.results/'finite-and-isa.json'
    def save():
        result_file.write_text(json.dumps(dict(schema='sox-ng/p15-r3-finite-and-isa/1',
            release_status='BLOCKED',status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
            scope='native-rate exact FIR finite convolution and buffer/ISA; nonidentity SRC differences observed, not accepted against unqualified envelope',
            summary=dict(passed=sum(r['status']=='PASS' for r in rows),
                         failed=sum(r['status']=='FAIL' for r in rows)),
            cases=rows),sort_keys=True,indent=2)+'\n')
    def case(name,fn):
        try:
            detail=fn();rows.append(dict(name=name,status='PASS',detail=detail))
        except Exception as e:
            print('FAIL',name,str(e)[:300],flush=True)
            rows.append(dict(name=name,status='FAIL',error=f'{type(e).__name__}: {e}'))
        save()
    def ensure(p,msg):
        if not p:raise AssertionError(msg)
    def probe(native,output,tier,channels,N,chunk,payload):
        p=subprocess.run([str(executable),str(native),str(output),'mastering_v2',
              tier,str(channels),str(N),str(chunk)],input=payload,
              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,
              env={**os.environ,'SOX_OPTS':'','OMP_NUM_THREADS':'1','LC_ALL':'C'})
        if p.returncode:
            return None,p.stderr.decode('utf-8',errors='replace')
        actual=np.frombuffer(p.stdout,dtype='<f8')
        ensure(actual.size==((N*output+native//2)//native)*channels,
              'wrong numeric decoder count')
        ensure(np.all(np.isfinite(actual)),'nonfinite decoder F64')
        ensure(f'tier={tier}'.encode() in p.stderr,'forced ISA silently downgraded')
        return actual,p.stderr.decode('utf-8')
    for ident,profile in sorted(meta['profiles'].items()):
        native=profile['native_hz'];R=profile['intermediate_hz'];D=profile['factor'];G=profile['delay_native_frames']
        coeff,bound=equivalent_fir(profile['stage_banks'])
        ensure(len(coeff)==2*G+1,'independent group delay disagrees with manifest')
        for channels in (1,6):
            N=32769
            timelines=fixtures.bits(N,channels,'random')
            payload=bytes(bit for frame in zip(*timelines) for bit in frame)
            for pcm in sorted({R,48000,352800}):
                def regression(native=native,R=R,D=D,G=G,coeff=coeff,bound=bound,
                               channels=channels,N=N,pcm=pcm,payload=payload,timelines=timelines):
                    output,stderr=probe(native,pcm,'scalar',channels,N,997,payload)
                    ensure(output is not None,'scalar decoder failed '+stderr)
                    expected=(N*pcm+native//2)//native
                    shape=output.reshape((expected,channels))
                    for chunk in (1,17,4096):
                        actual,msg=probe(native,pcm,'scalar',channels,N,chunk,payload)
                        ensure(actual is not None,'scalar chunking failed '+msg)
                        ensure(np.array_equal(actual,output),f'chunk {chunk} altered samples')
                    peak_error=None
                    if pcm==R:
                        # Source is numeric +1/-1 with exact zero extension.
                        # Test early/middle/final frames and all output channels.
                        indices=sorted({0,1,2,3,4,expected//2,max(0,expected-5),
                                        max(0,expected-2),max(0,expected-1)})
                        worst=0.0
                        for out_i in indices:
                            native_idx=G+out_i*D-np.arange(len(coeff),dtype=np.int64)
                            mask=(native_idx>=0)&(native_idx<N)
                            k=np.flatnonzero(mask)
                            for c in range(channels):
                                t=timelines[c]
                                values=np.array([2*int(t[int(native_idx[j])])-1 for j in k],dtype=np.longdouble)
                                hp=float(np.sum(coeff[k]*values,dtype=np.longdouble))
                                delta=abs(hp-float(shape[out_i,c]))
                                worst=max(worst,delta)
                        ensure(worst<=bound,f'independent finite FIR discrepancy {worst} > 8.6 bound {bound}')
                        peak_error=worst
                    comparisons={}
                    for tier in ('sse2','avx1','avx2','avx512'):
                        vector,msg=probe(native,pcm,tier,channels,N,389,payload)
                        if vector is None:
                            ensure('UNSUPPORTED' in msg,'unexpected forced-ISA error '+msg[-200:])
                            comparisons[tier]={'status':'UNRUN_UNSUPPORTED_ON_THIS_BUILD_OR_CPU'}
                            continue
                        max_delta=float(np.max(np.abs(output-vector))) if len(output) else 0.0
                        if pcm==R:ensure(max_delta<=bound,'FIR-only 8.6 cross-ISA bound exceeded')
                        comparisons[tier]={'status':'PASS_FIR' if pcm==R else 'OBSERVED_SRC_UNQUALIFIED',
                                           'max_binary64_delta':max_delta}
                    return dict(profile=ident,native_hz=native,output_hz=pcm,
                        channels=channels,native_frames=N,pcm_frames=expected,
                        scalar_sha256=hashlib.sha256(output.tobytes()).hexdigest(),
                        independent_fir_bound=bound if pcm==R else None,
                        independent_fir_max_delta=peak_error,cross_isa=comparisons)
                case(f'finite_v2_{native//44100}_{pcm}_{channels}ch',regression)
        for n in (0,1,2,31,32,33):
            def tiny(n=n,native=native,R=R):
                bits=fixtures.bits(n,1,'random')[0]
                actual,msg=probe(native,R,'scalar',1,n,1,bits)
                ensure(actual is not None,'tiny input failed '+msg)
                expected=(n*R+native//2)//native
                ensure(len(actual)==expected,'tiny terminal frame wrong')
                return dict(input_frames=n,output_frames=len(actual),digest=hashlib.sha256(actual.tobytes()).hexdigest())
            case(f'tiny_v2_{native//44100}_{n}frames',tiny)
    save()
    result=json.loads(result_file.read_text())
    print('P15-R3 independent FIR/ISA candidate:',result['status'],result['summary'],result_file)
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
