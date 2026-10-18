#!/usr/bin/env python3
"""Run the explicitly configured P15 final census and coverage aggregation.

Completion and source-code identities are checked before any output directory
is created. The numerical campaigns and scalar readjudication are separate
steps; this script never runs a spectral proof or overwrites their receipts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


def root_path(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('configuration paths must stay within the repository')
    return root / relative


def load(path):
    return json.loads(path.read_text())


def prepare(root, config, report):
    """Validate configured bytes, full plan populations, and frozen versions."""
    if config.get('schema') != 'P15/final-high-rate-aggregation/1':
        raise ValueError('unsupported aggregation configuration')
    for name, expected in config['pinned_files_sha256'].items():
        if sha256(root_path(root, name).read_bytes()).hexdigest() != expected:
            raise ValueError('configured input/source hash changed: ' + name)
    snapshots = {}
    summaries = []
    complete = True
    contributing = {}
    labels = set()
    for item in config['measurements']:
        if item['label'] in labels or item['role'] not in ('baseline', 'candidate'):
            raise ValueError('duplicate label or invalid experiment role')
        labels.add(item['label'])
        plan = load(root_path(root, item['plan']))
        expected = set(plan['job_indices'])
        if len(expected) != len(plan['job_indices']):
            raise ValueError('duplicate configured canonical job')
        if item['proof_snapshot'] not in snapshots:
            snapshots[item['proof_snapshot']] = report.proof_snapshot(root_path(root, item['proof_snapshot']))
        snapshot = snapshots[item['proof_snapshot']]
        entries = []
        directory = root_path(root, item['directory'])
        if directory.is_dir():
            for path in sorted(directory.glob('*.json')):
                doc = load(path)
                if not isinstance(doc, dict) or 'experiment_identity' not in doc or 'certificate' not in doc:
                    raise ValueError('unexpected non-experiment file in receipt directory: ' + str(path))
                if doc.get('prover_code_sha256') != snapshot['prover_code_sha256']:
                    raise ValueError('mixed or unrecognized proof version: ' + str(path))
                identity = doc['experiment_identity']
                if (any(identity['resources'].get(key) != value for key, value in item['resources'].items()) or
                        identity.get('profiling_enabled') is not False):
                    raise ValueError('configured resource/profiling scope mismatch: ' + str(path))
                index = doc.get('canonical_work_index')
                if type(index) is not int:
                    raise ValueError('missing canonical work index: ' + str(path))
                entries.append(index)
                if doc['certificate']['status'].startswith('PASS'):
                    contributing[(str(path.relative_to(root)), sha256(path.read_bytes()).hexdigest())] = report.digest(doc['job'])
        actual = set(entries)
        if len(actual) != len(entries) or actual - expected:
            raise ValueError('duplicate or unexpected configured work: ' + item['label'])
        missing = expected - actual
        complete = complete and not missing
        summaries.append(dict(label=item['label'], expected=len(expected), observed=len(actual),
                              missing_indices=sorted(missing)))
    return complete, summaries, contributing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('FINAL_AGGREGATION_CONFIG.json'))
    parser.add_argument('--readjudication', type=Path, required=True,
                        help='Refreshed exact-normative-envelope verification.json')
    parser.add_argument('--census-output', type=Path)
    parser.add_argument('--report-output', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    sys.path.insert(0, str(root / 'tests/dsd'))
    import p15_high_rate_census as census
    import p15_high_rate_coverage_report as report
    for module in (census, report):
        if Path(module.__file__).resolve() != root / 'tests/dsd' / (module.__name__ + '.py'):
            raise ValueError('aggregation imported a module from the wrong repository')
    config = load(args.config)
    complete, status, contributing = prepare(root, config, report)
    if not complete:
        print(json.dumps(dict(status='WAITING_FOR_CONFIGURED_RECEIPTS', measurements=status), sort_keys=True))
        return 2
    # Refuse an obsolete readjudication inventory before creating even the
    # census output. The report then checks all original and prior witnesses.
    readjudication = args.readjudication.resolve(strict=True)
    report.require_strict_readjudication(readjudication, contributing, report.bindings())
    if args.check_only:
        print(json.dumps(dict(status='READY', measurements=status), sort_keys=True))
        return 0
    if args.census_output is None or args.report_output is None:
        parser.error('--census-output and --report-output are required unless --check-only')
    measurements = config['measurements']
    census.create_census(args.census_output,
        [(m['label'], root_path(root, m['directory'])) for m in measurements])
    result = report.generate(args.census_output, args.report_output,
        {m['label']: root_path(root, m['proof_snapshot']) for m in measurements},
        {m['label']: root_path(root, m['plan']) for m in measurements},
        [tuple(pair) for pair in config['matched_pairs']],
        {m['label'] for m in measurements if m['role'] == 'candidate'},
        adjudication=readjudication)
    print(json.dumps({key: result[key] for key in ('status', 'current_unique_pass',
        'candidate_unique_pass', 'current_pass_new_vs_original',
        'cumulative_explicit_evidence_pass', 'complete_candidate_cells')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
