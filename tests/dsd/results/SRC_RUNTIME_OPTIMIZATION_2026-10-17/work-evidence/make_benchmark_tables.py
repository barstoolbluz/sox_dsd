#!/usr/bin/env python3
"""Render BENCHMARK_TABLES.md beside a completed benchmark-summary.json."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path


SCHEMA = 'sox/src-runtime-optimization-summary/1'


def literal(value):
    return '<code>' + html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ') + '</code>'


def number(value):
    """Preserve the stored numeric value; do not round reported medians."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'expected a finite number, received {value!r}')
    return json.dumps(value, allow_nan=False)


def relative(value):
    return 'undefined' if value is None else number(value)


def dispersion(stat):
    return (f'median {number(stat["median"])}<br>'
            f'MAD {number(stat["mad"])}<br>'
            f'relative MAD {relative(stat["relative_mad"])}')


def case_label(case):
    label = literal(case['id'])
    if case.get('repeat_of') is not None:
        label += '<br>Diagnostic repeat of ' + literal(case['repeat_of'])
    return label


def render(data, source_name, source_sha256):
    if data.get('schema') != SCHEMA or data.get('status') != 'PASS':
        raise ValueError('require a completed PASS summary with schema ' + SCHEMA)
    cases = data['cases']
    ids = [item['case']['id'] for item in cases]
    if len(cases) != data['case_count'] or len(set(ids)) != len(ids):
        raise ValueError('case count mismatch or duplicate case IDs')
    if set(data['executable_sha256']) != {'baseline', 'candidate'}:
        raise ValueError('require exactly baseline and candidate executable identities')
    lines = [
        '# Benchmark tables', '',
        f'Source: {literal(source_name)}. SHA256: {literal(source_sha256)}.', '',
        f'Recorded cases: **{data["case_count"]}**. Captured conversions: '
        f'**{data["conversions"]}**; timing conversions: **{data["timing_conversions"]}**.', '',
        html.escape(data['scope']), '', html.escape(data['numerical_scope']), '',
        'Each case appears below in source order, including diagnostic repeats. '
        'A repeat is labelled with its recorded `case.repeat_of` value and remains a separate row group.', '',
        'Numeric entries preserve the stored values in shortest round-trip decimal form. '
        'MAD is the median absolute deviation in the stated unit; relative MAD is MAD/median, '
        'shown as a fraction. An undefined relative MAD is labelled explicitly.', '',
        '## Timing and paired comparisons', '',
        'Timing statistics use the recorded timing repetitions. CPU time is child user plus system time; '
        'wall time is elapsed time. The speedup is the median paired baseline/candidate time ratio; '
        'values above 1 indicate less candidate time. It is not calculated by dividing the two arm medians.', '',
        'The 95% intervals are the recorded per-case paired bootstrap intervals, '
        '**unadjusted for multiple comparisons**. They are not simultaneous family-wise confidence bounds. '
        'The paired relative MAD describes the individual paired ratios.', '',
        '| Case | Clock | Baseline seconds | Candidate seconds | Paired B/C speedup |',
        '|---|---|---|---|---|',
    ]
    for item in cases:
        for metric, clock in [('cpu_seconds', 'CPU'), ('wall_seconds', 'Wall')]:
            baseline, candidate = (item['arms'][name][metric] for name in ('baseline', 'candidate'))
            comparison = item['comparisons'][metric]
            low, high = comparison['median_ci95']
            if low > high:
                raise ValueError('reversed confidence interval for ' + item['case']['id'])
            speedup = (f'median {number(comparison["median_speedup"])}<br>'
                       f'95% lower {number(low)}<br>95% upper {number(high)}<br>'
                       f'paired relative MAD {relative(comparison["relative_mad"])}')
            lines.append(f'| {case_label(item["case"])} | {clock}<br>n B/C: '
                         f'{baseline["n"]}/{candidate["n"]} | {dispersion(baseline)} | '
                         f'{dispersion(candidate)} | {speedup} |')
    lines += [
        '', '## Absolute throughput and memory', '',
        'Audio throughput is input audio seconds processed per CPU or wall second. '
        'Sample throughput is output sample values across all channels per CPU or wall second. '
        'These are the stored absolute throughput values, using the corresponding arm median time.', '',
        '**RSS is launcher-inclusive** child-process peak RSS from `wait4`, in KiB. '
        'The table gives the median and MAD of those per-run high-water measurements.', '',
        '| Case | Arm | Audio throughput (audio s/s) | Output throughput (samples/s) | Launcher-inclusive peak RSS (KiB) |',
        '|---|---|---|---|---|',
    ]
    for item in cases:
        for name in ('baseline', 'candidate'):
            arm = item['arms'][name]
            audio = (f'CPU {number(arm["audio_seconds_per_cpu_second"])}<br>'
                     f'wall {number(arm["audio_seconds_per_wall_second"])}')
            samples = (f'CPU {number(arm["output_samples_per_cpu_second"])}<br>'
                       f'wall {number(arm["output_samples_per_wall_second"])}')
            lines.append(f'| {case_label(item["case"])} | {name} | {audio} | {samples} | '
                         f'{dispersion(arm["max_rss_kib"])} |')
    lines += ['', '## Executable identities', '']
    for name in ('baseline', 'candidate'):
        lines.append(f'- {name}: {literal(data["executable_sha256"][name])}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--replace', action='store_true', help='replace an existing rendered table file')
    args = parser.parse_args()
    source = args.summary.resolve()
    output = source.with_name('BENCHMARK_TABLES.md')
    if output.exists() and not args.replace:
        parser.error('refusing to replace existing BENCHMARK_TABLES.md; use --replace')
    raw = source.read_bytes()
    data = json.loads(raw)
    document = render(data, source.name, hashlib.sha256(raw).hexdigest())
    output.write_text(document)
    print(json.dumps({'output': str(output), 'cases': data['case_count'], 'bytes': output.stat().st_size}))


if __name__ == '__main__':
    main()
