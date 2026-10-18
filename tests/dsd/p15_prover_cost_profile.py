#!/usr/bin/env python3
"""Machine-readable cProfile breakdown for the independent source FIR hotspot."""
from __future__ import annotations
import cProfile
from fractions import Fraction
import json
from pathlib import Path
import resource
import time

from p15_src_capture_matrix import verify_pair,DEFAULT
from p15_src_stagewise_alias_proof import make_src_stages
from p15_src_continuum_bounds import TrigPoly
from p15_src_interval_recurrence import general_magnitude_bounds
from p15_src_fixed_interval import fixed_symmetric_magnitude_bounds

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18/PROFILE_COSTS.json'


def profile(fn,poly,lo,hi):
    p=cProfile.Profile()
    started=time.monotonic()
    p.enable()
    result=fn(poly,lo,hi)
    p.disable()
    elapsed=time.monotonic()-started
    methods=[]
    for (filename,line,func),(primitive,number,own_time,cumulative,callers) in pstats_dict(p).items():
        if ('p15_' in filename or ('mpmath/' in filename and func in
            ('mpi_cos','mpi_sin','sin','cos','mpi_mul','mpi_add','mpi_sub'))):
            methods.append(dict(module=Path(filename).name,function=func,line=line,
                                calls=number,self_s=own_time,inclusive_s=cumulative))
    return dict(elapsed_s=elapsed,bounds=[float(result[0].a),float(result[1].b)],
                relevant_functions=sorted(methods,key=lambda x:-x['self_s'])[:30])


def pstats_dict(p):
    import pstats
    return pstats.Stats(p).stats


def run():
    _,op=verify_pair(DEFAULT/'88200-192000',88200,192000)
    stage=next(s for s in make_src_stages(op) if len(s.taps)==4160)
    poly=TrigPoly(stage.taps,Fraction(0))
    lo,hi=Fraction(1374,10000),Fraction(1374,10000)+Fraction(1,10000000)
    # Warm both before profiling caches to avoid misclassifying one-off
    # source moment setup as per-evaluation numerical work.
    general_magnitude_bounds(poly,lo,hi)
    fixed_symmetric_magnitude_bounds(poly,lo,hi)
    result=dict(schema='P15/source-fir-cprofile-costs/1',taps=len(stage.taps),
        normalized_interval=[str(lo),str(hi)],
        baseline_complex_iv=profile(general_magnitude_bounds,poly,lo,hi),
        optimized_real_dyadic=profile(fixed_symmetric_magnitude_bounds,poly,lo,hi),
        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        caveat='Profiler self/inclusive times are instrumentation-perturbed; nested cumulative times overlap')
    DEST.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for variant in ('baseline_complex_iv','optimized_real_dyadic'):
        print(variant,round(result[variant]['elapsed_s'],3),'seconds')
        for item in result[variant]['relevant_functions'][:8]:
            print('  ',item['function'],item['calls'],round(item['self_s'],4))


if __name__=='__main__':run()
