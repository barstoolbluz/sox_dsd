#!/usr/bin/env python3
"""Feasibility probe, not a release coefficient generator/certification suite."""
import json,pathlib,numpy as np
from scipy import signal
OUT=pathlib.Path(__file__).resolve().parent
A=190.; beta=0.1102*(A-8.7)
def design(p,s,hb=False):
    n=int(np.ceil((A-8)/(2.285*2*np.pi*(s-p))))+1
    n+= (1-n)%4
    while True:
        h=signal.firwin(n,(p+s)/2,window=('kaiser',beta),fs=1.,scale=True)
        if hb:
            mid=n//2; inds=np.arange(n)
            h[(inds-mid)%2==0]=0.;h[mid]=.5
            side=inds!=mid;h[side]*=.5/np.sum(h[side])
        f,H=signal.freqz(h,worN=1<<19,fs=1.)
        ripple=np.max(np.abs(20*np.log10(np.abs(H[f<=p]))))
        stop=20*np.log10(np.max(np.abs(H[f>=s])))
        if ripple<5e-7 and stop < -185:break
        n+=4
        if n>2001:raise RuntimeError('no design found')
    return h,{'taps':len(h),'pass_cycles_per_input':p,'stop_cycles_per_input':s,'max_abs_pass_error_db':float(ripple),'max_stop_db':float(stop),'dc_gain':float(sum(h)),'beta':beta}
hb,mhb=design(.10,.40,True)
filters={'halfband':hb};meta={'halfband':mhb}
for name,p,s in [('master64_256',20000/176400,40000/176400),('master128',30000/352800,60000/352800),('wide',.2,.25)]:
    filters[name],meta[name]=design(p,s)
# Evaluate equivalent cascade on a dense full-Nyquist grid, including folded stage frequencies.
profiles={}
for k in (64,128,256):
  fs=44100*k
  for prof in ('master','wide'):
    if prof=='wide': R=fs//32; P=.4*R; S=.5*R;last='wide'
    else:
      R={64:88200,128:176400,256:176400}[k]
      P={64:20000,128:30000,256:40000}[k];S=2*P;last='master128' if k==128 else 'master64_256'
    D=fs//R;J=D.bit_length()-1;bank=[hb]*(J-1)+[filters[last]]
    f=np.linspace(0,fs/2,1<<18);H=np.ones(f.size,dtype=np.complex128)
    for j,h in enumerate(bank):H*=signal.freqz(h,worN=2*np.pi*f/(fs/(2**j)))[1]
    ripple=float(np.max(np.abs(20*np.log10(np.maximum(np.abs(H[f<=P]),1e-300)))))
    # Coherent sum of all unwanted images that fold into the desired passband.
    fb=np.linspace(0,P,4097);alias=np.zeros_like(fb)
    for image in range(1,D):
      ff=fb+image*R;hh=np.ones(fb.size,dtype=np.complex128)
      for j,h in enumerate(bank):hh*=signal.freqz(h,worN=2*np.pi*ff/(fs/(2**j)))[1]
      alias+=np.abs(hh)
    G=sum((len(h)-1)//2*(2**j)for j,h in enumerate(bank))
    profiles[f'{prof}{k}']={'source_hz':fs,'intermediate_hz':R,'factor':D,'pass_hz':P,'stop_hz':S,'taps':[len(h)for h in bank],'aggregate_ripple_db':ripple,'aggregate_stop_db':float(20*np.log10(np.max(np.abs(H[f>=S])))),'coherent_alias_sum_db':float(20*np.log10(max(alias))),'delay_input_frames':G,'delay_seconds':G/fs,'output_phase':G%D,'discard_output_frames':G//D}
result={'method':'Kaiser-windowed sinc, candidate binary64 coefficients; dense-grid feasibility only','filters':meta,'profiles':profiles}
(OUT/'filter_feasibility.json').write_text(json.dumps(result,indent=2)+'\n')
np.savez(OUT/'candidate_filter_coefficients.npz',**filters)
print(json.dumps(result,indent=2))
