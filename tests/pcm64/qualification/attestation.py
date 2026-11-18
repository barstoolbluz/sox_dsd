"""Accepted-production attestation and independent, fixed coefficient fixtures.

The expected SHA-256 and coefficient words are checked into the Phase 08
qualification reference *outside* the program under test. They are not
recreated from the current source/header, a running probe, or a receipt.
A changed production source requires explicit re-qualification, not an
automatic refresh of this reference manifest.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REFERENCE=Path(__file__).with_name('reference')

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def expected():
    return json.loads((REFERENCE/'accepted-8005f35.json').read_text())

def verify(source):
    source=Path(source).resolve()
    p=expected()
    if p.get('schema')!='p08-accepted-source-independent-reference/1':
        raise AssertionError('unrecognized independent qualification baseline')
    for relative,want in p['source_file_sha256'].items():
        path=source/relative
        if (not path.is_file() or not path.resolve().is_relative_to(source) or
                digest(path)!=want):
            raise AssertionError('accepted production source changed: '+relative)
    for relative,want in p['src_stage_files'].items():
        path=REFERENCE/relative
        if not path.is_file() or digest(path)!=want:
            raise AssertionError('independent reference stage snapshot changed: '+relative)
    return p
