#!/usr/bin/env python3
"""Interval-bounded trigonometric responses for P15 SRC transfer certificates.

This module is an *independent mathematical checker*, not an SRC model.  It
certifies continuous-frequency magnitude bounds on a finite coefficient
witness, including a conservative coherent sum over provided alias families.
It does not assert that the supplied witness represents src/rate.c.  That
separate source/coefficients/phase/finite-support binding remains essential.

Uses mpmath interval arithmetic for directed-rounded complex midpoint values
and derivatives.  A Taylor remainder bounds *every* frequency between tested
points; a dense FFT or scalar optimizer alone would not.  Resource exhaustion,
missing alias families, and absent source binding are OPEN, never PASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math

from mpmath import iv

iv.dps = 75
ORDER = 8


class BadWitness(ValueError):
    pass


def fraction(value) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float) and not math.isfinite(value):
        raise BadWitness('nonfinite frequency')
    return Fraction(str(value))


def scalar(n: Fraction):
    return iv.mpf(n.numerator) / iv.mpf(n.denominator)


def upper(x) -> float:
    # For diagnostics only: round outwards when converting to binary64.
    return math.nextafter(float(x.b), math.inf)


def lower(x) -> float:
    return math.nextafter(float(x.a), -math.inf)


def is_below(a, b) -> bool:
    return bool(a.b < b.a)


def is_above(a, b) -> bool:
    return bool(a.a > b.b)


@dataclass(frozen=True)
class TrigPoly:
    """Finite real binary64 response sum h[k] exp(2*pi*i*k*f).

    Hex literal coefficients are required: no decimal re-rounding and no
    gain/cancellation accidentally introduced by a parser.  Negative tap
    positions and phase-centering are valid.  Frequency uses input cycles.
    """
    taps: tuple[tuple[int, float], ...]
    center: Fraction

    @classmethod
    def from_hex(cls, taps: dict[int, str], *, center=0):
        if not taps or len(taps) > 200000:
            raise BadWitness('empty or oversized coefficient witness')
        c = fraction(center)
        if abs(c) > 10000000:
            raise BadWitness('unbounded phase origin')
        accepted = []
        for k, v in taps.items():
            if type(k) is not int or abs(k) > 10000000 or not isinstance(v, str):
                raise BadWitness('invalid tap identity')
            try:
                x = float.fromhex(v)
            except (ValueError, OverflowError) as exc:
                raise BadWitness('invalid hexadecimal coefficient') from exc
            if not math.isfinite(x) or x.hex().lower() != v.lower() or x == 0.0 and v.startswith('-'):
                raise BadWitness('noncanonical/nonfinite coefficient')
            accepted.append((k, x))
        return cls(tuple(sorted(accepted)), c)


def magnitude_bounds(poly: TrigPoly, lo: Fraction, hi: Fraction, order=ORDER):
    """Rigorous bound on |H(f)| over inclusive [lo,hi].

    Uses the Taylor polynomial at the midpoint and an absolute, *global*
    derivative remainder.  Interval evaluations include argument reduction,
    coefficient multiplication and derivative accumulation rounding.
    """
    if not 1 <= order <= 12 or not Fraction(0) <= lo <= hi <= Fraction(1, 2):
        raise BadWitness('invalid interval/order')
    midpoint = (lo + hi) / 2
    radius = (hi - lo) / 2
    p = scalar(midpoint)
    r = scalar(radius)
    two_pi = 2 * iv.pi
    re = [iv.mpf(0) for _ in range(order + 1)]
    im = [iv.mpf(0) for _ in range(order + 1)]
    rem = iv.mpf(0)
    for k, coefficient in poly.taps:
        shifted = scalar(Fraction(k) - poly.center)
        t = two_pi * shifted
        phase = t * p
        z_re = iv.mpf(coefficient) * iv.cos(phase)
        z_im = iv.mpf(coefficient) * iv.sin(phase)
        power = iv.mpf(1)
        for j in range(order + 1):
            rotate = j % 4
            if rotate == 0:
                re[j] += power*z_re; im[j] += power*z_im
            elif rotate == 1:
                re[j] -= power*z_im; im[j] += power*z_re
            elif rotate == 2:
                re[j] -= power*z_re; im[j] -= power*z_im
            else:
                re[j] += power*z_im; im[j] -= power*z_re
            power *= t
        rem += iv.fabs(iv.mpf(coefficient)) * ((iv.fabs(t) * r) ** (order+1))
    rem /= math.factorial(order+1)
    center_mag = iv.sqrt(re[0]**2 + im[0]**2)
    variation = rem
    for j in range(1, order + 1):
        variation += iv.sqrt(re[j]**2+im[j]**2) * r**j / math.factorial(j)
    # Calculate using interval endpoints (not rounded display floats).
    low = center_mag.a - variation.b
    high = center_mag.b + variation.b
    return low, high, center_mag


def certify(polynomials: tuple[TrigPoly, ...], low, high, *,
            amplitude_max=None, amplitude_min=None,
            max_nodes=16384, order=ORDER) -> dict:
    """Certify a continuous interval or conservative coherent alias sum.

    For coherent alias checks, each polynomial must already identify a
    distinct unwanted transfer family.  The checked quantity is sum |H_k|,
    NOT rms/quadrature or a sampled frequency-bin average.

    A low/high band must be fully within [0,0.5] input cycles.  PASS only
    when each subinterval has interval-proven safe bounds; FAIL only when a
    witnessed *center* is provably outside.  Other cases are OPEN.
    """
    a, b = fraction(low), fraction(high)
    if not 0 <= a <= b <= Fraction(1, 2) or not polynomials or max_nodes < 1:
        raise BadWitness('invalid frequency band or empty alias population')
    if amplitude_min is None and amplitude_max is None:
        raise BadWitness('no acceptance envelope')
    if amplitude_min is not None and len(polynomials) != 1:
        raise BadWitness('a coherent alias sum cannot have a passband lower limit')
    min_ref = None if amplitude_min is None else iv.mpf(str(amplitude_min))
    max_ref = None if amplitude_max is None else iv.mpf(str(amplitude_max))
    if ((min_ref is not None and not is_above(min_ref, iv.mpf(0))) or
        (max_ref is not None and not is_above(max_ref, iv.mpf(0)))):
        raise BadWitness('envelope must be strictly positive')
    if min_ref is not None and max_ref is not None and not is_below(min_ref, max_ref):
        raise BadWitness('inverted envelope')
    pending = [(a, b)]
    complete = 0
    max_seen = 0.0
    min_seen = math.inf
    deepest = 0
    while pending:
        if complete + len(pending) > max_nodes:
            return dict(status='OPEN', reason='subdivision_budget_exhausted',
                        intervals_proven=complete, pending=len(pending),
                        maximum_upper_amplitude=max_seen, minimum_lower_amplitude=min_seen)
        l, h = pending.pop()
        n = sum_bounds = center_sum = None
        sum_bounds = iv.mpf(0); center_sum = iv.mpf(0)
        lows = []
        for poly in polynomials:
            low_mag, high_mag, center_mag = magnitude_bounds(poly, l, h, order)
            sum_bounds += high_mag.b
            center_sum += center_mag
            lows.append(low_mag)
        low_sum = lows[0] if len(lows) == 1 else iv.mpf(0)
        if max_ref is not None and is_above(center_sum, max_ref):
            return dict(status='FAIL', reason='center_witness_exceeds_max',
                        witness_hz_fraction=str((l+h)/2),
                        witness_lower_amplitude=lower(center_sum),
                        intervals_proven=complete)
        if min_ref is not None and is_below(center_sum, min_ref):
            return dict(status='FAIL', reason='center_witness_below_min',
                        witness_hz_fraction=str((l+h)/2),
                        witness_upper_amplitude=upper(center_sum),
                        intervals_proven=complete)
        safe_upper = max_ref is None or is_below(sum_bounds, max_ref)
        safe_lower = min_ref is None or is_above(low_sum, min_ref)
        if safe_upper and safe_lower:
            complete += 1
            max_seen = max(max_seen, upper(sum_bounds))
            min_seen = min(min_seen, lower(low_sum))
        elif l == h:
            return dict(status='OPEN', reason='insufficient_interval_precision',
                        intervals_proven=complete)
        else:
            mid=(l+h)/2
            pending.extend(((l, mid), (mid, h)))
            deepest=max(deepest, mid.denominator.bit_length())
    return dict(status='PASS', intervals_proven=complete,
                maximum_upper_amplitude=max_seen,
                minimum_lower_amplitude=min_seen if len(polynomials)==1 else None,
                splitting_precision_bits=deepest,
                method='75-digit outward interval Taylor with exact binary64 tap identity',
                witness_scope='finite response witness ONLY; source binding separately mandatory')


def _exact_interval_string(value):
    """Serialize finite dyadic endpoints exactly, preserving the full interval.

    mpmath's display strings and binary64 diagnostics are not policy bounds.
    A dyadic m*2**(-k) has the exact decimal form (m*5**k)/10**k.
    """
    def endpoint(raw):
        sign, mantissa, exponent, bits = raw
        if bits < 0:
            raise BadWitness('nonfinite acceptance endpoint')
        if exponent >= 0:
            digits = str(mantissa << exponent)
        else:
            places = -exponent
            digits = str(mantissa * 5**places).zfill(places + 1)
            digits = digits[:-places] + '.' + digits[-places:]
        return ('-' if sign else '') + digits
    return '[' + endpoint(value._mpi_[0]) + ', ' + endpoint(value._mpi_[1]) + ']'


def db_band(ripple_db: str = '0.0001'):
    """Enclose the exact linear policy limits without changing their direction.

    Keep both endpoints: PASS compares against the inward endpoints, while a
    generic center-witness FAIL must lie outside the outward endpoints.
    """
    db=iv.mpf(ripple_db)
    gain=iv.exp(iv.ln(iv.mpf(10)) * db / 20)
    return _exact_interval_string(1/gain), _exact_interval_string(gain)


if __name__ == '__main__':
    raise SystemExit('Library only; see test_p15_src_continuum_bounds.py. '
                     'No autonomous PASS without an independently source-bound SRC operator.')
