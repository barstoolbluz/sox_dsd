#!/usr/bin/env python3
"""P06 independent finite convolution oracle for compiled scalar C vectors.

Reconstruct H_eq by arbitrary-precision polynomial convolution, independently
of the streaming stage/ring/phase algorithm. Each stream is checked against
extended-precision direct convolution, with targeted 75-digit edge/impulse
checks. Do not import the P06 coefficient generator or feasibility data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import subprocess
import sys
import time

try:
    import mpmath as mp
    import numpy as np
    from certify_filters import load_coefficients
except ImportError as error:
    print(f"UNRUN required P06/P07 numerical oracle (missing {error.name})", file=sys.stderr)
    raise SystemExit(2) from None

ROOT = pathlib.Path(__file__).resolve().parents[2]
mp.mp.dps = 75
DBL_EPS=2.0**-52


def native_bit(i,c,pattern,n):
    x = (i*1664525 + c*1013904223 + (i >> 3)*2246822519)&0xffffffff
    x ^= x >> 13
    if pattern==0:return (x&1) != 0
    if pattern==1:return False
    if pattern==2:return True
    return i == n//2 and c==0


def build_eq(banks,names):
    """Exact convolution of IEEE-754 values at 75 decimal digits; sparse dilations."""
    out=[mp.mpf(1)]
    for j,name in enumerate(names):
        h=banks[name]
        step=1<<j
        new=[mp.mpf(0)]*(len(out)+(len(h)-1)*step)
        for i,v in enumerate(h):
            if not v:continue
            coef=mp.mpf(float(v))
            start=i*step
            for k,a in enumerate(out):
                if a:new[k+start]+=coef*a
        out=new
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unit',type=pathlib.Path,default=ROOT/'test/dsd_test_decode')
    p.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P06/scalar')
    args=p.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    t0=time.monotonic()
    test=subprocess.run([str(args.unit),'--unit'],capture_output=True,text=True,timeout=300,cwd=ROOT)
    (args.results/'unit.log').write_text(test.stdout+test.stderr)
    if test.returncode:
        raise RuntimeError('compiled C unit contract failed: '+test.stderr)
    vector=subprocess.run([str(args.unit),'--vectors'],capture_output=True,text=True,timeout=300,cwd=ROOT)
    if vector.returncode:
        raise RuntimeError('compiled C vector probe failed: '+vector.stderr)
    (args.results/'vectors.jsonl').write_text(vector.stdout)
    manifest=json.loads((ROOT/'tests/dsd/reference/p06_coefficients.json').read_text())
    banks=load_coefficients()
    eq_cache={}
    bound_cache={}
    for prof,meta in manifest['profiles'].items():
        names=tuple(meta['stage_banks'])
        if names not in eq_cache:
            eq_cache[names]=build_eq(banks,names)
            assert len(eq_cache[names])==2*meta['delay_native_frames']+1
            assert abs(mp.fsum(eq_cache[names])-1)<mp.mpf('1e-13')
        bound_cache[prof]=16*DBL_EPS*sum(len(banks[n]) for n in names)*math.prod(
                float(np.sum(np.abs(banks[n]),dtype=np.longdouble)) for n in names)
    # Convert high-precision coefficients once to 80-bit precision for all
    # vector samples.  On platforms with 64-bit longdouble this still receives
    # independent mpmath checks and the same roundoff envelope.
    eq_ld={names:np.asarray([np.longdouble(mp.nstr(x,35)) for x in h],dtype=np.longdouble)
           for names,h in eq_cache.items()}
    checks=0
    mp_checks=0
    max_error=0.0
    max_mp_error=0.0
    max_relative_bound=0.0
    cases=0
    profiles_seen=set()
    configurations=set()
    for line in vector.stdout.splitlines():
        case=json.loads(line)
        prof=case['profile']; channels=case['channels']; N=case['length']; pattern=case['pattern']
        meta=manifest['profiles'][prof]
        D=meta['factor'];G=meta['delay_native_frames']; M=(N+D-1)//D
        names=tuple(meta['stage_banks'])
        coeff=eq_ld[names]
        got=np.array([float.fromhex(w) for w in case['values']],dtype=np.float64)
        if len(got)!=M*channels:
            raise AssertionError(f'{prof}/{channels}/{N}: got {len(got)} != {M*channels}')
        got=got.reshape((M,channels))
        profiles_seen.add(prof);configurations.add((prof,channels,N,pattern))
        bound=bound_cache[prof]
        if M and N:
            indexes=np.arange(N,dtype=np.int64)
            for c in range(channels):
                x=np.array([1 if native_bit(i,c,pattern,N) else -1 for i in range(N)],dtype=np.longdouble)
                for m in range(M):
                    at=G+m*D-indexes
                    inrange=(at>=0)&(at<len(coeff))
                    ref=np.dot(coeff[at[inrange]],x[inrange])
                    error=float(abs(np.longdouble(got[m,c])-ref))
                    max_error=max(max_error,error)
                    max_relative_bound=max(max_relative_bound,error/bound)
                    if not np.isfinite(got[m,c]) or error>bound:
                        raise AssertionError(f'{prof}/{channels}/{N}/pattern{pattern}/frame{m}/channel{c}: got {got[m,c]} ref {ref} abs error {error} > {bound}')
                    checks+=1
                # 75-digit direct coefficient oracle for both endpoints and an
                # interior sample; includes short impulse perturbations.
                selected={0,M//2,M-1}
                for m in sorted(selected):
                    center=G+m*D
                    lo=max(0,center-(len(coeff)-1));hi=min(N,center+1)
                    direct=mp.fsum(eq_cache[names][center-i]*
                                   (1 if native_bit(i,c,pattern,N) else -1)
                                   for i in range(lo,hi))
                    error=float(abs(mp.mpf(float(got[m,c]))-direct))
                    max_mp_error=max(max_mp_error,error)
                    if error>bound:
                        raise AssertionError(f'high-precision finite oracle {prof}/{channels}/{N}/p{pattern}/m{m}/c{c}: {error} > {bound}')
                    mp_checks+=1
        cases+=1
    assert profiles_seen==set(manifest['profiles'])
    assert cases==6*4*11*4,(cases,'unexpected vector coverage')
    report=dict(schema='sox-ng/p06-scalar-oracle/1',cases=cases,frames_compared=checks,
                high_precision_finite_samples_compared=mp_checks,
                max_binary64_vs_direct_longdouble_abs=max_error,
                max_binary64_vs_75_digit_abs=max_mp_error,
                largest_fraction_of_design_bound=max_relative_bound,
                design_bound='16 * DBL_EPSILON * sum(taps) * product(stage_L1) * max(1,input_peak)',
                input='canonical native +/-SOX_SAMPLE_MAX; 0 outside finite input',
                independent_method='75-digit equivalent polynomial; direct finite-signal convolution, longdouble for full streams and 75-digit boundary/interior checks',
                vector_sha256=hashlib.sha256(vector.stdout.encode()).hexdigest(),
                elapsed_seconds=time.monotonic()-t0,
                channels=[1,2,5,6],profiles=sorted(profiles_seen),
                unit_stdout=test.stdout.strip(),passed=True)
    (args.results/'oracle.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(f'P06 scalar oracle PASS: {cases} vectors, {checks} frame/channel samples, '
          f'{mp_checks} high-precision checks; largest bound fraction {max_relative_bound:.6f}; {report["elapsed_seconds"]:.1f}s')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
