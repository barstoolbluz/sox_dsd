#!/usr/bin/env python3
"""Finite high-precision P3 final SRC witnesses for the unified DSD64/128 decoder.

The five FIRs are evaluated by the independent chronological long-double
convolution, including the *ceil(native/32)* intermediate words actually
passed to rate.c before the public output frame count is trimmed. The final
SRC's exact source-bound binary64 coefficients and phase graph are evaluated
at 192/256/384 bits. No public decoder/C FIR, or output bitstream, is used
as an oracle. D11's universal same-operator proof still needs an FFT4G error
certificate, compilation premises, accepted domains and owner sign-off.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import mpmath as mp
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/dsd'))
sys.path.insert(0,str(ROOT/'tests/pcm64'))
sys.path.insert(0,str(ROOT/'tests/dsd/reference'))
from p15_src_bound_operator import load_snapshot
from decode import parse_wav
from unified_reference import banks, independent_reconstruction
import fixtures

OUTPUT_HZ=96000
U=2**-53
BITS=(192,256,384)
# Short/partial-block, interior, unaligned long, exact output rounding. The
# n=8193 and 131073 cases have an extra native-clock reconstruction tail.
LENGTHS=(33,8193,32787,131073)


def demand(condition,message):
    if not condition:raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate_at(op,n,source):
    row=op.exact_row(n,len(source),precision=140)
    estimates={}
    for precision in BITS:
        with mp.workprec(precision):
            estimates[precision]=mp.fsum(weight*mp.mpf(float(source[j]))
                                         for j,weight in row.items())
    with mp.workprec(384):
        conv_192=abs(estimates[384]-estimates[192])
        conv_256=abs(estimates[384]-estimates[256])
        demand(conv_192 <= mp.power(2,-168)*max(1,abs(estimates[384])) and
               conv_256 <= mp.power(2,-230)*max(1,abs(estimates[384])),
               f'final SRC reference precision failed to converge at {n}')
    return row,estimates[384]


def sampled_indices(total):
    return sorted(i for i in {0,1,2,total//2-1,total//2,total//2+1,
                              total-3,total-2,total-1} if 0<=i<total)


def source_fft_screen(op,peak):
    """Finite engineering screen, *not* a universal FFT4G error proof."""
    l1=math.prod(s.L*math.fsum(abs(x) for x in s.coeff) if s.kind==2
                 else max(1.,math.fsum(abs(x) for x in s.coeff))
                 for s in op.stages)
    fft_steps=sum(math.ceil(math.log2(s.dft_length)) for s in op.stages
                  if s.kind==2)
    poly_operations=sum(2*s.n for s in op.stages if s.kind==3)
    # Conservative screening multiplier for this finite fixture, not a
    # claim of an FFT4G butterfly error theorem.
    return 512*fft_steps*U*l1*peak + 4*poly_operations*U*l1*peak+1e-14


def execute(sox,exporter,results):
    coeff=banks()
    cases=[];controls=[];snapshots={}
    max_error=0.
    results.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='phase08-final-src-',dir=results) as scratch:
        scratch=Path(scratch)
        for rate in (fixtures.DSD64,2*fixtures.DSD64):
            native=rate//32
            p=scratch/f'rate-{native}.json'
            cmd=[str(exporter),str(native),str(OUTPUT_HZ),str(p)]
            cp=subprocess.run(cmd,capture_output=True,timeout=30)
            demand(cp.returncode==0,
                   f'SRC exporter failed {native}->96k: {cp.stderr[-300:]!r}')
            operator=load_snapshot(p)
            demand(operator.input_hz==native and operator.output_hz==OUTPUT_HZ and
                   len(operator.stages)==2 and
                   {s.kind for s in operator.stages}=={2,3} and
                   all(s.order in (-1,0) for s in operator.stages),
                   f'{native}: unsupported actual source-bound SRC operator')
            stored=results/f'final-src-{native}-to-{OUTPUT_HZ}.json'
            stored.write_bytes(p.read_bytes())
            snapshots[str(native)]={'path':stored.name,'sha256':sha(stored),
                                    'stages':[{'kind':s.kind,'L':s.L,'M':s.M,
                                               'fft_size':s.dft_length,'poly_order':s.order,
                                               'coefficient_count':len(s.coeff)}
                                              for s in operator.stages]}
            for profile in ('mastering','wideband'):
                for n in LENGTHS:
                    channels=1
                    physical=fixtures.bits(n,channels,
                                           'random' if n>100 else '69')
                    source=scratch/'physical.dsf'
                    source.write_bytes(fixtures.make_dsf(physical,rate))
                    # The DSD reconstruction front end finishes at ceil(N/32)
                    # even if the public native-clock output is rounded to the
                    # nearest frame. Omitting the last word changes the SRC.
                    expected_mid=(n+16)//32
                    offered_mid=(n+31)//32
                    extra=offered_mid-expected_mid
                    demand(extra in (0,1),'unexpected extra reconstruction count')
                    input_words,front_bound,delay=independent_reconstruction(
                        physical[0],rate,profile,coeff,tail_frames=extra)
                    demand(len(input_words)==offered_mid,
                           'front-end produced wrong finite tail count')
                    target=(n*OUTPUT_HZ+rate//2)//rate
                    for kernel in ('scalar','auto'):
                        out=scratch/'converted.wav'
                        argv=[str(sox),'--precision','64','--decode',
                              f'decode.{profile}.dsd{rate//44100}',
                              '--dsd-level','preserve','--dsd-bandwidth',
                              'strict' if profile=='mastering' else 'adapt',
                              str(source),'-b','64','-e','floating-point',
                              '-r',str(OUTPUT_HZ),str(out)]
                        env=dict(os.environ,SOX_DSD_KERNEL_FIR=kernel)
                        cp=subprocess.run(argv,capture_output=True,env=env,timeout=60)
                        demand(cp.returncode==0,
                               f'{rate}/{profile}/{n}/{kernel}: {cp.stderr[-400:]!r}')
                        payload,_=parse_wav(out,target,channels,OUTPUT_HZ)
                        observed=np.frombuffer(payload,dtype='<f8')
                        demand(len(observed)==target and np.isfinite(observed).all(),
                               'nonfinite/miscounted final PCM output')
                        peak=max(float(np.max(np.abs(input_words))),1e-200)
                        screen=source_fft_screen(operator,peak)
                        row_checks=[]
                        for j in sampled_indices(target):
                            row,ideal=evaluate_at(operator,j,input_words)
                            # B_{5} reaches the actual SRC by its output-row
                            # L1 norm; the stage screen covers the source-rate
                            # floating point convolution and phase arithmetic.
                            row_l1=float(mp.fsum(abs(w) for w in row.values()))
                            budget=screen + front_bound*row_l1
                            with mp.workprec(384):
                                err=float(abs(mp.mpf(float(observed[j]))-ideal))
                            demand(err<=budget,
                                   f'P3 final-SRC numeric screen failed {rate}/{profile}/'
                                   f'{n}/{kernel}@{j}: {err:.8g} > {budget:.8g}')
                            max_error=max(max_error,err)
                            row_checks.append({'frame':j,'source_terms':len(row),
                                               'abs_error':err,'finite_screen':budget})
                        if extra and n==8193 and profile=='mastering' and kernel=='scalar':
                            last=target-1
                            row,ideal=evaluate_at(operator,last,input_words)
                            with mp.workprec(384):
                                wrong=mp.fsum(w*mp.mpf(float(input_words[k]))
                                              for k,w in row.items() if k<expected_mid)
                                gap=float(abs(ideal-wrong))
                            demand(gap>1e-7,'missing-tail mutant went undetected')
                            controls.append({'native_hz':rate,
                                'kind':'omit_last_offered_reconstruction_word',
                                'last_frame':last,'separation':gap,'status':'REJECTED'})
                        cases.append({'native_hz':rate,'profile':profile,
                            'kernel':kernel,'input_dsd_frames':n,
                            'output_pcm_frames':target,'intermediate_offered':offered_mid,
                            'intermediate_public_at_native_rate':expected_mid,
                            'extra_SRC_tail_words':extra,'front_fir_bound':front_bound,
                            'frontend_delay_native_frames':delay,
                            'output_sha256':hashlib.sha256(payload).hexdigest(),
                            'input_dsf_sha256':sha(source),'rows':row_checks})
    demand(len(cases)==2*2*len(LENGTHS)*2 and len(controls)==2,
           'final SRC qualification corpus incomplete')
    return {'schema':'phase08-p3-final-src-source-witness/1',
            'status':'PASS_FINITE_WITNESSES_ONLY',
            'd11_universal_p3_bound':'OPEN',
            'source_sha256':{p:sha(ROOT/p) for p in
                ('src/rate.c','src/dsd_decode.c','src/dsd_public.c',
                 'src/dsd_coeffs.h','tests/dsd/p15_src_bound_operator.py',
                 'tests/pcm64/qualification/unified_reference.py')},
            'exporter_sha256':sha(exporter),'sox_sha256':sha(sox),
            'source_operator_snapshots':snapshots,'precision_bits':list(BITS),
            'independent_method':'five-stage independent long-double chronological FIR, source-bound final SRC output row at 192/256/384 bits',
            'finite_screen_basis':'512 * sum_fft_log2N * eps * product_L1 * peak + poly_ops * eps * product_L1 + upstream per-stage FIR gamma bound',
            'limitations':'finite source-derived SRC operator/phase screening only; universal FFT4G error, output-precision/gain domains and compiler/ISA proof remain OPEN',
            'wrong_tail_mutants':controls,'case_count':len(cases),
            'max_abs_error':max_error,'cases':cases}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',required=True,type=Path)
    ap.add_argument('--exporter',required=True,type=Path)
    ap.add_argument('--results',required=True,type=Path)
    args=ap.parse_args()
    try:record=execute(args.sox.resolve(),args.exporter.resolve(),args.results.resolve())
    except Exception as exc:
        record={'status':'FAIL','d11_universal_p3_bound':'OPEN',
                'error':f'{type(exc).__name__}: {exc}'}
    args.results.mkdir(parents=True,exist_ok=True)
    (args.results/'final-src-reference.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print('P3 final SRC:',record['status'],record.get('case_count',0),
          record.get('error',''))
    raise SystemExit(0 if record['status'].startswith('PASS') else 1)

if __name__=='__main__':main()
