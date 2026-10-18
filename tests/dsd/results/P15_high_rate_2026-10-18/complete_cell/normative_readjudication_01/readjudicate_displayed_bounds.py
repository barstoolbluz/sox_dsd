#!/usr/bin/env python3
"""Readjudicate preserved P15 PASS summaries against exact normative limits.

No numerical proof is rerun. Source/operator identity checks are reported
separately; exact scalar admission does not manufacture missing provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

import verify_complete_cell as exact


ORIGINAL = 'tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/receipts'
LARGER = 'tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/budget-sample'
THIRD = 'tests/dsd/results/P15_prover_third_pass_2026-10-18/final_local_certificates'
CURRENT = 'tests/dsd/results/P15_high_rate_2026-10-18'
HISTORICAL_DISPLAY_CODE = 'tests/dsd/results/P15_prover_optimization_2026-10-18/baseline_code/p15_src_stagewise_continuum.py'
HISTORICAL_DISPLAY_CODE_SHA = '81811f88791ef95388c7d33a0c46b9dacc678367ff83f324864a33f64b543d10'
INHERITED_INVENTORY = CURRENT + '/authority/INHERITED_FILES.sha256'
INHERITED_INVENTORY_SHA = '173f819d8884f50237c126c71c66c7b3222c8d1f39f0a4270966a402bce12783'
BOUND_FIELDS = ('max_coherent_alias_upper', 'max_native_stop_source_transfer_upper',
                'min_wanted_transfer_lower', 'max_total_transfer_upper')
PASS_STATES = ('PASS-LOCAL-BAND', 'PASS-LOCAL-STOP-SOURCE')


class Insufficient(exact.Invalid):
    pass


def certificate_and_mode(doc):
    cert = doc.get('certificate', doc)
    if type(cert) is not dict or cert.get('status') not in PASS_STATES:
        return None, None
    return cert, 'pass' if cert['status'] == 'PASS-LOCAL-BAND' else 'stop'


def validate_obligation(doc, cert, mode, profiles):
    required = (*BOUND_FIELDS, 'profile', 'native_hz', 'input_hz', 'output_hz',
                'band_kind', 'certified_hz', 'governing_passband_hz',
                'governing_stopband_hz', 'limits', 'qualified_release')
    missing = [name for name in required if name not in cert]
    if missing:
        raise Insufficient('missing certificate fields: ' + ','.join(missing))
    if doc.get('schema') not in (exact.SCHEMA, 'P15/local-source-bound-composite-continuum/1'):
        raise Insufficient('unreviewed receipt schema')
    exact.require(doc.get('qualified_release') is False and cert['qualified_release'] is False,
                  'release disposition is not explicitly unqualified')
    exact.require(cert['profile'] in profiles and cert['profile'] in exact.NORMATIVE_BANDS,
                  'unrecognized native profile')
    profile = profiles[cert['profile']]
    P, S = exact.NORMATIVE_BANDS[cert['profile']]
    exact.require((profile['pass_hz'], profile['stop_hz']) == (P, S), 'native normative band mismatch')
    exact.require(cert['native_hz'] == profile['native_hz'] and cert['input_hz'] == profile['intermediate_hz'],
                  'native/intermediate clock mismatch')
    exact.require(type(cert['output_hz']) is int and cert['output_hz'] > 0, 'invalid PCM output clock')
    exact.require(cert['band_kind'] == mode and cert['governing_passband_hz'] == P and
                  cert['governing_stopband_hz'] == S and
                  cert['limits'] == {'passband_db': '0.0001', 'coherent_alias_db': '-160'},
                  'normative obligation mismatch')
    endpoints = cert['certified_hz']
    exact.require(type(endpoints) is list and len(endpoints) == 2 and all(type(x) is str for x in endpoints),
                  'invalid frequency endpoints')
    lo, hi = map(Fraction, endpoints)
    effective = min(Fraction(P), Fraction(475, 1000)*min(cert['input_hz'], cert['output_hz']))
    end = effective if mode == 'pass' else Fraction(cert['output_hz'], 2)
    exact.require(0 <= lo <= hi <= min(end, Fraction(cert['native_hz'], 2)), 'frequency outside normative obligation')
    display_profile = ('mastering_v2' if cert['profile'].startswith('decode.mastering.v2.') else
                       'mastering' if cert['profile'].startswith('master') else 'wideband')
    cell = f"dsd{cert['native_hz']//44100}.{display_profile}.pcm{cert['output_hz']}"
    job = dict(cell_id=cell, profile=cert['profile'], intermediate_hz=cert['input_hz'],
               output_hz=cert['output_hz'], mode=mode, lo=str(lo), hi=str(hi),
               effective_p=str(effective), source_s=S)
    if 'job' in doc:
        exact.require(doc['job'] == job, 'outer canonical job and certificate disagree')
    canonical = (lo < end and lo.denominator == 1 and lo % 1000 == 0 and hi == min(lo+1000, end))
    return job, exact.digest(job) if canonical else None


def provenance(doc, expected_binding, pair_hashes):
    if 'binding' in doc:
        binding = doc['binding']
    else:
        binding = dict(source=doc.get('source_sha256'), design=doc.get('governing_dsd_design_sha256'))
    source_status = ('CURRENT_SOURCE_AND_DESIGN_PINS_MATCH' if binding == expected_binding else
                     'MISSING_SOURCE_BINDING' if binding.get('source') is None else 'SOURCE_BINDING_MISMATCH')
    cert = doc.get('certificate', doc)
    pair = (cert.get('input_hz'), cert.get('output_hz'))
    snapshot, operator = doc.get('stage_snapshot_sha256'), doc.get('verified_operator_binding_sha256')
    if snapshot is None and operator is None:
        operator_status = 'NOT_RECORDED_IN_HISTORICAL_RECEIPT'
    else:
        expected = pair_hashes(*pair)
        operator_status = ('RECORDED_OPERATOR_IDENTITIES_MATCH' if (snapshot, operator) == expected else
                           'OPERATOR_IDENTITY_MISMATCH')
    code = doc.get('prover_code_sha256')
    code_status = ('NOT_RECORDED_IN_HISTORICAL_RECEIPT' if code is None else 'RECORDED_SEPARATELY')
    identity = doc.get('experiment_identity')
    if identity is not None:
        exact.require(type(identity) is dict and identity.get('binding') == binding and
                      identity.get('job') == doc.get('job') and identity.get('prover_code_sha256') == code and
                      identity.get('stage_snapshot_sha256') == snapshot and
                      identity.get('verified_operator_binding_sha256') == operator,
                      'experiment identity disagrees with receipt provenance')
    return binding, dict(source_binding_status=source_status, operator_identity_status=operator_status,
                        prover_identity_status=code_status,
                        recorded_stage_snapshot_sha256=snapshot,
                        recorded_operator_binding_sha256=operator,
                        recorded_prover_identity_sha256=exact.digest(code) if code is not None else None,
                        recorded_harness_sha256=identity.get('harness_sha256') if identity else None)


def assess(doc, profiles):
    """Only the scalar mathematical envelope is adjudicated by this function."""
    cert, mode = certificate_and_mode(doc)
    exact.require(cert is not None, 'not a preserved PASS receipt')
    try:
        job, work = validate_obligation(doc, cert, mode, profiles)
    except Insufficient as exc:
        return dict(normative_envelope_status='INSUFFICIENT_FIELDS', reason=str(exc)), None
    except (exact.Invalid, ValueError, TypeError, KeyError) as exc:
        return dict(normative_envelope_status='INVALID', reason=str(exc)), None
    result = dict(job=job, canonical_work_sha256=work)
    try:
        checked = exact.check_inequalities(cert, mode)
    except (exact.Invalid, ValueError, TypeError, KeyError) as exc:
        result.update(normative_envelope_status='DISPLAY_INEQUALITY_UNPROVED', reason=str(exc))
        return result, None
    margins = exact.exact_margins(cert, mode)
    exact.require(all(value > 0 for value in margins.values()), 'nonpositive exact threshold margin')
    result.update(normative_envelope_status='EXACT_NORMATIVE_ENVELOPE_VERIFIED', checked_bounds=checked,
        amplitude_margin_lower_binary64_hex={name: math.nextafter(float(value), -math.inf).hex()
                                             for name, value in margins.items()})
    return result, margins


def default_paths(root):
    groups = [(name, sorted((root/path).glob('*.json'))) for name, path in (
        ('original_canonical', ORIGINAL), ('historical_600s', LARGER), ('third_pass_local', THIRD))]
    current = [path for path in sorted((root/CURRENT).rglob('*.json'))
               if 'complete_cell' not in path.relative_to(root/CURRENT).parts]
    groups.append(('current_high_rate', current))
    return [(scope, path, None) for scope, paths in groups for path in paths]


def scan(root, inventory_path=None):
    # This validates the fixed source identities and source-code snapshots.
    expected_binding, _ = exact.dependencies(root)
    profiles = exact.load(root/'tests/dsd/reference/p06_coefficients.json')['profiles']
    profiles.update(exact.load(root/'tests/dsd/reference/p15_r3_coefficients.json')['profiles'])
    inventory_raw = exact.pinned(root/INHERITED_INVENTORY, INHERITED_INVENTORY_SHA)
    inherited = {}
    for line in inventory_raw.decode().splitlines():
        value, name = line.split('  ', 1)
        inherited[name] = value
    exact.pinned(root/HISTORICAL_DISPLAY_CODE, HISTORICAL_DISPLAY_CODE_SHA)
    if inventory_path:
        prior = exact.load(inventory_path)
        paths = []
        for item in prior:
            rel = Path(item['receipt_path'])
            exact.require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe replay inventory path')
            paths.append((item['scope'], root/rel, item['receipt_sha256']))
    else:
        paths = default_paths(root)
    cache = {}
    def pair_hashes(input_hz, output_hz):
        key = input_hz, output_hz
        if key not in cache:
            folder = root/'tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17'/f'{input_hz}-{output_hz}'
            cache[key] = tuple(sha256(exact.read_file(folder/name)).hexdigest()
                               for name in ('stage-snapshot.json', 'operator-binding.json'))
        return cache[key]
    receipts, inventory, unparsed, source_bindings, prover_identities = [], [], [], {}, {}
    scanned, passes = Counter(), Counter()
    minima = {}
    for scope, path, expected_hash in paths:
        raw = exact.read_file(path)
        value = sha256(raw).hexdigest()
        rel = str(path.relative_to(root))
        if expected_hash is not None:
            exact.require(value == expected_hash, 'scan replay receipt hash mismatch: ' + rel)
        inventory.append(dict(scope=scope, receipt_path=rel, receipt_sha256=value))
        scanned[scope] += 1
        try:
            doc = exact.strict_json(raw)
        except (ValueError, TypeError) as exc:
            unparsed.append(dict(receipt_path=rel, receipt_sha256=value, reason=str(exc)))
            continue
        if type(doc) is not dict:
            continue
        cert, mode = certificate_and_mode(doc)
        if cert is None:
            continue
        passes[scope] += 1
        row = dict(receipt_path=rel, receipt_sha256=value, scope=scope,
                   original_status=cert['status'], numerical_proof_replayed=False)
        scalar, margins = assess(doc, profiles)
        row.update(scalar)
        binding, details = provenance(doc, expected_binding, pair_hashes)
        binding_id = exact.digest(binding)
        source_bindings[binding_id] = binding
        row.update(details, recorded_source_binding_sha256=binding_id)
        code = doc.get('prover_code_sha256')
        if code is not None:
            prover_identities[exact.digest(code)] = code
        if scope != 'current_high_rate':
            row['inherited_receipt_sha256_matches'] = inherited.get(rel) == value
        if row.get('canonical_work_sha256') and re.fullmatch('[0-9a-f]{64}', path.stem):
            exact.require(path.stem == row['canonical_work_sha256'], 'canonical receipt filename mismatch: ' + rel)
        if margins is not None:
            for name, margin in margins.items():
                if name not in minima or margin < minima[name][0]:
                    minima[name] = margin, row
        receipts.append(row)
    exact.require(scanned['original_canonical'] == 11516 and passes['original_canonical'] == 6835,
                  'original canonical receipt population changed')
    exact.require(scanned['historical_600s'] == 48 and passes['historical_600s'] == 36,
                  'historical larger-budget population changed')
    exact.require(scanned['third_pass_local'] == passes['third_pass_local'] == 4,
                  'third-pass local certificate population changed')
    counts = Counter(row['normative_envelope_status'] for row in receipts)
    summary_by_scope = {scope: dict(scanned_files=scanned[scope], preserved_pass_receipts=passes[scope],
        dispositions=dict(Counter(row['normative_envelope_status'] for row in receipts if row['scope'] == scope)))
        for scope in sorted(scanned)}
    min_summary = {name: dict(amplitude_margin_lower_rational=str(margin),
        amplitude_margin_lower_display=math.nextafter(float(margin), -math.inf),
        receipt_path=row['receipt_path'], receipt_sha256=row['receipt_sha256'],
        source_scope=row['scope'], canonical_work_sha256=row.get('canonical_work_sha256'))
        for name, (margin, row) in minima.items()}
    report = dict(schema='P15/exact-normative-envelope-readjudication/1',
        status='ALL_SCANNED_PASS_SUMMARIES_EXACT_NORMATIVE' if
            counts['EXACT_NORMATIVE_ENVELOPE_VERIFIED'] == len(receipts) and not unparsed else 'OPEN',
        qualified_release=False, p15_release='BLOCKED', numerical_proof_replayed=False,
        receipt_count=len(receipts), dispositions=dict(counts), by_scope=summary_by_scope,
        minimum_amplitude_margin_by_bound=min_summary,
        source_binding_dispositions=dict(Counter(row['source_binding_status'] for row in receipts)),
        operator_identity_dispositions=dict(Counter(row['operator_identity_status'] for row in receipts)),
        recorded_source_bindings=source_bindings, recorded_prover_identities=prover_identities,
        inherited_inventory_sha256=INHERITED_INVENTORY_SHA,
        historical_outward_display_code=dict(path=HISTORICAL_DISPLAY_CODE, sha256=HISTORICAL_DISPLAY_CODE_SHA),
        exact_threshold_enclosures=dict(gain_minus=[str(q) for q in exact.GAIN_MINUS],
            gain_plus=[str(q) for q in exact.GAIN_PLUS], alias_limit='1/100000000'),
        implementation_sha256={Path(__file__).name: sha256(exact.read_file(Path(__file__))).hexdigest(),
            Path(exact.__file__).name: sha256(exact.read_file(Path(exact.__file__))).hexdigest()},
        scope=('Readjudication of the recorded outward numerical enclosure summaries against exact normative '
               'scalar limits, avoiding the inherited widened db_band thresholds. The original dispositions '
               'and receipt bytes are unchanged. No interval arithmetic, alias population, phase identity, '
               'internal leaf coverage, FFT4G execution-roundoff, or physical qualification is recomputed. '
               'Source/operator/prover provenance is recorded and checked separately; absent historical '
               'per-receipt operator/prover hashes are not synthesized. Source identity alone is not a '
               'numerical proof replay. This report describes only its frozen scan inventory.'),
        unparsed_input_files=unparsed, receipts=receipts)
    return report, inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, help='Replay the exact file/hash inventory of an earlier scan')
    args = parser.parse_args(argv)
    report, inventory = scan(args.root.resolve(strict=True), args.inventory)
    out = args.output.absolute()
    exact.publish(out/'verification.json', exact.encoded(report))
    exact.publish(out/'scan_inventory.json', exact.encoded(inventory))
    admitted = [row for row in report['receipts'] if row['normative_envelope_status'] == 'EXACT_NORMATIVE_ENVELOPE_VERIFIED']
    exact.publish(out/'EXACT_NORMATIVE_RECEIPTS.sha256', ''.join(
        row['receipt_sha256'] + '  ' + row['receipt_path'] + '\n' for row in admitted).encode())
    for path in (Path(__file__), Path(exact.__file__)):
        exact.publish(out/path.name, exact.read_file(path))
    lines = ['# Exact normative readjudication of preserved PASS receipts', '',
        report['status'], '', '| Scope | Preserved PASS receipts | Exact normative envelopes verified |',
        '|---|---:|---:|']
    for scope, row in report['by_scope'].items():
        lines.append(f"| {scope} | {row['preserved_pass_receipts']} | {row['dispositions'].get('EXACT_NORMATIVE_ENVELOPE_VERIFIED', 0)} |")
    lines += ['', 'No numerical proof was replayed. Original receipt bytes and dispositions remain unchanged.',
        'All scalar comparisons use exact rational threshold enclosures; the widened historical db_band decision limits are not used.',
        'Source and operator provenance appear separately in verification.json. Missing historical per-receipt hashes are not invented.',
        'P15 remains BLOCKED.', '', '## Smallest independently bounded amplitude margins', '']
    for name, row in report['minimum_amplitude_margin_by_bound'].items():
        lines.append(f"- {name}: at least {row['amplitude_margin_lower_display']:.17g}; receipt SHA-256 `{row['receipt_sha256']}`.")
    exact.publish(out/'SUMMARY.md', ('\n'.join(lines)+'\n').encode())
    manifest = ''.join(sha256(exact.read_file(path)).hexdigest()+'  '+path.name+'\n'
                       for path in sorted(out.iterdir()) if path.is_file() and path.name != 'SHA256SUMS')
    exact.publish(out/'SHA256SUMS', manifest.encode())
    print(json.dumps({key: report[key] for key in ('status', 'receipt_count', 'dispositions',
        'by_scope', 'source_binding_dispositions', 'operator_identity_dispositions')}, sort_keys=True))
    print(json.dumps({'minimum_margin_displays': {key: row['amplitude_margin_lower_display']
          for key, row in report['minimum_amplitude_margin_by_bound'].items()}}, sort_keys=True))
    return 0 if report['status'] == 'ALL_SCANNED_PASS_SUMMARIES_EXACT_NORMATIVE' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (exact.Invalid, ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps(dict(status='OPEN', qualified_release=False, error=str(exc)), sort_keys=True))
        raise SystemExit(2)
