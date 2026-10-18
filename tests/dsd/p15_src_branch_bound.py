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
from p15_src_halfband_majorant import halfband_alias_sum_upper

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


def _complete_subtree_caps(root, stages):
    """Uniform full-branch gains, only for a structurally valid branch trie.

    A selected population may omit branches, since all contributions to this
    magnitude majorant are nonnegative. It may not duplicate one full path or
    replace a complementary halfband pair by two unrelated frequencies. The
    checks below make the cap safe also for synthetic callers of this module,
    without relying on the production complete_paths admission check.
    """
    pairs = [halfband_alias_sum_upper(stage) for stage in stages]
    if all(value is None for value in pairs):
        return None
    pending = [(root, 0)]
    while pending:
        node, depth = pending.pop()
        if depth == len(stages):
            if node.children or node.count != 1:
                return None  # A duplicate complete path retains its old bound.
            continue
        stage = stages[depth]
        if not 1 <= len(node.children) <= stage.M:
            return None
        if pairs[depth] is not None and len(node.children) == 2:
            shifts = [child.term[1] for child in node.children.values()]
            if (shifts[0] - shifts[1]) % stage.input_hz != Fraction(stage.input_hz, 2):
                return None
        pending.extend((child, depth + 1) for child in node.children.values())
    caps = [iv.mpf(1)] * (len(stages) + 1)
    for depth in range(len(stages) - 1, -1, -1):
        gain = pairs[depth]
        if gain is None:
            gain = stages[depth].M * exact_l1_gain(stages[depth])
        caps[depth] = (gain * caps[depth + 1]).b
    return caps


def bound_population(paths,lo,hi,*,include,limit,evaluate,stats=None,
                     use_subtree_caps=True,use_terminal_saturation=True):
    """Upper-bound the sum of |cascade path transfer| for selected paths.

    Inclusion is exact from the fully enumerated path population.  A prefix
    bound counts all descendants even if their trigonometric factors are not
    individually evaluated.  ``evaluate`` must return a directed upper bound.
    """
    if stats is None:
        stats = {}
    stats.update(trie_nodes=0,frontier_insertions=0,frontier_expansions=0,
                 subtree_caps_used=0,terminal_saturation_returns=0)
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
    stats['trie_nodes'] = 1
    for path in chosen:
        root.count+=1
        cur=root
        for stage,shift in path.terms:
            key=(id(stage),shift)
            if key not in cur.children:
                cur.children[key]=Node((stage,shift))
                stats['trie_nodes'] += 1
            cur=cur.children[key]
            cur.count+=1
    full_caps = _complete_subtree_caps(root, stages) if use_subtree_caps else None
    tick=itertools.count()
    heap=[]
    evaluated=0
    total=iv.mpf(0)
    fixed_upper_sum=iv.mpf(0)
    # upper values are endpoints, stored as exact interval points so the
    # subsequent subtraction/addition contains the sum of the replacements.
    def insert(node,depth,prefix,ready):
        nonlocal total
        factor=tails[depth if ready else depth-1]
        upper=(prefix*factor*node.count).b
        if full_caps is not None:
            # At a ready node the whole remaining branch population is
            # included by the cap. At an unevaluated node only this single
            # branch's current FIR factor precedes the remaining population.
            cap = full_caps[depth]
            if not ready:
                cap = cap * exact_l1_gain(stages[depth - 1])
            alternative = (prefix * cap).b
            if bool(alternative < upper):
                upper = alternative
                stats['subtree_caps_used'] += 1
        total+=upper
        stats['frontier_insertions'] += 1
        priority=-float(upper)
        heapq.heappush(heap,(priority,next(tick),node,depth,prefix,ready,upper))
    insert(root,0,iv.mpf(1),True)
    ref=iv.mpf(str(limit))
    while heap and not bool(total.b<ref.a):
        stats['frontier_expansions'] += 1
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
            if use_terminal_saturation:
                fixed_upper_sum+=old
                # These are fixed UPPER endpoints, not actual amplitudes.
                # No remaining frontier refinement can reduce their sum.
                # Return the still-valid complete upper so the caller can
                # subdivide, rather than evaluating every irrelevant leaf.
                if bool(fixed_upper_sum.a>=ref.b):
                    stats['terminal_saturation_returns']+=1
                    return total.b,evaluated
    return total.b,evaluated
