#!/usr/bin/env python3
"""Paired production CLI DSP measurements; no external time utility required.

Example (15 randomized pairs per case, pinned to an available CPU):
  python3 tests/dsd/bench_src_optimization.py --variants \
    baseline=/old/sox candidate=/new/sox --cpu 0 --results /tmp/src-bench

--cases accepts a JSON list of objects with id, kind (pcm|dsd), input_hz,
output_hz, channels, and seconds (or exact frames). DSD cases require a
versioned profile. Optional fields: buffer (8192), quality (-v), fir_kernel
(auto). Use --list-cases to print the representative built-in corpus.
Use --screen explicitly to permit fewer than 15 paired repetitions. A screen
cannot be reported as final performance evidence. All results remain local
host observations, not a physical-host qualification or a P15 certificate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import signal
import statistics
import subprocess
import sys
import threading
import time

import numpy as np
from profile_decode import atomic_json, host, make_fixture, sha256

ROOT = Path(__file__).resolve().parents[2]
SEED = 0x50152026


def default_cases():
    cases = []
    pairs = [(44100, 88200), (48000, 96000), (44100, 96000), (48000, 88200),
             (88200, 176400), (96000, 192000), (176400, 352800), (192000, 384000),
             (352800, 88200), (384000, 96000), (44100, 48000), (48000, 44100),
             (352800, 384000), (384000, 352800), (176400, 192000), (192000, 176400),
             (384000, 44100), (352800, 44100)]
    for a, b in pairs:
        cases.append(dict(id=f'pcm_{a}_{b}_stereo', kind='pcm', input_hz=a,
                          output_hz=b, channels=2, seconds=15))
    for channels in (1, 6):
        for a, b in ((48000, 44100), (176400, 192000)):
            cases.append(dict(id=f'pcm_{a}_{b}_{channels}ch', kind='pcm', input_hz=a,
                              output_hz=b, channels=channels, seconds=15))
    outputs = (88200, 96000, 176400, 192000, 352800, 384000)
    for i, b in enumerate(outputs):
        cases.append(dict(id=f'pcm_short_{b}', kind='pcm', input_hz=48000 if i % 2 == 0 else 44100,
                          output_hz=b, channels=1 if i % 2 == 0 else 2, frames=1013, buffer=256))
    for native in (2822400, 5644800, 11289600):
        for i, b in enumerate(outputs):
            profile = ('mastering.v1', 'wideband.v1', 'mastering.v2')[i % 3]
            cases.append(dict(id=f'dsd{native//44100}_{profile}_{b}', kind='dsd', input_hz=native,
                              output_hz=b, channels=(1, 2, 6, 2, 2, 2)[i], seconds=2,
                              profile=f'decode.{profile}.dsd{native//44100}'))
        cases.append(dict(id=f'dsd{native//44100}_short', kind='dsd', input_hz=native,
                          output_hz=192000, channels=2, frames=32771, buffer=256,
                          profile=f'decode.mastering.v2.dsd{native//44100}'))
    return cases


def normalize(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError('case list must be nonempty')
    result, seen = [], set()
    for raw in cases:
        c = dict(raw)
        ident = c.get('id', '')
        if not isinstance(ident, str) or ident in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9_.-]+', ident) or ident in seen:
            raise ValueError('case IDs must be unique path-safe names')
        seen.add(ident)
        if c.get('kind') not in ('pcm', 'dsd'):
            raise ValueError(f'{ident}: kind must be pcm or dsd')
        for key in ('input_hz', 'output_hz', 'channels'):
            if type(c.get(key)) is not int or c[key] <= 0:
                raise ValueError(f'{ident}: positive integer {key} required')
        if c['channels'] not in (1, 2, 6) or not 8000 <= c['output_hz'] <= 705600:
            raise ValueError(f'{ident}: unsupported channels or output rate')
        if 'frames' not in c:
            seconds = c.get('seconds')
            if not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or not 0 < seconds <= 60:
                raise ValueError(f'{ident}: require frames or 0 < seconds <= 60')
            c['frames'] = round(seconds * c['input_hz'])
        if type(c['frames']) is not int or not 0 < c['frames'] <= 60 * c['input_hz']:
            raise ValueError(f'{ident}: invalid frame count')
        c['seconds'] = c['frames'] / c['input_hz']
        c.setdefault('buffer', 8192)
        c.setdefault('quality', '-v')
        c.setdefault('fir_kernel', 'auto')
        if type(c['buffer']) is not int or not 32 <= c['buffer'] <= 16777216:
            raise ValueError(f'{ident}: invalid buffer size')
        if c['quality'] not in ('-q', '-l', '-m', '-g', '-h', '-v', '-e', '-u'):
            raise ValueError(f'{ident}: unsupported rate quality')
        if c['fir_kernel'] not in ('auto', 'scalar', 'sse2', 'avx1', 'avx2', 'avx512'):
            raise ValueError(f'{ident}: invalid FIR kernel')
        if c['kind'] == 'dsd':
            if c['input_hz'] not in (2822400, 5644800, 11289600):
                raise ValueError(f'{ident}: invalid DSD rate')
            legal = {f'decode.{p}.dsd{c["input_hz"]//44100}' for p in
                     ('mastering.v1', 'wideband.v1', 'mastering.v2')}
            if c.get('profile') not in legal:
                raise ValueError(f'{ident}: require a matching explicit versioned DSD profile')
        elif not 8000 <= c['input_hz'] <= 705600:
            raise ValueError(f'{ident}: invalid PCM rate')
        result.append(c)
    return result


def pcm_fixture(path, frames, channels):
    """Bounded int32 stimulus at <=1/8 full scale; fixed PCG64 generator."""
    rng = np.random.Generator(np.random.PCG64(SEED))
    with path.open('wb') as stream:
        left = frames
        while left:
            n = min(left, 65536)
            x = rng.integers(-(1 << 28), 1 << 28, size=(n, channels), dtype=np.int32)
            stream.write(x.astype('<i4', copy=False).tobytes())
            left -= n


def invocation(exe, case, fixture, output):
    command = [str(exe), '-D', '--single-threaded', '--buffer', str(case['buffer'])]
    if case['kind'] == 'pcm':
        command += ['-t', 'raw', '-e', 'signed-integer', '-b', '32', '-L',
                    '-r', str(case['input_hz']), '-c', str(case['channels']), str(fixture)]
    else:
        # The benchmark writes raw sample bytes; explicitly acknowledge that
        # this selected output carrier has no named-channel metadata fields.
        command += ['--dsd-mode', 'auto', '--dsd-decode', case['profile'],
                    '--dsd-layout-loss', 'warn', str(fixture)]
    command += ['-t', 'raw', '-e', 'signed-integer', '-b', '32', '-L',
                '-r', str(case['output_hz']), str(output)]
    if case['kind'] == 'pcm':
        command += ['rate', case['quality'], str(case['output_hz'])]
    return command


def measure(command, cwd, overrides, timeout, stdout, stderr):
    env = dict(os.environ, **overrides)
    env.pop('GMON_OUT_PREFIX', None)
    expired = threading.Event()
    with stdout.open('w') as out, stderr.open('w') as err:
        start = time.perf_counter_ns()
        child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        def stop():
            expired.set()
            try:
                os.kill(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        timer = threading.Timer(timeout, stop)
        timer.daemon = True
        timer.start()
        try:
            _, status, usage = os.wait4(child.pid, 0)
            elapsed = (time.perf_counter_ns() - start) * 1e-9
            child.returncode = os.waitstatus_to_exitcode(status)
        except BaseException:
            try:
                os.kill(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise
        finally:
            timer.cancel()
            timer.join()
    return dict(exit=child.returncode, timed_out=expired.is_set(), wall_seconds=elapsed,
                cpu_user_seconds=usage.ru_utime, cpu_system_seconds=usage.ru_stime,
                cpu_seconds=usage.ru_utime + usage.ru_stime, max_rss_kib=usage.ru_maxrss,
                minor_faults=usage.ru_minflt, major_faults=usage.ru_majflt,
                voluntary_context_switches=usage.ru_nvcsw, involuntary_context_switches=usage.ru_nivcsw)


def summary(values):
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    return dict(n=len(values), median=median, mad=mad, relative_mad=mad/median if median else None,
                minimum=min(values), maximum=max(values))


def speedup(base, candidate, metric, rng):
    ratios = [base[i][metric] / candidate[i][metric] for i in range(len(base))]
    boot = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(4000))
    return dict(paired_ratios=summary(ratios), median_ci95=[boot[100], boot[3899]],
                method='paired percentile bootstrap of median baseline/candidate ratios, 4000 resamples')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variants', nargs='+', help='unique name=executable entries, including baseline')
    ap.add_argument('--baseline', type=Path)
    ap.add_argument('--candidate', type=Path)
    ap.add_argument('--cases', type=Path)
    ap.add_argument('--list-cases', action='store_true')
    ap.add_argument('--results', type=Path)
    ap.add_argument('--cpu', type=int)
    ap.add_argument('--repetitions', type=int, default=15)
    ap.add_argument('--warmups', type=int, default=2)
    ap.add_argument('--screen', action='store_true')
    ap.add_argument('--timeout', type=float, default=180)
    ap.add_argument('--keep-fixtures', action='store_true')
    a = ap.parse_args()
    if a.list_cases:
        print(json.dumps(default_cases(), indent=2))
        return 0
    try:
        raw = json.loads(a.cases.read_text()) if a.cases else default_cases()
        cases = normalize(raw.get('cases', []) if isinstance(raw, dict) else raw)
        if a.variants and (a.baseline or a.candidate):
            raise ValueError('use --variants or --baseline and --candidate')
        entries = a.variants or [f'baseline={a.baseline}', f'candidate={a.candidate}']
        variants = {}
        for entry in entries:
            name, value = entry.split('=', 1)
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in variants:
                raise ValueError('variant names must be unique and path-safe')
            path = Path(value).resolve()
            if not path.is_file() or not os.access(path, os.X_OK):
                raise ValueError(f'executable unavailable: {path}')
            variants[name] = path
        if 'baseline' not in variants or len(variants) < 2:
            raise ValueError('need baseline and at least one candidate')
        if not hasattr(os, 'wait4') or sys.platform != 'linux':
            raise ValueError('this rusage/RSS runner requires Linux wait4')
        if not a.results or not (1 if a.screen else 15) <= a.repetitions <= 1000 or not 1 <= a.warmups <= 100:
            raise ValueError('need results, >=15 repetitions (or explicit --screen), >=1 warmup')
        if not math.isfinite(a.timeout) or a.timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        if a.cpu is not None:
            if a.cpu not in os.sched_getaffinity(0):
                raise ValueError('CPU is outside available affinity')
            os.sched_setaffinity(0, {a.cpu})
        dest = a.results.resolve()
        if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
            raise ValueError('refusing nonempty results directory')
    except (ValueError, OSError, TypeError) as exc:
        ap.error(str(exc))
    dest.mkdir(parents=True, exist_ok=True)
    hardware = host()
    hardware['io'] = 'Generated input files; raw signed-32 little-endian PCM output; all output bytes hashed after each timed child exits.'
    report = dict(schema='sox/production-dsp-paired/1', status='RUNNING', mode='SCREEN' if a.screen else 'PAIRED',
                  qualification='Local host observations; no physical-host gate, P15 certificate, or default promotion.',
                  hardware=hardware, seed=SEED, numpy_version=np.__version__, cases=cases,
                  config=dict(repetitions=a.repetitions, warmups=a.warmups, cpu=a.cpu, timeout=a.timeout,
                              timings='steady input processing plus CLI startup, input/output I/O; short cases expose startup',
                              rss='per-child wait4 ru_maxrss in KiB on Linux, including process launch footprint',
                              equality_scope='exact no-dither int32 CLI output bytes in this corpus; not a binary64 arithmetic proof',
                              keep_fixtures=a.keep_fixtures),
                  variants={n:dict(executable=str(p), sha256=sha256(p)) for n, p in variants.items()},
                  source_sha256={str(p.relative_to(ROOT)):sha256(p) for p in
                                 [Path(__file__), ROOT/'tests/dsd/profile_decode.py', *sorted((ROOT/'src').glob('*.c')), *sorted((ROOT/'src').glob('*.h'))]},
                  fixtures={}, raw=[], summaries={}, comparisons={}, errors=[])
    for name, path in variants.items():
        build_record = path.parent/'build-record.json'
        if build_record.is_file():
            report['variants'][name]['build_record'] = json.loads(build_record.read_text())
    save = lambda: atomic_json(dest/'measurements.json', report)
    save()
    rng = random.Random(SEED)
    try:
        for case in cases:
            directory = dest/case['id']; directory.mkdir()
            fixture = directory/('input.dsf' if case['kind'] == 'dsd' else 'input.s32')
            if case['kind'] == 'dsd':
                make_fixture(fixture, case['input_hz'], case['channels'], case['frames'])
            else:
                pcm_fixture(fixture, case['frames'], case['channels'])
            report['fixtures'][case['id']] = dict(sha256=sha256(fixture), bytes=fixture.stat().st_size,
                generator='profile_decode.make_fixture' if case['kind']=='dsd' else 'PCG64 bounded signed-int32')
            overrides = dict(SOX_OPTS='', LC_ALL='C', OMP_NUM_THREADS='1', SOX_DSD_KERNEL_FIR=case['fir_kernel'])
            expected_frames = (case['frames'] * case['output_hz'] + case['input_hz']//2)//case['input_hz']
            reference = None
            for phase, count in (('preflight', 1), ('warmup', a.warmups), ('timing', a.repetitions)):
                for repeat in range(count):
                    order = list(variants)
                    rng.shuffle(order)
                    if phase == 'preflight':
                        order = ['baseline'] + [name for name in order if name != 'baseline']
                    for position, name in enumerate(order):
                        label = f'{phase}-{repeat:03d}-{name}'
                        output = directory/(label+'.s32')
                        command = invocation(variants[name], case, fixture, output)
                        row = dict(case=case['id'], variant=name, phase=phase, repeat=repeat, position=position,
                                   command=command, env_overrides=overrides,
                                   stdout=str((directory/(label+'.stdout.txt')).relative_to(dest)),
                                   stderr=str((directory/(label+'.stderr.txt')).relative_to(dest)))
                        row.update(measure(command, directory, overrides, a.timeout, dest/row['stdout'], dest/row['stderr']))
                        report['raw'].append(row); save()
                        if row['exit'] or row['timed_out']:
                            raise RuntimeError(f'{case["id"]}/{label}: execution failed; see retained stderr')
                        row.update(output_sha256=sha256(output), output_bytes=output.stat().st_size,
                                   output_frames=output.stat().st_size//(4*case['channels']))
                        if row['output_bytes'] != expected_frames*case['channels']*4:
                            raise RuntimeError(f'{case["id"]}/{label}: unexpected output length')
                        if reference is None:
                            reference = row['output_sha256']
                        row['bit_identical_to_baseline'] = row['output_sha256'] == reference
                        save()
                        if not row['bit_identical_to_baseline']:
                            raise RuntimeError(f'{case["id"]}/{label}: output differs from baseline')
                        output.unlink()
            rows = {name:[r for r in report['raw'] if r['case']==case['id'] and r['variant']==name and r['phase']=='timing'] for name in variants}
            for name, measured in rows.items():
                values = {key:summary([r[key] for r in measured]) for key in ('cpu_seconds', 'wall_seconds', 'max_rss_kib')}
                values.update(audio_seconds_per_wall_second=case['seconds']/values['wall_seconds']['median'],
                              audio_seconds_per_cpu_second=case['seconds']/values['cpu_seconds']['median'],
                              output_samples_per_wall_second=expected_frames*case['channels']/values['wall_seconds']['median'],
                              output_samples_per_cpu_second=expected_frames*case['channels']/values['cpu_seconds']['median'],
                              observed_relative_mad_above_2pct=any((values[k]['relative_mad'] or 0) > .02 for k in ('cpu_seconds','wall_seconds')))
                report['summaries'][case['id']+'/'+name] = values
                if name != 'baseline':
                    report['comparisons'][case['id']+'/'+name] = {metric:speedup(rows['baseline'], measured, metric, rng) for metric in ('cpu_seconds','wall_seconds')}
            if not a.keep_fixtures:
                fixture.unlink()
            save()
            print(f'PASS {case["id"]}: paired output identity, {a.repetitions} timing repetitions', flush=True)
        report['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        report['status'] = 'INCOMPLETE' if isinstance(exc, KeyboardInterrupt) else 'FAIL'
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    save()
    # Seal the final receipt after all timed children have exited. A separate
    # small completion record makes a missing/stale final receipt detectable.
    receipt = dest/'measurements.json'
    with receipt.open('rb') as stream:
        os.fsync(stream.fileno())
    atomic_json(dest/'completion.json', dict(
        status=report['status'], measurement_sha256=sha256(receipt),
        raw_rows=len(report['raw']), summarized_cases=len(report['comparisons']),
        errors=report['errors']))
    with (dest/'completion.json').open('rb') as stream:
        os.fsync(stream.fileno())
    directory_fd = os.open(dest, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(report['status'], dest/'measurements.json', flush=True)
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
