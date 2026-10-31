#!/usr/bin/env python3
"""Paired CPU-time and bitstream qualification for globally ISA-tuned SoX builds.

Example:
  python3 tests/dsd/bench_legacy_sdm_avx.py \
    --base /build/default/src/sox --candidate v3=/build/v3/src/sox \
    --candidate v4=/build/v4/src/sox --rounds 7 --out /tmp/legacy-avx.json

The two test inputs are created once by --base and reused by every binary.
No dependency on host-specific taskset, perf privileges or external fixtures.
Timing is total child user+system CPU, with alternating run order and SHA-256
of each completed DSF. Run when the host is otherwise idle for stable results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import tempfile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(args: list[str], *, timeout: int) -> tuple[float, str]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = subprocess.run(args, capture_output=True, env=ENV, timeout=timeout)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {args}: {result.stderr[-400:].decode(errors='replace')}")
    cpu = ((after.ru_utime + after.ru_stime)
           - (before.ru_utime + before.ru_stime))
    return cpu, result.stderr.decode(errors='replace')[-200:]


ENV = os.environ.copy()
ENV.pop('SOX_OPTS', None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--candidate', action='append', default=[], metavar='NAME=PATH', required=True)
    parser.add_argument('--rounds', type=int, default=7)
    parser.add_argument('--route-seconds', type=int, default=20)
    parser.add_argument('--native-seconds', type=int, default=10)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 3 or args.route_seconds < 1 or args.native_seconds < 1:
        parser.error('at least 3 rounds and positive input durations required')
    base = args.base.resolve(strict=True)
    candidates: dict[str, Path] = {}
    for item in args.candidate:
        if '=' not in item or not item.split('=', 1)[0]:
            parser.error('--candidate must be NAME=PATH')
        name, path = item.split('=', 1)
        if name == 'default' or name in candidates:
            parser.error(f'duplicate/reserved candidate: {name}')
        candidates[name] = Path(path).resolve(strict=True)
    binaries = {'default': base, **candidates}
    data = {
        'schema': 'legacy-sdm-cross-build-benchmark/1',
        'binary_sha256': {n: sha(p) for n, p in binaries.items()},
        'builds': {n: str(p) for n, p in binaries.items()},
        'rounds': args.rounds,
        'route_seconds': args.route_seconds,
        'native_seconds': args.native_seconds,
        'groups': [],
    }
    with tempfile.TemporaryDirectory(prefix='sdm-build-bench-') as folder:
        tmp = Path(folder)
        wav, f32 = tmp / 'route.wav', tmp / 'native.f32'
        call([str(base), '-R', '-n', '-r', '44100', '-c', '2', '-b', '24',
              str(wav), 'synth', str(args.route_seconds), 'pinknoise', 'gain', '-6'], timeout=120)
        call([str(base), '-R', '-r', '5644800', '-c', '2', '-n', '-t', 'f32',
              str(f32), 'synth', str(args.native_seconds), 'pinknoise', 'gain', '-6'], timeout=120)
        data['input_sha256'] = {'route.wav': sha(wav), 'native.f32': sha(f32)}
        for mode in ('default', 'on'):
            opts = [] if mode == 'default' else ['--sdm-guard=on']
            for group in ('route', 'sdm'):
                results: dict[str, dict] = {n: {'cpu_seconds': [], 'hashes': []} for n in binaries}
                for round_num in range(args.rounds):
                    # Rotate first/last placement to reduce systematic bias.
                    order = list(binaries)
                    if round_num & 1:
                        order.reverse()
                    for name in order:
                        output = tmp / f'{name}.{group}.{mode}.dsf'
                        output.unlink(missing_ok=True)
                        if group == 'route':
                            command = [str(binaries[name]), '-R', *opts,
                                       str(wav), '-r', '5644800', str(output)]
                        else:
                            command = [str(binaries[name]), '-R', *opts,
                                       '-t', 'f32', '-r', '5644800', '-c', '2', str(f32),
                                       '-r', '5644800', str(output), 'sdm', '-f', 'clans-4']
                        cpu, _ = call(command, timeout=180)
                        results[name]['cpu_seconds'].append(round(cpu, 8))
                        results[name]['hashes'].append(sha(output))
                canonical = results['default']['hashes'][0]
                record = {'mode': mode, 'group': group, 'bit_identical': True,
                          'samples': results, 'median_cpu': {}, 'ratios': {}}
                for name in binaries:
                    if any(d != canonical for d in results[name]['hashes']):
                        record['bit_identical'] = False
                    record['median_cpu'][name] = statistics.median(results[name]['cpu_seconds'])
                for name in candidates:
                    record['ratios'][name] = record['median_cpu'][name] / record['median_cpu']['default']
                data['groups'].append(record)
                print(f"{mode} {group}: identity={record['bit_identical']} "
                      + ' '.join(f"{name}={ratio:.4f}x" for name, ratio in record['ratios'].items()), flush=True)
    data['bit_identical'] = all(row['bit_identical'] for row in data['groups'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + '\n')
    if not data['bit_identical']:
        raise SystemExit('ERROR: output identity failed (inspect JSON)')


if __name__ == '__main__':
    main()
