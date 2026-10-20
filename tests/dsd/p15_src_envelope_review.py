#!/usr/bin/env python3
"""Source-bound, read-only P15 SRC numerical comparator disposition.

The historical cells compare production SRC with a DIFFERENT polyphase filter;
those residuals do not admit an arithmetic-error threshold. Apply the
normative §8.6.1 out-of-scope decision to all 36 native/PCM fractional cells,
inspect the 36 additional SRC-active integer-ratio cells, and explicitly keep
same-transfer arithmetic/composite spectral acceptance OPEN. No raw replay,
previous evidence overwrite, or new production DSP behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from p15_matrix_contract import make_plan, REQUIRED_TIERS
from p15_readjudication import write_new

ROOT = Path(__file__).resolve().parents[2]
CRITERIA = Path('tests/dsd/reference/p15_src_numerical_criteria.json')
DESIGN = Path('docs/dsd/DSD_DESIGN.md')
SCHEMA = 'P15/src-numerical-disposition/1'
PLACEHOLDER = 'REQUIRES_SEPARATE_NUMERICAL_ENVELOPE'
REFERENCE = 'independently-designed-rational-polyphase-kaiser-sinc'
EXPECTED = {'v1': (54, 24, 48), 'v2': (27, 12, 24)}


class InvalidEvidence(ValueError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidEvidence(message)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for buf in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def read(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def metric(row: dict, name: str) -> dict:
    """Reject NaN, negatives, impossible summary consistency and silent omissions."""
    check(isinstance(row, dict), name + ': missing metric')
    fields = ('first_abs', 'last_abs', 'interior_max_abs', 'max_abs', 'rms_abs', 'ref_peak')
    for k in fields:
        n = row.get(k)
        check(type(n) in (int, float) and math.isfinite(n) and n >= 0,
              name + ': invalid ' + k)
    frames = row.get('frames')
    check(type(frames) is int and frames >= 0, name + ': invalid frames')
    check(all(row[k] <= row['max_abs'] + 1e-14 for k in
              ('first_abs', 'last_abs', 'interior_max_abs', 'rms_abs')),
          name + ': inconsistent absolute metric')
    if not frames:
        check(all(row[k] == 0 for k in fields), name + ': nonzero empty metric')
    return row


def same_operator_threshold(*, n_ops: int, weighted_input_abs: float,
                            coefficient_error_abs: float, other_error_abs: float,
                            native_fir_propagated_abs: float) -> float:
    """Evaluate the exact §8.6.1 forward-error expression for a bound witness.

    This computation alone cannot prove an N_ops audit, transfer identity, or
    that its input quantities were derived independently. It must never be
    used as a gate on unlike-transfer existing P15 metrics.
    """
    u = 2.0 ** -53
    check(type(n_ops) is int and 0 <= n_ops < 2 ** 53,
          'invalid/unbounded N_ops')
    values = (weighted_input_abs, coefficient_error_abs,
              other_error_abs, native_fir_propagated_abs)
    check(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values),
          'missing/nonfinite/negative bound term')
    term = (n_ops * u) / (1.0 - n_ops * u) * weighted_input_abs
    total = math.fsum((term, coefficient_error_abs, other_error_abs,
                       native_fir_propagated_abs))
    check(math.isfinite(total), 'nonfinite numerical bound')
    return total


def verify_cell(directory: Path, ident: str, spec: dict, tier: str,
                src_clock: int | None = None) -> dict:
    relative = directory / tier / 'cells' / (ident + '.json')
    path = ROOT / relative
    check(path.is_file() and path.with_suffix('.sha256').is_file(),
          'missing cell or digest: ' + str(relative))
    check(path.with_suffix('.sha256').read_text().strip() == sha(path),
          'cell record hash mismatch: ' + str(relative))
    row = read(relative)
    check(row.get('id') == ident and row.get('qualified') is False and
          row.get('status') == 'MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW',
          'cell identity/status invalid: ' + str(relative))
    check(all(row.get(k) == spec[k] for k in ('native_hz', 'pcm_hz', 'profile')),
          'worklist cell mismatch: ' + str(relative))
    intermediate = row.get('intermediate_hz')
    check(type(intermediate) is int and intermediate > 0 and
          (src_clock is None or src_clock == intermediate),
          'intermediate clock drift: ' + str(relative))
    expected = (row['frames_native'] * spec['pcm_hz'] + spec['native_hz']//2)//spec['native_hz']
    check(row['frames_native'] == 262144 and
          row['output_frames_measured'] == row['output_count_exact'] == expected,
          'output count drift: ' + str(relative))
    check(row.get('raw_receipt', {}).get('file') == 'arrays/' + ident + '.npz' and
          isinstance(row['raw_receipt'].get('sha256'), str) and
          len(row['raw_receipt']['sha256']) == 64,
          'missing raw identity: ' + str(relative))
    payload = ROOT / directory / tier / row['raw_receipt']['file']
    if payload.is_file():
        check(sha(payload) == row['raw_receipt']['sha256'],
              'raw array hash mismatch: ' + str(relative))
    return row


def inspect_matrix(revision: str, folder: Path) -> dict:
    """Read, but never modify, the five pinned measured sessions and cell rows."""
    plan = make_plan(revision)
    worklist = {s['id']: s for s in plan['scalar_cells']}
    cells_total, fractional_total, src_total = EXPECTED[revision]
    check(len(worklist) == cells_total, 'matrix scalar worklist changed: ' + revision)
    pins = 17 if revision == 'v1' else 22
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    for tier in REQUIRED_TIERS:
        session = read(folder / tier / 'session.json')
        check(session.get('worklist_sha256') == plan_hash and
              read(folder / tier / 'worklist.json') == json.loads(json.dumps(plan)),
              'plan/source worklist changed: ' + revision + '/' + tier)
        check(set(session['cells']) == set(worklist) and session['frames'] == 262144 and
              session['mode'] == 'full' and
              session['tiers'] == (['scalar'] if tier == 'scalar' else ['scalar',tier]) and
              len(session['reference_inputs']) - int('src/.libs/libsox_ng.a' in session['reference_inputs']) == pins,
              'session binding invalid: ' + revision + '/' + tier)
        for relative, digest in session['reference_inputs'].items():
            if relative != 'src/.libs/libsox_ng.a':
                check(sha(ROOT / relative) == digest,
                      'measured session source differs: ' + relative)
        # All tier recordings must reference the exact planned grid, rather
        # than a plausible but unrelated ID list or a post-hoc cherry-pick.
        check(sha(ROOT / folder / tier / 'worklist.json') ==
              sha(ROOT / folder / 'scalar' / 'worklist.json'),
              'session worklist mismatch: ' + revision + '/' + tier)

    result = []
    fractional = src_active = true_bypass = native_integer_src = 0
    fir_scoped_pass = 0
    max_fractional_residual = 0.0
    missing_raw = 0
    cross_isa = 0
    for ident, spec in sorted(worklist.items()):
        row = verify_cell(folder, ident, spec, 'scalar')
        is_src = row['intermediate_hz'] != row['pcm_hz']
        fractional_reference = row['native_hz'] % row['pcm_hz'] != 0
        check(row['reference_type'] == spec['reference_type'],
              'historical comparator label changed: ' + ident)
        scalar = metric(row['scalar_program']['metric'], ident + '/scalar')
        fir = metric(row['isolated_fir']['metric'], ident + '/fir')
        bound = row['isolated_fir']['roundoff_bound']
        check(type(bound) in (int,float) and math.isfinite(bound) and bound > 0,
              'missing/invalid native FIR bound: ' + ident)
        check(fir['max_abs'] <= bound,
              'isolated native FIR exceeds its existing numerical bound: ' + ident)
        check(row['production_src_spectral']['passed'] is True and
              row['production_src_spectral']['status'] == ('SAMPLED_PASS' if is_src else 'IDENTITY_BYPASS'),
              'sampled SRC receipt failed/incorrect bypass: ' + ident)
        raw = ROOT / folder / 'scalar' / row['raw_receipt']['file']
        missing_raw += int(not raw.is_file())
        if fractional_reference:
            check(is_src, 'fractional native/output ratio unexpectedly bypasses SRC: ' + ident)
            fractional += 1
        if is_src:
            src_active += 1
            check(row['src_reference']['type'] == REFERENCE and
                  row['properties']['combined_fractional_src_error'] ==
                  'MEASURED_REQUIRES_ADJUDICATED_ENVELOPE',
                  'different-transfer comparator identity or pending status changed: ' + ident)
            if not fractional_reference:
                native_integer_src += 1
            if fractional_reference:
                max_fractional_residual = max(max_fractional_residual, scalar['max_abs'])
            status = 'DIAGNOSTIC_DIFFERENT_TRANSFER; NUMERICAL_OPERATOR_CERTIFICATE_OPEN'
        else:
            true_bypass += 1
            check(row['src_reference']['type'] == 'identity' and
                  scalar['max_abs'] <= bound,
                  'bypass scalar FIR vs independent reference exceeds FIR bound: ' + ident)
            fir_scoped_pass += 1
            status = 'PASS_SCOPED_FIR_NUMERICAL; COMPOSITE_TRANSFER_STILL_OPEN'
        result.append(dict(id=ident, cell_sha256=sha(ROOT / folder / 'scalar' / 'cells' / (ident + '.json')),
                           src_active=is_src, native_pcm_fractional=fractional_reference,
                           comparator='DIFFERENT_TRANSFER' if is_src else 'IDENTITY_FIR',
                           absolute_difference_max_observed=scalar['max_abs'],
                           recorded_first_abs=scalar['first_abs'],
                           recorded_last_abs=scalar['last_abs'], status=status))
        for tier in REQUIRED_TIERS[1:]:
            other = verify_cell(folder, ident, spec, tier, row['intermediate_hz'])
            check(len(other['cross_isa']) == 1 and other['cross_isa'][0].get('tier') == tier,
                  'missing/duplicate same-cell ISA receipt: ' + ident + '/' + tier)
            comp = other['cross_isa'][0]
            check(comp.get('composite_tolerance') == PLACEHOLDER and
                  comp.get('count_and_chunk_invariant') is True and
                  comp.get('status') == 'MEASURED',
                  'cross-ISA residual incorrectly qualified: ' + ident + '/' + tier)
            measured = metric(comp['same_cell_scalar_composite'], ident + '/' + tier + '/same-scalar')
            check(measured['frames'] == row['output_frames_measured'],
                  'cross-ISA output length mismatch: ' + ident + '/' + tier)
            # This observed same-transfer comparison is informative, but the
            # historical placeholder correctly does NOT assert a full-chain
            # high-precision arithmetic certificate.
            cross_isa += 1
    check((len(result), fractional, src_active, true_bypass, native_integer_src,
           fir_scoped_pass, cross_isa) ==
          (cells_total, fractional_total, src_total, cells_total-src_total,
           src_total-fractional_total, cells_total-src_total, cells_total*4),
          'matrix partition/count mismatch: ' + revision)
    return dict(schema='P15/src-matrix-disposition/1', revision=revision,
                evidence_directory=str(folder), source_pins_per_session=pins,
                total_scalar_cells=len(result), native_fractional_diagnostic_cells=fractional,
                src_active_cells=src_active, integer_native_pcm_ratio_but_src_active=native_integer_src,
                true_src_identity_bypass_cells=true_bypass,
                scoped_fir_numerical_pass_cells=fir_scoped_pass,
                inspected_forced_isa_comparisons=cross_isa,
                omitted_npz_payloads=missing_raw,
                observed_fractional_max_abs_not_a_tolerance=max_fractional_residual,
                full_src_same_transfer_numerical_status='OPEN',
                independent_composite_extrema_alias_status='OPEN',
                cells=result)


def report() -> dict:
    criteria = read(CRITERIA)
    check(criteria.get('schema') == 'P15/src-numerical-disposition-criteria/1' and
          criteria['policy']['different_transfer_samplewise_disposition'] ==
          'DIAGNOSTIC_NOT_AN_ACCEPTANCE_THRESHOLD', 'unrecognized criteria')
    design = (ROOT / DESIGN).read_text(encoding='utf-8')
    check('### 8.6.1 P15 full-chain SRC numerical acceptance' in design and
          'There is **no valid' in design and 'gamma(N_ops[n])' in design,
          'design numerical authority missing/changed')
    results = {}
    for revision in ('v1', 'v2'):
        folder = Path(criteria['expected_source_bound_sessions'][revision])
        check(not folder.is_absolute() and '..' not in folder.parts,
              'unsafe evidence locator')
        results[revision] = inspect_matrix(revision, folder)
    check(sum(results[r]['native_fractional_diagnostic_cells'] for r in results) == 36,
          'fractional count mismatch')
    check(sum(results[r]['src_active_cells'] for r in results) == 72,
          'SRC-use count mismatch')
    return dict(schema=SCHEMA, date='2026-10-15',
                criteria_file=str(CRITERIA), criteria_sha256=sha(ROOT / CRITERIA),
                normative_design_file=str(DESIGN), design_sha256=sha(ROOT / DESIGN),
                disposition='DIFFERENT_TRANSFER_RESIDUAL_OUT_OF_SCOPE',
                fractional_diagnostic_cases_disposed=36,
                integer_ratio_additional_src_cells=36,
                identity_fir_numerical_cases_accepted_scoped=9,
                source_bound_scalar_cells=81, cross_isa_observations_inspected=324,
                matrices=results,
                mandatory_full_chain_numeric='OPEN_MISSING_INDEPENDENT_EFFECTIVE_SRC_OPERATOR',
                mandatory_composite_response='OPEN_MISSING_CERTIFIED_EXTREMA_AND_COHERENT_ALIASES',
                release_status='BLOCKED', default_promotion_authorized=False,
                p16_authorized=False,
                note='Diagnostic comparison disposed without a made-up threshold. '
                     'The existing cells lack a complete independent same-transfer SRC oracle '
                     'and independently bounded complete-chain transfer; no release PASS claim.')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True,
                    help='new additive result file, not an existing session cell')
    ap.add_argument('--require-qualified', action='store_true',
                    help='exit 2 if mandatory first-release proof remains open')
    args = ap.parse_args()
    try:
        target = args.output.resolve()
        for folder in ('P15_v1_matrix_rebound_2026-10-20',
                       'P15_v2_matrix_rebound_2026-10-20',
                       'P15_v1_matrix_rebound_2026-10-15',
                       'P15_v2_matrix_2026-10-15'):
            check(not target.is_relative_to((ROOT / 'tests/dsd/results' / folder).resolve()),
                  'cannot write into historical measurement directory')
        outcome = report()
        write_new(args.output, outcome)  # bytes remain immutable on a rerun
        print(json.dumps(dict(release=outcome['release_status'],
                              fractional_diagnostic=outcome['fractional_diagnostic_cases_disposed'],
                              src_active=72, output=args.output.name),sort_keys=True))
        return 2 if args.require_qualified else 0
    except (InvalidEvidence, OSError, TypeError, ValueError, KeyError,
            AttributeError, AssertionError) as e:
        print('P15 SRC disposition INVALID: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
