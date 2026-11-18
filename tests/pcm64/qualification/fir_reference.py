#!/usr/bin/env python3
"""Independent bounded MPFR-like multiprecision reference for the actual FIR.

Uses exact hexadecimal source coefficient literals; no revised filter design.
The standalone test probe compiles the production scalar FIR and does not
intercept or modify the source project's DSP object. This validates the
current deployed coefficient banks and actual scalar rounding order.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

import mpmath as mp
from attestation import verify as verify_accepted_source

BANKS = {64:("lsx_pcmdsd_coeff_master64_256",61),
         128:("lsx_pcmdsd_coeff_master128",77)}
PRECISIONS=(192,256,384)


def check(ok:bool, detail:str):
    if not ok:raise AssertionError(detail)


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def doubles_digest(a:list[float])->str:
    return hashlib.sha256(struct.pack(f'<{len(a)}d',*a)).hexdigest()


def read_bank(path:Path, name:str, expected:int)->list[float]:
    source=path.read_text()
    expr=(r'\b'+re.escape(name)+r'\s*\[\s*(\d+)\s*\]\s*=\s*\{(.*?)\}')
    match=re.search(expr,source,flags=re.S)
    check(match is not None,f'coefficient bank {name} absent')
    words=re.findall(r'[-+]?0x[\da-f]+\.[\da-f]+p[-+]?\d+',match.group(2),flags=re.I)
    n=int(match.group(1))
    check(n==expected and len(words)==expected,f'bank size mismatch: {name}')
    bank=[float.fromhex(word) for word in words]
    check(all(math.isfinite(x) for x in bank) and
          all(struct.pack('<d',bank[i])==struct.pack('<d',bank[~i])
              for i in range(n)),f'asymmetric/nonfinite bank {name}')
    return bank


def stimulus(kind:str,n:int)->list[float]:
    if kind=='one':return [1.0]
    if kind=='zero':return [0.0]*n
    if kind=='alternating':return [1.0 if i%2==0 else -1.0 for i in range(n)]
    if kind=='impulse_head':return [0.8 if i==0 else 0. for i in range(n)]
    if kind=='impulse_tail':return [-0.75 if i==n-1 else 0. for i in range(n)]
    if kind=='longwave':return [.53*math.sin(i*0.231)+.13*math.cos(i*.087) for i in range(n)]
    if kind=='quiet':
        return [((-1)**i)*math.ldexp(1.0,-40)* (1.0+(i%7)/16) for i in range(n)]
    if kind=='subnormal':return [(-1.0 if i%2 else 1.0)*math.ldexp(1.0,-1074) for i in range(n)]
    raise ValueError(kind)


def window_at(source:list[float],length:int,received:int,*,mutate=False)->list[float]:
    """True oldest-to-newest ring order at a centered FIR emission.

    feed_fir writes at the prior head, increments head, and passes
    ``ring + prior_head + 1`` to the scalar kernel. The window therefore
    contains exactly samples [received-length, received). At startup and
    EOF the missing values are numeric zeros; never rotate the oldest word
    into the newest slot. The independent C probe consumes this same window.
    """
    pos=[received-length+i for i in range(length)]
    if mutate:
        pos=[j+1 for j in pos]
    return [source[i] if 0<=i<len(source) else 0.0 for i in pos]


def evaluate(bank:list[float],source:list[float],bits:int,*,mutate=False):
    length=len(bank);mid=length//2
    with mp.workprec(bits):
        coeff=[mp.mpf(x) for x in bank]
        results=[]
        for out in range(len(source)):
            received=out+mid+1
            w=window_at(source,length,received,mutate=mutate)
            terms=[mp.mpf(x) for x in w]
            val=coeff[mid]*terms[mid]
            for i in range(mid):
                val+=coeff[i]*(terms[i]+terms[length-1-i])
            results.append(val)
        return results


def exact_rational_fir(bank,source,out):
    """Exact dyadic coefficients/PCM with independently indexed zero extension."""
    half=len(bank)//2
    return sum((Fraction.from_float(bank[j])*Fraction.from_float(source[k])
                for j in range(len(bank))
                for k in (out-half+j,)
                if 0<=k<len(source) and source[k]!=0),Fraction(0))


def reject_reduced_reference(actual,fraction,scale,label):
    # At 192-bit precision the sum of a short, exactly dyadic FIR is
    # unambiguous at 2^-155 even if its correctly rounded binary64 is not.
    with mp.workprec(384):
        reference=mp.mpf(fraction.numerator)/mp.mpf(fraction.denominator)
        delta=abs(actual-reference)
        bound=mp.power(2,-155)*max(mp.mpf(1),mp.mpf(scale))
        check(delta<bound,
              f'{label}: purported 192-bit reference uses reduced precision '
              f'or incorrect centering (error={mp.nstr(delta,24)})')
    return mp.nstr(delta,48)


def error_budget(bank:list[float],source:list[float],out:int)->mp.mpf:
    length=len(bank);mid=length//2
    w=window_at(source,length,out+mid+1)
    with mp.workprec(384):
        positive=abs(mp.mpf(bank[mid])*mp.mpf(w[mid]))
        for i in range(mid):
            positive+=abs(mp.mpf(bank[i]))*(abs(mp.mpf(w[i]))+abs(mp.mpf(w[length-1-i])))
        u=mp.power(2,-53)
        # One center multiplication, and one pair sum, multiply and add
        # for each symmetric pair. The actual scalar disables contraction.
        operations=1+3*mid
        gamma=operations*u/(1-operations*u)
        subnormal_allowance=(operations+1)*mp.power(2,-1074)
        return gamma*positive+subnormal_allowance


def compile_probe(source:Path,target:Path)->list[str]:
    c=source/'tests/pcm64/qualification/fir_probe.c'
    kernel=source/'src/dsd_kernels_scalar.c'
    command=[os.environ.get('CC','cc'),'-O2','-ffp-contract=off','-fno-fast-math',
             '-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
             '-Isrc','-I.','-o',str(target),str(c),str(kernel),'-lm']
    cp=subprocess.run(command,cwd=source,capture_output=True,text=True,timeout=40)
    check(cp.returncode==0,f'FIR probe compile failed ({cp.returncode}): {cp.stderr[-1600:]}')
    check(target.is_file() and target.stat().st_size>0,'FIR executable missing')
    return command


def run_probe(path:Path,rate:int,signal:list[float])->list[float]:
    # The supplied test-only C binary calls the unmodified production scalar
    # directly. Pass each source-index-derived ring window as exact C99 hex.
    taps=BANKS[rate][1]
    half=taps//2
    lines=[]
    for output in range(len(signal)):
        # Independent physical probe indexing, NOT the reference window_at()
        # being verified. This separates a shifted reference from its witness.
        window=[signal[j] if 0<=j<len(signal) else 0.0
                for j in range(output-half,output-half+taps)]
        lines.append(str(rate)+" "+" ".join(x.hex() for x in window))
    cp=subprocess.run([str(path)],input=("\n".join(lines)+"\n").encode(),
                      capture_output=True,timeout=30)
    rows=cp.stdout.decode().splitlines()
    check(cp.returncode==0 and len(rows)==len(signal),
          f'actual C FIR probe failed rate={rate}, rc={cp.returncode}, error={cp.stderr[:500]!r}')
    return [float.fromhex(row) for row in rows]


def execute(source:Path,results:Path)->dict:
    source=source.resolve();results.mkdir(parents=True,exist_ok=True)
    att=verify_accepted_source(source)
    coeff=source/'src/pcmdsd_coeffs.h'
    with tempfile.TemporaryDirectory(prefix='phase08-fir-',dir=results) as scratch:
        probe=Path(scratch)/'fir_probe'
        command=compile_probe(source,probe)
        cases=[];controls=[]
        for rate,(name,count) in BANKS.items():
            # Coefficients used by the reference come from a separately
            # committed acceptance fixture, NOT the mutated C header.
            bank=[float.fromhex(x) for x in att['fir_bank_f64_hex'][str(rate)]]
            check(bank==read_bank(coeff,name,count),
                  f'{rate}: production FIR coefficient differs from fixed reference')
            for pattern in ('one','zero','alternating','impulse_head','impulse_tail',
                            'longwave','quiet','subnormal'):
                length=1 if pattern=='one' else 127
                data=stimulus(pattern,length)
                actual=run_probe(probe,rate,data)
                res={k:evaluate(bank,data,k) for k in PRECISIONS}
                max_error=mp.mpf(0);max_ratio=mp.mpf(0)
                max_convergence=mp.mpf(0)
                max_spot=mp.mpf(0)
                independent_exact_error=None
                with mp.workprec(384):
                    for i,x in enumerate(actual):
                        ideal=res[384][i]
                        delta=abs(mp.mpf(x)-ideal)
                        budget=error_budget(bank,data,i)
                        check(delta<=budget,f'{rate}/{pattern}/{i}: scalar FIR outside error bound')
                        max_error=max(max_error,delta)
                        max_ratio=max(max_ratio,delta/budget if budget else mp.mpf(0))
                        max_convergence=max(max_convergence,abs(res[192][i]-res[256][i]))
                        max_spot=max(max_spot,abs(res[256][i]-res[384][i]))
                        # Explicit precision-convergence criterion before comparison.
                        reliable=(mp.power(2,-175)*sum(abs(mp.mpf(v)) for v in bank)
                                  + mp.power(2,-1100))
                        check(abs(res[192][i]-res[256][i])<=reliable and
                              abs(res[256][i]-res[384][i])<=reliable,
                              f'{rate}/{pattern}/{i}: high-precision reference not converged')
                if pattern=='longwave':
                    j=length//2
                    independent_exact_error=reject_reduced_reference(
                        res[192][j],exact_rational_fir(bank,data,j),
                        math.fsum(abs(x) for x in bank)*max(map(abs,data)),
                        f'{rate}/{pattern}/{j}')
                cases.append({
                    'rate':rate,'pattern':pattern,'input_words':len(data),
                    'input_f64_sha256':doubles_digest(data),
                    'scalar_output_f64_sha256':doubles_digest(actual),
                    'coefficient_words_sha256':doubles_digest(bank),
                    'operation_count_separate':1+3*(count//2),
                    'operation_count_fma_hypothesis':1+2*(count//2),
                    'max_abs_error_hex':mp.nstr(max_error,70),
                    'max_bound_ratio':mp.nstr(max_ratio,30),
                    'max_ref192_vs256':mp.nstr(max_convergence,36),
                    'max_ref256_vs384':mp.nstr(max_spot,36),
                    'independent_exact_rational_error':independent_exact_error,
                    'status':'PASS'})
                if pattern=='longwave':
                    with mp.workprec(384):
                        wrong=evaluate(bank,data,384,mutate=True)
                        phase_error=max(abs(mp.mpf(x)-y) for x,y in zip(actual,wrong))
                        check(phase_error>mp.power(2,-20),f'{rate}: wrong phase escaped')
                        controls.append({'rate':rate,'name':'wrong-phase',
                            'detected_difference':mp.nstr(phase_error,30),'status':'REJECTED'})
                        short=evaluate(bank,data,24)
                        reduced_error=max(abs(mp.mpf(x)-y) for x,y in zip(actual,short))
                        check(reduced_error>mp.power(2,-29),f'{rate}: reduced precision escaped')
                        controls.append({'rate':rate,'name':'24bit-reference',
                            'detected_difference':mp.nstr(reduced_error,30),'status':'REJECTED'})
        check(len(cases)==16 and len(controls)==4,'FIR suite missing cases or controls')
        source_paths=[source/'src/dsd_kernels_scalar.c',source/'src/pcmdsd.c',
                      source/'src/pcmdsd_coeffs.h',source/'tests/pcm64/qualification/fir_probe.c',
                      source/'tests/pcm64/qualification/fir_reference.py']
        receipt={'suite':'phase08-independent-fir','status':'PASS',
            'scope':'SHORT_FIR_ARITHMETIC_ONLY_NOT_SINGULAR_SRC_FLOOR',
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'precision_bits':[192,256,384],
            'fma_contraction':'disabled in production scalar and test probe',
            'reference_type':'independent arbitrary-precision centered ring-window scalar FIR, exact float64 literals',
            'roundoff':'u=2^-53; gamma_(1+3*half) times L1 abs products; one subnormal ulp allowance per operation',
            'source_sha256':{str(p.relative_to(source)):sha256(p) for p in source_paths},
            'probe_compile_command':command,'probe_sha256':sha256(probe),
            'cases':cases,'negative_controls':controls}
        return receipt


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    output=args.results/'independent-fir.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.unlink(missing_ok=True)
    try:
        report=execute(args.source,args.results)
    except Exception as exc:
        output.write_text(json.dumps({'suite':'phase08-independent-fir',
              'status':'FAIL','error':f'{type(exc).__name__}: {exc}'},indent=2)+'\n')
        print(f'FAIL phase08 independent FIR: {exc}',file=sys.stderr)
        return 1
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(f'PASS Phase08 FIR: {len(report["cases"])} converged cases, '
          f'{len(report["negative_controls"])} rejected mutants')
    return 0

if __name__=='__main__':raise SystemExit(main())
