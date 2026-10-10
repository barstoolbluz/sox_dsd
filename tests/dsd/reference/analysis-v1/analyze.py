"""Frozen analysis-v1 decoder and metrology; independent of production SoX.

No tuning, automatic window choice, threshold fallbacks, or coefficient
regeneration is possible in this module. Coefficient files are SHA-checked on
load. FFT overlap/add computes the linear convolution then exact decimation;
the integer FIR group delay is removed before any time-domain fitting.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy import fft

HERE = Path(__file__).resolve().parent
OUTPUT_RATE = 88200
WINDOW = (0.35875, 0.48829, 0.14128, 0.01168)


def manifest():
    m = json.loads((HERE/'manifest.json').read_text())
    assert m['id'] == 'analysis-v1' and m['status'] == 'frozen'
    return m


def fir(rate):
    item = next((r for r in manifest()['records'] if r['rate_hz'] == rate), None)
    if item is None: raise ValueError(f'unsupported native analysis rate {rate}')
    raw = (HERE/item['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('frozen analysis coefficient hash mismatch')
    h = np.frombuffer(raw, dtype='<f8')
    if h.size != item['num_taps'] or not np.array_equal(h, h[::-1]):
        raise ValueError('frozen analysis filter length or symmetry mismatch')
    if rate % OUTPUT_RATE or item['delay_native_frames'] != (h.size-1)//2:
        raise ValueError('frozen analysis rate/delay metadata mismatch')
    return h, item


def decode_packed(path, frames, rate, *, block=262144):
    """Full-convolution FFT overlap-add into only the exact decimated points.

    Native bit 1 is +1. Last partial native byte must not be analyzed as audio.
    n_out = ceil(N_native / integer decimation factor), even at odd lengths.
    """
    h, info = fir(rate)
    factor = info['decimation_factor']
    if block <= 0 or block % 8: raise ValueError('block must be positive multiple of 8')
    if frames < 0 or Path(path).stat().st_size != (frames+7)//8:
        raise ValueError('invalid packed length')
    count = (frames+factor-1)//factor
    out = np.zeros(count, dtype=np.float64)
    if not frames: return out
    payload = np.memmap(path, dtype=np.uint8, mode='r')
    nfft = fft.next_fast_len(block+h.size-1)
    H = fft.rfft(h, nfft)
    delay = info['delay_native_frames']
    for offset in range(0, frames, block):
        length = min(block, frames-offset)
        byte_start = offset//8
        byte_stop = (offset+length+7)//8
        bits = np.unpackbits(payload[byte_start:byte_stop], bitorder='big')[:length]
        signal = np.asarray(bits, dtype=np.float64)*2.0 - 1.0
        y = fft.irfft(fft.rfft(signal, nfft)*H, nfft)[:length+h.size-1]
        first = max(0, (offset-delay+factor-1)//factor)
        last = min(count, (offset+len(y)-1-delay)//factor+1)
        if last > first:
            indices = (delay + np.arange(first,last,dtype=np.int64)*factor-offset)
            out[first:last] += y[indices]
    return out


def bh4(n):
    i = np.arange(n, dtype=np.float64)
    a0,a1,a2,a3 = WINDOW
    angle = 2*np.pi*i/n
    w = a0 - a1*np.cos(angle) + a2*np.cos(2*angle) - a3*np.cos(3*angle)
    return w, n*float(np.dot(w,w))/float(np.sum(w)**2)


def band_power(y, rate=OUTPUT_RATE, lo=20., hi=20000., window='blackman-harris-4'):
    samples = np.asarray(y,dtype=np.float64)
    n = samples.size
    if n < 16 or not np.all(np.isfinite(samples)):
        raise ValueError('nonfinite/insufficient samples')
    if not 0 <= lo < hi <= rate/2: raise ValueError('invalid integration band')
    if window == 'blackman-harris-4':
        w,enbw = bh4(n)
    elif window == 'rectangular':
        w,enbw = np.ones(n),1.
    else: raise ValueError('invalid frozen window')
    spectrum = fft.rfft(samples*w)
    freqs = fft.rfftfreq(n,1./rate)
    twice = np.full(spectrum.size,2.); twice[0] = 1.
    if n%2 == 0: twice[-1] = 1.
    selected=(freqs>=lo)&(freqs<=hi)
    power=float(np.sum((np.abs(spectrum[selected])**2)*twice[selected])/(n*np.dot(w,w)))
    return dict(power=power,dbfs=(10*math.log10(power/.5) if power else None),
                enbw_bins=enbw, window=window, low_hz=lo, high_hz=hi)


def fit(y, frequency_hz, *, rate=OUTPUT_RATE, window='rectangular'):
    """Weighted LS is fixed per caller's declared coherent/noncoherent case.

    Residual keeps harmonic distortion, and the power integration does not
    remove it. Phase convention is +sin(2*pi*f*t+phase).
    """
    x=np.asarray(y,dtype=np.float64)
    if x.size < 16 or not np.all(np.isfinite(x)) or not 0<frequency_hz<rate/2:
        raise ValueError('invalid tone vector')
    if window=='rectangular':
        if abs(x.size*frequency_hz/rate-round(x.size*frequency_hz/rate))>1e-9:
            raise ValueError('rectangular requires coherent aligned integer cycles')
        weights=np.ones(x.size)
    elif window=='blackman-harris-4':weights,_=bh4(x.size)
    else:raise ValueError('invalid fit window')
    theta=2*np.pi*(frequency_hz/rate)*np.arange(x.size)
    basis=np.column_stack((np.ones(x.size),np.sin(theta),np.cos(theta)))
    a=basis*weights[:,None]
    coef=np.linalg.solve(basis.T@a,a.T@x)
    dc, sine, cosine=map(float,coef)
    peak=math.hypot(sine,cosine)
    residual=x-basis@coef
    return dict(dc=dc,amplitude=peak,phase_rad=math.atan2(cosine,sine),
                fitted_power=.5*peak**2,residual=residual)


def measure(audio, frequency, expected_modulator_peak, *, window='rectangular'):
    r=fit(audio,frequency,window=window)
    residual=band_power(r['residual'], window=window)
    fitted=r['fitted_power']
    if fitted<=0:raise ValueError('nonpositive fitted signal power')
    harmonics=[]
    harmonic_basis=[]
    for k in range(2,int(20000//frequency)+1):
        t=2*np.pi*k*frequency*np.arange(len(audio))/OUTPUT_RATE
        harmonic_basis.extend((np.sin(t),np.cos(t)))
    if harmonic_basis:
        harmonics=np.asarray(harmonic_basis).T
        # Determine harmonic distortion AFTER removing only fundamental/DC;
        # this fit is diagnostic, never subtracted from THD+N.
        coeff=np.linalg.lstsq(harmonics,r['residual'],rcond=None)[0]
        hp=float(np.sum(coeff**2)*.5)
    else:hp=0.
    snr=10*math.log10(fitted/residual['power']) if residual['power']>0 else None
    return dict(fitted_modulator_peak=r['amplitude'], phase_rad=r['phase_rad'],
                dc=r['dc'], gain_error_db=20*math.log10(r['amplitude']/expected_modulator_peak),
                fitted_dbfs=10*math.log10(fitted/.5),
                residual_band_dbfs=residual['dbfs'], residual_band_power=residual['power'],
                thdn_db=10*math.log10(residual['power']/fitted) if residual['power']>0 else None,
                snr_db=snr, thd_only_diagnostic_db=(10*math.log10(hp/fitted) if hp else None),
                residual_definition='DC+fundamental removed, all harmonics RETAINED',
                window=window, enbw_bins=residual['enbw_bins'])


def steady_segment(pcm, rate):
    h,_=fir(rate)
    trim=max(int(math.ceil(.25*OUTPUT_RATE)),
             int(math.ceil(2*(len(h)-1)*OUTPUT_RATE/rate)))
    if pcm.size - 2*trim < OUTPUT_RATE:
        raise ValueError('not enough steady audio after two-sided frozen trim')
    # Exactly one measured second, integer cycles for 997/1000 Hz.
    return pcm[trim:trim+OUTPUT_RATE], dict(trim_each_edge_samples=trim,
                                            retained_samples=OUTPUT_RATE,
                                            total_samples=int(pcm.size))
