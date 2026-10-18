#!/usr/bin/env python3
"""Independent P06 certification of final C hexadecimal coefficient bytes.

No dependency on the generator or the feasibility NPZ.  Search bank extrema
using derivative bracketing/refinement, then independently re-evaluate winning
extrema with mpmath.  For composites search the complete native Nyquist stop
region and coherent sums over EVERY alias image, not merely the final stage.
Short samples are refined adaptively; the full scan is also retained.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import re
import sys
import time

try:
    import mpmath as mp
    import numpy as np
    from scipy import optimize, signal
except ImportError as error:
    print(f"UNRUN required DSD filter certification (missing {error.name})", file=sys.stderr)
    raise SystemExit(2) from None

ROOT = pathlib.Path(__file__).resolve().parents[2]
mp.mp.dps = 75
ALIASES = ('halfband', 'master64_256', 'master128', 'wideband')


def load_coefficients():
    text = (ROOT/'src/dsd_coeffs.h').read_text()
    banks = {}
    for name in ALIASES:
        found = re.search(r'\blsx_dsd_coeff_'+name+r'\[(\d+)\]\s*=\s*\{(.*?)\};', text, re.S)
        if found is None:
            raise AssertionError('bank missing from production header: ' + name)
        h = np.array([float.fromhex(w.strip()) for w in found.group(2).split(',') if w.strip()], dtype=np.float64)
        assert len(h) == int(found.group(1))
        banks[name] = h
    return banks


def eq_real(h, f):
    # Independently fold a symmetric FIR into real zero-phase cosine terms.
    mid = len(h)//2
    fc = np.asarray(f)
    return np.polynomial.chebyshev.chebval(np.cos(2*np.pi*fc),
            np.concatenate(([h[mid]], 2*h[mid+1:])))


def eq_derivative(h, f):
    mid = len(h)//2
    k = np.arange(1, mid+1)
    return -4*np.pi*np.sum((k*h[mid+1:]) * np.sin(2*np.pi*np.asarray(f)[...,None]*k), axis=-1)


def hp_response(h, cyc):
    # mpmath consumes exact IEEE-754 values, not rounded decimal re-encoding.
    q = mp.mpf(float(cyc))
    mid = len(h)//2
    return mp.mpf(float(h[mid]))+2*mp.fsum(
        mp.mpf(float(h[mid+k]))*mp.cos(2*mp.pi*k*q) for k in range(1,mid+1))


def bank_extrema(h, lo, hi):
    xx = np.linspace(lo, hi, 16385)
    der = eq_derivative(h, xx)
    pts = [lo, hi]
    for k in range(len(xx)-1):
        if der[k] == 0:
            pts.append(float(xx[k]))
        elif (der[k] < 0) != (der[k+1] < 0):
            pts.append(float(optimize.brentq(lambda f:eq_derivative(h, f),xx[k],xx[k+1],xtol=5e-16)))
    evaluated = [(float(x), float(abs(hp_response(h,x)))) for x in pts]
    return max(evaluated, key=lambda r: r[1]), len(pts), float(np.max(np.abs(eq_real(h,xx))))


def response(banks, names, fs, frequencies):
    f = np.asarray(frequencies)
    r = np.ones_like(f, dtype=np.float64)
    for j, name in enumerate(names):
        r *= eq_real(banks[name], f/(fs/(1<<j)))
    return r


def hp_composite(banks, names, fs, f):
    r = mp.mpf(1)
    for j,name in enumerate(names):
        r *= hp_response(banks[name],float(f)/(fs/(1<<j)))
    return r


def adaptive_max(fun, low, high, steps, refinement=20):
    xx = np.linspace(low, high, steps+1)
    yy = np.asarray(fun(xx), dtype=float)
    # All local maxima are bracketed; refine the strongest even if sampling
    # aliases a lobe. A second half-cell shifted grid detects missed narrow maxima.
    peaks, _ = signal.find_peaks(yy)
    indexes = set(peaks.tolist()+[0, steps])
    for i in np.argsort(yy)[-refinement:]:
        indexes.add(int(i))
    evaluated = [(float(xx[i]),float(yy[i])) for i in indexes]
    candidates = sorted(indexes,key=lambda i:float(yy[i]),reverse=True)[:max(refinement,12)]
    for i in candidates:
        l = max(0,i-1); r = min(steps,i+1)
        if l == r: continue
        fit = optimize.minimize_scalar(lambda z:-float(fun(z)),bounds=(float(xx[l]),float(xx[r])),
                method='bounded',options={'xatol':max(1e-12, (high-low)*1e-12)})
        evaluated.append((float(fit.x),-float(fit.fun)))
    return max(evaluated,key=lambda item:item[1]),dict(grid_points=len(xx),
        localized_extrema=len(peaks),optimized_candidates=len(candidates),
        grid_max=float(yy.max()))


def db(x):
    return 20*math.log10(max(float(x),1e-300))


def validate_banks(banks, manifest):
    results = {}
    for name, h in banks.items():
        meta = manifest['banks'][name]
        p, s = meta['pass_cycles_per_input'],meta['stop_cycles_per_input']
        assert len(h) == meta['length'] and len(h)%4 == 1
        assert np.array_equal(h,h[::-1]),name+' asymmetry'
        assert abs(float(np.sum(h,dtype=np.longdouble))-1)<2e-15
        assert meta['rounded_hex_sha256'] == hashlib.sha256(('\n'.join(v.hex() for v in h)+'\n').encode()).hexdigest()
        if name == 'halfband':
            mid=len(h)//2
            assert h[mid] == 0.5
            assert all(h[i] == 0 for i in range(len(h)) if i!=mid and (i-mid)%2==0)
        pp, pn, pg = bank_extrema(h,0,p)
        ss, sn, sg = bank_extrema(h,s,.5)
        # Passband ripple includes gain below and above unity, not maximum gain only.
        # Scan derivative extrema to find min separately.
        frequencies=np.linspace(0,p,16385)
        der=eq_derivative(h,frequencies)
        pts=[0,p]
        for k in range(len(der)-1):
            if (der[k]<0)!=(der[k+1]<0):
                pts.append(float(optimize.brentq(lambda f:eq_derivative(h,f),frequencies[k],frequencies[k+1],xtol=5e-16)))
        deviations=[abs(db(abs(hp_response(h,t)))) for t in pts]
        ripple=max(deviations)
        stop_db=db(ss[1])
        results[name] = dict(taps=len(h),sha256=meta['rounded_hex_sha256'],
            pass_ripple_db=ripple,pass_extrema_checked=len(pts),
            stop_max_db=stop_db,stop_peak_cycles_per_input=ss[0],
            stop_extrema_checked=sn, dense_grid_stop_max_db=db(sg),
            hp_stop_peak_amplitude=mp.nstr(hp_response(h,ss[0]),20),
            pass_grid_peak_gain_db=db(pg),passes=ripple<=0.0001 and stop_db<=-185.0)
        if not results[name]['passes']:
            raise AssertionError(f'{name} violates bank envelope: {results[name]}')
    return results


def validate_composites(banks, manifest, steps):
    results={}
    for name, meta in manifest['profiles'].items():
        fs = meta['native_hz']; R=meta['intermediate_hz']; D=meta['factor']; P=meta['pass_hz'];S=meta['stop_hz']; names=meta['stage_banks']
        assert len(names) == D.bit_length()-1
        assert fs == R*D
        ppeak, pdetail=adaptive_max(lambda f:np.abs(20*np.log10(np.maximum(np.abs(response(banks,names,fs,f)),1e-300))),0,P,steps)
        stoppeak,sdetail=adaptive_max(lambda f:np.abs(response(banks,names,fs,f)),S,fs/2,steps)
        # Image amplitudes add coherently (conservative phase-independent bound).
        # k=1..D-1 at every given baseband f: not only adjacent Nyquist images.
        def aliased(f):
            f=np.asarray(f)
            acc=np.zeros_like(f,dtype=float)
            for k in range(1,D):
                acc += np.abs(response(banks,names,fs,f+k*R))
            return acc
        apeak,adetail=adaptive_max(aliased,0,P,max(2048,steps//8),refinement=16)
        # Incoherent flat-power sum, deliberately distinct from coherent bound.
        x=np.linspace(0,P,1025)
        flat=np.zeros_like(x)
        shaped=np.zeros_like(x)
        for k in range(1,D):
            freq = x + k*R
            transfer = response(banks,names,fs,freq)
            flat += transfer**2
            shaped += transfer**2*(freq/(fs/2))**4
        noise_flat = db(math.sqrt(float(np.max(flat))))
        noise_shaped=db(math.sqrt(float(np.max(shaped))))
        # Independent 75-digit evaluation of final C hex values at maxima.
        highp=db(abs(hp_composite(banks,names,fs,ppeak[0])))
        highs=db(abs(hp_composite(banks,names,fs,stoppeak[0])))
        higha=db(mp.fsum(abs(hp_composite(banks,names,fs,apeak[0]+k*R)) for k in range(1,D)))
        profile=dict(native_hz=fs,intermediate_hz=R,factor=D,pass_hz=P,stop_hz=S,
            stage_banks=names,delay_native_frames=meta['delay_native_frames'],
            phase_native_frames=meta['phase_native_frames'],discard_frames=meta['discard_output_frames'],
            pass_ripple_db=ppeak[1],stop_max_db=db(stoppeak[1]),
            coherent_alias_sum_db=db(apeak[1]),
            high_precision_ripple_db=highp, high_precision_stop_db=highs,
            high_precision_alias_db=higha,
            worst_pass_hz=ppeak[0],worst_stop_hz=stoppeak[0],worst_alias_base_hz=apeak[0],
            incoherent_flat_image_sum_db=noise_flat,
            synthetic_f4_noise_weighted_image_db=noise_shaped,
            adaptive_extrema=dict(passband=pdetail,stopband=sdetail,alias=adetail),
            passes=ppeak[1]<=.0001 and db(stoppeak[1])<=-160 and db(apeak[1])<=-160)
        results[name]=profile
        if not profile['passes']:
            raise AssertionError('composite violates envelope: '+name+' '+repr(profile))
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P06/numeric')
    ap.add_argument('--grid',type=int,default=8192)
    args=ap.parse_args()
    manifest=json.loads((ROOT/'tests/dsd/reference/p06_coefficients.json').read_text())
    banks=load_coefficients()
    start=time.monotonic()
    bank_results=validate_banks(banks,manifest)
    profile_results=validate_composites(banks,manifest,args.grid)
    report={'schema':'sox-ng/p06-certificate/1',
        'input':'src/dsd_coeffs.h, parsed C99 hex, not feasibility NPZ',
        'method':'derivative-root bracketing for banks, adaptive local optimization for composite extrema, 75-digit verification at peaks, all coherent images',
        'numeric_precision':'IEEE binary64 hex source; 75-digit mpmath extrema checks',
        'limitations':'dense searches and local extrema refinements are independent high-precision numerical evidence, not an interval-arithmetic exhaustive mathematical proof',
        'coherent_images':'sum(abs(H_eq(f+k*R)),k=1..D-1)',
        'synthetic_noise_psd':'f^4 weighting normalized to unity at native Nyquist; illustration, not measured recording noise',
        'elapsed_seconds':time.monotonic()-start, 'banks':bank_results,'profiles':profile_results,
        'summary':{'banks_passed':sum(x['passes'] for x in bank_results.values()),
          'profiles_passed':sum(x['passes'] for x in profile_results.values()),'failed':0}}
    args.results.mkdir(parents=True,exist_ok=True)
    (args.results/'filter-certificate.json').write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['summary'])+' '+f'{report["elapsed_seconds"]:.1f}s')
    for name,x in profile_results.items():
        print(name,f'pass {x["pass_ripple_db"]:.3e} dB; stop {x["stop_max_db"]:.3f} dB; alias {x["coherent_alias_sum_db"]:.3f} dB; HP stop {x["high_precision_stop_db"]:.3f} dB')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
