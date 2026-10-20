#!/usr/bin/env python3
"""R7 exact composite spectral engine, with separately qualified fast FIR recurrence.

This subclass leaves the R6 alias enumeration, frequency transitions, trie,
conservative pruning and original acceptance policy unmodified. It replaces
only the expensive single-FIR Taylor interval primitive and matching halfband
Q-continuum proof by the exact-grid recurrence from p15_r7_fast_fir.
"""
from __future__ import annotations
from fractions import Fraction as F
from functools import lru_cache

from p15_r6_exact_composite import ExactComposite
from p15_r5_integer_spectral import IntervalRefusal
from p15_r7_fast_fir import certify_fir_auto


@lru_cache(maxsize=8192)
def _qualified_fir_cache(taps,lo,hi,order):
    """Cache only exact source-tap and interval identities, never object IDs."""
    return certify_fir_auto(taps,lo,hi,order=order)


@lru_cache(maxsize=64)
def _qualified_halfband_cache(q,max_nodes):
    """Source-coefficient-keyed global quarter-cycle certificate, no trust shift."""
    fallback=sum((abs(F.from_float(v)) for _,v in q),F(0))
    if not q:return F(1),0
    target=F(50000001,100000000)
    todo=[(F(0),F(1,4))];largest=F(0);examined=0
    while todo and examined<max_nodes:
        lo,hi=todo.pop();examined+=1
        c=_qualified_fir_cache(q,lo,hi,8)
        if c.upper()<target:
            largest=max(largest,c.upper())
        else:
            mid=(lo+hi)/2
            todo.extend(((lo,mid),(mid,hi)))
    if todo:return 2*max(F(1,2),fallback),examined
    return 2*max(F(1,2),largest),examined


class FastComposite(ExactComposite):
    def halfband_cap(self,index):
        if index in self.halfbands:return self.halfbands[index]
        q=self._odd_halfband(index)
        if q is None:return None
        self.halfbands[index]=_qualified_halfband_cache(q,self.max_halfband_nodes)
        return self.halfbands[index]

    def stage_bounds(self,index,shift,lo,hi,*,wanted=False):
        key=(index,shift,lo,hi,wanted)
        if key in self.bounds_cache:return self.bounds_cache[key]
        a,b=self._normalized(index,shift,lo,hi)
        if not wanted:
            shortcut=self._difference_upper(index,a,b)
            if shortcut is not None and shortcut<F(1,1000000000):
                self.difference_uses+=1
                answer=(F(0),min(shortcut,self.l1(index)))
                self.bounds_cache[key]=answer
                return answer
        if self.evaluations>=self.max_evaluations:
            from p15_r6_exact_composite import ExactRefusal
            raise ExactRefusal('exact FIR evaluation budget exhausted')
        self.evaluations+=1
        s=self.stages[index]
        # The geometric Taylor bound remains independently valid for every
        # permitted order. Use fewer exact derivative terms only when the
        # entire tap/interval phase radius admits a safely small product.
        max_k=max(abs(k) for k,_ in s.taps)
        phase_radius=7*(b-a)*max_k/2  # 7 > 2*pi
        order=4 if phase_radius<=F(1,16) else (6 if phase_radius<=F(1,3) else 8)
        c=_qualified_fir_cache(s.taps,a,b,order)
        answer=(max(F(0),c.lower())/s.L,min(c.upper()/s.L,self.l1(index)))
        self.bounds_cache[key]=answer
        return answer
