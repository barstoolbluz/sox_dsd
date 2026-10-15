#!/usr/bin/env python3
"""Deterministic additive v2 reconstruction banks; leaves P06 v1 bytes untouched.

The length estimate is only a starting point. Each rounded filter is checked
against a preliminary numerical envelope; independent certification is in
certify_p15_r3_filters.py (which does not import this generator).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy import signal
from generate_coeffs import design, hexdigest, mp, BETA

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT/'src/dsd_coeffs_v2.h'
MANIFEST = ROOT/'tests/dsd/reference/p15_r3_coefficients.json'
PROFILES = (
    ('master64_v2', 'decode.mastering.v2.dsd64', 2822400, 88200, 25000, 40000),
    ('master128_v2','decode.mastering.v2.dsd128',5644800,176400,48000,60000),
    ('master256_v2','decode.mastering.v2.dsd256',11289600,176400,66000,80000),
)


def preliminary_bank_test(h, P, S, fs):
    # Guard against gross design failure; this does NOT qualify the bank.
    # SOS and full coherent alias certification use the independent program.
    w, v = signal.freqz(np.asarray(h), worN=262144, fs=fs)
    mag = np.abs(v)
    passband = mag[w <= P]
    stopband = mag[w >= S]
    ripple = float(np.max(np.abs(20*np.log10(np.maximum(passband, 1.e-300)))))
    stop = float(np.max(stopband))
    return ripple, 20*math.log10(max(stop,1e-300))


def candidate_length(P,S,fs):
    delta=(S-P)/fs
    estimate=math.ceil((190-8)/(2.285*2*math.pi*delta))+1
    return estimate + (1-estimate)%4


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    header=['/* P15-R3 decoder mastering v2 FIR banks. Do not alter P06 v1 header. */',
            '#ifndef LSX_DSD_COEFFS_V2_H','#define LSX_DSD_COEFFS_V2_H','']
    meta=dict(schema='sox-ng/p15-r3-coefficients/1',generator='tests/dsd/generate_p15_r3_coeffs.py',
        generator_version=1,arithmetic='mpmath 95 decimal digits to IEEE 754 binary64',
        mpmath_version=mp.__version__, design_attenuation_db=190,
        beta_decimal=str(BETA),bank_sha256_algorithm='sha256 of ASCII float.hex() words joined by newline, terminating newline',
        bank_source='separate from unchanged src/dsd_coeffs.h',banks={}, profiles={})
    for name,ident,native,R,P,S in PROFILES:
        fs=2*R
        L=candidate_length(P,S,fs)
        for attempt in range(64):
            h=design(L,mp.mpf(P)/fs,mp.mpf(S)/fs,False)
            ripple,stop_db=preliminary_bank_test(h,P,S,fs)
            if ripple <= 0.0001 and stop_db <= -185:
                break
            L+=4
        else:
            raise RuntimeError(f'{name}: no candidate meets preliminary limits, last length {L}: {ripple}, {stop_db}')
        sym='lsx_dsd_coeff_'+name
        header.append(f'static const double {sym}[{L}] = {{')
        for i in range(0,L,4):
            header.append('  '+', '.join(v.hex() for v in h[i:i+4])+(',' if i+4<L else ''))
        header.extend(['};',''])
        D=native//R
        banks=['halfband'] * (D.bit_length()-2)+[name]
        G=sum((57//2 if j<len(banks)-1 else L//2)*(1<<j) for j in range(len(banks)))
        meta['banks'][name]=dict(length=L,halfband=False,pass_cycles_per_input=P/fs,stop_cycles_per_input=S/fs,
            midpoint_cycles_per_input=(P+S)/(2*fs),pass_hz=P,stop_hz=S,
            input_hz=fs,group_delay_input_samples=L//2,rounded_hex_sha256=hexdigest(h),
            rounded_dc_sum_hex=float(sum(h)).hex(),preliminary_ripple_db=ripple,
            preliminary_stop_max_db=stop_db)
        meta['profiles'][ident]=dict(native_hz=native, intermediate_hz=R, pass_hz=P,stop_hz=S,
            factor=D,stage_banks=banks,delay_native_frames=G,phase_native_frames=G%D,
            discard_output_frames=G//D,stage_phases=[(G>>j)&1 for j in range(len(banks))])
    header.append('#endif /* LSX_DSD_COEFFS_V2_H */')
    outputs=[(HEADER,'\n'.join(header)+'\n'),(MANIFEST,json.dumps(meta,sort_keys=True,indent=2)+'\n')]
    if args.check:
        for path,content in outputs:
            if not path.exists() or path.read_text()!=content:
                print('MISMATCH',path,file=sys.stderr)
                return 1
        print('P15-R3 generator byte-idempotence: PASS')
    else:
        for path,content in outputs:
            path.write_text(content)
        print('P15-R3 candidate banks:',[(x['length'],x['rounded_hex_sha256']) for x in meta['banks'].values()])
    return 0

if __name__=='__main__':raise SystemExit(main())
