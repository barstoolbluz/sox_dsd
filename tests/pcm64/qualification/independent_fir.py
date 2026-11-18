#!/usr/bin/env python3
"""Independent 192/256/384-bit paired centered FIR qualification.

Actual production lsx_dsd_fir_scalar() is called by a separately built,
test-only C driver. Input and coefficient words are consumed as hexadecimal
IEEE754 binary64 values. This checks arithmetic of the centered FIR itself,
not full SRC interpolation or analog/acoustic properties.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import struct
import subprocess
import sys

import mpmath as mp

SOURCE=Path(__file__).resolve().parents[3]
COEFF=SOURCE/'src/pcmdsd_coeffs.h'
U=2**-53
MIN_SUB=2**-1074
SEED=20261118


def demand(test,message):
    if not test: raise AssertionError(message)


def sha(path):
    with Path(path).open('rb') as fp:
        h=hashlib.sha256()
        for part in iter(lambda:fp.read(1<<18),b''):h.update(part)
        return h.hexdigest()


def coefficients():
    data=COEFF.read_text()
    result={}
    for rate,name,n in ((64,'lsx_pcmdsd_coeff_master64_256',61),
                        (128,'lsx_pcmdsd_coeff_master128',77)):
        m=re.search(r'\b'+name+r'\['+str(n)+r'\]\s*=\s*\{([^}]*)\}',data,re.S)
        demand(m is not None,f'missing or redefined production bank {name}')
        hexes=[x.strip() for x in m.group(1).split(',') if x.strip()]
        demand(len(hexes)==n,'coefficient count invalid')
        vals=[float.fromhex(x) for x in hexes]
        demand(all(math.isfinite(v) for v in vals),'nonfinite coefficients')
        result[rate]={'name':name,'values':vals,'hex':hexes,
                       'sha256_ieee64_words':hashlib.sha256(struct.pack('<'+str(n)+'d',*vals)).hexdigest()}
    return result


def vectors(n):
    r=random.Random(SEED+n)
    result={
        'impulse_center':[.5 if i==n//2 else 0. for i in range(n)],
        'impulse_oldest':[.5 if i==0 else 0. for i in range(n)],
        'impulse_latest':[-.5 if i==n-1 else 0. for i in range(n)],
        'silence':[-0.0 if i%2 else 0.0 for i in range(n)],
        'quiet':[math.ldexp(-1. if i%2 else 1.,-40) for i in range(n)],
        'alternating':[(-.5 if i%2 else .5) for i in range(n)],
        'dc':[.3125 for i in range(n)],
        'ramp':[(i-n//2)/n for i in range(n)],
        'near_rail':[(-1 if i%3 else 1)*math.nextafter(.5,0.) for i in range(n)],
    }
    for k in range(24):
        vals=[r.uniform(-.5,.5) for _ in range(n)]
        if k%4==0: vals[n//3]=math.ldexp(1.,-40)
        if k%4==1: vals[n//3]=math.nextafter(vals[n//3],math.inf)
        result['seeded_%02d'%k]=vals
    return result


def independent_at_precision(h,x,dps):
    # mp.mpf constructed from Python binary64 exactly, not decimal source.
    with mp.workdps(dps):
        L=len(h); mid=L//2
        result=mp.mpf(h[mid])*mp.mpf(x[mid])
        for i in range(mid):
            result+=mp.mpf(h[i])*(mp.mpf(x[i])+mp.mpf(x[L-1-i]))
        return +result


def strict_model(h,x):
    mid=len(h)//2
    total=h[mid]*x[mid]
    for i in range(mid):total+=h[i]*(x[i]+x[-1-i])
    return total


def bound(h,x):
    L=len(h);mid=L//2
    ops=1+3*mid
    g=ops*U/(1-ops*U)
    l1=abs(h[mid]*x[mid])+sum(abs(h[i])*(abs(x[i])+abs(x[L-1-i]))
                                for i in range(mid))
    return (2*g*l1 + (ops+1)*MIN_SUB),ops,l1


def run(probe,out):
    probe=Path(probe).resolve()
    demand(probe.is_file(),'compiled source FIR probe absent')
    coeff=coefficients(); commands=[]; cases=[]; input_lines=[]; labels=[]
    for rate,bank in coeff.items():
        for name,x in vectors(len(bank['values'])).items():
            input_lines.append(str(rate)+' '+' '.join(v.hex() for v in x))
            labels.append((rate,name,x))
    process=subprocess.run([str(probe)],input=('\n'.join(input_lines)+'\n').encode(),
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    demand(process.returncode==0,'compiled production FIR invocation failed: '+repr(process.stderr[:500]))
    outputs=process.stdout.decode().splitlines()
    demand(len(outputs)==len(labels),'missing or extra production FIR output')
    negative_wrong_center=False;negative_precision=False
    max_normalized_error=0.
    for (rate,name,x),actual_hex in zip(labels,outputs):
        h=coeff[rate]['values']
        actual=float.fromhex(actual_hex)
        demand(math.isfinite(actual),'nonfinite production FIR')
        high={}
        for bits,dps in ((192,65),(256,85),(384,125)):
            high[bits]=independent_at_precision(h,x,dps)
        # mpmath values from different contexts are rounded into current
        # context on subtraction; perform the convergence subtraction at 384 bits.
        with mp.workdps(135):
            delta192=abs(mp.mpf(high[192])-mp.mpf(high[384]))
            delta256=abs(mp.mpf(high[256])-mp.mpf(high[384]))
            reference=float(high[384])
        demand(delta192<=mp.mpf('1e-54') and delta256<=mp.mpf('1e-74'),
               f'192/256-bit reference failed convergence at {rate}:{name}')
        strict=strict_model(h,x)
        demand(struct.pack('<d',strict)==struct.pack('<d',actual),
               f'actual compiled scalar and separate-rounding model disagree {rate}:{name}')
        absolute_error=abs(actual-reference)
        error_limit,ops,l1=bound(h,x)
        demand(absolute_error<=error_limit,
               f'FIR absolute error above independently justified bound {rate}:{name}')
        if error_limit:
            max_normalized_error=max(max_normalized_error,absolute_error/error_limit)
        if name=='impulse_center':
            shifted=x[1:]+x[:1]
            negative_wrong_center|=(strict_model(h,shifted)!=actual)
        if name.startswith('seeded_'):
            # Reduced precision mutant: simulate rounding to 24-bit mantissa
            # on every tap input, rather than exact binary64 arithmetic.
            shifted=[struct.unpack('<f',struct.pack('<f',v))[0] for v in x]
            negative_precision|=(strict_model(h,shifted)!=actual)
        cases.append({'rate':rate,'name':name,'source_input_sha256':hashlib.sha256(
                     struct.pack('<'+str(len(x))+'d',*x)).hexdigest(),
                      'output_hex':actual.hex(),'reference_384_hex':reference.hex(),
                      'absolute_error':absolute_error,
                      'upper_absolute_bound':error_limit,
                      'sum_abs_products_l1':l1,'rounding_operations_upper':ops,
                      'reference_192_to_384_abs':str(delta192),
                      'reference_256_to_384_abs':str(delta256)})
    demand(negative_wrong_center,'wrong-centering mutant unexpectedly identical')
    demand(negative_precision,'reduced-precision mutant unexpectedly identical')
    result={'schema':'sox-native64-independent-fir/1','status':'PASS',
            'scope':'BOUNDED_FIR_ARITHMETIC_NOT_WHOLE_SRC_PROOF',
            'timestamp':dt.datetime.now(dt.timezone.utc).isoformat(),
            'probe_sha256':sha(probe),'scalar_source_sha256':sha(SOURCE/'src/dsd_kernels_scalar.c'),
            'coeff_header_sha256':sha(COEFF),
            'coeff_banks':{str(k):{'name':v['name'],
                'ieee64_sha256':v['sha256_ieee64_words'],
                'coeff_count':len(v['values'])} for k,v in coeff.items()},
            'precision_bits':[192,256,384],
            'reference_method':'exact IEEE754 input words, centered paired FIR, + zero extension; mpmath converged',
            'arithmetic_model':'center multiply, pair sum, pair product, sequential add, separate roundings',
            'bound_model':'gamma_n with n = 1 + 3*floor(L/2), epsilon=2^-53; 2*gamma_n*L1 + (n+1)*2^-1074',
            'max_fraction_of_error_bound':max_normalized_error,
            'wrong_center_mutant_rejected':True,
            'reduced_precision_mutant_rejected':True,
            'count':len(cases),'cases':cases}
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f'PASS independent FIR: {len(cases)} compiled production taps at 192/256/384-bit')
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--probe',required=True);a.add_argument('--out',required=True)
    p=a.parse_args();run(p.probe,p.out)
