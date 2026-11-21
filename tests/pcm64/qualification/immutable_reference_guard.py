#!/usr/bin/env python3
"""Fail closed on unapproved edits to accepted Phase 08 references (D13).

The predecessor is the named, fixed 595d401 Git object, never the candidate
source, a freshly generated receipt, or an automatically rewritten manifest.
Owner approval requires a separately reviewed successor reference and an
explicit predecessor/reason record; this guard intentionally cannot grant it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = '595d401a244fd0329fa39229b0a6d1918bcf00ff'
TARGET = 'tests/pcm64/qualification/reference/'
SOURCE_PINS = ('src/dsd_coeffs.h', 'src/pcmdsd.c', 'src/pcmdsd.h',
               'src/pcmdsd_coeffs.h')


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.PIPE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def baseline_bytes(path: str) -> bytes:
    return git('show', f'{BASE}:{path}')


def validate_pair(path: str, raw: bytes) -> dict:
    expected = baseline_bytes(path)
    if raw != expected:
        raise AssertionError(f'UNAUTHORIZED REFERENCE CHANGE: {path}; predecessor preserved at {BASE}')
    return {'path': path, 'sha256': digest(expected), 'size': len(expected)}


def run():
    parent = git('rev-parse', BASE).decode().strip()
    if parent != BASE:
        raise AssertionError('source baseline mismatch')
    names = git('ls-tree', '-r', '--name-only', BASE, TARGET).decode().splitlines()
    assert names and any(x.endswith('accepted-reconstruction-sse2.zlib') for x in names)
    checked = []
    for name in names:
        checked.append(validate_pair(name, (ROOT / name).read_bytes()))
    # Certified encoder front end, unchanged by owner decision D3. Historical
    # profile identities and the coefficient arrays must never auto-update.
    for name in SOURCE_PINS:
        if (ROOT / name).exists() and git('cat-file', '-e', f'{BASE}:{name}') is not None:
            checked.append(validate_pair(name, (ROOT / name).read_bytes()))
    sys.path.insert(0, str(ROOT / 'tests/pcm64/qualification'))
    from reconstruction_reference import accepted_words
    items = accepted_words()
    if len(items) != 19:
        raise AssertionError('historical predecessor has wrong accepted sample count')
    # Mutation control: flipping one byte, in memory, must cause rejection.
    victim = next(name for name in names if name.endswith('accepted-reconstruction-sse2.zlib'))
    altered = bytearray((ROOT / victim).read_bytes())
    altered[len(altered) // 2] ^= 1
    rejected = False
    try:
        validate_pair(victim, altered)
    except AssertionError:
        rejected = True
    if not rejected:
        raise AssertionError('D13 mutation check failed: guard did not reject edit')
    return {'schema':'phase08-reference-immutability/1',
            'status':'PASS_LOCKED_PREDECESSOR',
            'baseline':BASE,
            'predecessor_type':'historical v2 reconstruction; NOT unified decoder oracle',
            'accepted_v2_fixtures':len(items),
            'mutation_rejection':'PASS',
            'unified_decoder_reference_approval':'OPEN',
            'files':checked}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    try: result=run()
    except Exception as e: result={'status':'FAIL','error':str(e), 'unified_decoder_reference_approval':'OPEN'}
    args.results.mkdir(parents=True,exist_ok=True)
    (args.results/'immutable-reference.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f"{result['status']}: D13 sealed predecessor; D16 unified approval OPEN")
    if result['status']=='FAIL':print(result['error'],file=sys.stderr)
    return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
