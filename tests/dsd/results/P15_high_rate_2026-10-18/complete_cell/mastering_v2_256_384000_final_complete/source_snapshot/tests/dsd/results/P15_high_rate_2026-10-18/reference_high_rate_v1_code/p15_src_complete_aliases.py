#!/usr/bin/env python3
"""Complete rational-stage *alias-family enumeration* for P15.

No alias is omitted on the basis of magnitude or a sampled-tone cutoff.
Unlike a single-rate gcd shortcut, the input/output shift lattice is computed
from every intermediate rate.c stage (including halfband parity). An output
frequency f in [0, Fout/2] admits the complete, non-overlapping source set
    f_s = f + s * Fout / U_effective
with one s for each native frequency in [-Fnative/2, Fnative/2).

Diagnostic amplitudes are evaluated from source-exported SRC polyphase W and
independently SHA-verified native FIR coefficient banks. Vectorized Fourier
sums evaluate *every* source family, with coherent magnitudes added linearly.
They are ordinary binary64 sampled values, not outward-rounded continuous-
frequency bounds; this module MUST NEVER report a spectral acceptance PASS.
It is a source-bound enumeration and a foundation for a separate interval
certificate and complete 8.6.1 numerical forward-error proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from p15_src_bound_operator import SRCOperator, UnboundOperator, load_snapshot
from p15_numerical_reference import bank_data_for_profile

ROOT=Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Family:
    s: int
    source_hz: Fraction
    src_residue: int
    desired: bool


def _ceil(a: Fraction) -> int:
    return -((-a.numerator)//a.denominator)


def _floor(a: Fraction) -> int:
    return a.numerator//a.denominator


def alias_families(native_hz: int, op: SRCOperator, output_frequency) -> tuple[Family,...]:
    """Exhaustive half-open input Nyquist partition, no arbitrary bandwidth crop.

    A frequency in the half-open native interval is represented exactly once,
    including one Nyquist endpoint. Each source frequency is capable of
    reaching the chosen output frequency via a stage-periodic image (possibly
    with exactly zero effective coefficient). Its SRC image branch is s mod V.
    """
    if type(native_hz) is not int or native_hz<=0 or native_hz%op.input_hz:
        raise UnboundOperator('invalid native/intermediate rate pairing')
    f=Fraction(output_frequency)
    if not 0<=f<=Fraction(op.output_hz,2):
        raise UnboundOperator('output frequency outside inclusive output Nyquist')
    spacing=Fraction(op.output_hz,op.U)
    lower=_ceil((-Fraction(native_hz,2)-f)/spacing)
    upper=_ceil((Fraction(native_hz,2)-f)/spacing)-1
    if lower>upper or upper-lower+1>1000000:
        raise UnboundOperator('invalid/excessive alias population')
    result=tuple(Family(s=s,source_hz=f+s*spacing,src_residue=s%op.V,
                        desired=(s==0)) for s in range(lower,upper+1))
    assert len(result)==native_hz//spacing  # Exact partition for supported clock lattice.
    return result


def native_profile(profile: str):
    manifest,banks=bank_data_for_profile(profile)
    meta=manifest['profiles'][profile]
    native=meta['native_hz'];R=meta['intermediate_hz']
    names=tuple(meta['stage_banks'])
    if not all(name in banks for name in names) or native//R!=2**len(names):
        raise UnboundOperator('invalid or unpinned native reconstruction topology')
    return native,R,names,banks


def native_frequency_response(profile: str, frequencies: np.ndarray) -> np.ndarray:
    """Centered infinite native FIR response; no finite-boundary extrapolation.

    Each 2:1 stage is a real symmetric FIR sampled at its native stage clock.
    Its input domain is the original DSD clock divided by 2**stage; a native
    harmonic at f reaches that stage with the physical same f modulo its
    sampled rate. Multiply all stages' (centered) transfer functions.
    """
    native,_,names,banks=native_profile(profile)
    f=np.asarray(frequencies,dtype=np.float64)
    if f.ndim!=1 or not np.isfinite(f).all() or np.any(abs(f)>native/2):
        raise UnboundOperator('invalid native frequency vector')
    response=np.ones(len(f),dtype=np.complex128)
    for stage,name in enumerate(names):
        coeff=np.asarray(banks[name],dtype=np.float64)
        center=(len(coeff)-1)//2
        # Pair symmetric taps: no interpolation; all original taps contribute.
        argument=(2*np.pi*(1<<stage)/native)*f
        H=np.full(len(f),coeff[center],dtype=np.float64)
        for j in range(1,center+1):
            H+=2*coeff[center+j]*np.cos(argument*j)
        response*=H
    return response


def src_image_coefficients(op: SRCOperator, output_frequency) -> np.ndarray:
    """All V stage-periodic coefficients at one EXACT output frequency.

    W[n,j] is the independently indexed source-bound stage cascade. For
    f_s=f_out+s*R/V, the ideal transfer into f_out is
       C_s=(1/U) sum_{n=0}^{U-1} sum_j W[n,j]
             exp(2pi i * f_s*j/R - 2pi i*f_out*n/Fout).
    Re-index j modulo V to evaluate all s=0..V-1 by one IFFT per phase.
    Never truncate W by amplitude: cancellation is evaluated after all taps.
    """
    f=Fraction(output_frequency)
    if not 0<=f<=Fraction(op.output_hz,2):
        raise UnboundOperator('invalid output frequency')
    if op.U>4096 or op.V>4096 or op.U*op.V>1000000:
        raise UnboundOperator('unsupported period requires resource review')
    dest=np.zeros(op.V,dtype=np.complex128)
    freq=float(f)
    for output_index in range(op.U):
        row=op.row(output_index)
        indices=np.fromiter((j for j,_ in row),dtype=np.int64,count=len(row))
        weights=np.fromiter((w for _,w in row),dtype=np.float64,count=len(row))
        vector=np.zeros(op.V,dtype=np.complex128)
        factor=weights*np.exp(2j*np.pi*freq/op.input_hz*indices)
        np.add.at(vector,np.mod(indices,op.V),factor)
        # +sign inverse transform equals exp(+2pi*i*s*j/V) in C_s.
        dest+=(np.fft.ifft(vector)*op.V)*np.exp(
            -2j*np.pi*freq/op.output_hz*output_index)
    return dest/op.U


def complete_sample(profile: str,op: SRCOperator,frequency_hz):
    """Evaluate every coherent source family at *one* output frequency.

    This returns SAMPLED_DIAGNOSTIC, never PASS or a continuous bound.
    """
    native,R,names,_=native_profile(profile)
    if R!=op.input_hz:
        raise UnboundOperator('native bank intermediate and SRC clocks differ')
    families=alias_families(native,op,frequency_hz)
    image=src_image_coefficients(op,frequency_hz)
    frequencies=np.fromiter((float(f.source_hz) for f in families),dtype=np.float64)
    native_transfer=native_frequency_response(profile,frequencies)
    residues=np.fromiter((f.src_residue for f in families),dtype=np.int64)
    composite=native_transfer*image[residues]
    abs_terms=np.abs(composite)
    desired_index=-families[0].s
    if not 0<=desired_index<len(families) or not families[desired_index].desired:
        raise UnboundOperator('missing wanted baseband source family')
    # math.fsum is less susceptible than ordinary vector sum to dominated
    # small aliases, but this remains non-directed binary64 diagnostics.
    alias_sum=math.fsum(float(t) for i,t in enumerate(abs_terms) if i!=desired_index)
    all_sum=math.fsum(float(t) for t in abs_terms)
    return dict(schema='P15/complete-source-alias-lattice/1',
        status='SAMPLED_DIAGNOSTIC_UNCERTIFIED',qualified=False,
        profile=profile,source_native_hz=native,intermediate_hz=R,
        output_hz=op.output_hz,frequency_hz=str(Fraction(frequency_hz)),
        stage_period=dict(input=op.V,output=op.U,multiple=op.stage_period_multiple,
                          reduced_input=op.reduced_V,reduced_output=op.reduced_U),
        frequency_spacing_hz=str(Fraction(op.output_hz,op.U)),
        alias_family_count=len(families),wanted_family_s=0,
        actual_family_min_s=families[0].s,actual_family_max_s=families[-1].s,
        wanted_abs=float(abs_terms[desired_index]),
        coherent_unwanted_abs=alias_sum,
        coherent_including_wanted_abs=all_sum,
        source_endpoints='[-native/2,native/2) exact, no family omissions',
        numerical_scope='sampled double-precision complex evaluation; no continuous supremum or FFT4G bound')


def all_active_cells() -> tuple[dict,...]:
    """Bind to *both* 2026-10-15 frozen v1 and v2 worklists.

    Preserve cell identity; reuse an SRC rate-pair realization only when the
    intermediate/final clocks (and stage snapshot) are identical.
    """
    sources=[ROOT/'tests/dsd/results/P15_v1_matrix_rebound_2026-10-15/scalar/worklist.json',
             ROOT/'tests/dsd/results/P15_v2_matrix_2026-10-15/scalar/worklist.json']
    results=[]
    for matrix,path in zip(('v1','v2'),sources):
        if not path.is_file():raise UnboundOperator('required immutable matrix worklist missing')
        raw=json.loads(path.read_text())
        cells=raw.get('scalar_cells',[])
        if len(cells)!=(54 if matrix=='v1' else 27):
            raise UnboundOperator('unexpected historical cell population')
        for c in cells:
            native=c['native_hz']; target=c['pcm_hz']
            ident=c['id']
            if matrix=='v2':
                name=f'decode.mastering.v2.dsd{native//44100}'
            else:
                name=('master' if c['profile']=='mastering' else 'wide')+str(native//44100)
            n,R,_,_=native_profile(name)
            if n!=native:raise UnboundOperator('cell ID/bank native clock mismatch')
            if R!=target:
                results.append(dict(matrix=matrix,id=ident,profile=name,
                                    native_hz=n,intermediate_hz=R,output_hz=target))
    if len(results)!=72 or len({(x['intermediate_hz'],x['output_hz']) for x in results})!=24:
        raise UnboundOperator('SRC population is not 72 cells / 24 rate pairs')
    return tuple(results)


def snapshot_receipt(path: Path, profile: str, frequency_hz) -> dict:
    """Only treat a snapshot as bound if the paired current source hashes pass."""
    from p15_src_bound_operator import source_identity,sha_file
    path=path.resolve()
    digest=json.loads((path.parent/'operator-binding.json').read_text())
    if not (digest.get('source_sha256')==source_identity() and
            digest.get('snapshot_sha256')==sha_file(path) and
            digest.get('schema')=='P15/stage-source-binding/1'):
        raise UnboundOperator('source-stage snapshot missing/mismatched binding')
    op=load_snapshot(path)
    return dict(sample=complete_sample(profile,op,frequency_hz),
                snapshot_sha256=sha_file(path),binding_sha256=sha_file(path.parent/'operator-binding.json'),
                native_coefficient_pins={name:sha_file(ROOT/name) for name in
                    ('src/dsd_coeffs.h','src/dsd_coeffs_v2.h',
                     'tests/dsd/reference/p06_coefficients.json',
                     'tests/dsd/reference/p15_r3_coefficients.json')})
