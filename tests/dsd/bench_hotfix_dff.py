#!/usr/bin/env python3
"""Paired P05-before/P05-after DFF benchmark; not a P01-to-P02 gate substitute.

Both P05 arms receive the same explicit channel-layout-loss permission for a
null sink. A repack comparison must write identical bytes; disagreement is a
hard error, never an excuse to remove a workload from the measured set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import resource
import subprocess
import tempfile

from bench_read_p02 import dff_bytes, summarize


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary: Path, source: Path, output: Path, sink: str,
        cpu: int) -> tuple[int, float, str, str | None]:
    if output.exists():
        output.unlink()
    argv = ['taskset', '-c', str(cpu), str(binary),
            '--dsd-layout-loss', 'warn', '--buffer', '65536', str(source)]
    argv += ['-t', 'null', '-'] if sink == 'null' else [str(output)]
    start = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = subprocess.run(argv, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=120)
    end = resource.getrusage(resource.RUSAGE_CHILDREN)
    seconds = end.ru_utime + end.ru_stime - start.ru_utime - start.ru_stime
    digest = sha256(output) if proc.returncode == 0 and sink == 'repack' else None
    return proc.returncode, seconds, proc.stderr.decode(errors='replace')[-500:], digest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before-sox', type=Path, required=True)
    p.add_argument('--after-sox', type=Path, required=True)
    p.add_argument('--cpu', type=int, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--frames', type=int, default=16777216)
    p.add_argument('--pairs', type=int, default=25)
    p.add_argument('--warmups', type=int, default=2)
    p.add_argument('--working-directory', type=Path, default=Path('/dev/shm'))
    args = p.parse_args()
    if args.frames < 32768 or args.frames % 32768 or args.pairs < 15 or args.warmups < 1:
        p.error('require whole DSF blocks, >=15 pairs and >=1 warmup')
    binaries = {'before': args.before_sox.resolve(), 'after': args.after_sox.resolve()}
    reports = {}
    errors = []
    with tempfile.TemporaryDirectory(prefix='sox-ng-hotfix-bench-',
                                     dir=args.working_directory) as directory:
        temp = Path(directory)
        for channels in (2, 6):
            source = temp / f'dff-{channels}.dff'
            source.write_bytes(dff_bytes(channels, args.frames))
            for sink in ('null', 'repack'):
                timing = {'before': [], 'after': []}
                hashes = {'before': [], 'after': []}
                order = ['before', 'after'] * args.warmups
                rng = random.Random(0x502 + channels)
                for _ in range(args.pairs):
                    order.extend(('after', 'before') if rng.randrange(2)
                                 else ('before', 'after'))
                for index, name in enumerate(order):
                    output = temp / f'output-{channels}-{sink}-{name}.dff'
                    try:
                        code, cpu, stderr, digest = run(binaries[name], source,
                                                        output, sink, args.cpu)
                    except (subprocess.TimeoutExpired, OSError) as exc:
                        errors.append(f'{channels}ch {sink} {name}: {exc.__class__.__name__}')
                        continue
                    if code:
                        errors.append(f'{channels}ch {sink} {name}: exit {code}, {stderr}')
                    elif index >= 2 * args.warmups:
                        timing[name].append(cpu)
                    if digest:
                        hashes[name].append(digest)
                key = f'dff-{channels}ch-{sink}-large'
                if min(map(len, timing.values())) == args.pairs:
                    row = summarize(timing['before'], timing['after'], 0x502)
                    if sink == 'repack':
                        row['output_sha256'] = {'before': hashes['before'][0],
                                                'after': hashes['after'][0]}
                        row['all_outputs_identical'] = (
                            len(set(hashes['before'] + hashes['after'])) == 1)
                        if not row['all_outputs_identical']:
                            errors.append(f'{key}: output bytes changed')
                    reports[key] = row
                    print(f'{key}: {row["regression_percent"]:+.2f}%, '
                          f'noise {100 * row["measurement_noise"]:.2f}%', flush=True)
                else:
                    errors.append(f'{key}: incomplete pairs')
    outcome = ('failed' if errors else 'inconclusive-noise' if any(
        r['measurement_noise'] >= .02 for r in reports.values()) else 'measured')
    result = {'purpose': 'P05 input tree to hotfix, not historical P02 gate',
              'before_sha256': sha256(binaries['before']),
              'after_sha256': sha256(binaries['after']),
              'pinned_cpu': args.cpu, 'frames': args.frames,
              'pairs': args.pairs, 'warmups': args.warmups,
              'results': reports, 'errors': errors, 'status': outcome}
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{outcome}: {len(errors)} errors, {len(reports)} workloads', flush=True)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
