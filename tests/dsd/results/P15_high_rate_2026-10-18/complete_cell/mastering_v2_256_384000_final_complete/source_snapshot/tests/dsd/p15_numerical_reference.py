#!/usr/bin/env python3
"""P15 independent finite DSD/PCM reference; no production SRC or ring code.

FIR: exact binary64 coefficient values from the pinned C hex banks, composed
as a dilated polynomial at 75 decimal digits, then directly convolved with
finite numeric input. Selected frames are checked again at 75 digits.

SRC: *separately designed* 180 dB Kaiser-windowed-sinc fractional resampler.
The output is computed by explicit rational polyphase indexing and finite
zero extension, not via scipy.signal.resample_poly or SoX rate.c. Long-double
accumulation is independently checked by 75-digit sums at selected outputs.
The window/cutoff are independent engineering reference choices, NOT claimed
identical to SoX's distinct multistage SRC; filter differences at endpoints
and transition bands must be reported, not mislabelled FIR roundoff.
"""
from __future__ import annotations

from functools import lru_cache
from fractions import Fraction
import hashlib
import json
import math
import re
from pathlib import Path

import mpmath as mp
import numpy as np
from scipy.special import i0

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'tests/dsd/reference/p06_coefficients.json'
BANKS = ROOT / 'src/dsd_coeffs.h'
V2_MANIFEST = ROOT / 'tests/dsd/reference/p15_r3_coefficients.json'
V2_BANKS = ROOT / 'src/dsd_coeffs_v2.h'
MP_DIGITS = 75
KAISER_BETA = 18.9
RATIO_TAPS = 401
CUTOFF_NYQUIST_FRACTION = 0.975


def reference_input_hashes(matrix: str = 'v1') -> dict[str, str]:
    if matrix not in ('v1', 'v2'):
        raise ValueError('invalid reference matrix')
    paths = (Path(__file__), BANKS, MANIFEST)
    if matrix == 'v2':
        paths += (V2_BANKS, V2_MANIFEST)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def profile_name(profile: str, native: int) -> str:
    if native not in (2822400, 5644800, 11289600):
        raise ValueError('unsupported native DSD rate')
    if profile == 'mastering_v2':
        return f'decode.mastering.v2.dsd{native//44100}'
    if profile in ('mastering', 'wideband'):
        return ('master' if profile == 'mastering' else 'wide')+str(native//44100)
    raise ValueError('unknown metrology profile: ' + profile)


def bank_data_for_profile(profile: str) -> tuple[dict, dict]:
    return bank_data('v2' if profile.startswith('decode.mastering.v2.dsd') else 'v1')


@lru_cache(maxsize=2)
def bank_data(matrix: str = 'v1') -> tuple[dict, dict]:
    # Read the independently authored exact C hexadecimal bank words, never
    # the candidate's coefficient generator. P06's halfband is shared unchanged.
    from certify_filters import load_coefficients
    if matrix not in ('v1', 'v2'):
        raise ValueError('invalid reference matrix')
    banks = load_coefficients()
    p06 = json.loads(MANIFEST.read_text())
    for name, values in banks.items():
        digest = hashlib.sha256(('\n'.join(x.hex() for x in values)+'\n').encode()).hexdigest()
        if p06['banks'][name]['rounded_hex_sha256'] != digest:
            raise ValueError('P06 certified coefficient/manifest discrepancy: ' + name)
        if len(values) != p06['banks'][name]['length'] or not np.array_equal(values,values[::-1]):
            raise ValueError('P06 coefficient symmetry/length mismatch: ' + name)
    if matrix == 'v1':
        return p06, banks
    obj = json.loads(V2_MANIFEST.read_text())
    if obj.get('schema') != 'sox-ng/p15-r3-coefficients/1' or len(obj.get('profiles', {})) != 3:
        raise ValueError('invalid P15-R3 v2 reference manifest')
    code = V2_BANKS.read_text()
    for name, details in obj['banks'].items():
        match = re.search(r'\blsx_dsd_coeff_'+re.escape(name)+r'\[(\d+)\]\s*=\s*\{(.*?)\};',
                          code, re.S)
        if match is None:
            raise ValueError('missing P15 v2 production C bank: ' + name)
        values = np.array([float.fromhex(w.strip()) for w in match.group(2).split(',')
                           if w.strip()], dtype=np.float64)
        digest = hashlib.sha256(('\n'.join(x.hex() for x in values)+'\n').encode()).hexdigest()
        if (len(values) != int(match.group(1)) or len(values) != details['length'] or
            digest != details['rounded_hex_sha256'] or
            not np.array_equal(values, values[::-1])):
            raise ValueError('P15 v2 production coefficient/manifest discrepancy: ' + name)
        banks[name] = values
    return obj, banks


@lru_cache(maxsize=9)
def equivalent_exact(profile: str) -> tuple[tuple, int, int]:
    """75-digit composition from *exact binary64* certified bank inputs.

    Unlike a 75-digit sum of previously rounded longdouble cascade taps, this
    retains the full original 75-digit multi-stage polynomial for independent
    witness values and roundoff attribution. The public numerical reference
    intentionally uses a separate longdouble reduction of these exact taps.
    """
    manifest, banks = bank_data_for_profile(profile)
    meta = manifest['profiles'][profile]
    delay, down = meta['delay_native_frames'], meta['factor']
    with mp.workdps(MP_DIGITS):
        taps = [mp.mpf(1)]
        for stage, name in enumerate(meta['stage_banks']):
            width = 1 << stage
            h = [mp.mpf(float(t)) for t in banks[name]]
            next_taps = [mp.mpf(0)] * (len(taps) + (len(h)-1)*width)
            for j, value in enumerate(h):
                if not value:
                    continue
                start = j*width
                for k, coeff in enumerate(taps):
                    if coeff:
                        next_taps[start+k] += value*coeff
            taps = next_taps
        if len(taps) != 2*delay+1:
            raise ValueError('equivalent FIR group delay mismatch')
        dc = mp.fsum(taps)
        if abs(dc-1) > mp.mpf('1e-13'):
            raise ValueError('equivalent FIR is not unity DC')
    return tuple(taps), delay, down


@lru_cache(maxsize=9)
def equivalent(profile: str) -> tuple[np.ndarray, tuple, int, int]:
    """Longdouble vector made from the independently composed 75-digit taps."""
    manifest, _ = bank_data_for_profile(profile)
    taps,delay,down=equivalent_exact(profile)
    coeff=np.array([np.longdouble(mp.nstr(t,45)) for t in taps],dtype=np.longdouble)
    return coeff, tuple(manifest['profiles'][profile]['stage_banks']), delay, down


def front_end(bits: np.ndarray, profile: str) -> np.ndarray:
    """Direct finite convolution and exact ceil(N/D) centered output count."""
    b = np.asarray(bits,dtype=np.uint8)
    if b.ndim != 1 or np.any(b > 1):
        raise ValueError('front-end accepts chronological one-bit 0/1 arrays only')
    h, _, delay, down = equivalent(profile)
    n = len(b)
    out = np.empty((n+down-1)//down, dtype=np.longdouble)
    x = 2*b.astype(np.int16)-1
    for m in range(len(out)):
        center = delay+m*down
        lo = max(0,center+1-len(h)); hi = min(n,center+1)
        idx = center-np.arange(lo,hi,dtype=np.int64)
        out[m] = np.dot(h[idx], x[lo:hi].astype(np.longdouble))
    return out


def front_end_impulse(length: int, profile: str, at: int) -> np.ndarray:
    """Unit linear impulse (from half the delta of paired genuine one-bit inputs)."""
    if not 0 <= at < length:
        raise ValueError('impulse outside stream')
    h, _, delay, down = equivalent(profile)
    centers = delay + np.arange((length+down-1)//down,dtype=np.int64)*down
    at_h = centers-at
    values = np.zeros(len(at_h),dtype=np.longdouble)
    inside = (at_h>=0) & (at_h<len(h))
    values[inside] = h[at_h[inside]]
    return values


def front_mp_witness(bits: np.ndarray, profile: str, indexes: tuple[int,...]) -> dict:
    """Direct 75-digit convolution of exact binary64 bank-composed taps.

    The high-precision witness never substitutes the rounded longdouble
    equivalent taps into the mpmath summation; that would fail to exercise the
    true full-precision cascade. Both coefficient quantization and reduction
    error are measured against the same original rounded C hex constants.
    """
    data = np.asarray(bits,dtype=np.uint8)
    mp_taps,delay,down = equivalent_exact(profile)
    full = front_end(data,profile)
    rows = []
    with mp.workdps(MP_DIGITS):
        for m in sorted(set(indexes)):
            if not 0 <= m < len(full):
                continue
            center = delay+m*down
            lo = max(0,center+1-len(mp_taps));hi = min(len(data),center+1)
            exact = mp.fsum(mp_taps[center-k] * (1 if data[k] else -1)
                            for k in range(lo,hi))
            ld = mp.mpf(str(full[m]))
            rows.append(dict(frame=m, exact_75digit=mp.nstr(exact,38),
                             longdouble_vs_75digit_abs=float(abs(exact-ld))))
    return dict(precision_digits=MP_DIGITS,witnesses=rows)


def pair_ratio(source_hz: int, target_hz: int) -> tuple[int,int]:
    if source_hz <= 0 or target_hz <= 0:
        raise ValueError('invalid clocks')
    ratio = Fraction(target_hz, source_hz)
    return ratio.numerator, ratio.denominator


@lru_cache(maxsize=32)
def rational_taps(up: int, down: int) -> np.ndarray:
    """Independent symmetrical Kaiser-sinc low-pass at the upsampled clock."""
    if not (1 <= up <= 10000 and 1 <= down <= 10000 and math.gcd(up,down)==1):
        raise ValueError('unreduced or unreasonably large SRC ratio')
    high = max(up,down)
    length = RATIO_TAPS*high+1
    if length % 2 == 0:
        length += 1
    radius = (length-1)//2
    # Always use an odd tap count. The full Kaiser argument is symmetric.
    position = np.arange(-radius,radius+1,dtype=np.float64)
    window = i0(KAISER_BETA*np.sqrt(np.maximum(0.,1.-(position/radius)**2))) / i0(KAISER_BETA)
    h = (CUTOFF_NYQUIST_FRACTION/high)*np.sinc(
        position*(CUTOFF_NYQUIST_FRACTION/high))*window
    h = h / np.sum(h,dtype=np.longdouble)
    if h.size != 2*radius+1 or not np.array_equal(h,h[::-1]):
        raise AssertionError('independent FIR symmetry')
    return h.astype(np.longdouble)


def polyphase(values: np.ndarray, source_hz: int, target_hz: int,
              *, output_count: int | None = None) -> np.ndarray:
    """Finite rational resampler with exact integer output coordinates.

    For output m, t = m * down / up in input-frame units. Zero-extend the
    finite input; only source i for which |m*down - i*up| <= radius can matter.
    This directly evaluates the zero-insertion/kernel-convolution/decimation
    expression, independent of scipy.signal.upfirdn/resample_poly.
    """
    src = np.asarray(values,dtype=np.longdouble)
    if src.ndim != 1 or not np.all(np.isfinite(src)):
        raise ValueError('invalid resampler samples')
    if source_hz==target_hz:
        # The centered native cascade produces ceil(N/D) samples, but the
        # original-native timeline fixes N_out=round(N*F_out/F_native).
        # At tiny/non-multiple-of-D lengths these differ by one even when
        # the SRC is bypassed. Preserve the native count rule by trimming the
        # *final* centered sample; never fabricate data or add a silent frame.
        if output_count is None:
            return src.copy()
        if not 0 <= output_count <= len(src):
            raise ValueError('identity SRC original-timeline count mismatch')
        return src[:output_count].copy()
    up, down = pair_ratio(source_hz,target_hz)
    h = rational_taps(up,down)
    radius = (len(h)-1)//2
    n = (len(src)*up+down-1)//down if output_count is None else output_count
    if n < 0 or n > (1<<26):
        raise ValueError('unreasonable SRC output count')
    out = np.zeros(n,dtype=np.longdouble)
    for m in range(n):
        t = m*down
        lo = max(0,(t-radius+up-1)//up)
        hi = min(len(src), (t+radius)//up + 1)
        if hi>lo:
            ix = np.arange(lo,hi,dtype=np.int64)
            out[m] = up*np.dot(src[lo:hi],h[radius+t-ix*up])
    return out


def polyphase_mp_witness(values: np.ndarray, source_hz: int, target_hz: int,
                         output_frames: int, indexes: tuple[int,...]) -> dict:
    """75-digit accumulation of exact *reference* FIR and sample values.

    The high-precision sum verifies the independent polyphase indexing and
    longdouble accumulation; it does not claim that its Kaiser window is the
    byte-exact private production SRC filter. Separately verify selected
    window taps against mpmath's I0 and sinc constructions.
    """
    if source_hz==target_hz:
        return dict(precision_digits=MP_DIGITS, witnesses=[],window_witnesses=[])
    src=np.asarray(values,dtype=np.longdouble)
    up,down=pair_ratio(source_hz,target_hz)
    h=rational_taps(up,down);radius=(len(h)-1)//2
    calculated=polyphase(src,source_hz,target_hz,output_count=output_frames)
    rows=[]
    with mp.workdps(MP_DIGITS):
        for m in sorted(set(indexes)):
            if not 0<=m<output_frames:
                continue
            t=m*down
            lo=max(0,(t-radius+up-1)//up)
            hi=min(len(src),(t+radius)//up+1)
            result=mp.fsum(mp.mpf(str(src[j]))*mp.mpf(str(h[radius+t-j*up]))
                           for j in range(lo,hi))*up
            rows.append(dict(output_frame=m, longdouble_vs_75digit_abs=float(
                abs(result-mp.mpf(str(calculated[m]))))))
        window_witness=[]
        for k in sorted({0,radius//3,radius,radius+radius//3,2*radius}):
            pos=k-radius
            beta=mp.mpf(str(KAISER_BETA))
            frac=mp.mpf(pos)/radius
            sinc_arg=mp.mpf(str(CUTOFF_NYQUIST_FRACTION))/max(up,down)*pos
            sinc=mp.sin(mp.pi*sinc_arg)/(mp.pi*sinc_arg) if sinc_arg else mp.mpf(1)
            unnorm=(mp.mpf(str(CUTOFF_NYQUIST_FRACTION))/max(up,down))*sinc*(
                mp.besseli(0,beta*mp.sqrt(1-frac*frac))/mp.besseli(0,beta))
            # Window coefficients are normalized with the total discrete sum;
            # checking the unnormalized numerator catches indexing and cutoff.
            window_witness.append(dict(index=k, high_precision_unnormalized=mp.nstr(unnorm,25)))
    return dict(precision_digits=MP_DIGITS,witnesses=rows,
                window_witnesses=window_witness)


def reference(bits: np.ndarray, profile: str, native_hz: int,
              pcm_hz: int, *, impulse_at: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    manifest,_=bank_data_for_profile(profile)
    meta=manifest['profiles'][profile]
    if meta['native_hz']!=native_hz:
        raise ValueError('profile/native mismatch')
    if impulse_at is None:
        mid=front_end(bits,profile)
        native_len=len(bits)
    else:
        native_len=len(bits)
        mid=front_end_impulse(native_len,profile,impulse_at)
    final=(native_len*pcm_hz+native_hz//2)//native_hz
    return mid, polyphase(mid,meta['intermediate_hz'],pcm_hz,output_count=final)


def fir_roundoff_bound(profile: str) -> float:
    meta,banks=bank_data_for_profile(profile)
    names=meta['profiles'][profile]['stage_banks']
    return (16*(2.**-52)*sum(len(banks[n]) for n in names)*
            math.prod(float(np.sum(np.abs(banks[n]),dtype=np.longdouble)) for n in names))


def src_design_metadata(source_hz: int, target_hz: int) -> dict:
    if source_hz==target_hz:
        return dict(type='identity',input_hz=source_hz,output_hz=target_hz)
    up,down=pair_ratio(source_hz,target_hz)
    taps=rational_taps(up,down)
    return dict(type='independently-designed-rational-polyphase-kaiser-sinc',
                input_hz=source_hz,output_hz=target_hz,up=up,down=down,
                taps=len(taps),beta=KAISER_BETA,cutoff_fraction=CUTOFF_NYQUIST_FRACTION,
                hashed_binary64_taps=hashlib.sha256(
                    np.asarray(taps,dtype='<f8').tobytes()).hexdigest(),
                zero_extension='numeric',alignment='zero-centered first output',
                accumulation='numpy.longdouble with sampled 75-digit check')
