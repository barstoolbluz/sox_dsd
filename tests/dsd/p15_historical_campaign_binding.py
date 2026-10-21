#!/usr/bin/env python3
"""Independent historical campaign identity across the Oct 20 SRC rebind.

Historical 11,516 receipts remain bound to the source they actually certified.
A byte-identical stage recapture does NOT turn these into receipts for the new
35-file provenance set; current-source campaign reuse remains fail-closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from p15_src_bound_operator import source_identity, sha_file, UnboundOperator
from p15_current_closeout import (ROOT, RESULTS, REBOUND, ACTIVE_STAGES,
                                  REBOUND_PAIRS, _reviewed_rebind_admission,
                                  _admitted_revision)

EXPECTED_2026_10_20_NONSTAGE_DRIFT = frozenset(
    ('src/dsd.c', 'src/dsd_public.c', 'test/Makefile.am'))
DESIGN = ROOT / 'docs/dsd/DSD_DESIGN.md'


def historical_bindings() -> dict:
    """Read only historical binding; verify exact, separately audited lineage."""
    revisions, audit = _reviewed_rebind_admission()
    current = source_identity()
    old_source = None
    old_exporter = None
    for pair in REBOUND_PAIRS:
        rel = str(ACTIVE_STAGES / pair / 'operator-binding.json')
        row = revisions[rel]
        _admitted_revision(rel, row['historical_sha256'],
                           row['current_sha256'], revisions, audit)
        old = json.loads((ROOT / REBOUND / 'preimages' / rel).read_text())
        current_doc = json.loads((ROOT / rel).read_text())
        actual_stage = sha_file(ROOT / ACTIVE_STAGES / pair / 'stage-snapshot.json')
        if (old['snapshot_sha256'] != actual_stage or
            current_doc['snapshot_sha256'] != actual_stage):
            raise UnboundOperator('stage snapshot differs from frozen operator: ' + pair)
        if old_source is None:
            old_source = old['source_sha256']
            old_exporter = old['exporter_sha256']
        elif old_source != old['source_sha256'] or old_exporter != old['exporter_sha256']:
            raise UnboundOperator('mixed historical SRC operator source/exporter identities')
    if (old_source is None or set(old_source) != set(current) or
        {p for p in current if old_source[p] != current[p]} !=
        EXPECTED_2026_10_20_NONSTAGE_DRIFT):
        raise UnboundOperator('not the reviewed historical/current source lineage')
    return {'source': old_source, 'design': sha_file(DESIGN)}


def status() -> dict:
    historic = historical_bindings()
    current = source_identity()
    return dict(schema='P15/historical-to-current-SRC-lineage/1',
                status='HISTORICAL_RECEIPTS_VERIFIABLE_NOT_CURRENT_SOURCE_CERTIFICATES',
                qualified_release=False, preserved_historical_source=historic['source'],
                new_current_source=current,
                nonstage_hash_drift=sorted(EXPECTED_2026_10_20_NONSTAGE_DRIFT),
                byte_identical_stage_snapshots=24)
