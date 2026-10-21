#!/usr/bin/env python3
"""P17 independent high-rate numerical tests; NOT a release certificate.

FIR mathematics is from checked-in immutable C99 hex words, evaluated by
independent polynomial composition / FFT sampling / longdouble inner products.
The exporter only supplies production outputs, never the mathematical oracle.
Coherent aliases cover ALL D-1 images for each sampled baseband frequency.
Sampled extrema and brief synthetic SDM runs do not discharge the missing
independent media and controlled high-rate soak obligations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

import numpy as np
from scipy import signal

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'src/dsd_coeffs.h'
MANIFEST=ROOT/'tests/dsd/reference/p17_profiles.json'
BASE=ROOT/'tests/dsd/reference/p06_coefficients.json'
FIR=ROOT/'test/dsd_test_p17'
BANKS=('halfband','master64_256','wideband')
THRESHOLD={'pass_ripple_db':0.0001,'stop_max_db':-160.,'coherent_alias_sum_db':-160.}


def sha(x:bytes)->str:return hashlib.sha256(x).hexdigest()

def atomic(path:Path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
    temp.replace(path)

def bank_words():
    text=SOURCE.read_text();baseline=json.loads(BASE.read_text())
    result={}
    for name in BANKS:
        m=re.search(r'\blsx_dsd_coeff_'+name+r'\[(\d+)\]\s*=\s*\{(.*?)\};',text,re.S)
        if not m:raise AssertionError('missing bank '+name)
        words=[s.strip() for s in m.group(2).split(',') if s.strip()]
        h=np.asarray([float.fromhex(x) for x in words])
        assert len(words)==int(m.group(1)) and np.array_equal(h,h[::-1])
        assert sha(('\n'.join(words)+'\n').encode())==baseline['banks'][name]['rounded_hex_sha256']
        assert abs(float(np.sum(h,dtype=np.longdouble))-1)<2e-15
        result[name]=h
    return result

def fir_fft(banks,names,fft_size):
    """Complex response of upsampled convolutions, NOT production ring FIR."""
    bins=np.arange(fft_size,dtype=np.int64)
    H=np.ones(fft_size,dtype=np.complex128)
    cache={name:np.fft.fft(banks[name],n=fft_size) for name in set(names)}
    for stage,name in enumerate(names):
        H*=cache[name][(bins*(1<<stage))&(fft_size-1)]
    return H

def spectral_cases(banks,manifest,fft_size=1<<19):
    rows=[]
    for key,m in sorted(manifest['reconstruction'].items()):
        native=m['native_hz']; R=m['intermediate_hz']; D=m['factor']
        assert native==D*R and D&(D-1)==0
        assert len(m['stage_banks'])==D.bit_length()-1<=8
        names=m['stage_banks']
        assert all(name=='halfband' for name in names[:-1])
        calculated_delay=sum((len(banks[x])//2)*(1<<j) for j,x in enumerate(names))
        assert calculated_delay==m['delay_native_frames']
        assert [((calculated_delay>>j)&1) for j in range(len(names))]==m['stage_phases']
        assert calculated_delay//D==m['discard_output_frames']
        if 'mastering' in key:
            assert names[-1]=='master64_256' and 2*R==352800
            assert (m['pass_hz'],m['stop_hz'])==(40000,80000)
        else:
            assert names[-1]=='wideband'
            assert m['pass_hz']==.4*R and m['stop_hz']==.5*R
        H=fir_fft(banks,names,fft_size)
        step=native/fft_size
        pass_bins=int(math.ceil(m['pass_hz']/step))
        stop_start=int(math.ceil(m['stop_hz']/step))
        pass_band=np.abs(H[:pass_bins+1])
        ripple=float(np.max(np.abs(20*np.log10(np.maximum(pass_band,1e-300)))))
        stop_band=np.abs(H[stop_start:fft_size//2+1])
        stop_max=float(20*np.log10(max(float(stop_band.max()),1e-300)))
        # Exact integer FFT-bin images, including negative-frequency aliases,
        # which appear as wrapped positive FFT frequencies. The independent
        # sign/phase choice is worst-case coherent amplitude addition.
        shift=fft_size//D
        bins=np.arange(pass_bins+1,dtype=np.int64)
        aliases=np.zeros(len(bins),dtype=np.float64)
        alias_power=np.zeros(len(bins),dtype=np.float64)
        for k in range(1,D):
            mag=np.abs(H[(bins+k*shift)&(fft_size-1)])
            aliases+=mag
            alias_power+=mag*mag
        alias_db=float(20*np.log10(max(float(aliases.max()),1e-300)))
        incoherent_db=float(10*np.log10(max(float(alias_power.max()),1e-300)))
        result=dict(profile=key,native_hz=native,intermediate_hz=R,
           physical_pass_hz=m['pass_hz'],physical_stop_hz=m['stop_hz'],
           factor=D,stages=len(names),delay_native_frames=calculated_delay,
           last_stage_input_hz=R*2,frame_clock_spacing_hz=step,
           pass_ripple_db=ripple,stop_max_db=stop_max,
           coherent_alias_sum_db=alias_db,incoherent_alias_power_db=incoherent_db,
           aliases_per_base_frequency=D-1,sampled_base_frequencies=len(bins),
           sampled_native_frequencies=fft_size//2+1,
           upper_public_output_hz=705600,
           effective_bandwidth_at_705600_hz=min(m['pass_hz'],.475*min(R,705600)),
           strict_705600_supported=(R==705600 or .475*min(R,705600)>=m['pass_hz']),
           status='PASS' if ripple<=THRESHOLD['pass_ripple_db'] and
             stop_max<=THRESHOLD['stop_max_db'] and alias_db<=THRESHOLD['coherent_alias_sum_db'] else 'FAIL')
        if key=='decode.wideband.v1.dsd1024':
            assert result['effective_bandwidth_at_705600_hz']==335160.0
            assert not result['strict_705600_supported']
        rows.append(result)
    return dict(schema='P17/finite-grid-fft/1',
       status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
       qualified=False,fft_bins=fft_size,thresholds=THRESHOLD,
       method='independent zero-padded FFT product of bank responses at all native frequency bins; D-1 coherent alias images per baseband bin',
       caveat='finite grid does not prove continuous-frequency extrema; existing bank certificates are inherited, not replaced',
       cases=rows)

def composed_taps(banks,names):
    q=np.array([1.],dtype=np.float64)
    norm=1.;count=0
    for j,name in enumerate(names):
        b=banks[name]
        padded=np.zeros((len(b)-1)*(1<<j)+1,dtype=np.float64)
        padded[::1<<j]=b
        q=np.convolve(q,padded)
        norm*=float(np.sum(np.abs(b),dtype=np.longdouble));count+=len(b)
    return q,16*np.finfo(np.float64).eps*count*norm

def bit_sequences(frames,ch):
    """Independent seeded PCG64 bitstreams, one chronological byte per bit."""
    rng=np.random.Generator(np.random.PCG64(0x17cafe+ch))
    return rng.integers(0,2,size=(frames,ch),dtype=np.uint8)

def finite_cases(banks,manifest):
    cases=[]
    for key,m in sorted(manifest['reconstruction'].items()):
        profile=1 if '.wideband.' in key else 0
        N=32769
        coeff,bound=composed_taps(banks,m['stage_banks'])
        D=m['factor'];G=m['delay_native_frames']
        assert len(coeff)==2*G+1
        expected=N//D+(N%D!=0)
        for channels in (1,6):
            bits=bit_sequences(N,channels)
            command=[str(FIR),'export',str(m['native_hz']),str(profile),str(channels),str(N)]
            cp=subprocess.run(command,cwd=ROOT,input=bits.tobytes(),capture_output=True,timeout=180)
            assert cp.returncode==0,cp.stderr.decode(errors='replace')[-1000:]
            assert b'P17_EXPORT_OK' in cp.stderr
            result=np.frombuffer(cp.stdout,dtype='<f8')
            assert result.size==expected*channels
            assert np.all(np.isfinite(result))
            output=result.reshape((expected,channels))
            indices=sorted({0,1,2,3,4,expected//2,max(0,expected-5),
                            max(0,expected-3),expected-1})
            worst=0.;checked=0
            time_indices=np.arange(len(coeff),dtype=np.int64)
            for n in indices:
                native_index=G+n*D-time_indices
                selected=(native_index>=0)&(native_index<N)
                k=native_index[selected]
                taps=coeff[selected].astype(np.longdouble)
                for c in range(channels):
                    signs=(2*bits[k,c].astype(np.int16)-1).astype(np.longdouble)
                    expected_sample=float(np.sum(signs*taps,dtype=np.longdouble))
                    worst=max(worst,abs(expected_sample-output[n,c]))
                    checked+=1
            cases.append(dict(profile=key,channels=channels,native_frames=N,
                expected_output_frames=expected,output_sha256=sha(cp.stdout),
                checked_fir_samples=checked,independent_fir_roundoff_bound=bound,
                max_absolute_fir_error=worst,status='PASS' if worst<=bound else 'FAIL'))
    return dict(schema='P17/independent-finite-fir/1',
      status='PASS' if all(x['status']=='PASS' for x in cases) else 'FAIL',
      qualified=False,source_bits='independent fixed-seed PCG64; binary64 production exporter has no reference coefficients',
      method='expanded coefficient polynomial + zero-extension + longdouble scalar inner product at beginnings/middle/EOF; P15 section 8.6 bound',
      cases=cases)

def sdm_cases(duration=4096):
    cases=[]
    # Exactly coherent in the source signal generator. Tone is well below the
    # required .5 envelope; a deliberate overload is tested separately in C.
    source_hz=176400
    t=np.arange(duration,dtype=float)/source_hz
    waveform=(.1*np.sin(2*np.pi*1001*t)+.025*np.cos(2*np.pi*3431*t)).astype('<f8')
    for hz in (22579200,45158400):
        trials=[]
        for tier in ('scalar','sse2','avx1','avx2','avx512'):
            command=[str(FIR),'encode-export',str(hz),str(duration)]
            cp=subprocess.run(command,input=waveform.tobytes(),capture_output=True,
                 cwd=ROOT,timeout=150,env={**os.environ,'SOX_DSD_KERNEL_SDM':tier})
            if cp.returncode:
                # Impossible ISA tier is a named unrun, never a pass.
                if b'P17 FAIL' in cp.stderr and b'candidate_create' in cp.stderr:
                    trials.append(dict(tier=tier,status='UNRUN_UNSUPPORTED_ISA',
                       stderr=cp.stderr.decode(errors='replace')[-250:]))
                    continue
                raise AssertionError(f'candidate {hz}/{tier}: '+cp.stderr.decode(errors='replace')[-900:])
            assert b'P17_ENCODE_EXPORT' in cp.stderr
            native=np.frombuffer(cp.stdout,dtype=np.uint8)
            expected=(duration*hz+source_hz//2)//source_hz
            assert native.size==expected and np.all(native<=1)
            # Statistical smoke only: no 30 minute sample, no independent media.
            # This is deliberately NOT the P10 28-bit admission window gate.
            windows=np.cumsum(native.astype(np.int64),dtype=np.int64)
            sums=windows[27:]-np.concatenate(([0],windows[:-28]))
            fractions=(np.count_nonzero(sums<7)+np.count_nonzero(sums>22))/len(sums)
            r=dict(tier=tier,status='PASS_DIAGNOSTIC',frames=int(native.size),
               bitstream_sha256=sha(cp.stdout),ones_fraction=float(native.mean()),
               ones28_min=int(sums.min()),ones28_max=int(sums.max()),
               ones28_outside_7_22_fraction=float(fractions),
               monitor=cp.stderr.decode().strip())
            trials.append(r)
        cases.append(dict(native_hz=hz,source_hz=source_hz,
           source_frames=duration,source_duration_seconds=duration/source_hz,
           input_peak=float(np.max(np.abs(waveform))),trials=trials,
           status='PASS' if all(x['status']=='PASS_DIAGNOSTIC' for x in trials if not x['status'].startswith('UNRUN')) else 'FAIL'))
    return dict(schema='P17/sdm-synthetic-diagnostic/1',status='PASS' if all(x['status']=='PASS' for x in cases) else 'FAIL',
       qualified=False,limits='28-bit population is diagnostic, not SACD normative, and cannot establish stability or professional quality',
       cases=cases)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17/numeric-p17')
    ap.add_argument('--fft',type=int,default=1<<19)
    ap.add_argument('--source-frames',type=int,default=4096)
    args=ap.parse_args()
    if args.fft<1<<17 or args.fft>1<<21 or args.fft&(args.fft-1):ap.error('fft size must be a power of two between 2^17 and 2^21')
    if not 256<=args.source_frames<=65536:ap.error('source-frames out of range')
    args.results.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(MANIFEST.read_text())
    t0=time.monotonic()
    records=[]
    for name,producer,file in [('spectral_grid',lambda:spectral_cases(bank_words(),manifest,args.fft),'filter-development-evidence.json'),
                               ('finite_oracle',lambda:finite_cases(bank_words(),manifest),'finite-reference-evidence.json'),
                               ('candidate_sdm',lambda:sdm_cases(args.source_frames),'sdm-candidate-diagnostics.json')]:
        try:out=producer()
        except Exception as error:out=dict(schema='P17/error/1',status='FAIL',error=repr(error))
        atomic(args.results/file,out)
        records.append(dict(name=name,status=out['status'],path=file))
        print(name,out['status'],flush=True)
    summary=dict(schema='P17/numeric-qualification-status/1',
        result='PASS_DEVELOPMENT_TESTS_UNQUALIFIED' if all(x['status']=='PASS' for x in records) else 'FAILED',
        rate_specific_profile_certificates_qualified=False,writer_enabled=False,
        elapsed_seconds=time.monotonic()-t0,host=dict(node=platform.node(),
        python=platform.python_version(),numpy=np.__version__,machine=platform.machine()),
        records=records,
        outstanding=['continuous-frequency composite extremum/alias interval proof (sampled evidence recorded, inherited bank certificates unchanged)',
          'independent commercial/reference DSD512/1024 program corpus and external decoder interoperability',
          '30-minute-per-rate mastering/ultrasonic/gain/stability holdouts and 1-hour sustained native/ISA soak',
          'physical Intel and AMD AVX-512 cross-host numerical/performance evidence',
          'P18-specific DSF/DFF/DoP writer and physical-device compatibility'],
        policy='do not enable any native/DoP writer or claim professional high-rate encoder qualification')
    atomic(args.results/'qualification.json',summary)
    print(json.dumps(dict(status=summary['result'],elapsed=summary['elapsed_seconds'])),flush=True)
    return 0 if summary['result']=='PASS_DEVELOPMENT_TESTS_UNQUALIFIED' else 1
if __name__=='__main__':raise SystemExit(main())
