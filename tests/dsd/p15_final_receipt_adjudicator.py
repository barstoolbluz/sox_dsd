#!/usr/bin/env python3
"""Read-only, source-archive-bound audit of the original P15 PASS receipt inventory.

Checks archive identity, byte-level correspondence, canonical coverage and
reported policy inequalities.  It does NOT independently recompute FIR bounds
or grant mathematical or release qualification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import math
from pathlib import Path
import tarfile

from p15_full_band_campaign import (SCHEMA, PROFILE_BANDS,
    canonical_plan, check_one, digest, receipt_path)

ARCHIVE_SHA256 = 'd058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210'
RECEIPT_PREFIX = 'sox_ng/tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/receipts/'

class UnacceptableReceipt(ValueError):
    pass


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _number(record: dict, name: str) -> Decimal:
    value = record.get(name)
    if type(value) is not float and type(value) is not int:
        raise UnacceptableReceipt('missing/non-numeric bound: ' + name)
    if not math.isfinite(value):
        raise UnacceptableReceipt('nonfinite bound: ' + name)
    return Decimal.from_float(float(value))


def audit_receipt(doc: dict, job: dict, binding: dict):
    """Check receipt's claimed numbers, not the underlying mathematics."""
    if doc.get('schema') != SCHEMA or doc.get('job') != job or doc.get('binding') != binding:
        raise UnacceptableReceipt('job/source/design binding mismatch')
    if doc.get('qualified_release') is not False:
        raise UnacceptableReceipt('release qualification fabricated')
    c = doc.get('certificate')
    if not isinstance(c, dict):
        raise UnacceptableReceipt('missing certificate')
    want = 'PASS-LOCAL-BAND' if job['mode'] == 'pass' else 'PASS-LOCAL-STOP-SOURCE'
    if c.get('status') != want or c.get('qualified_release') is not False:
        raise UnacceptableReceipt('non-PASS or release upgrade')
    for key, value in [('profile', job['profile']), ('certified_hz', [job['lo'], job['hi']]),
                       ('band_kind', job['mode']), ('input_hz', job['intermediate_hz']),
                       ('output_hz', job['output_hz']), ('governing_stopband_hz', job['source_s']),
                       ('governing_passband_hz', PROFILE_BANDS[job['profile']][0]),
                       ('limits', {'passband_db': '0.0001', 'coherent_alias_db': '-160'})]:
        if c.get(key) != value:
            raise UnacceptableReceipt('certificate field mismatch: ' + key)
    if type(c.get('fully_proven_subintervals')) is not int or c['fully_proven_subintervals'] < 1:
        raise UnacceptableReceipt('no certified subintervals')
    with localcontext() as ctx:
        ctx.prec = 90
        lower = Decimal(10) ** (-Decimal('0.0001') / 20)
        upper = Decimal(10) ** (Decimal('0.0001') / 20)
        aliases = Decimal('1e-8')
        if job['mode'] == 'pass':
            observations = [('min_wanted_transfer_lower', lower, '>'),
                ('max_total_transfer_upper', upper, '<'),
                ('max_coherent_alias_upper', aliases, '<')]
        else:
            observations = [('max_native_stop_source_transfer_upper', aliases, '<')]
        for name, target, relation in observations:
            value = _number(c, name)
            if value < 0 or not (value > target if relation == '>' else value < target):
                raise UnacceptableReceipt('reported PASS contradicts policy: ' + name)
    return want


def archive_compare(archive: Path, receipts: Path, expected_names: set[str]):
    if file_sha256(archive) != ARCHIVE_SHA256:
        raise UnacceptableReceipt('original compressed source archive SHA mismatch')
    found = set()
    with tarfile.open(archive, 'r:gz') as package:
        for member in package:
            if not member.name.startswith(RECEIPT_PREFIX):
                continue
            name = member.name[len(RECEIPT_PREFIX):]
            if not member.isfile() or name not in expected_names or name in found:
                raise UnacceptableReceipt('unexpected/duplicate archived receipt: ' + name)
            found.add(name)
            original = package.extractfile(member)
            if original is None:
                raise UnacceptableReceipt('unreadable archived receipt')
            data = original.read()
            local = receipts / name
            if local.is_symlink() or not local.is_file() or data != local.read_bytes():
                raise UnacceptableReceipt('archived receipt byte mismatch: ' + name)
    if found != expected_names:
        raise UnacceptableReceipt('archive receipt coverage incomplete')
    return len(found)


def verify(receipts: Path, archive: Path | None = None):
    jobs = canonical_plan('1000')
    # Do not pass current source_identity() to a 2026-10-18 historical receipt:
    # the three independently reviewed Oct-20 nonstage edits would mask every
    # policy check behind an early source-binding failure.
    from p15_historical_campaign_binding import historical_bindings
    binding = historical_bindings()
    if len(jobs) != 11516 or len({digest(j) for j in jobs}) != 11516:
        raise UnacceptableReceipt('canonical plan changed')
    if receipts.is_symlink() or not receipts.is_dir():
        raise UnacceptableReceipt('invalid receipt folder')
    expected = {digest(job) + '.json' for job in jobs}
    actual = {p.name for p in receipts.iterdir() if p.suffix == '.json'}
    if expected != actual:
        raise UnacceptableReceipt('unexpected/missing JSON receipts')
    counts = Counter()
    methods = Counter()
    inventory = sha256()
    for job in jobs:
        name = digest(job) + '.json'
        doc = check_one(receipts, job, binding)
        if doc is None:
            raise UnacceptableReceipt('missing receipt: ' + name)
        state = audit_receipt(doc, job, binding)
        counts[state] += 1
        methods[doc['certificate'].get('method', '<missing>')] += 1
        inventory.update(name.encode('ascii') + b'\0' + file_sha256(receipts / name).encode('ascii') + b'\n')
    if len(methods) != 1:
        raise UnacceptableReceipt('unexpected mixed prover-method receipt population')
    authenticated = archive_compare(archive, receipts, expected) if archive is not None else None
    return {'schema': 'P15/final-historical-receipt-adjudication/1',
        'status': 'RECEIPTS_CONSISTENT_WITH_REPORTED_POLICY_NOT_INDEPENDENT_MATH_PROOF',
        'archive_sha256': ARCHIVE_SHA256 if authenticated is not None else None,
        'bytes_compared_to_source_archive': authenticated,
        'jobs': len(jobs), 'counts': dict(counts), 'prover_method_population': dict(methods),
        'receipt_sha256_inventory': inventory.hexdigest(),
        'limits': {'passband_db': '0.0001', 'coherent_unwanted_amplitude': '1e-8'},
        'source_binding_status': 'HISTORICAL_SOURCE_WITH_SEPARATE_STAGE_REBIND',
        'qualified_mathematical_proof': False, 'qualified_release': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', required=True, type=Path)
    parser.add_argument('--source-archive', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = verify(args.receipts, args.source_archive)
    data = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.out:
        args.out.write_text(data)
    print(data, end='')

if __name__ == '__main__':
    main()
