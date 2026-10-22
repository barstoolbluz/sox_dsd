#!/usr/bin/env python3
"""Reproducible, nonproduction linearized-NTF screening of SoX SDM recurrences.

N.B. The one-bit closed loop is NONLINEAR: the linearized NTF, Lee peak and
linear poles cannot certify numerical stability or audio quality. Confirm
candidate behavior using the exact native renderer before drawing conclusions.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

RATE=22579200
SOURCE=Path(__file__).resolve().parents[3]/'src/sdm.c'
FREQS_BAND=np.linspace(0,150000,751)
FREQS_GLOBAL=np.geomspace(150001,RATE/2,301)
FREQS=np.r_[FREQS_BAND,FREQS_GLOBAL]
Z=np.exp(2j*np.pi*FREQS/RATE)


def legacy_coeffs():
    source=SOURCE.read_text().split('static const sdm_filter_t sdm_filters[] = {')[1]
    pat=r'\{\s*\{([\d\s.,+eE-]+)\},\s*\{([\d\s.,+eE-]+)\},\s*(\d+),\s*(\d+)\s*\*\s*44100,\s*"([^"]+)"'
    out={}
    for a,g,order,rate,name in re.findall(pat,source):
        if int(rate)!=256 or name not in [f'sdm-{i}' for i in range(4,8)]+['clans-7']:continue
        v=np.array([float(x) for x in a.split(',') if x.strip()]); w=np.array([float(x) for x in g.split(',') if x.strip()]); n=int(order)
        assert len(v)==n and len(w)<=n
        out[name]=(v,np.pad(w,(0,n-len(w))))
    assert len(out)==5
    return out

def linear_model(a,g):
    """Reference C loop: s'=M*s+e0*(x-y_prev), v=x+a.s', y=Q(v).

    For additive quantizer noise e: NTF(z)=det(zI-M)/det(zI-M+e0*a^T).
    Both polynomials monic, so NTF tends to 1 at high frequency.
    """
    n=len(a); m=np.eye(n)
    for i in range(1,n):m[i,i-1]=1
    for i in range(n-1):m[i,i+1]=-g[i]
    b=np.zeros(n);b[0]=1
    poles=np.linalg.eigvals(m-np.outer(b,a)); zeros=np.linalg.eigvals(m)
    # Products of roots avoid extreme cancellation in polynomial coefficients.
    h=np.prod(Z[:,None]-zeros[None,:],axis=1)/np.prod(Z[:,None]-poles[None,:],axis=1)
    return h,poles,zeros


def metrics(a,g):
    h,p,z=linear_model(a,g); pw=np.abs(h)**2
    def band(u): return 10*np.log10(max(float(np.mean(pw[:len(FREQS_BAND)][FREQS_BAND<=u])),1e-300))
    return dict(ntf_rms_0_20k_db=band(20000),ntf_rms_0_40k_db=band(40000),
        ntf_rms_0_100k_db=band(100000),ntf_rms_0_150k_db=band(150000),
        ntf_max_gain=float(np.max(abs(h))),
        pole_max_radius=float(np.max(abs(p))),
        zeros=[(float(z0.real),float(z0.imag)) for z0 in z],
        poles=[(float(p0.real),float(p0.imag)) for p0 in p])


def optimize(order, bandwidth, seed, rng, nstarts=3):
    a0,g0=seed; indices=np.flatnonzero(g0)
    n=len(a0); k=len(indices)
    # bounded smooth parameterization of a and nonzero g (the loop topology
    # and zero pattern are unchanged). Strict Lee-like linear-screen heuristic:
    # peak NTF <=1.6, closed-loop pole radius <=0.98. These are not proofs.
    bounds=[(math.log(.60),math.log(1.60))]*n+[(math.log(.3),math.log(28.))]*k
    mask=FREQS_BAND<=bandwidth
    score_trace=[]
    def calc(x,raw=False):
        a=a0*np.exp(x[:n]); g=g0.copy(); g[indices]*=np.exp(x[n:]);
        if raw:return a,g
        try:
            h,p,_=linear_model(a,g)
            if not np.all(np.isfinite(h)):return 1e5
            rho=float(np.max(abs(p)));peak=float(np.max(abs(h)))
            bandpower=float(np.mean(abs(h[:len(FREQS_BAND)])[mask]**2))
            val=10*math.log10(max(bandpower,1e-300))
            # Soft penalties mean unacceptable results can be screened OUT,
            # instead of silently forcing them into a feasible class.
            val+=260*max(0,peak-1.60)**2+4000*max(0,rho-.98)**2
            val+=0.025*float(x@x)
            return val
        except (FloatingPointError, OverflowError, ZeroDivisionError,ValueError):return 1e5
    starts=[np.r_[np.zeros(n),np.full(k,math.log(2.))],
            np.r_[np.full(n,math.log(1.06)),np.full(k,math.log(6.))],
            np.r_[np.full(n,math.log(1.04)),np.full(k,math.log(12.))]]
    good=[]
    for idx,x0 in enumerate(starts[:nstarts]):
        r=minimize(calc,x0,bounds=bounds,method='L-BFGS-B',
            options={'maxiter':125,'ftol':1e-9,'maxls':20})
        a,g=calc(r.x,True); met=metrics(a,g)
        passed=(met['ntf_max_gain']<=1.61 and met['pole_max_radius']<=.981)
        score_trace.append(dict(start=idx,iterations=int(r.nit),evaluations=int(r.nfev),
                         optimizer_success=bool(r.success),loss=float(r.fun),
                         feasible_screen=bool(passed),band_rms_db=met[f'ntf_rms_0_{bandwidth//1000}k_db']))
        if passed:good.append((met[f'ntf_rms_0_{bandwidth//1000}k_db'],a,g,met,idx))
    if not good:return None,score_trace
    best=min(good,key=lambda t:t[0]); return best,score_trace


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--starts',type=int,default=3)
    a=p.parse_args()
    seeds=legacy_coeffs(); rng=np.random.default_rng(20261022)
    data={'schema':'experimental-NTF-design/1','native_hz':RATE,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'notes':['Models linearized one-bit recurrence; not a stability certificate.',
                   'Design degrees of freedom: existing positive a and nonzero g coefficients with bounded log-multipliers.',
                   'Reference source family: historical SDM order 4-7 at DSD256; current CLANS-7 as a separate unchanged reference.',
                   'Hinf<=1.61, max linear-pole modulus<=0.981 are heuristic screens, not sufficient for stability.',
                   'Uniform-frequency band integrated magnitude; applied before nonlinear native screening.'], 'designs':{},'references':{}}
    for name,(aa,gg) in seeds.items():
        data['references'][name]={'order':len(aa),'a':[float(x).hex() for x in aa], 'g':[float(x).hex() for x in gg], 'linearized_ntf':metrics(aa,gg)}
    for order in (4,5,6,7):
        for bw in (100000,150000):
            key=f'order{order}-band{bw//1000}k'
            best,trace=optimize(order,bw,seeds[f'sdm-{order}'],rng,a.starts)
            if best is None:
                print('UNFEASIBLE',key,flush=True);data['designs'][key]={'screen_rejected':True,'optimizer_starts':trace};continue
            metric,aa,gg,met,seedid=best
            data['designs'][key]={'order':order,'bandwidth_hz':bw,'a':[float(x).hex() for x in aa],
               'g':[float(x).hex() for x in gg],'linearized_ntf':met,
               'screen_rejected':False,'selected_start':seedid,'optimizer_starts':trace}
            print(key,'approx',round(metric,2),'max gain',round(met['ntf_max_gain'],3),
                  'pole',round(met['pole_max_radius'],5),flush=True)
            tmp=Path(a.output);tmp.parent.mkdir(parents=True,exist_ok=True)
            tmp.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp=Path(a.output);tmp.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
