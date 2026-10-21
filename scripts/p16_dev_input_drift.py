#!/usr/bin/env python3
"""Nonqualifying P16 development drift report against frozen P00 + P15 admission.

No hashes are 'approved' by this tool. P00 and the reviewed P15 admissions
are read-only baselines. Only explicitly included non-P00 files are inventoried;
this is not a complete proof-input closure or a replacement for git history.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from verify_p15_sixteenth_readmission import (ADMISSION_AFTER_SHA, EvidenceError,
    REBOUND, file_at, file_hash, original_manifest, read_json, require, verify_chain)

ROOT = Path(__file__).resolve().parents[1]


def intentionally_omitted(name: str) -> bool:
    p = Path(name)
    return (('arrays' in p.parts and p.suffix == '.npz') or
            name == 'docs/dsd/evidence/candidate_filter_coefficients.npz' or
            'graph-raw' in p.parts or p.suffix == '.state')


def report(root: Path = ROOT, additional_paths=()) -> dict:
    root = Path(root).resolve(strict=True)
    # This authenticates the *baseline chain* but deliberately does not
    # require the mutable P16 tree to satisfy historic P15 current-source pins.
    chain = verify_chain(root)
    baseline = original_manifest(root)
    admission = read_json(root, REBOUND + '/ADMISSION.json', ADMISSION_AFTER_SHA)
    revisions = admission['revisions']
    changes = []
    absent_bulk = {}
    for name, historical in baseline.items():
        expected = revisions[name]['current_sha256'] if name in revisions else historical
        p = root / name
        if p.is_symlink():
            changes.append(dict(path=name, status='SYMLINK_REFUSED', baseline_sha256=expected))
        elif not p.is_file():
            if intentionally_omitted(name):
                category = ('arrays_npz' if 'arrays' in Path(name).parts else
                    'supplemental_npz' if name.endswith('candidate_filter_coefficients.npz') else
                    'graph_raw' if 'graph-raw' in Path(name).parts else 'state')
                absent_bulk[category] = absent_bulk.get(category, 0) + 1
            else:
                changes.append(dict(path=name, status='MISSING', baseline_sha256=expected))
        else:
            actual = file_hash(p)
            if actual != expected:
                changes.append(dict(path=name, status='MODIFIED',
                                    baseline_sha256=expected, current_sha256=actual))
    extras = {}
    for name in sorted(set(additional_paths)):
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and p.as_posix() == name,
                'invalid non-P00 --include path: ' + str(name))
        require(name not in baseline, '--include already P00-indexed: ' + name)
        found = file_at(root, name)
        extras[name] = dict(sha256=file_hash(found), byte_size=found.stat().st_size)
    return dict(schema='P16/nonqualifying-development-input-drift/1',
                disposition='WORKING_TREE_DRIFT_NOT_REVIEWED_OR_CERTIFIED',
                source_baseline='frozen P00, with exactly 32 reviewed P15 current revisions',
                p00_sha256=chain['p00_root_sha256'],
                reviewed_p15_admission_sha256=chain['current_admission_sha256'],
                checked_indexed_files=len(baseline),
                p00_indexed_drift=sorted(changes, key=lambda row: row['path']),
                drift_count=len(changes),
                known_omitted_historical_payloads=dict(sorted(absent_bulk.items())),
                explicitly_included_unindexed_files=extras,
                warning=('This report covers P00-indexed paths and --include paths ONLY; '
                         'new unlisted P16 files, toolchains, build options, runtime choices '
                         'and semantic equivalence are not checked.'),
                certified=False, historical_p15_source_qualified=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--include', action='append', default=[], metavar='RELATIVE_PATH')
    parser.add_argument('--out', type=Path, help='write immutable, idempotent snapshot to a new file')
    args = parser.parse_args()
    try:
        doc = report(args.root, args.include)
        data = (json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        if args.out:
            path = args.out
            require(not path.is_symlink(), 'refusing symlink output')
            if path.exists():
                require(path.is_file() and path.read_bytes() == data,
                        'conflicting pre-existing P16 checkpoint; select a new path')
            else:
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                fd = os.open(path, flags, 0o644)
                with os.fdopen(fd, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            print('P16 nonqualifying checkpoint:', path)
        else:
            sys.stdout.buffer.write(data)
        return 0
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print('P16 drift scan REFUSED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
