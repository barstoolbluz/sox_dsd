#!/usr/bin/env python3
"""Verify the exact 2026-10-20 one-file P15 readmission; never certify P16.

The P00 inventory remains the historical root. This script pins the prior
rebind ledger and its one reviewed successor. The successor's presence is not
a signature, and a bare file manifest cannot replace an independent review.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TEST = 'tests/dsd/test_p15_remaining_math.py'
INDEX = 'tests/dsd/results/P00/P00_SHA256SUMS.txt'
REBOUND = 'tests/dsd/results/P15_OPERATOR_REBIND_2026-10-20'
FOLLOWON = 'tests/dsd/results/P15_SIXTEENTH_READMISSION_2026-10-20'
P00_SHA = 'f3b06a48cae0e0bb451c8bac0a476364dea3017d82c66d9dd1b2abaf2b9aac4f'
ADMISSION_BEFORE_SHA = 'fae43e0c574f8d598d6de88ec97966945e5ab4493f8b421f170596ebedb7fcde'
ADMISSION_AFTER_SHA = 'e22bfb2341c4f694e232d4386b3a027846a8792adf67605a27445542a788eaa8'
TEST_BEFORE_SHA = '8343403d83357c58adce8e7f195003a5735993b6da95e42d79dc483e6e603a5c'
TEST_AFTER_SHA = '4f92486d3c81563309e9d7159d8d0d6ff7d57b3cb4175264f03f3298399a926d'
TEST_P00_SHA = 'df301c318b072d6e6360b8de8680a9e24e18e96c81b3932e56e5f33f9a56b30d'
PATCH_SHA = 'd1ca3e707bdd030b16b4179c0b7008b875bacd9c681ec7e89ba2576a1c5d95fe'
RECORD_SHA = '68f0d8ebb508c4061873120705daeb72edbf3ff14002840b1652ecf1c6c9e31c'


class EvidenceError(ValueError):
    pass


def require(condition: bool, problem: str) -> None:
    if not condition:
        raise EvidenceError(problem)


def file_hash(path: Path) -> str:
    h = sha256()
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_at(root: Path, relative: str) -> Path:
    sub = Path(relative)
    require(bool(relative) and not sub.is_absolute() and '..' not in sub.parts and
            sub.as_posix() == relative, 'unsafe evidence relative path: ' + relative)
    location = root
    for part in sub.parts:
        location = location / part
        require(not location.is_symlink(), 'symlinked evidence path: ' + relative)
    require(location.is_file(), 'missing evidence file: ' + relative)
    return location


def exact_file(root: Path, relative: str, expected_sha: str) -> Path:
    f = file_at(root, relative)
    require(file_hash(f) == expected_sha, 'unexpected SHA-256: ' + relative)
    return f


def read_json(root: Path, relative: str, expected_sha: str | None = None) -> dict:
    p = exact_file(root, relative, expected_sha) if expected_sha else file_at(root, relative)
    try:
        content = json.loads(p.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError('invalid JSON: ' + relative) from exc
    require(isinstance(content, dict), 'expected JSON object: ' + relative)
    return content


def original_manifest(root: Path) -> dict[str, str]:
    frozen = exact_file(root, INDEX, P00_SHA)
    result = {}
    for line in frozen.read_text(encoding='utf-8').splitlines():
        require(len(line) >= 67 and line[64:66] == '  ' and
                len(line[:64]) == 64 and all(ch in '0123456789abcdef' for ch in line[:64]),
                'malformed P00 inventory record')
        digest, name = line[:64], line[66:]
        require(bool(name) and name not in result and not name.startswith('/') and
                '..' not in Path(name).parts, 'P00 inventory collision or unsafe name')
        result[name] = digest
    require(result.get(TEST) == TEST_P00_SHA, 'P00 test baseline identity changed')
    return result


def verify_chain(root: Path = ROOT) -> dict:
    """Validate reviewed anchor/successor without demanding unchanged P16 worktree."""
    root = Path(root).resolve(strict=True)
    p00 = original_manifest(root)
    historic = read_json(root, FOLLOWON + '/BEFORE_ADMISSION.json', ADMISSION_BEFORE_SHA)
    current = read_json(root, REBOUND + '/ADMISSION.json', ADMISSION_AFTER_SHA)
    readmission = read_json(root, FOLLOWON + '/READMISSION.json', RECORD_SHA)
    exact_file(root, FOLLOWON + '/BEFORE_TEST.py', TEST_BEFORE_SHA)
    exact_file(root, FOLLOWON + '/sox_dsd-sixteenth.patch', PATCH_SHA)
    require(historic.get('schema') == current.get('schema') ==
            'P15/rebound-P00-version-admission/1', 'admission schema changed')
    require(historic.get('qualified') is False and current.get('qualified') is False,
            'admission improperly promotes qualification')
    require(historic.get('original_inventory_sha256') == P00_SHA and
            current.get('original_inventory_sha256') == P00_SHA,
            'admission lacks frozen P00 root')
    old_revisions, new_revisions = historic.get('revisions'), current.get('revisions')
    require(isinstance(old_revisions, dict) and len(old_revisions) == 32 and
            isinstance(new_revisions, dict) and old_revisions.keys() == new_revisions.keys(),
            '32-entry admission inventory changed')
    require(all(old_revisions[n] == new_revisions[n] for n in old_revisions if n != TEST),
            'unreviewed admission revision')
    require(old_revisions[TEST] == dict(historical_sha256=TEST_P00_SHA,
                                       current_sha256=TEST_BEFORE_SHA) and
            new_revisions[TEST] == dict(historical_sha256=TEST_P00_SHA,
                                       current_sha256=TEST_AFTER_SHA),
            'test digest transition is not exact')
    require({k: v for k, v in historic.items() if k != 'revisions'} ==
            {k: v for k, v in current.items() if k != 'revisions'},
            'non-revision admission metadata changed')
    for name, entry in new_revisions.items():
        require(name in p00 and entry['historical_sha256'] == p00[name],
                'admitted entry does not anchor to P00: ' + name)
        exact_file(root, REBOUND + '/preimages/' + name, entry['historical_sha256'])
    require(readmission.get('schema') == 'P15/exact-one-file-readmission/1' and
            readmission.get('decision') == 'ADMIT_SINGLE_TEST_REVISION_ONLY' and
            readmission.get('qualified_release') is False and
            readmission.get('proof_upgrade') is False and
            readmission.get('original_rebind_admission_sha256') == ADMISSION_BEFORE_SHA and
            readmission.get('updated_rebind_admission_sha256') == ADMISSION_AFTER_SHA and
            readmission.get('historical_p00_index_sha256') == P00_SHA and
            readmission.get('previous_admitted_test_sha256') == TEST_BEFORE_SHA and
            readmission.get('next_admitted_test_sha256') == TEST_AFTER_SHA and
            readmission.get('original_p00_test_sha256') == TEST_P00_SHA and
            readmission.get('patch_sha256') == PATCH_SHA and
            readmission.get('admitted_path') == TEST and
            readmission.get('previous_admission_entries') ==
            readmission.get('next_admission_entries') == 32 and
            readmission.get('other_admission_entries_unchanged') == 31,
            'unrecognized reviewed admission decision')
    return dict(schema='P15/readmission-verification/1', status='REVIEWED_CHAIN_VERIFIED',
                p00_root_sha256=P00_SHA, prior_admission_sha256=ADMISSION_BEFORE_SHA,
                current_admission_sha256=ADMISSION_AFTER_SHA, admitted_entries=32,
                changed_entries=1, production_sources_changed_by_this_amendment=False,
                release_qualified=False)


def verify_current(root: Path = ROOT) -> dict:
    """Validate the admitted P15 *current tree*, which must fail on P16 edits."""
    result = verify_chain(root)
    current = read_json(Path(root), REBOUND + '/ADMISSION.json', ADMISSION_AFTER_SHA)
    for name, entry in current['revisions'].items():
        exact_file(Path(root), name, entry['current_sha256'])
    result['status'] = 'P15_ADMITTED_CURRENT_FILES_VERIFIED'
    result['matched_current_revision_files'] = 32
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--chain-only', action='store_true',
                    help='validate frozen ledger chain without insisting on a P15 worktree')
    ap.add_argument('--inventory', action='store_true',
                    help='also run the existing complete P15 current-source inventory')
    a = ap.parse_args()
    try:
        require(not (a.chain_only and a.inventory), '--inventory requires current-tree check')
        result = verify_chain(a.root) if a.chain_only else verify_current(a.root)
        if a.inventory:
            sys.path.insert(0, str(a.root / 'tests/dsd'))
            from p15_current_closeout import inventory
            result['p15_inventory'] = inventory()
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (EvidenceError, OSError, KeyError, TypeError, ValueError) as exc:
        print('P15 readmission REFUSED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
