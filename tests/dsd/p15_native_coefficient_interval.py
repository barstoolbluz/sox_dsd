#!/usr/bin/env python3
"""Independent, directed-interval certificate of rounded native DSD FIR banks.

Bound the *ideal exact-rational* Kaiser/sinc specification directly: I0 is
represented by its positive convergent series with an explicit geometric tail,
all other operations use mpmath/MPFI-style directed interval arithmetic. For ordinary nonzero terms the real interval must fall STRICTLY between
the exact IEEE754 rounding midpoints. The historical 95-digit generator emits
a few tiny nonzero coefficients at exact-rational sinc zeros; instead of falsely
claiming strict rounding there, we prove a strict tiny absolute deviation.

This is intentionally independent of generate_coeffs.py, SciPy, and the 95-digit
production coefficient generator. This does NOT certify SoX's separate runtime
Kaiser design (effects_i_dsp.c) or FFT4G execution; those require separate work.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from mpmath import iv

ROOT=Path(__file__).resolve().parents[2]
BETA=Fraction(1102,10000)*(Fraction(190)-Fraction(87,10))
BANKS={
    'halfband':(57,Fraction(1,10),Fraction(2,5),True,'src/dsd_coeffs.h'),
    'master64_256':(117,Fraction(20000,176400),Fraction(40000,176400),False,'src/dsd_coeffs.h'),
    'master128':(153,Fraction(30000,352800),Fraction(60000,352800),False,'src/dsd_coeffs.h'),
    'wideband':(257,Fraction(1,5),Fraction(1,4),False,'src/dsd_coeffs.h'),
    'master64_v2':(153,Fraction(25000,176400),Fraction(40000,176400),False,'src/dsd_coeffs_v2.h'),
    'master128_v2':(377,Fraction(48000,352800),Fraction(60000,352800),False,'src/dsd_coeffs_v2.h'),
    'master256_v2':(325,Fraction(66000,352800),Fraction(80000,352800),False,'src/dsd_coeffs_v2.h'),
}


class CertificateError(ValueError): pass


def q(x: Fraction):
    return iv.mpf(x.numerator)/iv.mpf(x.denominator)


def rational_mpf_tuple(mpf):
    """Conversion of a *binary exact* mpf endpoint to a Python rational."""
    sign,man,exp,_=mpf
    n=-man if sign else man
    return Fraction(n<<exp) if exp>=0 else Fraction(n,1<<-exp)


def bounds(x):
    return rational_mpf_tuple(x._mpi_[0]),rational_mpf_tuple(x._mpi_[1])


def i0_interval(z, n=135):
    """I_0(z) for nonnegative z, with a mathematical upper bound for its tail.

    For a_k=(z*z/4)^k / (k!)^2, a_(k+1)/a_k=q/(k+1)^2.
    After a_(n-1), the remainder is <= a_n / (1-q_max/(n+1)^2).
    Outward interval arithmetic encloses all finite terms.
    """
    if not 40<=n<=250:
        raise CertificateError('unreviewed Bessel term count')
    lo,hi=bounds(z)
    if lo<0 or hi>Fraction(22):
        raise CertificateError('Bessel argument outside audited bound [0,22]')
    factor=z*z/4
    a=iv.mpf(1); total=iv.mpf(1)
    for k in range(1,n):
        a=a*factor/(k*k)
        total+=a
    a_n=a*factor/(n*n)
    bound_ratio=Fraction(22*22,4*(n+1)*(n+1))
    if bound_ratio>=1:
        raise CertificateError('nonconvergent certified tail bound')
    # Only the upper end gets the positive tail. Explicit interval endpoints
    # prevent incorrectly treating the neglected positive series as zero.
    tail_bound=a_n/(1-q(bound_ratio))
    return iv.mpf([total.a,(total+tail_bound).b])


def rounded_correct(interval, word):
    x=float.fromhex(word)
    if not math.isfinite(x) or x.hex()!=word or x==0 and word.startswith('-'):
        raise CertificateError('noncanonical binary64 word')
    actual=Fraction(*x.as_integer_ratio())
    low,high=bounds(interval)
    left=math.nextafter(x,-math.inf)
    right=math.nextafter(x,math.inf)
    if not all(math.isfinite(v) for v in (left,right)):
        raise CertificateError('unbounded binary64 neighbor')
    midpoint_left=(Fraction(*left.as_integer_ratio())+actual)/2
    midpoint_right=(actual+Fraction(*right.as_integer_ratio()))/2
    # Strict inequalities avoid all tie-to-even corner cases.
    return low>midpoint_left and high<midpoint_right, (low,high,actual)


def source_hex(path,bank,length):
    text=path.read_text()
    match=re.search(r'\blsx_dsd_coeff_'+re.escape(bank)+r'\[(\d+)\]\s*=\s*\{(.*?)\};',text,re.S)
    if not match or int(match.group(1))!=length:
        raise CertificateError(f'bank identity/length mismatch: {bank}')
    words=[w.strip() for w in match.group(2).split(',') if w.strip()]
    if len(words)!=length or any(not re.fullmatch(r'-?0x[0-9a-f]+\.[0-9a-f]+p[+-]\d+',w) for w in words):
        raise CertificateError(f'bad hex header: {bank}')
    return words


def certificate(precision=112, bessel_terms=135):
    if precision<90 or precision>200:
        raise CertificateError('unsupported directed interval precision')
    iv.dps=precision
    beta=q(BETA)
    denom=i0_interval(beta,bessel_terms)
    rows=[]
    for name,(n,p,s,halfband,header) in BANKS.items():
        words=source_hex(ROOT/header,name,n)
        m=(n-1)//2
        fc=q((p+s)/2)
        taps=[]
        for d in range(m+1):
            if halfband and d and d%2==0:
                taps.append(iv.mpf(0));continue
            sinc=(2*fc if d==0 else iv.sin(2*iv.pi*fc*d)/(iv.pi*d))
            window=i0_interval(beta*iv.sqrt(1-q(Fraction(2*d,n-1))**2),bessel_terms)/denom
            taps.append(sinc*window)
        if halfband:
            taps[0]=q(Fraction(1,2))
            sides=2*sum(taps[1:],iv.mpf(0))
            taps=[h if d==0 else h*q(Fraction(1,2))/sides for d,h in enumerate(taps)]
        else:
            unity=taps[0]+2*sum(taps[1:],iv.mpf(0))
            taps=[h/unity for h in taps]
        successes=0
        exceptional=[]
        max_diff=0.
        worst=None
        for k,word in enumerate(words):
            d=abs(k-m)
            possible,triplet=rounded_correct(taps[d],word)
            lo,hi,actual=triplet
            if possible:
                successes+=1
            elif max(abs(actual-lo),abs(actual-hi)) < Fraction(1,2**280):
                # The historical generator evaluated sin(integer*pi) with a
                # finite-precision pi; its tiny nonzero word is not correctly
                # rounded for mathematically exact rational zeros. We can
                # still certify its mathematical deviation without equating
                # an interval containing zero to an exact IEEE rounding.
                exceptional.append(dict(index=k,word=word,
                           max_absolute_deviation_upper=math.nextafter(
                               float(max(abs(actual-lo),abs(actual-hi))),math.inf)))
            else:
                raise CertificateError(f'{name}[{k}]: mathematical deviation unproved '+
                      word+f', interval=[{float(lo):.18g}, {float(hi):.18g}]')
            diff=max(abs(actual-lo),abs(actual-hi))
            if float(diff)>max_diff: max_diff=float(diff);worst=k
        digest=sha256(('\n'.join(words)+'\n').encode('ascii')).hexdigest()
        rows.append(dict(bank=name,header=header,sha256_header=sha256((ROOT/header).read_bytes()).hexdigest(),
                         rounded_hex_sha256=digest,length=n,taps_strictly_rounded=successes,
                         tiny_generator_artifacts=exceptional,
                         all_words_deviation_interval_certified=True,
                         max_absolute_rounding_deviation_upper=math.nextafter(max_diff,math.inf),
                         maximal_deviation_at=worst,scope='ideal exact-rational Kaiser specification'))
    return dict(schema='P15/native-bank-outward-rounding/1',status='PASS',qualified_release=False,
                method='directed 112-digit intervals, positive Bessel series, exact geometric tail, '
                       'exact rational IEEE754 midpoint test with no floating midpoint subtraction',
                precision_decimal_digits=precision,bessel_terms=bessel_terms,beta_rational=str(BETA),
                python_math='fraction+mpmath.iv (outward interval)',source_sha256={
                    str(p):sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(x[-1] for x in BANKS.values()))},
                banks=rows,limitations=('This is a native-DSD filter coefficient-rounding proof only. '
                  'SoX runtime rate.c Kaiser and FFT4G coefficient-bin generation/execution are separate obligations.'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--precision',type=int,default=112)
    p.add_argument('--bessel-terms',type=int,default=135)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=certificate(a.precision,a.bessel_terms)
    if a.output:
        if a.output.exists():
            if json.loads(a.output.read_text())!=result:
                raise CertificateError('existing proof receipt disagrees; refusing overwrite')
        else:
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print('native exact Kaiser rounding:',len(result['banks']),'banks,',
          sum(i['taps_strictly_rounded'] for i in result['banks']),'strict rounded; ',
          sum(len(i['tiny_generator_artifacts']) for i in result['banks']),'bounded tiny artifacts')

if __name__=='__main__':main()
