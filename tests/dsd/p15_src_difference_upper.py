#!/usr/bin/env python3
"""Exact-coefficient finite-difference majorant for FIR high-frequency aliases.

If H(z) = sum_k c[k] z**k, then (1-z)**p H(z) has integer-
coefficient convolution (1,-1)**p * c. For |z|=1 its modulus is
bounded by the exact L1 of that convolution. Since |1-e^(2*pi*i*x)|
=2*sin(pi*x), 0 < x <= 1/2, an outward upper majorant for the WHOLE
interval [a,b] is sum(abs(diff_p(c))) / (2*sin(pi*a))**p.
No source tap is truncated or rounded; every input float is decoded as its
exact binary64 rational. This is a valid upper, NOT a lower bound.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import math
from mpmath import iv
from p15_src_continuum_bounds import TrigPoly,scalar,BadWitness

iv.dps=75

@lru_cache(maxsize=128)
def difference_moments(poly:TrigPoly):
    if not poly.taps or len(poly.taps)>100000:
        return None
    pairs=sorted(poly.taps)
    if (any(type(k) is not int or not math.isfinite(value) for k,value in pairs)
            or any(pairs[i-1][0]==pairs[i][0] for i in range(1,len(pairs)))):
        raise BadWitness('invalid tap identity for finite-difference majorant')
    span=pairs[-1][0]-pairs[0][0]+1
    if span>131072 or span<len(pairs):
        return None  # Numerically expensive sparse witnesses use prior prover.
    rational=[(value.as_integer_ratio(),k) for k,value in pairs]
    denominator=max(d for (n,d),k in rational)
    arr=[0]*span
    for (n,d),k in rational:
        arr[k-pairs[0][0]]=n*(denominator//d)
    moments=[]
    # The zero-padded coefficient extension is REQUIRED at both endpoints.
    for power in range(1,7):
        arr=[arr[0]]+[arr[i]-arr[i-1] for i in range(1,len(arr))]+[-arr[-1]]
        if power in (2,4,6):
            moments.append((power,Fraction(sum(abs(v) for v in arr),denominator)))
    return tuple(moments)


def difference_upper(poly:TrigPoly,lo:Fraction,hi:Fraction):
    """Outward upper bound for |H(x)| on [lo,hi], or None if unusable.

    The 75-digit directed sine interval is evaluated at the left endpoint;
    sin(pi*x) increases on [0,1/2]. A returned upper needs no sampling,
    spectral phase assumption, or frequency cut-off.
    """
    if not Fraction(0)<=lo<=hi<=Fraction(1,2):
        raise BadWitness('invalid normalized frequency for difference bound')
    if lo==0:
        return None
    moments=difference_moments(poly)
    if moments is None:
        return None
    denom=(2*iv.sin(iv.pi*scalar(lo))).a
    if not bool(denom>0):
        return None
    best=None
    for power,moment in moments:
        upper=(scalar(moment)/(denom**power)).b
        if best is None or bool(upper<best):
            best=upper
    return best
