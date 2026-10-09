#!/usr/bin/env python3
"""Independent finite-composite DSD->F64 validation across 48-kHz rates.

The intermediate FIR is rebuilt as direct equivalent polynomial convolution
from the certified P06 coefficient *values*, not production ring/filter state.
The final SRC uses independently designed 180dB Kaiser-windowed-sinc FIR.
No LSB proof is transferred from the FIR stage to the final SRC.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import subprocess
try:
    import numpy as np
    from scipy.signal import firwin,resample_poly,fftconvolve
    from certify_filters import load_coefficients
except ImportError as error:
    print(f"UNRUN required P07 composite reference (missing {error.name})", file=__import__("sys").stderr)
    raise SystemExit(2) from None

N=262144
CASES=(('master64',48000),('master128',96000),('master256',192000),
       ('wide64',48000),('wide128',96000),('wide256',192000),
       ('master64',88200),('wide128',176400))


def effective_filter(banks,names):
    filt=np.array([1.],dtype=np.float64)
    for stage,name in enumerate(names):
        unit=np.zeros((len(banks[name])-1)*(1<<stage)+1,dtype=np.float64)
        unit[::1<<stage]=banks[name]
        filt=np.convolve(filt,unit)
    return filt


def reference(profile,meta,rate,banks):
    h=effective_filter(banks,meta['stage_banks'])
    G,D=meta['delay_native_frames'],meta['factor']
    x=np.where((np.arange(N)//512)&1,-1.,1.)
    signal=fftconvolve(x,h)
    mid=signal[G+np.arange((N+D-1)//D)*D]
    if rate==meta['intermediate_hz']:
        return mid
    up=rate//math.gcd(rate,meta['intermediate_hz'])
    down=meta['intermediate_hz']//math.gcd(rate,meta['intermediate_hz'])
    high=max(up,down)
    taps=401*high+1
    if taps%2==0:taps+=1
    fir=firwin(taps,0.975/high,window=('kaiser',18.9))
    return resample_poly(mid,up,down,window=fir)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--unit',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    manifest=json.loads((Path(__file__).parent/'reference'/'p06_coefficients.json').read_text())
    banks=load_coefficients()
    rows=[]
    for key,output in CASES:
        meta=manifest['profiles'][key]
        native=meta['native_hz']
        family=int(key.startswith('wide'))
        cp=subprocess.run([str(a.unit.resolve()),'--dsd',str(native),str(output),
                           str(family),str(N)],capture_output=True,timeout=90)
        if cp.returncode:
            raise RuntimeError((key,output,cp.returncode,cp.stderr.decode(errors='replace')[:250]))
        got=np.frombuffer(cp.stdout,dtype='<f8')
        length=(N*output+native//2)//native
        assert len(got)==length,(key,output,len(got),length)
        ref=reference(key,meta,output,banks)[:length]
        assert len(ref)==length,(key,output,len(ref),length)
        err=np.abs(got-ref)
        edge=max(64,length//10)
        interior=err[edge:-edge] if length>2*edge else err
        row=dict(profile=key,native_hz=native,output_hz=output,
                 frames=length,max_abs=float(err.max(initial=0)),
                 interior_abs_max=float(interior.max(initial=0)),
                 rms=float(np.sqrt(np.mean(err*err))),
                 interior_rms=float(np.sqrt(np.mean(interior*interior))),
                 comparator='independent finite P06 equivalent FIR convolution; separate windowed-sinc SRC')
        # A separate composite tolerance (two independently designed
        # finite-window SRCs differ at the boundaries). Compare *all*
        # endpoints and report them; do not apply the P06 FIR LSB envelope.
        if row['interior_abs_max'] > 2.e-9 or row['max_abs'] > .0085:
            raise AssertionError(f'finite composite reference tolerance exceeded: {row}')
        rows.append(row)
        print(f'{key} -> {output}: max={row["max_abs"]:.6g}, '
              f'interior={row["interior_abs_max"]:.6g}',flush=True)
    result=dict(schema='sox.dsd.p07.independent-finite-composite.v1',
                description='End-to-end samples and count at original native clock, including boundaries',
                interior_tolerance_abs=2.e-9,full_endpoint_tolerance_abs=.0085,
                cases=rows)
    a.results.mkdir(parents=True,exist_ok=True)
    path=a.results/'composite-reference.json'
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');tmp.replace(path)
    return 0
if __name__=='__main__':raise SystemExit(main())
