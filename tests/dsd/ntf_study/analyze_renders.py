#!/usr/bin/env python3
"""Independent high-rate reconstruction and spectral partition of DSD512 trials.

P20 calibration: replay unchanged CLANS7 candidate and check 176.4k output
against the frozen unquantized-F64 record. Additional 352.8k route uses five
frozen halfband decimators and an explicitly specified 401-tap final FIR,
which passes 0-150k and suppresses 200k+ images. No claim of response or
signal fidelity >88.2k is made for the present 176.4k input pipeline.
"""
import argparse,hashlib,json,math,os,sys,tempfile
from pathlib import Path
import numpy as np
from scipy.signal import firwin,upfirdn

BANDS=((0,20000),(20000,40000),(40000,60000),(60000,80000),(80000,100000),(100000,120000),(120000,150000),(150000,176400))

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()

def dbfs(v):return float(20*np.log10(max(math.sqrt(2.)*float(v),1e-300)))

def residual_and_bands(waveform,sr,bands, windowed=False, tone_hz=997., window_start_s=.4, window_stop_s=1.2):
 start,stop=int(window_start_s*sr),int(window_stop_s*sr)
 x=np.asarray(waveform[start:stop],dtype=np.float64)
 n=np.arange(start,stop,dtype=np.float64)
 phase=2*np.pi*tone_hz*n/sr
 basis=np.column_stack([np.sin(phase),np.cos(phase),np.ones(len(n))])
 co=np.linalg.lstsq(basis,x,rcond=None)[0]
 delta=x-basis@co
 n=len(delta)
 win=np.kaiser(n,30) if windowed else np.ones(n,dtype=np.float64)
 scale=float(np.mean(win*win))
 sp=np.fft.rfft(delta*win)
 f=np.fft.rfftfreq(n,1./sr)
 weights=np.full(sp.size,2.,dtype=np.float64)
 weights[0]=1.
 if n%2==0:weights[-1]=1.
 pw=(np.abs(sp)**2)*weights/n**2/scale
 fullpower=float(np.mean((delta*win)**2))/scale
 assert np.isclose(fullpower,float(np.sum(pw)),rtol=1e-8,atol=1e-30),'Parseval failed'
 parts={}
 for low,high in bands:
  mask=(f>=low)&((f<high) if high<sr/2 else (f<=high))
  bd=math.sqrt(float(np.sum(pw[mask])))
  sp_power=np.abs(sp[mask]); fbin=f[mask]
  pk_idx=int(np.argmax(sp_power)) if len(sp_power) else 0
  pkamp=2*sp_power[pk_idx]/n if len(sp_power) else 0
  parts[f'{low}-{high}Hz']={'sine_equivalent_dbfs':dbfs(bd),
       'rms':bd,'strongest_fft_bin_hz':float(fbin[pk_idx]) if len(fbin) else None,
       'strongest_fft_bin_peak_dbfs':float(20*np.log10(max(pkamp,1e-300)))}
 total=math.sqrt(fullpower)
 return {'sine_equivalent_dbfs':dbfs(total),'rms':total,
         'fundamental_peak':float(np.hypot(*co[:2])),
         'fitted_dc':float(co[2]),'start_s':window_start_s,'stop_s':window_stop_s,'fit_tone_hz':tone_hz,
         'sample_hz':sr,'window':('kaiser_beta30_power_compensated' if windowed else 'rectangular'),
         'unwindowed_total_sine_equivalent_dbfs':dbfs(math.sqrt(float(np.mean(delta**2)))),
         'parts':parts}

def decode(data,halfband,final,stages):
 b=np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='big')
 p=b.astype(np.float64)*2.-1.
 del b
 for s in range(stages):p=upfirdn(halfband if s<stages-1 else final,p,down=2)
 return p

def publish(path,rec):
 payload=(json.dumps(rec,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.name,suffix='.tmp',delete=False) as f:
  f.write(payload); f.flush();os.fsync(f.fileno()); tmp=Path(f.name)
 try:
  try:os.link(tmp,path)
  except FileExistsError:
   if path.read_bytes()!=payload:raise RuntimeError('differing result exists: '+str(path))
 finally:tmp.unlink()

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input-dir',type=Path,required=True)
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--source-root',type=Path,required=True)
 p.add_argument('--only',nargs='*')
 p.add_argument('--alternative-fir',action='store_true')
 a=p.parse_args()
 sys.path.insert(0,str(a.source_root/'tests/dsd'))
 import p20_audio_compare
 half=p20_audio_compare.coefficients('halfband')
 master=p20_audio_compare.coefficients('master64_256')
 final=firwin(601 if a.alternative_fir else 401,176400,fs=705600,window=('kaiser',25 if a.alternative_fir else 22))
 for path in sorted(a.input_dir.glob('*.receipt.json')):
  rec=json.loads(path.read_text());key=rec['key']
  if a.only and key not in a.only:continue
  if rec['returncode']!=0:
   print('SKIP_FAILED',key,flush=True);continue
  packed=a.input_dir/(key+'.packed')
  assert sha(packed)==rec['packed_sha256']
  result_path=a.output_dir/(key+('.alternate' if a.alternative_fir else '')+'.json')
  if result_path.exists():
   obj=json.loads(result_path.read_text());assert obj['packed_sha256']==rec['packed_sha256'];print('REUSE',key,flush=True);continue
  raw=packed.read_bytes()
  # Main 352.8-kHz path. 6x2 cascades from 22,579,200 to 352,800.
  y=decode(raw,half,final,6)
  result={'schema':'DSD512-NTF-nonlinear-reconstruction/1','key':key,'sample_hz':352800,
       'reconstruction':'5 frozen in-tree 57tap halfbands plus 401tap beta22 (or 601/beta25) Kaiser final 2:1 decimator at 705600 Hz; 1.6s binary64 997Hz taper',
       'packed_sha256':rec['packed_sha256'], 'source_sha256':rec['source_sha256'],
       'candidate_qualified':False,'stages':6,'native_hz':22579200,
       'analysis':residual_and_bands(y,352800,BANDS,windowed=True)}
  del y
  if key=='P20-CLANS7-baseline' and not a.alternative_fir:
   # Completely unchanged 176.4 kHz P20 decimator; compare preserved result.
   old=decode(raw,half,master,7)
   result['baseline_original_176k_reproduction']=residual_and_bands(old,176400,((0,88200),))
   orig=json.loads((a.source_root/'tests/dsd/results/P20_RESIDUAL_ASYMMETRY_2026-10-22/analysis.json').read_text())
   expect=orig['sources']['unquantized_f64']['dsd512']['v2']['spectrum']['residual_dbfs_rms_equivalent']
   got=result['baseline_original_176k_reproduction']['sine_equivalent_dbfs']
   if abs(expect-got)>0.001:raise AssertionError(f'baseline regression {got} vs {expect}')
   result['baseline_original_176k_expected_dbfs']=expect
  publish(result_path,result)
  x=result['analysis']; print('ANALYZED',key,'tot',round(x['sine_equivalent_dbfs'],3),
      '0-40',round(dbfs(math.sqrt(sum(x['parts'][f'{l}-{u}Hz']['rms']**2 for l,u in BANDS[:2]))),3),
      '40-100',round(dbfs(math.sqrt(sum(x['parts'][f'{l}-{u}Hz']['rms']**2 for l,u in BANDS[2:5]))),3),
      '100-150',round(dbfs(math.sqrt(sum(x['parts'][f'{l}-{u}Hz']['rms']**2 for l,u in BANDS[5:7]))),3),flush=True)

if __name__=='__main__':main()
