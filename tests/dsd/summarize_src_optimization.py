#!/usr/bin/env python3
"""Consolidate completed paired CLI measurements without changing raw receipts."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measurements', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to replace an existing summary')
    result = dict(schema='sox/src-runtime-optimization-summary/1', status='PASS',
                  scope='Local virtual-host CLI measurements; no physical qualification or P15 certificate.',
                  numerical_scope='Exact no-dither signed-32 PCM output identity for every captured conversion.',
                  intervals='Per-case paired bootstrap intervals, not simultaneous family-wise confidence bounds.',
                  measurements=[], cases=[], conversions=0, timing_conversions=0)
    identities = None
    seen = set()
    for path in args.measurements:
        raw = path.read_bytes()
        data = json.loads(raw)
        if data['status'] != 'PASS' or data['mode'] != 'PAIRED':
            raise ValueError(f'{path}: require a completed paired measurement')
        current = {name: item['sha256'] for name, item in data['variants'].items()}
        if set(current) != {'baseline', 'candidate'}:
            raise ValueError('summary requires exactly baseline and candidate')
        if identities is not None and current != identities:
            raise ValueError('measurement files compare different executable identities')
        identities = current
        expected_rows = len(data['cases']) * 2 * (1 + data['config']['warmups'] + data['config']['repetitions'])
        if len(data['raw']) != expected_rows:
            raise ValueError(f'{path}: incomplete row count')
        for row in data['raw']:
            if row['exit'] or row['timed_out'] or not row['bit_identical_to_baseline']:
                raise ValueError(f'{path}: unsuccessful output comparison')
        result['measurements'].append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
            cases=len(data['cases']), conversions=len(data['raw']), hardware=data['hardware'], config=data['config']))
        result['conversions'] += len(data['raw'])
        result['timing_conversions'] += sum(row['phase'] == 'timing' for row in data['raw'])
        for case in data['cases']:
            ident = case['id']
            if ident in seen:
                raise ValueError('duplicate case ID across measurements')
            seen.add(ident)
            baseline = data['summaries'][ident + '/baseline']
            candidate = data['summaries'][ident + '/candidate']
            comparison = data['comparisons'][ident + '/candidate']
            item = dict(case=case, arms={}, comparisons={})
            for name, arm in [('baseline', baseline), ('candidate', candidate)]:
                item['arms'][name] = dict(
                    cpu_seconds=arm['cpu_seconds'], wall_seconds=arm['wall_seconds'],
                    max_rss_kib=arm['max_rss_kib'],
                    audio_seconds_per_cpu_second=arm['audio_seconds_per_cpu_second'],
                    audio_seconds_per_wall_second=arm['audio_seconds_per_wall_second'],
                    output_samples_per_cpu_second=arm['output_samples_per_cpu_second'],
                    output_samples_per_wall_second=arm['output_samples_per_wall_second'])
            for metric in ('cpu_seconds', 'wall_seconds'):
                stat = comparison[metric]
                low, high = stat['median_ci95']
                item['comparisons'][metric] = dict(
                    median_speedup=stat['paired_ratios']['median'],
                    median_ci95=stat['median_ci95'],
                    relative_mad=stat['paired_ratios']['relative_mad'],
                    descriptive_interval_position='above_one' if low > 1 else 'below_one' if high < 1 else 'includes_one')
            result['cases'].append(item)
    result['executable_sha256'] = identities
    result['case_count'] = len(result['cases'])
    result['counts'] = {metric: {label: sum(c['comparisons'][metric]['descriptive_interval_position'] == label
                              for c in result['cases'])
                       for label in ('above_one', 'includes_one', 'below_one')}
                       for metric in ('cpu_seconds', 'wall_seconds')}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'case_count', 'conversions', 'timing_conversions', 'counts')}))


if __name__ == '__main__':
    main()
