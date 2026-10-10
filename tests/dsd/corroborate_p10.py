#!/usr/bin/env python3
"""Corroborate selected native outputs with independent polyphase reconstruction.

SciPy's direct polyphase FIR decimator and newly generated Kaiser filters are
separate from analysis-v1's frozen coefficients and FFT overlap/add decoder.
The secondary numbers never replace, average, or retune primary acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from scipy import signal
from p10_corpus import stimulus, RATES
from soak_p10 import atomic, sha
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd/reference/analysis-v1'))
from analyze import measure, band_power


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--primary',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args();a.results.mkdir(parents=True,exist_ok=True)
    primary=json.loads(a.primary.read_text())
    selections=[(r,'tone-997--6') for r in RATES]+[(RATES[0],'tone-1000--90'),(RATES[0],'silence')]
    report=dict(schema='P10/independent-reconstruction/1',status='INCOMPLETE',qualified=False,
        method='scipy.signal.resample_poly direct polyphase FIR; independently synthesized 220 dB Kaiser design, 22 kHz cutoff',
        unit_sha256=sha(a.unit),primary_reference='analysis-v1 (unchanged)',rows=[],filters=[])
    filters={}
    for native in RATES:
        down=native//88200
        estimate=math.ceil((220-8)*native/(2.285*2*math.pi*4000))
        taps=2*down*math.ceil((estimate-1)/(2*down))+1
        h=signal.firwin(taps,22000,window=('kaiser',.1102*(220-8.7)),fs=native,scale=True)
        f,H=signal.freqz(h,worN=1<<20,fs=native)
        stop=-20*np.log10(np.max(np.abs(H[f>=24000])))
        pass_error=float(np.max(np.abs(20*np.log10(np.abs(H[f<=20000])))))
        if stop<180 or pass_error>1e-5:
            raise RuntimeError('secondary filter does not meet the declared analysis band')
        filters[native]=h
        report['filters'].append(dict(native_hz=native,taps=taps,
            sha256=hashlib.sha256(h.astype('<f8').tobytes()).hexdigest(),
            stop_attenuation_db=float(stop),passband_error_db=pass_error,
            delay_native_samples=(taps-1)//2,decimation=down))
    with tempfile.TemporaryDirectory(prefix='p10-secondary-') as td:
        tmp=Path(td)
        for native,name in selections:
            row=next((r for r in primary['rows'] if r['control']=='mastering' and
                r['source']['native_hz']==native and r['source']['name']==name),None)
            if row is None or row['exit_code']:
                raise RuntimeError(f'missing successful primary case {native}/{name}')
            config=row['source'];raw,meta=stimulus(config)
            source=tmp/'source.f64le';packed=tmp/'audio.bits';result=tmp/'render.json'
            source.write_bytes(raw)
            proc=subprocess.run([str(a.unit.resolve()),'--render',str(config['source_hz']),str(native),
                row['candidate_profile'],'.5','guarded',str(source),str(packed),str(result)],
                capture_output=True,text=True,timeout=300)
            if proc.returncode or sha(packed)!=row['bits_sha256']:
                raise RuntimeError('secondary rerender differs from recorded primary native bits')
            frames=row['render']['committed_native_frames']
            bits=np.unpackbits(np.frombuffer(packed.read_bytes(),dtype=np.uint8))[:frames]
            y=bits.astype(np.float64)*2-1
            reconstructed=signal.resample_poly(y,1,native//88200,window=filters[native])
            samples=reconstructed[22050:22050+88200]
            if len(samples)!=88200 or not np.all(np.isfinite(samples)):
                raise RuntimeError('secondary reconstruction has invalid finite extent')
            if config['kind']=='tone':
                measured=measure(samples,config['frequency'],.5*10**(config['dbfs']/20),window='rectangular')
                differences=dict(residual_db=measured['residual_band_dbfs']-row['analysis']['residual_band_dbfs'],
                    gain_db=measured['gain_error_db']-row['analysis']['gain_error_db'],
                    phase_rad=math.remainder(measured['phase_rad']-row['analysis']['phase_rad'],2*math.pi))
            else:
                measured=band_power(samples-np.mean(samples))
                differences=dict(residual_db=measured['dbfs']-row['analysis']['band']['dbfs'])
            report['rows'].append(dict(name=name,native_hz=native,exit_code=proc.returncode,
                bits_sha256=sha(packed),source_sha256=meta['source_f64le_sha256'],
                secondary=measured,difference_from_primary=differences,
                precision=row.get('precision'),interpretation='corroboration only; analysis-v1 controls primary gates'))
            atomic(a.results/'corroboration.json',report)
            print(native,name,differences,flush=True)
    report['status']='PASS'
    report['scope']='Five recorded bitstreams reproduced exactly; independent filters validated and measurements retained. Not a replacement qualification.'
    atomic(a.results/'corroboration.json',report)
    return 0


if __name__=='__main__':raise SystemExit(main())
