#!/usr/bin/env python3
"""Exhaustive reverse alias paths through actual SRC and native FIR stages.

A rational L/M stage is represented as upsampling by L, convolution with
its EXACT captured high-rate phase FIR g[t], then decimation by M. For an
output sinusoid f, the M upstream Fourier branches are f+k*Fout inside
[-L*Fin/2,L*Fin/2); each contributes G(f+k*Fout)/L and has a unique input
frequency modulo Fin. The native 2:1 decimating FIR banks are included as
ordinary L=1,M=2 stages. No aliases are dropped based on magnitude.

For a point, this is a source-derived, high-precision diagnostic (not an
execution-roundoff certificate). For continuous intervals, it can use
p15_src_continuum_bounds.TrigPoly to bound each filter continuously, but
exhaustiveness and phase-branch boundary coverage must be proven before PASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import math

import mpmath as mp
from p15_src_bound_operator import SRCOperator,Stage,UnboundOperator,load_snapshot
from p15_src_complete_aliases import native_profile,alias_families

mp.mp.dps=75
ROOT=Path(__file__).resolve().parents[2]

class AliasProofError(ValueError): pass

@dataclass(frozen=True)
class FIRStage:
    kind:str
    input_hz:int
    output_hz:Fraction
    L:int
    M:int
    taps:tuple[tuple[int,float], ...]


def make_src_stages(op:SRCOperator):
    result=[]
    clock=Fraction(op.input_hz)
    for stage in op.stages:
        if stage.kind==1:
            # Same centered parity mapping as rate_half_fir source.
            pairs=[(0,0.5)]
            for j,c in enumerate(stage.coeff):
                pairs.extend(((-(2*j+1),c),(2*j+1,c)))
            L,M=1,2
        elif stage.kind==2:
            L=stage.L
            M=(1<<-stage.M) if stage.M<0 else stage.M
            if L!=1 and (L&(L-1)):
                raise AliasProofError('unreviewed arbitrary FFT interpolation')
            pairs=[(stage.dft_post_peak+j-stage.dft_taps+1,c*L)
                   for j,c in enumerate(stage.coeff)]
        elif stage.kind==3 and stage.order==0:
            L,M=stage.L,stage.M
            if stage.at_i64 or stage.step_i64!=(M<<32) or stage.phases!=L:
                raise AliasProofError('unreviewed rational stage clock or interpolation order')
            pairs=[(phase+L*(stage.preload-j),stage.coeff[phase*stage.n+j])
                   for phase in range(L) for j in range(stage.n)]
        else:
            raise AliasProofError('unknown SRC stage type')
        out=clock*L/M
        if out.denominator!=1:
            raise AliasProofError('non-integral intermediate clock not supported')
        result.append(FIRStage(kind=f'src-kind-{stage.kind}',input_hz=int(clock),output_hz=out,
                               L=L,M=M,taps=tuple(sorted(pairs))))
        clock=out
    if clock!=op.output_hz:
        raise AliasProofError('SRC stage product does not equal recorded rate')
    return tuple(result)


def make_native_stages(profile):
    native,R,names,banks=native_profile(profile)
    clock=native
    result=[]
    for name in names:
        h=banks[name]
        mid=(len(h)-1)//2
        result.append(FIRStage('native-'+name,clock,Fraction(clock,2),1,2,
            tuple((k-mid,float(v)) for k,v in enumerate(h))))
        clock//=2
    if clock!=R:
        raise AliasProofError('incorrect native FIR stage clock')
    return tuple(result)


def branches(stage:FIRStage,output_frequency):
    """Return *all M* input frequency / high-rate filter branches exactly."""
    f=Fraction(output_frequency)
    out=stage.output_hz
    upper=stage.L*stage.input_hz/2
    # Integer ceil/floor with exact rationals. Nyquist +endpoint excluded.
    low=-Fraction(stage.L*stage.input_hz,2)
    high=Fraction(stage.L*stage.input_hz,2)
    def ceil(q): return -((-q.numerator)//q.denominator)
    kmin=ceil((low-f)/out)
    kmax=ceil((high-f)/out)-1
    if kmax-kmin+1!=stage.M:
        raise AliasProofError('missing/doubled reverse-FFT frequency branch')
    result=[]
    for k in range(kmin,kmax+1):
        fu=f+k*out
        # Distinct primitive aliases are separated by Fin; fold to native
        # stage input Nyquist, retaining signed full-frequency index.
        fin=Fraction(stage.input_hz)
        folded=fu-fin*math.floor((fu+fin/2)/fin)
        result.append((fu,folded))
    return tuple(result)


@lru_cache(maxsize=4096)
def response_at(stage:FIRStage, frequency_hz:int):
    # 75-digit evaluation from binary64-coefficient taps, no FFT/NumPy.
    freq=mp.mpf(frequency_hz)
    clock=mp.mpf(stage.input_hz)*stage.L
    angle=2*mp.pi*freq/clock
    return mp.fsum(mp.mpf(w)*mp.exp(1j*angle*k) for k,w in stage.taps)/stage.L


def response_at_fraction(stage:FIRStage,frequency):
    freq=Fraction(frequency)
    if freq.denominator==1:
        return response_at(stage,int(freq))
    angle=2*mp.pi*(mp.mpf(freq.numerator)/freq.denominator)/(stage.input_hz*stage.L)
    return mp.fsum(mp.mpf(w)*mp.exp(1j*angle*k) for k,w in stage.taps)/stage.L


def point_bounds(profile,op:SRCOperator,frequency_hz, *, max_paths=100000):
    """Conservative coherent upper over all *complete* native harmonic paths.

    The resulting sum is >= the true coherent unwanted alias sum; different
    stage paths can hit the same native harmonic and interfere. The desired
    lower bound is main_path_amplitude minus every other path amplitude; it
    does not assume that phase-compensated delays are identical.
    """
    stage_seq=make_native_stages(profile)+make_src_stages(op)
    f=Fraction(frequency_hz)
    if not 0<=f<=Fraction(op.output_hz,2):
        raise AliasProofError('point outside output Nyquist')
    paths=[(f,mp.mpf(1),True)]
    for stage in reversed(stage_seq):
        next_paths=[]
        for prev,amp,primary in paths:
            for j,(fu,upstream) in enumerate(branches(stage,prev)):
                # A main-path branch must continue to represent physical
                # source f, even if intermediate filters wrap around Nyquist.
                v=abs(response_at_fraction(stage,fu))
                next_paths.append((upstream,amp*v,primary and upstream==f))
        paths=next_paths
        if len(paths)>max_paths:
            raise AliasProofError('refusing unbounded complete alias expansion')
    # Every independent native source harmonic is represented at least once;
    # *all* paths are included, even multiple paths to one source frequency.
    families=alias_families(native_profile(profile)[0],op,f)
    expected=[x.source_hz for x in families]
    represented={freq for freq,_,_ in paths}
    if len(paths)!=len(families) or represented!=set(expected):
        raise AliasProofError('native alias coverage does not match stage-true lattice')
    primary=[amp for x,amp,p in paths if p]
    other=[amp for x,amp,p in paths if not p]
    if len(primary)!=1:
        raise AliasProofError('dominant direct path not uniquely identified')
    direct=primary[0]
    unwanted=mp.fsum(other)
    return dict(status='SAMPLED_STAGEWISE_CONSERVATIVE',qualified=False,
        profile=profile,output_hz=op.output_hz,frequency_hz=str(f),
        unique_native_sources=len(represented),all_alias_paths=len(paths),
        direct_amplitude=float(direct),coherent_unwanted_path_upper=float(unwanted),
        total_upper=float(direct+unwanted),
        wanted_lower=max(0.,float(direct-unwanted)),
        scope='sampled 75-digit ideal stage FIR products, not continuum/execution roundoff')

if __name__=='__main__':
    import argparse,json
    ap=argparse.ArgumentParser()
    ap.add_argument('--profile',default='master64')
    ap.add_argument('--snapshot',type=Path,required=True)
    ap.add_argument('--frequency',type=int,default=1000)
    a=ap.parse_args()
    op=load_snapshot(a.snapshot)
    print(json.dumps(point_bounds(a.profile,op,a.frequency),indent=2))
