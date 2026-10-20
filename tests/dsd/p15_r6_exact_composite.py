#!/usr/bin/env python3
"""P15 R6 independent integer/rational ideal-cascade certificate kernel.

No mpmath.iv, float transcendental, numpy, or unqualified interval package is
used by any arithmetic capable of granting PASS. Binary64 taps are decoded as
exact fractions. Stage decoding/source binding is deliberately reused, and is
listed separately as a trusted source-identity dependency. Leaf records are
hints for repeat computation; no claimed numerical upper bound is trusted.
"""
from __future__ import annotations

from dataclasses import dataclass,field
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
import heapq
import itertools
import json
import math

from p15_r5_exact_trig import GRID,sincos,pi_interval
from p15_r5_integer_spectral import certify_fir,IntervalRefusal
from p15_r6_exact_policy import db_pass_bounds
from p15_src_stagewise_alias_proof import make_native_stages, make_src_stages
from p15_src_complete_aliases import native_profile

class ExactRefusal(ValueError): pass


def ceil(q:F): return -((-q.numerator)//q.denominator)

def floor(q:F): return q.numerator//q.denominator


def frac(s):
    """Admit only finite exact integers/rational strings, never float parsing."""
    if isinstance(s,F):return s
    if type(s) is int or type(s) is str and len(s)<2048:
        try:return F(s)
        except (ValueError,ZeroDivisionError) as exc:raise ExactRefusal('invalid rational') from exc
    raise ExactRefusal('unsupported frequency input')


@dataclass(frozen=True)
class Path:
    source_shift:F
    terms:tuple[tuple[int,F],...]
    direct:bool


@dataclass(frozen=True)
class Split:
    at:F


def ceil_upper_left(q):
    # q(f) is strictly decreasing at positive rate. Left limit of ceil(q)
    # when q(hi) is an integer n is n+1.
    return ceil(q)+(q.denominator==1)


def floor_upper_left(q):
    # q(f) is strictly increasing. At integral q(hi)=n, left floor is n-1.
    return floor(q)-(q.denominator==1)


def all_paths(stages, native:int, output:int, U:int, lo:F,hi:F, *,
              require_direct=True, max_paths=20000):
    """Enumerate every inverse highrate branch on a stationary closed segment.

    For a stage of rational clocks Fin,L,M, k ranges over *all* integers
    -Fin*L/2 <= f+offset+k*Fout < Fin*L/2. On each open segment, integer
    ceilings and input-frequency wraps must be constant. Every interior
    transition is solved exactly, and an exact split is returned instead of
    certifying a midpoint's branch population past a transition.
    """
    if not F(0)<=lo<=hi<=F(output,2):
        raise ExactRefusal('outside output Nyquist')
    paths=[Path(F(0),(),True)]
    mid=(lo+hi)/2
    for index in range(len(stages)-1,-1,-1):
        s=stages[index]
        if (s.L<1 or s.M<1 or s.input_hz<=0 or
            s.output_hz!=F(s.input_hz*s.L,s.M)):
            raise ExactRefusal('invalid stage clock or interpolation ratio')
        high=F(s.input_hz*s.L,2);out=F(s.output_hz);fin=F(s.input_hz)
        next_paths=[]
        for path in paths:
            base=path.source_shift
            km=ceil((-high-mid-base)/out)
            kmax=ceil((high-mid-base)/out)-1
            if kmax-km+1!=s.M:
                raise ExactRefusal('stage branch multiplicity differs from M')
            for side in (-1,1):
                bound=side*high
                qlo=(bound-lo-base)/out
                qhi=(bound-hi-base)/out
                midval=km if side==-1 else kmax+1
                if midval!=ceil(qlo) or midval!=(ceil_upper_left(qhi) if lo<hi else ceil(qhi)):
                    # ceil(q) changes when q passes the integer immediately
                    # below ceil(qlo). Its f position is exact.
                    crossing=lo+(qlo-(ceil(qlo)-1))*out
                    if lo<crossing<hi:return Split(crossing)
                    raise ExactRefusal('unlocated inverse branch transition')
            for k in range(km,kmax+1):
                shift=base+k*out
                qlo=(lo+shift+fin/2)/fin
                qhi=(hi+shift+fin/2)/fin
                wrap=floor((mid+shift+fin/2)/fin)
                if wrap!=floor(qlo) or wrap!=(floor_upper_left(qhi) if lo<hi else floor(qhi)):
                    crossing=lo+(floor(qlo)+1-qlo)*fin
                    if lo<crossing<hi:return Split(crossing)
                    raise ExactRefusal('unlocated input wrap transition')
                source_shift=shift-wrap*fin
                next_paths.append(Path(source_shift,path.terms+((index,shift),),
                                       path.direct and source_shift==0))
                if len(next_paths)>max_paths:
                    raise ExactRefusal('path budget exhausted')
        paths=next_paths
    if not paths or stages[0].input_hz!=native:
        raise ExactRefusal('primitive native stage clock mismatch')
    # A single source harmonic can be reached through multiple stage histories.
    # Verify the ENTIRE primitive lattice, but retain duplicate histories.
    spacing=F(output,U)
    count=F(native)/spacing
    low=ceil((-F(native,2)-mid)/spacing)
    high=ceil((F(native,2)-mid)/spacing)-1
    if count.denominator!=1 or int(count)!=high-low+1 or len(paths)<int(count):
        raise ExactRefusal('native harmonic count mismatch')
    observed=set()
    for path in paths:
        z=path.source_shift/spacing
        if z.denominator!=1 or not low<=z.numerator<=high:
            raise ExactRefusal('unrepresentable native harmonic')
        observed.add(z.numerator)
    if len(observed)!=int(count):
        raise ExactRefusal('missing native harmonic family')
    if require_direct and sum(p.direct for p in paths)!=1:
        raise ExactRefusal('wanted family is missing or nonunique')
    return tuple(paths)


def fir_norm(stage):
    return sum((abs(F.from_float(v)) for k,v in stage.taps),F(0))/stage.L


@dataclass(slots=True)
class Node:
    count:int=0
    term:object=None
    children:dict=field(default_factory=dict)


class ExactComposite:
    def __init__(self,profile,op,*,max_evaluations=150,max_halfband_nodes=256):
        self.profile=profile;self.op=op
        self.native,self.R,_,_=native_profile(profile)
        if self.R!=op.input_hz:
            raise ExactRefusal('profile/R does not match captured SRC')
        self.stages=make_native_stages(profile)+make_src_stages(op)
        if self.stages[0].input_hz!=self.native or self.stages[-1].output_hz!=op.output_hz:
            raise ExactRefusal('native and output clock binding disagreement')
        if len(self.stages)>32:raise ExactRefusal('unreviewed stage depth')
        self.max_evaluations=max_evaluations
        self.max_halfband_nodes=max_halfband_nodes
        self.bounds_cache={};self.moments_cache={};self.halfbands={}
        self.evaluations=0;self.difference_uses=0
        self.alias_frontier=0;self.global_caps_used=0

    def l1(self,index):
        return fir_norm(self.stages[index])

    def _odd_halfband(self,index):
        s=self.stages[index]
        if s.L!=1 or s.M!=2 or s.output_hz!=F(s.input_hz,2):
            return None
        taps=dict(s.taps)
        if (len(taps)!=len(s.taps) or taps.get(0)!=0.5 or
            any(k!=0 and v and (k%2==0 or taps.get(-k)!=v) for k,v in s.taps)):
            return None
        return tuple((k,v) for k,v in s.taps if k and v)

    def halfband_cap(self,index):
        """Complete pair majorant from a pure-integer Q continuum cover.

        For h0=1/2, only odd symmetric nonzero taps: Q(f+1/2)=-Q(f),
        |H(f)|+|H(f+1/2)|=2max(1/2,|Q(f)|). Real parity/oddness
        reduce the global |Q| search to f in [0,1/4]. If adaptive proof
        exceeds budget, the exact coefficient L1 is still a valid bound.
        """
        if index in self.halfbands:return self.halfbands[index]
        q=self._odd_halfband(index)
        if q is None:return None
        coeffs=tuple(q or ((0,0.0),))
        fallback=sum((abs(F.from_float(v)) for _,v in q),F(0))
        if not q:
            self.halfbands[index]=(F(1),0)
            return self.halfbands[index]
        target=F(50000001,100000000)
        todo=[(F(0),F(1,4))];largest=F(0);examined=0
        while todo and examined<self.max_halfband_nodes:
            lo,hi=todo.pop();examined+=1
            c=certify_fir(coeffs,lo,hi,order=8)
            if c.upper()<target:
                largest=max(largest,c.upper())
            else:
                mid=(lo+hi)/2
                todo.extend(((lo,mid),(mid,hi)))
        if todo:
            self.halfbands[index]=(2*max(F(1,2),fallback),examined)
        else:
            self.halfbands[index]=(2*max(F(1,2),largest),examined)
        return self.halfbands[index]

    def _difference_moments(self,index):
        """Exact finite-difference convolution against zero-extended FIR."""
        if index in self.moments_cache:return self.moments_cache[index]
        taps=sorted(self.stages[index].taps)
        if not taps or len(taps)>100000 or len(set(k for k,v in taps))!=len(taps):
            raise ExactRefusal('invalid difference FIR')
        span=taps[-1][0]-taps[0][0]+1
        if span>131072:
            self.moments_cache[index]=None
            return None
        floats=[(F.from_float(v),k) for k,v in taps]
        den=max(q.denominator for q,k in floats)
        arr=[0]*span
        for q,k in floats:arr[k-taps[0][0]]=q.numerator*(den//q.denominator)
        ret=[]
        for p in range(1,7):
            arr=[arr[0]]+[arr[j]-arr[j-1] for j in range(1,len(arr))]+[-arr[-1]]
            if p%2==0:ret.append((p,F(sum(abs(x) for x in arr),den)))
        self.moments_cache[index]=tuple(ret)
        return self.moments_cache[index]

    def _normalized(self,index,shift,lo,hi):
        s=self.stages[index]
        a=lo+shift;b=hi+shift
        lower=F(0) if a<=0<=b else min(abs(a),abs(b))
        upper=max(abs(a),abs(b))
        rate=s.input_hz*s.L
        if lower<0 or upper>F(rate,2):
            raise ExactRefusal('FIR highrate frequency outside certified domain')
        return lower/rate,upper/rate

    @lru_cache(maxsize=50000)
    def _sine_lower(self,q:F):
        # sin(pi*q) = sin(2*pi*(q/2)) for q in (0,1/2].
        lo,hi=sincos(q/2)[0]
        return F(lo,GRID)

    def _difference_upper(self,index,nlo,nhi):
        if nlo==0:return None
        moments=self._difference_moments(index)
        if moments is None:return None
        lower=2*self._sine_lower(nlo)
        if lower<=0:return None
        return min((m/(lower**p) for p,m in moments),default=None)/self.stages[index].L

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
            raise ExactRefusal('exact FIR evaluation budget exhausted')
        self.evaluations+=1
        s=self.stages[index]
        c=certify_fir(s.taps,a,b,order=8)
        answer=(max(F(0),c.lower())/s.L,c.upper()/s.L)
        # Triangle inequality gives an independent additional safe upper.
        answer=(answer[0],min(answer[1],self.l1(index)))
        self.bounds_cache[key]=answer
        return answer

    def _alias_sum(self,paths,lo,hi,*,selected,limit=F(1,100000000)):
        if not paths:return F(0)
        depth=len(paths[0].terms)
        stage_ids=[i for i,_ in paths[0].terms]
        if depth==0 or any([i for i,_ in p.terms]!=stage_ids for p in paths):
            raise ExactRefusal('mixed path topology')
        tail=[F(1)]*(depth+1)
        cap=[F(1)]*(depth+1)
        for d in range(depth-1,-1,-1):
            index=stage_ids[d]
            tail[d]=tail[d+1]*self.l1(index)
            pair=self.halfband_cap(index)
            perstage=(pair[0] if pair else self.stages[index].M*self.l1(index))
            cap[d]=cap[d+1]*perstage
        root=Node()
        for p in paths:
            root.count+=1;cur=root
            for i,shift in p.terms:
                key=(i,shift)
                if key not in cur.children:cur.children[key]=Node(term=key)
                cur=cur.children[key];cur.count+=1
        # Exact no-double-count and structural branching check. Otherwise
        # this checker refuses the tighter global cap entirely.
        valid=True;pending=[(root,0)]
        while pending:
            node,d=pending.pop()
            if d==depth:
                if node.children or node.count!=1:valid=False;break
            else:
                index=stage_ids[d]
                if not 1<=len(node.children)<=self.stages[index].M:
                    valid=False;break
                if self._odd_halfband(index) is not None and len(node.children)==2:
                    shifts=[child.term[1] for child in node.children.values()]
                    s=self.stages[index]
                    if (shifts[0]-shifts[1])%s.input_hz!=F(s.input_hz,2):
                        valid=False;break
                pending.extend((x,d+1) for x in node.children.values())
        if not valid:
            raise ExactRefusal('invalid branch trie: duplicate or omitted multiplicity')
        tick=itertools.count();heap=[];total=F(0);fixed=F(0)
        def insert(node,d,prefix,ready):
            nonlocal total
            estimate=prefix*(tail[d] if ready else tail[d-1])*node.count
            if ready:
                alternate=prefix*cap[d]
            else:
                alternate=prefix*self.l1(stage_ids[d-1])*cap[d]
            if alternate<estimate:
                estimate=alternate;self.global_caps_used+=1
            total+=estimate
            heapq.heappush(heap,(-estimate,next(tick),node,d,prefix,ready,estimate))
        insert(root,0,F(1),True)
        while heap and total>=limit:
            self.alias_frontier+=1
            _,_,node,d,prefix,ready,old=heapq.heappop(heap)
            total-=old
            if not ready:
                i,shift=node.term
                _,upper=self.stage_bounds(i,shift,lo,hi)
                insert(node,d,prefix*upper,True)
            elif node.children:
                for child in node.children.values():
                    insert(child,d+1,prefix,False)
            else:
                # Saturated leaves remain part of the certified total. This
                # only terminates refinement; no PASS if the limit is exceeded.
                total+=old;fixed+=old
                if fixed>=limit:return total
        return total

    def leaf(self,lo:F,hi:F,mode:str,stop_source:int,*,max_paths=20000):
        if mode not in ('pass','stop'):
            raise ExactRefusal('invalid spectral mode')
        paths=all_paths(self.stages,self.native,self.op.output_hz,self.op.U,lo,hi,
                        require_direct=(mode=='pass'),max_paths=max_paths)
        if isinstance(paths,Split):return paths
        if mode=='stop':
            # Include each source family intersecting |f| >= S, even if the
            # harmonic crosses the stop edge inside this spectral interval.
            chosen=[p for p in paths if max(abs(lo+p.source_shift),
                                            abs(hi+p.source_shift))>=stop_source]
            upper=self._alias_sum(chosen,lo,hi,selected='stop')
            safe=upper<F(1,100000000)
            return dict(safe=safe,source_stop_upper=upper,alias_paths=len(paths),
                        included_paths=len(chosen))
        wanted=[p for p in paths if p.direct]
        if len(wanted)!=1:raise ExactRefusal('wanted path nonunique')
        wlow=F(1);whigh=F(1)
        for i,shift in wanted[0].terms:
            low,high=self.stage_bounds(i,shift,lo,hi,wanted=True)
            wlow*=low;whigh*=high
        undesired=[p for p in paths if not p.direct]
        alias=self._alias_sum(undesired,lo,hi,selected='alias')
        bottom=max(F(0),wlow-alias);top=whigh+alias
        lower_policy,upper_policy=db_pass_bounds()
        safe=bottom>lower_policy[1] and top<upper_policy[0] and alias<F(1,100000000)
        return dict(safe=safe,wanted_lower=bottom,total_upper=top,
                    coherent_alias_upper=alias,alias_paths=len(paths),
                    included_paths=len(undesired))


def exact_json(d):
    """Serialize exact fractions, preserving all rational endpoints."""
    if isinstance(d,F):return str(d)
    if isinstance(d,dict):return {k:exact_json(v) for k,v in d.items()}
    if isinstance(d,(list,tuple)):return [exact_json(v) for v in d]
    return d
