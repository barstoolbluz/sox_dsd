#!/usr/bin/env python3
"""Finite native-FIR + private SoX SRC coefficient/phase composition, P15.

The native FIR banks are independently pinned by P06/P15R3 coefficient
manifests; the SRC coefficients and clocks are exported from the exact rate.c
source in a test-only binary, then re-indexed independently. This is the
*ideal* stage cascade from rounded source coefficients, not a certificate of
FFT4G's arithmetic or of all finite-frequency extrema. Never issue PASS.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import math
import json
from pathlib import Path
import subprocess

import mpmath as mp
import numpy as np

from p15_numerical_reference import equivalent_exact, front_end
from p15_src_bound_operator import SRCOperator, UnboundOperator
from p15_src_complete_aliases import native_profile


def full_period(profile: str, src: SRCOperator) -> tuple[int,int]:
    """(native input frames, output frames) of the complete centered chain."""
    native, R, names, _ = native_profile(profile)
    if R != src.input_hz:
        raise UnboundOperator('native and SRC intermediate clocks differ')
    D = native // R
    if D != 2**len(names):
        raise UnboundOperator('native decimation phase schedule invalid')
    return D * src.V, src.U


def native_composite_gain(profile: str, src: SRCOperator,
                          output_index: int, native_index: int,
                          native_frames: int | None = None, precision=75):
    """75-digit finite sample gain for one binary64 input pulse at native_index.

    The native FIR's finite exactly centered time mapping is
        h[delay + m*D - k]
    and each private SRC output is sum_m W[n,m] * x[m]. Input and intermediate
    streams use numeric zeros outside the finite source. Every nonzero SRC
    coefficient participates; do not prune by amplitude or assume the source
    has infinite duration. The bin/execution coefficient residual remains OPEN.
    """
    if type(output_index) is not int or output_index < 0 or output_index > 1000000:
        raise UnboundOperator('output index outside bounded audit')
    if type(native_index) is not int or native_index < 0:
        raise UnboundOperator('negative native index')
    native,R,_,_ = native_profile(profile)
    if R != src.input_hz:
        raise UnboundOperator('native and SRC clocks differ')
    if native_frames is not None:
        if type(native_frames) is not int or not 1 <= native_frames <= 10000000:
            raise UnboundOperator('invalid native stream length')
        if native_index >= native_frames:
            raise UnboundOperator('native impulse outside finite stream')
        frame_count=(native_frames*R + native-1)//native
    else:
        frame_count=None
    equivalent,delay,down = equivalent_exact(profile)
    with mp.workdps(precision):
        row=src.exact_row(output_index, frame_count,precision=precision)
        return mp.fsum(w*equivalent[delay + m*down-native_index]
                       for m,w in row.items()
                       if 0 <= delay + m*down-native_index < len(equivalent))


def finite_chain_source(profile: str, src: SRCOperator,
                        native_input: np.ndarray, output_indexes: tuple[int,...]) -> dict[int,float]:
    """Independent high-accuracy finite reference, for bounded test lengths.

    This invokes the existing independent native FIR reference, then computes
    the source-indexed SRC *ideal* cascade with longdouble accumulation.
    The original one-bit domain is checked, unlike hypothetical float-native
    samples passed through a codec API.
    """
    bits=np.asarray(native_input,dtype=np.uint8)
    if bits.ndim != 1 or len(bits)>262144 or np.any(bits>1):
        raise UnboundOperator('bad native bit input / exceeded review limit')
    native,R,_,_=native_profile(profile)
    if R!=src.input_hz:
        raise UnboundOperator('profile clock mismatch')
    front=front_end(bits,profile)
    out_count=(len(bits)*src.output_hz + native//2)//native
    result={}
    for n in output_indexes:
        if type(n) is not int or not 0<=n<out_count:
            raise UnboundOperator('requested output index outside finite stream')
        row=src.row(n,len(front))
        # Two independent constructions can be compared for selected positions.
        result[n]=float(math.fsum(float(w)*float(front[j]) for j,w in row))
    return result


def verify_real_src_impulses(probe: Path, src: SRCOperator, *, frames=4096,
                             anchors: tuple[int,...] | None=None,
                             local_radius=8) -> dict:
    """Cross-check both finite boundaries and interior against production P07.

    The *entire* emitted F64 vector is hashed. The independently evaluated
    coefficients are compared at explicit start, end and impulse neighborhoods
    (not a blanket assertion over unreviewed output indices). Residuals are
    observations only and CANNOT be promoted to a P15 arithmetic PASS.
    """
    from p15_src_operator_observations import impulse
    if anchors is None:
        anchors=(0,frames//2,frames-1)
    if not 2048<=frames<=65536 or not anchors or len(anchors)>8 or not 2<=local_radius<=32:
        raise UnboundOperator('unbounded production audit')
    results=[]
    for anchor in anchors:
        if not 0<=anchor<frames:
            raise UnboundOperator('bad impulse anchor')
        obs,digest=impulse(probe,src.input_hz,src.output_hz,frames,anchor)
        approx=int(anchor*src.output_hz/src.input_hz)
        indices=sorted({i for i in (list(range(0,min(5,len(obs))))+
                    list(range(max(0,len(obs)-5),len(obs)))+
                    list(range(max(0,approx-local_radius),
                                   min(len(obs),approx+local_radius+1))))})
        expected=np.fromiter((.5*src.gain(i,anchor,frames) for i in indices),
                             dtype=np.float64,count=len(indices))
        delta=obs[indices]-expected
        results.append(dict(intermediate_input_impulse=anchor,
                  output_frames=len(obs),output_indices=indices,
                  p07_binary64_sha256=digest,
                  maximum_absolute_observed_disagreement=float(np.max(abs(delta))),
                  rms_observed_disagreement=float(np.sqrt(np.mean(delta*delta)))))
    return dict(schema='P15/src-operator-impulse-comparison/1',
                status='OBSERVED_UNCERTIFIED',qualified=False,
                input_hz=src.input_hz,output_hz=src.output_hz,frames=frames,
                probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256((Path(__file__).resolve().parents[2] /
                                 'tests/dsd/test_p07_reference.c').read_bytes()).hexdigest(),
                period_intermediate_input=src.V,period_output=src.U,
                checked=results)


def verify_real_composite(probe: Path, profile: str, src: SRCOperator,
                          *, native_frames=65536) -> dict:
    """Three-boundary checks on genuine native one-bit input, source SHA bound.

    Output is a sampled *diagnostic*. Large differences constitute a model
    problem, but small values do not establish a numerical acceptance bound.
    """
    import subprocess
    native,R,_,_=native_profile(profile)
    if R!=src.input_hz or native_frames>262144 or native_frames<8192:
        raise UnboundOperator('bad source profile/size')
    enum=3 if profile.startswith('decode.mastering.v2.') else (1 if profile.startswith('wide') else 0)
    cmd=[str(probe.resolve()),'--dsd',str(native),str(src.output_hz),
         str(enum),str(native_frames)]
    p=subprocess.run(cmd,capture_output=True,timeout=120)
    expected=(native_frames*src.output_hz + native//2)//native
    if p.returncode or len(p.stdout)!=expected*8:
        raise UnboundOperator('real one-bit decoder failed to export expected F64 count')
    observed=np.frombuffer(p.stdout,dtype='<f8').copy()
    if not np.isfinite(observed).all():
        raise UnboundOperator('nonfinite production composite output')
    bits=np.fromiter((0 if (i//512)&1 else 1 for i in range(native_frames)),
                     dtype=np.uint8,count=native_frames)
    ids=tuple(sorted({i for i in (0,1,2,3,4,expected//2-1,expected//2,
              expected//2+1,expected-5,expected-4,expected-3,expected-2,expected-1)
              if 0<=i<expected}))
    expected_values=finite_chain_source(profile,src,bits,ids)
    delta=[abs(float(observed[i])-expected_values[i]) for i in ids]
    return dict(schema='P15/source-native-fir-src-production-crosscheck/1',
           status='OBSERVED_UNCERTIFIED',qualified=False,profile=profile,
           native_hz=native,intermediate_hz=R,output_hz=src.output_hz,
           native_frames=native_frames,output_frames=expected,
           sampled_output_indexes=ids,maximum_observed_disagreement=max(delta),
           output_sha256=hashlib.sha256(p.stdout).hexdigest(),
           probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
           native_bank_pins={name:hashlib.sha256((Path(__file__).resolve().parents[2]/name).read_bytes()).hexdigest()
                        for name in ('src/dsd_coeffs.h','src/dsd_coeffs_v2.h',
                                     'tests/dsd/reference/p06_coefficients.json',
                                     'tests/dsd/reference/p15_r3_coefficients.json')},
           numerical_scope='observed finite-input reference comparison; no arithmetic PASS')
