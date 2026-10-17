#!/usr/bin/env python3
"""Extract 48 complete cases from the preserved, incomplete primary receipt."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


PARENT_SHA256 = '8f7d6edbd8d50edc905eff86b185c06b74093e3ee20001fe1f2f3a033cc70419'
ARMS = ('baseline', 'candidate')
COUNTS = {'preflight': 1, 'warmup': 2, 'timing': 15}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stats(values):
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    return dict(n=len(values), median=median, mad=mad,
                relative_mad=mad / median if median else None,
                minimum=min(values), maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parent = args.parent.resolve()
    output = args.output.resolve()
    require(output != parent, 'output must differ from preserved parent')
    require(not output.exists(), 'refusing to replace an existing output')
    require(not output.parent.exists() or not any(output.parent.iterdir()),
            'output directory must be new or empty')
    raw = parent.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == PARENT_SHA256, 'parent differs from the frozen incomplete receipt')
    data = json.loads(raw)
    require(data['schema'] == 'sox/production-dsp-paired/1', 'unexpected schema')
    require(data['status'] == 'RUNNING' and data['mode'] == 'PAIRED', 'unexpected parent status/mode')
    require(not data['errors'], 'parent records errors')
    require(set(data['variants']) == set(ARMS), 'unexpected variants')
    require(data['config']['repetitions'] == 15 and data['config']['warmups'] == 2,
            'unexpected repetition counts')
    require(len(data['cases']) == 49 and len(data['raw']) == 1761, 'unexpected parent size')
    cases = {case['id']: case for case in data['cases']}
    require(len(cases) == 49, 'duplicate case ID')
    grouped = {name: {} for name in cases}
    indices = {name: [] for name in cases}
    for index, row in enumerate(data['raw']):
        name = row['case']
        require(name in cases, 'row refers to unknown case')
        key = (row['phase'], row['repeat'], row['variant'])
        require(key[0] in COUNTS and key[2] in ARMS and 0 <= key[1] < COUNTS[key[0]],
                'unexpected phase/repeat/variant identity')
        require(key not in grouped[name], 'duplicate phase/repeat/variant identity')
        require(row['exit'] == 0 and not row['timed_out'], 'unsuccessful child execution')
        require(row['bit_identical_to_baseline'] is True, 'recorded output mismatch')
        require(re.fullmatch('[0-9a-f]{64}', row['output_sha256']) is not None,
                'missing or malformed recorded output hash')
        case = cases[name]
        frames = (case['frames'] * case['output_hz'] + case['input_hz'] // 2) // case['input_hz']
        require(row['output_frames'] == frames and row['output_bytes'] == frames * case['channels'] * 4,
                'recorded output length mismatch')
        require(row['command'][0] == data['variants'][key[2]]['executable'], 'command identity mismatch')
        for metric in ('cpu_seconds', 'wall_seconds', 'max_rss_kib'):
            require(math.isfinite(row[metric]) and row[metric] >= 0, 'invalid recorded measurement')
        require(row['cpu_seconds'] > 0 and row['wall_seconds'] > 0, 'nonpositive recorded time')
        grouped[name][key] = row
        indices[name].append(index)
    expected = {(phase, repeat, arm) for phase, count in COUNTS.items()
                for repeat in range(count) for arm in ARMS}
    included, excluded, missing = [], [], []
    for name, case in cases.items():
        rows = grouped[name]
        reference = rows[('preflight', 0, 'baseline')]['output_sha256']
        require(all(row['output_sha256'] == reference for row in rows.values()),
                'inconsistent recorded output hashes for ' + name)
        absent = expected - set(rows)
        if absent:
            excluded.append(name)
            missing.extend(dict(case=name, phase=phase, repeat=repeat, variant=arm)
                           for phase, repeat, arm in sorted(absent))
            continue
        included.append(name)
        frames = (case['frames'] * case['output_hz'] + case['input_hz'] // 2) // case['input_hz']
        measured = {arm: [rows[('timing', repeat, arm)] for repeat in range(15)] for arm in ARMS}
        for arm in ARMS:
            stored = data['summaries'][name + '/' + arm]
            for metric in ('cpu_seconds', 'wall_seconds', 'max_rss_kib'):
                require(stored[metric] == stats([row[metric] for row in measured[arm]]),
                        'arm summary differs from recorded observations: ' + name + '/' + arm + '/' + metric)
            for clock in ('cpu', 'wall'):
                median = stored[clock + '_seconds']['median']
                require(stored['audio_seconds_per_' + clock + '_second'] == case['seconds'] / median,
                        'audio throughput mismatch')
                require(stored['output_samples_per_' + clock + '_second'] == frames * case['channels'] / median,
                        'sample throughput mismatch')
        for metric in ('cpu_seconds', 'wall_seconds'):
            stored = data['comparisons'][name + '/candidate'][metric]
            ratios = [measured['baseline'][i][metric] / measured['candidate'][i][metric] for i in range(15)]
            require(stored['paired_ratios'] == stats(ratios), 'paired-ratio summary mismatch')
            low, high = stored['median_ci95']
            require(math.isfinite(low) and math.isfinite(high) and 0 < low <= high,
                    'invalid recorded confidence interval')
    require(len(included) == 48 and excluded == ['dsd256_short'] and len(missing) == 3,
            'expected exactly 48 complete cases and three missing dsd256_short observations')
    selected = set(included)
    result = copy.deepcopy(data)
    result['cases'] = [case for case in data['cases'] if case['id'] in selected]
    row_indices = [i for i, row in enumerate(data['raw']) if row['case'] in selected]
    result['raw'] = [data['raw'][i] for i in row_indices]
    result['fixtures'] = {name: data['fixtures'][name] for name in included}
    for field in ('summaries', 'comparisons'):
        result[field] = {key: value for key, value in data[field].items() if key.rsplit('/', 1)[0] in selected}
    result['status'] = 'PASS'
    result['qualification'] = ('Validated complete-case subset of an incomplete RUNNING parent receipt. '
                               'PASS applies only to these 48 retained cases. ' + data['qualification'])
    result['derivation'] = dict(
        kind='complete-case extraction; no new or reconstructed observations',
        parent_path=str(parent), parent_sha256=digest, parent_status=data['status'],
        parent_recorded_cases=49, parent_recorded_rows=1761, parent_expected_rows=1764,
        included_cases=included, excluded_cases=excluded, excluded_recorded_rows=33,
        missing_parent_observations=missing, selected_rows=1728, selected_timing_rows=1440,
        source_row_indices=row_indices, source_case_indices=[i for i, case in enumerate(data['cases'])
                                                            if case['id'] in selected],
        original_results_directory=str(parent.parent),
        path_provenance={'commands': 'Retained verbatim, including original absolute executable/input/output paths.',
                         'stdout_stderr': 'Retained relative paths resolve against original_results_directory, not this derived directory.',
                         'fixtures': 'Retained original fixture hashes; no fixture or output audio regenerated.'},
        statistical_verification='All arm n/median/MAD/relative-MAD/minimum/maximum, absolute throughput, and paired-ratio statistics independently recomputed from recorded timing rows and matched exactly.',
        confidence_intervals='Retained verbatim from the parent, including original bootstrap method; not recomputed.',
        recorded_output_verification='All captured rows had exit 0, no timeout, expected recorded frame/byte length, and a recorded hash equal to their case baseline preflight. Deleted output audio was not re-created or re-hashed.',
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    require(len(result['raw']) == 1728, 'unexpected subset row count')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    require(hashlib.sha256(parent.read_bytes()).hexdigest() == digest, 'parent changed during extraction')
    temporary.replace(output)
    print(json.dumps(dict(output=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                          status=result['status'], cases=48, rows=1728, timing_rows=1440,
                          parent_status=data['status'], parent_sha256=digest,
                          excluded_cases=excluded, missing_observations=missing), indent=2))


if __name__ == '__main__':
    main()
