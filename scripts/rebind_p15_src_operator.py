#!/usr/bin/env python3
"""Fail-closed mechanical P15 SRC operator rebinding after reviewed source drift.

Never weakens SOURCE pinning, never replaces stage snapshots, and never upgrades
SOURCE_BOUND_UNCERTIFIED to a proof of arbitrary-input spectral correctness.

Example (review exact hashes before running):
  python3 scripts/rebind_p15_src_operator.py --exporter /build/test/dsd_test_p15_src_stage_export \
    --approve-drift src/dsd.c=OLD_SHA:NEW_SHA \
    --approve-drift src/dsd_public.c=OLD_SHA:NEW_SHA \
    --approve-drift test/Makefile.am=OLD_SHA:NEW_SHA \
    --audit-out tests/dsd/results/P15_OPERATOR_REBIND_2026-10-20 --publish

Omit --publish to inspect the comparison without editing the source tree.
An approved hash change is not, by itself, an engineering review: the reviewer
must independently establish whether the changed source can affect the captured
stage operator or unmeasured full-chain behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/dsd'))
from p15_src_bound_operator import (UnboundOperator, load_snapshot, sha_file,
                                    source_identity, SOURCES)
from p15_src_capture_matrix import DEFAULT, verify_matrix, publish as publish_summary
from p15_src_complete_aliases import all_active_cells

EXTRA = ('VALIDATION.json', 'RECAPTURE_AUDIT.json',
         'BUILD_PROVENANCE.json', 'OPERATOR_VERIFICATION.md')
EXPECTED_STATUS = 'SOURCE_BOUND_UNCERTIFIED'
HEX = set('0123456789abcdef')


def die(msg: str) -> None:
    raise UnboundOperator(msg)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(obj: dict) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def parse_approved(values: list[str]) -> dict[str, tuple[str, str]]:
    result = {}
    for item in values:
        try:
            path, pair = item.split('=', 1)
            before, after = pair.split(':', 1)
        except ValueError:
            die('approve-drift needs PATH=OLD_SHA256:NEW_SHA256')
        if (path not in SOURCES or path in result or
            any(len(h) != 64 or not set(h) <= HEX for h in (before, after)) or
            before == after):
            die('malformed, duplicate, unpinned or unchanged drift authorization: ' + path)
        result[path] = (before, after)
    return result


def safe_read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        die('unsafe/missing regular evidence file: ' + str(path))
    return path.read_bytes()


def atomic_replace(path: Path, body: bytes) -> None:
    if path.is_symlink() or not path.is_file():
        die('refusing to replace non-regular receipt: ' + str(path))
    fd, tmp = tempfile.mkstemp(prefix='.operator-rebind-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(exporter: Path, approved: dict, audit_out: Path | None, publish: bool) -> dict:
    if not exporter.is_file() or not os.access(exporter, os.X_OK):
        die('missing/non-executable test-only C stage exporter')
    exporter_digest = sha_file(exporter)
    source_before = source_identity()
    approved_used = set()
    pairs = sorted({(c['intermediate_hz'], c['output_hz']) for c in all_active_cells()})
    if len(pairs) != 24:
        die('canonical P15 active SRC pair set has changed')
    names = {f'{a}-{b}' for a, b in pairs}
    if {p.name for p in DEFAULT.iterdir() if p.is_dir()} != names:
        die('missing/extra or unrecognized active source-bound stage pair directory')
    if (DEFAULT.is_symlink() or not DEFAULT.is_dir() or
        audit_out is not None and (audit_out.exists() or audit_out.is_symlink())):
        die('unsafe active directory or existing audit destination (refuse overwrite)')

    original = {}
    drift = {}
    pinned = set(SOURCES)
    for a, b in pairs:
        name = f'{a}-{b}'
        folder = DEFAULT / name
        if folder.is_symlink() or {p.name for p in folder.iterdir()} != {
            'operator-binding.json', 'stage-snapshot.json'}:
            die('unsafe/noncanonical active stage receipt: ' + name)
        raw = safe_read(folder/'stage-snapshot.json')
        binding_bytes = safe_read(folder/'operator-binding.json')
        receipt = json.loads(binding_bytes)
        op = load_snapshot(folder/'stage-snapshot.json')
        if (receipt.get('schema') != 'P15/stage-source-binding/1' or
            receipt.get('status') != EXPECTED_STATUS or receipt.get('qualified') is not False or
            set(receipt.get('source_sha256', {})) != pinned or
            receipt.get('snapshot_sha256') != digest(raw) or
            (receipt.get('input_hz'), receipt.get('output_hz')) != (a, b) or
            (op.input_hz, op.output_hz, op.U, op.V, op.stage_period_multiple) !=
            (a, b, receipt.get('U'), receipt.get('V'), receipt.get('period_multiple'))):
            die('invalid preexisting stage snapshot/binding: ' + name)
        pair_drift = {}
        for path, old_hash in receipt['source_sha256'].items():
            current_hash = source_before[path]
            if old_hash == current_hash:
                continue
            if approved.get(path) != (old_hash, current_hash):
                die('unapproved source hash drift in ' + name + ': ' + path)
            pair_drift[path] = {'before': old_hash, 'after': current_hash}
            approved_used.add(path)
            if path in drift and drift[path] != pair_drift[path]:
                die('non-uniform predecessor hash: ' + path)
            drift[path] = pair_drift[path]
        original[name] = (raw, binding_bytes, receipt)
    if approved_used != set(approved):
        die('unused/mismatched drift approvals: ' + repr(sorted(set(approved) - approved_used)))

    with tempfile.TemporaryDirectory(prefix='p15-independent-recapture-') as tmp:
        stage = Path(tmp) / 'new'
        matrix = verify_matrix(stage, exporter)
        publish_summary(matrix, stage/'SUMMARY.json')
        new = {}
        for a, b in pairs:
            name = f'{a}-{b}'
            saved_raw, _, saved = original[name]
            fresh_raw = safe_read(stage/name/'stage-snapshot.json')
            fresh_body = safe_read(stage/name/'operator-binding.json')
            fresh = json.loads(fresh_body)
            if fresh_raw != saved_raw:
                die('OPERATOR CHANGED: stage snapshots are not byte-identical for ' + name)
            if fresh['source_sha256'] != source_before or fresh['exporter_sha256'] != exporter_digest:
                die('new capture is not bound to the requested source/exporter: ' + name)
            differing = {key for key in saved.keys() | fresh.keys() if saved.get(key) != fresh.get(key)}
            if differing - {'source_sha256', 'exporter_sha256'}:
                die('operator receipt has additional changes: ' + name + ' / ' + str(differing))
            new[name] = (fresh_body, fresh)
        existing_summary = json.loads(safe_read(DEFAULT/'SUMMARY.json'))
        expected_summary = json.loads(safe_read(stage/'SUMMARY.json'))
        if ({key: val for key, val in existing_summary.items() if key != 'source_sha256'} !=
            {key: val for key, val in expected_summary.items() if key != 'source_sha256'}):
            die('summary changed beyond source hashes')
        if source_identity() != source_before or sha_file(exporter) != exporter_digest:
            die('source/exporter changed during independent recapture')

        record = dict(schema='P15/mechanical-source-rebind-audit/1',
                      status='CAPTURED_IDENTICAL_SOURCE_BOUND_UNCERTIFIED',
                      qualified=False, scope='24 private SRC stage snapshots only; no full-chain runtime proof',
                      source_root=str(ROOT), exporter_sha256=exporter_digest,
                      source_sha256=source_before, approved_source_drift=drift,
                      pairs=[dict(pair=name, stage_snapshot_sha256=digest(original[name][0]),
                                  previous_binding_sha256=digest(original[name][1]),
                                  new_binding_sha256=digest(new[name][0]),
                                  bytes_identical=True) for name in sorted(new)],
                      distinct_src_realizations=matrix['distinct_private_src_realizations'],
                      matrix_cells=matrix['tested_matrix_cells'],
                      alias_families=matrix['total_individually_enumerated_families_at_1khz'],
                      release='NOT_CHANGED', old_summary_sha256=sha_file(DEFAULT/'SUMMARY.json'),
                      new_summary_sha256=sha_file(stage/'SUMMARY.json'),
                      safeguards=['explicit exact old/new SHA256 approvals for every drift',
                                  'all 35 pins retained', 'new actual C exporter replay',
                                  'all 24 stage JSON byte-identical',
                                  'all receipt nonbinding fields identical',
                                  'matrix semantics and summary unchanged'])
        if publish:
            if audit_out is None:
                die('publication requires an unused --audit-out to preserve predecessor receipts')
            audit_out.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.p15-audit-prepared-', dir=audit_out.parent) as scratch:
                archive = Path(scratch) / 'audit'
                (archive/'previous_bindings').mkdir(parents=True)
                (archive/'previous_audit').mkdir()
                for name in names:
                    (archive/'previous_bindings'/(name+'.json')).write_bytes(original[name][1])
                for filename in EXTRA:
                    (archive/'previous_audit'/filename).write_bytes(safe_read(DEFAULT/filename))
                (archive/'RECAPTURE_AUDIT.json').write_bytes(encode(record))
                (archive/'new_SUMMARY.json').write_bytes(safe_read(stage/'SUMMARY.json'))
                (archive/'rebind_script_sha256.txt').write_text(sha_file(Path(__file__))+'\n')
                for dirpath, _, filenames in os.walk(archive):
                    for filename in filenames:
                        with (Path(dirpath)/filename).open('rb') as f:
                            os.fsync(f.fileno())
                if audit_out.exists():
                    die('audit destination appeared while preparing publication')
                os.replace(archive, audit_out)
            for name in sorted(new):
                path = DEFAULT/name/'operator-binding.json'
                if safe_read(path) != original[name][1]:
                    die('concurrent receipt change, review audit/rollback directory: ' + name)
                if original[name][1] != new[name][0]:
                    atomic_replace(path, new[name][0])
            atomic_replace(DEFAULT/'SUMMARY.json', safe_read(audit_out/'new_SUMMARY.json'))
            record['published'] = True
        else:
            record['published'] = False
        print(json.dumps({k: record[k] for k in (
            'status', 'distinct_src_realizations', 'matrix_cells', 'alias_families', 'published')},
            sort_keys=True))
        return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exporter', required=True, type=Path)
    parser.add_argument('--approve-drift', action='append', default=[], metavar='PATH=OLD:NEW')
    parser.add_argument('--audit-out', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    try:
        run(args.exporter, parse_approved(args.approve_drift), args.audit_out, args.publish)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, 'REFUSED: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
