#!/usr/bin/env python3
"""Validated real cosine Taylor enclosure for exactly even source FIRs.

This is an optional numerical fast path; a non-even witness uses the
independent general complex evaluator. All identities are checked from the
actual binary64 tap values before using symmetry. No approximate equality,
truncation, or cancellation-based alias exclusion is allowed.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import math

from mpmath import iv
from p15_src_continuum_bounds import TrigPoly, BadWitness, scalar

iv.dps = 75


@lru_cache(maxsize=128)
def even_taps(poly: TrigPoly):
    """Return (central coefficient, positive taps) iff H has exact real parity.

    Zero coefficients may be unpaired. Negative zero is also exactly zero;
    signs of zero cannot influence the mathematical FIR response.
    """
    if poly.center != 0 or not poly.taps:
        return None
    taps = dict(poly.taps)
    if len(taps) != len(poly.taps):
        return None
    for k, value in poly.taps:
        if not isinstance(k, int) or not math.isfinite(value):
            return None
        if value and taps.get(-k) != value:
            return None
    return taps.get(0, 0.0), tuple((k, value) for k, value in poly.taps
                                      if k > 0 and value != 0)


@lru_cache(maxsize=128)
def _absolute_moment(poly: TrigPoly, order: int) -> Fraction:
    """Exact moment of the signed binary64 coefficient witness.

    Both members of each nonzero symmetric pair contribute. The order is
    fixed and small (<=12). The moment is frequency-independent and can be
    safely reused across subdivisions of the same source stage.
    """
    symmetrical = even_taps(poly)
    if symmetrical is None:
        raise BadWitness('non-even response has no real-cosine moment')
    return sum((2 * abs(Fraction.from_float(value)) * k**order
                for k, value in symmetrical[1]), Fraction(0))


def symmetric_magnitude_bounds(poly: TrigPoly, lo: Fraction, hi: Fraction,
                               order: int = 8):
    """Outward interval bound on |H(f)| for every f in closed [lo,hi].

    For the exact even FIR, H(f) = h[0] + 2 sum_{k>0} h[k] cos(2*pi*k*f)
    is REAL. Taylor coefficients and a global absolute derivative remainder
    enclose H uniformly. All endpoint operations, including trig, use
    directed 75-digit mpmath intervals. The independent complex evaluator
    remains available to check this reduction.
    """
    if not 1 <= order <= 12 or not Fraction(0) <= lo <= hi <= Fraction(1, 2):
        raise BadWitness('invalid interval/order')
    symmetrical = even_taps(poly)
    if symmetrical is None:
        raise BadWitness('non-even source coefficient witness')
    central, pairs = symmetrical
    theta = 2 * iv.pi * scalar((lo + hi) / 2)
    radius = scalar((hi - lo) / 2)
    two_pi = 2 * iv.pi
    derivative = [iv.mpf(0) for _ in range(order + 1)]
    derivative[0] += iv.mpf(central)

    previous = None
    since_anchor = 0
    zr = zi = None
    rotations = {}
    for k, coefficient in pairs:
        if previous is None or since_anchor == 48:
            angle = theta * k
            zr, zi = iv.cos(angle), iv.sin(angle)
            since_anchor = 0
        else:
            step = k - previous
            if step <= 0:
                raise BadWitness('unordered real cosine witness')
            if step not in rotations:
                angle = theta * step
                rotations[step] = (iv.cos(angle), iv.sin(angle))
            cr, ci = rotations[step]
            zr, zi = zr*cr - zi*ci, zr*ci + zi*cr
            since_anchor += 1
        previous = k
        coeff = 2 * iv.mpf(coefficient)
        power = iv.mpf(1)
        t = two_pi * k
        for j in range(order + 1):
            signed = (zr if j % 2 == 0 else zi) * (-1 if j % 4 in (1, 2) else 1)
            derivative[j] += coeff * power * signed
            power *= t

    # The exact moment includes every coefficient: no omitted tap term, even
    # when a response vanishes by cancellation at the midpoint.
    rem = (scalar(_absolute_moment(poly, order + 1)) *
           (two_pi * radius)**(order + 1) / math.factorial(order + 1))
    variation = rem.b
    for j in range(1, order + 1):
        variation += (iv.fabs(derivative[j]).b * radius**j /
                      math.factorial(j)).b
    center = iv.fabs(derivative[0])
    return center.a - variation.b, center.b + variation.b, center
