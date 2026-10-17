#!/usr/bin/env python3
"""Source-bound continuous-frequency coherent-alias interval certificate.

This is an on-demand, *rigorous* interval instrument for the ideal captured
coefficient cascade. It expands EVERY frequency branch of every native/SRC
stage, then uses outward-rounded finite-trigonometric Taylor bounds for each
factor on each closed input-frequency interval. It subtracts the maximum
coherent unwanted sum when bounding the dominant direct path. It never
substitutes sparse tone sampling, RMS summation, magnitude cutoffs or a
shortened band for the continuum.

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
from p15_src_continuum_bounds import (TrigPoly,magnitude_bounds,db_band,
                                       fraction,scalar)
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
            # Endpoint validity is mandatory. If a boundary crosses the band,
            # caller bisects. No PASS from a midpoint-only branch schedule.
            # Use exact one-sided limits at upper endpoints. A frequency-
            # family relabeling exactly at an interval boundary cannot
            # invalidate a uniform bound on its analytic interior: the
            # continuous endpoint is covered by the limiting inequality.
            # Comparing ceil/floor at the closed upper endpoint itself would
            # instead trigger endless subdivision at Nyquist crossings.
            def ceil_hi(x):return ceil_left_limit(x) if lo<hi else ceil(x)
            if (kmin!=ceil((-high-lo-base)/clock) or
                kmin!=ceil_hi((-high-hi-base)/clock) or
                kmax!=ceil((high-lo-base)/clock)-1 or
                kmax!=ceil_hi((high-hi-base)/clock)-1):
                return None  # exact interior crossover; bisect
            for k in range(kmin,kmax+1):
                offset=base+k*clock
                fin=Fraction(stage.input_hz)
                wrap=math.floor((midpoint+offset+fin/2)/fin)
                q_lo=(lo+offset+fin/2)/fin
                q_hi=(hi+offset+fin/2)/fin
                if wrap!=math.floor(q_lo) or \
                   wrap!=(floor_left_limit(q_hi) if lo<hi else math.floor(q_hi)):
                    return None
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


def bound_segment(paths,lo,hi,*,stop_source_hz):
    # Cache stage response bounds in each subinterval. Repeated use of the
    # same filter at the same wrapped frequency costs no additional analysis.
    cache={}
    upper_alias=iv.mpf(0)
    source_stop_upper=iv.mpf(0)
    direct_low=direct_high=None
    for path in paths:
        low=iv.mpf(1);up=iv.mpf(1)
        for key in path.terms:
            if key not in cache:
                cache[key]=bounds_single(key[0],key[1],lo,hi)
            low*=cache[key][0]
            up*=cache[key][1]
        # A source harmonic touching the native >=S region anywhere on
        # this interval is included across the ENTIRE interval. This can
        # produce OPEN near S, but never a false spectral acceptance.
        source_lo=lo+path.upstream_shift
        source_hi=hi+path.upstream_shift
        if max(abs(source_lo),abs(source_hi)) >= stop_source_hz:
            source_stop_upper += up
        if path.direct:
            direct_low=low;direct_high=up
        else:
            upper_alias+=up
    if direct_low is None:
        direct_low=iv.mpf(0);direct_high=iv.mpf(0)
    total_upper=direct_high+upper_alias
    pass_lower=(direct_low-upper_alias).a
    pass_lower=pass_lower if bool(pass_lower>0) else iv.mpf(0)
    return dict(wanted_lower=pass_lower,wanted_upper=total_upper,
                unwanted_upper=upper_alias,source_stopband_upper=source_stop_upper,
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
    todo=[(lo,hi)];complete=0;max_alias=0.;min_wanted=1.;max_total=0.
    while todo:
        if complete+len(todo)>max_nodes:
            return dict(status='OPEN',reason='subdivision_node_budget',
                        proven_subintervals=complete,pending_intervals=len(todo))
        l,h=todo.pop()
        try:
            paths=complete_paths(profile,op,l,h,max_paths=max_paths,require_direct=(mode=='pass'))
        except (AliasProofError,Unproved) as exc:
            return dict(status='OPEN',reason='operator_path_precondition:'+str(exc))
        if paths is None:
            if l==h:return dict(status='OPEN',reason='unresolved_Nyquist_endpoint')
            mid=(l+h)/2;todo.extend(((l,mid),(mid,h)));continue
        result=bound_segment(paths,l,h,stop_source_hz=S)
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
            return dict(status='OPEN',reason='insufficient_interval_information_at_point')
        mid=(l+h)/2
        todo.extend(((l,mid),(mid,h)))
    return dict(status='PASS-LOCAL-BAND' if mode=='pass' else 'PASS-LOCAL-STOP-SOURCE',qualified_release=False,
        profile=profile,input_hz=op.input_hz,output_hz=op.output_hz,
        band_kind=mode,governing_passband_hz=P,governing_stopband_hz=S,
        certified_hz=[str(lo),str(hi)],native_hz=native,
        fully_proven_subintervals=complete,
        max_coherent_alias_upper=max_alias if mode=='pass' else None,
        max_native_stop_source_transfer_upper=max_alias if mode=='stop' else None,
        min_wanted_transfer_lower=min_wanted if mode=='pass' else None,
        max_total_transfer_upper=max_total,
        method='75-digit directed interval Taylor, complete stagewise inverse alias expansion',
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
