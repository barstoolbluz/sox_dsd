#!/usr/bin/env python3
"""Summarize exact config02 campaign/retry populations; no numerical proving.

This checks plan membership, immutable source/proof/harness identity and all
supervised executions. Canonical spectral admission remains the independent
coverage verifier's responsibility. Existing outputs may only match exactly.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path


LABELS = ('candidate_final_campaign_60s',
          'candidate_final_wide256_192000_6000_7000_180s',
          'candidate_final_retry_180s')
COUNTERS = ('fir_interval_evaluations', 'cheap_difference_majorants_used',
            'nodes_examined', 'fully_proven_subintervals', 'exact_branch_splits',
            'exact_path_enumerations', 'interval_subdivisions')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def publish(path, document):
    data = (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('refusing to replace different evidence: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def summary(rows):
    passed = [r for r in rows if r['status'].startswith('PASS-LOCAL-')]
    cpu = math.fsum(r['measurement']['cpu_s'] for r in rows)
    process_wall = math.fsum(r['supervision']['process_wall_s'] for r in rows)
    populations = {key: sum(r['population_operations'][key] for r in passed)
                   for key in passed[0]['population_operations']} if passed else {}
    return dict(attempts=len(rows), passes=len(passed),
        statuses=dict(Counter(r['status'] for r in rows)),
        open_reasons=dict(Counter(r['reason'] for r in rows if r['status'] == 'OPEN')),
        proof_wall_seconds_sum=math.fsum(r['measurement']['elapsed_s'] for r in rows),
        proof_cpu_seconds_sum=cpu,
        harness_process_seconds_sum=math.fsum(r['measurement']['process_elapsed_s'] for r in rows),
        supervised_process_wall_seconds_sum=process_wall,
        peak_single_process_rss_kib=max(r['measurement']['peak_rss_kib'] for r in rows),
        passes_per_proof_cpu_hour=3600 * len(passed) / cpu,
        passes_per_supervised_process_wall_hour=3600 * len(passed) / process_wall,
        pass_only_counters={key: sum(r['counters'][key] for r in passed) for key in COUNTERS},
        pass_only_population_operations=populations,
        attempts_with_unrecorded_proof_counters=len(rows)-len(passed),
        max_recorded_alias_path_population=max(r['max_alias_path_population'] for r in passed),
        external_kills=sum(r['supervision']['external_deadline_killed'] for r in rows),
        execution_failures=sum(r['supervision']['exit_code'] not in (0, 2) for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    config = load(args.config)
    if config['schema'] != 'P15/final-high-rate-aggregation/1':
        raise ValueError('unsupported final configuration')
    specs = {s['label']: s for s in config['measurements']}
    selected = [specs[label] for label in LABELS]
    snapshot = root / selected[0]['proof_snapshot'] / 'IDENTITY.json'
    proof = load(snapshot)['prover_code_sha256']
    source_binding = None
    harness_hash = digest(root / 'tests/dsd/p15_high_rate_experiment.py')
    operator_identities, environments, runs = {}, {}, []
    for spec in selected:
        plan_path = root / spec['plan']
        plan = load(plan_path)['job_indices']
        if len(set(plan)) != len(plan):
            raise ValueError('duplicate planned job')
        directory = root / spec['directory']
        rows, indices = [], set()
        for path in sorted(directory.glob('*.json')):
            doc = load(path)
            index, job, identity = doc['canonical_work_index'], doc['job'], doc['experiment_identity']
            if type(index) is not int or index in indices or index not in plan:
                raise ValueError('duplicate or unexpected canonical job')
            indices.add(index)
            if path.stem != sha256(json.dumps(job, sort_keys=True, separators=(',', ':')).encode()).hexdigest():
                raise ValueError('work filename mismatch')
            if doc['prover_code_sha256'] != proof or identity['prover_code_sha256'] != proof:
                raise ValueError('proof snapshot mismatch')
            if identity['harness_sha256'] != harness_hash or identity['profiling_enabled']:
                raise ValueError('harness identity or profiling mismatch')
            for key in ('job', 'binding', 'stage_snapshot_sha256', 'verified_operator_binding_sha256'):
                if doc[key] != identity[key]:
                    raise ValueError('inconsistent inner/outer identity')
            if any(identity['resources'][key] != value for key, value in spec['resources'].items()):
                raise ValueError('configured resources mismatch')
            if source_binding is None:
                source_binding = doc['binding']
            if doc['binding'] != source_binding:
                raise ValueError('mixed source/design binding')
            pair = f"{job['intermediate_hz']}-{job['output_hz']}"
            op = {key: doc[key] for key in ('stage_snapshot_sha256', 'verified_operator_binding_sha256')}
            if pair in operator_identities and operator_identities[pair] != op:
                raise ValueError('mixed operator snapshot/binding')
            operator_identities[pair] = op
            env = doc['measurement']['environment']
            env_key = sha256(json.dumps(env, sort_keys=True).encode()).hexdigest()
            environments[env_key] = env
            logs = list((directory / 'supervision').glob(f'*/{index:05d}-candidate.json'))
            if len(logs) != 1:
                raise ValueError('missing or duplicate supervision log')
            log_path = logs[0]
            log, request = load(log_path), load(log_path.with_name('request.json'))
            cert, measure = doc['certificate'], doc['measurement']
            expected_exit = 0 if cert['status'].startswith('PASS-LOCAL-') else 2
            if (log['exit_code'] != expected_exit or log['external_deadline_killed'] or
                    index not in request['jobs'] or
                    request['per_job_signal_seconds'] != identity['resources']['seconds']):
                raise ValueError('unexpected supervised execution')
            if env['affinity'] != [identity['resources']['cpu']] or measure['profiling_enabled']:
                raise ValueError('affinity or profiling mismatch')
            numeric = {key: measure[key] for key in ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib')}
            if any(not math.isfinite(v) or v < 0 for v in numeric.values()):
                raise ValueError('invalid measurement')
            rows.append(dict(canonical_work_index=index, job=job,
                receipt=str(path.relative_to(root)), receipt_sha256=digest(path),
                status=cert['status'], reason=cert.get('reason'), measurement=numeric,
                environment_sha256=env_key, resources=identity['resources'],
                counters={key: cert.get(key) for key in COUNTERS},
                population_operations=cert.get('alias_population_operations'),
                max_alias_path_population=cert.get('max_alias_path_population'),
                max_coherent_alias_upper=cert.get('max_coherent_alias_upper'),
                supervision=dict(path=str(log_path.relative_to(root)), sha256=digest(log_path),
                    request=str(log_path.with_name('request.json').relative_to(root)),
                    request_sha256=digest(log_path.with_name('request.json')),
                    external_seconds=request['per_process_kill_seconds'],
                    process_wall_s=log['process_wall_s'], exit_code=log['exit_code'],
                    external_deadline_killed=log['external_deadline_killed'])))
        if indices != set(plan) or len(rows) != spec['expected_receipts']:
            raise ValueError('incomplete configured campaign/retry population')
        rows.sort(key=lambda r: r['canonical_work_index'])
        runs.append(dict(label=spec['label'], directory=spec['directory'],
                         plan=spec['plan'], plan_sha256=digest(plan_path),
                         summary=summary(rows), rows=rows))
    original = {r['canonical_work_index']: r for r in runs[0]['rows']}
    retries = runs[1]['rows'] + runs[2]['rows']
    retry_indices = [r['canonical_work_index'] for r in retries]
    open_indices = {i for i, row in original.items() if row['status'] == 'OPEN'}
    if len(set(retry_indices)) != len(retry_indices) or set(retry_indices) != open_indices:
        raise ValueError('retry population does not exactly match original OPEN set')
    if any(not r['status'].startswith('PASS-LOCAL-') or r['job'] != original[r['canonical_work_index']]['job'] for r in retries):
        raise ValueError('retry is not a same-work PASS')
    checked = {'tests/dsd/' + name: expected for name, expected in proof.items()}
    checked.update(source_binding['source'])
    checked['tests/dsd/p15_high_rate_experiment.py'] = harness_hash
    for name, expected in checked.items():
        if digest(root / name) != expected:
            raise ValueError('current source/proof/harness differs: ' + name)
    groups = defaultdict(list)
    for row in runs[0]['rows']:
        groups[row['job']['cell_id']].append(row)
    all_rows = runs[0]['rows'] + retries
    union_summary = summary(all_rows)
    union_summary['unique_canonical_jobs_certified'] = len(original)
    union_summary['total_attempts_including_failed_first_attempts'] = len(all_rows)
    document = dict(schema='P15/final-campaign-addendum/1',
        config=str(args.config.resolve().relative_to(root)), config_sha256=digest(args.config),
        generator_sha256=digest(Path(__file__)), proof_code_sha256=proof,
        harness_sha256=harness_hash, source_binding=source_binding,
        current_source_proof_harness_files_verified=checked,
        operator_identities=operator_identities, environments=environments,
        runs=runs, retries_combined=summary(retries),
        first_attempt_by_cell={cell: summary(rows) for cell, rows in sorted(groups.items())},
        first_attempt_output_rates=dict(Counter(str(r['job']['output_hz']) for r in runs[0]['rows'])),
        first_attempt_dsd_rates=dict(Counter(r['job']['cell_id'].split('.')[0] for r in runs[0]['rows'])),
        first_attempt_plus_retries=union_summary,
        retry_under_60_seconds=sum(r['measurement']['elapsed_s'] < 60 for r in retries),
        retry_over_60_seconds=sum(r['measurement']['elapsed_s'] > 60 for r in retries),
        limitations=['Campaign resource yield, not matched baseline speedup.',
            'Sum of per-process wall times is not dispatcher makespan.',
            'Peak RSS is single-process, not simultaneous cgroup memory.',
            'OPEN attempts do not retain unfinished proof counters.',
            'A larger permitted budget is not evidence that it was necessary.',
            'Independent numerical replay and exact normative admission are separate from this timing summary.'])
    publish(args.output, document)
    print(json.dumps({'runs': [{k: r[k] for k in ('label', 'summary')} for r in runs],
                      'combined': union_summary}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
