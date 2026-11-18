#!/usr/bin/env python3
"""Independent impulse/correlation phase calibration for physical native64 family.

This is a fixed-calibration observation. It does not shift or refit any output
or adjust the spectral windows; it compares actual emitted binary64 PCM with
an independently regenerated input impulse and source tones. The exact zero
sample displacement criterion is confined to the centered impulse fixture.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decode import parse_wav
from qualification import FRAMES, SOURCE_RATE, CHANNELS, sha256, demand


def measure(root:Path)->dict:
    record=json.loads((root/'qualification.json').read_text())
    by_case={c['id']:c for c in record['cases']}
    calibration=[]
    for rate in ('dsd64','dsd128'):
        key=f'{rate}-impulse'
        demand(key in by_case,'missing independently generated impulse: '+key)
        case=by_case[key]
        source_file=root/case['source_path']
        output_file=root/case['reconstructed_path']
        raw_in,_=parse_wav(source_file,FRAMES,CHANNELS,SOURCE_RATE)
        raw_out,_=parse_wav(output_file,FRAMES,CHANNELS,SOURCE_RATE)
        source=np.frombuffer(raw_in,dtype='<f8').reshape(FRAMES,CHANNELS)
        observed=np.frombuffer(raw_out,dtype='<f8').reshape(FRAMES,CHANNELS)
        for channel in range(CHANNELS):
            ref=source[:,channel]
            actual=observed[:,channel]
            impulse=int(np.argmax(abs(ref)))
            peak=int(np.argmax(abs(actual)))
            corr=np.correlate(actual,ref,mode='full')
            lag=int(np.argmax(abs(corr))-(FRAMES-1))
            demand(int(np.count_nonzero(ref))==1 and impulse==FRAMES//2,
                   'calibration input is not isolated at declared sample')
            demand(peak==impulse and lag==0 and
                   math.copysign(1.,float(actual[peak]))==math.copysign(1.,float(ref[impulse])),
                   f'{rate} channel {channel}: incorrect sample-centered impulse phase')
            calibration.append({'rate':rate,'channel':channel,
                'input_peak_sample':impulse,'reconstructed_peak_sample':peak,
                'correlation_lag_samples':lag,'correlation_signed_peak':float(corr[FRAMES-1]),
                'actual_peak_f64_hex':float(actual[peak]).hex(),
                'raw_input_sha256':hashlib.sha256(raw_in).hexdigest(),
                'reconstructed_words_sha256':hashlib.sha256(raw_out).hexdigest(),
                'input_file_sha256':sha256(source_file),
                'output_file_sha256':sha256(output_file),'status':'PASS'})
    # Tone phase estimates are measurements only; no per-test phase/gain fits.
    # Quantization noise and finite observation windows limit phase accuracy.
    tones=[]
    t=np.arange(FRAMES,dtype=np.float64)/SOURCE_RATE
    for rate in ('dsd64','dsd128'):
        c=by_case[rate+'-tone']
        raw_i,_=parse_wav(root/c['source_path'],FRAMES,CHANNELS,SOURCE_RATE)
        raw_o,_=parse_wav(root/c['reconstructed_path'],FRAMES,CHANNELS,SOURCE_RATE)
        inp=np.frombuffer(raw_i,dtype='<f8').reshape(FRAMES,CHANNELS)
        out=np.frombuffer(raw_o,dtype='<f8').reshape(FRAMES,CHANNELS)
        for ch in range(CHANNELS):
            f=997+ch*313
            osc=np.exp(-2j*np.pi*f*t)
            x=np.dot(inp[:,ch],osc)
            y=np.dot(out[:,ch],osc)
            demand(abs(x)>0 and abs(y)>0,'tone phase undefined')
            p=float(np.angle(y/x))
            tones.append({'rate':rate,'channel':ch,'tone_hz':f,
                'phase_difference_radians':p,
                'phase_difference_degrees':p*180/math.pi,
                'amplitude_ratio':float(abs(y/x)),
                'scope':'MEASURED_NOT_A_NEW_QUANTITATIVE_GATE'})
    demand(len(calibration)==4 and len(tones)==4,'incomplete alignment measurements')
    return {'suite':'phase08-impulse-calibration','status':'PASS',
            'scope':'IMPULSE_EXACT_ZERO_LAG; TONE_PHASE_FINITE_MEASUREMENT_ONLY',
            'source_git_commit':record['source_git_commit'],
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'qualification_receipt_sha256':sha256(root/'qualification.json'),
            'impulses':calibration,'tone_phase':tones,
            'no_free_gain_or_shift_fits':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,required=True)
    a=parser.parse_args();result=a.results.resolve()
    outcome=result/'alignment.json';outcome.unlink(missing_ok=True)
    try:record=measure(result)
    except Exception as exc:
        outcome.write_text(json.dumps({'suite':'phase08-impulse-calibration',
                         'status':'FAIL','error':str(exc)},indent=2)+'\n')
        print(f'FAIL Phase08 impulse calibration: {exc}',file=sys.stderr)
        return 1
    outcome.write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    print('PASS Phase08 impulse calibration: four independent centered impulse traces; four measured tone phases')
    return 0

if __name__=='__main__':raise SystemExit(main())
