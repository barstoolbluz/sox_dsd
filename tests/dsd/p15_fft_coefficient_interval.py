#!/usr/bin/env python3
"""Directed interval FFT certificate for SOURCE-CAPTURED SoX SRC coefficient bins.

This independently evaluates the mathematical DFT of the *binary64 input*
to FFT4G by a radix-2 interval Cooley-Tukey algorithm, comparing all observed
packed FFT4G bin words with the exact DFT's enclosures. It rigorously bounds
PRECOMPUTED coefficient-bin numerical realization, not arbitrary runtime FFT4G
butterfly roundoff. No operator/release PASS is issued.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from mpmath import iv

from p15_src_bound_operator import load_snapshot,sha_file,source_identity

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16'

class CertificateError(ValueError): pass


def upper(x):
    return math.nextafter(float(x.b),math.inf)


def complex_dft_intervals(reals, *, precision=80):
    """Return outward interval enclosures for exact radix-2 DFT. No NumPy FFT."""
    iv.dps=precision
    n=len(reals)
    if not 64<=n<=16384 or n&(n-1):
        raise CertificateError('unsupported DFT length')
    r=[iv.mpf(0)]*n
    im=[iv.mpf(0)]*n
    bits=n.bit_length()-1
    for i,x in enumerate(reals):
        reversed_bits=int(format(i,f'0{bits}b')[::-1],2)
        r[reversed_bits]=iv.mpf(x)
    length=2
    while length<=n:
        # Directed interval cos/sin of exact rational roots of unity.
        tw=[(iv.cos(-2*iv.pi*k/length),iv.sin(-2*iv.pi*k/length))
            for k in range(length//2)]
        half=length//2
        for start in range(0,n,length):
            for k,(c,s) in enumerate(tw):
                i=start+k; j=i+half
                ar=r[i]; ai=im[i]
                br=r[j]*c-im[j]*s
                bi=r[j]*s+im[j]*c
                r[i]=ar+br; im[i]=ai+bi
                r[j]=ar-br; im[j]=ai-bi
        length*=2
    return r,im


def bin_certificate(stage,*,precision=80):
    if stage.kind!=2:
        raise CertificateError('not an FFT4G stage')
    length=stage.dft_length
    # Actual C path: f->coefs[(i + N - taps + 1)&(N-1)] = h[i]/N*2*L;
    # L is always power-of-two for the current P15 routes. This ensures the
    # preparation is EXACT in IEEE binary64 provided all shifts are normal.
    if length&(length-1) or stage.L&(stage.L-1):
        raise CertificateError('unreviewed FFT preparation: non-power-of-two L/N')
    inp=[0.]*length
    for i,h in enumerate(stage.coeff):
        # The two binary64 operations are power-of-two scalings in this scope.
        scaled=h/length * 2 * stage.L
        rational=h.as_integer_ratio()
        ideal_n=rational[0]*2*stage.L
        ideal_d=rational[1]*length
        if (not math.isfinite(scaled) or scaled==0. and h!=0 or
              scaled.as_integer_ratio() != float(scaled).as_integer_ratio() or
              ideal_n*scaled.as_integer_ratio()[1]!=ideal_d*scaled.as_integer_ratio()[0]):
            raise CertificateError('FFT coefficient preparation not mathematically exact')
        inp[(i+length-stage.dft_taps+1)&(length-1)]=scaled
    r,im=complex_dft_intervals(inp,precision=precision)
    observed=stage.fft_bins
    if len(observed)!=length or not all(math.isfinite(v) for v in observed):
        raise CertificateError('noncanonical captured packed bins')
    maxre=0.;maxim=0.;worst_bin=-1
    # Exact DFT values of *real* input, conjugate-symmetric coefficients.
    # FFT4G stores negative imag in its real/imag packed array.
    values=[]
    for i in range(length//2+1):
        cr=observed[0] if i==0 else observed[1] if i==length//2 else observed[2*i]
        ci=0. if i in (0,length//2) else -observed[2*i+1]
        err_re=iv.fabs(r[i]-iv.mpf(cr));err_im=iv.fabs(im[i]-iv.mpf(ci))
        ur=upper(err_re);ui=upper(err_im)
        magnitude=upper(iv.sqrt(iv.mpf(ur)**2+iv.mpf(ui)**2))
        values.append(magnitude)
        if magnitude>math.hypot(maxre,maxim):
            maxre=ur;maxim=ui;worst_bin=i
    # Time-domain transfer upper bound for observed packed FFT4G bins versus
    # the exact DFT: with FFT4G's unscaled real inverse, the inverse Fourier
    # coefficient is bounded by the sum of all bin differences / N. The
    # overlap-save runtime factor N/2 therefore leaves 1/2 * sum |delta|.
    # Directed interval bounds include every binary64 sum-rounding step.
    total_error_upper=upper(iv.mpf(values[0])+iv.mpf(values[-1])+
                2*sum((iv.mpf(x) for x in values[1:-1]),iv.mpf(0)))
    per_impulse_absolute_bound=upper(iv.mpf(total_error_upper)/2)
    return dict(dft_length=length,dft_taps=stage.dft_taps,interpolation_L=stage.L,
                max_complex_bin_deviation=upper(iv.sqrt(iv.mpf(maxre)**2+iv.mpf(maxim)**2)),
                worst_bin=worst_bin,
                precomputed_bin_delta_absolute_sum_full=total_error_upper,
                worst_single_impulse_bin_realization_bound=per_impulse_absolute_bound,
                certified_includes='all packed FFT bins; exact mathematical DFT of binary64 pre-FFT stage words',
                unresolved='FFT4G runtime transform, multiplication, inverse and accumulation roundoff')


def certificate(snapshot:Path,*,precision=80):
    pair=snapshot.parent
    binding=json.loads((pair/'operator-binding.json').read_text())
    if binding.get('source_sha256') !=source_identity() or binding.get('snapshot_sha256')!=sha_file(snapshot):
        raise CertificateError('source / stage binding has changed')
    op=load_snapshot(snapshot)
    rows=[bin_certificate(s,precision=precision) for s in op.stages if s.kind==2]
    if not rows:
        raise CertificateError('expected at least one FFT stage')
    return dict(schema='P15/src-fft4g-captured-bin-interval/1',status='PRECOMPUTED_BINS_BOUNDED',
                release='BLOCKED',qualified=False, precision_digits=precision,
                input_hz=op.input_hz,output_hz=op.output_hz,
                snapshot_sha256=sha_file(snapshot),
                source_sha256=binding['source_sha256'],fft_stages=rows,
                limitations='Exact realized coefficient-bin error bound, NOT FFT4G generic or full-chain execution roundoff')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot',type=Path,default=DEFAULT/'88200-48000'/'stage-snapshot.json')
    p.add_argument('--precision',type=int,default=80)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=certificate(a.snapshot,precision=a.precision)
    if a.output:
        content=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n'
        if a.output.exists():
            if a.output.read_text()!=content:
                raise CertificateError('refusing to overwrite different FFT interval evidence')
        else:
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(content)
    print(json.dumps({'status':result['status'],'rate_pair':[
        result['input_hz'],result['output_hz']],
        'max_complex_bin_deviation':[s['max_complex_bin_deviation'] for s in result['fft_stages']],
        'worst_single_impulse_bin_realization_bound':[
           s['worst_single_impulse_bin_realization_bound'] for s in result['fft_stages']]},sort_keys=True))

if __name__=='__main__':main()
