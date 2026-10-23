#!/usr/bin/env python3
"""Bounded-memory raw native DSD1024 spectrum; not a DAC or fidelity oracle.

The whole-bitstream PSD has DIFFERENT absolute units from reconstructed
sine-equivalent residual dBFS. Only compare raw-DSD candidate/control values
from this script using identical source and plateau.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.signal.windows import hann

from model import RATE, WORKING, sha
from study import native_pass, write_once

FFT_SIZE=65536
START_S=.4
STOP_S=.8
BANDS=((150000,500000),(500000,1000000),(1000000,2000000),
       (2000000,5000000),(5000000,10000000),(10000000,RATE//2))
FILTERS=((2,100000),(2,200000),(4,100000),(4,200000))
SCHEMA='DSD1024-NTF-R2-native-PSD/1'


def analyze(packed: Path, receipt: dict, *, start: float=START_S, stop: float=STOP_S) -> dict:
    good,reason=native_pass(receipt)
    if not good:raise ValueError('Refuse PSD for native-failed render: '+reason)
    if receipt['native_hz']!=RATE or receipt['working_hz']!=WORKING or receipt['input_frames']!=round(1.6*WORKING):
        raise ValueError('Unexpected native clock or primary duration')
    if not packed.is_file() or sha(packed)!=receipt['packed_sha256']:
        raise ValueError('Packed bitstream digest mismatch')
    total_native=receipt['input_frames']*(RATE//WORKING)
    if packed.stat().st_size!=(total_native+7)//8:
        raise ValueError('Incomplete packed output')
    start_frame=round(start*RATE);stop_frame=round(stop*RATE)
    if not (0<=start_frame<stop_frame<=total_native and start_frame%8==0):
        raise ValueError('Invalid or unaligned plateau')
    n_segments=(stop_frame-start_frame)//FFT_SIZE
    if n_segments<4:raise ValueError('Insufficient FFT segments')
    window=hann(FFT_SIZE,sym=False).astype('float64')
    wsquared=float(np.sum(window**2))
    # DSD bipolar signal: 1 -> +1, 0 -> -1, MSB first.
    # One-sided PSD normalized such that sum(PSD * bin_width) = 1
    # exactly (apart from rounding) for any bipolar +/-1 bitstream.
    scale=1/(RATE*wsquared)
    average=np.zeros(FFT_SIZE//2+1,dtype=np.float64)
    with packed.open('rb') as f:
        f.seek(start_frame//8)
        for i in range(n_segments):
            raw=f.read(FFT_SIZE//8)
            if len(raw)!=FFT_SIZE//8:raise ValueError('Premature end of packed DSD stream')
            bits=np.unpackbits(np.frombuffer(raw,dtype='uint8'),bitorder='big')
            x=bits.astype(np.float64)*2.-1.
            ft=np.fft.rfft(x*window)
            ps=(ft.real*ft.real+ft.imag*ft.imag)*scale
            ps[1:-1]*=2
            average+=ps
    average/=n_segments
    df=RATE/FFT_SIZE
    freq=np.fft.rfftfreq(FFT_SIZE,d=1/RATE)
    full=float(np.sum(average)*df)
    if not math.isclose(full,1.,rel_tol=3e-12,abs_tol=3e-12):
        raise ValueError('Power-Parseval invariant for native +/-1 stream failed: '+repr(full))
    output={}
    for lower,upper in BANDS:
        selection=(freq>=lower)&(freq<upper if upper<RATE//2 else freq<=upper)
        local=average[selection]
        if local.size==0:raise ValueError('Band contains no frequency bins')
        power=float(np.sum(local)*df)
        maxidx=int(np.argmax(local))
        strongest=float(freq[selection][maxidx]);peak_power=float(local[maxidx]*df)
        median=float(np.median(local))
        output[f'{lower}-{upper}Hz']={
            'integrated_power':power,
            'integrated_power_db':10*math.log10(max(power,1e-300)),
            'largest_bin_frequency_hz':strongest,
            'largest_bin_power_db':10*math.log10(max(peak_power,1e-300)),
            'largest_bin_to_band_median_db':10*math.log10(max(float(local[maxidx])/max(median,1e-300),1e-300)),
            'spur_warning':'Peak bin is a diagnostic, not proof of tonal spurs; 689-Hz bins and 0.4s averaging.'}
    weights={}
    ultrasound=freq>=150000
    for order,cutoff in FILTERS:
        response=1./(1.+(freq[ultrasound]/cutoff)**(2*order))
        energy=float(np.sum(average[ultrasound]*response)*df)
        weights[f'butterworth_{order}pole_{cutoff}hz_above150k']={
            'weighted_ultrasonic_power':energy,
            'weighted_ultrasonic_power_db':10*math.log10(max(energy,1e-300)),
            'model':'illustrative digital Butterworth magnitude squared; no DAC/EMI/IMD inference'}
    return {'schema':SCHEMA,'key':receipt['key'],
        'packed_sha256':receipt['packed_sha256'],
        'input_sha256':receipt['input_sha256'],
        'native_render_receipt_sha256':None,
        'native_hz':RATE,'native_bits_per_sample':1,
        'bit_order':'MSB first; 1->+1, 0->-1',
        'normalization':'one-sided Hann Welch density scaled so integrated bipolar +/-1 power is 1; dB=10log10(power)',
        'nfft':FFT_SIZE,'overlap':0,'segments':n_segments,
        'segment_duration_s':FFT_SIZE/RATE,'source_analysis_start_s':start_frame/RATE,
        'source_analysis_stop_s':(start_frame+n_segments*FFT_SIZE)/RATE,
        'total_bipolar_power':full,
        'bands':output,'illustrative_filters':weights,
        'interpretation':'Raw native PSD power, NOT reconstructed sine-equivalent residual dBFS or analog hardware certification.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packed',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--compare',type=Path)
    args=p.parse_args()
    receipt=json.loads(args.receipt.read_text());result=analyze(args.packed,receipt)
    result['native_render_receipt_sha256']=sha(args.receipt)
    if args.compare:
        prior=json.loads(args.compare.read_text())
        # Regenerate FFT results; compare all the authoritative numerical
        # fields, not only presence/finite shape. Published timestamps absent.
        if prior!=result:raise ValueError('Independently reproduced native PSD differs from archived result')
        print('WELCH_REPRODUCED',receipt['key'])
    else:
        write_once(args.output,result)
        print('NATIVE_PSD',receipt['key'],{k:round(v['integrated_power_db'],2)
              for k,v in result['bands'].items()},flush=True)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError) as exc:
        print('R2 NATIVE PSD FAIL',str(exc),file=sys.stderr);sys.exit(2)
