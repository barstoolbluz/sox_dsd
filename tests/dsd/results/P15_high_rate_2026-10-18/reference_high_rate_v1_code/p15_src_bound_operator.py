#!/usr/bin/env python3
"""P15: independently indexed stage-to-input operator from source-bound C words.

The test-only exporter includes the exact production ``src/rate.c`` and captures
its original binary64 LPF taps before FFT4G preparation. Its output is a
coefficient/clock *witness*, not a production-source-independent derivation of
the Kaiser design function or an FFT4G arithmetic proof. This module independently
implements the finite centered multirate indexing in rate.c, rate_half_fir.h,
rate_poly_fir{0,}.h, and the overlap/save ideal FIR equivalent.

All coefficient words are preserved; neither small taps nor stage families are
silently dropped. The resulting W represents the mathematically ideal cascade
of the exported binary64 FIR taps, not each rounded FFT4G butterfly. A final
release certificate additionally needs B_coeff / B_other / N_ops and the
source-locked native input vectors described in DSD_DESIGN.md 8.6.1.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
import math
import re
from pathlib import Path

import mpmath as mp
import numpy as np
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCES=(
 'src/rate.c','src/rate_filters.h','src/rate_half_fir.h',
 'src/rate_poly_fir.h','src/rate_poly_fir0.h','src/rate_internal.h',
 'src/dft_filter.h','src/fft4g.h','src/sox_i.h',
 'src/effects_i_dsp.c',
 'src/fft4g.c','src/dft_filter.c','src/dsd.c','src/dsd_decode.c',
 'src/dsd_coeffs.h','src/dsd_coeffs_v2.h',
 'src/dsd.h','src/dsd_public.c','src/dsd_kernels.h',
 'test/Makefile.am',
 'src/dsd_kernels_scalar.c','src/dsd_decode.h',
 'tests/dsd/reference/p06_coefficients.json',
 'tests/dsd/reference/p15_r3_coefficients.json',
 'tests/dsd/test_p15_src_stage_export.c',
 'tests/dsd/p15_numerical_reference.py',
 'tests/dsd/certify_filters.py','tests/dsd/test_p07_reference.c',
 'tests/dsd/p15_src_operator_observations.py',
 'tests/dsd/results/P15_v1_matrix_rebound_2026-10-15/scalar/worklist.json',
 'tests/dsd/results/P15_v2_matrix_2026-10-15/scalar/worklist.json',
 'tests/dsd/p15_src_bound_operator.py',
 'tests/dsd/p15_src_complete_aliases.py',
 'tests/dsd/p15_src_full_chain.py',
 'tests/dsd/p15_src_capture_matrix.py',
)
MAX_STAGES=10
MAX_COEFFICIENTS=1000000
MAX_ROW_TERMS=400000

class UnboundOperator(ValueError):
    """Reject invalid, unrecognized or unbounded production source evidence."""


def sha_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def source_identity() -> dict[str,str]:
    return {name:sha_file(ROOT/name) for name in SOURCES}


def _require_int(s: dict, key: str, low: int, high: int) -> int:
    v=s.get(key)
    if type(v) is not int or not low<=v<=high:
        raise UnboundOperator(f'invalid {key}')
    return v


def _as_floats(s: list[str], count: int) -> tuple[float,...]:
    if type(s) is not list or len(s)!=count or count>MAX_COEFFICIENTS:
        raise UnboundOperator('coefficient count mismatch')
    values=[]
    for item in s:
        if type(item) is not str:
            raise UnboundOperator('noncanonical coefficient')
        try: v=float.fromhex(item)
        except (ValueError,OverflowError) as exc:
            raise UnboundOperator('invalid coefficient') from exc
        if not math.isfinite(v) or not re.fullmatch(r'-?0x[0-9a-f]+(?:\.[0-9a-f]+)?p[+-][0-9]+',item) or (v==0 and item.startswith('-')):
            raise UnboundOperator('noncanonical/nonfinite binary64 coefficient')
        values.append(v)
    return tuple(values)


@dataclass(frozen=True,eq=False)
class Stage:
    kind: int
    order: int
    n: int
    L: int
    M: int
    phases: int
    phase_bits: int
    preload: int
    pre: int
    pre_post: int
    dft_taps: int
    dft_length: int
    dft_post_peak: int
    remL: int
    remM: int
    at_i64: int
    step_i64: int
    coeff: tuple[float,...]
    fft_bins: tuple[float,...]

    def validate_fft4g_preparation(self) -> None:
        """Independent packed-bin reconstruction of rate.c's FFT preparation.

        NumPy is a distinct algorithm from FFT4G. The conservative threshold
        is a gross identity/packing check, NOT its forward-error certificate.
        """
        if self.kind!=2:return
        raw=np.zeros(self.dft_length,dtype=np.float64)
        original=np.asarray(self.coeff,dtype=np.float64)
        indices=(np.arange(self.dft_taps)+self.dft_length-self.dft_taps+1)%self.dft_length
        raw[indices]=original*(2*self.L/self.dft_length)
        bins=np.fft.rfft(raw)
        packed=np.empty(self.dft_length,dtype=np.float64)
        packed[0]=bins[0].real
        packed[1]=bins[-1].real
        packed[2::2]=bins[1:-1].real
        packed[3::2]=-bins[1:-1].imag  # FFT4G stores conjugate imaginary sign.
        observed=np.asarray(self.fft_bins,dtype=np.float64)
        allowed=(256*np.finfo(np.float64).eps *
                 max(1.,math.log2(self.dft_length))*np.sum(abs(raw)))
        if not np.isfinite(packed).all() or np.max(abs(packed-observed))>allowed:
            raise UnboundOperator('source FFT bin identity disagrees with captured design taps')

    def ratio(self) -> Fraction:
        if self.kind==1: return Fraction(1,2)
        if self.kind==2:
            # rate.c's negative step is the frequency-domain /2^m case.
            return Fraction(self.L,1 << -self.M) if self.M<0 else Fraction(self.L,self.M)
        if self.kind==3:
            if self.order==0: return Fraction(self.L,self.M)
            return Fraction(1<<32,self.step_i64)
        raise UnboundOperator('unrecognized stage')

    @lru_cache(maxsize=4096)
    def taps_to_previous(self, output_index: int) -> tuple[tuple[int,float],...]:
        """Infinite ideal stage row; centered startup uses virtual negative zeros."""
        if type(output_index) is not int or abs(output_index)>100000000:
            raise UnboundOperator('stage index exceeds bounded analysis range')
        if self.kind==1:
            # r_half_fir's p->pre == p->preload == 2*num_coefs.
            result=[(2*output_index,.5)]
            for j,c in enumerate(self.coeff):
                dx=2*j+1
                result.extend(((2*output_index-dx,c),(2*output_index+dx,c)))
            return tuple(result)
        if self.kind==2:
            effective_M=(1<<-self.M) if self.M<0 else self.M
            t=output_index*effective_M
            # Unrotated exact LPF h[j] was located at ((j-overlap) mod N)
            # in FFT4G. Overlap/save discards N-(N-overlap) delayed entries.
            # f->post_peak original zero-padding cancels the group delay.
            base=t+self.dft_taps-1-self.dft_post_peak
            return tuple(((base-j)//self.L,c*self.L)
                for j,c in enumerate(self.coeff)
                if (base-j)%self.L==0)
        if self.kind==3:
            if self.order==0:
                at=self.at_i64//(1<<32)+output_index*(self.step_i64//(1<<32))
                quotient,phase=divmod(at,self.L)
                x=0.
            else:
                total=self.at_i64+output_index*self.step_i64
                integer,fraction=divmod(total,1<<32)
                phase=fraction >> (32-self.phase_bits)
                # The C unsigned << discards high bits. Result is the
                # remaining fraction *within* the selected phase cell.
                x=((fraction<<self.phase_bits)&0xffffffff)/float(1<<32)
                quotient=integer
            if not 0<=phase<self.phases:
                raise UnboundOperator('phase selection outside captured bank')
            stride=self.order+1
            row=[]
            for j in range(self.n):
                off=self.n*(stride*phase)+stride*j
                # rate.c coef() stores interpolation powers in reverse order,
                # and reverses the FIR tap j within each phase.
                block=self.coeff[off:off+stride]
                if self.order==0: value=block[0]
                else:
                    value=block[0]
                    for term in block[1:]: value=value*x+term
                row.append((quotient+j-self.preload,value))
            return tuple(row)
        raise UnboundOperator('unsupported stage type')


@dataclass(frozen=True,eq=False)
class SRCOperator:
    input_hz: int
    output_hz: int
    stages: tuple[Stage,...]

    @property
    def reduced_U(self) -> int:
        return self.output_hz//math.gcd(self.input_hz,self.output_hz)

    @property
    def reduced_V(self) -> int:
        return self.input_hz//math.gcd(self.input_hz,self.output_hz)

    @property
    def stage_period_multiple(self) -> int:
        """The nominal rational period may not reset EVERY stage's parity.

        A valid input translation of V frames must induce integral stage
        translations at each intermediate output, not merely at the final
        clock. This is stricter than gcd(input_hz,output_hz), and prevents
        silently dropping staggered halfband/polyphase families.
        """
        delta=Fraction(self.reduced_V)
        multiplier=1
        for stage in self.stages:
            delta*=stage.ratio()
            multiplier=math.lcm(multiplier,delta.denominator)
        return multiplier

    @property
    def U(self) -> int:
        return self.reduced_U*self.stage_period_multiple

    @property
    def V(self) -> int:
        return self.reduced_V*self.stage_period_multiple

    def exact_row(self, n: int, frames: int | None = None, *, precision=75):
        """75-digit ideal effective binary64 coefficient operator at output n.

        This is not an FFT4G primitive/roundoff certificate. It is used to
        independently check the same centered coefficient/phase mapping.
        """
        if not 75<=precision<=200:
            raise UnboundOperator('insufficient/excessive requested precision')
        with mp.workdps(precision):
            def recurse(stage_id,position):
                if stage_id>=0 and frames is not None and position<0:
                    return {}  # Separate per-stage leading zero extension.
                if stage_id<0: return {position:mp.mpf(1)}
                st=self.stages[stage_id]
                terms={}
                for prev,weight in st.taps_to_previous(position):
                    # For the P15 rates every coefficient stage uses no
                    # interpolation: all weights are exact captured binary64.
                    # Other interpolation modes have separately rounded
                    # phase polynomial terms and require explicit handling.
                    if st.kind==3 and st.order!=0:
                        raise UnboundOperator('75-digit interpolated phase binding not implemented')
                    if not weight:continue
                    for j,c in recurse(stage_id-1,prev).items():
                        terms[j]=terms.get(j,mp.mpf(0))+mp.mpf(weight)*c
                    if len(terms)>MAX_ROW_TERMS:
                        raise UnboundOperator('exact operator row too large')
                return terms
            taps=recurse(len(self.stages)-1,n)
            return {j:v for j,v in sorted(taps.items())
                    if frames is None or 0<=j<frames}

    @lru_cache(maxsize=4096)
    def stage_row(self, stage_index: int, output_index: int) -> tuple[tuple[int,float],...]:
        if stage_index<0: return ((output_index,1.),)
        result=defaultdict(float)
        for prev,weight in self.stages[stage_index].taps_to_previous(output_index):
            if weight==0.:continue
            for original,coefficient in self.stage_row(stage_index-1,prev):
                result[original]+=weight*coefficient
            if len(result)>MAX_ROW_TERMS:
                raise UnboundOperator('effective operator row too large')
        return tuple(sorted(result.items()))

    @lru_cache(maxsize=4096)
    def stage_row_finite(self, stage_index: int, output_index: int) -> tuple[tuple[int,float],...]:
        """Causal stream startup differs from the infinite spectral operator.

        Every stage is separately primed with *numeric zeros*, not the
        nonzero negative-time outputs of the preceding anticausal FIR.
        Historical tests probing only interior impulses miss this effect.
        """
        if output_index<0:return ()
        if stage_index<0:return ((output_index,1.),)
        result=defaultdict(float)
        for prev,weight in self.stages[stage_index].taps_to_previous(output_index):
            if prev<0 or weight==0.:continue
            for original,coefficient in self.stage_row_finite(stage_index-1,prev):
                result[original]+=weight*coefficient
            if len(result)>MAX_ROW_TERMS:
                raise UnboundOperator('finite effective operator row too large')
        return tuple(sorted(result.items()))

    def row(self, n: int, frames: int | None = None) -> tuple[tuple[int,float],...]:
        pairs=(self.stage_row(len(self.stages)-1,n) if frames is None else
               self.stage_row_finite(len(self.stages)-1,n))
        # Numeric zero extension of source and every intermediate stage.
        if frames is not None:
            if type(frames) is not int or frames<0:
                raise UnboundOperator('invalid finite input length')
            pairs=tuple((j,w) for j,w in pairs if 0<=j<frames)
        return pairs

    def gain(self,n: int,source_index: int,frames: int | None=None) -> float:
        return dict(self.row(n,frames)).get(source_index,0.)

    def shift_residual(self, n: int) -> float:
        """Period test against rational U/V, independent of impulse recordings."""
        a=dict(self.row(n));b=dict(self.row(n+self.U))
        keys=set(a)|{k-self.V for k in b}
        return max((abs(a.get(k,0.)-b.get(k+self.V,0.)) for k in keys),default=0.)


def load_snapshot(path: Path) -> SRCOperator:
    try:
        obj=json.loads(path.read_text())
    except (OSError,ValueError) as exc:
        raise UnboundOperator('invalid rate.c stage snapshot') from exc
    if type(obj) is not dict or obj.get('schema')!='P15/source-rate-stage-snapshot/1':
        raise UnboundOperator('unknown stage snapshot schema')
    input_hz=_require_int(obj,'input_hz',8000,1000000)
    output_hz=_require_int(obj,'output_hz',8000,1000000)
    stages=obj.get('stages');count=_require_int(obj,'stage_count',1,MAX_STAGES)
    if (input_hz==output_hz or type(stages) is not list or len(stages)!=count):
        raise UnboundOperator('incorrect SRC stage count')
    result=[]
    for i,s in enumerate(stages):
        if type(s) is not dict or s.get('index')!=i or type(s.get('use_hi_prec_clock')) is not bool:
            raise UnboundOperator('invalid stage index/clock')
        if s['use_hi_prec_clock']:
            raise UnboundOperator('high-precision clock requires a distinct implementation')
        kind=_require_int(s,'kind',1,3)
        order=_require_int(s,'order',-1,3)
        n=_require_int(s,'n',0,100000)
        phases=_require_int(s,'phases',0,1<<22)
        L=_require_int(s,'L',0,1<<22)
        M=_require_int(s,'M',-(1<<20),1<<22)
        phase_bits=_require_int(s,'phase_bits',-16,22)
        preload=_require_int(s,'preload',0,1000000)
        pre=_require_int(s,'pre',0,1000000)
        pre_post=_require_int(s,'pre_post',0,2000000)
        dtaps=_require_int(s,'dft_taps',0,200000)
        dlength=_require_int(s,'dft_length',0,1<<22)
        dpeak=_require_int(s,'dft_post_peak',0,200000)
        remL=_require_int(s,'remL',0,1<<22)
        remM=_require_int(s,'remM',0,1<<22)
        if any(type(s.get(k)) is not str or not re.fullmatch(r'-?(0|[1-9][0-9]*)',s[k])
               for k in ('at_i64','step_i64')):
            raise UnboundOperator('noncanonical fixed-point clock')
        at=int(s['at_i64']);step=int(s['step_i64'])
        if not (-1<<63)<=at<(1<<63) or not (-1<<63)<step<(1<<63):
            raise UnboundOperator('invalid clock word')
        if kind==1:
            if (order!=-1 or n or phases or dtaps or dlength or M or L!=0 or
                preload!=pre or pre_post!=2*pre or pre%2 or not 8<=pre//2<=13):
                raise UnboundOperator('halfband stage metadata violates rate.c')
            expected=pre//2
        elif kind==2:
            if (order!=-1 or phases or dtaps<3 or dtaps%2!=1 or
                dlength<dtaps or dlength&(dlength-1) or L==0 or
                dpeak!=dtaps//2 or pre or pre_post or
                preload!=dpeak//L or remL!=dpeak%L or
                M==0 or (M<0 and (1<<(-M))>dlength)):
                raise UnboundOperator('FFT/overlap stage metadata violates rate.c')
            expected=dtaps
        else:
            if (not 0<=order<=3 or n<2 or phases<1 or M<=0 or L==0 or
                dtaps or dlength or pre or pre_post!=n-1 or preload!=(n-1)//2 or
                (order==0 and (phases!=L or at%(1<<32) or step%(1<<32))) or
                (order>0 and (phases!=(1<<phase_bits) or phase_bits>22))):
                raise UnboundOperator('polyphase metadata violates rate.c')
            expected=n*phases*(order+1)
        coeff=_as_floats(s.get('coefficients'),expected)
        fft= _as_floats(s.get('fft4g_realized_bins'),dlength) if kind==2 else ()
        stage=Stage(kind,order,n,L,M,phases,phase_bits,preload,pre,pre_post,
                    dtaps,dlength,dpeak,remL,remM,at,step,coeff,fft)
        stage.validate_fft4g_preparation()
        result.append(stage)
    op=SRCOperator(input_hz,output_hz,tuple(result))
    ratio=math.prod((s.ratio() for s in op.stages),start=Fraction(1))
    if ratio!=Fraction(output_hz,input_hz):
        raise UnboundOperator(f'stage product ratio {ratio} != {output_hz}/{input_hz}')
    return op


def capture(executable: Path,input_hz: int,output_hz: int,dest: Path) -> dict:
    """Digest-bound, repeatable staging. No overwrite of conflicting receipts."""
    executable=executable.resolve()
    if not executable.is_file() or not 8000<=input_hz<=1000000 or not 8000<=output_hz<=1000000:
        raise UnboundOperator('invalid executable or clock')
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink():raise UnboundOperator('refusing symlink destination')
        if not dest.is_dir() or {p.name for p in dest.iterdir()} != {
            'operator-binding.json','stage-snapshot.json'} or any(
            p.is_symlink() or not p.is_file() for p in dest.iterdir()):
            raise UnboundOperator('incomplete or unsafe existing stage receipt')
        receipt=json.loads((dest/'operator-binding.json').read_text())
        op=load_snapshot(dest/'stage-snapshot.json')
        if (receipt.get('status')!='SOURCE_BOUND_UNCERTIFIED' or
            receipt.get('qualified') is not False or receipt.get('U')!=op.U or
            receipt.get('V')!=op.V or receipt.get('period_multiple')!=op.stage_period_multiple or
            receipt.get('schema')!='P15/stage-source-binding/1' or
            receipt.get('source_sha256')!=source_identity() or
            receipt.get('exporter_sha256')!=sha_file(executable) or
            receipt.get('input_hz')!=input_hz or receipt.get('output_hz')!=output_hz or
            receipt.get('snapshot_sha256')!=sha_file(dest/'stage-snapshot.json')):
            raise UnboundOperator('existing binding receipt cannot be reused')
        return receipt
    if not dest.parent.is_dir():
        dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p15-stage-',dir=dest.parent) as tmp:
        pending=Path(tmp)/'stage-snapshot.json'
        cmd=[str(executable),str(input_hz),str(output_hz),str(pending)]
        proc=subprocess.run(cmd,capture_output=True,timeout=90)
        if proc.returncode or not pending.is_file() or proc.stdout:
            raise UnboundOperator('stage export failed: '+proc.stderr.decode(errors='replace')[:400])
        op=load_snapshot(pending)
        receipt=dict(schema='P15/stage-source-binding/1',status='SOURCE_BOUND_UNCERTIFIED',
                     qualified=False,input_hz=input_hz,output_hz=output_hz,
                     U=op.U,V=op.V,reduced_U=op.reduced_U,
                     reduced_V=op.reduced_V,period_multiple=op.stage_period_multiple,
                     exporter_sha256=sha_file(executable),source_sha256=source_identity(),
                     snapshot_sha256=sha_file(pending),
                     stages=[dict(kind=x.kind,order=x.order,coefficients=len(x.coeff),
                                  ratio=str(x.ratio())) for x in op.stages],
                     limitation='source-captured realized design taps and phases; '
                       'FFT4G arithmetic, bounded rounding, exact nonlinear coefficient '
                       'generation and full continuum extrema not independently certified')
        (Path(tmp)/'operator-binding.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        import os
        for entry in (pending,Path(tmp)/'operator-binding.json'):
            with entry.open('rb') as f: os.fsync(f.fileno())
        fd=os.open(tmp,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)
        # Atomic across both objects. Stop if another writer won the pathname.
        if dest.exists() or dest.is_symlink():
            raise UnboundOperator('destination appeared while acquiring')
        os.replace(tmp,dest)
        fd=os.open(dest.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)
    return receipt
