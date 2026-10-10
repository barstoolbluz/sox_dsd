#!/usr/bin/env python3
"""Remove ephemeral build/workstation paths only from P09 recorded evidence.

The previously delivered P00-P08 evidence is never touched. This transforms
provenance command strings, not measurements or numerical values.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASELINE=Path('/mnt/data/p09baseline/sox_ng')


def clean(value):
    if isinstance(value,str):
        value=value.replace(str(BASELINE),'<P08_BASELINE_ROOT>')
        value=value.replace(str(ROOT),'<SOURCE_ROOT>')
        value=re.sub(r'/dev/shm/tmp[-A-Za-z0-9._]+','<TMPFS_BENCH>',value)
        value=re.sub(r'/tmp/(?:tmp|sox-ng|dsd-)[-A-Za-z0-9._]+','<TEMP>',value)
        return value
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,dict):return {key:clean(v) for key,v in value.items()}
    return value


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args(); target=args.results.resolve()
    if target!=ROOT/'tests/dsd/results/P09':
        ap.error('safety: only the source-tree P09 results directory is allowed')
    updated=[]
    for f in sorted(target.rglob('*.json')):
        current=f.read_text()
        normalized=json.dumps(clean(json.loads(current)),sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if current != normalized:
            f.write_text(normalized)
            updated.append(str(f.relative_to(target)))
    print('P09 JSON sanitized:',len(updated),'of',len(list(target.rglob('*.json'))))
    return 0

if __name__=='__main__':raise SystemExit(main())
