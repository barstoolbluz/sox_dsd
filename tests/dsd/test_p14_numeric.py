#!/usr/bin/env python3
"""P14 numerical gate: independent SciPy Butterworth design and direct bit oracles.

The SOS oracle is scipy.signal.butter, not production C's Q-factor formula.
The power-average oracle is implemented separately, including first event
and 20 ms warm-up exclusions. This is not SACD hardware certification.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import subprocess
import tempfile

import numpy as np
from scipy import signal
from reference import fixtures

RATES=(2822400,5644800,11289600)


def check(condition, explanation):
    if not condition:
        raise AssertionError(explanation)


def unit_sos(unit, hz, cutoff, hp):
    p=subprocess.run([str(unit),'--sos',str(hz),str(cutoff),'hp' if hp else 'lp'],
                     capture_output=True,text=True,timeout=20)
    check(p.returncode==0,f'unit SOS exit {p.returncode}: {p.stderr}')
    rows=[]
    for row in p.stdout.strip().splitlines():
        v=list(map(float,row.split()))
        check(len(v)==6,'SOS row size')
        order,b0,b1,b2,a1,a2=v
        check(order in (1,2),'SOS section order')
        rows.append([b0,b1,b2,1.,a1,a2])
    check(len(rows)==3,'fifth order SOS has three sections')
    return np.asarray(rows)


def independent_sos_check(unit):
    records=[]
    for rate in RATES:
        for cutoff,hp in ((20000,True),(40000,True),(50000,False),
                          (100000,False),(100000,True),(200000,False),(200000,True)):
            got=unit_sos(unit,rate,cutoff,hp)
            expected=signal.butter(5,cutoff,btype='highpass' if hp else 'lowpass',
                                   fs=rate,output='sos')
            freqs=np.asarray([1.,1000.,15000.,20000.,39000.,40000.,50000.,
                              60000.,80000.,100000.,150000.,200000.,300000.,rate*.45])
            freqs=freqs[freqs <rate/2]
            _,actual_h=signal.sosfreqz(got,worN=freqs,fs=rate)
            _,reference_h=signal.sosfreqz(expected,worN=freqs,fs=rate)
            error=float(np.max(np.abs(actual_h-reference_h)))
            check(error<2e-10,f'SOS transfer mismatch {rate} {cutoff} {hp} {error}')
            check(np.all(np.isfinite(got)),'nonfinite filter coefficients')
            records.append(dict(rate_hz=rate,cutoff_hz=cutoff,highpass=hp,
                                max_complex_gain_deviation=error,
                                reference='scipy.signal.butter(order=5,output=sos)'))
    return records


def unit_sample_analysis(unit):
    cp=subprocess.run([str(unit),'--json','512','analysis'],capture_output=True,
                      text=True,timeout=10)
    check(cp.returncode==0,cp.stderr)
    report=json.loads(cp.stdout)
    ch=report['channels']
    for c in range(2):
        bits=np.asarray([int(12<=i<55 or i%5==0) if c==0 else
                         int(i%7<3) if not 29<=i<72 else 0
                         for i in range(512)])
        x=2.*bits-1
        lsos=signal.butter(5,50000,fs=RATES[0],output='sos')
        hsos=signal.butter(5,40000,btype='highpass',fs=RATES[0],output='sos')
        usos=signal.butter(5,100000,fs=RATES[0],output='sos')
        level=signal.sosfilt(lsos,x)
        ultra=signal.sosfilt(usos,signal.sosfilt(hsos,x))
        power=0.
        maxpower=0.
        for y in ultra:
            power += (y*y-power)/524288.
            maxpower=max(maxpower,power)
        expected_lv=20*math.log10(np.max(np.abs(level))/.5)
        expected_us=10*math.log10(maxpower/.125)
        m=ch[c]['measurement']
        check(m['integrated_frames']=='0','warmup frames should exclude all 512')
        check(m['sacd_style']['power_average_alpha']==1/524288,'wrong averaging alpha')
        check(abs(m['sacd_style']['lowpass_peak_db_sacd']-expected_lv)<1e-7,
              'SACD-style LP level mismatch')
        check(abs(m['sacd_style']['band_exp_rms_max_db_sacd']-expected_us)<1e-7,
              'SACD-style exponential band power mismatch')
        check(all(v['power_dbfs_sine_reference'] is None for v in m['integrated_bands']),
              'short input should report unknown integrated band energy')
    return dict(rate_hz=RATES[0],frames_per_channel=512,
                alpha=1/524288,oracle='SciPy independent SOS + explicit power recurrence',
                tolerance_db=1e-7)


def native_band_test(sox,results):
    rate=RATES[0]
    frames=120000
    band=80000
    wave=bytes(int(math.sin(2*math.pi*band*i/rate)>=0) for i in range(frames))
    with tempfile.TemporaryDirectory(prefix='p14-numeric-') as td:
        d=pathlib.Path(td)
        inp=d/'input.dsf';out=d/'output.dsf';report=d/'report.json'
        inp.write_bytes(fixtures.make_dsf((wave,),rate))
        cmd=[str(sox),'--dsd-mode','native','--dsd-report',str(report),
             '-D',str(inp),str(out),'dsdstat','-a']
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        check(cp.returncode==0,f'P14 native ultrasonic analysis failed: {cp.stderr}')
        data=json.loads(report.read_text())
        measurement=data['dsdstat']['channels'][0]['measurement']
        energies=measurement['integrated_bands']
        check(data['status']=='complete','analysis conversion incomplete')
        check(int(measurement['integrated_frames'])==frames-rate//50,'bad warmup length')
        check(energies[1]['power_dbfs_sine_reference'] is not None,
              '40-100 kHz original-native energy missing')
        check(energies[0]['power_dbfs_sine_reference'] is not None,'20-40k missing')
        diff=energies[1]['power_dbfs_sine_reference']-energies[0]['power_dbfs_sine_reference']
        check(diff>10, f'80 kHz native signal not observed in its original band: {diff}')
        return dict(input_hz=rate,native_tone_hz=band,frames=frames,
                    native_20_40_dbfs=energies[0]['power_dbfs_sine_reference'],
                    native_40_100_dbfs=energies[1]['power_dbfs_sine_reference'],
                    band_advantage_db=diff,reference='independent native-rate input before decoder')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=pathlib.Path,required=True)
    ap.add_argument('--sox',type=pathlib.Path,required=True)
    ap.add_argument('--results',type=pathlib.Path,required=True)
    args=ap.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,fn in [('independent_butterworth5_sos',lambda:independent_sos_check(args.unit)),
                    ('sacd_exponential_reference',lambda:unit_sample_analysis(args.unit)),
                    ('original_native_ultrasonic_band',lambda:native_band_test(args.sox,args.results))]:
        try:
            detail=fn();records.append(dict(name=name,status='PASS',detail=detail))
            print('PASS',name,flush=True)
        except Exception as e:
            records.append(dict(name=name,status='FAIL',error=f'{type(e).__name__}: {e}'))
            print('FAIL',name,e,flush=True)
    output=dict(schema='sox.dsd.P14.numeric.v1',cases=records,
                limitation='not certified analog SACD metrology or physical silicon qualification')
    (args.results/'numeric-p14.json').write_text(json.dumps(output,indent=2,sort_keys=True,allow_nan=False)+'\n')
    return int(any(x['status']!='PASS' for x in records))


if __name__=='__main__':
    raise SystemExit(main())
