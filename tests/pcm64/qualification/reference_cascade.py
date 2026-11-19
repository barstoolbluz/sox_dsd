#!/usr/bin/env python3
"""Bounded P08-D02 primitive and source-SRC + centered-FIR references.

The P15 source-bound stage exporter includes the *unchanged* production
rate.c in a test executable and exposes the exact binary64 coefficients and
clock. P15's independent stage-index oracle validates those snapshot words.
This module independently evaluates short primitive and composed-stage
responses at 192, 256 and 384 bits, and compares to actual composite stage
observations. It does not certify FFT4G butterfly error or the downstream
working-to-native SRC; those remain covered by the existing named SRC tests.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import mpmath as mp

SOURCE=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(SOURCE/'tests/dsd'))
from p15_src_bound_operator import load_snapshot
from fir_reference import BANKS, sha256, window_at
from attestation import verify as verify_accepted_source, REFERENCE

PRECISIONS=(192,256,384)
FRAMES=1537
SOURCE_RATE=44100
INPUTS=(('head',0,False),('middle',FRAMES//2,False),
        ('tail',FRAMES-1,False),('composed',FRAMES//2-3,True))


def demand(ok,message):
    if not ok:raise AssertionError(message)


def invoke(argv,timeout=60):
    cp=subprocess.run([str(x) for x in argv],capture_output=True,timeout=timeout)
    demand(cp.returncode==0,f'failed {argv[:3]}: {cp.stderr[-650:]!r}')
    return cp


def unpack_f64(path:Path,n:int):
    data=path.read_bytes()
    demand(len(data)==n*8,f'{path.name}: wrong byte count')
    out=struct.unpack(f'<{n}d',data)
    demand(all(math.isfinite(v) for v in out),'nonfinite SRC/FIR observation')
    return out


def expected_length(frames,hz):
    return (frames*hz+SOURCE_RATE//2)//SOURCE_RATE


def nonzero_source(anchor,dual):
    return {anchor:0.5,**({anchor+1:-0.25,anchor+3:0.125} if dual else {})}


def exact_rational_src(stage,n,source):
    # The mapping comes from a frozen accepted-stage fixture, not the exporter
    # under test. Fraction.from_float retains every stored coefficient bit.
    return sum((Fraction.from_float(coef)*Fraction.from_float(source[j])
                for j,coef in stage.taps_to_previous(n)
                if 0<=j<FRAMES and j in source),Fraction(0))


def check_exact_reference(observed,expected,scale,where):
    with mp.workprec(384):
        reference=mp.mpf(expected.numerator)/mp.mpf(expected.denominator)
        delta=abs(observed-reference)
        maximum=mp.power(2,-155)*max(mp.mpf(1),mp.mpf(scale))
        demand(delta<=maximum,
               f'{where}: nominal 192-bit reference is low-precision or wrong phase: '
               f'{mp.nstr(delta,28)}')
    return mp.nstr(delta,48)


def oracle_src(stage,n:int,source:dict[int,float],bits:int,*,shift=0):
    # Same discrete phase schedule as the existing independent P15 operator.
    # Input zeros outside [0,FRAMES); exact stored coefficient words.
    with mp.workprec(bits):
        row=stage.taps_to_previous(n+shift)
        return mp.fsum(mp.mpf(coef)*mp.mpf(source.get(j,0.))
                       for j,coef in row if 0<=j<FRAMES and source.get(j,0.)!=0.)


def oracle_fir(stage,n:int,source:dict[int,float],bank:list[float],
               working_frames:int,bits:int,*,wrong_phase=False):
    taps=len(bank);half=taps//2
    received=n+half+1
    pos=[received-taps+j for j in range(taps)]
    if wrong_phase:pos=[k+1 for k in pos]
    with mp.workprec(bits):
        w=[oracle_src(stage,k,source,bits) if 0<=k<working_frames
           else mp.mpf(0) for k in pos]
        total=mp.mpf(bank[half])*w[half]
        for k in range(half):
            total+=mp.mpf(bank[k])*(w[k]+w[taps-1-k])
        return +total


def convergence(values,absolute_scale,where):
    # 192-bit input and coefficient words converge long before binary64.
    with mp.workprec(384):
        d1=abs(values[192]-values[256]);d2=abs(values[256]-values[384])
        allowed=(mp.power(2,-168)*max(mp.mpf(1),absolute_scale)+
                 mp.power(2,-1074))
        demand(d1<=allowed and d2<=allowed,
               f'{where}: high precision not converged: {d1} {d2}')
        return mp.nstr(d1,30),mp.nstr(d2,30)


def primitive_bound(stage,source):
    # FFT4G primitive is evaluated via convolution of captured *original*
    # exact LPF taps. A conservative N*eps*L1 estimate covers FFT butterflies,
    # plus the named P07 5e-10 independent SRC interior design criterion.
    # The latter is not a substitute for this phase/word-integrity oracle.
    taps=stage.coeff
    l1=math.fsum(abs(v) for v in taps)*stage.L
    peak=max(abs(x) for x in source.values())
    fft_est=(256*math.ceil(math.log2(stage.dft_length))*2**-53*l1*peak+
             4*math.ldexp(1.,-1074))
    return min(5e-10,max(fft_est,2e-14)),l1


def sampled_indices(n,anchor,up):
    approx=anchor*up
    return sorted({i for i in (0,1,2,n-3,n-2,n-1,
        approx-3,approx-1,approx,approx+1,approx+3)
        if 0<=i<n})


def checked_disagreement(actual,ideal,budget,where):
    with mp.workprec(384):
        error=abs(mp.mpf(actual)-ideal)
        demand(error<=mp.mpf(budget),
               f'{where}: observed {actual.hex()} differs by {mp.nstr(error,30)} '
               f'(bound={budget:.6g})')
        return float(error)


def execute(source:Path,exporter:Path,src_probe:Path,cascade:Path,results:Path):
    for binary in (exporter,src_probe,cascade):demand(binary.is_file(),f'absent: {binary}')
    results.mkdir(parents=True,exist_ok=True)
    att=verify_accepted_source(source)
    rows=[];controls=[];snapshots={};max_src_err=0.;max_cascade_err=0.
    with tempfile.TemporaryDirectory(prefix='p08-cascade-',dir=results) as d:
        tmp=Path(d)
        for multiplier,native in ((2,2822400),(4,5644800)):
            working=SOURCE_RATE*multiplier
            snap=tmp/f'stage-{multiplier}.json'
            invoke([exporter,SOURCE_RATE,working,snap])
            accepted=REFERENCE/f'stage-{multiplier}.json'
            demand(snap.read_bytes()==accepted.read_bytes(),
                   f'{multiplier}: production SRC coefficients or clock changed')
            stage_op=load_snapshot(accepted)
            demand(stage_op.input_hz==SOURCE_RATE and stage_op.output_hz==working
                   and len(stage_op.stages)==1,
                   f'unexpected actual SRC stage decomposition at {working} Hz')
            stage=stage_op.stages[0]
            demand(stage.kind==2 and stage.L==multiplier and stage.M==1,
                   f'unsupported primitive at {working} Hz: no speculative model')
            snap_store=results/f'src-stage-{multiplier}.json'
            snap_store.write_bytes(snap.read_bytes())
            snapshots[str(multiplier)]={'path':snap_store.name,'sha256':sha256(snap_store),
                                        'stage_count':len(stage_op.stages),
                                        'coeff_sha256':hashlib.sha256(
                                            struct.pack(f'<{len(stage.coeff)}d',*stage.coeff)).hexdigest(),
                                        'dft_taps':stage.dft_taps,
                                        'phase':{'L':stage.L,'M':stage.M,'post_peak':stage.dft_post_peak,
                                                 'preload':stage.preload,'remL':stage.remL}}
            bank=[float.fromhex(x) for x in att['fir_bank_f64_hex'][str(native//44100)]]
            actual_working=expected_length(FRAMES,working)
            actual_native=expected_length(FRAMES,native)
            demand(actual_working==FRAMES*multiplier,
                   'nonintegral count changes test model')
            for label,anchor,dual in INPUTS:
                key=f'dsd{native//44100}-{label}'
                p=tmp/key
                stage_result=json.loads(invoke([cascade,native,FRAMES,anchor,p,*(['dual'] if dual else [])]).stdout)
                demand(stage_result['source_frames']==FRAMES and
                       stage_result['working_frames']==actual_working and
                       stage_result['filtered_frames']==actual_working and
                       stage_result['native_frames']==actual_native,
                       f'{key}: incorrect actual finite SRC/FIR/native counts')
                working_words=unpack_f64(Path(str(p)+'.working.f64'),actual_working)
                filtered_words=unpack_f64(Path(str(p)+'.filtered.f64'),actual_working)
                if not dual:
                    independent=invoke([src_probe,'--impulse',SOURCE_RATE,
                                        working,FRAMES,anchor])
                    demand(independent.stdout==Path(str(p)+'.working.f64').read_bytes(),
                           f'{key}: composite R stage differs from independent P07 SRC')
                source_signal=nonzero_source(anchor,dual)
                prim_budget,l1src=primitive_bound(stage,source_signal)
                max_raw=0.;max_filtered=0.;max_conv1=0.;max_conv2=0.
                idx=sampled_indices(actual_working,anchor,multiplier)
                for j in idx:
                    values={b:oracle_src(stage,j,source_signal,b) for b in PRECISIONS}
                    if label=='composed' and j in (anchor*multiplier, anchor*multiplier+1,anchor*multiplier+3):
                        check_exact_reference(values[192],
                            exact_rational_src(stage,j,source_signal),l1src,
                            f'{key}/source-SRC/{j}')
                    c1,c2=convergence(values,mp.mpf(l1src),f'{key}/src/{j}')
                    max_conv1=max(max_conv1,float(mp.mpf(c1)))
                    max_conv2=max(max_conv2,float(mp.mpf(c2)))
                    err=checked_disagreement(working_words[j],values[384],
                                             prim_budget,f'{key}/SRC/{j}')
                    max_raw=max(max_raw,err)
                    if label=='composed' or j in (0,1,actual_working-1):
                        fir_values={b:oracle_fir(stage,j,source_signal,bank,
                                                 actual_working,b) for b in PRECISIONS}
                        convergence(fir_values,mp.mpf(l1src)*mp.fsum(abs(x) for x in bank),
                                    f'{key}/FIR/{j}')
                        # Propagate source error through L1 FIR, and account for
                        # 1+3*half separate-rounding operations in its scalar.
                        l1_fir=math.fsum(abs(x) for x in bank)
                        ops=1+3*(len(bank)//2)
                        gamma=(ops*2**-53)/(1-ops*2**-53)
                        bound=prim_budget*l1_fir+gamma*l1_fir*max(source_signal.values(),
                                key=abs).__abs__()*l1src+4e-15
                        f_err=checked_disagreement(filtered_words[j],fir_values[384],
                                                   bound,f'{key}/source SRC+FIR/{j}')
                        max_filtered=max(max_filtered,f_err)
                max_src_err=max(max_src_err,max_raw)
                max_cascade_err=max(max_cascade_err,max_filtered)
                rows.append({'rate_hz':native,'pattern':label,'anchor':anchor,
                             'source_frames':FRAMES,'working_frames':actual_working,
                             'filtered_frames':actual_working,'native_frames':actual_native,
                             'checked_working_indices':idx,
                             'raw_sha256':sha256(Path(str(p)+'.working.f64')),
                             'filtered_sha256':sha256(Path(str(p)+'.filtered.f64')),
                             'prim_bound_abs':prim_budget,
                             'max_src_abs_error':max_raw,
                             'max_cascade_abs_error':max_filtered,
                             'convergence_192_256_max':max_conv1,
                             'convergence_256_384_max':max_conv2})
                if label=='composed':
                    mid=anchor*multiplier
                    # Wrong phase perturbs SRC and the FIR, even if DSD bits
                    # themselves might not change for a quiet sample.
                    with mp.workprec(384):
                        ideal=oracle_src(stage,mid,source_signal,384)
                        wrong=oracle_src(stage,mid,source_signal,384,shift=1)
                        difference=abs(ideal-wrong)
                        demand(difference>mp.mpf(prim_budget)*10,
                               f'{key}: wrong SRC phase escaped')
                        j=mid
                        correct=oracle_fir(stage,j,source_signal,bank,actual_working,384)
                        shifted=oracle_fir(stage,j,source_signal,bank,actual_working,384,wrong_phase=True)
                        fir_diff=abs(correct-shifted)
                        demand(fir_diff>mp.mpf(prim_budget)*10,
                               f'{key}: wrong FIR centering escaped')
                    # Actual physical tail loss/duplication is injected and
                    # read back in qualification/verify.py. A bare inequality
                    # between n and n-1 would not be an observed stage fault.
                    controls.extend([{'rate_hz':native,'kind':'wrong-SRC-phase',
                        'difference':mp.nstr(difference,24),'status':'REJECTED'},
                        {'rate_hz':native,'kind':'wrong-FIR-centering',
                         'difference':mp.nstr(fir_diff,24),'status':'REJECTED'}])
        demand(len(rows)==8 and len(controls)==4,'missing primitive/cascade cases or mutants')
    return {'schema':'phase08-src-fir-short-reference/1','status':'PASS',
        'scope':'BOUNDED_SOURCE_SRC_PRIMITIVE_AND_SRC_TO_CENTERED_FIR_NOT_NATIVE_SRC_NOISE_FLOOR',
        'precision_bits':[192,256,384],
        'source_sha256':{name:sha256(source/name) for name in (
           'src/rate.c','src/pcmdsd.c','src/pcmdsd_coeffs.h',
           'src/rate_internal.h','tests/dsd/test_p15_src_stage_export.c',
           'tests/dsd/p15_src_bound_operator.py','tests/dsd/test_p07_reference.c',
           'tests/pcm64/qualification/cascade_probe.c',
           'tests/pcm64/qualification/reference_cascade.py')},
        'binary_sha256':{name:sha256(binary) for name,binary in (
            ('src_exporter',exporter),('src_probe',src_probe),('cascade_probe',cascade))},
        'snapshots':snapshots,'primitive_and_composed_cases':rows,
        'negative_controls':controls,'max_src_abs_error':max_src_err,
        'max_cascade_abs_error':max_cascade_err,
        'reference_method':'actual source-bound design tap words; separately computed 192/256/384-bit phase-indexed zero-extended rational LPF and chronological FIR',
        'roundoff_limit':'source FFT butterfly allowance 256 * ceil(log2 FFT size) * 2^-53 * L1, capped at existing P07 5e-10 interior tolerance; centered scalar FIR gamma_(1+3*half) * FIR L1 and source-error L1 propagation',
        'separate_rounding':'FIR center + symmetric pairs, not contracted FMA',
        'limitations':'Not a complete second/native 32x SRC numerical proof or 256-dB noise floor certificate'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--exporter',type=Path,required=True)
    parser.add_argument('--src-probe',type=Path,required=True)
    parser.add_argument('--cascade-probe',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    results=args.results.resolve();results.mkdir(parents=True,exist_ok=True)
    receipt=results/'independent-primitive-cascade.json'
    receipt.unlink(missing_ok=True)
    try:
        report=execute(args.source.resolve(),args.exporter.resolve(),
                       args.src_probe.resolve(),args.cascade_probe.resolve(),results)
        receipt.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
    except Exception as error:
        receipt.unlink(missing_ok=True)
        print(f'FAIL SRC primitive/cascade: {type(error).__name__}: {error}',file=sys.stderr)
        return 1
    print(f'PASS primitive/cascade: {len(report["primitive_and_composed_cases"])} physical cases '
          f'at two rates, 192/256/384-bit, {len(report["negative_controls"])} mutations')
    return 0

if __name__=='__main__':raise SystemExit(main())
