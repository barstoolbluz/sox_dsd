#!/usr/bin/env python3
"""Render the final SRC performance narrative from the consolidated summary.

This is a presentation step only. It neither runs conversions nor modifies
measurement receipts. Original configurations and case.repeat_of diagnostics
remain separate. The expected corpus is 49 primary plus 21 revised controls.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


SCHEMA = 'sox/src-runtime-optimization-summary/1'
ARMS = ('baseline', 'candidate')
METRICS = ('cpu_seconds', 'wall_seconds')
POSITIONS = ('above_one', 'includes_one', 'below_one')
PCM_REPRESENTATIVES = (
    'pcm_44100_48000_stereo',
    'pcm_48000_44100_stereo',
    'pcm_44100_96000_stereo',
    'pcm_48000_88200_stereo',
    'pcm_176400_192000_stereo',
    'pcm_384000_44100_stereo',
    'pcm_44100_88200_stereo',
)
PCM_CONTROLS = (
    'pcm_buffer32_44100_48000',
    'pcm_buffer128_48000_44100',
    'pcm_buffer256_44100_48000',
    'pcm_buffer256_48000_44100',
    'pcm_qualityl_44100_48000',
    'pcm_qualityl_48000_44100',
    'pcm_qualitym_44100_48000',
    'pcm_qualitym_48000_44100',
    'pcm_qualityh_44100_48000',
    'pcm_qualityh_48000_44100',
    'pcm_qualityu_44100_48000',
    'pcm_qualityu_48000_44100',
)
DSD_NATIVE = (
    'dsd64_mastering.v2_176400',
    'dsd128_mastering.v2_176400',
    'dsd256_mastering.v2_176400',
)
DSD_TIERS = tuple('dsd256_v2_384000_' + tier for tier in
                  ('scalar', 'sse2', 'avx1', 'avx2', 'avx512'))
DSD_CONTINUITY = (
    'dsd256_mastering_v1_176400_stereo_continuity',
    'dsd256_mastering_v1_352800_stereo_continuity',
    'dsd256_mastering_v2_176400_stereo_continuity',
    'dsd256_mastering_v2_352800_stereo_continuity',
)
CONTROL_IDS = frozenset(PCM_CONTROLS + DSD_TIERS + DSD_CONTINUITY)
MATCHING_PARAMETERS = (
    'kind', 'input_hz', 'output_hz', 'channels', 'frames', 'seconds',
    'buffer', 'quality', 'fir_kernel', 'profile',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    """Six significant digits for display; the JSON keeps full precision."""
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), 'non-finite or nonnumeric display value')
    return format(value, '.6g')


def integer(value, description):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            description + ' must be a nonnegative integer')
    return value


def literal(value):
    require('`' not in value and '\n' not in value and '|' not in value,
            'unsafe Markdown case identifier')
    return '`' + value + '`'


def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |',
             '| ' + ' | '.join('---' for _ in headers) + ' |']
    for row in rows:
        require(len(row) == len(headers), 'table width mismatch')
        lines.append('| ' + ' | '.join(str(cell) for cell in row) + ' |')
    return '\n'.join(lines)


def position(item, metric):
    stat = item['comparisons'][metric]
    low, high = stat['median_ci95']
    require(0 < low <= high and math.isfinite(low) and math.isfinite(high),
            'invalid confidence interval for ' + item['case']['id'])
    result = 'above_one' if low > 1 else 'below_one' if high < 1 else 'includes_one'
    require(stat['descriptive_interval_position'] == result,
            'stored interval position disagrees with bounds')
    return result


def ratio(item, metric='cpu_seconds'):
    stat = item['comparisons'][metric]
    low, high = stat['median_ci95']
    return number(stat['median_speedup']) + '× [' + number(low) + ', ' + number(high) + ']'


def median(item, arm, metric):
    return number(item['arms'][arm][metric]['median'])


def rate_label(item):
    case = item['case']
    return number(case['input_hz'] / 1000) + '→' + number(case['output_hz'] / 1000)


def paired_values(item, key, summary=False):
    values = [item['arms'][arm][key] for arm in ARMS]
    if summary:
        values = [value['median'] for value in values]
    return number(values[0]) + ' → ' + number(values[1])


def counts(items, metric):
    return {label: sum(position(item, metric) == label for item in items)
            for label in POSITIONS}


def build_section(data, summary_sha256):
    require(data['schema'] == SCHEMA and data['status'] == 'PASS',
            'require a completed consolidated SRC summary')
    require(set(data['executable_sha256']) == set(ARMS),
            'require baseline and candidate executable identities')
    records = data['cases']
    require(data['case_count'] == len(records), 'summary case count mismatch')
    by_id = {item['case']['id']: item for item in records}
    require(len(by_id) == len(records), 'duplicate case IDs')
    for ident in by_id:
        literal(ident)

    originals = [item for item in records if item['case'].get('repeat_of') is None]
    repeats = [item for item in records if item['case'].get('repeat_of') is not None]
    original_ids = {item['case']['id'] for item in originals}
    controls = [item for item in originals if item['case']['id'] in CONTROL_IDS]
    primary = [item for item in originals if item['case']['id'] not in CONTROL_IDS]
    require(len(originals) == 70 and len(primary) == 49 and len(controls) == 21,
            'require 49 primary plus 21 revised-control configurations')
    require(CONTROL_IDS <= original_ids, 'a required revised control is absent')
    require(set(PCM_REPRESENTATIVES + DSD_NATIVE) <= original_ids,
            'a required representative primary case is absent')

    warmups_by_repetitions = {}
    for measurement in data['measurements']:
        config = measurement['config']
        n = integer(config['repetitions'], 'measurement repetitions')
        warmups = integer(config['warmups'], 'measurement warmups')
        warmups_by_repetitions.setdefault(n, set()).add(warmups)
        expected = measurement['cases'] * 2 * (1 + warmups + n)
        require(measurement['conversions'] == expected,
                'measurement conversion count disagrees with its configuration')
    require(all(len(values) == 1 for values in warmups_by_repetitions.values()),
            'summary lacks the per-case provenance needed for ambiguous warmup counts')
    require(sum(row['cases'] for row in data['measurements']) == len(records),
            'measurement metadata case counts disagree with accepted records')

    samples = {}
    for item in records:
        ident = item['case']['id']
        expected_n = 30 if item['case'].get('repeat_of') is not None else 15
        for arm in ARMS:
            for metric in ('cpu_seconds', 'wall_seconds', 'max_rss_kib'):
                require(item['arms'][arm][metric]['n'] == expected_n,
                        ident + ': expected ' + str(expected_n) + ' timed samples per arm')
        require(expected_n in warmups_by_repetitions,
                ident + ': timed samples have no matching measurement configuration')
        samples[ident] = expected_n
        for metric in METRICS:
            position(item, metric)
    for repeat in repeats:
        case = repeat['case']
        require(case['repeat_of'] in original_ids,
                case['id'] + ': repeat_of does not name an accepted original configuration')
        original = by_id[case['repeat_of']]['case']
        for key in MATCHING_PARAMETERS:
            require(case.get(key) == original.get(key),
                    case['id'] + ': repeat changes conversion parameter ' + key)

    def totals(items):
        timing = sum(2 * samples[item['case']['id']] for item in items)
        conversions = sum(2 * (1 + next(iter(warmups_by_repetitions[
            samples[item['case']['id']]])) + samples[item['case']['id']]) for item in items)
        return conversions, timing

    ordinary_conversions, ordinary_timing = totals(originals)
    repeat_conversions, repeat_timing = totals(repeats)
    require(ordinary_conversions + repeat_conversions == data['conversions'],
            'accepted conversion totals disagree with summary')
    require(ordinary_timing + repeat_timing == data['timing_conversions'],
            'accepted timing totals disagree with summary')
    for metric in METRICS:
        require(counts(records, metric) == data['counts'][metric],
                'recomputed interval counts disagree with summary')

    out = ['## Production performance results', '']
    out.append(
        'The accepted evidence covers **70 distinct configurations: 49 primary cases and '
        '21 revised controls**, plus **' + str(len(repeats)) + ' diagnostic repeat records** '
        'identified by `case.repeat_of`. The primary/control configurations contribute '
        f'{ordinary_conversions:,} accepted conversions, including {ordinary_timing:,} timed '
        'conversions. The repeats contribute '
        f'{repeat_conversions:,} accepted conversions, including {repeat_timing:,} timed '
        f'conversions. The combined total is {data["conversions"]:,} accepted conversions '
        f'and {data["timing_conversions"]:,} timed conversions across {len(records)} case '
        'records. A diagnostic repeat is another observation of an existing configuration, '
        'not an additional distinct workload.')
    out.extend(['',
        'Accepted counts exclude partial rows and failed or truncated conversions. '
        'The recovered complete primary cases, replacement final short case, revised '
        'controls, and diagnostic repeats keep their separate source receipts. Every '
        'accepted conversion passed output-length and baseline-versus-candidate '
        'signed-32 sample-identity checks at matching parameters and buffer settings.', ''])

    count_rows = []
    for label, items in (('Primary configurations', primary),
                         ('Revised controls', controls),
                         ('All distinct configurations', originals),
                         ('Diagnostic repeat records', repeats)):
        stat = counts(items, 'cpu_seconds')
        count_rows.append((label, len(items), stat['above_one'], stat['includes_one'], stat['below_one']))
    out.extend([table(
        ('CPU interval classification', 'Records', 'Wholly above 1', 'Includes 1', 'Wholly below 1'),
        count_rows), '',
        'These are counts of per-case descriptive intervals. The combined configuration '
        'row includes the primary and control rows; it is not a third set of tests. '
        'Repeat rows are kept separate, and the intervals are not simultaneous '
        'family-wise confidence bounds. Ratios are original time divided by candidate '
        'time, so values above one favor the candidate.', ''])

    def noisy_arms(items):
        return sum((item['arms'][arm]['cpu_seconds']['relative_mad'] or 0) > 0.02
                   for item in items for arm in ARMS)

    out.append(
        f'CPU relative MAD exceeds 2% in {noisy_arms(originals)} of {2 * len(originals)} '
        f'primary/control arm distributions and {noisy_arms(repeats)} of '
        f'{2 * len(repeats)} repeat arm distributions. Each arm distribution is the '
        'set of repeated baseline or candidate timings for one case. The virtual host '
        'was not qualified for frequency, interference, or isolation; these observations '
        'describe this run and are not a prepared physical-host performance guarantee.')

    selected_pcm = [by_id[ident] for ident in PCM_REPRESENTATIVES]
    out.extend(['', '### Representative PCM conversions', '',
        'All seven rows use stereo PCM and very-high quality (`rate -v`). CPU times '
        'are independent arm medians in seconds. The paired ratio is computed from '
        'the timing pairs and need not equal the ratio of those two medians.', '',
        table(('Conversion (kHz)', 'Input audio (s)', 'Baseline CPU (s)', 'Candidate CPU (s)',
               'Paired CPU speedup [95% interval]'),
              [(rate_label(item), number(item['case']['seconds']),
                median(item, 'baseline', 'cpu_seconds'), median(item, 'candidate', 'cpu_seconds'),
                ratio(item)) for item in selected_pcm]), '',
        'The following absolute values use **baseline → candidate** in each cell. '
        'Audio seconds per clock second measure conversion throughput; the audio duration '
        'does not multiply by channel count. Peak RSS is the median of per-child '
        '`wait4` maxima and includes the process-launch footprint.', '',
        table(('Conversion (kHz)', 'Audio s / CPU s', 'Audio s / wall s', 'Median peak RSS (KiB)'),
              [(rate_label(item), paired_values(item, 'audio_seconds_per_cpu_second'),
                paired_values(item, 'audio_seconds_per_wall_second'),
                paired_values(item, 'max_rss_kib', summary=True)) for item in selected_pcm])])

    out.extend(['', '### PCM buffer and quality controls', '',
        'All twelve accepted PCM controls passed the execution, output-length and '
        'sample-identity checks. Buffer values are application bytes, not internal FIR '
        'input lengths. The reverse small-buffer control uses 128 bytes after the '
        'inherited 32/64-byte truncation was diagnosed; the valid forward control '
        'retains 32 bytes.', '',
        table(('Conversion (kHz)', 'Control', 'Input audio (s)', 'Paired CPU speedup [95% interval]'),
              [(rate_label(by_id[ident]),
                ('buffer ' + str(by_id[ident]['case']['buffer']) + ' bytes; `rate -v`')
                if ident.startswith('pcm_buffer') else
                ('quality `rate ' + by_id[ident]['case']['quality'] + '`'),
                number(by_id[ident]['case']['seconds']), ratio(by_id[ident]))
               for ident in PCM_CONTROLS])])

    out.extend(['', '### Native DSD and stereo continuity observations', '',
        'The first table keeps all three six-channel mastering-v2 decodes to '
        '176.4 kHz, including unfavorable results. These native-family observations '
        'must not be presented as evidence that every DSD route benefits from the '
        'rational-FIR change.', '',
        table(('Source', 'Baseline CPU (s)', 'Candidate CPU (s)',
               'Paired CPU speedup [95% interval]'),
              [('DSD' + str(by_id[ident]['case']['input_hz'] // 44100),
                median(by_id[ident], 'baseline', 'cpu_seconds'),
                median(by_id[ident], 'candidate', 'cpu_seconds'), ratio(by_id[ident]))
               for ident in DSD_NATIVE]), '',
        'Four DSD256 stereo continuity controls retain both mastering versions and '
        '176.4/352.8 kHz outputs. Their comparator is this session\'s frozen CLI. '
        'They do not replace the historical physical-host comparison or transfer '
        'its speedup to a rebuilt legacy comparator.', '',
        table(('Mastering profile', 'Output (kHz)', 'Baseline CPU (s)', 'Candidate CPU (s)',
               'Paired CPU speedup [95% interval]'),
              [('v1' if '.v1.' in by_id[ident]['case']['profile'] else 'v2',
                number(by_id[ident]['case']['output_hz'] / 1000),
                median(by_id[ident], 'baseline', 'cpu_seconds'),
                median(by_id[ident], 'candidate', 'cpu_seconds'), ratio(by_id[ident]))
               for ident in DSD_CONTINUITY])])
    tier_ratios = [by_id[ident]['comparisons']['cpu_seconds']['median_speedup'] for ident in DSD_TIERS]
    out.extend(['',
        'The five explicit DSD FIR dispatch controls (scalar, SSE2, AVX1, AVX2, '
        'AVX-512) have paired median CPU ratios from ' + number(min(tier_ratios)) + '× to '
        + number(max(tier_ratios)) + '×. Their complete intervals and absolute timings '
        'remain in `BENCHMARK_TABLES.md`; every below-one interval is also listed below.'])

    out.extend(['', '### Every unfavorable CPU or wall interval', '',
        'The following table includes every accepted original or diagnostic-repeat '
        'observation whose CPU **or** wall 95% interval lies wholly below one. An '
        'original adverse result stays here even when its repeat has an interval '
        'that includes one. A short wall-only result is identified explicitly; it '
        'does not establish a sustained CPU-throughput regression.', ''])
    negative_rows = []
    for item in originals + repeats:
        case = item['case']
        for metric in METRICS:
            if position(item, metric) != 'below_one':
                continue
            group = 'Diagnostic repeat' if case.get('repeat_of') is not None else (
                'Control' if case['id'] in CONTROL_IDS else 'Primary')
            note = 'Short wall-only observation' if (
                metric == 'wall_seconds' and case['seconds'] < 1 and
                position(item, 'cpu_seconds') != 'below_one') else ''
            negative_rows.append((literal(case['id']), group,
                                  'CPU' if metric == 'cpu_seconds' else 'Wall',
                                  median(item, 'baseline', metric),
                                  median(item, 'candidate', metric), ratio(item, metric), note))
    if negative_rows:
        out.append(table(('Case', 'Evidence set', 'Clock', 'Baseline median (s)',
                          'Candidate median (s)', 'Paired speedup [95% interval]', 'Interpretation'),
                         negative_rows))
    else:
        out.append('No accepted CPU or wall interval lies wholly below one.')

    out.extend(['', '### Thirty-pair diagnostic repeats', ''])
    if repeats:
        out.append(
            'The recorded policy selected sustained cases whose original per-case CPU '
            'interval lay wholly below one. Each diagnostic uses 30 timing pairs and '
            'retains the same conversion parameters. The table reports **every** '
            'diagnostic alongside its original 15-pair observation, for both clocks. '
            'This is a stability check on selected cases, not replacement evidence '
            'or a correction for testing many cases.')
        out.extend(['', table(('Original case', 'Original CPU ratio [95% interval]',
                               'Repeat CPU ratio [95% interval]', 'Original wall ratio [95% interval]',
                               'Repeat wall ratio [95% interval]'),
                              [(literal(item['case']['repeat_of']),
                                ratio(by_id[item['case']['repeat_of']]), ratio(item),
                                ratio(by_id[item['case']['repeat_of']], 'wall_seconds'),
                                ratio(item, 'wall_seconds')) for item in repeats])])
        for item in repeats:
            original = by_id[item['case']['repeat_of']]
            require(original['case']['seconds'] >= 1 and
                    position(original, 'cpu_seconds') == 'below_one',
                    'diagnostic repeat does not match the recorded selection policy')
            state = position(item, 'cpu_seconds')
            label = literal(item['case']['repeat_of'])
            if state == 'includes_one':
                interpretation = (
                    'The repeat of ' + label + ' has a CPU interval that includes one. '
                    'The original wholly below-one CPU interval was not reproduced in '
                    'this repeat; this is **not proof of no regression**, and the '
                    'original result remains part of the evidence.')
            elif state == 'below_one':
                interpretation = (
                    'The repeat of ' + label + ' also has a CPU interval wholly below '
                    'one. Its unfavorable direction persists in this diagnostic; '
                    'the original and repeated estimates are both retained.')
            else:
                interpretation = (
                    'The repeat of ' + label + ' has a CPU interval wholly above one, '
                    'opposite to the original interval. The differing observations '
                    'show instability across runs and do not erase the original '
                    'unfavorable result or establish a universal absence of regression.')
            out.extend(['', interpretation])
    else:
        out.append('No diagnostic repeat records are present in this accepted summary.')

    out.extend(['',
        'The full per-case medians, dispersion, throughput, RSS and intervals are in '
        '`BENCHMARK_TABLES.md`. The authoritative full-precision values are in '
        '`benchmark-summary.json`; narrative tables use six significant digits. '
        'The consolidated summary used for this section has SHA-256 '
        '`' + summary_sha256 + '`.', ''])
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to replace an existing performance section')
    if args.output.suffix.lower() != '.md':
        parser.error('--output must name a Markdown .md file')
    try:
        raw = args.summary.read_bytes()
        section = build_section(json.loads(raw), hashlib.sha256(raw).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(section)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output), 'summary': str(args.summary),
                      'summary_sha256': hashlib.sha256(raw).hexdigest()}))


if __name__ == '__main__':
    main()
