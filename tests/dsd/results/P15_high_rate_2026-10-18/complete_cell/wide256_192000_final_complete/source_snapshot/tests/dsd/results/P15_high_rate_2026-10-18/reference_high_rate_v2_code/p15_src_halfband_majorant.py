#!/usr/bin/env python3
"""Rigorous complete alias-pair norm for exact centered halfband FIRs.

For a real, even FIR with h[0] = 1/2 and every other nonzero tap at an odd
index, write H(x) = 1/2 + Q(x).  Then Q is real and
H(x + 1/2) = 1/2 - Q(x), exactly.  Consequently

  |H(x)| + |H(x + 1/2)| = 2 max(1/2, |Q(x)|).

This bounds the SUM OF MAGNITUDES of both inverse-decimation branches; it
does not assume their phases cancel and does not omit either alias.  Q's
symmetries reduce its global absolute maximum to [0, 1/4].  The existing
outward-rounded Taylor evaluator covers that ENTIRE interval before this
module returns a bound.  Resource exhaustion or a different coefficient
pattern returns None, so callers retain their previous exact L1 majorant.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
import math

from mpmath import iv

from p15_src_continuum_bounds import TrigPoly, scalar
from p15_src_fixed_interval import fixed_symmetric_magnitude_bounds


iv.dps = 75
_TARGET = Fraction(50000001, 100000000)  # A cost guard, never a spectral tolerance.
_MAX_NODES = 256
_MAX_TAPS = 4096


@dataclass(frozen=True, slots=True)
class HalfbandMajorant:
    upper: object
    odd_upper: object
    nodes_examined: int
    covered_intervals: tuple[tuple[Fraction, Fraction], ...]
    coefficient_sha256: str
    precision_decimal_digits: int


def _valid_taps(taps):
    """Recognize the exact algebraic identity; approximate equality is unsafe."""
    if not taps or len(taps) > _MAX_TAPS:
        return False
    if any(type(k) is not int or type(v) is not float or not math.isfinite(v)
           for k, v in taps):
        return False
    coefficients = dict(taps)
    if len(coefficients) != len(taps) or coefficients.get(0) != 0.5:
        return False
    for k, value in taps:
        if value and k:
            if not k % 2 or coefficients.get(-k) != value:
                return False
    return True


def _certify_taps(taps, *, max_nodes=_MAX_NODES):
    """Prove a complete normalized-frequency cover or decline the shortcut."""
    if not _valid_taps(taps) or not 1 <= max_nodes <= _MAX_NODES:
        return None
    # The dyadic engine uses directed 75-digit transcendental anchors.  The
    # exact tap tuple, not a nominal bank name or source clock, is the cache
    # identity and mathematical input.  Sorting changes no coefficient.
    if iv.dps < 75:
        return None
    taps = tuple(sorted(taps))
    odd_taps = tuple((k, v) for k, v in taps if k and v)
    # Q = 0 is admissible and needs no trigonometric evaluation.
    poly = TrigPoly(odd_taps or ((0, 0.0),), Fraction(0))
    target = scalar(_TARGET).a
    pending = [(Fraction(0), Fraction(1, 4))]
    covered = []
    nodes = 0
    largest = iv.mpf(0)
    while pending:
        if nodes >= max_nodes:
            return None
        lo, hi = pending.pop()
        nodes += 1
        _lower, upper, _center = fixed_symmetric_magnitude_bounds(poly, lo, hi)
        if bool(upper.b < target):
            covered.append((lo, hi))
            if bool(upper.b > largest):
                largest = upper.b
        else:
            middle = (lo + hi) / 2
            pending.extend(((lo, middle), (middle, hi)))
    result = (2 * largest).b
    if bool(result < 1):
        result = iv.mpf(1)
    coefficient_identity = json.dumps(
        [[k, value.hex()] for k, value in taps], separators=(",", ":"))
    return HalfbandMajorant(
        upper=result, odd_upper=largest, nodes_examined=nodes,
        covered_intervals=tuple(sorted(covered)),
        coefficient_sha256=sha256(coefficient_identity.encode("ascii")).hexdigest(),
        precision_decimal_digits=iv.dps)


@lru_cache(maxsize=16)
def _cached_taps(tap_words, precision_decimal_digits):
    # Include precision in the cache identity.  A result at a different
    # directed precision is still valid, but should not receive false metadata.
    # Hexadecimal words distinguish signed zeros, unlike Python float equality.
    taps = tuple((k, float.fromhex(word)) for k, word in tap_words)
    return _certify_taps(taps)


def halfband_majorant(stage):
    """Return the immutable proof record for an admissible 2:1 FIR stage."""
    if (stage.L != 1 or stage.M != 2 or type(stage.input_hz) is not int or
            stage.input_hz <= 0 or
            stage.output_hz != Fraction(stage.input_hz, 2)):
        return None
    taps = tuple(stage.taps)
    # Validate BEFORE lookup: equal-valued non-float coefficients must not hit
    # a valid float key and bypass the exact captured-binary64 precondition.
    if not _valid_taps(taps):
        return None
    tap_words = tuple((k, value.hex()) for k, value in sorted(taps))
    return _cached_taps(tap_words, iv.dps)


def halfband_alias_sum_upper(stage):
    """Return a directed point upper for BOTH aliases, or None if unproved."""
    proof = halfband_majorant(stage)
    return None if proof is None else proof.upper


def halfband_majorant_info(stage):
    """JSON-compatible, reproducible evidence for the reusable global proof.

    Float fields are diagnostics rounded outwards.  The caller uses the
    directed multiprecision endpoints in the proof record itself.
    """
    proof = halfband_majorant(stage)
    if proof is None:
        return None
    return dict(
        schema="P15/exact-halfband-alias-pair-majorant/1",
        coefficient_sha256=proof.coefficient_sha256,
        upper_dyadic=list(proof.upper._mpi_[1]),
        odd_upper_dyadic=list(proof.odd_upper._mpi_[1]),
        alias_pair_upper=math.nextafter(float(proof.upper), math.inf),
        nodes_examined=proof.nodes_examined,
        closed_cover=[[str(lo), str(hi)] for lo, hi in proof.covered_intervals],
        cover_domain=["0", "1/4"],
        precision_decimal_digits=proof.precision_decimal_digits,
        internal_odd_target=str(_TARGET),
        method="exact halfband complement identity and complete directed Taylor cover",
        limitations="ideal captured coefficient alias-pair norm; no execution-roundoff claim")
