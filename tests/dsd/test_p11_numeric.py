#!/usr/bin/env python3
"""P11 ISA-independent analysis-v1 tone/SDM state qualification.

Uses frozen P09 analysis filters/metrology, not an emitted DSD byte hash as
an equivalence oracle. Synthetic normal SDM only: no claim about P10's full
interpolator/overload/real-world release qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import numpy as np
from scipy import fft

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/dsd/reference/analysis-v1'))
from analyze import decode_packed, fit, band_power, measure, steady_segment
from measure_candidates import confirm_lock


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp.replace(path)


def spur_dbfs(samples, fundamental_hz=997.):
    """Diagnostic largest coherent residual bin (4-term BH, 1-second window)."""
    fit_result=fit(samples,fundamental_hz)
    residual=fit_result['residual']
    n=len(residual)
    t=np.arange(n,dtype=np.float64)
    w=.35875-.48829*np.cos(2*np.pi*t/n)+.14128*np.cos(4*np.pi*t/n)-.01168*np.cos(6*np.pi*t/n)
    spectrum=np.abs(fft.rfft(residual*w))
    scale=2.0/float(np.sum(w))
    return 20.0*math.log10(float(np.max(spectrum[1:]))*scale) if spectrum.size>1 else None


def match_pair(scalar, candidate, rate, hz):
    s=scalar['measure'];v=candidate['measure']
    gain=abs(v['gain_error_db']-s['gain_error_db'])
    phase=abs(math.remainder(v['phase_rad']-s['phase_rad'],2*math.pi))
    # Frozen section 10.6: 0.001 dB gain, sub-sample phase, +1 dB
    # residual/integrated ultrasonic noise, +3 dB pairwise residual margin.
    checks={'gain_max_0_001_db':gain<=.001,
            'phase_subsample':phase < (2*math.pi*hz/88200.),
            'residual_no_plus_1_db':v['residual_band_dbfs']<=s['residual_band_dbfs']+1.,
            'ultrasonic_no_plus_1_db':v['ultrasonic_dbfs']<=s['ultrasonic_dbfs']+1.}
    sres=scalar['residual'];vres=candidate['residual']
    pair=band_power(vres-sres,lo=20.,hi=20000.,window='rectangular')['power']
    sum_noise=s['residual_band_power']+v['residual_band_power']
    pair_excess=10*math.log10(pair/sum_noise) if pair and sum_noise else None
    checks['pairwise_plus_3_db']=pair_excess is None or pair_excess<=3.
    scalar_spur=s['spur_dbfs'];candidate_spur=v['spur_dbfs']
    # Cross-ISA spur gate is significance-limited by scalar floor.
    if scalar_spur>-140.:
        checks['spur_plus_3_db']=candidate_spur<=scalar_spur+3.
    else: checks['spur_plus_3_db']=True
    state_s=scalar['monitor'];state_v=candidate['monitor']
    checks['no_nonfinite_or_overload']=all(state_v[k]==0 for k in ('nonfinite','overloads','counter_saturated'))
    checks['equal_frames_windows']=(state_s['frames']==state_v['frames'] and
         state_s['windows28']==state_v['windows28'])
    checks['dsd64_28bit_population']=rate!=2822400 or (state_v['min_ones28']>=4 and state_v['max_ones28']<=24 and state_v['excursions28']==0)
    return {'checks':checks,'gain_delta_db':gain,'phase_delta_rad':phase,
            'residual_delta_db':v['residual_band_dbfs']-s['residual_band_dbfs'],
            'ultrasonic_delta_db':v['ultrasonic_dbfs']-s['ultrasonic_dbfs'],
            'pairwise_excess_db':pair_excess,'spur_delta_db':candidate_spur-scalar_spur,
            'state_max_abs_scalar':state_s['max_abs_state'],
            'state_max_abs_candidate':state_v['max_abs_state']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p11')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--duration',type=float,default=1.6)
    ap.add_argument('--rates',type=int,nargs='*',default=[2822400,5644800,11289600])
    ap.add_argument('--frequency',type=float,default=997.)
    ap.add_argument('--dbfs',type=float,default=-6.)
    a=ap.parse_args()
    if not 1.51<=a.duration<=60:ap.error('duration >=1.51 and <=60 seconds required by frozen two-sided trim')
    if any(x not in (2822400,5644800,11289600) for x in a.rates):ap.error('unsupported rate')
    confirm_lock()
    a.results.mkdir(parents=True,exist_ok=True)
    report=dict(schema='P11/analysis-v1/1',method='frozen analysis-v1',
      analysis_lock_sha256=hashlib.sha256((ROOT/'tests/dsd/reference/analysis-v1/SHA256SUMS.txt').read_bytes()).hexdigest(),
      host=platform.platform(),machine=platform.machine(),
      command=[str(x).replace(str(ROOT),'<tree>') for x in sys.argv],
      qualification='synthetic cross-ISA kernels; P10 certification unchanged; not P15 promotion',
      records=[],comparisons=[],errors=[],unrun=[])
    tiers=['scalar','sse2','avx1']
    for rate in a.rates:
      results={}
      profile=f'encode.mastering.v1.dsd{rate//44100}'
      for tier in tiers:
        command=[str(a.unit),'--render',tier,profile,str(rate),str(a.frequency),
                 str(a.dbfs),str(a.duration)]
        try:
          with tempfile.TemporaryDirectory(prefix='p11-numeric-') as tmp:
            path=Path(tmp)/'bits.bin'
            cp=subprocess.run([*command,str(path)],capture_output=True,text=True,
                    timeout=300,cwd=ROOT,env=dict(os.environ,OMP_NUM_THREADS='1'))
            if cp.returncode==2:
              report['unrun'].append(dict(tier=tier,rate=rate,reason=cp.stderr.strip(),
                    command=[str(x).replace(str(ROOT),'<tree>') for x in [*command,'<temporary-bits>']],exit=2))
              continue
            if cp.returncode:raise RuntimeError(f'render exit {cp.returncode}: {cp.stderr[-300:]}')
            mon=json.loads(cp.stdout)
            bits_sha=hashlib.sha256(path.read_bytes()).hexdigest()
            output=decode_packed(path,mon['frames'],rate)
          window,trim=steady_segment(output,rate)
          nominal=.5*10**(a.dbfs/20.)
          measured=measure(window,a.frequency,nominal)
          ultrasonic=band_power(window,lo=20000.,hi=40000.,window='blackman-harris-4')
          summary={k:v for k,v in measured.items() if k not in ('residual_definition','window','enbw_bins')}
          summary['ultrasonic_dbfs']=ultrasonic['dbfs']
          summary['spur_dbfs']=spur_dbfs(window,a.frequency)
          item=dict(tier=tier,rate=rate,profile=profile,render_command=[str(x).replace(str(ROOT),'<tree>') for x in [*command,'<temporary-bits>']],
                    render_exit=cp.returncode,input_peak=nominal,native_sha256=bits_sha,
                    monitor=mon,measure=summary,metrology_trim=trim,status='measured')
          report['records'].append(item)
          results[tier]=dict(**item,residual=measured['residual'] if 'residual' in measured else fit(window,a.frequency)['residual'])
          print('P11 analysis-v1',rate,tier,'gain',round(summary['gain_error_db'],6),
                'residual',round(summary['residual_band_dbfs'],3),'spur',round(summary['spur_dbfs'],3),flush=True)
        except Exception as exc:
          report['errors'].append(dict(rate=rate,tier=tier,error=repr(exc)))
        finally:atomic(a.results/'cross-isa.json',report)
      if 'scalar' in results:
        for tier in tiers[1:]:
          if tier not in results:continue
          comparison=match_pair(results['scalar'],results[tier],rate,a.frequency)
          row=dict(rate=rate,tier=tier,scalar='scalar',**comparison)
          row['status']='PASS' if all(comparison['checks'].values()) else 'FAIL'
          report['comparisons'].append(row)
          print('P11 cross-ISA',rate,tier,row['status'],flush=True)
      atomic(a.results/'cross-isa.json',report)
    report['status']='PASS' if not report['errors'] and report['comparisons'] and all(
        r['status']=='PASS' for r in report['comparisons']) else 'INCOMPLETE' if report['unrun'] else 'FAIL'
    atomic(a.results/'cross-isa.json',report)
    return 0 if report['status']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
