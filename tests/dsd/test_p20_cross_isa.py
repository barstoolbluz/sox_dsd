#!/usr/bin/env python3
"""DSD512 v2 cross-ISA smoke: whole-composite fault, count and population parity.

Hash exact emitted bits but do not demand scalar/SIMD bit identity; it is not a
contract of the original modulator. Source images come from frozen P10 holdout.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
import p17_qualify_guards as p17
R=22579200
ID='encode.mastering.v2.dsd512'
OUT=ROOT/'tests/dsd/results/P20_DSD512_CORRECTION/cross-isa.json'
SELECT=(1,16,17,21,25)
TIERS=('scalar','sse2','avx1','avx2','avx512')

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()

def run(task):
    tier,index,src,conf=task
    from p10_corpus import stimulus
    with tempfile.TemporaryDirectory(prefix='p20-isa-') as d:
        d=Path(d);raw,stamp=stimulus(conf)
        i=d/'source.f64le';i.write_bytes(raw)
        o=d/'stream.dsd';r=d/'report.json'
        cp=subprocess.run([str(ROOT/'test/dsd_test_p10'),'--render',str(conf['source_hz']),
            str(R),ID,'.5','guarded',str(i),str(o),str(r)],
            cwd=ROOT,env={**os.environ,'LSX_DSD_SDM_KERNEL':tier},
            capture_output=True,timeout=180)
        if not r.is_file():
            raise RuntimeError('ISA unavailable or candidate error '+tier+': '+cp.stderr.decode(errors='replace')[-800:])
        report=json.loads(r.read_text())
        if index==25:
            passed=cp.returncode!=0 and report['failure']==2 and report['nonfinite_states']==0
        else:
            frames=(stamp['frames']*R+conf['source_hz']//2)//conf['source_hz']
            passed=(cp.returncode==0 and report['failure']==0 and report['status']==3
                and report['processed_native_frames']==frames and report['committed_native_frames']==frames
                and report['nonfinite_states']==0 and report['excursions28']==0
                and report['monitor_overloads_nominal_half']==0)
        return dict(tier=tier,case=conf['name'],index=index,passed=bool(passed),
            source_sha256=stamp['source_f64le_sha256'],
            packed_sha256=sha(o),output_bytes=o.stat().st_size,
            frames=report['processed_native_frames'],state_max=report['max_abs_state'],
            excursion28=report['excursions28'],
            min_ones28=report['min_ones28'],max_ones28=report['max_ones28'],failure=report['failure'],
            first_bad_frame=report['first_bad_frame'],kernel_exit=cp.returncode)

def write_result_once(path, data):
    encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError(
                f'Refusing to overwrite differing P20 evidence: {path}. '
                'Use --results PATH to store this independent replay separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=OUT,
                        help='JSON receipt path (existing differing evidence is never overwritten)')
    args = parser.parse_args()
    cases=[c for c in p17.configs('holdout') if c['native_hz']==R]
    tasks=[(tier,index,None,cases[index]) for tier in TIERS for index in SELECT]
    rows=[]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for future in as_completed([executor.submit(run,x) for x in tasks]):
            item=future.result();rows.append(item)
            print('CROSS_ISA',item['tier'],item['case'],item['passed'],flush=True)
    rows.sort(key=lambda x:(TIERS.index(x['tier']),x['index']))
    data=dict(schema='P20/DSD512-v2-cross-isa/1',
        status='PASS' if all(r['passed'] for r in rows) else 'FAIL',
        profile=ID,qualified=False,tiers=list(TIERS),test_case_indices=list(SELECT),
        binary_sha256=sha(ROOT/'test/dsd_test_p10'),
        candidate_sha256=sha(ROOT/'src/sdm_p20_candidates.h'),
        guard_sha256=sha(ROOT/'src/pcmdsd_p20_guards.h'),
        cases=rows)
    try:
        write_result_once(args.results, data)
    except RuntimeError as exc:
        print('CROSS_ISA_RESULT REFUSED:', exc, file=sys.stderr)
        return 2
    print('CROSS_ISA_RESULT', data['status'], len(rows), args.results)
    return 0 if data['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
