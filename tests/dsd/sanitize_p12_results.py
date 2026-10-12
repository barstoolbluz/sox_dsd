#!/usr/bin/env python3
"""Remove ephemeral host paths from P12 textual receipts, retaining raw values.

This only touches P12 result text, never inherited P00-P11 evidence, and
records before/after SHA-256 for each changed file. It does not alter
performance or numerical values, fixture digests, or audio payloads.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'tests/dsd/results/P12'
SUFFIXES = {'.json', '.jsonl', '.log', '.tsv', '.txt'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def portable(text):
    # The source path must be replaced before the enclosing scratch directory.
    text = text.replace(str(ROOT), '<tree>')
    text = re.sub(r'/(?:tmp|dev/shm)/[^/\s"\\<>]+/',
                  '<temporary>/', text)
    text = text.replace('/mnt/data/p12-work', '<workspace>')
    text = text.replace('/tmp/', '<temporary>/')
    text = text.replace('/dev/shm/', '<temporary>/')
    return text


def main():
    if not RESULTS.is_dir():
        raise SystemExit('P12 results directory missing')
    changes = []
    for p in sorted(RESULTS.rglob('*')):
        if not p.is_file() or p.suffix not in SUFFIXES or p.name == 'path-redaction.json':
            continue
        before = p.read_bytes()
        try:
            text = before.decode('utf-8')
        except UnicodeDecodeError:
            continue
        updated = portable(text)
        if updated == text:
            continue
        if p.suffix == '.json':
            json.loads(updated)
        if p.suffix == '.jsonl':
            for line in updated.splitlines():
                if line.strip():
                    json.loads(line)
        after = updated.encode('utf-8')
        p.write_bytes(after)
        changes.append(dict(path=p.relative_to(RESULTS).as_posix(),
                            before_sha256=sha(before), after_sha256=sha(after)))
    destination = RESULTS / 'build/path-redaction.json'
    if not changes and destination.is_file():
        print('P12 portable receipt rewrite PASS (unchanged; prior audit retained)')
        return
    receipt = dict(schema='P12/portable-receipts/1', scope='P12 only',
                   source_or_prior_phase_modified=False,
                   numeric_fields_modified=False, file_count=len(changes), files=changes)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print('P12 portable receipt rewrite PASS', len(changes), 'text files')


if __name__ == '__main__':
    main()
