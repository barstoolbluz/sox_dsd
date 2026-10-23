#!/usr/bin/env python3
"""Fail-closed offline verifier of the DSD1024 experiment's retained evidence.

Does not attest to omitted packed streams, re-run the experiment, or confer
candidate qualification. A second native replay is documented in REPLAY.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

from model import ROOT, RATE, WORKING, SOURCE, make_designs, sha
from study import DESIGNS, native_pass, definitions

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE/'evidence'
SCREEN_CASES = ('hot-997', 'noise-safe', 'dc-step', 'silence')
FINALISTS = ('clans-7', 'clans-8', 'sdm-8', 'sdm-8-g2p0', 'd512-sdm7-g3')
FINALIST_CASES = ('quiet-997', 'tone-20k', 'tone-40k', 'stress32')
BANDS = ('0_40k', '40_100k', '100_150k', '150_176p4k')


def require(test: bool, what: str) -> None:
    if not test:
        raise AssertionError(what)


def read(path: Path) -> dict:
    require(path.is_file(), 'Missing evidence '+str(path))
    return json.loads(path.read_text())


def verified_render(path: Path, key: str, case: str, manifest: dict, registry: dict) -> dict:
    r=read(path)
    binding=registry[key]
    for field,expected in {
        'schema':'DSD1024-NTF-native-render/1', 'key':key,
        'profile':binding['profile'], 'design_sha256':sha(DESIGNS),
        'input_sha256':manifest[case]['sha256'], 'input_frames':manifest[case]['frames'],
        'experimental_header_sha256':binding['header_sha256'],
        'experimental_sdm_sha256':binding['sdm_sha256'],
        'native_hz':RATE, 'working_hz':WORKING,
        'candidate_qualified':False, 'guard':'training/unbounded experimental',
        'kernel':'scalar', 'scale':0.5,
    }.items():
        require(r.get(field)==expected, f'{path}: {field}: mismatched value')
    expected_frames = r['input_frames'] * (RATE//WORKING)
    require(r.get('packed_bytes') == (expected_frames+7)//8, f'{path}: packed size')
    require(isinstance(r.get('packed_sha256'),str) and len(r['packed_sha256'])==64,
            f'{path}: missing packed digest')
    require(r['status']['processed_native_frames']==expected_frames and
            r['status']['committed_native_frames']==expected_frames,
            f'{path}: incomplete native result')
    good,why=native_pass(r)
    require(good, f'{path}: native diagnostic check failed: {why}')
    return r


def verified_spectrum(path: Path, key: str, render_path: Path,
                      render: dict, alternative: bool = False,
                      case: str = 'primary') -> dict:
    s=read(path)
    assert_fields = {'schema':'DSD1024-NTF-reconstruction/1', 'key':key,
                     'packed_sha256':render['packed_sha256'],
                     'render_receipt_sha256':sha(render_path),
                     'reconstructed_rate_hz':352800,'number_of_2x_decimations':7,
                     'last_fir_taps':601 if alternative else 401,
                     'last_fir_beta':25 if alternative else 22,
                     'halfband_taps':57,
                     'experimental_only':True,'candidate_qualified':False,
                     'status':'screen-passed'}
    for field,value in assert_fields.items():
        require(s.get(field)==value, f'{path}: {field} mismatch')
    # F-02/F-03: Source identity fixes both the source's fitted fundamental
    # and its steady plateau. The 1.2s tonal holdouts MUST NOT include the
    # 25ms EOF taper; 0.4--1.2s gave a spurious ~189dB noise increase.
    windows = {'primary':(997.,.4,1.2),
               'tone-20k':(20000.,.25,.95),
               'tone-40k':(40000.,.25,.95)}
    require(case in windows, f'{path}: unknown certified spectral source')
    expected_hz, start, stop = windows[case]
    manifest=read(EVIDENCE/'stimuli-manifest.json')['cases'][case]
    require(render['input_sha256']==manifest['sha256'] and
            render['input_frames']==manifest['frames'], f'{path}: source digest or length')
    spectrum=s['spectrum']
    for field,value in {'sample_hz':352800,
        'fit_tone_hz':expected_hz,'start_s':start,'stop_s':stop,
        'window':'kaiser_beta30_power_compensated'}.items():
        require(spectrum.get(field)==value, f'{path}: invalid source/analysis parameter {field}')
    require(all(isinstance(spectrum.get(k),(float,int)) and
                math.isfinite(spectrum[k]) for k in
                ('rms','sine_equivalent_dbfs','unwindowed_total_sine_equivalent_dbfs',
                 'fundamental_peak','fitted_dc')),f'{path}: invalid spectral fit fields')
    require(spectrum['rms']>=0, f'{path}: negative total RMS')
    # Native renderer's reference 0.5 scale means a 0.501187 source
    # predicts ~0.25059 reconstructed fundamental, and 0.6 -> ~0.3.
    expected_peak = .5*10**(-6/20) if case=='primary' else .3
    require(abs(spectrum['fundamental_peak']-expected_peak)<.01,
            f'{path}: incompatible fundamental amplitude')
    hz_parts=((0,20000),(20000,40000),(40000,60000),(60000,80000),
              (80000,100000),(100000,120000),(120000,150000),(150000,176400))
    parts=spectrum['parts']
    expected_names=[f'{lo}-{hi}Hz' for lo,hi in hz_parts]
    require(set(parts)==set(expected_names),f'{path}: wrong FFT partitions')
    squares=[]
    for (lo,hi),name in zip(hz_parts,expected_names):
        b=parts[name]
        for field in ('rms','sine_equivalent_dbfs','strongest_fft_bin_peak_dbfs'):
            require(isinstance(b.get(field),(float,int)) and math.isfinite(b[field]),
                    f'{path}: invalid partition field {name} {field}')
        require(b['rms']>=0, f'{path}: negative partition power')
        require(math.isclose(b['sine_equivalent_dbfs'],
                20*math.log10(max(math.sqrt(2)*b['rms'],1e-300)),abs_tol=1e-8),
                f'{path}: inconsistent partition dB {name}')
        f=b.get('strongest_fft_bin_hz')
        require(f is None or (math.isfinite(f) and lo<=f<=hi),
                f'{path}: FFT peak lies outside band {name}')
        squares.append(b['rms']**2)
    require(math.isclose(sum(squares),spectrum['rms']**2,rel_tol=2e-7,abs_tol=1e-26),
            f'{path}: spectral energy does not close')
    require(math.isclose(spectrum['sine_equivalent_dbfs'],
            20*math.log10(max(math.sqrt(2)*spectrum['rms'],1e-300)),abs_tol=1e-8),
            f'{path}: fitted total level not derived from RMS')
    bands=s['integrated_sine_equivalent_dbfs']
    require(set(BANDS)==set(bands) and all(math.isfinite(v) for v in bands.values()),
            f'{path}: missing/invalid integrated bands')
    for group, indices in {'0_40k':range(0,2),'40_100k':range(2,5),
                           '100_150k':range(5,7),'150_176p4k':range(7,8)}.items():
        expected_db=20*math.log10(max(math.sqrt(2)*math.sqrt(sum(squares[i] for i in indices)),1e-300))
        require(math.isclose(bands[group],expected_db,abs_tol=1e-8),
                f'{path}: integrated band does not follow FFT energies: {group}')
    # No offline checker can recompute omitted raw audio from its hash.
    # Native bitstream regeneration + an independently implemented FFT is
    # available in r2_welch.py / r2_numeric.py; this checks internal
    # numerical semantics and authority-bound analysis settings.
    return s


def verify() -> dict:
    designs=definitions()
    manifest=read(EVIDENCE/'stimuli-manifest.json')
    require(manifest['schema']=='DSD1024-NTF-stimuli/1', 'stimulus manifest schema')
    cases=manifest['cases']
    require(set(cases)=={'primary',*SCREEN_CASES,*FINALIST_CASES,'hot-997','multitone','silence','dc-step','noise-safe'},
            'Unexpected missing or additional cases in generated stimulus manifest')
    require(cases['primary']['sha256']=='ca844611f9ba9f7f95428f69927e62c03806ddde21d3e43e8d5b3ab46a95701a',
            'Frozen primary high-precision source mismatch')
    for name,stim in cases.items():
        require(stim['source_hz']==WORKING and stim['frames']>0, 'bad source '+name)
        require(len(stim['sha256'])==64,'no source digest '+name)
    require(cases['stress32']['frames']==32*WORKING,'stress32 duration mismatch')
    r=read(EVIDENCE/'experimental-registry.json')
    require(r['schema']=='DSD1024-NTF-registry/1','registry schema mismatch')
    require(r['design_sha256']==sha(DESIGNS),'registry coefficient catalogue digest mismatch')
    require(r['original_sdm_sha256']==sha(SOURCE),'production bank mutated')
    require(len(r['candidates'])==len(designs['designs'])==55,'wrong registry count')
    bindings={c['key']:{**c,'header_sha256':r['experimental_header_sha256'],
                          'sdm_sha256':r['experimental_sdm_sha256']} for c in r['candidates']}
    require(set(bindings)==set(designs['designs']),'registry omissions or duplicates')
    require(bindings['clans-7']['profile']=='encode.mastering.v2.dsd1024',
            'Incumbent not the original native profile')
    require(all((b['profile'].startswith('encode.experimental.ntf.') if key!='clans-7' else True)
                for key,b in bindings.items()), 'production profile substitution')

    comparison=read(EVIDENCE/'comparison.json')
    require(comparison['schema']=='DSD1024-NTF-comparison/1' and
            comparison['native_hz']==RATE and comparison['source_hz']==WORKING and
            comparison['incumbent']=='clans-7' and
            comparison['candidate_count']==55 and comparison['screen_pass_count']==55 and
            comparison['screen_complete_count']==55 and comparison['spectral_comparison_count']==55,
            'inconsistent published comparison counts')
    require(comparison['required_screen_inputs']==list(SCREEN_CASES), 'screen definition changed')
    require('UNMODIFIED' in comparison['decisions']['production'] and
            'Self-generated' in comparison['decisions']['read_qualification'],
            'decision guard or read exclusion missing')
    primary={}
    count=0
    for key in sorted(designs['designs']):
        screens=comparison['screens'][key]
        require(screens['complete'] and screens['passed'] and len(screens['cases'])==4,
                'incorrect screen status '+key)
        for case in SCREEN_CASES:
            path=EVIDENCE/'screen'/case/(key+'.json')
            verified_render(path,key,case,cases,bindings)
            entry=next((entry for entry in screens['cases'] if entry['case']==case),None)
            require(entry is not None and entry['passed'] and
                    entry['receipt_sha256']==sha(path), 'comparison screen receipt mismatch '+str(path))
            count+=1
        path=EVIDENCE/'primary'/(key+'.json')
        render=verified_render(path,key,'primary',cases,bindings)
        spec_path=EVIDENCE/'spectra'/(key+'.json')
        spec=verified_spectrum(spec_path,key,path,render)
        primary[key]=spec
        recorded=comparison['spectra'][key]
        require(recorded['receipt_sha256']==sha(spec_path) and
                recorded['integrated_sine_equivalent_dbfs']==spec['integrated_sine_equivalent_dbfs'],
                'comparison lacks authentic spectrum '+key)
    # Verify candidate decisions against the actual retained 55 independent spectra.
    winners=[]
    baseline=primary['clans-7']['integrated_sine_equivalent_dbfs']
    for key,spec in primary.items():
        if key=='clans-7': continue
        bands=spec['integrated_sine_equivalent_dbfs']
        if bands['0_40k']<=baseline['0_40k']+1 and bands['40_100k']<=baseline['40_100k']-3 and bands['100_150k']<=baseline['100_150k']-3:
            winners.append(key)
    published={item['key'] for item in comparison['research_pareto_candidates']}
    require(set(winners)==published and len(winners)==23,'selection rule or winner set mismatch')
    for candidate in FINALISTS:
        for case in FINALIST_CASES:
            path=EVIDENCE/'finalists'/case/(candidate+'.json')
            render=verified_render(path,candidate,case,cases,bindings)
            require(render['input_frames']==cases[case]['frames'], 'finalist length mismatch')
            if case in ('tone-20k','tone-40k'):
                verified_spectrum(EVIDENCE/'holdout-spectra'/case/(candidate+'.json'),
                                  candidate,path,render,case=case)
    max_fir_delta=0.0
    for candidate in ('clans-7','clans-8','sdm-8','sdm-8-g2p0'):
        receipt_path=EVIDENCE/'primary'/(candidate+'.json')
        r0=read(receipt_path)
        other=verified_spectrum(EVIDENCE/'spectra-alternative'/(candidate+'.json'),
                                candidate,receipt_path,r0,alternative=True)
        for band in ('0_40k','40_100k','100_150k'):
            delta=abs(other['integrated_sine_equivalent_dbfs'][band]-
                      primary[candidate]['integrated_sine_equivalent_dbfs'][band])
            max_fir_delta=max(max_fir_delta,delta)
            require(delta<0.1,'FIR sensitivity greater than .1dB: '+candidate+' '+band)
    original=read(ROOT/'tests/dsd/reference/p19_dsd1024_v2_guard.json')
    regenerated=read(EVIDENCE/'requalification/recreated-guard.json')
    outcome=read(EVIDENCE/'requalification/result.json')
    require(original['qualified'] is False and regenerated['qualified'] is False,
            'qualified-state was altered')
    require(regenerated['bounds']==original['bounds'] and
            regenerated['training_max_abs_state']==original['training_max_abs_state'],
            'guard replay disagrees with historical frozen maxima or bounds')
    require(outcome['bounds_match'] and outcome['maxima_exact_match'] and
            outcome['training_max_abs_state_abs_differences']==[0]*8 and
            outcome['original_frozen_sha256']==sha(ROOT/'tests/dsd/reference/p19_dsd1024_v2_guard.json') and
            outcome['recreated_frozen_sha256']==sha(EVIDENCE/'requalification/recreated-guard.json') and
            outcome['holdout_result']=='PASS' and outcome['training_cases']==17,
            'incorrect replay result')
    training=regenerated['training_receipts_sha256']
    require(len(training)==17,'not all training receipts reproduced')
    for original_relative,expected in training.items():
        path=EVIDENCE/'requalification/training'/Path(original_relative).name
        require(sha(path)==expected,'frozen proof training digest mismatch: '+str(path))
    holdouts=read(EVIDENCE/'requalification/holdout-summary.json')
    require(holdouts['result']=='PASS' and holdouts['case_count']==36 and
            holdouts['frozen_guard_sha256']==sha(EVIDENCE/'requalification/recreated-guard.json'),
            'requalified holdout summary/proof mismatch')
    require(outcome['holdout_summary_sha256']==sha(EVIDENCE/'requalification/holdout-summary.json'),
            'requalification summary hash mismatch')
    for original_relative,digest in holdouts['case_receipts_sha256'].items():
        path=EVIDENCE/'requalification/holdout'/Path(original_relative).name
        require(sha(path)==digest,'requalified holdout receipt digest mismatch: '+str(path))
    for name in ('training.log','freeze.log','verify.log','adjudicate.log'):
        require((EVIDENCE/'requalification'/name).is_file(),'missing P19 replay log '+name)
    return {'verdict':'PASS_HISTORICAL_R1_RECEIPTS_ONLY__SCREEN_SUPERSEDED_BY_R2',
            'design_count':55,'native_short_screen_receipts':count,
            'native_primary_receipts':55,'native_32_second_soaks':5,
            'native_finalist_receipts':20, 'spectral_primary_receipts':55,
            'spectral_holdout_receipts':10,'spectral_alternative_fir_receipts':4,
            'max_alternative_fir_absolute_delta_db':round(max_fir_delta,5),
            'research_winner_count':len(winners), 'host_requalification_training_receipts':17,
            'host_requalification_holdout_receipts':36,
            'not_qualified':['experimental shapers','DSD1024 independent read media',
                             'candidate 3,600-second native soak','full omitted-tree P15 suites'],
            'no_production_edits':True}


if __name__=='__main__':
    try:
        print(json.dumps(verify(),indent=2,sort_keys=True))
    except (OSError,KeyError,TypeError,ValueError,AssertionError) as error:
        print('EVIDENCE FAIL:',type(error).__name__,error,file=sys.stderr)
        sys.exit(2)
