#!/usr/bin/env python3
"""Fail-closed, *current-source* P15 evidence inventory, not a qualification test.

Never reinterpret the 2026-10-14 frozen release manifest, amend a P10
certificate, or call missing raw payloads a measurement failure. A successful
inventory run is not permission to promote defaults or start P16.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from p15_matrix_contract import CROSS_ISA_DETAIL_ENDPOINTS, make_plan
from p15_matrix_instrument import inherited_fir_certificate
from p15_intel_receipt_review import review as review_intel_physical
from p15_readjudication import (inspect_amendment, inspect_benchmark,
                                inspect_per_profile_benchmark, write_new)

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path('tests/dsd/results')
CERT = RESULTS / 'P10_certification_2026-10-11/certification.json'
BIND = RESULTS / 'DECODE_OPTIMIZATION_2026-10-12/validation/p10-certificate-binding.json'
PRIOR = RESULTS / 'P15_readjudication_2026-10-14/review.json'
DESIGN = Path('docs/dsd/DSD_DESIGN.md')
INTEL = Path('docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md')
V1 = RESULTS / 'P15_v1_matrix_rebound_2026-10-20'
V2 = RESULTS / 'P15_v2_matrix_rebound_2026-10-20'
TIERS = ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')
CHANGED_SOURCE = {'src/dsd_plan.c', 'src/pcmdsd.c', 'src/pcmdsd.h', 'src/sdm.c'}
# An exact input-revision admission, not a general exemption for edited design
# authority. Any subsequent amendment needs an explicit new adjudication.
REVIEWED_DESIGN_SHA256 = '458537dbe9a2ea1e687b68f998f43a90de10c369b604f809c78cf80c2389b94b'
REVIEWED_INTEL_SHA256 = '35e6eeff5f8fa584ec85659d9c70b12b825000be2aca50cbbb431b9b97ea5e84'


class InvalidEvidence(ValueError):
    pass


def require(ok: bool, why: str) -> None:
    if not ok:
        raise InvalidEvidence(why)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def digest(path: Path) -> str:
    return sha(ROOT / path)


def inventory() -> dict:
    """Retain omitted measured payload identities; refuse other absence/drift."""
    lines = (ROOT / RESULTS / 'P00/P00_SHA256SUMS.txt').read_text().splitlines()
    seen = set()
    omitted = {'arrays_npz': 0, 'supplemental_npz': 0, 'graph_raw': 0, 'state': 0}
    for line in lines:
        require(len(line) > 66 and line[64:66] == '  ', 'malformed P00 SHA line')
        expected, relative = line[:64], line[66:]
        require(len(expected) == 64 and all(c in '0123456789abcdef' for c in expected),
                'invalid P00 digest')
        p = Path(relative)
        require(relative not in seen and not p.is_absolute() and '..' not in p.parts,
                'unsafe/duplicate P00 entry: ' + relative)
        seen.add(relative)
        require(relative != str(RESULTS / 'P00/P00_SHA256SUMS.txt'),
                'P00 inventory must exclude itself')
        full = ROOT / p
        if full.is_file():
            require(sha(full) == expected, 'changed inventory entry: ' + relative)
        else:
            parts = p.parts
            if 'arrays' in parts and p.suffix == '.npz':
                omitted['arrays_npz'] += 1
            elif relative == 'docs/dsd/evidence/candidate_filter_coefficients.npz':
                # The transport explicitly omits this one independently indexed
                # historical artifact along with its 945 measured arrays.
                # Do not broaden this exemption to arbitrary missing files.
                omitted['supplemental_npz'] += 1
            elif 'graph-raw' in parts:
                omitted['graph_raw'] += 1
            elif p.suffix == '.state':
                omitted['state'] += 1
            else:
                raise InvalidEvidence('unexpected missing P00 entry: ' + relative)
    return dict(inventory_entries=len(lines), missing_expected_bulk_payloads=omitted,
                omitted_bulk_sha256_still_recorded=True,
                full_raw_replay_possible=not any(omitted.values()))


def lineage() -> dict:
    cert = load(CERT)
    binding = load(BIND)
    require(cert['decision'] == 'CERTIFIED' and cert['p10_phase'] == 'CLOSED',
            'historical P10 certification invalid')
    before = cert['input_sha256']
    mismatches = {row['path']: row for row in binding['mismatches']}
    require(set(mismatches) == CHANGED_SOURCE and len(before) == 35 and
            str(DESIGN) in before, 'P10 expected input inventory has changed')
    require(digest(DESIGN) == REVIEWED_DESIGN_SHA256 and
            digest(INTEL) == REVIEWED_INTEL_SHA256,
            'unreviewed operative design document or Intel amendment change')
    intel = inspect_amendment()
    require(intel['physical_test_execution'] == 'UNRUN', 'Intel scope changed')
    intact, changed = [], []
    for path, old in before.items():
        actual = digest(Path(path))
        if old == actual:
            intact.append(path)
        elif path in CHANGED_SOURCE:
            row = mismatches[path]
            require(row['certificate_sha256'] == old and
                    row['supplied_baseline_sha256'] != old,
                    'unexplained post-P10 executable lineage: ' + path)
            changed.append(dict(path=path, p10_sha256=old,
                                post_p10_binding_sha256=row['supplied_baseline_sha256'],
                                current_sha256=actual))
        elif path == str(DESIGN):
            changed.append(dict(path=path, p10_sha256=old, current_sha256=actual,
                                scope='current reviewed P15 design with Intel and v2 amendments; '
                                      'NOT a P10-certified document'))
        else:
            raise InvalidEvidence('unexpected changed P10 input: ' + path)
    require(len(intact) == 30 and len(changed) == 5,
            'P10 versioned lineage count differs')
    return dict(disposition='RECONCILED-SCOPED-NOT-RECERTIFIED',
                original_p10_certificate_sha256=digest(CERT),
                original_p10_inputs=35, byte_identical=30,
                later_executable_source_changes=4, reviewed_design_changes=1,
                current_changed_inputs=changed,
                intel_physical_performance='UNRUN-SCOPE-EXEMPT')


def matrix(folder: Path, matrix_name: str) -> dict:
    """Validate present source/cell receipts without pretending raw replay."""
    plan = make_plan(matrix_name)
    keys = {c['id']: c for c in plan['scalar_cells']}
    required = len(keys)
    pins_expected = 17 if matrix_name == 'v1' else 22
    require(len(keys) == (54 if matrix_name == 'v1' else 27),
            'matrix worklist changed')
    base_hash = {}
    missing_npz = 0
    src_active = 0
    native_fractional = 0
    graph_raw_missing = 0
    detailed = 0
    forced = 0
    for tier in TIERS:
        directory = folder / tier
        session = load(directory / 'session.json')
        worklist = load(directory / 'worklist.json')
        require(worklist == json.loads(json.dumps(plan)) and set(session['cells']) == set(keys) and
                session['mode'] == 'full' and session['frames'] == 262144 and
                session['worklist_sha256'] == hashlib.sha256(
                    json.dumps(plan, sort_keys=True).encode()).hexdigest(),
                'invalid worklist/session: ' + matrix_name + '/' + tier)
        require(session['tiers'] == (['scalar'] if tier == 'scalar' else ['scalar', tier]),
                'unexpected tiers: ' + matrix_name + '/' + tier)
        pins = session['reference_inputs']
        require(len(pins) - int('src/.libs/libsox_ng.a' in pins) == pins_expected,
                'unexpected source pin count: ' + matrix_name + '/' + tier)
        for path, expected in pins.items():
            if path != 'src/.libs/libsox_ng.a':
                require(digest(Path(path)) == expected,
                        'source hash drift: ' + matrix_name + '/' + tier + '/' + path)
        cells = ROOT / directory / 'cells'
        require({p.stem for p in cells.glob('*.json')} == set(keys),
                'missing or extra cell receipt: ' + matrix_name + '/' + tier)
        for ident, spec in keys.items():
            rel = directory / 'cells' / (ident + '.json')
            receipt_file = ROOT / rel
            require((ROOT / rel.with_suffix('.sha256')).read_text().strip() == sha(receipt_file),
                    'cell digest differs: ' + matrix_name + '/' + tier + '/' + ident)
            cell = load(rel)
            expected_frames = (262144 * spec['pcm_hz'] + spec['native_hz']//2) // spec['native_hz']
            require(cell['id'] == ident and cell['qualified'] is False and
                    cell['status'] == 'MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW' and
                    all(cell[k] == spec[k] for k in ('native_hz', 'profile', 'pcm_hz')) and
                    cell['frames_native'] == 262144 and
                    cell['output_frames_measured'] == expected_frames and
                    cell['output_count_exact'] == expected_frames,
                    'cell status/count mismatch: ' + matrix_name + '/' + tier + '/' + ident)
            raw = cell['raw_receipt']
            require(raw['file'] == 'arrays/' + ident + '.npz' and
                    len(raw['sha256']) == 64, 'missing raw array identity: ' + ident)
            raw_file = ROOT / directory / raw['file']
            if raw_file.is_file():
                require(sha(raw_file) == raw['sha256'], 'raw payload hash differs: ' + ident)
            else:
                missing_npz += 1
            src = cell['production_src_spectral']
            require(src['status'] in ('SAMPLED_PASS', 'IDENTITY_BYPASS') and
                    src['passed'] is True, 'sampled SRC failure: ' + ident)
            if src['status'] == 'SAMPLED_PASS':
                rel_src = directory / src['result_file']
                require(digest(rel_src) == src['sha256'] and
                        load(rel_src)['status'] == 'SAMPLED_PASS',
                        'SRC witness absent/corrupt: ' + ident)
            if tier == 'scalar':
                require(cell['production_graph']['status'] == 'PASS' and
                        cell['production_graph']['threaded_vs_serial_pcm_identical'] is True,
                        'graph witness missing/failed: ' + ident)
                base_hash[ident] = cell['scalar_program']['receipt']['binary64_sha256']
                src_active += int(cell['intermediate_hz'] != cell['pcm_hz'])
                native_fractional += int(cell['native_hz'] % cell['pcm_hz'] != 0)
                for entry in cell['production_graph']['raw_graph']:
                    f = ROOT / directory / entry['file']
                    if f.is_file():
                        require(sha(f) == entry['sha256'], 'graph raw hash differs: ' + ident)
                    else:
                        graph_raw_missing += 1
                require(cell['cross_isa'] == [], 'unexpected scalar forced ISA')
            else:
                require(cell['scalar_program']['receipt']['binary64_sha256'] == base_hash[ident],
                        'forced tier scalar baseline changed: ' + ident)
                variants = cell['cross_isa']
                require(len(variants) == 1 and variants[0]['tier'] == tier and
                        variants[0]['status'] == 'MEASURED' and
                        variants[0]['detailed_cross_isa'] ==
                          (cell['pcm_hz'] in CROSS_ISA_DETAIL_ENDPOINTS),
                        'forced ISA witness missing: ' + matrix_name + '/' + tier + '/' + ident)
                forced += 1
                detailed += int(variants[0]['detailed_cross_isa'])
    require((forced, detailed) == ((216, 96) if matrix_name == 'v1' else (108, 48)),
            'incomplete tier/detailed jobs')
    return dict(matrix=matrix_name, evidence_directory=str(folder),
                binding='CURRENT_SOURCE_SHA256_MATCH', source_pins_per_session=pins_expected,
                scalar_cells=required, forced_isa_jobs=forced, detailed_isa_jobs=detailed,
                graph_cells=required, sampled_src_cells=required,
                native_fractional_ratio_cells=native_fractional,
                src_active_cells=src_active, src_bypass_cells=required-src_active,
                absent_array_payloads_in_stripped_archive=missing_npz,
                absent_graph_payloads_in_stripped_archive=graph_raw_missing,
                disposition='MEASURED_SOURCE_BOUND_NOT_SPECTRALLY_QUALIFIED',
                full_raw_replay_completed=False)


def report() -> dict:
    files = inventory()
    code = lineage()
    from p15_src_envelope_review import report as src_disposition
    src_numerical = src_disposition()
    require(src_numerical['fractional_diagnostic_cases_disposed'] == 36 and
            src_numerical['integer_ratio_additional_src_cells'] == 36 and
            src_numerical['mandatory_full_chain_numeric'].startswith('OPEN') and
            src_numerical['release_status'] == 'BLOCKED',
            'unexpected SRC numerical scope/qualification')
    first = matrix(V1, 'v1')
    second = matrix(V2, 'v2')
    require((first['src_active_cells'], second['src_active_cells']) == (48, 24),
            'SRC adapter coverage expectation changed')
    earlier = load(PRIOR)
    require(earlier['release_status'] == 'BLOCKED' and
            earlier['soaks']['disposition'] == 'PASS-SCOPED' and
            earlier['soaks']['continuation_states_verified'] == 915 and
            earlier['soaks']['execution_receipts_verified'] == 15,
            'historical scoped soak qualification no longer supported')
    fir = inherited_fir_certificate('v2')
    require(fir['status'] == 'P15_R3_V2_NATIVE_FIR_CERTIFICATE_VERIFIED' and
            fir['three_profiles'] == 3 and fir['three_new_banks'] == 3,
            'v2 native FIR certificate not source-bound')
    # The R2 receipt is still reviewed, and still fails: its 20 kHz staged
    # sinc matched the passband of neither profile. It is kept because the
    # per-profile receipt supersedes it rather than erasing it.
    indexed_benchmark = inspect_benchmark()
    require(indexed_benchmark['disposition'] == 'OPEN-CONTROL-NOT-BANDWIDTH-MATCHED',
            'benchmark unexpectedly reclassified')
    # The measurement the gate asked for, with its comparator verified
    # spectrally rather than asserted from a command line. This raises on any
    # failure, so reaching the gate table at all means it holds.
    dsd256 = inspect_per_profile_benchmark()
    intel_measurement = review_intel_physical()
    require(dsd256['cells_measured'] == 4 and
            dsd256['comparisons_meeting_2x_at_ci_lower_bound'] == 8 and
            dsd256['control_bandwidth_match'] in
            ('CONTROL-EDGE-MISMATCH', 'CONTROL-FULL-PASSBAND-MATCH-VERIFIED'),
            'DSD256 per-profile matrix is not the expected 2 profiles x 2 rates x 2 controls')
    gates = [
        dict(id='P15-v1-and-v2-composite-SRC-acceptance', status='OPEN',
             evidence=[str(V1), str(V2),
                       'tests/dsd/reference/p15_src_numerical_criteria.json',
                       'tests/dsd/p15_src_envelope_review.py'],
             issue='36 fractional different-transfer residuals are diagnostic, not failures; '
                   'the further 36 integer-native-ratio cells also execute SRC. The 72 '
                   'SRC-active cells lack independent same-transfer arithmetic and '
                   'all-extrema/coherent-alias certificates; no tolerance can be fabricated.'),
        # Keep the whole guaranteed passband in scope.  A historical verifier
        # excluded its last 5% after finding a 6 dB discrepancy there.  That
        # evidence is useful but NOT a matched-comparator qualification.
        dict(id='P15-DSD256-direct-2x-and-matched-comparator',
             status=('PASS-SCOPED' if dsd256['disposition'] ==
                     'DIRECT-2X-AND-MATCHED-COMPARATOR-MEASURED' else 'OPEN'),
             evidence=['tests/dsd/results/P15_dsd256_2x_per_profile_2026-10-15/dsd256-2x.json',
                       'tests/dsd/results/P15_dsd256_2x_per_profile_2026-10-15/'
                       'dsd256-control-match.json',
                       'tests/dsd/verify_dsd256_control_match.py',
                       'tests/dsd/results/P15_matrix_metrology_R2_2026-10-14/dsd256-2x.json'],
             measured=dsd256,
             issue=('Eight timed comparisons exceed 2x at the bootstrap CI lower bound. '
                    'The original 95%-of-passband control verdict is not accepted: '
                    'the full v2 66 kHz guaranteed passband contains approximately '
                    '6 dB of decoder/control divergence at its edge. Direct speed '
                    'observation stands; the matched-control conjunct remains open. '
                    'Do not shift the passband or retroactively weaken the match rule.')),
        # Historical 2026-10-14 UNRUN-SCOPE-EXEMPT remains in the old ledger
        # and normative amendment.  A later physical run is MEASURED in this
        # new ledger, neither UNRUN nor PASS for a new dispatch preference.
        dict(id='P15-Intel-AVX512-physical-performance', status=intel_measurement['status'],
             historical_2026_10_14_status='UNRUN-SCOPE-EXEMPT',
             evidence=['docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md',
                       'tests/dsd/results/P15_intel_physical_avx512_2026-10-16'],
             measured=intel_measurement,
             issue='Physical Intel observation is now present and checked against raw '
                   'timings/source pins; no new Intel ISA preference or compatibility '
                   'claim, no change to the frozen historical UNRUN ledger.'),
        dict(id='P15-older-AVX1-physical-observation', status='PASS-SCOPED-INHERITED',
             evidence='tests/dsd/results/P15_avx1_physical_2026-10-13'),
        dict(id='P15-encoder-one-hour-soaks', status='PASS-SCOPED-INHERITED',
             evidence=str(PRIOR),
             issue='Previously verified 915 state records and 15 execution receipts; '
                   'removed .state payloads cannot be independently replayed from this archive'),
        dict(id='P15-independent-source-corpus', status='PASS-SCOPED-INHERITED',
             evidence=str(PRIOR),
             issue='Software-source-material tests, not DAC/device certification'),
    ]
    open_gates = [g['id'] for g in gates if g['status'] == 'OPEN']
    return dict(schema='P15/current-closeout-review/1', date='2026-10-16',
                input_archive_sha256='e119c315d192cb44f8abb1bf3ae61f4e30a4cef9394e5a7f089ebdecd24b5cde',
                reported_source_revision='ab7f0f56',
                transport=files, p10_lineage=code,
                matrices={'v1': first, 'v2': second},
                v2_native_fir_certificate=fir,
                src_numerical_disposition=src_numerical,
                earlier_scoped_review_sha256=digest(PRIOR),
                old_p15_manifest_unchanged_sha256=digest(RESULTS/'P15/release/release-manifest.json'),
                benchmark_r2_status=indexed_benchmark['disposition'],
                benchmark_per_profile_status=dsd256['disposition'],
                intel_physical_measurement=intel_measurement,
                dsd256_control_bandwidth_match=dsd256['control_bandwidth_match'],
                gates=gates, substantive_open_gates=open_gates,
                status='BLOCKED', p16_authorized=False, default_promotion_authorized=False,
                no_new_intel_preference=True, no_hardware_device_compatibility_claim=True,
                note='This is an indexed current-source evidence review, not re-execution of raw DSP metrology. '
                     'DSD256 direct timing is sound but the control differs materially within the '
                     'guaranteed v2 passband; the composite SRC gate also remains OPEN. Intel physical '
                     'measurements are now recorded separately from the immutable earlier UNRUN entry; '
                     'requires independent new evidence before any future promotion decision. A throughput '
                     'result authorises nothing on its own; on the evidence this review reads, release stays BLOCKED. The shipping v2 decode default was activated by operator decision on 2026-10-20, which this review does not assess.')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True,
                    help='new date-scoped JSON; earlier results are immutable')
    ap.add_argument('--require-release', action='store_true',
                    help='return 2 while release remains blocked')
    args = ap.parse_args()
    try:
        result = report()
        require(not args.output.resolve().is_relative_to((ROOT / V1).resolve()) and
                not args.output.resolve().is_relative_to((ROOT / V2).resolve()),
                'cannot write inside measured evidence')
        write_new(args.output, result)
        print(json.dumps({'status': result['status'],
                          'substantive_open_gates': result['substantive_open_gates'],
                          'output': args.output.name}, sort_keys=True))
        return 2 if args.require_release and result['status'] != 'READY' else 0
    except (InvalidEvidence, OSError, ValueError, KeyError, TypeError, AssertionError) as error:
        print('P15 current closeout INVALID: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
