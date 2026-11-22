#!/usr/bin/env python3
"""Independent numerical analysis of *shipped* DSD 1.1.2 FIR coefficients.

Read production C99 hex words; verify SHA-256 and symmetry; locate extrema
with derivative bracketing and 75-digit reevaluation; measure full native
Nyquist stopband and the coherent sum of every folded alias image.

This is a measured numerical certificate, not a formal interval proof.
The nonlinear SDM-8 is excluded: its output-noise spectrum is not H(f).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from scipy import optimize

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from certify_filters import (adaptive_max, bank_extrema, db, eq_derivative,
                             hp_response, hp_composite, response)


def load(header, prefix, names):
    source=(ROOT/'src'/header).read_text()
    result={}
    for name in names:
        match=re.search(r'\b'+re.escape(prefix+name)+r'\[(\d+)\]\s*=\s*\{(.*?)\};', source,re.S)
        if match is None: raise AssertionError(f'production bank absent: {name} in {header}')
        h=np.asarray([float.fromhex(w.strip()) for w in match.group(2).split(',') if w.strip()],dtype=np.float64)
        assert len(h)==int(match.group(1)),name
        result[name]=h
    return result


def peak_ripple(h,p):
    grid=np.linspace(0,p,16385)
    derivative=eq_derivative(h,grid)
    points=[0.,p]
    for i in range(len(grid)-1):
        if derivative[i] == 0:
            points.append(float(grid[i]))
        elif (derivative[i]<0)!=(derivative[i+1]<0):
            points.append(float(optimize.brentq(lambda x:eq_derivative(h,x),grid[i],grid[i+1],xtol=5e-16)))
    return max((abs(db(abs(hp_response(h,x)))),x) for x in points),len(points)


def coefficient_qualification(manifest):
    banks={}
    records={}
    for role,file,prefix in (
            ('encoder','pcmdsd_coeffs_112.h','lsx_dsd112_encoder_'),
            ('decoder','dsd_coeffs_112.h','lsx_dsd112_decoder_')):
        rows=manifest['banks'][role]
        owned=load(file,prefix,rows)
        banks[role]=owned
        records[role]={}
        for name,meta in rows.items():
            h=owned[name]
            p=meta['pass_cycles'];s=meta['stop_cycles']
            sha=hashlib.sha256(('\n'.join(v.hex() for v in h)+'\n').encode('ascii')).hexdigest()
            assert sha==meta['sha256_float_hex'] and len(h)==meta['taps']
            assert np.array_equal(h,h[::-1]),'non-symmetric production words'
            assert abs(float(np.sum(h,dtype=np.longdouble))-1.)<2e-15
            passpeak,count=peak_ripple(h,p)
            stoppeak,n_extrema,gridpeak=bank_extrema(h,s,.5)
            edge=float(abs(hp_response(h,s)))
            # Measure actual stop edge AND worst after that edge; never substitute.
            record=dict(taps=len(h),sha256=sha,pass_abs_peak_db=passpeak[0],
                pass_peak_hz=passpeak[1]*meta['input_hz'],pass_extrema=count,
                stop_edge_db=db(edge),stop_worst_db=db(stoppeak[1]),
                stop_worst_hz=stoppeak[0]*meta['input_hz'],
                stop_extrema=n_extrema,grid_worst_db=db(gridpeak),
                passes=(passpeak[0]<=.0001 and db(stoppeak[1])<=-185.0))
            records[role][name]=record
            if not record['passes']:
                raise AssertionError(f'{role} {name} violates FIR numerical contract: {record}')
    return banks,records


def composite_qualification(manifest,banks,grid):
    # Original 57-tap halfband is unchanged; use bytes from actual shipped P06 header.
    hb=load('dsd_coeffs.h','lsx_dsd_coeff_',['halfband'])['halfband']
    all_banks=dict(halfband=hb)
    all_banks.update(banks['decoder'])
    report={}
    for rate,meta in manifest['profiles'].items():
        fs=meta['native_hz']; R=meta['intermediate_hz']
        D=meta['factor']; P=meta['pass_hz'];S=meta['stop_hz']
        names=['halfband']*(meta['stages']-1)+[meta['bank']]
        assert fs==D*R and len(names)==D.bit_length()-1
        def transfer(f):
            return response(all_banks,names,fs,f)
        ppeak,pdetail=adaptive_max(lambda f:np.abs(20*np.log10(np.maximum(np.abs(transfer(f)),1e-300))),0,P,grid)
        stop,stopdetail=adaptive_max(lambda f:np.abs(transfer(f)),S,fs/2,grid)
        def coherent(f):
            f=np.asarray(f)
            acc=np.zeros_like(f,dtype=float)
            for k in range(1,D):
                acc+=np.abs(transfer(f+k*R))
            return acc
        alias,aliasdetail=adaptive_max(coherent,0,P,max(2048,grid//4),refinement=20)
        # Disambiguate stop edge transfer from worst stopband including all stages.
        stopedge=db(abs(hp_composite(all_banks,names,fs,S)))
        highp=db(abs(hp_composite(all_banks,names,fs,ppeak[0])))
        highstop=db(abs(hp_composite(all_banks,names,fs,stop[0])))
        from certify_filters import mp
        highalias=db(mp.fsum(abs(hp_composite(all_banks,names,fs,alias[0]+k*R)) for k in range(1,D)))
        # Additional diagnostics from DSD_DESIGN 6.3. Unlike the worst-case
        # coherent sum above, these assume uncorrelated image phases. The
        # synthetic f^4 shape is a frequency weighting, not an SDM-8 model.
        base=np.linspace(0,P,1025)
        flat=np.zeros_like(base)
        shaped=np.zeros_like(base)
        for k in range(1,D):
            freq=base+k*R
            h=np.abs(transfer(freq))
            flat+=h*h
            shaped+=h*h*(freq/(fs/2))**4
        incoherent_flat=db(math.sqrt(float(flat.max())))
        synthetic_f4_weighted=db(math.sqrt(float(shaped.max())))
        row=dict(native_hz=fs,intermediate_hz=R,factor=D,pass_hz=P,stop_hz=S,
                 stage_banks=names,stage_taps=meta['decoder_stage_taps'],
                 delay_native_frames=meta['delay_native_frames'],
                 pass_abs_peak_db=ppeak[1],pass_peak_hz=ppeak[0],
                 stop_edge_db=stopedge,stop_worst_db=db(stop[1]),stop_worst_hz=stop[0],
                 coherent_alias_sum_db=db(alias[1]),alias_peak_base_hz=alias[0],
                 high_precision_at_pass_peak_db=highp,
                 high_precision_at_stop_worst_db=highstop,
                 high_precision_at_alias_peak_db=highalias,
                 incoherent_flat_alias_power_db=incoherent_flat,
                 synthetic_f4_weighted_image_db=synthetic_f4_weighted,
                 noise_diagnostic_baseband_samples=len(base),
                 search=dict(passband=pdetail,stopband=stopdetail,aliases=aliasdetail),
                 passes=(ppeak[1]<=.0001 and db(stop[1])<=-160 and db(alias[1])<=-160))
        report[rate]=row
        if not row['passes']:
            raise AssertionError(f'{rate} complete front-end fails response contract: {row}')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid',type=int,default=8192)
    parser.add_argument('--output',type=Path,default=ROOT/'tests/dsd/results/P112/filter-response.json')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'tests/dsd/reference/mastering_passband_112.json').read_text())
    banks,bank_results=coefficient_qualification(manifest)
    cascades=composite_qualification(manifest,banks,args.grid)
    report=dict(schema='sox-dsd/1.1.2/fir-cascade-measurement/1',
        source='parsed binary64 production C hex words (not generated design samples)',
        method='derivative-bracket FIR extrema, adaptive full-native-Nyquist cascade extrema, all coherent image sums, separate sampled incoherent/weighted image powers, 75-digit reevaluation',
        limitation='numerical search with refined sampled extrema; not a rigorous interval-arithmetic global bound',
        thresholds=dict(pass_abs_max_db=.0001,decoder_composite_stop_max_db=-160,
            decoder_coherent_alias_sum_max_db=-160,individual_fir_stop_max_db=-185),
        banks=bank_results,profiles=cascades,
        summary={'banks_pass':sum(v['passes'] for rows in bank_results.values() for v in rows.values()),
                 'profiles_pass':sum(v['passes'] for v in cascades.values())})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['summary']))
    for rate,row in cascades.items():
        print(rate, 'pass', round(row['pass_abs_peak_db'],8),'stop',round(row['stop_worst_db'],2),'aliases',round(row['coherent_alias_sum_db'],2))

if __name__=='__main__':
    main()
