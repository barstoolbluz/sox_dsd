#!/usr/bin/env python3
"""Run the focused final numerical tests with explicit source and result roots."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time


MODULES = [
    'test_p15_prover_third_pass', 'test_p15_prover_second_pass',
    'test_p15_prover_fixed_interval', 'test_p15_campaign_corrective_synthetic',
    'test_p15_src_complete_aliases', 'test_p15_campaign_dispatch_corrective',
    'test_p15_src_bound_operator', 'test_p15_src_continuum_bounds',
    'test_p15_remaining_math', 'test_p15_high_rate_independent',
    'test_p15_high_rate_population', 'test_p15_high_rate_census',
    'test_p15_high_rate_experiment', 'test_p15_high_rate_terminal_saturation',
    'test_p15_high_rate_coverage_report', 'test_p15_normative_limit_rounding']


def sources(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / 'tests/dsd').glob('*.py'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--dependency-path', type=Path)
    parser.add_argument('--cpu', type=int, default=7)
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    if args.cpu not in os.sched_getaffinity(0):
        raise ValueError('CPU unavailable')
    os.sched_setaffinity(0, {args.cpu})
    os.nice(15)
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = sources(root)
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=':'.join(str(p) for p in
                   ([args.dependency_path] if args.dependency_path else []) + [root / 'tests/dsd']))
    command = [sys.executable, '-m', 'unittest', '-v', *MODULES]
    request = dict(command=command, cwd=str(root), cpu=args.cpu,
                   external_seconds=180, source_sha256=frozen,
                   environment={k: env[k] for k in ('PYTHONPATH',
                       'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')})
    (args.output / 'RUN_COMMAND.json').write_text(json.dumps(request, indent=2, sort_keys=True) + '\n')
    start = time.perf_counter()
    process = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, start_new_session=True)
    killed = False
    try:
        log, _ = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        killed = True
        os.killpg(process.pid, signal.SIGKILL)
        log, _ = process.communicate()
    wall = time.perf_counter() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    after = sources(root)
    drift = {k: [frozen.get(k), after.get(k)] for k in set(frozen) | set(after)
             if frozen.get(k) != after.get(k)}
    result_line = next((line for line in reversed(log.splitlines())
                        if line.startswith(('OK', 'FAILED'))), 'NO RESULT')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', log)
    skipped_match = re.search(r'skipped=(\d+)', result_line)
    (args.output / 'combined.log').write_text(log)
    result = dict(status='PASS' if process.returncode == 0 and not drift and not killed else 'FAIL',
                  exit_code=process.returncode, external_kill=killed, result_line=result_line,
                  tests_run=int(match[1]) if match else None,
                  unittest_seconds=float(match[2]) if match else None,
                  skipped=int(skipped_match[1]) if skipped_match else 0,
                  wall_seconds=wall, child_cpu_seconds=usage.ru_utime + usage.ru_stime,
                  peak_child_rss_kib=usage.ru_maxrss, source_drift=drift,
                  source_files_frozen=len(frozen), qualified_release=False)
    (args.output / 'RESULT.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    manifest = ''.join(f'{sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                       for p in sorted(args.output.iterdir()) if p.is_file())
    (args.output / 'SHA256SUMS').write_text(manifest)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
