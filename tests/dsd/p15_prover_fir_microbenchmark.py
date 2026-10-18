#!/usr/bin/env python3
"""Warm same-process baseline vs exact dyadic interval magnitude arithmetic."""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path
import importlib.metadata
import json
import platform
import resource
import statistics
import time
from p15_src_capture_matrix import verify_pair, DEFAULT
from p15_src_stagewise_alias_proof import make_native_stages,make_src_stages
from p15_src_continuum_bounds import TrigPoly
from p15_src_interval_recurrence import general_magnitude_bounds
from p15_src_fixed_interval import fixed_symmetric_magnitude_bounds

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18/FIR_MICROBENCH.json'


def run():
    _,op_a=verify_pair(DEFAULT/'176400-48000',176400,48000)
    _,op_b=verify_pair(DEFAULT/'88200-192000',88200,192000)
    kinds={}
    for s in make_native_stages('master128')+make_src_stages(op_a)+make_src_stages(op_b):
        kinds.setdefault(len(s.taps),s)
    results=[]
    low=Fraction(1374,10000)
    high=low+Fraction(1,10000000)
    for size in (57,153,720,1005,1845,4160):
        stage=kinds[size]
        poly=TrigPoly(stage.taps,Fraction(0))
        outputs={};times={}
        for name,fn in (('baseline_complex_iv',general_magnitude_bounds),
                        ('optimized_real_fixed',fixed_symmetric_magnitude_bounds)):
            fn(poly,low,high)  # prepare caches / warm interpreter
            samples=[]
            for _ in range(4):
                t=time.perf_counter()
                result=fn(poly,low,high)
                samples.append(time.perf_counter()-t)
            times[name]=samples
            outputs[name]=[float(result[0].a),float(result[1].b)]
        results.append(dict(stage=stage.kind,taps=size,timing_s=times,
            baseline_median_s=statistics.median(times['baseline_complex_iv']),
            optimized_median_s=statistics.median(times['optimized_real_fixed']),
            speedup=statistics.median(times['baseline_complex_iv'])/
                    statistics.median(times['optimized_real_fixed']),
            baseline_bounds=outputs['baseline_complex_iv'],
            optimized_bounds=outputs['optimized_real_fixed']))
        print(size,'baseline',results[-1]['baseline_median_s'],
              'optimized',results[-1]['optimized_median_s'],
              'speedup',results[-1]['speedup'],flush=True)
    doc=dict(schema='P15/source-fir-rigorous-arithmetic-microbenchmark/1',
        interval_normalized=[str(low),str(high)],repeats=4,
        mpmath=importlib.metadata.version('mpmath'),
        python=platform.python_version(),platform=platform.platform(),
        process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        results=results,limitations=('Warm single-process arithmetic-only microbenchmarks; '
          'not a 72-cell certificate or physical DSP benchmark'))
    OUT.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':run()
