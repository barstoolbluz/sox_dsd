#!/usr/bin/env python3
"""Independent P18-constructed DSF fixtures for the PRIVATE P17 full-file probe.

These synthetic cases validate the instrumentation, not licensed material.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
from reference import fixtures,verify

def invoke(binary,data,rate,profile,output,tier='scalar',pcm=None):
    with tempfile.TemporaryDirectory(prefix='p17-fixture-') as t:
        source=Path(t)/'fixture.dsf';source.write_bytes(data)
        cmd=[str(binary),str(source),profile,str(output),tier,'full']
        if pcm:cmd.append(str(pcm))
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
        try:r=json.loads(p.stdout,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError,json.JSONDecodeError):r=None
        return p.returncode,r,p.stderr

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--binary',type=Path,default=ROOT/'test/dsd_test_p17_dsf')
    a.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17_qualification_2026-10-21/fixtures')
    args=a.parse_args();args.binary=args.binary.resolve();args.results.mkdir(parents=True,exist_ok=True)
    if not args.binary.is_file():a.error('probe executable missing')
    cases=[]
    def record(name,ok,detail):
        cases.append(dict(name=name,status='PASS' if ok else 'FAIL',**detail))
        print('FIXTURE',name,'PASS' if ok else 'FAIL',flush=True)
    for rate in (22579200,45158400):
        for channels in (1,2,6):
            for frames in (1,17,32769):
                for bps in (1,8):
                    original=fixtures.bits(frames,channels,'distinct')
                    payload=fixtures.make_dsf(original,rate,bps)
                    independent=verify.decode_dsf(payload)
                    assert independent['rate']==rate and independent['channels']==channels
                    assert all(independent['timeline'][c][:frames]==original[c] for c in range(channels))
                    for profile,out in (('mastering',176400),('wideband',705600)):
                        rc,report,stderr=invoke(args.binary,payload,rate,profile,out)
                        expected=(frames*out+rate//2)//rate
                        ok=(rc==0 and report is not None and
                            report['status']=='PASS_FUNCTIONAL_ONLY' and
                            report['native_frames']==frames and report['pcm_frames']==expected and
                            report['channels']==channels and report['bits_per_sample']==bps and
                            report['packed_expanded_equal'] is True and
                            all((x['rms'] is not None if expected else x['rms'] is None)
                                for x in report['channels_numeric']))
                        record(f'positive-{rate}-{channels}-{frames}-{bps}-{profile}',ok,
                            dict(returncode=rc,input_sha256=hashlib.sha256(payload).hexdigest(),
                                 output=report,stderr_tail=stderr[-512:]))
    original=fixtures.make_dsf(fixtures.bits(32769,2,'distinct'),22579200,1)
    corrupted={
        'short-header':original[:50],
        'truncated-data':original[:-1],
        'invalid-tag':b'XXXX'+original[4:],
        'misdeclared-size':original[:12]+struct.pack('<Q',len(original)+1)+original[20:],
        'invalid-channels':original[:52]+struct.pack('<I',7)+original[56:],
        'invalid-bits':original[:60]+struct.pack('<I',2)+original[64:],
        'invalid-rate':original[:56]+struct.pack('<I',44100)+original[60:],
        'invalid-data-size':original[:84]+struct.pack('<Q',12)+original[92:],
        'invalid-block-size':original[:72]+struct.pack('<I',8192)+original[76:],
        'invalid-frame-count':original[:64]+struct.pack('<Q',2**64-1)+original[72:]
    }
    for name,payload in corrupted.items():
        rc,report,stderr=invoke(args.binary,payload,22579200,'mastering',176400)
        record('negative-'+name,rc!=0 and report is None and 'P17_DSF_FAIL' in stderr,
            dict(returncode=rc,stderr_tail=stderr[-512:]))
    rc,report,stderr=invoke(args.binary,original,22579200,'mastering',176400,tier='not-a-kernel')
    record('negative-invalid-kernel',rc!=0 and report is None and
        'unsupported explicit kernel' in stderr,dict(returncode=rc,stderr_tail=stderr[-512:]))
    with tempfile.TemporaryDirectory(prefix='p17-pcm-') as t:
        dst=Path(t)/'pcm.f64le'
        rc,report,stderr=invoke(args.binary,original,22579200,'mastering',176400,pcm=dst)
        frames=(32769*176400+22579200//2)//22579200
        ok=(rc==0 and report is not None and dst.is_file() and
            dst.stat().st_size==frames*2*8 and report['pcm_frames']==frames)
        record('pcm-export-size',ok,dict(returncode=rc,
            pcm_sha256=hashlib.sha256(dst.read_bytes()).hexdigest() if ok else None,
            stderr_tail=stderr[-512:]))
    data=dict(schema='P17/dsf-probe-fixtures/1',
        result='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
        qualification='SYNTHETIC_ONLY',
        source_probe_sha256=hashlib.sha256((ROOT/'tests/dsd/p17_dsf_probe.c').read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        counts=dict(pass_count=sum(c['status']=='PASS' for c in cases),
                    fail_count=sum(c['status']=='FAIL' for c in cases)),cases=cases)
    dest=args.results/'probe-fixtures.json';tmp=dest.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n');tmp.replace(dest)
    print('P17 DSF probe',data['result'],data['counts'])
    return 0 if data['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
