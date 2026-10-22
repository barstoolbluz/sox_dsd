#!/usr/bin/env python3
"""Held-out 997/20k/40k tone residuals (independent of optimization test)."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from scipy.signal import firwin
from analyze_renders import BANDS,decode,residual_and_bands,publish,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True)
 a=p.parse_args();sys.path.insert(0,str(a.source_root/'tests/dsd'))
 import p20_audio_compare
 h=p20_audio_compare.coefficients('halfband')
 final=firwin(401,176400,fs=705600,window=('kaiser',22))
 for case,tone in [('tone997-hot',997),('tone997-quiet',997),('tone20000',20000),('tone40000',40000)]:
  for checkout,key in [('renders','P20-CLANS7-baseline'),('renders','order6-band100k'),('renders-sweep','order7-pareto-g3p0')]:
   path=a.root/case/checkout/(key+'.receipt.json');rec=json.loads(path.read_text())
   assert rec['returncode']==0,(case,key)
   packed=path.with_name(key+'.packed')
   assert sha(packed)==rec['packed_sha256']
   out=a.root/'holdout-tone-spectra'/f'{case}-{key}.json'
   if out.is_file():
    print('REUSED',case,key);continue
   y=decode(packed.read_bytes(),h,final,6)
   report=residual_and_bands(y,352800,BANDS,windowed=True,tone_hz=tone,window_start_s=.25,window_stop_s=.95)
   res={'case':case,'key':key,'source_sha256':rec['source_sha256'], 'packed_sha256':rec['packed_sha256'],
      'analysis':report,'candidate_qualified':False}
   publish(out,res)
   rms=lambda ids:float(np.sqrt(sum(report['parts'][f'{low}-{high}Hz']['rms']**2 for low,high in ids)))
   from analyze_renders import dbfs
   print(case,key,'amp',round(report['fundamental_peak'],7),'0-40',round(dbfs(rms(BANDS[:2])),2),
       '40-100',round(dbfs(rms(BANDS[2:5])),2),'100-150',round(dbfs(rms(BANDS[5:7])),2),flush=True)
if __name__=='__main__':main()
