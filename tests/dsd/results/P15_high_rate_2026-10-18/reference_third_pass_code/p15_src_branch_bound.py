#!/usr/bin/env python3
"""Exact, fail-closed hierarchical bound for stagewise coherent-alias populations.

This is NOT a magnitude cutoff.  Every path contributes, including paths not
expanded to their leaf: a skipped subtree contributes a mathematically valid
upper bound equal to its complete path count times the exact binary64 FIR L1
operator gains of all unexpanded stages.  The most consequential subtrees are
refined first until the sum is below the SAME normative limit, or all paths
have been evaluated.  Branch ordering is a performance optimization only.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from fractions import Fraction
from functools import lru_cache
import heapq
import itertools
import math
from mpmath import iv
from p15_src_continuum_bounds import scalar

iv.dps=75


@dataclass(slots=True)
class Node:
    term:object=None
    count:int=0
    children:dict=field(default_factory=dict)


@lru_cache(maxsize=128)
def exact_l1_gain(stage):
    # Fraction.from_float decodes binary64 EXACTLY.  Outward-round only once
    # when converting that exact rational to the interval representation.
    absolute_sum=sum((abs(Fraction.from_float(tap)) for _,tap in stage.taps),Fraction(0))
    return (scalar(absolute_sum)/stage.L).b


def bound_population(paths,lo,hi,*,include,limit,evaluate):
    """Upper-bound the sum of |cascade path transfer| for selected paths.

    Inclusion is exact from the fully enumerated path population.  A prefix
    bound counts all descendants even if their trigonometric factors are not
    individually evaluated.  ``evaluate`` must return a directed upper bound.
    """
    chosen=[p for p in paths if include(p)]
    if not chosen:
        return iv.mpf(0),0
    length=len(chosen[0].terms)
    if not length or any(len(p.terms)!=length for p in chosen):
        raise ValueError('inconsistent complete alias path depth')
    stages=[term[0] for term in chosen[0].terms]
    if any(any(t[0] is not stages[i] for i,t in enumerate(p.terms)) for p in chosen):
        raise ValueError('mixed stage topology in one interval population')
    tails=[iv.mpf(1)]*(length+1)
    for i in range(length-1,-1,-1):
        tails[i]=tails[i+1]*exact_l1_gain(stages[i])
    root=Node()
    for path in chosen:
        root.count+=1
        cur=root
        for stage,shift in path.terms:
            key=(id(stage),shift)
            if key not in cur.children:
                cur.children[key]=Node((stage,shift))
            cur=cur.children[key]
            cur.count+=1
    tick=itertools.count()
    heap=[]
    evaluated=0
    total=iv.mpf(0)
    # upper values are endpoints, stored as exact interval points so the
    # subsequent subtraction/addition contains the sum of the replacements.
    def insert(node,depth,prefix,ready):
        nonlocal total
        factor=tails[depth if ready else depth-1]
        upper=(prefix*factor*node.count).b
        total+=upper
        priority=-float(upper)
        heapq.heappush(heap,(priority,next(tick),node,depth,prefix,ready,upper))
    insert(root,0,iv.mpf(1),True)
    ref=iv.mpf(str(limit))
    while heap and not bool(total.b<ref.a):
        _,_,node,depth,prefix,ready,old=heapq.heappop(heap)
        total-=old
        if not ready:
            upper=evaluate(node.term,lo,hi)
            evaluated+=1
            insert(node,depth,prefix*upper,True)
        elif node.children:
            for child in node.children.values():
                insert(child,depth+1,prefix,False)
        else:
            # A fully evaluated leaf cannot be refined further and must
            # remain in the total, with no speculative FAIL disposition.
            total+=old
    return total.b,evaluated
