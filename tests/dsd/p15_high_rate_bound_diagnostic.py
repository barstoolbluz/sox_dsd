#!/usr/bin/env python3
"""Bounded, explicitly instrumented investigation of one OPEN frequency band.

No prover file is changed. Runtime wrappers count work and record returned
segment bounds; --no-difference explicitly disables only the optional upper
shortcut. These diagnostic timings are not matched benchmark measurements.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction
import importlib
import json
import math
import os
from pathlib import Path
import resource
import time
from mpmath import iv

from p15_high_rate_experiment import encoded, file_sha, loaded_code, publish
import p15_full_band_campaign as campaign
import p15_src_stagewise_continuum as prover
from p15_src_capture_matrix import DEFAULT, verify_pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--input-hz', type=int, required=True)
    parser.add_argument('--output-hz', type=int, required=True)
    parser.add_argument('--lo', required=True)
    parser.add_argument('--hi', required=True)
    parser.add_argument('--mode', choices=('pass', 'stop'), default='pass')
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--cpu', type=int, default=7)
    parser.add_argument('--no-difference', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 180:
        raise ValueError('invalid diagnostic deadline')
    os.sched_setaffinity(0, {args.cpu})
    importlib.import_module('p15_src_fixed_interval')
    base = Path(__file__).resolve().parent
    code = loaded_code(base)
    pair = DEFAULT / f'{args.input_hz}-{args.output_hz}'
    _, operator = verify_pair(pair, args.input_hz, args.output_hz)
    lo, hi = Fraction(args.lo), Fraction(args.hi)
    identity = dict(profile=args.profile, input_hz=args.input_hz,
        output_hz=args.output_hz, lo=str(lo), hi=str(hi), mode=args.mode,
        seconds=args.seconds, cpu=args.cpu, max_nodes=128, max_paths=20000,
        no_difference=args.no_difference, instrumented=True,
        script_sha256=file_sha(__file__), prover_code_sha256=code,
        binding=campaign.bindings(), snapshot_sha256=file_sha(pair / 'stage-snapshot.json'),
        operator_binding_sha256=file_sha(pair / 'operator-binding.json'))
    output = args.output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        old = json.loads(output.read_text())
        if old.get('identity') != identity:
            raise ValueError('existing diagnostic has different identity')
        print(json.dumps(dict(action='SKIP', output=str(output))))
        return
    stage_stats = defaultdict(lambda: dict(taylor_calls=0, taylor_seconds=0.,
                                         difference_attempts=0, difference_uses=0))
    segments = []
    inflight = {}
    evaluated_terms = {}
    original_bound = prover.bounds_single
    original_cheap = prover.cheap_alias_upper
    original_segment = prover.bound_segment

    def stage_name(stage):
        return f'{stage.kind}:{stage.input_hz}:{stage.L}/{stage.M}:{len(stage.taps)}'

    def instrument_bound(stage, shift, left, right):
        key = stage_name(stage)
        started = time.perf_counter()
        inflight.update(stage=key, shift=str(shift), lo=str(left), hi=str(right))
        try:
            result = original_bound(stage, shift, left, right)
            evaluated_terms[(id(stage), shift)] = result[1].b
            return result
        finally:
            stage_stats[key]['taylor_calls'] += 1
            stage_stats[key]['taylor_seconds'] += time.perf_counter() - started
            inflight.clear()

    def instrument_cheap(stage, shift, left, right):
        key = stage_name(stage)
        stage_stats[key]['difference_attempts'] += 1
        answer = None if args.no_difference else original_cheap(stage, shift, left, right)
        if answer is not None:
            stage_stats[key]['difference_uses'] += 1
            evaluated_terms[(id(stage), shift)] = answer.b
        return answer

    def instrument_segment(paths, left, right, **kwargs):
        entry = dict(lo=str(left), hi=str(right), complete_paths=len(paths))
        segments.append(entry)
        evaluated_terms.clear()
        started = time.perf_counter()
        try:
            result = original_segment(paths, left, right, **kwargs)
            entry['returned'] = {}
            for key, value in result.items():
                if hasattr(value, '_mpi_'):
                    entry['returned'][key] = dict(
                        lower=math.nextafter(float(value.a), -math.inf),
                        upper=math.nextafter(float(value.b), math.inf))
                else:
                    entry['returned'][key] = value
            # Inspect fully evaluated unwanted leaves. These are upper-bound
            # contributions, NOT lower bounds on actual spectral transfer.
            # Their exact product lower endpoint can show that the existing
            # immutable upper sum cannot get below its limit without a new
            # interval. No pass/fail disposition is inferred from this data.
            largest = iv.mpf(0)
            largest_path = None
            known = 0
            fixed_upper_sum = iv.mpf(0)
            for path in paths:
                include = (not path.direct if kwargs['mode'] == 'pass' else
                    max(abs(left + path.upstream_shift), abs(right + path.upstream_shift)) >= kwargs['stop_source_hz'])
                if not include or any((id(stage), shift) not in evaluated_terms
                                      for stage, shift in path.terms):
                    continue
                known += 1
                product = iv.mpf(1)
                for stage, shift in path.terms:
                    product *= evaluated_terms[(id(stage), shift)]
                fixed_upper_sum += product
                if bool(product.b > largest.b):
                    largest = product
                    largest_path = path
            entry['fully_evaluated_unwanted_paths'] = known
            entry['evaluated_upper_product_sum'] = dict(
                lower=math.nextafter(float(fixed_upper_sum.a), -math.inf),
                upper=math.nextafter(float(fixed_upper_sum.b), math.inf))
            if largest_path is not None:
                entry['largest_evaluated_upper_product'] = dict(
                    lower=math.nextafter(float(largest.a), -math.inf),
                    upper=math.nextafter(float(largest.b), math.inf),
                    source_shift=str(largest_path.upstream_shift),
                    factors=[dict(stage=stage_name(stage), shift=str(shift),
                        upper=math.nextafter(float(evaluated_terms[(id(stage), shift)]), math.inf))
                        for stage, shift in largest_path.terms])
            return result
        finally:
            entry['elapsed_s'] = time.perf_counter() - started

    prover.bounds_single = instrument_bound
    prover.cheap_alias_upper = instrument_cheap
    prover.bound_segment = instrument_segment
    started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        with campaign.interval_deadline(args.seconds):
            result = prover.certificate(args.profile, operator, lo, hi,
                mode=args.mode, max_nodes=128, max_paths=20000)
    except campaign.IntervalBudgetExpired:
        result = dict(status='OPEN', reason='diagnostic_wall_clock_budget_exhausted')
    elapsed = time.perf_counter() - started
    if code != loaded_code(base) or identity['binding'] != campaign.bindings():
        raise ValueError('code or source binding changed during diagnostic')
    record = dict(schema='P15/high-rate-bound-diagnostic/1', identity=identity,
        qualified_release=False, timing_scope='instrumented diagnostic; excluded from matched timing',
        original_prover_result=result, segments=segments, stage_stats=dict(stage_stats),
        measurement=dict(elapsed_s=elapsed, cpu_s=time.process_time()-cpu_started,
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        inflight=inflight)
    publish(output, encoded(record))
    print(json.dumps(dict(output=str(output), result=result,
                         elapsed_s=elapsed, segment_count=len(segments)), sort_keys=True))


if __name__ == '__main__':
    main()
