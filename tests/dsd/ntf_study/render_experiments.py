#!/usr/bin/env python3
"""Render private NTF trials in the disposable P10 checkout.

Per-candidate atomic status files allow resume and preserve failed-stream
information; outputs are never promoted or mixed with frozen certificates.
"""
import argparse,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as fp:
  for b in iter(lambda:fp.read(2**20),b''):h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--checkout',type=Path,required=True)
 p.add_argument('--registry',type=Path,required=True)
 p.add_argument('--stimulus',type=Path,required=True)
 p.add_argument('--directory',type=Path,required=True)
 p.add_argument('--only',nargs='*')
 a=p.parse_args();a.stimulus=a.stimulus.resolve();a.directory=a.directory.resolve();a.checkout=a.checkout.resolve();a.registry=a.registry.resolve();a.directory.mkdir(parents=True,exist_ok=True)
 entries=[{'key':'P20-CLANS7-baseline','profile':'encode.mastering.v2.dsd512','order':7}]
 entries+=json.loads(a.registry.read_text())['candidates']
 binary=a.checkout/'test/dsd_test_p10'
 for e in entries:
  key=e['key']
  if a.only and key not in a.only:continue
  packed=a.directory/f'{key}.packed';monitor=a.directory/f'{key}.report.json';meta=a.directory/f'{key}.receipt.json'
  if meta.exists():
   d=json.loads(meta.read_text())
   if d['source_sha256']!=sha(a.stimulus) or d['binary_sha256']!=sha(binary):raise RuntimeError('Input or binary changed; refuse reuse '+key)
   if d.get('packed_sha256') and (not packed.exists() or sha(packed)!=d['packed_sha256']):raise RuntimeError('existing packed file digest mismatch '+key)
   print('REUSED',key,d.get('failure'),flush=True);continue
  if packed.exists() or monitor.exists():raise RuntimeError('Existing noncheckpoint result requires manual review '+key)
  cmd=[str(binary),'--render','176400','22579200',e['profile'],'.5','training',str(a.stimulus),str(packed),str(monitor)]
  t=time.monotonic()
  cp=subprocess.run(cmd,cwd=a.checkout,env={'LSX_DSD_SDM_KERNEL':'scalar'},capture_output=True,timeout=180)
  status=json.loads(monitor.read_text()) if monitor.exists() else {}
  result={'key':key,'order':e['order'],'profile':e['profile'], 'returncode':cp.returncode,'elapsed_seconds':time.monotonic()-t,
          'input_frames':int(a.stimulus.stat().st_size//8),'source_sha256':sha(a.stimulus),'binary_sha256':sha(binary),
          'stdout':cp.stdout.decode(errors='replace')[-1000:],'stderr':cp.stderr.decode(errors='replace')[-1000:],
          'status':status,'failure':int(status.get('failure',-1)),'packed_sha256':sha(packed) if cp.returncode==0 else None,
          'source_root_is_experimental':True,'candidate_qualified':False}
  payload=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
  with tempfile.NamedTemporaryFile(dir=a.directory,delete=False,prefix='.'+key,suffix='.tmp') as f:
   f.write(payload);f.flush();os.fsync(f.fileno());tmp=Path(f.name)
  os.link(tmp,meta);tmp.unlink()
  print('RAN',key,'return',cp.returncode,'frames',status.get('committed_native_frames'),
        'min28',status.get('min_ones28'),'maxrun',status.get('longest_run'),
        'exc',status.get('excursions28'),'time',round(result['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
