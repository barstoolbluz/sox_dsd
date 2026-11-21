#!/usr/bin/env python3
"""First frozen analysis-v1 measurements of *physical* v3 DSD64/128 output.

The analytic source WAV passes through the real native CLI source admission,
SRC, frozen v1 prefilter, and certified v3 modulator. The independently frozen
analysis-v1 filters score the extracted physical bits. This is an initial
measurement, not a comprehensive D4 spur limit or cross-ISA release verdict.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import numpy as np
from scipy import fft

ROOT=Path(__file__).resolve().parents[3]
ANALYSIS=ROOT/'tests/dsd/reference/analysis-v1'
sys.path.insert(0,str(ANALYSIS))
from analyze import decode_packed, steady_segment, measure, fit, bh4, band_power
from measure_candidates import confirm_lock


def demand(x,why):
    if not x:raise AssertionError(why)


def wav(path, frequency, peak, frames=141120, rate=88200):
    time=np.arange(frames,dtype=np.float64)/rate
    samples=(peak*np.sin(2*np.pi*frequency*time)).astype('<f8').tobytes()
    fmt=struct.pack('<HHIIHHH',3,1,rate,rate*8,8,64,0)
    chunks=b'fmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(samples))+samples
    path.write_bytes(b'RIFF'+struct.pack('<I',len(chunks)+4)+b'WAVE'+chunks)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed_dsf(src,dst,expected_rate):
    raw=src.read_bytes()
    demand(len(raw)>=92 and raw[:4]==b'DSD ' and raw[80:84]==b'data','invalid physical DSF')
    nch=struct.unpack_from('<I',raw,52)[0]
    rate=struct.unpack_from('<I',raw,56)[0]
    n=struct.unpack_from('<Q',raw,64)[0]
    demand(nch==1 and rate==expected_rate and n>0,'wrong DSF channel/clock/length')
    full=(n+32767)//32768
    demand(len(raw)==92+full*4096,'incorrect DSF physical extent')
    # SoX physical DSF is byte-blocked LSB-first; frozen analysis-v1 consumes
    # packed chronological MSB-first. This operation changes *representation*
    # but neither the physical bit chronology nor the sample values.
    physical=np.frombuffer(raw,dtype=np.uint8,offset=92)
    bitstream=np.unpackbits(physical,bitorder='little')[:n]
    packed=np.packbits(bitstream,bitorder='big').tobytes()
    dst.write_bytes(packed)
    return n,hashlib.sha256(raw).hexdigest(),hashlib.sha256(packed).hexdigest()


def spur(window,frequency):
    residual=(fit(window,frequency)['residual'] if frequency is not None
              else np.asarray(window,dtype=np.float64)-np.mean(window))
    taper,_=bh4(len(window))
    spectrum=np.abs(fft.rfft(residual*taper))
    hz=fft.rfftfreq(len(residual),1/88200)
    mask=(hz>=20)&(hz<=20000)
    values=spectrum[mask]
    demand(values.size>0,'no spur bins')
    strongest=float(np.max(values))*(2/float(taper.sum()))
    return {'band_hz':[20,20000], 'highest_single_residual_bin_dbfs':20*math.log10(max(strongest,1e-300)),
            'window':'blackman-harris-4', 'bin_hz':1.0,
            'fundamental_dc_removed':('least-squares, harmonics kept' if frequency is not None else 'DC only, silence')}


def run(sox,results):
    confirm_lock()
    reports=[]
    with tempfile.TemporaryDirectory(prefix='phase08-actual-v3-') as scratch:
        path=Path(scratch)
        for rate in (2822400,5644800):
            for peak,label in ((0.2,'low_level'),(0.0,'silence')):
                src=path/'sine.wav';dsf=path/'physical.dsf';bits=path/'physical.bits'
                sha=wav(src,997.0,peak)
                profile=f'encode.mastering.v3.dsd{rate//44100}'
                command=[str(sox),'--precision','64','--encode',profile,
                         '--dsd-clip','error',str(src),'-r',str(rate),str(dsf)]
                cp=subprocess.run(command,capture_output=True,timeout=120)
                demand(cp.returncode==0,f'{profile}: CLI exit {cp.returncode}: {cp.stderr[-300:]!r}')
                n,physical_sha,bitsha=packed_dsf(dsf,bits,rate)
                decoded=decode_packed(bits,n,rate)
                window,trim=steady_segment(decoded,rate)
                # D3's unity front-end gain is applied once; the documented
                # SACD level factor 0.5 maps PCM peak to modulator level.
                if peak:
                    metrology=measure(window,997.0,peak*.5,window='rectangular')
                    metrology.pop('residual_definition',None)
                    metrology['spur']=spur(window,997.0)
                else:
                    metrology={'silence_20_20k':band_power(window),
                               'signal_peak':float(np.max(np.abs(window))),
                               'spur':spur(window,None)}
                reports.append({'profile':profile,'rate_hz':rate,'case':label,
                                'physical_bits':n,'physical_dsf_sha256':physical_sha,
                                'chronological_bits_sha256':bitsha,
                                'source_wav_sha256':sha,'source_peak':peak,
                                'trim':trim,'measurement':metrology,
                                'command':[x if not x.startswith(str(path)) else '<temporary>'
                                           for x in command],
                                'status':'MEASURED_NOT_QUALIFIED',
                                'target_spur_dbfs':-110 if rate==2822400 else -120,
                                'spur_target_disposition':'REPORT_ONLY'})
    return {'schema':'phase08-first-v3-physical-analysis-v1/1',
            'status':'PASS_MEASUREMENT_ONLY',
            'frozen_method':'analysis-v1 (SHA256SUMS.txt; independently fixed coefficients)',
            'full_input_route':'source WAV through native binary64 v1 front end and certified v3 encoder',
            'qualification':'OPEN: first limited low-level synthetic tone does not qualify D4 spur, floor or cross-ISA gates',
            'silence_measurement':'DC-only frozen Blackman-Harris residual; no artificial fitted tone',
            'cases':reports}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sox',required=True,type=Path)
    ap.add_argument('--results',required=True,type=Path);a=ap.parse_args()
    try:r=run(a.sox.resolve(),a.results)
    except Exception as e:r={'status':'FAIL','error':repr(e)}
    a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'v3-analysis-v1.json').write_text(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(f"{r['status']}: D4 v3 native physical analysis-v1 ({len(r.get('cases', []))} rates)")
    if r['status']=='FAIL':print(r['error'],file=sys.stderr)
    return int(r['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
