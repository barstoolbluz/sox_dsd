#!/usr/bin/env python3
"""Deterministic holdout stimuli, distinct from NTF optimization stimulus."""
import hashlib,json,math
from pathlib import Path
import numpy as np
Fs=176400;Dur=1.2;N=round(Fs*Dur);n=np.arange(N,dtype=np.float64);t=n/Fs
root=Path(__file__).resolve().parent/'replay-holdouts';root.mkdir(exist_ok=True)
rng=np.random.default_rng(0x510D512)
def taper(x):
 x=x.copy(); nt=round(.025*Fs);q=np.arange(nt,dtype=np.float64)/nt;r=q*q*q*(10+q*(-15+6*q));x[:nt]*=r;x[-nt:]*=r[::-1];return x
signals={
 'silence':np.zeros(N),
 'step-dc':np.where((t>=.15)&(t<.55),.7,np.where((t>=.55)&(t<.95),-.7,0.)).astype('float64'),
 'tone997-hot':taper(.95*np.sin(2*np.pi*997*t)),
 'tone997-quiet':taper(.02*np.sin(2*np.pi*997*t)),
 'tone20000':taper(.60*np.sin(2*np.pi*20000*t)),
 'tone40000':taper(.60*np.sin(2*np.pi*40000*t)),
 'multitone':taper(.15*sum(np.sin(2*np.pi*f*t) for f in (53,997,5501,17011))),
 'noise':taper(.7*rng.uniform(-1.,1.,size=N)),
 'noise-safe':taper(.4*np.random.default_rng(0x510D512).uniform(-1.,1.,size=N)),
}
manifest={}
for name,samples in signals.items():
 assert np.max(np.abs(samples))<=1 and len(samples)==N
 data=samples.astype('<f8').tobytes();path=root/(name+'.f64le')
 if path.exists() and path.read_bytes()!=data:raise RuntimeError('Refusing to overwrite differing holdout')
 path.write_bytes(data)
 manifest[name]={'sha256':hashlib.sha256(data).hexdigest(),'frames':N,'seconds':Dur,
                 'max_abs':float(np.max(np.abs(samples))),'rms':float(np.sqrt(np.mean(samples*samples)))}
print(json.dumps(manifest,indent=2)); (root/'stimuli-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
