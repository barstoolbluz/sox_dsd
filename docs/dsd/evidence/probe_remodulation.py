#!/usr/bin/env python3
"""Baseline level/ordering experiment, not qualification of the proposed engine."""
import argparse,json,pathlib,subprocess,tempfile
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--sox',required=True);p.add_argument('--out',required=True);a=p.parse_args()
commands=[]
with tempfile.TemporaryDirectory() as t:
 d=pathlib.Path(t)
 def run(c):
  r=subprocess.run([a.sox]+c,capture_output=True,text=True)
  commands.append({'command':[a.sox]+[x.replace(str(d),'$TMP')for x in c],'exit':r.returncode,'stderr':r.stderr.strip()})
  if r.returncode:raise RuntimeError(r.stderr)
 run(['-n','-r','2822400','-c','1',str(d/'a.dsf'),'synth','0.5','sine','1000','gain','-1'])
 run([str(d/'a.dsf'),str(d/'raw_order.dsf'),'gain','-3'])
 run([str(d/'a.dsf'),str(d/'staged.dsf'),'rate','-v','88200','gain','-3','rate','-v','2822400'])
 amps={}
 for name in ('a','raw_order','staged'):
  run(['-D',str(d/f'{name}.dsf'),'-t','raw','-e','floating-point','-b','64','-r','88200',str(d/f'{name}.raw'),'rate','-v'])
  y=np.fromfile(d/f'{name}.raw',dtype='<f8');tt=np.arange(len(y))/88200;sel=(tt>.1)&(tt<.4)
  X=np.stack([np.ones(sel.sum()),np.cos(2*np.pi*1000*tt[sel]),np.sin(2*np.pi*1000*tt[sel])],axis=1)
  fit=np.linalg.lstsq(X,y[sel],rcond=None)[0];amps[name]=float(np.hypot(*fit[1:]))
 r={'scope':'baseline ordering and explicit-staging level experiment; source/analysis are sox_ng, so this is not an independent audio-quality oracle','commands':commands,'reconstructed_sine_peaks':amps,'measured_gain_db':{k:float(20*np.log10(v/amps['a'])) for k,v in amps.items()if k!='a'},'requested_gain_db':-3,'interpretation':'Raw-order result illustrates the known domain-boundary problem. Explicit staging still applies ordinary PCM-to-DSD half scaling, so a new automatic remodulation planner must preserve the DSD level reference to avoid an extra 6.0206 dB loss.'}
 pathlib.Path(a.out).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
