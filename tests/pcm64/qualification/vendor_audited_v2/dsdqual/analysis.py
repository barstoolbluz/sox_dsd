"""Matched native-input residual metrology, with explicit phase and leakage controls."""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from .dsf import read_channel_window,read_packed_window

BANDS={'20_20k':(20,20000),'20_30k':(20,30000),'20_40k':(20,40000),'20_50k':(20,50000),'20k_30k':(20000,30000),'30k_50k':(30000,50000),'50k_100k':(50000,100000),'100k_500k':(100000,500000),'500k_1m':(500000,1000000)}

def plan_windows(frames,fs,seconds=0.5,segments=3):
    if not (0.1<=seconds<=2.0 and 1<=segments<=9):raise ValueError('invalid window recipe')
    n=int(round(seconds*fs))
    margin=int(round(.1*fs))
    if frames<n+2*margin:raise ValueError('audio too short for valid steady-state windows; minimum = window+0.2 s')
    first=margin;last=frames-margin-n
    count=min(segments,max(1,(last-first)//n+1))
    if count==1:return [(first,n)]
    points=[int(round(first+(last-first)*i/(count-1))) for i in range(count)]
    if len(set(points))!=len(points):raise RuntimeError('duplicate spectral windows')
    return [(p,n) for p in points]

def bandpower(e,fs,beta):
    n=len(e)
    if not n:raise ValueError('zero samples')
    w=np.kaiser(n,beta)
    # Weighted DC removal; no removal of musical carriers or harmonics.
    sumw2=np.dot(w,w)
    dc=np.dot(e,w*w)/sumw2
    ew=(e-dc)*w
    z=np.fft.rfft(ew)
    power=(z.real*z.real+z.imag*z.imag)/(n*sumw2)
    if n>2:power[1:-1]*=2
    f=np.fft.rfftfreq(n,1/fs)
    result={}
    for k,(lo,hi) in BANDS.items():
        if hi>fs/2:continue
        left=int(np.searchsorted(f,lo,'left'));right=int(np.searchsorted(f,hi,'left'))
        use=power[left:right]
        result[k]={'power':float(np.sum(use,dtype=np.float64)),'max_1bin_dbfs':10*math.log10(max(float(np.max(use))/.125,1e-300)) if len(use) else None}
    return result

def compare(source_dsf,info,channel,packed,native_windows,windows,shift,candidate_shift,betas):
    records=[]
    for (start,length),path in zip(windows,native_windows):
        native=np.fromfile(path,dtype='<f8')
        if len(native)!=length:raise ValueError('incomplete native window '+str(path))
        if start+shift<0 or start+shift+length>info['frames'] or start+candidate_shift<0 or start+candidate_shift+length>info['frames']:raise ValueError('invalid measured timing correction')
        q0=read_channel_window(source_dsf,info,channel,start+shift,length)
        q1=read_packed_window(packed,start+candidate_shift,length)
        e0=q0.astype(np.float64)-native
        e1=q1.astype(np.float64)-native
        for beta in betas:
            m0=bandpower(e0,info['rate'],beta);m1=bandpower(e1,info['rate'],beta)
            result={}
            for key in m0:
                p0=m0[key]['power'];p1=m1[key]['power']
                result[key]={'legacy_dbfs':10*math.log10(max(p0/.125,1e-300)),'candidate_dbfs':10*math.log10(max(p1/.125,1e-300)),'delta_db':10*math.log10(max(p1,1e-300)/max(p0,1e-300)),'legacy_max_1bin_dbfs':m0[key]['max_1bin_dbfs'],'candidate_max_1bin_dbfs':m1[key]['max_1bin_dbfs']}
            records.append({'start_frame':start,'duration_frames':length,'window_kaiser_beta':beta,'bands':result,'native_peak':float(np.max(np.abs(native)))})
    aggregate={}
    for key in sorted({b for r in records for b in r['bands']}):
        aggregate[key]={}
        for beta in betas:
            vals=[r['bands'][key]['delta_db'] for r in records if r['window_kaiser_beta']==beta]
            aggregate[key][str(beta)]={'median_delta_db':float(np.median(vals)),'worst_delta_db':float(np.max(vals)),'best_delta_db':float(np.min(vals)),'per_window_delta_db':vals}
        agg_betas=[aggregate[key][str(b)]['median_delta_db'] for b in betas]
        aggregate[key]['beta_sensitivity_db']=float(max(agg_betas)-min(agg_betas))
        # Median agreement must not conceal a single window's changed verdict.
        aggregate[key]['max_per_window_beta_sensitivity_db']=float(max(
            max(r['bands'][key]['delta_db'] for r in records if r['start_frame']==start)
            -min(r['bands'][key]['delta_db'] for r in records if r['start_frame']==start)
            for start in {r['start_frame'] for r in records}))
    return {'per_window':records,'aggregate':aggregate,'legacy_shift_samples':shift,'candidate_shift_samples':candidate_shift,'windows':windows,'scope':'native q-x residual: DC removed; named carriers retained; independent matched input; not a DAC audible-noise theorem','reference_peak_dsd_full_scale':0.5}
