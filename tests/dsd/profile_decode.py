#!/usr/bin/env python3
"""Attribute decode CPU time without perf or per-call -pg instrumentation.

Build the optional link-only profiling executable with:
    make -C test sox_dsd_profile
Run this script against that executable AND the ordinary production executable.
The diagnostic preflight has --dsd-report; timed/profiled runs do not, unless
--with-report is explicitly selected. Raw samples, commands, output hashes and
partial progress are retained. Results describe this invocation's host only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import resource
import shutil
import statistics
import struct
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
RATES = (2822400, 5644800, 11289600)
TIERS = ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')
SEED = 0xD5D2026


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True,
                                    allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def make_fixture(path: Path, native_hz: int, channels: int, frames: int) -> None:
    """Bounded-memory, deterministic LSB-first DSF; performance stimulus only.

    One RNG stream fills channel blocks in file order. Incomplete bytes and
    blocks are zero-padded, but the declared logical bit count is exact.
    This is not independently encoded music or a mastering-quality corpus.
    """
    if native_hz not in RATES or channels not in (1, 2, 6) or frames <= 0:
        raise ValueError('unsupported fixture dimensions')
    block = 4096
    blocks = (frames + 8 * block - 1) // (8 * block)
    size = 92 + blocks * channels * block
    if size >= 1 << 64:
        raise ValueError('fixture is too large for DSF')
    header = (b'DSD ' + struct.pack('<QQQ', 28, size, 0) + b'fmt ' +
              struct.pack('<QIIIIIIQII', 52, 1, 0, channels + (channels > 4),
                          channels, native_hz, 1, frames, block, 0) +
              b'data' + struct.pack('<Q', size - 80))
    rng = random.Random(SEED)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as stream:
        stream.write(header)
        for b in range(blocks):
            remaining = min(block * 8, frames - b * block * 8)
            used_bytes = (remaining + 7) // 8
            for _ in range(channels):
                payload = bytearray(rng.getrandbits(block * 8).to_bytes(block, 'little'))
                if remaining % 8:
                    payload[used_bytes - 1] &= (1 << (remaining % 8)) - 1
                payload[used_bytes:] = bytes(block - used_bytes)
                stream.write(payload)
    temporary.replace(path)


def host() -> dict:
    cpuinfo = Path('/proc/cpuinfo')
    text = cpuinfo.read_text(errors='replace') if cpuinfo.is_file() else ''
    fields = {}
    for line in text.splitlines():
        key, sep, value = line.partition(':')
        if sep and key.strip() not in fields:
            fields[key.strip()] = value.strip()
    return dict(platform=platform.platform(), machine=platform.machine(),
                cpu_model=fields.get('model name'), cpu_vendor=fields.get('vendor_id'),
                microcode=fields.get('microcode'),
                hypervisor_flag_observed=('hypervisor' in fields['flags'].split()
                    if 'flags' in fields else None),
                affinity=sorted(os.sched_getaffinity(0))
                    if hasattr(os, 'sched_getaffinity') else None,
                physical_host_status='not established by this tool',
                governor_and_boost='not changed by this tool; record externally',
                io='input and WAV output included; filesystem is the selected results directory')


def parse_flat_profile(text: str) -> dict:
    """Preserve gprof's sampled executable-time denominator, not wall time."""
    match = re.search(r'Each sample counts as ([0-9.]+) seconds', text)
    rows = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        try:
            percent, _, seconds = map(float, fields[:3])
        except ValueError:
            continue
        if not all(math.isfinite(v) for v in (percent, seconds)):
            raise ValueError('nonfinite gprof result')
        rows.append(dict(symbol=fields[-1], sampled_percent=percent,
                         sampled_self_seconds=seconds))
    total = sum(row['sampled_self_seconds'] for row in rows)
    if not match or not rows or total <= 0:
        raise ValueError('no positive executable CPU samples; use a longer source')
    return dict(sample_period_seconds=float(match.group(1)),
                sampled_executable_seconds=total, functions=rows,
                denominator='sampled executable CPU time, not total wall time; '
                            'shared libraries and kernel time are not attributed',
                caveat='statistical samples; adjacent symbols may share histogram bins; '
                       'absence of samples is not proof that a function did not run')



def run_bounded(command: list[str], *, cwd: Path, env: dict, stdout, stderr,
                timeout: float) -> tuple[int, bool]:
    """Block on child exit, with a watchdog rather than timeout polling.

    Popen.wait(timeout=...) polls at up to 50 ms intervals on POSIX. That is
    acceptable supervision but adds inappropriate quantization to short wall
    timings. A sleeping watchdog preserves the blocking wait and file-backed,
    bounded-memory logs. Only the direct conversion child is launched here.
    """
    expired = threading.Event()
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=stdout, stderr=stderr) as child:
        def terminate() -> None:
            if child.poll() is None:
                expired.set()
                child.kill()
        watchdog = threading.Timer(timeout, terminate)
        watchdog.daemon = True
        watchdog.start()
        try:
            returncode = child.wait()
        except BaseException:
            child.kill()
            child.wait()
            raise
        finally:
            watchdog.cancel()
            watchdog.join()
    return returncode, expired.is_set()


def summarize(values: list[float]) -> dict:
    median = statistics.median(values)
    return dict(samples=len(values), median=median, minimum=min(values), maximum=max(values),
                mad=statistics.median(abs(v - median) for v in values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sox', type=Path, default=ROOT / 'src/sox_ng')
    parser.add_argument('--profile-sox', type=Path, default=ROOT / 'test/sox_dsd_profile')
    parser.add_argument('--source', type=Path, help='optional existing DSF or DFF source, never modified')
    parser.add_argument('--results', type=Path, required=True, help='new or empty output directory')
    parser.add_argument('--tiers', nargs='+', choices=TIERS, default=list(TIERS))
    parser.add_argument('--native-rate', type=int, choices=RATES, default=RATES[0])
    parser.add_argument('--pcm-rate', type=int, default=88200)
    parser.add_argument('--channels', type=int, choices=(1, 2, 6), default=2)
    parser.add_argument('--seconds', type=float, default=4.)
    parser.add_argument('--repetitions', type=int, default=15)
    parser.add_argument('--profile-repetitions', type=int, default=8)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--cpu', type=int, help='pin this process and its children to one allowed CPU')
    parser.add_argument('--with-report', action='store_true', help='explicit observational-overhead control')
    parser.add_argument('--timeout', type=float, default=300.)
    args = parser.parse_args()
    if (len(set(args.tiers)) != len(args.tiers) or
        not math.isfinite(args.seconds) or not .02 <= args.seconds <= 60 or
        not 15 <= args.repetitions <= 1000 or not 1 <= args.profile_repetitions <= 1000 or
        not 0 <= args.warmups <= 100 or not 1 <= args.pcm_rate <= 705600 or
        not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error('invalid or duplicate benchmark parameters; at least 15 timed repetitions required')
    args.sox = args.sox.resolve()
    args.profile_sox = args.profile_sox.resolve()
    for executable in (args.sox, args.profile_sox):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser.error(f'missing executable: {executable}')
    if not shutil.which('gprof'):
        parser.error('gprof is required (the optional executable must be linked with -pg)')
    if args.cpu is not None:
        if not hasattr(os, 'sched_getaffinity') or args.cpu not in os.sched_getaffinity(0):
            parser.error('--cpu is not in this process\'s permitted affinity set')
        os.sched_setaffinity(0, {args.cpu})
    dest = args.results.resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        parser.error('results must be new or empty; existing evidence will not be overwritten')
    if args.source is not None and not args.source.is_file():
        parser.error('source file does not exist')
    dest.mkdir(parents=True, exist_ok=True)
    report = dict(schema='dsd/decode-attribution/1', status='RUNNING', host=host(),
                  configuration=dict(tiers=args.tiers, native_rate=args.native_rate,
                      pcm_rate=args.pcm_rate, channels=args.channels, seconds=args.seconds,
                      repetitions=args.repetitions, profile_repetitions=args.profile_repetitions,
                      warmups=args.warmups, random_seed=SEED, reporting_in_timed_runs=args.with_report,
                      threads=1, buffer_bytes=8192,
                      wall_timer='perf_counter around blocking wait; watchdog only on timeout'),
                  executable_sha256=dict(normal=sha256(args.sox), profile=sha256(args.profile_sox)),
                  source_sha256={str(p.relative_to(ROOT)): sha256(p) for p in
                      [ROOT / 'tests/dsd/profile_decode.py', *sorted((ROOT / 'src').glob('dsd*.c')),
                       ROOT / 'src/dsd_coeffs.h']},
                  commands=[], raw=[], preflight={}, summary={}, profiles={}, errors=[],
                  qualification='attribution and local timing only; no physical-host or default promotion')
    manifest = dest / 'attribution.json'
    atomic_json(manifest, report)
    def save() -> None:
        atomic_json(manifest, report)
    def invoke(command: list[str], directory: Path, environment: dict, label: str) -> dict:
        directory.mkdir(parents=True, exist_ok=True)
        stdout = directory / (label + '.stdout.txt')
        stderr = directory / (label + '.stderr.txt')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        with stdout.open('w') as out, stderr.open('w') as err:
            returncode, timed_out = run_bounded(command, cwd=directory,
                env=environment, stdout=out, stderr=err, timeout=args.timeout)
        elapsed = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row = dict(command=command, directory=str(directory.relative_to(dest)),
                   stdout=str(stdout.relative_to(dest)), stderr=str(stderr.relative_to(dest)),
                   exit=returncode, timed_out=timed_out, wall_seconds=elapsed,
                   cpu_user_seconds=after.ru_utime-before.ru_utime,
                   cpu_system_seconds=after.ru_stime-before.ru_stime)
        report['commands'].append(row)
        save()
        if timed_out:
            raise RuntimeError(f'{label}: exceeded {args.timeout:g}s; see {stderr.relative_to(dest)}')
        if returncode:
            raise RuntimeError(f'{label}: exit {returncode}; see {stderr.relative_to(dest)}')
        return row
    def convert(executable: Path, source: Path, directory: Path, tier: str,
                reporting: bool) -> dict:
        target = directory / 'output.wav'
        env = dict(os.environ, SOX_OPTS='', OMP_NUM_THREADS='1', LC_ALL='C',
                   SOX_DSD_KERNEL_FIR=tier, SOX_DSD_KERNEL_SDM='not-used',
                   LSX_DSD_FIR_KERNEL='not-used', LSX_DSD_SDM_KERNEL='not-used')
        # An inherited GMON_OUT_PREFIX must not send evidence outside this run.
        env.pop('GMON_OUT_PREFIX', None)
        command = [str(executable), '--single-threaded', '--dsd-mode', 'auto', '-D',
                   '--buffer', '8192']
        if reporting:
            command += ['--dsd-report', str(directory / 'conversion.json')]
        command += [str(source), '-r', str(args.pcm_rate), '-e', 'signed-integer',
                    '-b', '32', str(target)]
        row = invoke(command, directory, env, 'convert')
        row = dict(row, tier=tier, output_sha256=sha256(target), output_bytes=target.stat().st_size)
        target.unlink()
        return row
    try:
        source = args.source.resolve() if args.source else dest / 'fixture.dsf'
        if not args.source:
            make_fixture(source, args.native_rate, args.channels, round(args.seconds*args.native_rate))
        report['input'] = dict(path=str(source), sha256=sha256(source), bytes=source.stat().st_size,
                               kind='user supplied' if args.source else 'seeded random bits; performance only')
        save()
        for tier in args.tiers:
            directory = dest / 'preflight' / tier
            receipt = convert(args.sox, source, directory, tier, True)
            facts = json.loads((directory / 'conversion.json').read_text())
            decoders = facts.get('processing', {}).get('decoder', [])
            if (facts.get('status') != 'complete' or not decoders or
                any(d.get('fir_kernel_actual') != tier for d in decoders)):
                raise ValueError(f'{tier}: preflight did not verify the actual forced FIR')
            if (facts['output']['channels'] != args.channels or
                any(d['source_native_hz'] != args.native_rate for d in decoders)):
                raise ValueError('source native rate/channels do not match the requested case')
            report['preflight'][tier] = dict(receipt=receipt, decoder=decoders,
                                             report_sha256=sha256(directory / 'conversion.json'))
            save()
        order = random.Random(SEED)
        for warmup, count in ((True, args.warmups), (False, args.repetitions)):
            for repeat in range(count):
                tiers = list(args.tiers)
                order.shuffle(tiers)
                for tier in tiers:
                    directory = dest / ('warmup' if warmup else 'timing') / f'{repeat:03d}-{tier}'
                    row = convert(args.sox, source, directory, tier, args.with_report)
                    if row['output_sha256'] != report['preflight'][tier]['receipt']['output_sha256']:
                        raise ValueError(f'{tier}: output changed between preflight and timed run')
                    report['raw'].append(dict(row, repeat=repeat, warmup=warmup))
                    save()
        for tier in args.tiers:
            rows = [r for r in report['raw'] if r['tier'] == tier and not r['warmup']]
            report['summary'][tier] = dict(
                wall_seconds=summarize([r['wall_seconds'] for r in rows]),
                cpu_seconds=summarize([r['cpu_user_seconds']+r['cpu_system_seconds'] for r in rows]),
                output_sha256=rows[0]['output_sha256'])
        save()
        for tier in args.tiers:
            gmons = []
            for repeat in range(args.profile_repetitions):
                directory = dest / 'profile' / tier / f'{repeat:03d}'
                row = convert(args.profile_sox, source, directory, tier, args.with_report)
                if row['output_sha256'] != report['preflight'][tier]['receipt']['output_sha256']:
                    raise ValueError(f'{tier}: profiling link changed decoded output')
                gmon = directory / 'gmon.out'
                if not gmon.is_file():
                    raise RuntimeError('no gmon.out; use the optional link-only -pg executable')
                gmons.append(gmon)
                report['raw'].append(dict(row, repeat=repeat, profiled=True,
                    gmon=str(gmon.relative_to(dest)), gmon_sha256=sha256(gmon)))
                save()
            directory = dest / 'profile' / tier
            env = dict(os.environ, LC_ALL='C')
            invoke(['gprof', '-Q', '-b', str(args.profile_sox), *map(str, gmons)],
                   directory, env, 'gprof')
            report['profiles'][tier] = parse_flat_profile((directory / 'gprof.stdout.txt').read_text())
            save()
        report['status'] = 'PASS'
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired,
            KeyboardInterrupt) as error:
        report['errors'].append(f'{type(error).__name__}: {error}')
        report['status'] = 'INCOMPLETE'
    save()
    print(report['status'], manifest, flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
