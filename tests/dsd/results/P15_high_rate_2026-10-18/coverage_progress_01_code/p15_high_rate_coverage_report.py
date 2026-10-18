#!/usr/bin/env python3
"""Aggregate an immutable high-rate census with explicit proof-code snapshots.

This independently checks canonical work identities, receipt hashes, current
source/operator bindings, and the complete recorded proof-module mapping. It
does not execute a numerical proof or turn local certificates into release
qualification. Different verified proof versions may establish intervals of
the same unchanged coefficient operator; their receipts remain separate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import statistics

import p15_high_rate_census as census
from p15_full_band_campaign import bindings, canonical_plan, digest

ROOT = Path(__file__).resolve().parents[2]
PRIOR_LABEL = 'third_pass_final_local'
METRICS = ('nodes_examined', 'exact_branch_splits', 'exact_path_enumerations',
           'fir_interval_evaluations', 'cheap_difference_majorants_used',
           'interval_subdivisions', 'max_alias_path_population',
           'alias_population_operations')


def load(path):
    return json.loads(path.read_text())


def file_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def proof_snapshot(path):
    """A flat frozen snapshot is recognized by its exact complete module map."""
    identity_file = path / 'IDENTITY.json'
    identity = load(identity_file)
    code = identity.get('prover_code_sha256')
    if not isinstance(code, dict) or not code:
        raise ValueError('missing complete proof-code snapshot identity')
    for name, expected in code.items():
        if Path(name).name != name or not name.endswith('.py'):
            raise ValueError('nonlocal proof snapshot module name')
        if census.sha_file(path / name) != expected:
            raise ValueError('proof snapshot hash mismatch: ' + name)
    return dict(directory=census.relative(path), identity_sha256=census.sha_file(identity_file),
                prover_code_sha256=code)


def receipt_metrics(doc):
    cert = doc['certificate']
    measured = doc.get('measurement', {})
    return dict(status=cert['status'], reason=cert.get('reason'),
                elapsed_s=measured.get('elapsed_s'), cpu_s=measured.get('cpu_s'),
                peak_rss_kib=measured.get('peak_rss_kib'),
                counters={key: cert.get(key) for key in METRICS})


def complete_cover(jobs, witnesses):
    """Require every named canonical job and exact gap-free rational coverage."""
    if any(digest(job) not in witnesses for job in jobs):
        return None
    bands = {}
    for mode in ('pass', 'stop'):
        selected = sorted((job for job in jobs if job['mode'] == mode),
                          key=lambda j: Fraction(j['lo']))
        if not selected:
            raise ValueError('complete cell is missing a normative band')
        expected_end = (Fraction(selected[0]['effective_p']) if mode == 'pass'
                        else Fraction(selected[0]['output_hz'], 2))
        cursor = Fraction(0)
        bound = []
        for job in selected:
            lo, hi = Fraction(job['lo']), Fraction(job['hi'])
            if lo != cursor or hi < lo:
                raise ValueError('canonical cell frequency gap/overlap')
            cursor = hi
            bound.append(dict(lo=job['lo'], hi=job['hi'], work_sha256=digest(job),
                              witness=witnesses[digest(job)]))
        if cursor != expected_end:
            raise ValueError('canonical cell does not reach its normative upper edge')
        bands[mode] = dict(lower_hz='0', upper_hz=census.freqstr(expected_end),
                           canonical_intervals=len(bound), intervals=bound)
    return bands


def matched_pair(baseline, candidate):
    """Only uncensored PASS/PASS timings receive a numerical speedup ratio."""
    a, b = baseline['doc'], candidate['doc']
    ia, ib = a['experiment_identity'], b['experiment_identity']
    for key in ('job', 'binding', 'stage_snapshot_sha256',
                'verified_operator_binding_sha256', 'resources',
                'harness_sha256', 'profiling_enabled'):
        if ia.get(key) != ib.get(key):
            raise ValueError('unmatched experiment identity: ' + key)
    ea, eb = a['measurement']['environment'], b['measurement']['environment']
    for key in ('python', 'executable', 'platform', 'mpmath', 'numpy',
                'affinity', 'openblas_num_threads'):
        if ea.get(key) != eb.get(key):
            raise ValueError('unmatched experiment environment: ' + key)
    ma, mb = receipt_metrics(a), receipt_metrics(b)
    both_pass = ma['status'].startswith('PASS') and mb['status'].startswith('PASS')
    speedup = ma['elapsed_s'] / mb['elapsed_s'] if both_pass else None
    return dict(job=a['job'], baseline=dict(receipt=baseline['reference'], **ma),
                candidate=dict(receipt=candidate['reference'], **mb),
                speedup_if_both_pass=speedup,
                timing_scope='Complete certificate call; startup excluded; timeout timings are censored')


def observed_state(records):
    if not records:
        return 'UNMEASURED'
    return 'PASS' if any(r['doc']['certificate']['status'].startswith('PASS')
                         for r in records) else 'OPEN'


def generate(census_dir, output, proof_roots, required_plans, matched_labels,
             candidate_labels, *, allow_partial=False):
    summary = load(census_dir / 'summary.json')
    if summary.get('census_code_sha256') != census.sha_file(Path(census.__file__)):
        raise ValueError('regenerate the final census with the current binding validator')
    for line in (census_dir / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        if Path(name).name != name or census.sha_file(census_dir / name) != expected:
            raise ValueError('census manifest mismatch')
    rows = [json.loads(line) for line in (census_dir / 'intervals.jsonl').read_text().splitlines()]
    jobs = canonical_plan()
    current_binding = bindings()
    if len(rows) != len(jobs) or len(jobs) != 11516:
        raise ValueError('not a complete canonical census')
    if summary['source_identity'] != current_binding['source'] or summary['design_sha256'] != current_binding['design']:
        raise ValueError('census does not bind the current unchanged source/design')
    by_hash = {digest(job): job for job in jobs}
    snapshots = {label: proof_snapshot(path) for label, path in proof_roots.items()}
    records = defaultdict(dict)
    original_pass = set()
    prior_pass = set()
    current_pass = set()
    candidate_pass = set()
    original_open = set()
    for index, (row, job) in enumerate(zip(rows, jobs)):
        work = digest(job)
        if row['canonical_index'] != index or row['job'] != job or row['work_sha256'] != work:
            raise ValueError('census canonical index/job mismatch')
        if row['original']['status'].startswith('PASS'):
            original_pass.add(work)
            prior_pass.add(work)
        else:
            original_open.add(work)
        for label, observations in row['observations'].items():
            if label.startswith('historical_') or label == PRIOR_LABEL:
                if any(o['status'].startswith('PASS') for o in observations):
                    prior_pass.add(work)
                continue
            if label not in snapshots:
                raise ValueError('unrecognized proof snapshot for measurement label: ' + label)
            if len(observations) != 1:
                raise ValueError('one version/budget per measurement label required')
            observation = observations[0]
            path = file_path(observation['path'])
            if census.sha_file(path) != observation['sha256']:
                raise ValueError('receipt changed after census publication')
            doc = load(path)
            if census.validate_overlay(doc, by_hash, current_binding) != work:
                raise ValueError('receipt belongs to another canonical interval')
            if doc.get('prover_code_sha256') != snapshots[label]['prover_code_sha256']:
                raise ValueError('receipt proof modules do not match recognized complete snapshot')
            if doc.get('canonical_work_index') != index:
                raise ValueError('experiment canonical work index mismatch')
            if doc['certificate']['status'].startswith('PASS') and (
                doc['certificate'].get('governing_stopband_hz') != job['source_s'] or
                doc['certificate'].get('limits') != {'passband_db': '0.0001', 'coherent_alias_db': '-160'}
            ):
                raise ValueError('experiment changed normative spectral obligations')
            reference = dict(path=observation['path'], sha256=observation['sha256'], label=label)
            records[label][work] = dict(doc=doc, reference=reference)
            if doc['certificate']['status'].startswith('PASS'):
                current_pass.add(work)
                if label in candidate_labels:
                    candidate_pass.add(work)

    plan_status = {}
    for label, path in required_plans.items():
        plan = load(path)
        indices = plan.get('job_indices')
        if (not isinstance(indices, list) or len(indices) != len(set(indices)) or
                any(type(i) is not int or not 0 <= i < len(jobs) for i in indices)):
            raise ValueError('invalid declared experiment plan')
        expected = {digest(jobs[i]) for i in indices}
        actual = set(records[label])
        missing, unexpected = expected - actual, actual - expected
        plan_status[label] = dict(plan=census.relative(path), plan_sha256=census.sha_file(path),
                                  expected=len(expected), observed=len(actual),
                                  missing_work_sha256=sorted(missing), unexpected_work_sha256=sorted(unexpected))
        if unexpected or (missing and not allow_partial):
            raise ValueError('selected plan is incomplete or has unexpected jobs: ' + label)

    candidates = defaultdict(list)
    baselines = defaultdict(list)
    for label, items in records.items():
        destination = candidates if label in candidate_labels else baselines
        for work, record in items.items():
            destination[work].append(record)
    classifications = []
    for row in rows:
        work = row['work_sha256']
        candidate, baseline = candidates[work], baselines[work]
        states = []
        if not candidate and not baseline:
            states.append('current_run_unmeasured')
        if any(r['doc']['certificate']['status'].startswith('PASS') for r in baseline):
            states.append('third_pass_baseline_certified_in_observed_budget')
        if work in candidate_pass and work in original_open:
            states.append('candidate_certifies_original_open')
        if work in candidate_pass and work not in prior_pass:
            states.append('candidate_certifies_beyond_prior_receipts_included_here')
        short_open = any(r['doc']['certificate']['status'] == 'OPEN' and
                         r['doc']['experiment_identity']['resources']['seconds'] <= 60
                         for r in candidate)
        longer_pass = any(r['doc']['certificate']['status'].startswith('PASS') and
                          r['doc']['experiment_identity']['resources']['seconds'] > 60
                          for r in candidate)
        if short_open and longer_pass:
            states.append('observed_60s_open_resolved_by_larger_budget')
        reason_counts = Counter(r['doc']['certificate'].get('reason') for r in candidate
                                if r['doc']['certificate']['status'] == 'OPEN')
        if observed_state(candidate) == 'OPEN':
            states.append('current_candidate_open_cause_unresolved')
        classifications.append(dict(canonical_index=row['canonical_index'], work_sha256=work,
            job=row['job'], original_status=row['original']['status'], original_reason=row['original']['reason'],
            candidate_state=observed_state(candidate), baseline_state=observed_state(baseline),
            classification=states, observed_candidate_open_reasons=dict(reason_counts),
            complete_path_count=row['complete_path_count'],
            stationary_piece_count=len(row['exact_stationary_piece_widths_hz']),
            effort_estimate=row['estimated_effort'],
            cause_limit='Timeouts alone establish neither a mathematical violation nor a loose-bound obstruction'))

    witnesses = {}
    for work, items in candidates.items():
        passing = sorted((r['reference'] for r in items if r['doc']['certificate']['status'].startswith('PASS')),
                         key=lambda r: (r['label'], r['sha256']))
        if passing:
            witnesses[work] = passing[0]
    grouped = defaultdict(list)
    for job in jobs:
        grouped[job['cell_id']].append(job)
    cell_rows = []
    complete_cells = {}
    union = prior_pass | current_pass
    for cell, cell_jobs in grouped.items():
        work = {digest(j) for j in cell_jobs}
        measured = {w for w in work if candidates[w]}
        bounds = complete_cover(cell_jobs, witnesses)
        if bounds is not None:
            complete_cells[cell] = dict(qualified_release=False, bands=bounds,
                canonical_work_sha256=digest([digest(j) for j in cell_jobs]),
                source_binding=current_binding,
                scope='Exhaustive local ideal-coefficient canonical coverage; independent release obligations remain')
        cell_rows.append(dict(cell_id=cell, canonical_intervals=len(work),
            canonical_pass=sum(j['mode'] == 'pass' for j in cell_jobs),
            canonical_stop=sum(j['mode'] == 'stop' for j in cell_jobs),
            original_pass=len(work & original_pass), original_open=len(work - original_pass),
            candidate_measured=len(measured), candidate_pass=len(work & candidate_pass),
            candidate_open_without_any_pass=len(measured - candidate_pass),
            candidate_unmeasured=len(work - measured),
            newly_certified_candidate_vs_original=len((work & candidate_pass) - original_pass),
            cumulative_explicit_evidence_pass=len(work & union),
            complete_candidate_cell=bounds is not None))

    pair_results = {}
    for baseline_label, candidate_label in matched_labels:
        common = sorted(set(records[baseline_label]) & set(records[candidate_label]),
                        key=lambda w: jobs.index(by_hash[w]))
        pair_results[baseline_label + ':' + candidate_label] = [
            matched_pair(records[baseline_label][w], records[candidate_label][w]) for w in common]
    label_statistics = {}
    for label, entries in sorted(records.items()):
        docs = [r['doc'] for r in entries.values()]
        count = Counter(d['certificate']['status'] for d in docs)
        cpu = sum(d['measurement']['cpu_s'] for d in docs)
        passed = sum(d['certificate']['status'].startswith('PASS') for d in docs)
        label_statistics[label] = dict(receipts=len(docs), statuses=dict(count),
            sum_certificate_cpu_s=cpu, sum_certificate_wall_s=sum(d['measurement']['elapsed_s'] for d in docs),
            peak_rss_kib=max((d['measurement']['peak_rss_kib'] for d in docs), default=None),
            passing_certificates_per_cpu_hour=passed * 3600 / cpu if cpu else None)
    result = dict(schema='P15/high-rate-coverage-report/1', qualified_release=False, release='BLOCKED',
        status='IN_PROGRESS' if any(v['missing_work_sha256'] for v in plan_status.values()) else 'SELECTED_PLANS_RECORDED',
        canonical_intervals=len(jobs), original_pass=len(original_pass),
        prior_pass_included_here=len(prior_pass), current_unique_pass=len(current_pass),
        current_pass_new_vs_original=len(current_pass - original_pass),
        current_pass_new_vs_included_prior=len(current_pass - prior_pass),
        candidate_unique_pass=len(candidate_pass), candidate_pass_new_vs_original=len(candidate_pass - original_pass),
        original_plus_current_pass=len(original_pass | current_pass),
        cumulative_explicit_evidence_pass=len(union), cumulative_remaining=len(jobs) - len(union),
        complete_candidate_cells=sorted(complete_cells), plans=plan_status,
        proof_snapshots=snapshots, label_statistics=label_statistics,
        census_summary_sha256=census.sha_file(census_dir / 'summary.json'),
        report_code_sha256=census.sha_file(Path(__file__)),
        historical_accounting='Prior means original 60s receipts + historical 600s sample + four third-pass final locals; no claim to inventory every historical proof in repository',
        source_binding=current_binding,
        verification_scope='Canonical coverage, receipt SHA, source/operator binding, complete frozen proof-code map, matched timing environment; not independent recomputation of the numerical inequalities')
    text = human_report(result, cell_rows, pair_results, classifications)
    files = {'SUMMARY.json': census.encoded(result), 'CELL_COVERAGE.json': census.encoded(cell_rows),
             'COMPLETE_CELL_WITNESSES.json': census.encoded(complete_cells),
             'MATCHED_BENCHMARKS.json': census.encoded(pair_results),
             'CLASSIFICATION.jsonl': b''.join((json.dumps(x, sort_keys=True, separators=(',', ':')) + '\n').encode() for x in classifications),
             'COVERAGE_REPORT.md': text.encode()}
    for name, data in files.items():
        census.publish(output / name, data)
    census.publish(output / 'SHA256SUMS', ''.join(
        f'{sha256(data).hexdigest()}  {name}\n' for name, data in sorted(files.items())).encode())
    return result


def human_report(result, cells, pairs, classifications):
    lines = ['# P15 high-rate coverage report', '',
             f"**Snapshot status: {result['status']}. P15 remains BLOCKED.**", '',
             f"The explicitly selected current runs contain **{result['current_unique_pass']} distinct canonical local passes**. Of these, **{result['current_pass_new_vs_original']}** were OPEN in the original 60-second campaign. The exact union of the original 6,835 passes and these current passes is **{result['original_plus_current_pass']} / 11,516**.", '',
             f"Including the historical 600-second sample and four third-pass final local receipts produces **{result['cumulative_explicit_evidence_pass']} / 11,516** explicitly covered intervals. This is a separate evidence union: **{result['current_pass_new_vs_included_prior']}** current passes are beyond those prior receipts. Historical receipts retain their original status.", '',
             '## Difficult cells', '',
             '| Cell | Canonical pass + stop | Original OPEN | Candidate PASS | Candidate OPEN | Unmeasured | Complete candidate cover |',
             '|---|---:|---:|---:|---:|---:|---|']
    for c in cells:
        if not (c['cell_id'].endswith('pcm384000') or
                c['cell_id'].startswith('dsd256.') and c['cell_id'].endswith('pcm192000')):
            continue
        lines.append(f"| {c['cell_id']} | {c['canonical_pass']} + {c['canonical_stop']} | {c['original_open']} | {c['candidate_pass']} | {c['candidate_open_without_any_pass']} | {c['candidate_unmeasured']} | {'yes' if c['complete_candidate_cell'] else 'no'} |")
    lines += ['', 'Candidate OPEN means at least one candidate attempt exists and none of the included candidate versions/budgets supplied a PASS. Unmeasured intervals have no candidate attempt in this snapshot. Neither classification establishes a spectral violation.', '', '## Complete-cell evidence', '']
    if result['complete_candidate_cells']:
        for name in result['complete_candidate_cells']:
            c = next(c for c in cells if c['cell_id'] == name)
            lines.append(f"- **{name}: {c['canonical_intervals']} / {c['canonical_intervals']} canonical intervals**, comprising {c['canonical_pass']} passband and {c['canonical_stop']} native-source-stop intervals.")
        lines += ['', '`COMPLETE_CELL_WITNESSES.json` names every canonical interval and immutable receipt hash, verifies exact shared endpoints from DC to each required upper edge, and binds the unchanged source. Local proofs from different recognized proof snapshots may cover the same unchanged coefficient operator. This is ideal-coefficient spectral coverage; FFT4G arithmetic and release adjudication remain separate.']
    else:
        lines.append('No complete candidate cell is claimed in this snapshot. Remaining canonical intervals remain explicitly unproved or unmeasured.')
    lines += ['', '## Matched complete-prover performance', '']
    for name, entries in pairs.items():
        usable = [p for p in entries if p['speedup_if_both_pass'] is not None]
        speedups = [p['speedup_if_both_pass'] for p in usable]
        baseline_pass = sum(p['baseline']['status'].startswith('PASS') for p in entries)
        candidate_pass = sum(p['candidate']['status'].startswith('PASS') for p in entries)
        lines.append(f"### {name}")
        lines += ['', f"{len(entries)} matched observations: baseline {baseline_pass} PASS, candidate {candidate_pass} PASS. Inputs, operator hashes, harness, budgets, CPU affinity, Python, and numerical-library versions are checked for each pair.", '']
        if speedups:
            lines.append(f"Across {len(speedups)} PASS/PASS pairs, the geometric mean complete-prover speedup is **{statistics.geometric_mean(speedups):.3f}×**, ranging from {min(speedups):.3f}× to {max(speedups):.3f}×. Ratios below 1 are measured regressions. Timeout results are censored and excluded from this ratio.")
        lines += ['', '| Cell / band / interval (Hz) | Baseline s | Candidate s | Ratio | Outcome |', '|---|---:|---:|---:|---|']
        for p in entries:
            j = p['job']; a = p['baseline']; b = p['candidate']
            ratio = 'censored' if p['speedup_if_both_pass'] is None else f"{p['speedup_if_both_pass']:.3f}×"
            lines.append(f"| {j['cell_id']} / {j['mode']} / {j['lo']}–{j['hi']} | {a['elapsed_s']:.3f} | {b['elapsed_s']:.3f} | {ratio} | {a['status']} → {b['status']} |")
        lines.append('')
    classes = Counter(category for row in classifications for category in row['classification'])
    reasons = Counter()
    for row in classifications:
        if row['candidate_state'] == 'OPEN':
            reasons.update(row['observed_candidate_open_reasons'])
    lines += ['## What prevents remaining certification', '',
        f"The observed classification matrix contains {classes['third_pass_baseline_certified_in_observed_budget']} intervals certified by the third-pass baseline within the explicitly recorded budgets, and {classes['observed_60s_open_resolved_by_larger_budget']} intervals with a 60-second candidate OPEN followed by a larger-budget PASS.", '',
        f"For intervals still candidate-OPEN, recorded attempt reasons are: `{json.dumps(dict(reasons), sort_keys=True)}`. These counts describe attempts; repeated budgets can contribute more than one reason to an interval.", '',
        'The structural census separates path population from routing density. DSD256 mastering at 384 kHz has 9,408 complete paths and routing transitions every 600 Hz. DSD64 at 384 kHz has 4,704 paths, three SRC stages, and transitions every 300 Hz. DSD256 wideband at 192 kHz has 9,408 paths for 4,704 source families; multiplicity is retained.', '',
        'FIR evaluation counts, finite-difference uses, alias-frontier operations, proof nodes, subdivisions, wall time, CPU time, and memory are retained in raw receipts and matched results. Missing baseline instrumentation is reported as null. The structural effort estimate is a work proxy, not a runtime prediction.', '',
        'Remaining timeouts do not by themselves distinguish repeated numerical work, a conservative bound, path expansion, or a true envelope violation. No included receipt is a source-bound violation witness. Exact stop-membership crossings are also distinct from routing crossings; their presence alone does not prove that splitting them would resolve an OPEN.', '',
        '## Reproduction and interpretation', '',
        'Every current receipt is checked against an explicitly named complete frozen proof-code snapshot. Flat snapshots must be overlaid onto an extracted source repository for numerical replay; importing them as standalone repositories would change source-root resolution. Existing canonical receipts are never overwritten.', '',
        'The accounting code verifies coverage and provenance. It does not recompute the interval arithmetic. Independent numerical replays and correctness tests are separate evidence. P15 remains BLOCKED until its independent production-arithmetic and release obligations are discharged.', '']
    return '\n'.join(lines)


def assignments(values):
    result = {}
    for item in values:
        if '=' not in item:
            raise ValueError('expected LABEL=PATH')
        label, value = item.split('=', 1)
        if not label or label in result:
            raise ValueError('missing or duplicate label')
        result[label] = Path(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proof-root', action='append', default=[], metavar='LABEL=FLAT_SNAPSHOT')
    parser.add_argument('--required-plan', action='append', default=[], metavar='LABEL=PLAN_JSON')
    parser.add_argument('--candidate-label', action='append', default=[])
    parser.add_argument('--matched', action='append', default=[], metavar='BASELINE_LABEL:CANDIDATE_LABEL')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    matched = [tuple(value.split(':')) for value in args.matched]
    if any(len(pair) != 2 for pair in matched):
        parser.error('--matched requires BASELINE_LABEL:CANDIDATE_LABEL')
    result = generate(args.census, args.output, assignments(args.proof_root),
        assignments(args.required_plan), matched, set(args.candidate_label), allow_partial=args.allow_partial)
    print(json.dumps({k: result[k] for k in ('status', 'current_unique_pass',
        'current_pass_new_vs_original', 'cumulative_explicit_evidence_pass', 'complete_candidate_cells')}, sort_keys=True))


if __name__ == '__main__':
    main()
