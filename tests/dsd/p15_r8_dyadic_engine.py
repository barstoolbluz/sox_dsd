#!/usr/bin/env python3
"""Proof-preserving dyadic envelope compression for P15 composite SRC certificates.

Does NOT modify DSP or previous R6/R7 certified mathematics. Applies outward
quantization only AFTER independently justified exact FIR stage enclosures,
thereby reducing repeated product/sum denominators without weakening the proof.
"""
from __future__ import annotations
from fractions import Fraction as F
from p15_r7_engine import FastComposite
from p15_r6_exact_composite import ExactRefusal

BITS = 192
GRID = 1 << BITS


def floor_dyadic(q: F) -> F:
    if not isinstance(q,F): raise ExactRefusal('non-rational lower endpoint')
    return F((q.numerator*GRID)//q.denominator, GRID)


def ceil_dyadic(q: F) -> F:
    if not isinstance(q,F): raise ExactRefusal('non-rational upper endpoint')
    return F(-((-q.numerator*GRID)//q.denominator), GRID)


class DyadicComposite(FastComposite):
    """Each stage interval is replaced by a provably enclosing dyadic interval."""
    def stage_bounds(self,index,shift,lo,hi,*,wanted=False):
        key=(index,shift,lo,hi,wanted)
        if key in self.bounds_cache:return self.bounds_cache[key]
        lower,upper=super().stage_bounds(index,shift,lo,hi,wanted=wanted)
        # Strict outward inclusions: floor(lower*2^BITS) /2^BITS <= lower;
        # ceil(upper*2^BITS)/2^BITS >= upper. The rounding uses exact
        # arbitrary-precision signed-integer arithmetic. No binary64 involved.
        ans=(max(F(0),floor_dyadic(lower)),ceil_dyadic(upper))
        if ans[0] > ans[1] or ans[0]<0: raise ExactRefusal('invalid dyadic stage enclosure')
        self.bounds_cache[key]=ans
        return ans
