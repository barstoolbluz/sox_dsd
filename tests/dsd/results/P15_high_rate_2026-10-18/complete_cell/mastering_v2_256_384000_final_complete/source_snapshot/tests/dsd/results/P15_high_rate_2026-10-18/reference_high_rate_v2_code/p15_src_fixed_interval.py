#!/usr/bin/env python3
"""Rigorous fixed-point Taylor evaluation of exact even binary64 FIRs.

Python integers perform all recurrence, moment, and interval accumulation
operations exactly. Trigonometric anchor intervals are provided by mpmath.iv
at >=75 decimal digits, then widened to an enclosing dyadic grid. No binary64
cosine, FFT, or heuristic forward-error assumption enters the certificate.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import math

from mpmath import iv
from p15_src_continuum_bounds import TrigPoly, BadWitness, scalar
from p15_src_symmetric_interval import even_taps, _absolute_moment

iv.dps = 75
_BITS = 288             # dyadic grid finer than the 75-digit IV anchors
_Q = 1 << _BITS


def _ceil_div(num: int, den: int) -> int:
    return -((-num) // den)


def _mpf_dyadic(raw: tuple, *, up: bool):
    """Round one exact mpmath endpoint to our integer grid, outward."""
    sign, mantissa, exponent, _bits = raw
    if (not isinstance(mantissa, int) or not isinstance(exponent, int) or
        _bits < 0 or sign not in (0, 1) or mantissa < 0):
        raise BadWitness('nonfinite multiprecision interval endpoint')
    num = -mantissa if sign else mantissa
    exponent += _BITS
    if exponent >= 0:
        return num << exponent
    divisor = 1 << (-exponent)
    return _ceil_div(num, divisor) if up else num // divisor


def _from_iv(value):
    a, b = value._mpi_
    return _mpf_dyadic(a, up=False), _mpf_dyadic(b, up=True)


def _add(a, b):
    return a[0] + b[0], a[1] + b[1]


def _neg(a):
    return -a[1], -a[0]


def _mul(a, b):
    products = (a[0]*b[0], a[0]*b[1], a[1]*b[0], a[1]*b[1])
    return min(products) // _Q, _ceil_div(max(products), _Q)


def _mul_positive(a, b):
    if a[0] < 0 or b[0] < 0:
        raise BadWitness('positive-factor optimization given signed interval')
    return a[0]*b[0] // _Q, _ceil_div(a[1]*b[1], _Q)


def _multiply_exact_coefficient(x, coefficient: float):
    numerator, denominator = coefficient.as_integer_ratio()  # exact binary64
    if numerator < 0:
        x = _neg(x)
        numerator = -numerator
    return (x[0]*numerator // denominator,
            _ceil_div(x[1]*numerator, denominator))


@lru_cache(maxsize=48)
def _derivative_weights(poly: TrigPoly, order: int):
    """Precompute the exact per-tap, frequency-independent FIR derivative.

    Returns (k, ((numerator, denominator), ...)) where weight j is exactly
    2*binary64_coefficient*k**j. All values are integers, with no floating
    evaluation or rounding. Reuse across subdivisions never changes a bound.
    """
    symmetry = even_taps(poly)
    if symmetry is None:
        raise BadWitness('derivative weight requested for non-even FIR')
    rows=[]
    for k,c in symmetry[1]:
        coeff=2*Fraction.from_float(c)
        power=1
        values=[]
        for j in range(order+1):
            w=coeff*power
            values.append((w.numerator,w.denominator))
            power*=k
        rows.append((k,tuple(values)))
    return tuple(rows)


def _multiply_ratio(x, numerator: int, denominator: int):
    """Multiply a signed outward dyadic interval by an EXACT rational."""
    if denominator<=0:
        raise BadWitness('invalid exact rational weight')
    if numerator<0:
        x=_neg(x)
        numerator=-numerator
    return (x[0]*numerator // denominator,
            _ceil_div(x[1]*numerator, denominator))


def _as_iv(lower: int, upper: int):
    return iv.mpf([scalar(Fraction(lower, _Q)).a,
                   scalar(Fraction(upper, _Q)).b])


def fixed_symmetric_magnitude_bounds(poly: TrigPoly, lo: Fraction,
                                     hi: Fraction, order: int = 8):
    """Uniform directed enclosure using a real Taylor series at the midpoint.

    For an even real coefficient sequence, H(x) is real. The signed Taylor
    coefficients are enclosed on a dyadic grid by exact integer interval
    operations, with outward rounding after multiplication. The remainder
    is bounded by the exact (order+1) binary64 absolute coefficient moment.
    """
    if not 1 <= order <= 12 or not Fraction(0) <= lo <= hi <= Fraction(1, 2):
        raise BadWitness('invalid frequency/order for fixed symmetric bound')
    symmetrical = even_taps(poly)
    if symmetrical is None:
        raise BadWitness('non-even finite FIR')
    central, pairs = symmetrical
    midpoint = (lo + hi) / 2
    radius = (hi - lo) / 2
    two_pi_iv = 2 * iv.pi
    theta = two_pi_iv * scalar(midpoint)
    two_pi = _from_iv(two_pi_iv)
    d = [(0, 0) for _ in range(order + 1)]
    d[0] = _multiply_exact_coefficient((_Q, _Q), central)
    previous = None
    since_anchor = 0
    zr = zi = None
    rotations = {}
    # The exact coefficient and integer k powers have no midpoint dependence.
    # In contrast, the shared 2*pi powers are outward dyadic enclosures.
    two_pi_powers=[(_Q,_Q)]
    for j in range(order):
        two_pi_powers.append(_mul_positive(two_pi_powers[-1],two_pi))
    for k, weights in _derivative_weights(poly,order):
        if previous is None or since_anchor == 48:
            angle = theta * k
            zr, zi = _from_iv(iv.cos(angle)), _from_iv(iv.sin(angle))
            since_anchor = 0
        else:
            step = k - previous
            if step <= 0:
                raise BadWitness('unsorted coefficient position')
            if step not in rotations:
                angle = theta * step
                rotations[step] = (_from_iv(iv.cos(angle)),
                                   _from_iv(iv.sin(angle)))
            cr, ci = rotations[step]
            oldr, oldi = zr, zi
            zr = _add(_mul(oldr, cr), _neg(_mul(oldi, ci)))
            zi = _add(_mul(oldr, ci), _mul(oldi, cr))
            since_anchor += 1
        previous = k
        for j, (num,den) in enumerate(weights):
            component = _mul(two_pi_powers[j],zr if j%2==0 else zi)
            term = _multiply_ratio(component,num,den)
            if j % 4 in (1, 2):
                term = _neg(term)
            d[j] = _add(d[j], term)

    variation = 0
    for j in range(1, order + 1):
        numerator = max(abs(d[j][0]), abs(d[j][1])) * radius.numerator**j
        denominator = radius.denominator**j * math.factorial(j)
        variation += _ceil_div(numerator, denominator)
    p = order + 1
    moment = _absolute_moment(poly, p)
    mnum, mden = moment.numerator, moment.denominator
    variation += _ceil_div(mnum * two_pi[1]**p * radius.numerator**p,
                           mden * (_Q**(p-1)) * radius.denominator**p * math.factorial(p))

    dmin, dmax = d[0]
    center_upper = max(abs(dmin), abs(dmax))
    center_lower = (dmin if dmin >= 0 else -dmax if dmax <= 0 else 0)
    low = scalar(Fraction(center_lower-variation, _Q)).a
    high = scalar(Fraction(center_upper+variation, _Q)).b
    center = _as_iv(center_lower, center_upper)
    return low, high, center
