#!/usr/bin/env python3
"""Independent final SRC comparison with SciPy rational polyphase FIR.

The production resampler's multi-stage -B95 180dB design is not reused.
The reference designs its own high-order Kaiser windowed-sinc FIR; numerical
acceptance is a *measured composite comparison*, never the P06 FIR bound.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import subprocess
try:
    import numpy as np
    from scipy.signal import firwin,resample_poly
except ImportError as error:
    print(f"UNRUN required P07 independent SRC reference (missing {error.name})", file=__import__("sys").stderr)
    raise SystemExit(2) from None

RATIOS=((88200,48000),(176400,96000),(352800,192000),
        (88200,96000),(176400,48000),(352800,384000))
LENGTH=65536


def src_signal(frequency, length=LENGTH):
    t=np.arange(length,dtype=np.float64)/frequency
    return .23*np.sin(2*np.pi*1007.3*t)+.17*np.cos(2*np.pi*4231.7*t)+\
           .02*np.sin(2*np.pi*15329.31*t)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    opts=parser.parse_args()
    rows=[]
    for input_hz,output_hz in RATIOS:
        run=subprocess.run([str(opts.unit.resolve()),str(input_hz),str(output_hz),str(LENGTH)],
                           capture_output=True,timeout=40)
        if run.returncode:raise RuntimeError((input_hz,output_hz,run.stderr.decode()[:500]))
        actual=np.frombuffer(run.stdout,dtype='<f8').copy()
        up=output_hz//math.gcd(input_hz,output_hz)
        down=input_hz//math.gcd(input_hz,output_hz)
        high=max(up,down)
        taps=401*high+1
        if taps%2==0:taps+=1
        # FIR cutoff halfway between 0-dB 95% and alias-free 100% of the
        # smaller Nyquist; 401 ratio units make 180-dB stopband feasible.
        ref_fir=firwin(taps,0.975/high,window=('kaiser',18.9))
        reference=resample_poly(src_signal(input_hz),up,down,window=ref_fir)
        desired=(LENGTH*output_hz+input_hz//2)//input_hz
        reference=reference[:desired]
        if len(actual)!=desired or len(reference)!=desired:
            raise AssertionError((input_hz,output_hz,len(actual),len(reference),desired))
        e=actual-reference
        # Full boundary values are included in metrics, but separate from
        # interior precision: two dissimilar FIR designs have different
        # finite-end convolution kernels, even with matching passband.
        edge=max(64,int(desired*.08))
        central=e[edge:-edge] if 2*edge<desired else e
        abs_max=float(np.max(np.abs(e)))
        interior_max=float(np.max(np.abs(central)))
        interior_rms=float(np.sqrt(np.mean(central*central)))
        row=dict(input_hz=input_hz,output_hz=output_hz,up=up,down=down,
                frames=desired,reference_taps=len(ref_fir),
                full_abs_max=abs_max,interior_abs_max=interior_max,
                interior_rms=interior_rms,signal_peak=float(max(np.abs(reference))),
                ref_method='independent SciPy Kaiser-window rational FIR',
                production_method='rate.c multistage 180-dB linear-phase -B95')
        # This is a measured SRC tolerance, *not* the P06 scalar-FIR
        # one-int32-LSB contract. Full endpoint differences are measured
        # against a different reference filter window.
        if interior_max > 5.e-10 or abs_max > .004:
            raise AssertionError(f'SRC independent reference exceeded tolerance: {row}')
        rows.append(row)
        print(f'{input_hz}->{output_hz}: interior_max={interior_max:.6g} '
              f'interior_rms={interior_rms:.6g} edge_max={abs_max:.6g}',flush=True)
    report=dict(schema='sox.dsd.p07.independent-src.v1',cases=len(rows),
                tolerance_note='Measured comparison to independently designed 180dB windowed-sinc SRC, not the P06 scalar FIR LSB bound',
                source_length=LENGTH,interior_tolerance_abs=5.e-10,
                full_endpoint_tolerance_abs=.004,results=rows)
    opts.results.mkdir(parents=True,exist_ok=True)
    p=opts.results/'src-reference.json';q=p.with_suffix('.tmp')
    q.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');q.replace(p)
    return 0
if __name__=='__main__':raise SystemExit(main())
