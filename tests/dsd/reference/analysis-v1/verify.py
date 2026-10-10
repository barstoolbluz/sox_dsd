#!/usr/bin/env python3
"""Analysis-v1 acceptance independent from source coefficients and SoX output."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import numpy as np
from scipy import fft, signal
from analyze import fir, band_power, fit, bh4, decode_packed, manifest


def response(rate):
    h,info=fir(rate)
    nfft=2**21
    spectrum=fft.rfft(h,nfft)
    freq=fft.rfftfreq(nfft,1/rate)
    passband=np.abs(spectrum[freq<=20000])
    stopband=np.abs(spectrum[freq>=24000])
    worst_pass=max(abs(20*math.log10(float(passband.min()))),
                   abs(20*math.log10(float(passband.max()))))
    worst_stop=20*math.log10(float(stopband.max()))
    if worst_pass>0.00001 or worst_stop> -180:
        raise AssertionError(f'filter envelope {rate}: pass={worst_pass}, stop={worst_stop}')
    return dict(rate_hz=rate,taps=int(h.size),passband_max_abs_db=worst_pass,
                worst_stopband_db=worst_stop, group_delay_native=info['delay_native_frames'],
                dc_sum=float(np.sum(h)), frequency_bins=nfft//2+1)


def pulse_count(rate):
    h,info=fir(rate)
    factor=info['decimation_factor']
    results=[]
    # Independent direct dot product at output positions on each impulse case;
    # exercise exact native tail counts, not just full-block boundaries.
    for n in (0,1,factor-1,factor,factor+1,2*factor+9,513):
        rng=np.random.default_rng(3817+n)
        bits=rng.integers(0,2,n,dtype=np.uint8)
        packed=np.packbits(bits,bitorder='big')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bits.bin';path.write_bytes(packed.tobytes())
            pcm=decode_packed(path,n,rate,block=1024)
        assert len(pcm)==(n+factor-1)//factor
        x=bits.astype(np.float64)*2-1
        for k,observed in enumerate(pcm):
            # Convolution at delay+k*factor with out-of-range zero extension.
            pos=info['delay_native_frames']+k*factor
            lo=max(0,pos-(h.size-1))
            hi=min(n,pos+1)
            expected=float(np.dot(x[lo:hi], h[pos-np.arange(lo,hi)]))
            if not abs(observed-expected)<2e-12:
                raise AssertionError((rate,n,k,observed,expected))
        results.append(dict(frames=n, output_samples=len(pcm)))
    return dict(rate_hz=rate, count_cases=results)


def signal_fits():
    rate=88200
    t=np.arange(rate,dtype=np.float64)/rate
    coherent=.37+ .33*np.sin(2*np.pi*1000*t+.23)
    c=fit(coherent,1000)
    assert abs(c['amplitude']-.33)<2e-13 and abs(c['dc']-.37)<2e-13
    assert abs(c['phase_rad']-.23)<2e-12
    assert max(abs(c['residual']))<1e-11
    try:fit(coherent,1000.3)
    except ValueError:pass
    else:raise AssertionError('noncoherent rectangular was accepted')
    # A coherent known -40 dBc harmonic is retained in THD+N.
    distorted=coherent+.0033*np.sin(2*np.pi*2000*t-.54)
    d=fit(distorted,1000)
    p=band_power(d['residual'],window='rectangular')
    harmonic_db=10*math.log10(p['power']/(.5*.33**2))
    assert abs(harmonic_db+40)<.0001, harmonic_db
    # Noncoherent BH known sine/amplitude and independently seeded broadband
    # noise. Check ENBW-corrected power against expected 20..20k band share.
    f=997.25
    rng=np.random.default_rng(918242)
    noise=rng.standard_normal(rate)*.001
    y=.17+.40*np.sin(2*np.pi*f*t+.7)+noise
    fitted=fit(y,f,window='blackman-harris-4')
    assert abs(fitted['amplitude']-.40)<.00003
    assert abs(fitted['dc']-.17)<.00002
    assert abs(fitted['phase_rad']-.7)<.0001
    result=band_power(fitted['residual'],window='blackman-harris-4')
    expected=.001**2 * (20000-20)/(rate/2)
    noise_error_db=10*math.log10(result['power']/expected)
    assert abs(noise_error_db)<.5,noise_error_db
    w,enbw=bh4(rate)
    assert abs(enbw-2.0043529382)<.00002
    assert abs(band_power(np.sin(2*np.pi*1000*t),window='rectangular')['power']-.5)<1e-9
    return dict(coherent_fitted_amp=c['amplitude'],coherent_fitted_phase=c['phase_rad'],
                distortion_thd_plus_noise_dbc=harmonic_db,
                noncoherent_fitted_amp=fitted['amplitude'], noncoherent_fitted_phase=fitted['phase_rad'],
                noncoherent_noise_power=result['power'], expected_noise_power=expected,
                noise_power_error_db=noise_error_db,blackman_harris_enbw_bins=enbw)


def second_filter_check():
    """Corroborative SciPy FIR + direct upfirdn, NOT a second scoring ruler."""
    rate=2822400
    n=16000
    count=(n+31)//32
    t=np.arange(n,dtype=np.float64)/rate
    x=(np.sin(2*np.pi*997*t)>0).astype(np.uint8)
    # Alternative SciPy firwin synthesis, intentionally distinct implementation.
    h,info=fir(rate)
    second=signal.firwin(len(h),22000,window=('kaiser',21.63226),fs=rate,scale=True)
    # Independent polyphase direct convolution, as a cross-check on an FFT
    # overlap-add reconstruction with the separately designed second FIR.
    offset=(-info['delay_native_frames'])%32
    poly=signal.upfirdn(second,np.pad(x.astype(float)*2-1,(offset,0)),down=32)
    secondary=poly[(info['delay_native_frames']+offset)//32:][:count]
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'x.bin'
        path.write_bytes(np.packbits(x,bitorder='big').tobytes())
        primary=decode_packed(path,n,rate,block=1024)
    # Alignment is accounted for exactly by native-prefix padding: this
    # alternative uses direct C polyphase, not the primary FFT algorithm.
    diff=float(np.max(np.abs(primary-secondary)))
    assert diff<.00001,diff
    return dict(rate_hz=rate,frames=n,alternative='scipy.signal.firwin + direct polyphase upfirdn',
                primary='numpy/scipy FFT overlap-add with high precision frozen Kaiser',
                max_abs_difference=diff,not_averaged=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    records=[]
    def test(name, f):
        try:records.append(dict(name=name,status='pass',result=f()))
        except Exception as exc: records.append(dict(name=name,status='fail',error=repr(exc)))
    for rate in (2822400,5644800,11289600):
        test(f'filter_response_{rate}',lambda r=rate: response(r))
        test(f'filter_count_direct_oracle_{rate}',lambda r=rate: pulse_count(r))
    test('coherent_and_noncoherent_known_noise_distortion',signal_fits)
    test('second_independent_filter_and_reconstruction',second_filter_check)
    out=dict(schema='analysis-v1/selftest/1',coefficients_manifest_sha256=hashlib.sha256((Path(__file__).parent/'manifest.json').read_bytes()).hexdigest(),
             tests=records,passed=sum(r['status']=='pass' for r in records),
             failed=sum(r['status']=='fail' for r in records))
    (args.results/'analysis-v1-selftest.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(passed=out['passed'],failed=out['failed'],results=str(args.results)),sort_keys=True))
    for r in records:
        if r['status']=='fail':print('FAILED',r['name'],r['error'],file=sys.stderr)
    return 0 if not out['failed'] else 1

if __name__ == '__main__':raise SystemExit(main())
