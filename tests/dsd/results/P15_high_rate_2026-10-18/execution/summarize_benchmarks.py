#!/usr/bin/env python3
"""Summarize matched, immutable experiment receipts without extrapolating OPENs.

Numerical receipt admission and canonical coverage are verified separately by
the high-rate census and complete-cell verifier. This report checks the paired
experimental controls, binds every raw receipt, and reports observed timings.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics


def load(directory):
    found = {}
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            raise ValueError('linked experiment receipt')
        raw = path.read_bytes()
        doc = json.loads(raw)
        if 'experiment_identity' not in doc:
            raise ValueError('not an experiment receipt: ' + str(path))
        index = doc['canonical_work_index']
        if index in found:
            raise ValueError('duplicate canonical measurement')
        found[index] = (doc, str(path), sha256(raw).hexdigest())
    return found


def metric(doc):
    cert = doc['certificate']
    measurement = doc['measurement']
    result = {key: measurement[key] for key in
              ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib')}
    if any(not math.isfinite(result[k]) or result[k] < 0 for k in result):
        raise ValueError('invalid measurement')
    result.update(status=cert['status'], reason=cert.get('reason'))
    for key in ('fir_interval_evaluations', 'cheap_difference_majorants_used',
                'nodes_examined', 'fully_proven_subintervals', 'exact_branch_splits',
                'exact_path_enumerations', 'interval_subdivisions',
                'max_alias_path_population', 'alias_population_operations'):
        # Missing baseline counters are unknown, never zero.
        result[key] = cert.get(key)
    return result


def summarize(spec):
    before = load(Path(spec['baseline']))
    after = load(Path(spec['candidate']))
    expected = set(spec['job_indices'])
    if set(before) != expected or set(after) != expected:
        raise ValueError('matched corpus incomplete or unexpected work present')
    rows = []
    for index in sorted(expected):
        b, bp, bh = before[index]
        c, cp, ch = after[index]
        for key in ('job', 'binding', 'stage_snapshot_sha256',
                    'verified_operator_binding_sha256'):
            if b[key] != c[key]:
                raise ValueError('mismatched source/operator/work: ' + key)
        if b['experiment_identity']['resources'] != c['experiment_identity']['resources']:
            raise ValueError('mismatched per-job resources')
        be, ce = b['measurement']['environment'], c['measurement']['environment']
        for key in ('python', 'executable', 'platform', 'mpmath', 'numpy',
                    'affinity', 'openblas_num_threads'):
            if be[key] != ce[key]:
                raise ValueError('mismatched execution environment: ' + key)
        if b['measurement']['profiling_enabled'] or c['measurement']['profiling_enabled']:
            raise ValueError('profiled timings do not belong in matched speed report')
        bm, cm = metric(b), metric(c)
        common_pass = bm['status'].startswith('PASS-') and cm['status'].startswith('PASS-')
        row = dict(job_index=index, job=b['job'], baseline=bm, candidate=cm,
                   both_pass=common_pass, resources=b['experiment_identity']['resources'],
                   baseline_receipt=bp, baseline_receipt_sha256=bh,
                   candidate_receipt=cp, candidate_receipt_sha256=ch,
                   baseline_proof_code=b['prover_code_sha256'],
                   candidate_proof_code=c['prover_code_sha256'])
        row['wall_speedup'] = bm['elapsed_s'] / cm['elapsed_s'] if common_pass else None
        row['cpu_speedup'] = bm['cpu_s'] / cm['cpu_s'] if common_pass else None
        row['candidate_wall_change_percent'] = (
            100 * (cm['elapsed_s'] / bm['elapsed_s'] - 1) if common_pass else None)
        rows.append(row)
    common = [r for r in rows if r['both_pass']]
    summary = {}
    for label in ('baseline', 'candidate'):
        metrics = [r[label] for r in rows]
        passes = sum(m['status'].startswith('PASS-') for m in metrics)
        proof_cpu = sum(m['cpu_s'] for m in metrics)
        summary[label] = dict(
            dispositions=dict(Counter(m['status'] for m in metrics)),
            proof_wall_seconds_sum=sum(m['elapsed_s'] for m in metrics),
            proof_cpu_seconds_sum=proof_cpu,
            process_wall_seconds_sum=sum(m['process_elapsed_s'] for m in metrics),
            peak_single_process_rss_kib=max(m['peak_rss_kib'] for m in metrics),
            certified_intervals_per_cpu_hour=3600 * passes / proof_cpu,
            missing_counter_fields_are_unknown=True)
    summary['common_pass_count'] = len(common)
    summary['common_pass_wall_speedup_ratio_of_sums'] = (
        sum(r['baseline']['elapsed_s'] for r in common) /
        sum(r['candidate']['elapsed_s'] for r in common) if common else None)
    summary['common_pass_wall_speedup_median'] = (
        statistics.median(r['wall_speedup'] for r in common) if common else None)
    summary['pass_to_open_regressions'] = [r['job_index'] for r in rows
        if r['baseline']['status'].startswith('PASS-') and r['candidate']['status'] == 'OPEN']
    summary['open_to_pass_improvements'] = [r['job_index'] for r in rows
        if r['baseline']['status'] == 'OPEN' and r['candidate']['status'].startswith('PASS-')]
    summary['slower_common_pass_jobs'] = [r['job_index'] for r in common
                                        if r['wall_speedup'] < 1]
    return dict(name=spec['name'], summary=summary, rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = dict(schema='P15/high-rate-matched-benchmarks/1',
                  runs=[summarize(s) for s in json.loads(args.runs.read_text())],
                  interpretation=[
                    'Each pair uses the same source, operator, hardware affinity and budgets.',
                    'Times are actual measurements, not microbenchmark extrapolations.',
                    'OPEN deadlines are censored outcomes; no speedup is calculated for them.',
                    'Per-process peak RSS is not aggregate simultaneous memory consumption.',
                    'Stage FIR counters exclude the separately recorded global halfband proof.',
                    'A single run is not a statistical confidence interval.'])
    content = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output.exists():
        if args.output.read_text() != content:
            raise ValueError('refusing to replace a different benchmark summary')
    else:
        with args.output.open('x') as stream:
            stream.write(content)
    print(json.dumps([dict(name=r['name'], **r['summary']) for r in result['runs']], indent=2))


if __name__ == '__main__':
    main()
