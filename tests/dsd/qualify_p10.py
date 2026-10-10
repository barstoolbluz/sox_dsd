#!/usr/bin/env python3
"""P10 evidence collector. A measurement is never a promotion certificate.

Training freezes finite state bounds from its declared corpus only. Holdout
never changes them. Qualification failure exits nonzero and is retained.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from p10_corpus import RATES, SOURCES, POLICY, training_cases, holdout_cases, stimulus, identity
ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT/'tests/dsd/reference/analysis-v1'
sys.path.insert(0, str(ANALYSIS))
from analyze import decode_packed, steady_segment, measure, fit, band_power, bh4
from measure_candidates import confirm_lock
import numpy as np
from scipy import fft


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, data):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    text=json.dumps(data, sort_keys=True, indent=2, allow_nan=False)+'\n'
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text);tmp.replace(path)


def render(args, config, *, mode, control='mastering', retain=False):
    native=config['native_hz']
    id_prefix={'mastering':'encode.mastering.v1', 'legacy':'encode.legacy.v1',
        'sdm6':'encode.diagnostic.sdm6.v1', 'clans8':'encode.diagnostic.clans8.v1'}[control]
    profile=f'{id_prefix}.dsd{native//44100}'
    raw, meta = stimulus(config)
    name=f'{native}-{config["source_hz"]}-{config["name"]}-{control}'
    with tempfile.TemporaryDirectory(prefix='p10-candidate-') as temp:
        temp=Path(temp);source=temp/'source.f64le';bits=temp/'audio.bits';report=temp/'render.json'
        source.write_bytes(raw)
        cmd=[str(args.unit.resolve()),'--render',str(config['source_hz']),str(native),
            profile,str(config.get('reference_scale',.5)),mode,str(source),str(bits),str(report)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
        row=dict(name=name,source=config,source_identity=meta,control=control,
            candidate_profile=profile,mode=mode,exit_code=proc.returncode,
            command=['test/dsd_test_p10','--render',str(config['source_hz']),str(native),profile,
                str(config.get('reference_scale',.5)),mode,'<fixture>/source.f64le',
                '<work>/audio.bits','<result>/render.json'],stderr=proc.stderr)
        if report.exists():
            row['render']=json.loads(report.read_text())
        else:
            row['execution_error']='renderer did not produce a report'
        if bits.exists():
            row['bits_sha256']=digest(bits)
            row['packed_bytes']=bits.stat().st_size
        if proc.returncode==0 and config['seconds']>=1.51 and not config.get('skip_analysis'):
            audio=decode_packed(bits,row['render']['committed_native_frames'],native)
            segment,trim=steady_segment(audio,native)
            row['analysis_trim']=trim
            kind=config['kind']
            if kind=='tone' and config.get('frequency',997.)<=20000:
                hz=config.get('frequency',997.);scale=config.get('reference_scale',.5)
                peak=config.get('peak',10**(config.get('dbfs',-6.)/20))*scale
                window='rectangular' if float(hz).is_integer() else 'blackman-harris-4'
                row['analysis']=measure(segment,hz,peak,window=window)
                residual=fit(segment,hz,window=window)['residual']
            elif kind=='multitone':
                frequencies=config.get('frequencies',[37.,997.,5501.,11003.,17011.])
                t=np.arange(len(segment))/88200
                basis=np.column_stack([np.ones(len(segment))]+[
                    fun(2*np.pi*f*t) for f in frequencies for fun in (np.sin,np.cos)])
                coeff=np.linalg.lstsq(basis,segment,rcond=None)[0]
                residual=segment-basis@coeff
                power=band_power(residual,window='rectangular')
                row['analysis']=dict(residual_band_power=power['power'],
                    residual_band_dbfs=power['dbfs'],window='rectangular',
                    residual_definition='DC and only the declared input multitone fundamentals removed')
            else:
                residual=segment-np.mean(segment)
                row['analysis']=dict(band=band_power(residual),
                    mean=float(np.mean(segment)),rms=float(np.sqrt(np.mean(segment*segment))))
            if 'residual_band_dbfs' in row['analysis']:
                # A worst-case source-quantization error bound is conservative:
                # half an int32 LSB mapped by the declared reference scale.
                # Below it, intrinsic encoder performance is not ranked.
                scale=config.get('reference_scale',.5)
                bound_power=(scale*.5/(2**31-1))**2
                floor=10*math.log10(bound_power/.5)
                row['precision']=dict(source_quantization_error_power_upper_bound_dbfs=floor,
                    fixture_floor_limited=row['analysis']['residual_band_dbfs']<=floor+6,
                    status='conservative source representation bound, not a measured analysis precision limit',
                    ranking='do not rank intrinsic modulator residual below this representation bound')
            # Coherent spectral line power uses the frozen window's coherent
            # gain, not its noise ENBW. This supplements (never replaces) the
            # frozen analyzer's residual/noise integration.
            window=row['analysis'].get('window','blackman-harris-4')
            weights=np.ones(len(segment)) if window=='rectangular' else bh4(len(segment))[0]
            spectrum=fft.rfft(residual*weights)
            f=fft.rfftfreq(len(segment),1/88200)
            power=2*np.abs(spectrum)**2/(float(weights.sum())**2)
            select=(f>=20)&(f<=20000)
            at=np.flatnonzero(select)[int(np.argmax(power[select]))]
            row['spectral_peak']=dict(frequency_hz=float(f[at]),
                line_power=float(power[at]),line_dbfs=10*math.log10(max(float(power[at]),1e-300)/.5),
                window=window,interpretation='largest in-band residual bin; stable-spur gate applies only to silence/low-level cases')
        if retain and bits.exists():
            destination=args.results/'retained'/f'{name}.bits'
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(bits.read_bytes())
            row['retained_bits']='retained/'+destination.name
        return row


def train(args):
    confirm_lock()
    all_configs=[c | {'skip_analysis':True} for r in RATES for c in training_cases(r)]
    report=dict(schema='P10/training/1',corpus_sha256=identity(all_configs),
        corpus=all_configs,rows=[],qualification='UNQUALIFIED',
        limitation='calibration has no finite guards; holdout and remaining release gates are separate')
    path=args.results/'training.json'
    frozen=ROOT/'tests/dsd/reference/p10_guards.json'
    if frozen.exists():
        expected=json.loads(frozen.read_text())
        if (not path.exists() or digest(path)!=expected['training_evidence_sha256'] or
                report['corpus_sha256']!=expected['training_corpus_sha256']):
            raise RuntimeError('frozen guards exist: refusing to overwrite or regenerate training evidence')
        prior=json.loads(path.read_text())
        if len(prior.get('rows',[]))!=len(all_configs):
            raise RuntimeError('frozen training evidence has incomplete coverage')
        print('retaining immutable training evidence',digest(path))
        return int(prior['summary']['rejected']!=0)
    if path.exists():
        prior=json.loads(path.read_text())
        if prior.get('corpus_sha256')!=report['corpus_sha256']:
            raise RuntimeError('training corpus changed; use a new versioned result directory')
        report=prior
    for config in all_configs:
        if any(row['source']==config for row in report['rows']):
            continue
        row=render(args,config,mode='training')
        report['rows'].append(row);atomic(path,report)
        print('training',row['name'],'exit',row['exit_code'],flush=True)
    bounds={}
    for native in RATES:
        rows=[r for r in report['rows'] if r['source']['native_hz']==native]
        admitted=[r for r in rows if r['exit_code']==0]
        if not admitted:raise RuntimeError('no admitted training at '+str(native))
        maxima=[max(row['render']['max_abs_state'][i] for row in admitted) for i in range(8)]
        frozen=[math.ldexp(1.,math.ceil(math.log2(16*max(1.,v)))) for v in maxima]
        bounds[str(native)]=dict(max_abs_state=maxima,bounds=frozen,
            successful_case_identities=[r['source_identity']['configuration_sha256'] for r in admitted],
            rejected_case_identities=[r['source_identity']['configuration_sha256'] for r in rows if r['exit_code']])
    report['bounds']=bounds
    report['summary']=dict(passed=sum(r['exit_code']==0 for r in report['rows']),
        rejected=sum(r['exit_code']!=0 for r in report['rows']))
    atomic(path,report)
    guard_manifest=dict(schema='P10/frozen-operational-guards/1',
        derivation='2**ceil(log2(16*max(1, coordinate maximum over admitted training)))',
        training_corpus_sha256=report['corpus_sha256'],training_evidence_sha256=digest(path),
        profiles=bounds,qualified=False,holdout_used_for_calibration=False)
    if args.freeze_training_bounds:
        target=ROOT/'tests/dsd/reference/p10_guards.json'
        if target.exists() and json.loads(target.read_text())!=guard_manifest:
            raise RuntimeError('refusing to silently replace frozen training bounds')
        atomic(target,guard_manifest)
        h=['/* Frozen P10 training bounds. Holdout cannot adjust them. */',
           '#ifndef LSX_PCMDSD_GUARDS_H','#define LSX_PCMDSD_GUARDS_H',
           'static const double lsx_pcmdsd_guards[3][8] = {']
        for rate in RATES:
            h.append('  {'+', '.join(v.hex() for v in bounds[str(rate)]['bounds'])+'},')
        h+=['};','#define LSX_PCMDSD_CERTIFICATE_SHA256 "unqualified-holdout-pending"','#endif','']
        (ROOT/'src/pcmdsd_guards.h').write_text('\n'.join(h))
    print(json.dumps(report['summary']))
    return int(report['summary']['rejected']!=0)


def configurations():
    cases=[c for r in RATES for c in holdout_cases(r)]
    for rate in RATES:
        for source in SOURCES:
            cases.append(dict(name=f'matrix-{source}',kind='tone',split='rate-matrix',
                native_hz=rate,source_hz=source,seconds=1.6,frequency=997.,dbfs=-6.,
                taper_seconds=.1,seed=301009))
    return cases


def jobs(cases):
    out=[]
    for config in cases:
        out.append((config,'mastering','guarded'))
        if (config['kind'] in ('tone','multitone') and not config.get('separately_handled_fullscale')
                and not config.get('expected_overload')):
            out.append((config,'legacy','training'))
        if config['name']=='tone-997--6':
            out.extend((config,c,'training') for c in ('sdm6','clans8'))
    return out


def implementation_identity():
    names=['src/pcmdsd.c','src/pcmdsd.h','src/pcmdsd_coeffs.h',
        'src/sdm.c','src/sdm.h','src/rate.c','src/rate_internal.h',
        'src/rate_filters.h','src/rate_half_fir.h','src/rate_poly_fir.h',
        'src/rate_poly_fir0.h','src/dsd_kernels_scalar.c']
    return {name:digest(ROOT/name) for name in names if (ROOT/name).exists()}


def evaluate(args):
    confirm_lock()
    guard_path=ROOT/'tests/dsd/reference/p10_guards.json'
    cases=configurations()
    report=dict(schema='P10/qualification/2',analysis='analysis-v1',
        analysis_lock_sha256=digest(ANALYSIS/'SHA256SUMS.txt'),
        guard_manifest_sha256=digest(guard_path),corpus_sha256=identity(cases),
        implementation=implementation_identity(),corpus=cases,rows=[],gates={},
        qualified=False,status='INCOMPLETE')
    path=args.results/'qualification.json'
    if path.exists():
        old=json.loads(path.read_text())
        for key in ('schema','analysis_lock_sha256','guard_manifest_sha256',
                'corpus_sha256','implementation'):
            if old.get(key)!=report[key]:
                raise RuntimeError(f'resume {key} differs; preserve old evidence and use a new result directory')
        report=old
    keys=set()
    for row in report['rows']:
        key=(identity(row['source']),row['control'],row['mode'])
        if key in keys:raise RuntimeError('duplicate cached qualification row')
        keys.add(key)
    for config,control,mode in jobs(cases):
        key=(identity(config),control,mode)
        if key in keys:continue
        row=render(args,config,mode=mode,control=control,
            retain=config.get('expected_overload',False))
        report['rows'].append(row);keys.add(key);atomic(path,report)
        print('holdout',row['name'],'exit',row['exit_code'],
            'residual',row.get('analysis',{}).get('residual_band_dbfs'),flush=True)
    return summarize(args,report)


def summarize(args,report=None):
    confirm_lock()
    path=args.results/'qualification.json'
    if report is None:report=json.loads(path.read_text())
    rows=report['rows']
    expected={(identity(c),control,mode) for c,control,mode in jobs(configurations())}
    actual=[(identity(r['source']),r['control'],r['mode']) for r in rows]
    missing=sorted(expected-set(actual));unexpected=sorted(set(actual)-expected)
    coverage=(not missing and not unexpected and len(actual)==len(set(actual)) and
        report.get('corpus_sha256')==identity(configurations()) and
        report.get('guard_manifest_sha256')==digest(ROOT/'tests/dsd/reference/p10_guards.json'))
    candidate=[r for r in rows if r['control']=='mastering']
    ordinary=[r for r in candidate if not r['source'].get('expected_overload')
        and not r['source'].get('separately_handled_fullscale')]
    failures=[r['name'] for r in ordinary if r['exit_code']!=0]
    guards=json.loads((ROOT/'tests/dsd/reference/p10_guards.json').read_text())
    invalid_evidence=[]
    for row in ordinary:
        if row['exit_code']!=0:continue
        c=row['source'];r=row.get('render',{});frames=round(c['source_hz']*c['seconds'])
        expected_frames=(frames*c['native_hz']+c['source_hz']//2)//c['source_hz']
        bounds=guards['profiles'][str(c['native_hz'])]['bounds']
        states=r.get('max_abs_state',[])
        if (r.get('status')!=3 or r.get('failure')!=0 or r.get('first_bad_frame') is not None or
            r.get('input_frames')!=frames or r.get('committed_native_frames')!=expected_frames or
            r.get('processed_native_frames')!=expected_frames or r.get('nonfinite_states')!=0 or
            r.get('windows28')!=max(0,expected_frames-27) or
            len(states)!=8 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or
                v<0 or v>bounds[i] for i,v in enumerate(states))):
            invalid_evidence.append(row['name'])
    if invalid_evidence:coverage=False
    admitted=[r for r in ordinary if r['exit_code']==0]
    windows=[r['name'] for r in admitted if r['source']['native_hz']==2822400
        and r.get('render',{}).get('excursions28')!=0]
    spur_failures=[]
    for r in admitted:
        c=r['source']
        if c['kind']=='silence' or (c['kind']=='tone' and c.get('dbfs',0)<=-60):
            threshold=-110. if c['native_hz']==2822400 else -120.
            measured=r.get('spectral_peak',{}).get('line_dbfs')
            if measured is None or not math.isfinite(measured) or measured>threshold:
                spur_failures.append(dict(name=r['name'],limit_dbfs=threshold,measured_dbfs=measured))
    pairs=[];comparison_missing=[]
    for r in admitted:
        c=r['source']
        if c['kind'] not in ('tone','multitone'):continue
        old=next((v for v in rows if v['control']=='legacy' and v['source']==c),None)
        new_db=r.get('analysis',{}).get('residual_band_dbfs')
        old_db=old.get('analysis',{}).get('residual_band_dbfs') if old else None
        if (old is None or old['exit_code']!=0 or new_db is None or old_db is None or
                not math.isfinite(new_db) or not math.isfinite(old_db)):
            # Tones above the declared 20 kHz analysis band are not scored.
            if c['kind']=='tone' and c.get('frequency',997)>20000:continue
            comparison_missing.append(r['name']);continue
        primary=c['split']=='holdout' and (c['kind']=='multitone' or
            (c['kind']=='tone' and c.get('frequency') in (997.,1000.)))
        pairs.append(dict(name=r['name'],native_hz=c['native_hz'],source_hz=c['source_hz'],
            primary=primary,candidate_dbfs=new_db,legacy_dbfs=old_db,
            improvement_db=old_db-new_db,
            precision=r.get('precision',{'status':'unbounded fixture/analysis floor; diagnostic value only'})))
    d64=[p for p in pairs if p['native_hz']==2822400 and p['primary']]
    aggregate=sum(p['improvement_db'] for p in d64)/len(d64) if len(d64)==13 else None
    all_d64=[p for p in pairs if p['native_hz']==2822400]
    aggregate_all=sum(p['improvement_db'] for p in all_d64)/len(all_d64) if all_d64 else None
    regressions=[p for p in pairs if p['improvement_db'] < -1.]
    overload=[r for r in candidate if r['source'].get('expected_overload')]
    overload_ok=len(overload)==3 and all(r['exit_code']!=0 and r.get('render',{}).get('failure')==2 for r in overload)
    fullscale=[dict(name=r['name'],exit_code=r['exit_code'],failure=r.get('render',{}).get('failure'),
        excursions28=r.get('render',{}).get('excursions28'))
        for r in candidate if r['source'].get('separately_handled_fullscale')]
    phase=args.results.parent
    soak_path=phase/'soak/soak.json'
    soak=json.loads(soak_path.read_text()) if soak_path.exists() else {'status':'UNRUN'}
    perf_path=phase/'performance/summary.json'
    perf=json.loads(perf_path.read_text()) if perf_path.exists() else {'status':'UNRUN'}
    second_path=phase/'corroboration/corroboration.json'
    second=json.loads(second_path.read_text()) if second_path.exists() else {'status':'UNRUN'}
    report['gates']=dict(
        complete_numeric_coverage=dict(status='PASS' if coverage else 'FAIL',
            expected_rows=len(expected),actual_rows=len(actual),missing=missing,unexpected=unexpected,invalid_success_records=invalid_evidence),
        nominal_pipeline=dict(status='FAIL' if failures or not coverage else 'PASS',failures=failures),
        heldout_state_bounds=dict(status='FAIL' if not coverage or any(
            r.get('render',{}).get('failure') in (3,4) for r in ordinary) else 'PASS',
            qualified=False,scope='declared holdout only, not a universal stability proof'),
        dsd64_windows28=dict(status='FAIL' if windows or not coverage else 'PASS',failures=windows),
        lowlevel_spurs=dict(status='FAIL' if spur_failures or not coverage else 'PASS',failures=spur_failures),
        residual_comparison=dict(status='PASS' if aggregate is not None and aggregate>=6 and aggregate_all is not None and aggregate_all>=6 and not regressions
            and not comparison_missing and coverage else 'FAIL',
            aggregate_dsd64_improvement_db=aggregate,primary_dsd64_case_count=len(d64),
            all_matched_dsd64_improvement_db=aggregate_all,all_matched_dsd64_case_count=len(all_d64),
            minimum_individual_dsd64_improvement_db=min((p['improvement_db'] for p in all_d64),default=None),
            aggregate_scope='12 specified non-overload 997/1000 Hz tones plus holdout multitone; source-rate matrix and edge tone reported separately',
            aggregate_method='arithmetic mean of dB improvements = geometric mean of residual power ratios',
            material_regression_limit_db=1.,pairs=pairs,regressions=regressions,missing_comparisons=comparison_missing,
            limitation='DSD128/256 very low residuals may be fixture limited; not ranked as intrinsic modulator performance'),
        expected_overload=dict(status='PASS' if overload_ok else 'FAIL'),
        separately_handled_fullscale=fullscale,
        release_30min_per_rate=dict(status=soak['status'],evidence='../soak/soak.json'),
        second_reconstruction=dict(status=second['status'],evidence='../corroboration/corroboration.json'),
        representative_hardware_hour_per_profile_isa=dict(status='UNRUN'),
        independent_realworld_corpus=dict(status='UNRUN',reason='independent recordings not obtained; synthetic fixtures are not a substitute'),
        controlled_host_performance=dict(status=perf['status'],evidence='../performance/summary.json'))
    report['status']='FAILED' if any(isinstance(g,dict) and g.get('status')=='FAIL' for g in report['gates'].values()) else 'INCOMPLETE'
    report['qualified']=False
    atomic(path,report)
    print(json.dumps(dict(status=report['status'],nominal_failures=failures,
        dsd64_window_failures=windows,spur_failures=len(spur_failures),
        aggregate_dsd64_improvement_db=aggregate,regressions=len(regressions))))
    return 1 if report['status']=='FAILED' else 2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--stage',choices=('train','evaluate','summarize'),required=True)
    ap.add_argument('--freeze-training-bounds',action='store_true')
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    if args.stage=='train':return train(args)
    if args.stage=='evaluate':return evaluate(args)
    return summarize(args)
if __name__=='__main__':raise SystemExit(main())
