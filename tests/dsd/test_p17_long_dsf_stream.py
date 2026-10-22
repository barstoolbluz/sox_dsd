#!/usr/bin/env python3
"""Large-block private DSF streaming probes, independently built DSF metadata.

Synthetic, not independent real media. Deliberately generates many DSF blocks
without materializing a full native-bit timeline or keeping the PCM in memory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'tests/dsd'))
from reference import fixtures,verify

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def create(path,rate,frames):
    template=fixtures.make_dsf(fixtures.bits(32768,2,'distinct'),rate,1)
    assert verify.decode_dsf(template)['frames']==32768
    block=template[92:]
    blocks=(frames+32767)//32768
    total=92+len(block)*blocks
    h=bytearray(template[:92]);struct.pack_into('<Q',h,12,total)
    struct.pack_into('<Q',h,64,frames)
    struct.pack_into('<Q',h,84,12+len(block)*blocks)
    with path.open('wb') as f:
        f.write(h)
        for _ in range(blocks):f.write(block)
    assert path.stat().st_size==total

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',type=Path,default=ROOT/'test/dsd_test_p17_dsf')
    ap.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17_qualification_2026-10-21/fixtures')
    args=ap.parse_args();probe=args.probe.resolve()
    if not probe.is_file():ap.error('probe executable missing')
    cases=[]
    with tempfile.TemporaryDirectory(prefix='p17-stream-') as d:
        directory=Path(d)
        for rate in (22579200,45158400):
            frames=rate//2+7  # ~half a second, final DSF block partially valid
            file=directory/f'synth-{rate}.dsf';create(file,rate,frames)
            for profile,out in (('mastering',176400),('wideband',705600)):
                started=time.monotonic()
                proc=subprocess.run([str(probe),str(file),profile,str(out),'scalar','full'],
                    stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
                try:result=json.loads(proc.stdout)
                except ValueError:result=None
                expected=(frames*out+rate//2)//rate
                passed=(proc.returncode==0 and result is not None and
                    result.get('native_frames')==frames and result.get('pcm_frames')==expected and
                    result.get('packed_expanded_equal') is True and
                    result.get('rate_hz')==rate and result.get('channels')==2 and
                    result.get('decode_wall_seconds',0)>0 and
                    result.get('max_rss_kb_platform_reported',0)>0)
                cases.append(dict(rate_hz=rate,profile=profile,source_sha256=sha(file),
                    source_bytes=file.stat().st_size,exit_code=proc.returncode,
                    wall_seconds=time.monotonic()-started,expected_pcm_frames=expected,
                    decoder=result,stderr_tail=proc.stderr[-1000:],
                    status='PASS' if passed else 'FAIL'))
                print('STREAM',rate,profile,'PASS' if passed else 'FAIL',flush=True)
    record=dict(schema='P17/synthetic-fullstream-fixtures/1',result='PASS' if all(
        x['status']=='PASS' for x in cases) else 'FAIL',qualification='SYNTHETIC_ONLY',
        test_source_sha256=sha(Path(__file__)),probe_sha256=sha(probe),cases=cases)
    args.results.mkdir(parents=True,exist_ok=True)
    out=args.results/'fullstream-fixtures.json';tmp=out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n');tmp.replace(out)
    return 0 if record['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
