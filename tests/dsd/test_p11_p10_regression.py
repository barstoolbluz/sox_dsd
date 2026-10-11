#!/usr/bin/env python3
"""Prove the untouched P10 binary and P11 scalar default emit identical DSF.

Must be given a separately rebuilt P10 source candidate. This historical
regression does not re-certify P10 source hashes after P11 edits, and does not
compare alternate ISA SDM hashes (which need spectral acceptance instead).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline-candidate',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    a.results.mkdir(parents=True,exist_ok=True)
    report=dict(schema='P11/P10-scalar-regression/1',
        baseline_executable_sha256=sha(a.baseline_candidate),
        p11_executable_sha256=sha(a.candidate),
        baseline_provenance='original P11 input extracted unchanged and built independently',
        trials=[],errors=[])
    file=a.results/'p10-scalar-bit-invariance.json'
    with tempfile.TemporaryDirectory(prefix='p11-p10-scalar-') as scratch:
        d=Path(scratch)
        source=d/'pcm.wav'
        n=4096;rate=88200
        t=np.arange(n,dtype=np.float64)/rate
        x=np.column_stack((.16*np.sin(2*np.pi*997*t),
                          .11*np.cos(2*np.pi*791*t+.4)))
        with wave.open(str(source),'wb') as f:
            f.setnchannels(2);f.setframerate(rate);f.setsampwidth(4)
            f.writeframes(np.rint(x*(2**31-1)).astype('<i4').tobytes())
        report['input_pcm_sha256']=sha(source)
        for native in (2822400,5644800,11289600):
            for buf,thread in ((257,'--single-threaded'),(8192,'--multi-threaded')):
                hashes={}
                for label,exe in (('P10',a.baseline_candidate),('P11-scalar',a.candidate)):
                    target=d/f'{label}-{native}-{buf}.dsf'
                    env=dict(os.environ,OMP_NUM_THREADS='2')
                    if label=='P11-scalar':env['LSX_DSD_SDM_KERNEL']='scalar'
                    else:env.pop('LSX_DSD_SDM_KERNEL',None)
                    argv=[str(exe),'--dsd-mode','auto','--dsd-layout-loss','warn',
                          '-D','--buffer',str(buf),thread,str(source),'-r',str(native),str(target)]
                    proc=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
                    if proc.returncode or not target.is_file():
                        report['errors'].append(dict(native=native,buf=buf,thread=thread,
                            arm=label,returncode=proc.returncode,stderr=proc.stderr[-800:]))
                        continue
                    hashes[label]=sha(target)
                trial=dict(rate=native,buffer=buf,thread=thread,shas=hashes,
                           status='PASS' if len(hashes)==2 and hashes['P10']==hashes['P11-scalar'] else 'FAIL')
                report['trials'].append(trial)
                if trial['status']=='FAIL':report['errors'].append(trial)
                file.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    report['status']='PASS' if not report['errors'] and len(report['trials'])==6 else 'FAIL'
    file.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    for row in report['trials']:
        print('P10/P11 scalar',row['rate'],row['buffer'],row['thread'],row['status'])
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
