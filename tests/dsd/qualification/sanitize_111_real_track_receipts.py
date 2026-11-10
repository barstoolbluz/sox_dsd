#!/usr/bin/env python3
"""Redact host filesystem paths in the historical 800-row real-track receipt.

The pre-cleanup original is not shipped in source after history rewrite;
pass --source /private/pre-cleanup/checkout/.../results.jsonl to reproduce
the original public redacted fixture. Original audio is not included.
"""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = (ROOT / 'tests/dsd/results/V1_HIGH_RATE_ENCODE_2026-11-07'
            / 'real-tracks/results.jsonl')
REDACTED = (ROOT / 'tests/dsd/release_evidence'
            / 'v1_high_rate_real_tracks_redacted.jsonl')
# Absolute local paths can occur inside SoX's stderr message fields. Keep
# warning text and counts while replacing only the potentially identifying
# path token. The separator handles backtick/quote-wrapped and bare paths.
LOCAL_PATH = re.compile(r'/(?:(?:home|Users|mnt|tmp|var|private)/)[^\s\x60\'"]+')


def sanitize(blob):
    rows=[]
    for no, line in enumerate(blob.splitlines(),1):
        entry=json.loads(line)
        if not isinstance(entry,dict) or not isinstance(entry.get('stderr'),str):
            raise ValueError(f'invalid real-track record at line {no}')
        entry['stderr'] = LOCAL_PATH.sub('[local-path-redacted]',entry['stderr'])
        rows.append(entry)
    if len(rows)!=800:
        raise ValueError(f'expected original 800 rows, got {len(rows)}')
    content = (''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows)).encode()
    if LOCAL_PATH.search(content.decode()):
        raise ValueError('output still contains local filesystem paths')
    return content, len(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--source',type=Path,default=ORIGINAL,
                    help='original private pre-cleanup JSONL receipt')
    ap.add_argument('--output',type=Path,default=REDACTED)
    args=ap.parse_args()
    if not args.source.is_file():
        ap.error('original receipt not present: specify --source from your private pre-cleanup backup')
    original=args.source.read_bytes()
    before=hashlib.sha256(original).hexdigest()
    result,count=sanitize(original)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes()!=result:
            raise SystemExit('sanitized release copy missing or differs from source')
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(result)
    if hashlib.sha256(args.source.read_bytes()).hexdigest()!=before:
        raise SystemExit('historical source modified during redaction')
    print(json.dumps(dict(rows=count, historical_source_sha256=before,
                          published_sha256=hashlib.sha256(result).hexdigest(),
                          verified=args.check),sort_keys=True))

if __name__=='__main__':
    main()
