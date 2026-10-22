#!/usr/bin/env python3
"""Continuous deterministic 32s study-only composite stimulus.

Not equivalent to P20's 60-minute soak, nor to a hardware/player test.
"""
import hashlib,json
from pathlib import Path
import numpy as np
fs=176400; seconds=32;segment=4*fs
path=Path(__file__).resolve().parent/'replay-holdouts/stress32.f64le'
path.parent.mkdir(parents=True,exist_ok=True)
with path.open('wb') as f:
 rng=np.random.default_rng(20261022)
 def write(x):
  assert np.all(np.isfinite(x)) and np.max(abs(x))<=.8+1e-10
  f.write(np.asarray(x,dtype='<f8').tobytes())
 t=np.arange(segment,dtype=np.float64)/fs
 def taper(x):
  x=x.copy();N=round(.02*fs); z=np.arange(N,dtype=np.float64)/N; w=z*z*z*(10+z*(-15+6*z));x[:N]*=w;x[-N:]*=w[::-1];return x
 write(np.zeros(segment))
 write(np.full(segment,.7))
 write(np.full(segment,-.7))
 write(taper(.15*sum(np.sin(2*np.pi*v*t) for v in (53,997,5501,17011))))
 write(taper(.4*rng.uniform(-1.,1.,size=segment)))
 write(taper(.8*np.sin(2*np.pi*997*t)))
 write(taper(.6*np.sin(2*np.pi*20000*t)))
 write(np.zeros(segment))
s=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({'source':str(path),'sha256':s,'input_hz':fs,'seconds':seconds,'samples':segment*8,
 'shape':'4s each: zero,+0.7 DC,-0.7 DC, multitones, seeded uniform .4, 997Hz .8, 20kHz .6, zero; tapers on oscillatory/noisy segments'},indent=2))
