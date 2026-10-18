#!/usr/bin/env python3
"""Reproduction recipe: supervise selected one-job experiment processes.

The existing p15_full_band_campaign.py dispatcher is unchanged. This script
only schedules evidence experiments and supplies an external kill deadline
in addition to the inherited per-interval Python signal deadline.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--source-root', required=True, type=Path)
    p.add_argument('--baseline-root', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--cpu-start', type=int, default=0)
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--external-seconds', type=float, default=85)
    a = p.parse_args()
    if (not 1 <= a.workers <= 8 or not math.isfinite(a.seconds) or
            not math.isfinite(a.external_seconds) or
            not 0 < a.seconds < a.external_seconds <= 3700):
        raise ValueError('invalid experiment supervision resources')
    if not set(range(a.cpu_start, a.cpu_start + a.workers)) <= os.sched_getaffinity(0):
        raise ValueError('worker CPUs outside current affinity')
    root = a.source_root.resolve(strict=True)
    baseline = a.baseline_root.resolve(strict=True) if a.baseline_root else None
    output = a.output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    run = output / 'supervision' / f'run-{time.time_ns()}-{os.getpid()}'
    run.mkdir(parents=True)
    jobs = json.loads(a.plan.read_text())['job_indices']
    if not jobs or len(jobs) != len(set(jobs)) or any(type(i) is not int for i in jobs):
        raise ValueError('empty, duplicate or malformed canonical job indices')
    harness = root / 'tests/dsd/p15_high_rate_experiment.py'
    env = os.environ.copy()
    env['OPENBLAS_NUM_THREADS'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    (run / 'request.json').write_text(json.dumps(dict(
        command=sys.argv, jobs=jobs, inherited_pythonpath=env.get('PYTHONPATH'),
        cpu_set=list(range(a.cpu_start, a.cpu_start + a.workers)),
        per_job_signal_seconds=a.seconds, per_process_kill_seconds=a.external_seconds,
        baseline=str(baseline) if baseline else None, source=str(root)), indent=2) + '\n')

    def worker(slot):
        failures = 0
        for position in range(slot, len(jobs), a.workers):
            index = jobs[position]
            variants = [('candidate', root)]
            if baseline:
                variants = [('baseline', baseline), ('candidate', root)]
                if position % 2:
                    variants.reverse()
            for label, source in variants:
                destination = output / label if baseline else output
                command = [sys.executable, str(harness), '--source-root', str(source),
                    '--job-index', str(index), '--label', label, '--output', str(destination),
                    '--seconds', str(a.seconds), '--max-nodes', '128', '--max-paths', '20000',
                    '--cpu', str(a.cpu_start + slot)]
                started = time.perf_counter()
                process = subprocess.Popen(command, cwd=root, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    start_new_session=True)
                killed = False
                try:
                    stdout, stderr = process.communicate(timeout=a.external_seconds)
                except subprocess.TimeoutExpired:
                    killed = True
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                log = dict(job_index=index, variant=label, command=command,
                    process_wall_s=time.perf_counter() - started, exit_code=process.returncode,
                    external_deadline_killed=killed, stdout=stdout, stderr=stderr)
                with (run / f'{index:05d}-{label}.json').open('x') as stream:
                    json.dump(log, stream, indent=2, sort_keys=True)
                    stream.write('\n')
                if process.returncode not in (0, 2) or killed:
                    failures += 1
                print(json.dumps(dict(job_index=index, variant=label,
                    exit_code=process.returncode, external_kill=killed,
                    wall_s=round(log['process_wall_s'], 3),
                    result=stdout.strip()[-1000:])), flush=True)
        return failures

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        failures = sum(pool.map(worker, range(a.workers)))
    print(json.dumps(dict(supervision=str(run), execution_failures=failures)), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
