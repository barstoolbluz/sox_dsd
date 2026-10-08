#!/usr/bin/env python3
"""P01 paired native DFF throughput comparison on identical source bytes.

Warmups and randomized AB/BA pairs use one pinned CPU. Every subprocess and
sample is saved atomically. Noisy results are inconclusive, never passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import statistics
import struct
import tempfile

from bench import atomic_json, host_info, run_command
from reference import fixtures, verify

ROOT = pathlib.Path(__file__).resolve().parents[2]


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def dsf_bytes(channels, frames):
    # Packed synthetic source; no writer under test constructs input.
    words = [bytes.fromhex(s) for s in json.loads(
        (ROOT/'tests/dsd/fixtures/p01_writer_vectors.json').read_text())['source_words_msb'][:channels]]
    reverse = bytes(int(f'{i:08b}'[::-1], 2) for i in range(256))
    channel_bytes = [((w * ((frames // 8 + len(w) - 1) // len(w)))[:frames // 8]).translate(reverse)
                     for w in words]
    blocks = frames // (8 * fixtures.BLOCK)
    payload = b''.join(ch[i * fixtures.BLOCK:(i + 1) * fixtures.BLOCK]
                       for i in range(blocks) for ch in channel_bytes)
    length = 92 + len(payload)
    typ = {1: 1, 2: 2, 6: 7}[channels]
    raw = (b'DSD ' + struct.pack('<QQQ', 28, length, 0) + b'fmt ' +
           struct.pack('<QIIIIIIQII', 52, 1, 0, typ, channels, fixtures.DSD64,
                       1, frames, fixtures.BLOCK, 0) + b'data' +
           struct.pack('<Q', 12 + len(payload)) + payload)
    expected = bytearray(channels * (frames // 8))
    for ch, data in enumerate(channel_bytes):
        expected[ch::channels] = data.translate(reverse)
    return raw, bytes(expected)


def dispersion(values):
    median = statistics.median(values)
    return dict(median_seconds=median, min_seconds=min(values), max_seconds=max(values),
                robust_relative_sigma=1.4826 * statistics.median(abs(v - median) for v in values) / median)


def interval(ratios):
    rng = random.Random(fixtures.SEED)
    medians = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(4000))
    return [medians[100], medians[3899]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline-sox', type=pathlib.Path, required=True)
    ap.add_argument('--sox', type=pathlib.Path, default=ROOT/'src/sox_ng')
    ap.add_argument('--results', type=pathlib.Path, default=ROOT/'tests/dsd/results/P01/bench-dff')
    ap.add_argument('--frames', type=int, default=8388608)
    ap.add_argument('--repetitions', type=int, default=15)
    ap.add_argument('--warmups', type=int, default=2)
    ap.add_argument('--cpu', type=int, default=None)
    ap.add_argument('--working-directory', type=pathlib.Path, default=None,
                    help='temporary input/output parent; /dev/shm isolates disk latency')
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    if args.frames <= 0 or args.frames % (8 * fixtures.BLOCK) or args.repetitions < 15 or args.warmups < 1:
        ap.error('positive whole DSF blocks, >=15 repetitions and >=1 warmup required')
    if not hasattr(os, 'sched_getaffinity'):
        ap.error('CPU affinity support is required for this comparison')
    affinity = sorted(os.sched_getaffinity(0))
    cpu = min(affinity) if args.cpu is None else args.cpu
    if cpu not in affinity: ap.error('requested CPU is outside available affinity')
    binaries = {'baseline': args.baseline_sox.resolve(), 'candidate': args.sox.resolve()}
    if not all(p.is_file() for p in binaries.values()): ap.error('missing built executable')
    args.results = args.results.resolve()
    outfile = args.results/'bench-dff.json'
    context = host_info()
    context.update(affinity=[cpu], input_rate_hz=fixtures.DSD64,
                   io_included=True, storage_directory=str(args.working_directory) if args.working_directory else 'system temporary directory',
                   rate_scope='DFF packing is rate independent; three native rates also run in bench.py')
    config = dict(frames=args.frames, repetitions=args.repetitions, warmups=args.warmups,
        cpu=cpu, seed=fixtures.SEED, binaries={k: str(v) for k, v in binaries.items()},
        binary_sha256={k: digest(v) for k, v in binaries.items()},
        benchmark_source_sha256=digest(pathlib.Path(__file__)),
        vectors_sha256=digest(ROOT/'tests/dsd/fixtures/p01_writer_vectors.json'),
        context=context, regression_limit=.05, noise_limit=.02)
    key = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    report = dict(schema='dsd-p01-native-dff-benchmark/1', config=config, config_sha256=key,
                  cases=[], status='incomplete')
    if outfile.exists():
        if not args.resume: ap.error('result exists; select --resume or a new result directory')
        report = json.loads(outfile.read_text())
        if report['config_sha256'] != key: ap.error('resume source/binary/host/configuration mismatch')
    atomic_json(outfile, report)
    by_channel = {case['channels']: case for case in report['cases']}
    rng = random.Random(fixtures.SEED)
    with tempfile.TemporaryDirectory(prefix='dsd-p01-paired-', dir=args.working_directory) as td:
        work = pathlib.Path(td)
        for nch in (1, 2, 6):
            source = work/f'input-{nch}.dsf'
            raw, expected = dsf_bytes(nch, args.frames)
            source.write_bytes(raw)
            del raw
            case = by_channel.get(nch)
            if case is None:
                orders = [rng.sample(['baseline', 'candidate'], 2) for _ in range(args.repetitions)]
                case = dict(channels=nch, source_sha256=digest(source), source_bytes=source.stat().st_size,
                            expected_audio_sha256=hashlib.sha256(expected).hexdigest(),
                            pair_orders=orders, warmups=[], pairs=[])
                report['cases'].append(case)
            else:
                # Advance the seed identically whether a case is complete or resumed.
                for _ in range(args.repetitions): rng.sample(['baseline', 'candidate'], 2)
                if case['source_sha256'] != digest(source): ap.error('resume input byte drift')

            def execute(variant):
                output = work/f'{variant}-{nch}.dff'
                (work/'time.txt').unlink(missing_ok=True)
                sample = run_command(['taskset', '-c', str(cpu), binaries[variant], '-D', source, output],
                                     work/'time.txt', 180)
                if sample['exit'] == 0:
                    written = output.read_bytes()
                    start = 122 + 4 * nch
                    audio = written[start:]
                    if variant == 'candidate':
                        # Walk the long file structurally without expanding
                        # millions of bits outside the timed process.
                        top = verify.chunks(written, 16, len(written))
                        sub = verify.chunks(written, top[1]['payload_start'] + 4, top[1]['payload_end'])
                        correct = (struct.unpack_from('>Q', written, 4)[0] == len(written) - 12 and
                                   [c['tag'] for c in top] == ['FVER', 'PROP', 'DSD '] and
                                   [c['tag'] for c in sub] == ['FS  ', 'CHNL', 'CMPR'] and
                                   top[-1]['payload_size'] == len(expected) and
                                   audio == expected)
                    else:
                        # P00 headers/first cluster are independently defective.
                        # Require the unaffected source bytes, without using them
                        # as the corrected writer's oracle.
                        correct = len(audio) == len(expected) and audio[nch:] == expected[nch:]
                    sample.update(output_sha256=hashlib.sha256(written).hexdigest(),
                                  output_bytes=len(written), native_bytes_correct=correct,
                                  frames_per_second_per_channel=args.frames/sample['wall_seconds'],
                                  aggregate_native_bits_per_second=args.frames*nch/sample['wall_seconds'],
                                  rtf_wall_seconds_per_audio_second=sample['wall_seconds']/(args.frames/fixtures.DSD64))
                    if not correct: sample['error'] = 'native output differs from independent expected payload'
                sample['variant'] = variant
                return sample

            for warm in range(args.warmups):
                if len(case['warmups']) <= warm:
                    case['warmups'].append(dict(index=warm, samples={}))
                entry = case['warmups'][warm]
                for variant in ('baseline', 'candidate'):
                    if variant in entry['samples']:
                        prior = entry['samples'][variant]
                        if prior['exit'] != 0 or prior['error']: return 1
                        continue
                    entry['samples'][variant] = execute(variant)
                    atomic_json(outfile, report)
                    if entry['samples'][variant]['exit'] != 0 or entry['samples'][variant]['error']:
                        print(json.dumps(entry)); return 1
            for index, order in enumerate(case['pair_orders']):
                if len(case['pairs']) <= index: case['pairs'].append(dict(index=index, samples={}))
                pair = case['pairs'][index]
                for variant in order:
                    if variant in pair['samples']:
                        prior = pair['samples'][variant]
                        if prior['exit'] != 0 or prior['error']: return 1
                        continue
                    pair['samples'][variant] = execute(variant)
                    atomic_json(outfile, report)
                    if pair['samples'][variant]['exit'] != 0 or pair['samples'][variant]['error']:
                        print(json.dumps(pair)); return 1
                print(f'{nch}ch paired repetition {index + 1}/{args.repetitions}', flush=True)
            values = {variant: [pair['samples'][variant]['wall_seconds'] for pair in case['pairs']]
                      for variant in binaries}
            summary = {variant: dispersion(v) for variant, v in values.items()}
            ratios = [pair['samples']['candidate']['wall_seconds']/pair['samples']['baseline']['wall_seconds']
                      for pair in case['pairs']]
            ratio = summary['candidate']['median_seconds']/summary['baseline']['median_seconds']
            ci = interval(ratios)
            noise = max(s['robust_relative_sigma'] for s in summary.values())
            status = ('inconclusive-noise' if noise >= .02 else
                      'fail-regression' if ratio > 1.05 else 'pass')
            case['summary'] = dict(variants=summary, median_wall_ratio=ratio, regression_percent=(ratio - 1)*100,
                paired_median_ratio=statistics.median(ratios), paired_bootstrap_95pct_interval=ci,
                measurement_noise=noise, status=status)
            atomic_json(outfile, report)
            print(json.dumps(dict(channels=nch, summary=case['summary'])), flush=True)
    statuses = [case['summary']['status'] for case in report['cases']]
    report['status'] = 'pass' if statuses == ['pass'] * 3 else 'incomplete' if 'inconclusive-noise' in statuses else 'fail'
    atomic_json(outfile, report)
    return 0 if report['status'] == 'pass' else 2 if report['status'] == 'incomplete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
