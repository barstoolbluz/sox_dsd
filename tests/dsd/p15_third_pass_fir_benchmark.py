#!/usr/bin/env python3
"""Reproducible warm arithmetic comparison, not a DSP or release benchmark."""
from __future__ import annotations
import hashlib,json,statistics,time,resource
from fractions import Fraction
from pathlib import Path
from p15_src_capture_matrix import verify_pair,DEFAULT
from p15_src_stagewise_alias_proof import make_src_stages
from p15_src_stagewise_continuum import cheap_alias_upper,bounds_single

_,operator=verify_pair(DEFAULT/'88200-192000',88200,192000)
stage=next(s for s in make_src_stages(operator) if len(s.taps)==4160)
shift=Fraction(stage.input_hz*stage.L)*Fraction(2,5)
lo,hi=Fraction(0),Fraction(1)
functions={'full_source_taylor':lambda:bounds_single(stage,shift,lo,hi)[1],
           'finite_difference_majorant':lambda:cheap_alias_upper(stage,shift,lo,hi)}
results={}
for name,fn in functions.items():
    fn()
    durations=[]
    for _ in range(9):
        begin=time.perf_counter();result=fn();durations.append(time.perf_counter()-begin)
    results[name]=dict(median_s=statistics.median(durations),
                       min_s=min(durations),max_s=max(durations),
                       rigorous_upper_before_stage_normalization=str(result.b*stage.L))
assert results['finite_difference_majorant']['rigorous_upper_before_stage_normalization']!='None'
result=dict(schema='P15/third-pass-warm-rigorous-fir-costs/1',
            stage_taps=len(stage.taps),src_L=stage.L,src_M=stage.M,
            normalized_image_frequency='2/5',output_interval_hz=['0','1'],
            runs=9,source_binding_sha256=hashlib.sha256((DEFAULT/'88200-192000/stage-snapshot.json').read_bytes()).hexdigest(),
            costs=results,stage_uppers_are_not_necessarily_equally_tight=True,
            speedup_full_over_difference=(results['full_source_taylor']['median_s']/
                results['finite_difference_majorant']['median_s']),
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
out=Path(__file__).resolve().parent/'results/P15_prover_third_pass_2026-10-18/FIR_WARM_EXACT_DIFFERENCE.json'
out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('warm rigorous FIR bound',round(result['speedup_full_over_difference'],1),
      'x; source full',round(results['full_source_taylor']['median_s']*1000,3),
      'ms, difference',round(results['finite_difference_majorant']['median_s']*1000,3),'ms')
