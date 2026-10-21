#!/usr/bin/env python3
"""P16 source/evidence-input inventory; neither P15 nor P16 acceptance authority.

Create-only (--write), or verify a recorded P16 manifest (--verify). Changes
require a newly named review manifest; no in-place recertification shortcut.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
FILES=(
    'Makefile.am', 'src/Makefile.am', 'src/dsf.c', 'src/dsdiff.c',
    'src/dsd_decode.c', 'src/dsd_decode.h', 'src/dsd_public.c',
    'src/dsd_packed.c', 'src/dsd_packed.h', 'src/sox_dsd.h',
    'src/sox_ng.c', 'test/Makefile.am',
    'tests/dsd/test_p16.c', 'tests/dsd/test_p16.py',
    'tests/dsd/bench_p16.py', 'tests/dsd/test_dff_writer.c',
    'tests/dsd/run.py', 'tests/dsd/measure.py', 'tests/dsd/bench.py',
    'docs/dsd/handoffs/P16.md',
    'docs/dsd/P00_P16_EVIDENCE_WORKFLOW_2026-10-20.md',
    'docs/dsd/amendments/P16_AUTHORIZATION_2026-10-20.md',
    'docs/dsd/sows/P16.md',
    'docs/dsd/DSD_DESIGN.md', 'docs/dsd/IMPLEMENTATION_PLAN.md',
    'scripts/p16_dev_input_drift.py', 'scripts/p16_verify_inputs.py',
    'tests/dsd/fixtures/manifest.json',
)


def source_file(name):
    p=ROOT/name
    if p.is_symlink() or not p.is_file():
        raise ValueError('missing/symlink source input: '+name)
    return p


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def snapshot():
    p00=source_file('tests/dsd/results/P00/P00_SHA256SUMS.txt')
    if sha(p00)!='f3b06a48cae0e0bb451c8bac0a476364dea3017d82c66d9dd1b2abaf2b9aac4f':
        raise ValueError('historical P00 index changed')
    return dict(schema='P16/source-inputs/1',certified=False,
        review_authority='nonqualifying self-generated developer inventory',
        baseline_archive_sha256='c43d8367c8f6426db3fe72b71e29b09e75dc51d52bcf129c73f8d8f5a6b34366',
        supplied_git_revision='f01d2687 (claimed by dispatch; no .git in archive)',
        p00_sha256=sha(p00),
        excludes='1350 historical arrays .npz and one filter study .npz absent in supplied snapshot',
        files=[dict(path=name,sha256=sha(source_file(name)),
                    bytes=source_file(name).stat().st_size) for name in FILES])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write',type=Path)
    mode.add_argument('--verify',type=Path)
    a=ap.parse_args()
    try:
        actual=snapshot()
        if a.write:
            p=a.write
            p.parent.mkdir(parents=True,exist_ok=True)
            data=(json.dumps(actual,indent=2,sort_keys=True)+'\n').encode()
            if p.exists():
                if p.is_symlink() or p.read_bytes()!=data:
                    raise ValueError('existing P16 input manifest differs; use a new checkpoint path')
            else:
                with p.open('xb') as f:f.write(data)
            print('P16 source inventory created/unchanged:',p)
        else:
            p=a.verify
            if p.is_symlink() or not p.is_file():raise ValueError('manifest missing or symlink')
            expected=json.loads(p.read_bytes())
            if expected!=actual:raise ValueError('P16 source input bytes differ from recorded manifest')
            print(f'P16 source inventory PASS: {len(FILES)} inputs verified')
        return 0
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:
        print('P16 source inventory REFUSED:',e,file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
