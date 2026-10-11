#!/usr/bin/env python3
"""Confined P11 evidence portability pass; never touches earlier receipts.

Rewrites only machine-specific workspace and scratch prefixes, and validates
that JSON files still parse after redaction. Numeric fields and SHA evidence of
produced audio remain untouched. Generates a checksum receipt of every edit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
RES=ROOT/'tests/dsd/results/P11'


def checksum(data):return hashlib.sha256(data).hexdigest()


def sanitize(s):
    # Replace longer paths first to preserve distinctions between the certified
    # input baseline and the modified P11 working tree.
    s=s.replace('/mnt/data/p11_baseline/sox_ng','<P10-source>')
    s=s.replace(str(ROOT),'<tree>')
    # remove randomly generated directory names but retain the fixture basename
    s=re.sub(r'/(?:tmp|dev/shm)/[^/\s"\\<>]+/', '<temporary>/', s)
    s=s.replace('/tmp/','<temporary>/').replace('/dev/shm/','<temporary>/')
    # Project-local CI/host paths may differ; no other unrelated paths changed.
    return s


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=RES)
    a=parser.parse_args()
    a.results=a.results.resolve()
    if a.results!=RES.resolve():parser.error('P11 results only; cannot touch P00-P10')
    changes=[]
    for file in sorted(a.results.rglob('*')):
        if not file.is_file() or file.name=='path-redaction.json':continue
        if file.suffix not in ('.json','.jsonl','.log','.tsv','.txt'):continue
        raw=file.read_bytes()
        try:old=raw.decode('utf-8')
        except UnicodeDecodeError:continue
        updated=sanitize(old)
        if updated==old:continue
        if file.suffix=='.json':json.loads(updated)
        if file.suffix=='.jsonl':
            for ln in updated.splitlines():
                if ln.strip():json.loads(ln)
        replacement=updated.encode('utf-8')
        file.write_bytes(replacement)
        changes.append(dict(file=file.relative_to(RES).as_posix(),
            sha256_before=checksum(raw),sha256_after=checksum(replacement),
            occurrences_removed=old.count('/mnt/data/')+old.count('/tmp/')+old.count('/dev/shm/')))
    report=dict(schema='P11/portable-receipts/1',scope='P11 only',
        numerical_evidence_changed=False,
        note='Textual path prefix replacements only; no P00-P10 source or evidence changed',
        files=changes,count=len(changes))
    (a.results/'build').mkdir(parents=True,exist_ok=True)
    (a.results/'build/path-redaction.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print('P11 portable receipt redaction',len(changes),'files')
    return 0

if __name__=='__main__':raise SystemExit(main())
