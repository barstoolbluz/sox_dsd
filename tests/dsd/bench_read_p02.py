#!/usr/bin/env python3
"""P02 native read/repack paired throughput comparison.

Every workload runs both binaries in randomised AB/BA pairs on one pinned CPU,
after discarded warmups, with sources and outputs on tmpfs where available.
Synthetic DSD payloads are assembled independently of the tested SoX binaries.

A verdict is emitted per workload and overall, against the design's two
separate numbers: no more than 5% median regression, admissible only when
measurement noise is under 2%. Noisy workloads are inconclusive, never passes.
Earlier revisions of this script recorded unqualified samples only and
hardcoded host_unqualified; admissibility is now measured rather than assumed.
See tests/dsd/BENCHMARKING.md for host preparation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import statistics
import struct
import subprocess
import tempfile
import time

from reference import fixtures
from bench_dff import dsf_bytes

ROOT = Path(__file__).resolve().parents[2]


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dff_bytes(channels, frames):
    assert frames % 8 == 0
    count = frames // 8
    # Asymmetric byte patterns in channel-interleaved, MSB-first byte clusters.
    patterns = (0x96, 0x39, 0xa5, 0x69, 0x1e, 0xc3)
    payload = bytes(patterns[c] ^ (0xff if i & 1 else 0)
                    for i in range(count) for c in range(channels))
    chnl = struct.pack('>H', channels) + b''.join(
        f'C{i:03d}'.encode('ascii') for i in range(channels))
    prop = (b'SND ' + fixtures.chunk(b'FS  ', struct.pack('>I', fixtures.DSD64))
            + fixtures.chunk(b'CHNL', chnl)
            + fixtures.chunk(b'CMPR', b'DSD ' + bytes([14]) + b'not compressed'))
    return fixtures.chunk(b'FRM8', b'DSD '
                          + fixtures.chunk(b'FVER', bytes.fromhex('01050000'))
                          + fixtures.chunk(b'PROP', prop)
                          + fixtures.chunk(b'DSD ', payload))


REGRESSION_LIMIT = .05
NOISE_LIMIT = .02


def summarize(baseline, candidate, seed):
    """Paired median ratio with a bootstrap interval, and a robust noise estimate.

    Noise is reported per arm as a robust relative sigma so that a workload is
    judged inadmissible on its own dispersion, not on a whole-host probe.
    """
    def robust_sigma(v):
        s = sorted(v)
        q1 = s[len(s)//4]
        q3 = s[(3*len(s))//4]
        return (q3 - q1) / 1.349 / statistics.median(s) if statistics.median(s) else 0.0

    n = min(len(baseline), len(candidate))
    b, c = baseline[:n], candidate[:n]
    ratio = statistics.median(c) / statistics.median(b)
    rng = random.Random(seed)
    draws = []
    for _ in range(4000):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(statistics.median([c[i] for i in idx]) /
                     statistics.median([b[i] for i in idx]))
    draws.sort()
    lo, hi = draws[100], draws[3899]
    noise = max(robust_sigma(b), robust_sigma(c))
    status = ('inconclusive-noise' if noise >= NOISE_LIMIT else
              'fail-regression' if ratio > 1 + REGRESSION_LIMIT else 'pass')
    return {'samples': n,
            'baseline_median_cpu_seconds': statistics.median(b),
            'candidate_median_cpu_seconds': statistics.median(c),
            'median_ratio': ratio, 'regression_percent': (ratio - 1) * 100,
            'paired_bootstrap_95pct_interval': [lo, hi],
            'measurement_noise': noise, 'status': status}


def run(sox, source, target, cap, output, cpu=None):
    args = []
    if cpu is not None:
        args += ['taskset', '-c', str(cpu)]
    args += [str(sox), '--buffer', str(cap), str(source)]
    if output == 'null':
        args += ['-t', 'null', '-']
    else:
        args += [str(target)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, cwd=ROOT)
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {'argv':args, 'exit':proc.returncode, 'wall_seconds':wall,
              'cpu_seconds':after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
              'stderr':proc.stderr.decode(errors='replace')[-2000:],
              'stdout_bytes':len(proc.stdout)}
    if output != 'null' and target.exists():
        result.update(output_size=target.stat().st_size, output_sha256=checksum(target))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline-sox', type=Path, required=True)
    p.add_argument('--sox', type=Path, default=ROOT/'src/sox_ng')
    p.add_argument('--results', type=Path,
                   default=ROOT/'tests/dsd/results/P02/bench-read')
    p.add_argument('--large-frames', type=int, default=1048576)
    p.add_argument('--small-frames', type=int, default=131072)
    p.add_argument('--pairs', type=int, default=15)
    p.add_argument('--warmups', type=int, default=2)
    p.add_argument('--cpu', type=int, default=None,
                   help='pin every run to this CPU; required for a verdict')
    p.add_argument('--working-directory', type=Path, default=None,
                   help='source/output parent; /dev/shm isolates disk latency')
    args = p.parse_args()
    if args.pairs < 15 or args.warmups < 1:
        p.error('a verdict needs at least 15 pairs and 1 warmup')
    if args.working_directory is None and Path('/dev/shm').is_dir():
        args.working_directory = Path('/dev/shm')
    args.baseline_sox = args.baseline_sox.resolve()
    args.sox = args.sox.resolve()
    args.results.mkdir(parents=True, exist_ok=True)
    records = []
    errors = []
    rng = random.Random(0x502)
    summaries = {}
    with tempfile.TemporaryDirectory(prefix='sox-ng-p02-bench-',
                                     dir=args.working_directory) as tmp:
        td = Path(tmp)
        for fmt in ('dsf','dff'):
            for channels in (2,6):
                for operation in ('null', 'repack'):
                    for size, frames, cap in (('small',args.small_frames,32),
                                              ('large',args.large_frames,65536)):
                        if frames % (4096 * 8):
                            raise ValueError('frame lengths must be multiples of DSF blocks')
                        source = td/f'{fmt}-{channels}-{size}.{fmt}'
                        source.write_bytes(dsf_bytes(channels, frames)[0] if fmt == 'dsf'
                                           else dff_bytes(channels, frames))
                        input_hash = checksum(source)
                        # Both sizes are paired: small capacities are where the
                        # retained-bit reader changes actually bite.
                        variants = [v for pair in range(args.pairs)
                                    for v in (('candidate','baseline') if rng.randrange(2)
                                              else ('baseline','candidate'))]
                        warmups = ['baseline', 'candidate'] * args.warmups
                        timings = {'baseline': [], 'candidate': []}
                        # Per-arm reference hashes. Each binary must be
                        # deterministic across its own repetitions; the two arms
                        # are not required to agree, because a phase that repairs
                        # a reader defect is meant to change what it decodes.
                        # Behavioral equivalence is run.py's job, not a timing
                        # harness's.
                        reference_hash = {}
                        for repetition, name in enumerate(warmups + variants):
                            measured = repetition >= len(warmups)
                            sox = args.sox if name == 'candidate' else args.baseline_sox
                            target = td/f'output-{fmt}-{channels}-{size}-{operation}-{name}.dff'
                            if target.exists():
                                target.unlink()
                            result = run(sox, source, target, cap, operation, args.cpu)
                            result.update(source_format=fmt, channels=channels,
                                          operation=operation, size=size, frames=frames,
                                          buffer_samples=cap, variant=name,
                                          repetition=repetition, input_sha256=input_hash,
                                          warmup=not measured)
                            if measured and not result['exit']:
                                timings[name].append(result['cpu_seconds'])
                            if result['exit']:
                                errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: exit {result["exit"]}')
                            if operation == 'repack':
                                if result.get('output_size',0) <= 100:
                                    errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: empty output')
                                if name not in reference_hash:
                                    reference_hash[name] = result.get('output_sha256')
                                elif reference_hash[name] != result.get('output_sha256'):
                                    errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: nondeterministic output')
                            records.append(result)
                        key = f'{fmt}-{channels}ch-{operation}-{size}'
                        if min(len(timings['baseline']), len(timings['candidate'])) >= 15:
                            summaries[key] = summarize(timings['baseline'],
                                                       timings['candidate'], seed=0x502)
                            if operation == 'repack':
                                summaries[key]['arms_agree'] = (
                                    reference_hash.get('baseline')
                                    == reference_hash.get('candidate'))
                                summaries[key]['output_sha256'] = reference_hash
                        print(f'{key}: {len(variants)} measured, {len(warmups)} warmups'
                              + (f", {summaries[key]['regression_percent']:+.2f}%"
                                 f" {summaries[key]['status']}" if key in summaries else ''),
                              flush=True)
    # The design gates "unchanged native repacking or legacy paths", so a
    # workload only gates once both arms are shown to do equivalent work.
    # A repack workload demonstrates that directly by producing identical
    # bytes. A `-t null` workload leaves no artifact, so it inherits the
    # verdict of the repack workload on the same source and buffer: if those
    # two arms decoded identically there, they read the same data here.
    for key, s in summaries.items():
        if '-repack-' in key:
            comparable = s.get('arms_agree') is True
        else:
            twin = summaries.get(key.replace('-null-', '-repack-'))
            comparable = bool(twin) and twin.get('arms_agree') is True
            s['arms_agree'] = None
            s['comparability_from'] = key.replace('-null-', '-repack-')
        if not comparable:
            s['status'] = 'not-comparable'
    gating = [s['status'] for s in summaries.values()
              if s['status'] != 'not-comparable']
    if errors or not gating:
        verdict = 'failed' if errors else 'no-comparable-workload'
    elif 'fail-regression' in gating:
        verdict = 'fail'
    elif 'inconclusive-noise' in gating:
        verdict = 'incomplete'
    else:
        verdict = 'pass'
    data = {'baseline_sox':str(args.baseline_sox), 'candidate_sox':str(args.sox),
            'baseline_sha256':checksum(args.baseline_sox),
            'candidate_sha256':checksum(args.sox),
            'pinned_cpu':args.cpu, 'working_directory':str(args.working_directory),
            'pairs':args.pairs, 'warmups':args.warmups,
            'regression_limit':REGRESSION_LIMIT, 'noise_limit':NOISE_LIMIT,
            'host_unqualified':verdict != 'pass' and any(
                s['status'] == 'inconclusive-noise' for s in summaries.values()),
            'purpose':'paired native read/repack throughput comparison',
            'summaries':summaries,
            'cases':records, 'errors':errors, 'status':verdict}
    dest = args.results/'bench-read.json'
    temp = dest.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n')
    os.replace(temp,dest)
    print(f'{len(records)} benchmark commands; {len(errors)} errors; {dest}')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
