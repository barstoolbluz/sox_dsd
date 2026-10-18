#!/usr/bin/env python3
"""Source-bound continuous-frequency coherent-alias interval certificate.

This is an on-demand, *rigorous* interval instrument for the ideal captured
coefficient cascade. It enumerates EVERY frequency branch of every native/SRC
stage, then uses outward-rounded finite-trigonometric Taylor bounds where
needed and exact L1 majorants for still-unexpanded branch subtrees. It
subtracts the full coherent unwanted bound when bounding the direct path.
It never substitutes sparse tone sampling, RMS summation, magnitude cutoffs
or a shortened band for the continuum.

PASS-LOCAL-BAND is valid ONLY for the explicitly named small frequency interval.
P15 full 72-cell approval additionally needs all bands, source execution
roundoff, AND an independently qualified whole-resource run. The independent
interval checker must return OPEN when its finite path/node budget is reached.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
import tempfile
from fractions import Fraction
from functools import lru_cache
import json
import math
from pathlib import Path

from mpmath import iv
from p15_src_stagewise_alias_proof import (FIRStage,make_src_stages,
                      make_native_stages,AliasProofError)
from p15_src_continuum_bounds import (TrigPoly,db_band,fraction,scalar)
from p15_src_interval_recurrence import magnitude_bounds
from p15_src_branch_bound import bound_population
from p15_src_capture_matrix import verify_pair
from p15_src_complete_aliases import native_profile
from p15_src_bound_operator import source_identity,sha_file

iv.dps=75

class Unproved(ValueError): pass

# Normative §6.1; profile identifiers also must resolve in the manifest.
# A source SHA of DSD_DESIGN.md is written in every published local receipt.
PROFILE_BANDS={
    'master64':(20000,40000), 'master128':(30000,60000),
    'master256':(40000,80000),
    'wide64':(35280,44100), 'wide128':(70560,88200),
    'wide256':(141120,176400),
    'decode.mastering.v2.dsd64':(25000,40000),
    'decode.mastering.v2.dsd128':(48000,60000),
    'decode.mastering.v2.dsd256':(66000,80000),
}


def ceil_left_limit(q:Fraction):
    """Ceil(q(f)) as f approaches the upper edge from below; q falls in f."""
    return ceil(q)+(int(q.denominator==1))


def floor_left_limit(q:Fraction):
    """Floor(q(f)) as f approaches the upper edge from below; q rises in f."""
    return math.floor(q)-(int(q.denominator==1))


def ceil(q):
    return -((-q.numerator)//q.denominator)


@dataclass(frozen=True)
class AliasPath:
    upstream_shift:Fraction
    terms:tuple[tuple[FIRStage,Fraction], ...]
    direct:bool


@dataclass(frozen=True)
class BranchBoundary:
    """Exact interior frequency at which an inverse-stage branch changes.

    The two adjacent regions must be enumerated separately. A crossing exactly
    at an endpoint does not require a split: one-sided limits of the analytic
    FIR transfers cover the shared endpoint by continuity.
    """
    at:Fraction


def _next_ceil_transition(lo,hi,quotient,clock):
    """First interior discontinuity of ceil(q(f)), q decreasing at 1/clock.

    Evaluate on the *right* side of lo; a transition at hi itself belongs to
    the interval on the right, not the left. Everything is exact rational.
    """
    boundary=lo+(quotient-(ceil(quotient)-1))*clock
    return boundary if lo<boundary<hi else None


def _next_floor_transition(lo,hi,quotient,clock):
    """First interior discontinuity of floor(q(f)), q increasing at 1/clock."""
    boundary=lo+(math.floor(quotient)+1-quotient)*clock
    return boundary if lo<boundary<hi else None


@lru_cache(maxsize=100)
def _poly(stage:FIRStage):
    # Coefficients are exact binary64 words from source-verified exporter.
    # Signed time-origin is retained; no coefficient magnitude is discarded.
    if len(stage.taps)>1000000 or not stage.taps:
        raise Unproved('invalid source FIR length')
    if len(set(k for k,_ in stage.taps)) !=len(stage.taps):
        raise Unproved('duplicate high-rate FIR index')
    return TrigPoly(tuple(stage.taps),Fraction(0))


def complete_paths(profile,op,lo:Fraction,hi:Fraction,*,max_paths=12000,require_direct=True):
    if not Fraction(0)<=lo<=hi<=Fraction(op.output_hz,2):
        raise Unproved('frequency band outside output Nyquist')
    stages=make_native_stages(profile)+make_src_stages(op)
    main=AliasPath(Fraction(0),(),True)
    paths=[main]
    midpoint=(lo+hi)/2
    for stage in reversed(stages):
        next_paths=[]
        clock=stage.output_hz
        high=Fraction(stage.L*stage.input_hz,2)
        for path in paths:
            base=path.upstream_shift
            # Select the M highrate branches for the interior midpoint.
            kmin=ceil((-high-midpoint-base)/clock)
            kmax=ceil(( high-midpoint-base)/clock)-1
            if kmax-kmin+1!=stage.M:
                raise Unproved('stage phase band not exhaustive')
            # Endpoint validity is mandatory. A crossover must be split at
            # its EXACT rational frequency, not indefinitely bisected toward
            # a non-dyadic boundary. No PASS from a midpoint-only schedule.
            # Use exact one-sided limits at upper endpoints. A frequency-
            # family relabeling exactly at an interval boundary cannot
            # invalidate a uniform bound on its analytic interior: the
            # continuous endpoint is covered by the limiting inequality.
            # Comparing ceil/floor at the closed upper endpoint itself would
            # instead trigger endless subdivision at Nyquist crossings.
            def ceil_hi(x):return ceil_left_limit(x) if lo<hi else ceil(x)
            q_min_lo=(-high-lo-base)/clock
            q_max_lo=( high-lo-base)/clock
            if (kmin!=ceil(q_min_lo) or
                kmin!=ceil_hi((-high-hi-base)/clock)):
                boundary=_next_ceil_transition(lo,hi,q_min_lo,clock)
                if boundary is None:raise Unproved('unlocated inverse-stage lower crossover')
                return BranchBoundary(boundary)
            if (kmax!=ceil(q_max_lo)-1 or
                kmax!=ceil_hi((high-hi-base)/clock)-1):
                boundary=_next_ceil_transition(lo,hi,q_max_lo,clock)
                if boundary is None:raise Unproved('unlocated inverse-stage upper crossover')
                return BranchBoundary(boundary)
            for k in range(kmin,kmax+1):
                offset=base+k*clock
                fin=Fraction(stage.input_hz)
                wrap=math.floor((midpoint+offset+fin/2)/fin)
                q_lo=(lo+offset+fin/2)/fin
                q_hi=(hi+offset+fin/2)/fin
                if wrap!=math.floor(q_lo) or \
                   wrap!=(floor_left_limit(q_hi) if lo<hi else math.floor(q_hi)):
                    boundary=_next_floor_transition(lo,hi,q_lo,fin)
                    if boundary is None:raise Unproved('unlocated inverse-fold crossover')
                    return BranchBoundary(boundary)
                new_offset=offset-wrap*fin
                # Record the exact high-rate argument f+offset. Phase is
                # irrelevant for norm upper, but all branches are retained.
                next_paths.append(AliasPath(new_offset,path.terms+((stage,offset),),
                        path.direct and new_offset==0))
        paths=next_paths
        if len(paths)>max_paths:
            raise Unproved('explicit path population exceeds allocated budget')
    native,_,_,_=native_profile(profile)
    # In a valid stage-true period, each harmonic has exactly one reverse path.
    # No frequency branch may be omitted or duplicated.
    expected=Fraction(native*op.U,op.output_hz)
    if expected.denominator!=1 or len(paths)!=int(expected):
        raise Unproved('whole-chain harmonic coverage/count inconsistent')
    if len({p.upstream_shift for p in paths})!=len(paths):
        raise Unproved('frequency families collide; must coherently regroup explicitly')
    if require_direct and sum(p.direct for p in paths)!=1:
        raise Unproved('no unique zero-shift wanted branch')
    return tuple(paths)


def bounds_single(stage:FIRStage,shift:Fraction,lo:Fraction,hi:Fraction):
    """Directed amplitude interval for |G((f+shift)/highrate)| / L."""
    a=lo+shift; b=hi+shift
    if a<=0<=b:
        qlo=Fraction(0);qhi=max(-a,b)
    elif b<0:
        qlo=-b;qhi=-a
    else:
        qlo=a;qhi=b
    rate=stage.input_hz*stage.L
    if qlo<0 or qhi>Fraction(rate,2):
        raise Unproved('highrate argument outside interval checker domain')
    down,up,_=magnitude_bounds(_poly(stage),qlo/rate,qhi/rate)
    # Frequencies and coefficients are exact, errors from MP interval
    # arithmetic have been propagated outward by magnitude_bounds.
    return (down.a/stage.L if bool(down.a>0) else iv.mpf(0)),up.b/stage.L


def bound_segment(paths,lo,hi,*,stop_source_hz,mode='pass'):
    """Certify a complete coherent-alias *upper* using exact L1 subtrees.

    Every unevaluated leaf remains included through its FIR L1 majorant; the
    rigorous frontier is refined only as necessary to meet the *unchanged*
    1e-8 source-stop / coherent-alias threshold. When it cannot, the caller
    subdivides or reports OPEN. No magnitude truncation or RMS sums.
    """
    if mode not in ('pass','stop'):
        raise Unproved('unknown population bound mode')
    cache={}
    def stage_upper(term,left,right):
        if term not in cache:
            cache[term]=bounds_single(term[0],term[1],left,right)
        return cache[term][1]

    if mode=='stop':
        def stop_source(path):
            a=lo+path.upstream_shift
            b=hi+path.upstream_shift
            # Including a touching harmonic for the whole interval is
            # conservative. It cannot undercount a boundary-crossing source.
            return max(abs(a),abs(b))>=stop_source_hz
        source_stop_upper,_=bound_population(paths,lo,hi,include=stop_source,
                                  limit='1e-8',evaluate=stage_upper)
        return dict(wanted_lower=None,wanted_upper=None,unwanted_upper=None,
                    source_stopband_upper=source_stop_upper,
                    amplitudes_evaluated=len(cache))

    direct=[path for path in paths if path.direct]
    if len(direct)!=1:
        raise Unproved('wanted branch absent or non-unique')
    low=iv.mpf(1);high=iv.mpf(1)
    for term in direct[0].terms:
        if term not in cache:
            cache[term]=bounds_single(term[0],term[1],lo,hi)
        low*=cache[term][0]
        high*=cache[term][1]
    upper_alias,_=bound_population(paths,lo,hi,include=lambda p:not p.direct,
                                   limit='1e-8',evaluate=stage_upper)
    pass_lower=(low-upper_alias).a
    if not bool(pass_lower>0):pass_lower=iv.mpf(0)
    return dict(wanted_lower=pass_lower,wanted_upper=high+upper_alias,
                unwanted_upper=upper_alias,source_stopband_upper=None,
                amplitudes_evaluated=len(cache))


def certificate(profile,op,lo_hz,hi_hz,*,mode="pass",max_nodes=32,max_paths=12000):
    lo,hi=fraction(lo_hz),fraction(hi_hz)
    if mode not in ('pass','stop') or profile not in PROFILE_BANDS:
        raise Unproved('unreviewed profile or spectral band classification')
    if not 1<=max_nodes<=131072 or not 1<=max_paths<=100000:
        raise Unproved('invalid bounded interval/path budget')
    P,S=PROFILE_BANDS[profile]
    if mode=='pass' and not (Fraction(0)<=lo<=hi<=P):
        raise Unproved('passband interval violates normative §6.1 profile P')
    if mode=='stop' and not (Fraction(0)<=lo<=hi):
        raise Unproved('negative output interval for native-source stopband')
    native,R,_,_=native_profile(profile)
    if op.input_hz!=R:
        raise Unproved('native/SRC clock mismatch')
    if not 0<=lo<=hi<=min(native//2,op.output_hz//2):
        raise Unproved('unqualified spectral evaluation band')
    # Normative 0.0001dB passband and -160dB coherent alias limits.
    pmin,pmax=db_band('0.0001')
    hi_ref=iv.mpf(pmax);lo_ref=iv.mpf(pmin)
    alias_ref=iv.mpf('1e-8')
    # Only a full, exact-rational stationary alias schedule may be reused.
    # A subinterval cannot introduce a new transition absent in its parent.
    todo=[(lo,hi,None)]
    complete=examined=exact_splits=0
    fir_evaluations=path_enumerations=0
    max_alias=0.;min_wanted=1.;max_total=0.
    def opened(reason):
        return dict(status='OPEN',reason=reason,qualified_release=False,
            proven_subintervals=complete,pending_intervals=len(todo),
            nodes_examined=examined,exact_branch_splits=exact_splits,
            fir_interval_evaluations=fir_evaluations,
            exact_path_enumerations=path_enumerations)
    while todo:
        if examined>=max_nodes:
            return opened('subdivision_node_budget')
        l,h,paths=todo.pop()
        examined+=1
        if paths is None:
            try:
                path_enumerations+=1
                paths=complete_paths(profile,op,l,h,max_paths=max_paths,
                                     require_direct=(mode=='pass'))
            except (AliasProofError,Unproved) as exc:
                return opened('operator_path_precondition:'+str(exc))
        if isinstance(paths,BranchBoundary):
            if not l<paths.at<h:
                return opened('noninterior_exact_branch_boundary')
            exact_splits+=1
            todo.extend(((l,paths.at,None),(paths.at,h,None)))
            continue
        try:
            result=bound_segment(paths,l,h,stop_source_hz=S,mode=mode)
        except (AliasProofError,Unproved) as exc:
            return opened('operator_bound_precondition:'+str(exc))
        fir_evaluations+=result['amplitudes_evaluated']
        wanted_lower=result['wanted_lower']
        wanted_upper=result['wanted_upper']
        aliases=result['unwanted_upper']
        safe=(result['source_stopband_upper'].b<alias_ref.a if mode=='stop' else
              (wanted_lower.a>lo_ref.b and wanted_upper.b<hi_ref.a and
               aliases.b<alias_ref.a))
        if safe:
            complete+=1
            max_alias=max(max_alias,math.nextafter(float(
                result['source_stopband_upper'].b if mode=='stop' else aliases.b),math.inf))
            if mode=='pass':
                min_wanted=min(min_wanted,math.nextafter(float(wanted_lower.a),-math.inf))
                max_total=max(max_total,math.nextafter(float(wanted_upper.b),math.inf))
            continue
        if l==h:
            return opened('insufficient_interval_information_at_point')
        mid=(l+h)/2
        todo.extend(((l,mid,paths),(mid,h,paths)))
    return dict(status='PASS-LOCAL-BAND' if mode=='pass' else 'PASS-LOCAL-STOP-SOURCE',
        qualified_release=False,profile=profile,input_hz=op.input_hz,
        output_hz=op.output_hz,band_kind=mode,
        governing_passband_hz=P,governing_stopband_hz=S,
        certified_hz=[str(lo),str(hi)],native_hz=native,
        fully_proven_subintervals=complete,nodes_examined=examined,
        exact_branch_splits=exact_splits,
        fir_interval_evaluations=fir_evaluations,
        exact_path_enumerations=path_enumerations,
        max_coherent_alias_upper=max_alias if mode=='pass' else None,
        max_native_stop_source_transfer_upper=max_alias if mode=='stop' else None,
        min_wanted_transfer_lower=min_wanted if mode=='pass' else None,
        max_total_transfer_upper=max_total if mode=='pass' else None,
        method=('288-bit outward dyadic Taylor recurrence for exact-even binary64 FIRs; '
                '75-digit directed complex fallback; exact rational branch splits; '
                'complete L1-majorized stagewise inverse aliases'),
        limits=dict(passband_db='0.0001',coherent_alias_db='-160'),
        limitations=('Local stationary coefficient operator only. Stop mode bounds native input '
          'frequencies beyond S folding into the named output interval; does not infer '
          'full-band or 72-cell certificate, nor FFT4G runtime rounding.'))


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--profile',default='master64')
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--lo',default='1000')
    p.add_argument('--hi',default='1000.001')
    p.add_argument('--max-nodes',type=int,default=32)
    p.add_argument('--mode',choices=('pass','stop'),default='pass')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    snapshot=args.snapshot.resolve(strict=True)
    # Stage snapshot must be bound to current source, no anonymous polynomial.
    op_tmp=__import__('p15_src_bound_operator').load_snapshot(snapshot)
    _,op=verify_pair(snapshot.parent,op_tmp.input_hz,op_tmp.output_hz)
    r=certificate(args.profile,op,args.lo,args.hi,mode=args.mode,max_nodes=args.max_nodes)
    r['schema']='P15/local-source-bound-composite-continuum/1'
    r['governing_dsd_design_sha256']=sha_file(Path(__file__).resolve().parents[2]/'docs/dsd/DSD_DESIGN.md')
    r['source_sha256']=source_identity()
    r['stage_snapshot_sha256']=sha_file(snapshot)
    r['verified_operator_binding_sha256']=sha_file(snapshot.parent/'operator-binding.json')
    if args.output:
        output=args.output.resolve()
        data=json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+'\n'
        if output.exists():
            if output.is_symlink() or output.read_text()!=data:
                raise Unproved('source-bound local spectral receipt conflict')
        else:
            output.parent.mkdir(parents=True,exist_ok=True)
            fd,temp=tempfile.mkstemp(prefix='.local-continuum-',dir=output.parent)
            try:
                with os.fdopen(fd,'w') as f:
                    f.write(data);f.flush();os.fsync(f.fileno())
                if output.exists():raise Unproved('output appeared during publication')
                os.replace(temp,output)
            finally:
                if os.path.exists(temp):os.unlink(temp)
    print(json.dumps({k:v for k,v in r.items() if k!='source_sha256'},indent=2,sort_keys=True))
    return 0 if r['status'].startswith('PASS-LOCAL-') else 2

if __name__=='__main__':raise SystemExit(main())
