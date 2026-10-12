#!/usr/bin/env python3
"""P12 real forced AVX2 1/2/5/6-channel decoder and encoder wrappers.

Compare decoded int32 samples against forced scalar (<=1 graph LSB);
check each tier's outputs are buffer-size invariant. Native DSD encoders are
compared for per-tier byte determinism, not cross-ISA identical pulses.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
from reference import fixtures,verify

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(body,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--sox',type=Path,default=ROOT/'src/sox_ng')
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    a=ap.parse_args()
    out=a.results/'channels.json'
    record=dict(schema='P12/channel-wrappers/1',cases=[],checks=[],errors=[],
        qualification='Forced scalar and AVX2 production CLI, 1/2/5/6 channels')
    with tempfile.TemporaryDirectory(prefix='p12-channels-') as temp:
        t=Path(temp)
        for channels in (1,2,5,6):
            native_frames=32768
            source=t/'input.dsf'
            source.write_bytes(fixtures.make_dsf(fixtures.bits(native_frames,channels),2822400))
            pcm=t/'input.wav'
            n=2048
            times=np.arange(n,dtype=np.float64)
            samples=np.column_stack([.08*np.sin(2*np.pi*(471+43*c)*times/88200 + c*.17)
                 for c in range(channels)])
            with wave.open(str(pcm),'wb') as f:
                f.setnchannels(channels);f.setframerate(88200);f.setsampwidth(4)
                f.writeframes(np.rint(samples*(2**31-1)).astype('<i4').tobytes())
            for family in ('decode','encode'):
                per_tier={}
                for tier in ('scalar','avx2'):
                    per_tier[tier]=[]
                    for buffer in (257,8192):
                        target=t/(f'{family}-{channels}-{tier}-{buffer}.'+('wav' if family=='decode' else 'dsf'))
                        env=dict(os.environ,OMP_NUM_THREADS='2',SOX_OPTS='',
                            SOX_DSD_KERNEL_FIR=tier if family=='decode' else 'unused-fir',
                            SOX_DSD_KERNEL_SDM=tier if family=='encode' else 'unused-sdm')
                        if family=='decode':
                            argv=[a.sox,'--dsd-mode','auto','-D','--buffer',str(buffer),
                                '--single-threaded',source,'-r','88200','-e','signed-integer',
                                '-b','32',target]
                        else:
                            # PCM WAV without a verified surround speaker map must
                            # receive an explicit, legal DSF channel assignment.
                            role_names={5:'FL,FR,FC,BL,BR',
                                        6:'FL,FR,FC,LFE,BL,BR'}
                            layout=['--dsd-layout',role_names[channels]] if channels>2 else []
                            argv=[a.candidate,'--dsd-mode','auto','--dsd-layout-loss','warn',
                                *layout,'-D','--buffer',str(buffer),'--single-threaded',pcm,
                                '-r','2822400',target]
                        cp=subprocess.run(list(map(str,argv)),env=env,cwd=ROOT,
                             capture_output=True,text=True,timeout=120)
                        row=dict(channels=channels,family=family,tier=tier,buffer=buffer,
                            exit=cp.returncode,source_sha256=sha(source if family=='decode' else pcm),
                            stderr=cp.stderr[-300:].replace(str(t),'<tmp>'))
                        if cp.returncode or not target.is_file():
                            record['errors'].append(dict(**row,error='CLI failure'))
                        else:
                            row['sha256']=sha(target)
                            try:
                                if family=='decode':
                                    with wave.open(str(target),'rb') as f:
                                        row['frames']=f.getnframes()
                                        assert f.getnchannels()==channels and f.getframerate()==88200
                                        assert f.getsampwidth()==4
                                        row['data']=np.frombuffer(f.readframes(f.getnframes()),dtype='<i4').copy()
                                    assert row['frames']==(native_frames+31)//32
                                else:
                                    bits=verify.decode_dsf(target.read_bytes())
                                    row['frames']=bits['frames']
                                    assert bits['channels']==channels and bits['frames']==n*32
                            except Exception as exc:
                                record['errors'].append(dict(**{k:v for k,v in row.items() if k!='data'},error=repr(exc)))
                            per_tier[tier].append(row)
                        record['cases'].append({k:v for k,v in row.items() if k!='data'})
                        save(out,record)
                    seq=per_tier[tier]
                    good=len(seq)==2 and seq[0]['sha256']==seq[1]['sha256']
                    record['checks'].append(dict(name=f'{family}-{channels}ch-{tier}-buffer-invariance',
                        status='PASS' if good else 'FAIL'))
                    if not good:record['errors'].append(dict(family=family,channels=channels,tier=tier,error='buffer invariance'))
                if family=='decode' and all(per_tier.values()):
                    lhs=per_tier['scalar'][0]['data'].astype(np.int64)
                    rhs=per_tier['avx2'][0]['data'].astype(np.int64)
                    delta=int(np.max(np.abs(lhs-rhs))) if lhs.shape==rhs.shape else None
                    good=delta is not None and delta<=1
                    record['checks'].append(dict(name=f'decode-{channels}ch-scalar-avx2-lsb',
                        status='PASS' if good else 'FAIL',max_delta=delta))
                    if not good:record['errors'].append(dict(channels=channels,error='graph sample delta',delta=delta))
                save(out,record)
    record['status']='PASS' if not record['errors'] else 'FAIL'
    save(out,record)
    for r in record['checks']:print(r['status'],r['name'],r.get('max_delta',''))
    print('P12 channels',record['status'],len(record['cases']),'executions')
    return 0 if record['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
