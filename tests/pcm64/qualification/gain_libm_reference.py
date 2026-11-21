#!/usr/bin/env python3
"""Source-operator numerical witnesses for D6 dB factors on the running libm.

This is finite, target-library evidence, not a universal maximum-ulp claim.
D6's accepted platform pow/exp error premise remains an owner proof gate.
"""
from __future__ import annotations
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sys
import mpmath as mp

ROOT=Path(__file__).resolve().parents[3]
M_LN10=float.fromhex('0x1.26bb1bbb55516p+1')
DPS=120


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_libm():
    filename=ctypes.util.find_library('m')
    if not filename:raise RuntimeError('libm not found: no numeric witness available')
    lib=ctypes.CDLL(filename)
    for name in ('pow','exp'):
        f=getattr(lib,name)
        f.argtypes=[ctypes.c_double]*(2 if name=='pow' else 1)
        f.restype=ctypes.c_double
    return lib,filename


def error_in_ulp(actual,ideal):
    with mp.workdps(DPS):
        ulp=mp.mpf(math.ulp(float(ideal)))
        delta=abs(mp.mpf(actual)-ideal)
        return float(delta/ulp),mp.nstr(delta,35)


def run():
    lib,name=load_libm()
    choices=['0','-0','0.0001','0.915','3.0103','6.0206','24','100','120']
    rng=random.Random(20261121)
    choices += [format(rng.randrange(0,1200000000000)/1e10,'.10f')
                for _ in range(32)]
    rows=[];max_pow=0.;max_exp=0.
    with mp.workdps(DPS):
        for original in choices:
            # The CLI accepts the decimal through strtod. Python's correctly
            # rounded float parsing gives the same IEEE binary64 word here.
            parsed=float(original)
            exponent=-parsed/20.0  # src/pcmdsd.c and src/sox_ng.c
            physical=lib.pow(10.,exponent)
            exact=mp.power(10,mp.mpf(exponent))
            pow_ulp,pow_abs=error_in_ulp(physical,exact)
            # src/gain.c uses dB_to_linear(), i.e. exp(d*M_LN10*0.05)
            # rather than pow(10,d/20), so test its actual operator too.
            gain_exponent=(parsed*M_LN10)*0.05
            gain=lib.exp(gain_exponent)
            gain_exact=mp.exp(mp.mpf(gain_exponent))
            exp_ulp,exp_abs=error_in_ulp(gain,gain_exact)
            if not (math.isfinite(physical) and physical>0 and
                    math.isfinite(gain) and gain>0 and
                    pow_ulp<2 and exp_ulp<2):
                raise AssertionError(f'finite libm witness exceeds 2 ulp screen: {original}')
            max_pow=max(max_pow,pow_ulp);max_exp=max(max_exp,exp_ulp)
            rows.append({'decimal_dB':original,'parsed_binary64_hex':parsed.hex(),
                         'headroom_exponent_hex':exponent.hex(),
                         'libm_pow_hex':physical.hex(),
                         'pow_error_ulps':pow_ulp,'pow_error_abs':pow_abs,
                         'gain_exp_exponent_hex':gain_exponent.hex(),
                         'libm_exp_hex':gain.hex(),
                         'exp_error_ulps':exp_ulp,'exp_error_abs':exp_abs,
                         'ideal_decimal_headroom':mp.nstr(mp.power(10,-mp.mpf(original)/20),50)})
    return {'schema':'phase08-d6-runtime-libm-witness/1',
            'status':'PASS_FINITE_WITNESSES_ONLY',
            'd6_pow_universal_error_premise':'OPEN',
            'libm':name,'platform_libc':platform.libc_ver(),
            'platform':platform.platform(),
            'source_sha256':{p:sha(ROOT/p) for p in
                 ('src/pcmdsd.c','src/sox_ng.c','src/gain.c','src/util.h')},
            'sample_count':len(rows),
            'finite_screen_max_ulps':2,
            'observed_max_pow_ulps':max_pow,
            'observed_max_exp_ulps':max_exp,
            'numeric_method':'384+-bit mpmath exponent reference from exact binary64 operand; 2-ulp finite screening; dB decimal operand documented separately',
            'limitations':'not a platform guarantee over every admitted decimal argument; no C strtod/exp/pow universal bound or compiler-contraction proof',
            'samples':rows}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--results',required=True,type=Path)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    try:record=run()
    except Exception as exc:record={'status':'FAIL','error':f'{type(exc).__name__}: {exc}',
                                    'd6_pow_universal_error_premise':'OPEN'}
    (args.results/'gain-libm-reference.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print('D6 libm:',record['status'],record.get('sample_count',0),record.get('error',''))
    raise SystemExit(0 if record['status'].startswith('PASS') else 1)

if __name__=='__main__':main()
