#!/usr/bin/env python3
"""Sample actual production SRC using the existing link-only gprof technique.

Build sox_dsd_profile_linkonly with tools/build_src_optimization.py, or use
the project's profiling target after checking that only linking adds -pg.
The executable-time sample denominator excludes unprofiled shared libraries
and kernel work. This is attribution, not a hardware-counter measurement.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from bench_src_optimization import normalize, pcm_fixture, invocation, measure
from profile_decode import atomic_json, host, parse_flat_profile, sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--cases', type=Path, required=True)
    ap.add_argument('--cpu', type=int, default=0)
    ap.add_argument('--repetitions', type=int, default=4)
    a = ap.parse_args()
    exe = a.sox.resolve()
    cases = normalize(json.loads(a.cases.read_text()))
    if any(c['kind'] != 'pcm' for c in cases) or not 1 <= a.repetitions <= 100:
        ap.error('PCM cases and 1..100 repetitions required')
    if a.cpu not in os.sched_getaffinity(0) or not exe.is_file():
        ap.error('unavailable CPU or executable')
    dest = a.results.resolve()
    if dest.exists() and any(dest.iterdir()):
        ap.error('refusing nonempty results directory')
    dest.mkdir(parents=True, exist_ok=True)
    os.sched_setaffinity(0, {a.cpu})
    hardware = host()
    hardware['io'] = 'Generated raw signed-32 little-endian PCM input and output; output hashes recorded after each child exits.'
    report = dict(schema='sox/src-production-attribution/1', host=hardware,
                  executable=str(exe), executable_sha256=sha256(exe), cases=[],
                  scope='statistical production-code samples; no physical qualification')
    atomic_json(dest/'profiles.json', report)
    for case in cases:
        directory = dest/case['id']; directory.mkdir()
        fixture = directory/'input.s32'; output = directory/'output.s32'
        pcm_fixture(fixture, case['frames'], case['channels'])
        command = invocation(exe, case, fixture, output)
        # measure() deliberately strips GMON_OUT_PREFIX for ordinary benchmark
        # runs. Here gmon.out is produced in a unique directory and renamed.
        rows = []; expected = None
        for i in range(a.repetitions):
            row = measure(command, directory,
                          dict(SOX_OPTS='', LC_ALL='C', OMP_NUM_THREADS='1'),
                          180, directory/f'{i}.stdout', directory/f'{i}.stderr')
            if row['exit'] or row['timed_out']:
                raise RuntimeError(f'profiling invocation failed: {directory}')
            digest = sha256(output)
            if expected is not None and expected != digest:
                raise RuntimeError('nondeterministic profile output')
            expected = digest; row['output_sha256'] = digest; rows.append(row)
            (directory/'gmon.out').rename(directory/f'gmon.{i}')
        gcmd = ['gprof', '-b', '-p', str(exe),
                *[str(directory/f'gmon.{i}') for i in range(a.repetitions)]]
        flat = subprocess.check_output(gcmd, text=True)
        (directory/'gprof.txt').write_text(flat)
        profile = parse_flat_profile(flat)
        report['cases'].append(dict(case=case, command=command,
            input_sha256=sha256(fixture), runs=rows, gprof_command=gcmd, profile=profile))
        atomic_json(dest/'profiles.json', report)
        fixture.unlink(); output.unlink()
        print(case['id'], [(r['symbol'], r['sampled_percent'])
                           for r in profile['functions'][:5]], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
