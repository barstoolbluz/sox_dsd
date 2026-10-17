#!/usr/bin/env python3
"""Directed-interval Fourier/Taylor evaluation with exact phase-step recurrence.

Unlike a sampled FFT this computes a continuum inclusion bound.  Replacing a
trigonometric call per tap with one outward-rounded complex rotation per tap
preserves enclosures (rounding widens the intervals) and avoids thousands of
expensive argument reductions in rational SRC branches.  The original direct
interval implementation remains an independent cross-check.
"""
from __future__ import annotations
from fractions import Fraction
import math
from mpmath import iv
from p15_src_continuum_bounds import TrigPoly,BadWitness,scalar

iv.dps=75


def magnitude_bounds(poly: TrigPoly,lo:Fraction,hi:Fraction,order=8):
    if not 1 <= order <= 12 or not Fraction(0)<=lo<=hi<=Fraction(1,2) or not poly.taps:
        raise BadWitness('invalid interval/order/coefficient witness')
    theta=2*iv.pi*scalar((lo+hi)/2)
    radius=scalar((hi-lo)/2)
    re=[iv.mpf(0) for _ in range(order+1)]
    im=[iv.mpf(0) for _ in range(order+1)]
    remainder=iv.mpf(0)
    delta_rot={}
    previous=None
    since_anchor=0
    z_re=z_im=None
    two_pi=2*iv.pi
    for k,coef in poly.taps:
        # Re-anchor before independent real/imaginary interval widths can
        # grow geometrically through interval complex rotations. 48 steps
        # keeps the amplification < 2**48 even at 45-degree rotations.
        if previous is None or since_anchor == 48:
            initial=theta*scalar(Fraction(k)-poly.center)
            z_re,z_im=iv.cos(initial),iv.sin(initial)
            since_anchor=0
        else:
            delta=k-previous
            if delta<=0:
                raise BadWitness('unsorted/duplicate coefficient positions')
            if delta not in delta_rot:
                phase=theta*delta
                delta_rot[delta]=(iv.cos(phase),iv.sin(phase))
            cr,ci=delta_rot[delta]
            z_re,z_im=z_re*cr-z_im*ci,z_re*ci+z_im*cr
            since_anchor+=1
        previous=k
        c=iv.mpf(coef)
        zc_re,zc_im=c*z_re,c*z_im
        t=two_pi*scalar(Fraction(k)-poly.center)
        power=iv.mpf(1)
        for j in range(order+1):
            if j%4==0:
                re[j]+=power*zc_re;im[j]+=power*zc_im
            elif j%4==1:
                re[j]-=power*zc_im;im[j]+=power*zc_re
            elif j%4==2:
                re[j]-=power*zc_re;im[j]-=power*zc_im
            else:
                re[j]+=power*zc_im;im[j]-=power*zc_re
            power*=t
        remainder+=iv.fabs(c)*(iv.fabs(t)*radius)**(order+1)
    remainder/=math.factorial(order+1)
    center=iv.sqrt(re[0]**2+im[0]**2)
    variation=remainder
    for j in range(1,order+1):
        variation+=iv.sqrt(re[j]**2+im[j]**2)*radius**j/math.factorial(j)
    return center.a-variation.b,center.b+variation.b,center
