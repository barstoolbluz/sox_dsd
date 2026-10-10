#!/usr/bin/env python3
"""Reproduce every original P10 holdout/control bitstream with the corrective binary.

No analysis-v1 coefficient or old evidence is altered. The primary numerical
results remain those obtained from the frozen oracle; this audit establishes
bit-equivalence for all 183 source/control/mode observations in a new executable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from p10_corpus import stimulus,identity
ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    original=ROOT/'tests/dsd/results/P10/numeric/qualification.json'
    source=json.loads(original.read_text());rows=source['rows']
    assert len(rows)==183
    pin=dict(schema='P10/corrective-bit-equivalence/1',original_evidence_sha256=sha(original),
        executable_sha256=sha(args.unit),source_generator_sha256=sha(ROOT/'tests/dsd/test_p10.c'),
        frozen_analysis_lock_sha256=sha(ROOT/'tests/dsd/reference/analysis-v1/SHA256SUMS.txt'))
    result_file=args.results/'bit-equivalence.json'
    if result_file.exists():
        result=json.loads(result_file.read_text())
        for k,v in pin.items():
            if result.get(k)!=v:raise RuntimeError('incompatible resumed binary or source; use versioned new result directory')
    else:result=dict(pin,rows=[],status='INCOMPLETE',qualified=False)
    if len(result['rows'])>len(rows):raise ValueError('saved row count exceeds expected suite')
    for i,old in enumerate(rows):
        if i<len(result['rows']):
            old_row=result['rows'][i]
            if (old_row.get('name')!=old['name'] or old_row.get('expected_bits_sha256')!=old['bits_sha256']):
                raise RuntimeError('checkpoint does not match frozen source record')
            if old_row['status']!='PASS':return 1
            continue
        config=old['source'];raw,source_identity=stimulus(config)
        source_sha=hashlib.sha256(raw).hexdigest()
        if source_sha!=old['source_identity']['source_f64le_sha256'] or source_identity['frames']!=old['source_identity']['frames']:
            raise RuntimeError('source stimulus identity mismatch '+old['name'])
        with tempfile.TemporaryDirectory(prefix='p10-bits-') as td:
            tmp=Path(td);pcm=tmp/'source.f64le';bits=tmp/'audio.bits';report=tmp/'render.json'
            pcm.write_bytes(raw)
            mode=old['mode']
            command=[str(args.unit.resolve()),'--render',str(config['source_hz']),
                str(config['native_hz']),old['candidate_profile'],'0.5',mode,str(pcm),str(bits),str(report)]
            process=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=240)
            measurement=json.loads(report.read_text()) if report.exists() else {}
            output_sha=sha(bits) if bits.exists() else None
        stable_fields=('status','failure','input_frames','committed_native_frames',
            'processed_native_frames','first_bad_frame','peak','failure_value',
            'windows28','excursions28','min_ones28','max_ones28','longest_run','max_abs_state')
        mismatches={key:(old['render'].get(key),measurement.get(key)) for key in stable_fields
            if old['render'].get(key)!=measurement.get(key)}
        good=(process.returncode==old['exit_code'] and output_sha==old['bits_sha256']
            and not mismatches)
        record=dict(name=old['name'],source_identity_sha256=source_sha,
            expected_exit_code=old['exit_code'],actual_exit_code=process.returncode,
            expected_bits_sha256=old['bits_sha256'],actual_bits_sha256=output_sha,
            inherited_native_frames=old['render']['committed_native_frames'],
            observed_native_frames=measurement.get('committed_native_frames'),
            mismatches=mismatches,stderr=process.stderr,status='PASS' if good else 'FAIL')
        result['rows'].append(record)
        if not good:result['status']='FAIL'
        atomic(result_file,result)
        if not good:
            print('FAIL',i,old['name'],mismatches,flush=True);return 1
        if i%10==0:print('matched',i+1,'of',len(rows),old['name'],flush=True)
    result['status']='PASS' if len(result['rows'])==len(rows) else 'INCOMPLETE'
    result['suite_totals']=dict(original_rows=len(rows),matched=len(result['rows']),
        original_overload_rejections=sum(r['exit_code'] for r in rows),
        qualifying_profile=False, analysis_recomputed=False,
        limitation='bit-identical replay validates inherited frozen numeric results; this is not new independent analysis')
    atomic(result_file,result)
    print('P10 corrective bitstream replay',result['status'],len(result['rows']))
    return int(result['status']!='PASS')

if __name__=='__main__':raise SystemExit(main())
