#!/usr/bin/env python3
"""Fail-closed, idempotent recovery for interrupted P15 operator publication.

The original rebind publishes the immutable audit archive *before* replacing
24 active binding receipts and the matrix summary. A process interruption can
leave an incomplete commit; this utility independently re-captures the current
C exporter, authenticates both sides against the archived hashes, and publishes
only validated missing replacements. A rebuilt verifier exporter is accepted
only if the re-captured stage bytes and the original published receipt hashes
are identical; the audit's originally published exporter hash is retained. No stage snapshot or historical receipt
is ever edited. Without --publish it runs as a read-only preflight.

Example:
  python3 scripts/recover_p15_src_operator_rebind.py \
    --exporter /build/test/dsd_test_p15_src_stage_export --publish
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/dsd'))
import rebind_p15_src_operator as reb
from p15_src_capture_matrix import DEFAULT, publish as publish_summary, verify_matrix
from p15_src_bound_operator import SOURCES, UnboundOperator, sha_file, source_identity
from p15_src_complete_aliases import all_active_cells

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / 'tests/dsd/results/P15_OPERATOR_REBIND_2026-10-20'


def require(ok: bool, description: str) -> None:
    if not ok:
        raise UnboundOperator('RECOVERY REFUSED: ' + description)


def recover(exporter: Path, audit_dir: Path, publish: bool, active_dir: Path = DEFAULT) -> dict:
    require(exporter.is_file() and os.access(exporter, os.X_OK),
            'missing/non-executable C stage exporter')
    require(audit_dir.is_dir() and not audit_dir.is_symlink() and
            active_dir.is_dir() and not active_dir.is_symlink(), 'unsafe audit or stage directory')
    record = json.loads(reb.safe_read(audit_dir / 'RECAPTURE_AUDIT.json'))
    require(record.get('schema') == 'P15/mechanical-source-rebind-audit/1' and
            record.get('status') == 'CAPTURED_IDENTICAL_SOURCE_BOUND_UNCERTIFIED' and
            record.get('qualified') is False and record.get('release') == 'NOT_CHANGED',
            'unrecognized source rebind audit')
    before = source_identity()
    exporter_sha = sha_file(exporter)
    require(record.get('source_sha256') == before and
            set(before) == set(SOURCES) and len(before) == 35 and
            isinstance(record.get('exporter_sha256'), str) and
            len(record['exporter_sha256']) == 64 and
            set(record.get('approved_source_drift', {})) ==
            {'src/dsd.c', 'src/dsd_public.c', 'test/Makefile.am'},
            'source identity, exporter identity or reviewed source-drift set changed')
    for path, hashes in record['approved_source_drift'].items():
        require(hashes['after'] == before[path] and hashes['before'] != hashes['after'],
                'audit has invalid drift pair: ' + path)

    pairs = sorted({f"{c['intermediate_hz']}-{c['output_hz']}" for c in all_active_cells()})
    require(len(pairs) == 24 and
            len(record.get('pairs', [])) == 24 and
            {r['pair'] for r in record['pairs']} == set(pairs) and
            record.get('matrix_cells') == 72 and
            record.get('alias_families') == 214432 and
            record.get('distinct_src_realizations') == 24,
            'audit pair/alias/cell coverage invalid')
    require({p.name for p in active_dir.iterdir() if p.is_dir()} == set(pairs),
            'active directory contains missing/extra stages')
    indexed = {entry['pair']: entry for entry in record['pairs']}
    states = {}

    with tempfile.TemporaryDirectory(prefix='p15-recovery-independent-capture-') as tmp:
        captured = Path(tmp) / 'captured'
        matrix = verify_matrix(captured, exporter)
        publish_summary(matrix, captured / 'SUMMARY.json')
        require(matrix['distinct_private_src_realizations'] == 24 and
                matrix['tested_matrix_cells'] == 72 and
                matrix['total_individually_enumerated_families_at_1khz'] == 214432,
                'independent recapture has incorrect dimensions')
        new_summary = reb.safe_read(captured / 'SUMMARY.json')
        require(reb.digest(new_summary) == record['new_summary_sha256'] ==
                sha_file(audit_dir / 'new_SUMMARY.json') and
                reb.safe_read(audit_dir / 'new_SUMMARY.json') == new_summary,
                'new matrix summary differs from the audited result')
        for pair in pairs:
            path = active_dir / pair
            require(path.is_dir() and not path.is_symlink() and
                    {p.name for p in path.iterdir()} ==
                    {'operator-binding.json', 'stage-snapshot.json'},
                    'noncanonical active directory: ' + pair)
            row = indexed[pair]
            stage = reb.safe_read(path / 'stage-snapshot.json')
            captured_stage = reb.safe_read(captured / pair / 'stage-snapshot.json')
            require(stage == captured_stage and reb.digest(stage) == row['stage_snapshot_sha256']
                    and row['bytes_identical'] is True,
                    'operator changed during recovery: ' + pair)
            old = reb.safe_read(audit_dir / 'previous_bindings' / (pair + '.json'))
            # The *verifying* exporter may be rebuilt on a different host,
            # with a different libtool wrapper hash. Preserve the published
            # audit's old exporter identity; rewrite no historical evidence.
            # A different verifier is admissible only when it independently
            # re-captures exactly the same stage bytes and the normalized
            # original audited binding hashes check byte-for-byte.
            verifier_binding = json.loads(reb.safe_read(
                captured / pair / 'operator-binding.json'))
            require(verifier_binding.get('exporter_sha256') == exporter_sha,
                    'fresh receipt does not identify independent verifier: ' + pair)
            published_binding = dict(verifier_binding,
                                     exporter_sha256=record['exporter_sha256'])
            new = reb.encode(published_binding)
            current = reb.safe_read(path / 'operator-binding.json')
            require(reb.digest(old) == row['previous_binding_sha256'] and
                    reb.digest(new) == row['new_binding_sha256'] and
                    current in (old, new),
                    'binding neither archived original nor verified recapture: ' + pair)
            previous = json.loads(old)
            fresh = json.loads(new)
            require(previous['snapshot_sha256'] == fresh['snapshot_sha256'] ==
                    row['stage_snapshot_sha256'] and
                    fresh.get('source_sha256') == before and
                    fresh.get('exporter_sha256') == record['exporter_sha256'] and
                    fresh.get('status') == previous.get('status') == 'SOURCE_BOUND_UNCERTIFIED' and
                    fresh.get('qualified') is previous.get('qualified') is False and
                    {k: v for k,v in previous.items()
                     if k not in ('source_sha256', 'exporter_sha256')} ==
                    {k: v for k,v in fresh.items()
                     if k not in ('source_sha256', 'exporter_sha256')},
                    'audited lineage changes nonbinding fields: ' + pair)
            historical = previous['source_sha256']
            require(set(historical) == set(before) and
                    {p for p in before if historical[p] != before[p]} ==
                    set(record['approved_source_drift']) and
                    all(historical[p] == hashes['before'] for p, hashes in
                        record['approved_source_drift'].items()),
                    'archived source is not the approved predecessor: ' + pair)
            states[pair] = (path / 'operator-binding.json', current, old, new)

        summary_path = active_dir / 'SUMMARY.json'
        summary_before = reb.safe_read(summary_path)
        require(reb.digest(summary_before) in
                (record['old_summary_sha256'], record['new_summary_sha256']) and
                (summary_before == new_summary or
                 reb.digest(summary_before) == record['old_summary_sha256']),
                'active summary is neither historical nor independently recaptured')
        if publish:
            require(source_identity() == before and sha_file(exporter) == exporter_sha,
                    'source or exporter changed after validation')
            # Every active file was validated before any mutation. Refuse races.
            for path, expected, _old, _new in states.values():
                require(reb.safe_read(path) == expected,
                        'concurrent receipt mutation during recovery')
            require(reb.safe_read(summary_path) == summary_before,
                    'concurrent summary mutation during recovery')
            for path, current, old, new in states.values():
                if current == old and old != new:
                    reb.atomic_replace(path, new)
            if summary_before != new_summary:
                reb.atomic_replace(summary_path, new_summary)
            require(all(reb.safe_read(row[0]) == row[3] for row in states.values()) and
                    reb.safe_read(summary_path) == new_summary and
                    source_identity() == before and sha_file(exporter) == exporter_sha,
                    'post-publication validation failed')
        status = dict(schema='P15/operator-rebind-recovery/1',
                      status='ALL_STAGE_SNAPSHOTS_BYTE_IDENTICAL',
                      published=publish,
                      already_current=sum(cur == new for _,cur,_,new in states.values()),
                      replacements_needed=sum(cur != new for _,cur,_,new in states.values()),
                      summary_already_current=summary_before == new_summary,
                      checked_stage_realizations=len(states),
                      source_sha256=before, verifier_exporter_sha256=exporter_sha,
                      bound_exporter_sha256=record['exporter_sha256'],
                      independently_rebuilt_exporter=exporter_sha != record['exporter_sha256'])
        print(json.dumps(status, sort_keys=True))
        return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exporter', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, default=DEFAULT_AUDIT)
    parser.add_argument('--publish', action='store_true', help='publish only missing audited updates')
    args = parser.parse_args()
    try:
        recover(args.exporter, args.audit_dir, args.publish)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, 'REFUSED: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
