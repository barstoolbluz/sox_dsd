#!/usr/bin/env python3
"""Normalize only newly generated P10 corrective regression provenance paths.

Preserves numeric measurements, status, hashes of audio and the original P00-P10
historic record verbatim. Source-root and temporary-fixture directory spellings
are not portable and are not useful as stable evidence identities.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
ALLOWED=ROOT/'tests/dsd/results/P10_corrective/regression'


def normalize(value):
    if isinstance(value,str):
        value=value.replace(str(ROOT),'<SOURCE_ROOT>')
        if re.fullmatch(r'/[A-Za-z0-9_./-]+/python3(?:\.[0-9]+)?',value):
            return 'python3'
        value=re.sub(r'/dev/shm/[^/\\\s"\\]+','<TEMP_STORAGE>',value)
        value=re.sub(r'/tmp/[^/\\\s"\\]+','<TEMP>',value)
        return value
    if isinstance(value,list):return [normalize(v) for v in value]
    if isinstance(value,dict):return {key:normalize(v) for key,v in value.items()}
    return value


def run(target):
    if target.resolve()!=ALLOWED:
        raise ValueError('only P10_corrective/regression results may be sanitized')
    changed=[]
    for f in sorted(target.rglob('*.json')):
        data=json.loads(f.read_text())
        normalized=json.dumps(normalize(data),sort_keys=True,indent=2,allow_nan=False)+'\n'
        if f.read_text()!=normalized:
            f.write_text(normalized)
            changed.append(str(f.relative_to(target)))
    evidence=ROOT/'tests/dsd/results/P10_corrective/path-normalization.json'
    if evidence.exists():
        previous=json.loads(evidence.read_text())
        changed=sorted(set(changed)|set(previous.get('changed_files',[])))
    out=dict(schema='P10/corrective-path-normalization/1', scope='new regression JSON only',
        paths='machine-specific source-root and temporary-prefix identifiers only',
        changed_files=changed, numeric_measurements_unchanged=True,
        historic_P10_untouched=True)
    evidence.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ALLOWED)
    args=ap.parse_args()
    result=run(args.results)
    print('sanitized',len(result['changed_files']),'files')

if __name__=='__main__':main()
