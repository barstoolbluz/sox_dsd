"""Independent historical-harness measurement semantics, on matched q - x.

The arithmetic follows the unmodified audited harness's dsdqual/analysis.py:
0.5-second windows for the long metrology family, 0.1-second boundary
margins, weighted DC using w**2, Kaiser beta 30/34, one-sided power,
N*sum(w**2) normalization, nine half-open bands, DSD full-scale .5.
This code never imports the native64 generator or its analysis function.
"""
from __future__ import annotations
import math
import numpy as np

BANDS={'20_20k':(20,20000),'20_30k':(20,30000),
       '20_40k':(20,40000),'20_50k':(20,50000),
       '20k_30k':(20000,30000),'30k_50k':(30000,50000),
       '50k_100k':(50000,100000),'100k_500k':(100000,500000),
       '500k_1m':(500000,1000000)}
BETAS=(30.0,34.0)
FS_POWER=.125

def analyze(residual,rate,beta):
    e=np.asarray(residual,dtype=np.float64)
    n=e.size
    if n==0 or not np.all(np.isfinite(e)) or not (0 < beta < 40):
        raise ValueError('invalid physical residual/window')
    w=np.kaiser(n,beta)
    w2=w*w
    power_w=float(np.dot(w,w))
    dc=float(np.dot(e,w2)/power_w)
    ew=(e-dc)*w
    z=np.fft.rfft(ew)
    powers=(z.real*z.real+z.imag*z.imag)/(n*power_w)
    if n>2:powers[1:-1]*=2
    f=np.fft.rfftfreq(n,1/rate)
    bands={}
    for key,(lo,hi) in BANDS.items():
        if hi>rate/2:
            raise ValueError('band exceeds Nyquist')
        a=int(np.searchsorted(f,lo,side='left'))
        b=int(np.searchsorted(f,hi,side='left'))
        if b<=a:raise ValueError('band has no bins: '+key)
        p=float(np.sum(powers[a:b],dtype=np.float64))
        if not math.isfinite(p) or p<0:raise ValueError('invalid band power')
        bands[key]={'power':p,'dbfs':10*math.log10(max(p/FS_POWER,1e-300)),
                    'bins':[a,b]}
    return dc,bands

def compare(stored,recomputed,where):
    actual_dc,actual_bands=recomputed
    if not math.isclose(stored['weighted_dc'],actual_dc,rel_tol=0,abs_tol=1e-13):
        raise AssertionError(where+': weighted DC changed')
    if set(stored['bands'])!=set(BANDS):
        raise AssertionError(where+': missing/changed band names')
    for name,value in actual_bands.items():
        seen=stored['bands'][name]
        p=seen['power']
        if not isinstance(p,(int,float)) or not math.isfinite(p) or p<0:
            raise AssertionError(where+': invalid power')
        if (seen['bins']!=value['bins'] or
                not math.isclose(seen['dbfs'],10*math.log10(max(p/FS_POWER,1e-300)),rel_tol=0,abs_tol=1e-11) or
                not math.isclose(p,value['power'],rel_tol=5e-7,abs_tol=0)):
            raise AssertionError(where+': corrupted '+name)
