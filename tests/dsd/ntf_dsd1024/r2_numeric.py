#!/usr/bin/env python3
"""Independent FFT/reconstruction numeric replay from SHA-bound native bits.

Offline metadata verification is NOT a replacement for this bitstream-bound
calculation. Recreate the packed stream from the specified native binary and
require its hash to equal the unmodified R1 receipt before calling this.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.signal import upfirdn, firwin

from model import WORKING, RATE, sha
from study import native_pass, write_once

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
GROUPS={'0_40k':((0,20000),(20000,40000)),
        '40_100k':((40000,60000),(60000,80000),(80000,100000)),
        '100_150k':((100000,120000),(120000,150000)),
        '150_176p4k':((150000,176400),)}
WINDOWS={'primary':(997.,.4,1.2),
         'tone-20k':(20000.,.25,.95),
         'tone-40k':(40000.,.25,.95)}


def independent_levels(packed: Path, *, tone: float, start: float, stop: float,
                       alternative: bool=False) -> dict[str,float]:
    """Explicit seven-stage decimation, QR sine+DC fit, and Welch-like FFT band energy.

    Calculations are programmed separately from study.decode_and_spectrum and
    the earlier DSD512 analyzer; they share immutable reference FIR coefficients.
    They are NOT independent of the chosen reconstruction transfer function.
    """
    sys.path.insert(0,str(HERE.parent))
    from p20_audio_compare import coefficients
    h=coefficients('halfband')
    last=firwin(601 if alternative else 401,176400,fs=705600,
                window=('kaiser',25 if alternative else 22))
    with packed.open('rb') as f:
        arr=np.frombuffer(f.read(),dtype=np.uint8)
    y=np.unpackbits(arr,bitorder='big').astype('float64')*2.-1.
    for stage in range(7):
        y=upfirdn(last if stage==6 else h,y,down=2)
    sr=352800
    first=int(start*sr);lastidx=int(stop*sr)
    data=y[first:lastidx]
    n=data.size
    if n<1000:raise ValueError('Numerical source window too short')
    sample=np.arange(first,lastidx,dtype='float64')
    phase=2*np.pi*tone*sample/sr
    basis=np.column_stack((np.sin(phase),np.cos(phase),np.ones(n)))
    coeff, *_=np.linalg.lstsq(basis,data,rcond=None)
    residual=data-basis@coeff
    window=np.kaiser(n,30)
    spec=np.fft.rfft(residual*window)
    freq=np.fft.rfftfreq(n,1/sr)
    power=(spec.real**2+spec.imag**2)/(n*n*float(np.mean(window**2)))
    power[1:-1]*=2
    group={}
    for name,bands in GROUPS.items():
        integrated=0.
        for lo,hi in bands:
            sel=(freq>=lo)&(freq<hi if hi<sr/2 else freq<=hi)
            integrated+=float(np.sum(power[sel],dtype=np.float64))
        group[name]=float(10*math.log10(max(2*integrated,1e-300)))
    if not all(math.isfinite(v) for v in group.values()):
        raise ValueError('Nonfinite independent spectral metric')
    return group


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=WINDOWS,default='primary')
    p.add_argument('--key',required=True)
    p.add_argument('--packed',required=True,type=Path)
    p.add_argument('--native-receipt',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    case=args.case
    receipt=json.loads(args.native_receipt.read_text())
    source_manifest=json.loads((E/'stimuli-manifest.json').read_text())['cases'][case]
    rp=(E/'primary'/f'{args.key}.json') if case=='primary' else (E/'finalists'/case/f'{args.key}.json')
    sr=(E/'spectra'/f'{args.key}.json') if case=='primary' else (E/'holdout-spectra'/case/f'{args.key}.json')
    frozen=json.loads(rp.read_text());published=json.loads(sr.read_text())
    if (receipt['key']!=args.key or receipt['input_sha256']!=source_manifest['sha256']
        or receipt['input_frames']!=source_manifest['frames']
        or receipt['packed_sha256']!=frozen['packed_sha256']
        or receipt['packed_sha256']!=published['packed_sha256']
        or sha(args.packed)!=receipt['packed_sha256'] or not native_pass(receipt)[0]):
        raise ValueError('Replay does not match the original R1 exact native source/bitstream')
    tone,start,stop=WINDOWS[case]
    x=published['spectrum']
    if (x['fit_tone_hz'],x['start_s'],x['stop_s'])!=(tone,start,stop):
        raise ValueError('Published spectrum has incorrect source plateau or frequency')
    bands=independent_levels(args.packed,tone=tone,start=start,stop=stop)
    delta={name:bands[name]-published['integrated_sine_equivalent_dbfs'][name] for name in bands}
    if max(abs(d) for d in delta.values())>.05:
        raise ValueError('Numerically independent reconstruction difference exceeds 0.05dB')
    result={'schema':'DSD1024-NTF-R2-independent-reconstruction/1',
            'key':args.key,'case':case,'packed_sha256':receipt['packed_sha256'],
            'source_sha256':source_manifest['sha256'],
            'native_replay_receipt_sha256':sha(args.native_receipt),
            'original_spectrum_sha256':sha(sr),'source_window_s':[start,stop],
            'source_tone_hz':tone,'recomputed_sine_equivalent_dbfs':bands,
            'delta_from_original_db':delta,
            'method':'second standalone FFT implementation, source-bound, identical reference FIR coefficients',
            'qualified':False}
    write_once(args.output,result)
    print('R2_NUMERIC_REPLAY',args.key,case,'max difference dB',max(abs(v) for v in delta.values()))

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as exc:
        print('R2 NUMERIC FAIL',type(exc).__name__,exc,file=sys.stderr)
        sys.exit(2)
