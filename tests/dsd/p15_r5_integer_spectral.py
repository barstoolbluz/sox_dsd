#!/usr/bin/env python3
"""Independent exact-integer/Fraction continuous FIR interval checker.

No mpmath, numpy, libm, float arithmetic, or third-party transcendental code
participates in constructing the result. A certified bound is for ONE source-
selected finite binary64 FIR (not a P15 composite alias proof). Every tap is
included and all signs/cancellations are retained at the Taylor midpoint.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache
from math import factorial, isqrt
import math

from p15_r5_exact_trig import GRID, GRID_BITS, TrigRefusal, pi_interval, sincos


class IntervalRefusal(ValueError):
    pass


def ceil_f(q: F) -> int:
    return -((-q.numerator) // q.denominator)


def mul(a:tuple[int,int], b:tuple[int,int]) -> tuple[int,int]:
    values=(a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1])
    return min(values)//GRID, ceil_f(F(max(values),GRID))


def add(a:tuple[int,int],b:tuple[int,int]) -> tuple[int,int]:
    return a[0]+b[0],a[1]+b[1]


def neg(a):return -a[1],-a[0]


def ratio(a:tuple[int,int],q:F)->tuple[int,int]:
    if q<0:
        a=neg(a);q=-q
    return (a[0]*q.numerator)//q.denominator,ceil_f(F(a[1]*q.numerator,q.denominator))


def pi2():
    a,b=pi_interval()
    return 2*(a*GRID).numerator//(a*GRID).denominator,ceil_f(2*b*GRID)


def maxabs(a):return max(abs(a[0]),abs(a[1]))


def minabs(a):return 0 if a[0]<=0<=a[1] else min(abs(a[0]),abs(a[1]))


def magnitude_upper(re,im):
    r=maxabs(re)**2+maxabs(im)**2
    floor=isqrt(r)
    return floor if floor*floor==r else floor+1


def magnitude_lower(re,im):
    return isqrt(minabs(re)**2+minabs(im)**2)


@dataclass(frozen=True)
class FIRCertificate:
    low_integer: int
    high_integer: int
    grid_bits: int
    tap_count: int
    order: int
    interval_start: str
    interval_end: str
    center_enclosure: tuple[int,int]
    total_derivative_variation: int
    remainder_variation: int
    trusted_primitive: str = 'exact integer arithmetic + Machin/alternating arctan + Taylor/Lagrange'

    def lower(self):return F(self.low_integer,GRID)
    def upper(self):return F(self.high_integer,GRID)


def certify_fir(taps:tuple[tuple[int,float],...], lo:F,hi:F,
                *,center:F=F(0),order:int=8)->FIRCertificate:
    """Sound interval for |sum_k h[k] exp(2pi i (k-center)f)| for all f in [lo,hi].

    By complex Taylor with global real-variable remainder:
    |H(f)-H(m)| <= sum_j |H^(j)(m)| r^j/j! +
        (2pi*r)^p/p! sum_k |h_k| |k-center|^p, p=order+1.
    Each H^(j)(m) enclosed using outward dyadic arithmetic. Integer sqrt
    bounds replace any dependency on floating sqrt. Cancellation is honored
    in the midpoint derivative sums, not in the uniform L1 remainder.
    """
    if (type(lo) is not F or type(hi) is not F or type(center) is not F or
        not F(0)<=lo<=hi<=F(1,2) or not 1<=order<=14 or
        not 1<=len(taps)<=10000):
        raise IntervalRefusal('unsupported range / Taylor order / input')
    if len({k for k,_ in taps})!=len(taps) or any(type(k) is not int or abs(k)>10**8 or type(h) is not float or not math.isfinite(h) for k,h in taps):
        raise IntervalRefusal('malformed FIR taps')
    m=(lo+hi)/2;r=(hi-lo)/2
    derivatives=[((0,0),(0,0)) for _ in range(order+1)]
    pi=pi2()
    p=order+1
    moment=F(0)
    for k,h in taps:
        u=F(k)-center
        coeff=F.from_float(h)
        moment+=abs(coeff)*abs(u)**p
        s,c=sincos(u*m)
        re=ratio(c,coeff)
        im=ratio(s,coeff)
        freq=ratio(pi,u)
        for j in range(order+1):
            re0,im0=derivatives[j]
            derivatives[j]=(add(re0,re),add(im0,im))
            if j<order:
                re,im=neg(mul(im,freq)),mul(re,freq)
    c_re,c_im=derivatives[0]
    central_lo=magnitude_lower(c_re,c_im)
    central_hi=magnitude_upper(c_re,c_im)
    delta=0
    for j in range(1,order+1):
        re,im=derivatives[j]
        delta+=ceil_f(F(magnitude_upper(re,im))*r**j/factorial(j))
    # pi[1]/GRID is a rational upper bound for 2pi.
    global_remainder=moment*(F(pi[1],GRID)*r)**p/factorial(p)
    remainder=ceil_f(global_remainder*GRID)
    variation=delta+remainder
    return FIRCertificate(max(0,central_lo-variation),central_hi+variation,
                          GRID_BITS,len(taps),order,str(lo),str(hi),
                          (central_lo,central_hi),delta,remainder)
