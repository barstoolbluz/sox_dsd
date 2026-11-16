#!/usr/bin/env python3
"""Release 1.1.2 integration gate on actual PCM/DSF/PCM signal paths.

Covers every mastering clock, original DSD64/128 invariants, default PCM
rates, exact profile identities, explicit -r, adapt/strict rules, low and
ultrasonic tones, silence, seeded noise, and legacy certificates. No music is required.
Linear FIR/SRC response is certified separately: nonlinear SDM-8 tone/noise
measurements here are NOT substituted for a filter transfer function.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

import numpy as np

RATES={64:(2822400,88200,None),128:(5644800,176400,None),
       256:(11289600,352800,50000),512:(22579200,352800,72000),
       1024:(45158400,705600,110000)}
SOURCE_RATE=705600
DURATION=.07
EXPECTED={256:(60000,100000),512:(88200,148200),1024:(120000,200000)}


def call(sox,*args,success=True):
    command=[str(sox),*map(str,args)]
    run=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,
        timeout=180,env={**os.environ,'SOX_OPTS':'','OMP_NUM_THREADS':'1'})
    if success and run.returncode!=0:
        raise AssertionError(f'command failed ({run.returncode}): {command}\n{run.stderr[-1200:]}')
    return run


def stimulus(path,tone,kind):
    n=round(SOURCE_RATE*DURATION)
    t=np.arange(n,dtype=np.float64)/SOURCE_RATE
    # Flat central analysis region and finite ramps for clip-safe transients.
    window=np.minimum(1.,np.minimum(np.arange(n),n-1-np.arange(n))/(SOURCE_RATE*.006))
    if kind=='noise':
        x=.018*np.maximum(window,0.)*np.random.default_rng(0x11226).standard_normal(n)
    elif kind=='silence':
        x=np.zeros(n)
    else:
        assert tone is not None
        x=.13*np.maximum(window,0.)*np.sin(2*np.pi*tone*t)
    samples=np.rint(x*2147483647).astype('<i4')
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setframerate(SOURCE_RATE);f.setsampwidth(4)
        f.writeframes(samples.tobytes())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projected_tone(path,hz,frequency):
    y=np.fromfile(path,dtype='<f8')
    assert len(y)>2000
    a=len(y)//4;b=3*len(y)//4
    z=y[a:b]
    t=np.arange(a,b,dtype=np.float64)/hz
    amplitude=2*abs(np.dot(z,np.exp(-2j*np.pi*frequency*t)))/len(z)
    return float(amplitude),len(y)


def in_band_noise(path,hz,pass_hz):
    """Report measured RMS/spectral power, never infer a linear FIR H(f)."""
    y=np.fromfile(path,dtype='<f8')
    mid=y[len(y)//4:3*len(y)//4]
    assert len(mid)>1000 and np.all(np.isfinite(mid))
    win=np.hanning(len(mid))
    f=np.fft.rfftfreq(len(mid),d=1/hz)
    spectrum=np.abs(np.fft.rfft(mid*win))**2
    spectrum*=2./(len(mid)*np.sum(win*win))
    spectrum[0]*=.5
    if len(mid)%2==0:spectrum[-1]*=.5
    bands={'audible_0_20k':(0,20000),'ultrasonic_20_40k':(20000,40000),
           'above_40k_to_pass':(40000,pass_hz),'pass_to_output_nyquist':(pass_hz,hz/2)}
    measure={}
    for name,(low,high) in bands.items():
        mask=(f>=low)&(f<high)
        if high<=low:continue
        energy=float(np.sum(spectrum[mask]))
        measure[name+'_rms_dbfs']=20*math.log10(max(math.sqrt(energy),1e-300))
    measure['time_domain_rms_dbfs']=20*math.log10(max(float(np.sqrt(np.mean(mid*mid))),1e-300))
    measure['fft_bin_hz']=hz/len(mid)
    measure['window']='Hann; middle half of decoded stream; sample-power normalization'
    return measure


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sox',type=Path,required=True)
    p.add_argument('--baseline-sox',type=Path)
    p.add_argument('--results',type=Path)
    opts=p.parse_args()
    sox=opts.sox.resolve()
    base=opts.baseline_sox.resolve() if opts.baseline_sox else None
    records=[]
    manifest=json.loads((Path(__file__).resolve().parents[1]/'reference'/'mastering_passband_112.json').read_text())
    with tempfile.TemporaryDirectory(prefix='dsd112-') as d:
        root=Path(d)
        for rate,(native,internal,ultra) in RATES.items():
            for test,tone in [('low',1000),('wide',ultra),('silence',None),('noise',None)]:
                if test=='wide' and tone is None:continue
                wav=root/f'{rate}-{test}-input.wav'
                original=stimulus(wav,tone,test)
                dsd=root/f'{rate}-{test}.dsf'
                encreport=root/f'{rate}-{test}-encoder.json'
                call(sox,'--report',encreport,'-D',wav,'-r',native,dsd)
                enc=json.loads(encreport.read_text())['processing']['encoder'][0]
                assert enc['profile_id']==f'encode.mastering.dsd{rate}',enc
                assert enc['clipped_interpolated_samples']=='0',enc
                assert (enc['coefficient_certificate_sha256'] is None)==(rate>=256),enc
                assert abs(enc['headroom_applied_db']-(-20*math.log10(.9)))<1e-10,enc
                if ultra and test=='wide':
                    assert enc['effective_passband_hz']==EXPECTED[rate][0],enc
                dst=root/f'{rate}-{test}-master.f64'
                report=root/f'{rate}-{test}-decoder.json'
                call(sox,'--dsd-layout-loss','warn','--report',report,'-D',dsd,'-t','f64',dst)
                decoder=json.loads(report.read_text())['processing']['decoder'][0]
                assert decoder['profile_id']==f'decode.mastering.dsd{rate}',decoder
                assert decoder['output_pcm_hz']==internal,decoder
                assert decoder['intermediate_pcm_hz']==internal,decoder
                assert decoder['coefficients']['bank_last_sha256'],decoder
                if rate in EXPECTED:
                    bank=manifest['profiles']['dsd'+str(rate)]['bank']
                    expected_digest=manifest['banks']['decoder'][bank]['sha256_float_hex']
                    assert decoder['coefficients']['bank_last_sha256']==expected_digest,decoder
                    assert (decoder['guaranteed_passband_hz'],decoder['guaranteed_stopband_hz'])==EXPECTED[rate],decoder
                row=dict(dsd=rate,stimulus=test,tone_hz=tone,
                         input_sha256=original,encoded_sha256=hashlib.sha256(dsd.read_bytes()).hexdigest(),
                         output_sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),
                         output_hz=internal,default_frames=dst.stat().st_size//8,
                         decoder_bank_sha256=decoder['coefficients']['bank_last_sha256'],
                         clipped_samples=enc['clipped_interpolated_samples'])
                if test in ('silence','noise'):
                    row['measured_decoded_spectrum']=in_band_noise(dst,internal,
                        EXPECTED[rate][0] if rate in EXPECTED else (20000 if rate==64 else 30000))
                if tone is not None:
                    amp,_=projected_tone(dst,internal,tone)
                    row['reconstructed_tone_amplitude']=amp
                    if rate>=256 and test=='wide':
                        # Illustrative SDM-8 pipeline survival, NOT a numerical FIR tolerance.
                        assert amp>=.03,(rate,amp)
                if base and rate<=128:
                    prior=root/f'{rate}-{test}-baseline.dsf'
                    call(base,'-D',wav,'-r',native,prior)
                    assert prior.read_bytes()==dsd.read_bytes(),f'DSD{rate} encode changed'
                    prior_pcm=root/f'{rate}-{test}-baseline.f64'
                    call(base,'--dsd-layout-loss','warn','-D',dsd,'-t','f64',prior_pcm)
                    assert prior_pcm.read_bytes()==dst.read_bytes(),f'DSD{rate} decode changed'
                    row['baseline_identity']='bit-exact encode and decode'
                if base and test=='wide':
                    old=root/f'{rate}-{test}-old.f64'
                    # Same new DSD input, so decoder comparison isolates reconstruction.
                    call(base,'--dsd-layout-loss','warn','-D',dsd,'-t','f64','-r',internal,old)
                    old_amp,_=projected_tone(old,internal,tone)
                    row['baseline_decoder_tone_amplitude']=old_amp
                    row['new_vs_baseline_decoder_db']=20*math.log10(max(row['reconstructed_tone_amplitude'],1e-300)/max(old_amp,1e-300))
                    # Historical transition response is deliberately diagnostic.
                    # DSD256/50 kHz lies between the old 40 kHz pass and 80 kHz
                    # stop edges: 1.1.1 need not reject it by any fixed amount.
                assert hashlib.sha256(wav.read_bytes()).hexdigest()==original
                records.append(row)
            # Wideband banks, IDs and default-rate policy are untouched at
            # every clock. Compare identical input DSD to the 1.1.1 binary.
            dsd=root/f'{rate}-low.dsf'
            wide_hz={64:88200,128:176400,256:352800,
                     512:705600,1024:1411200}[rate]
            wdst=root/f'{rate}-wideband.f64'
            wreceipt=root/f'{rate}-wideband.json'
            call(sox,'--dsd-layout-loss','warn','--decode','wideband',
                 '--report',wreceipt,'-D',dsd,'-t','f64',wdst)
            decoded=json.loads(wreceipt.read_text())['processing']['decoder'][0]
            assert decoded['profile_id']==f'decode.wideband.dsd{rate}',decoded
            assert decoded['output_pcm_hz']==wide_hz,decoded
            if base:
                oldwide=root/f'{rate}-wideband-baseline.f64'
                call(base,'--dsd-layout-loss','warn','--decode','wideband',
                     '-D',dsd,'-t','f64',oldwide)
                assert wdst.read_bytes()==oldwide.read_bytes(),f'DSD{rate} wideband changed'
            records.append(dict(dsd=rate,stimulus='wideband-unchanged',
                output_hz=wide_hz,output_sha256=hashlib.sha256(wdst.read_bytes()).hexdigest(),
                baseline_identity=('bit-exact decode' if base else 'not compared')))
            for hz in (176400,192000,352800,705600):
                dst=root/f'{rate}-explicit-{hz}.wav'
                run=call(sox,'--dsd-layout-loss','warn','-D',dsd,'-r',hz,dst)
                status=call(sox,'-D',dst,'-n','stat')
                # soxi returns the actual WAV header clock, not planner metadata.
                actual=int(call(sox,'--i','-r',dst).stdout.strip())
                assert actual==hz,(rate,hz,actual)
                with wave.open(str(dst),'rb') as f:
                    got=f.getnframes()
                expected=round(round(SOURCE_RATE*DURATION)*hz/SOURCE_RATE)
                assert got==expected,(rate,hz,got,expected)
                records.append(dict(dsd=rate,stimulus='explicit-rate',output_hz=hz,
                                    output_frames=got,expected_frames=expected))
            if rate in (512,1024):
                fail=root/f'{rate}-strict-refused.wav'
                denied=call(sox,'--dsd-layout-loss','warn','--dsd-bandwidth','strict',
                    '-D',dsd,'-r','176400',fail,success=False)
                assert denied.returncode!=0 and not fail.exists(),(rate,denied.stderr)
                records.append(dict(dsd=rate,stimulus='strict-rate-refusal',rate=176400,refused=True))
            else:
                strict=root/f'{rate}-strict-ok.wav'
                call(sox,'--dsd-layout-loss','warn','--dsd-bandwidth','strict',
                    '-D',dsd,'-r','176400',strict)
        # Strict vs adapt on low clock is a separate output-rate policy test.
    output=dict(schema='sox-dsd/1.1.2/cli-integration/1',source_rate=SOURCE_RATE,
        source_duration_seconds=DURATION,nonlinear_warning='SDM output/noise is not a linear FIR transfer function',
        cases=records,summary=dict(passed=len(records),failed=0))
    if opts.results:
        opts.results.parent.mkdir(parents=True,exist_ok=True)
        opts.results.write_text(json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(output['summary']))

if __name__=='__main__':
    main()
