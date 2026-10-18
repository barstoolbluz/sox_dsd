#!/usr/bin/env python3
"""One immutable canonical P15 experiment, with explicit prover isolation.

This evidence harness reuses the canonical worklist and existing signal
deadline; it does not change the campaign dispatcher or release policy.
Invoke in an externally supervised fresh process for a strict wall limit.
"""
from __future__ import annotations

import argparse
import cProfile
import importlib
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import pstats
import resource
import sys
import tempfile
import time


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def publish(path, data):
    """Exclusive publication, including an exact concurrent-content check."""
    if path.is_symlink():
        raise ValueError('symlink experiment receipt')
    fd, temporary = tempfile.mkstemp(prefix='.high-rate-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError('immutable experiment publication conflict')
    finally:
        os.unlink(temporary)


def loaded_code(base):
    """Assert actual imported numerical modules come from the named tree."""
    result = {}
    for name, module in sorted(sys.modules.items()):
        if not name.startswith('p15_') or not getattr(module, '__file__', None):
            continue
        path = Path(module.__file__).resolve()
        if path.parent != base:
            raise ValueError('mixed prover implementations: ' + name + ' at ' + str(path))
        result[path.name] = file_sha(path)
    if 'p15_src_stagewise_continuum.py' not in result:
        raise ValueError('prover module not loaded')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--job-index', type=int, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--max-nodes', type=int, default=128)
    parser.add_argument('--max-paths', type=int, default=20000)
    parser.add_argument('--cpu', type=int)
    parser.add_argument('--profile-cost', action='store_true')
    args = parser.parse_args()
    if (not math.isfinite(args.seconds) or not 0 < args.seconds <= 3600 or
            not 1 <= args.max_nodes <= 131072 or not 1 <= args.max_paths <= 100000):
        raise ValueError('invalid bounded experiment resources')
    process_started = time.perf_counter()
    if args.cpu is not None:
        if args.cpu not in os.sched_getaffinity(0):
            raise ValueError('requested CPU outside permitted affinity')
        os.sched_setaffinity(0, {args.cpu})
    root = args.source_root.resolve(strict=True)
    base = root / 'tests/dsd'
    if not (base / 'p15_src_stagewise_continuum.py').is_file():
        raise ValueError('not a source tree containing the P15 prover')
    harness_hash = file_sha(__file__)
    before_import = {path.name: file_sha(path) for path in base.glob('p15_*.py')}
    # The script itself may live in the candidate tree while measuring the
    # baseline. Never leave that implicit script directory ahead of baseline.
    sys.path.insert(0, str(base))
    import mpmath
    import numpy
    import p15_full_band_campaign as campaign
    import p15_src_stagewise_continuum as prover
    from p15_src_capture_matrix import verify_pair, DEFAULT
    # The third-pass recurrence imports this optional acceleration lazily.
    # Load it before freezing the actual module inventory for both variants.
    if (base / 'p15_src_fixed_interval.py').is_file():
        importlib.import_module('p15_src_fixed_interval')
    code = loaded_code(base)
    if any(before_import.get(name) != value for name, value in code.items()):
        raise ValueError('prover sources changed during import')
    jobs = campaign.canonical_plan()
    if not 0 <= args.job_index < len(jobs):
        raise ValueError('canonical job index out of range')
    job = jobs[args.job_index]
    binding = campaign.bindings()
    pair = DEFAULT / f"{job['intermediate_hz']}-{job['output_hz']}"
    snapshot_hash = file_sha(pair / 'stage-snapshot.json')
    operator_binding_hash = file_sha(pair / 'operator-binding.json')
    _, operator = verify_pair(pair, job['intermediate_hz'], job['output_hz'])
    if (loaded_code(base) != code or campaign.bindings() != binding or
            file_sha(pair / 'stage-snapshot.json') != snapshot_hash or
            file_sha(pair / 'operator-binding.json') != operator_binding_hash or
            file_sha(__file__) != harness_hash):
        raise ValueError('prover or bound inputs changed during operator verification')
    identity = dict(job=job, binding=binding, prover_code_sha256=code,
        harness_sha256=harness_hash, label=args.label,
        stage_snapshot_sha256=snapshot_hash,
        verified_operator_binding_sha256=operator_binding_hash,
        resources=dict(seconds=args.seconds, max_nodes=args.max_nodes,
                       max_paths=args.max_paths, cpu=args.cpu),
        profiling_enabled=args.profile_cost)
    output = args.output.absolute()
    if output.is_symlink():
        raise ValueError('symlink experiment directory')
    output.mkdir(parents=True, exist_ok=True)
    destination = campaign.receipt_path(output, job)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError('unsafe existing experiment receipt')
        prior = json.loads(destination.read_text())
        if prior.get('experiment_identity') != identity:
            raise ValueError('existing experiment belongs to different inputs/code/budget')
        campaign.check_one(output, job, binding)
        print(json.dumps(dict(action='SKIP', job_index=args.job_index,
            cell=job['cell_id'], status=prior['certificate']['status'],
            receipt=str(destination)), sort_keys=True), flush=True)
        return 0
    profile = cProfile.Profile() if args.profile_cost else None
    if profile:
        profile.enable()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        with campaign.interval_deadline(args.seconds):
            result = prover.certificate(job['profile'], operator, job['lo'], job['hi'],
                mode=job['mode'], max_nodes=args.max_nodes, max_paths=args.max_paths)
    except campaign.IntervalBudgetExpired:
        result = dict(status='OPEN', reason='interval_wall_clock_budget_exhausted',
            qualified_release=False, certified_hz=[job['lo'], job['hi']],
            band_kind=job['mode'], input_hz=job['intermediate_hz'],
            output_hz=job['output_hz'])
    finally:
        elapsed = time.perf_counter() - wall_start
        cpu_elapsed = time.process_time() - cpu_start
        if profile:
            profile.disable()
    if (loaded_code(base) != code or campaign.bindings() != binding or
            file_sha(pair / 'stage-snapshot.json') != snapshot_hash or
            file_sha(pair / 'operator-binding.json') != operator_binding_hash or
            file_sha(__file__) != harness_hash):
        raise ValueError('prover, source, snapshot, operator binding or harness changed during experiment')
    measurement = dict(elapsed_s=elapsed, cpu_s=cpu_elapsed,
        process_elapsed_s=time.perf_counter() - process_started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        profiling_enabled=args.profile_cost,
        deadline='existing repeated Python SIGALRM; external supervision required for hard termination',
        environment=dict(python=sys.version, executable=sys.executable,
            platform=platform.platform(), mpmath=mpmath.__version__, numpy=numpy.__version__,
            affinity=sorted(os.sched_getaffinity(0)),
            openblas_num_threads=os.environ.get('OPENBLAS_NUM_THREADS'),
            imported_prover=str(Path(prover.__file__).resolve())))
    if profile:
        costs = []
        for (filename, line, name), (primitive, calls, own, cumulative, _) in pstats.Stats(profile).stats.items():
            costs.append(dict(module=Path(filename).name, function=name, line=line,
                primitive_calls=primitive, calls=calls, self_s=own, inclusive_s=cumulative))
        measurement['profile_functions'] = sorted(costs, key=lambda x: -x['self_s'])[:80]
    receipt = dict(schema=campaign.SCHEMA, job=job, binding=binding, certificate=result,
        qualified_release=False, mathematical_scope='local continuous ideal-coefficient interval',
        experiment_identity=identity, measurement=measurement,
        canonical_work_index=args.job_index, prover_code_sha256=code,
        stage_snapshot_sha256=identity['stage_snapshot_sha256'],
        verified_operator_binding_sha256=identity['verified_operator_binding_sha256'])
    publish(destination, encoded(receipt))
    campaign.check_one(output, job, binding)
    print(json.dumps(dict(action='PUBLISHED', job_index=args.job_index, cell=job['cell_id'],
        mode=job['mode'], interval=[job['lo'], job['hi']], status=result['status'],
        reason=result.get('reason'), elapsed_s=elapsed, receipt=str(destination)),
        sort_keys=True), flush=True)
    return 0 if result['status'].startswith('PASS-LOCAL-') else 2


if __name__ == '__main__':
    raise SystemExit(main())
