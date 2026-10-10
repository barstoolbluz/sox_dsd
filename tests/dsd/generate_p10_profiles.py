#!/usr/bin/env python3
"""Reproduce P10's negative certificates. This tool cannot promote a profile.

Evidence is copied to a fixed certificate-input snapshot before generation.
Later experiments must use new result IDs; changing the snapshot is explicit.
The certificate binds scientific rows and failed soaks, not its own compiled
binary, so recording its hash cannot introduce a self-referential hash cycle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from p10_corpus import RATES, identity
ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'tests/dsd/results/P10/certificate-input.json'
OUTPUT=ROOT/'tests/dsd/reference/p10_profiles.json'
HEADER=ROOT/'src/pcmdsd_guards.h'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    inputs=json.loads(INPUT.read_text())
    guard_file=ROOT/'tests/dsd/reference/p10_guards.json'
    guards=json.loads(guard_file.read_text())
    prefilter_file=ROOT/'tests/dsd/reference/p10_prefilters.json'
    prefilters=json.loads(prefilter_file.read_text())
    originals=json.loads((ROOT/'tests/dsd/reference/p09_original_coefficients.json').read_text())
    if inputs.get('qualified') is not False or inputs.get('status') not in ('FAILED','INCOMPLETE'):
        raise RuntimeError('this P10 generator only records negative qualification')
    if inputs['guard_manifest_sha256']!=sha(guard_file):
        raise RuntimeError('certificate input uses different frozen guards')
    profiles=[]
    for native in RATES:
        definition=next(p for p in prefilters['profiles'] if p['native_hz']==native)
        selected=next(e for e in originals['entries'] if e['filter']=='sdm-8' and e['rate_hz']==native)
        soak=next(p for p in inputs['soaks'] if p['native_hz']==native)
        profiles.append(dict(**definition,qualified=False,status=inputs['status'],
            activation='blocked; no experimental bypass in the production CLI',
            sdm=dict(name='sdm-8',order=8,trellis=False,
                coefficient_sha256=selected['sha256_a8_g8'],
                initial_integrators=[0.]*8,initial_previous_decision=0),
            prefilter=prefilters['banks'][definition['bank']],
            src=dict(arithmetic='binary64',rejection_db=180.,bandwidth_0db_percent=95.,phase_percent=50.,identity_bypass=True),
            reference_scale=dict(ordinary_pcm=.5,dsd_preserve=1.,dsd_sacd=.5,mixed_with_pcm=.5),
            input_envelope='abs(x) <= 0.5 + resolved_scale * 2 / 2147483647 after interpolation; no clipping',
            guard_bounds=guards['profiles'][str(native)]['bounds'],
            guard_derivation=guards['derivation'],training=inputs['training'],
            holdout=inputs['holdout'][str(native)],soak=soak,
            numeric_gates=inputs['numeric_gates'],
            passed_implementation_tests=inputs['passed_implementation_tests'],
            remaining_gates=inputs['remaining_gates']))
    return dict(schema='P10/negative-profile-certificates/1',qualified=False,
        status=inputs['status'],default_promotion=False,
        note='Implemented candidate; qualification failed/incomplete. No positive certificate is issued.',
        evidence_input='tests/dsd/results/P10/certificate-input.json',
        evidence_input_sha256=sha(INPUT),
        analysis_lock_sha256=sha(ROOT/'tests/dsd/reference/analysis-v1/SHA256SUMS.txt'),
        guard_manifest_sha256=sha(guard_file),prefilter_manifest_sha256=sha(prefilter_file),
        profiles=profiles)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    text=json.dumps(generate(),sort_keys=True,indent=2,allow_nan=False)+'\n'
    digest=hashlib.sha256(text.encode()).hexdigest()
    header=HEADER.read_text()
    updated,n=re.subn(r'(#define LSX_PCMDSD_CERTIFICATE_SHA256 )"[^"]*"',
        lambda m:m[1]+'"'+digest+'"',header)
    if n!=1:raise RuntimeError('expected exactly one certificate binding')
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text()!=text or header!=updated:
            raise RuntimeError('certificate bytes/hash do not match the frozen evidence snapshot')
    else:
        for path,value in ((OUTPUT,text),(HEADER,updated)):
            tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(value);tmp.replace(path)
    print(json.dumps(dict(qualified=False,certificate_sha256=digest,profiles=3)))
    return 0


if __name__=='__main__':raise SystemExit(main())
