#!/usr/bin/env python3
"""Strict R2 evidence adjudication: R1 history + all R2 native screens.

Offline verification can bind recorded SHA-256 bitstreams and internally
recompute spectral arithmetic. It CANNOT derive absent packed bits from
hashes; r2_numeric.py and r2_welch.py supply separate bitstream replay.
"""
from __future__ import annotations
from argparse import Namespace
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import sys

from model import sha
from study import definitions
from r2_screen import CASES, assess, material
from verify_evidence import verify as verify_r1, require
from r2_welch import SCHEMA as PSD_SCHEMA, FFT_SIZE, BANDS, FILTERS, START_S

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
R2=HERE/'evidence_r2'
PSD_KEYS=('clans-7','clans-8','sdm-8','sdm-8-g2p0','sdm-8-g0p25',
          'd512-r5-a20','d512-r5-a20-g0p25','d512-r5-a20-g0p5',
          'd512-r8-a20','d512-r8-a20-g0p25','d512-r8-a20-g0p5')


def load(path):
    require(path.is_file(),'Missing R2 evidence '+str(path))
    return json.loads(path.read_text())


def check_psd() -> dict:
    import numpy as np
    r1=load(E/'stimuli-manifest.json')['cases']['primary']
    require(set(p.stem for p in (R2/'native_psd').glob('*.json'))==set(PSD_KEYS),
            'R2 native PSD coverage changed')
    require(set(p.stem for p in (R2/'primary-replay').glob('*.json'))==set(PSD_KEYS),
            'R2 independent native primary replay coverage changed')
    result={}
    for key in PSD_KEYS:
        frozen=load(E/'primary'/f'{key}.json')
        replaypath=R2/'primary-replay'/f'{key}.json'
        replay=load(replaypath)
        require(replay['key']==key and replay['input_sha256']==r1['sha256'] and
                replay['input_frames']==r1['frames'] and replay['return_code']==0 and
                replay['status']['failure']==0 and replay['status']['nonfinite_states']==0 and
                replay['packed_sha256']==frozen['packed_sha256'] and
                replay['working_hz']==176400 and replay['native_hz']==45158400 and
                replay['guard']=='training/unbounded experimental' and
                replay['candidate_qualified'] is False,
                'Native primary replay not identical to archive '+key)
        rec=load(R2/'native_psd'/f'{key}.json')
        require(rec['schema']==PSD_SCHEMA and rec['key']==key and
                rec['packed_sha256']==frozen['packed_sha256'] and
                rec['native_render_receipt_sha256']==sha(replaypath) and
                rec['input_sha256']==r1['sha256'] and rec['native_hz']==45158400 and
                rec['nfft']==FFT_SIZE and rec['overlap']==0 and
                rec['source_analysis_start_s']==START_S and
                rec['segments']>=270 and abs(rec['total_bipolar_power']-1)<3e-12,
                'R2 PSD identity or Parseval error '+key)
        require(set(rec['bands'])=={f'{lo}-{hi}Hz' for lo,hi in BANDS},
                'R2 PSD bands incomplete '+key)
        require(set(rec['illustrative_filters'])=={
                f'butterworth_{order}pole_{cutoff}hz_above150k' for order,cutoff in FILTERS},
                'Transfer-function scenarios missing '+key)
        for band,info in rec['bands'].items():
            power=info['integrated_power']
            require(power>0 and math.isfinite(power) and
                    math.isclose(10*math.log10(power),info['integrated_power_db'],abs_tol=1e-9),
                    'R2 inconsistent raw band power '+key+' '+band)
        for scenario,info in rec['illustrative_filters'].items():
            power=info['weighted_ultrasonic_power']
            require(power>0 and math.isfinite(power) and
                    math.isclose(10*math.log10(power),info['weighted_ultrasonic_power_db'],abs_tol=1e-9),
                    'R2 inconsistent digital transfer model '+key+' '+scenario)
        result[key]=rec
    # Numerical challenge from F-04, independently reproduced with our
    # bounded-memory FFT and a different native-built executable than R1.
    for key,expected_05,expected_12 in (('clans-7',-51.65,-34.48),
                                        ('sdm-8',-36.71,-24.01),
                                        ('sdm-8-g2p0',-36.69,-23.87)):
        row=result[key]['bands']
        require(abs(row['500000-1000000Hz']['integrated_power_db']-expected_05)<.08 and
                abs(row['1000000-2000000Hz']['integrated_power_db']-expected_12)<.08,
                'Core independently observed native ultrasonic claim not reproduced: '+key)
    incumbent=result['clans-7']['bands']
    return {key:{band:round(result[key]['bands'][band]['integrated_power_db'] -
                            incumbent[band]['integrated_power_db'],4)
                 for band in ('500000-1000000Hz','1000000-2000000Hz')}
            for key in PSD_KEYS if key!='clans-7'}


def check_numeric() -> int:
    require((R2/'numeric_replay').is_dir(),'Missing R2 independent numeric receipts')
    files=list((R2/'numeric_replay').glob('*.json'))
    require(all(x.name.startswith('primary-') for x in files),
            'Unexpected spectrum replay case')
    require({x.stem[len('primary-'):] for x in files}==set(PSD_KEYS),
            'Missing independently reconstructed candidate(s)')
    for key in PSD_KEYS:
        p=R2/'numeric_replay'/f'primary-{key}.json';rec=load(p)
        original=load(E/'spectra'/f'{key}.json');originalpath=E/'spectra'/f'{key}.json'
        replaypath=R2/'primary-replay'/f'{key}.json'
        render=load(replaypath)
        require(rec['schema']=='DSD1024-NTF-R2-independent-reconstruction/1' and
                rec['key']==key and rec['case']=='primary' and
                rec['packed_sha256']==render['packed_sha256'] and
                rec['native_replay_receipt_sha256']==sha(replaypath) and
                rec['original_spectrum_sha256']==sha(originalpath) and
                rec['source_window_s']==[.4,1.2] and rec['source_tone_hz']==997. and
                rec['qualified'] is False,
                'R2 independent numerical provenance mismatch '+key)
        require(set(rec['delta_from_original_db'])==set(original['integrated_sine_equivalent_dbfs']),
                'Independent replay omitted band '+key)
        for band,delta in rec['delta_from_original_db'].items():
            recomputed=rec['recomputed_sine_equivalent_dbfs'][band]
            require(math.isfinite(recomputed) and math.isfinite(delta) and
                    abs(delta)<.05 and
                    math.isclose(recomputed,original['integrated_sine_equivalent_dbfs'][band]+delta,abs_tol=1e-9),
                    'Incorrectly reconstructed numeric metric '+key+' '+band)
    return len(files)


def check_holdout_numeric() -> int:
    cases=('tone-20k','tone-40k')
    require(set(p.stem for p in (R2/'numeric_holdout').glob('*.json'))=={
                case+'-sdm-8' for case in cases},'Missing independent tonal holdout(s)')
    require(set(p.stem for p in (R2/'holdout-replay').glob('*.json'))=={
                case+'-sdm-8' for case in cases},'Missing tonal native replay(s)')
    original_inputs=load(E/'stimuli-manifest.json')['cases']
    for case in cases:
        path=R2/'numeric_holdout'/f'{case}-sdm-8.json';record=load(path)
        rp=R2/'holdout-replay'/f'{case}-sdm-8.json'
        render=load(rp)
        specpath=E/'holdout-spectra'/case/'sdm-8.json'
        spectrum=load(specpath)
        original_render=load(E/'finalists'/case/'sdm-8.json')
        expected_hz=20000. if case=='tone-20k' else 40000.
        require(render['key']=='sdm-8' and render['input_sha256']==original_inputs[case]['sha256']
                and render['packed_sha256']==original_render['packed_sha256']
                and render['return_code']==0 and render['status']['nonfinite_states']==0
                and record['original_spectrum_sha256']==sha(specpath)
                and record['native_replay_receipt_sha256']==sha(rp)
                and record['packed_sha256']==render['packed_sha256']
                and record['source_window_s']==[.25,.95]
                and record['source_tone_hz']==expected_hz,
                'Invalid correction to original tonal holdout '+case)
        for band,level in record['recomputed_sine_equivalent_dbfs'].items():
            require(abs(level-spectrum['integrated_sine_equivalent_dbfs'][band])<.05,
                    'Tone replay spectral numeric mismatch '+case+' '+band)
    return len(cases)


def verify() -> dict:
    original=verify_r1()
    require(original['research_winner_count']==23,'Wrong original historical comparison count')
    manifest=load(R2/'stimuli-manifest.json')
    require(manifest['schema']=='DSD1024-NTF-R2-stimuli/1' and
            set(manifest['cases'])==set(CASES), 'Missing one or more mandatory R2 stress sources')
    import hashlib
    for name in CASES:
        data,_=material(name)
        info=manifest['cases'][name]
        require(info['sha256']==hashlib.sha256(data).hexdigest() and
                info['frames']==len(data)//8 and info['working_hz']==176400,
                'Nondeterministic or mismatched R2 stress signal '+name)
    with redirect_stdout(io.StringIO()):
        comparison=assess(Namespace(manifest=R2/'stimuli-manifest.json',
                                    results=R2/'screen',output=R2/'assessment.json'))
    psd_deltas=check_psd()
    numerical=check_numeric()
    tonal_replays=check_holdout_numeric()
    require(comparison['pass_all_count']==36 and
            comparison['stable_and_spectral_candidate_count']==8 and
            len(comparison['r1_spectral_cannot_advance_keys'])==15,
            'Full-scale corrective results differ from verified native campaign')
    require(comparison['designs']==55 and comparison['native_receipts']==55*len(CASES),
            'R2 mandatory screen incomplete')
    require('NO PROMOTION' in comparison['decision'] and
            comparison['r1_comparison_sha256']==sha(E/'comparison.json'),
            'R2 source and decision authority mismatch')
    return {'verdict':'CORRECTIVE_R2_EXPLORATORY_ONLY__NO_PRODUCTION_AUTHORIZATION',
            'historical_r1_receipts_verified':original['native_short_screen_receipts'],
            'r2_designs':comparison['designs'],
            'r2_native_stress_receipts':comparison['native_receipts'],
            'r2_designs_passing_all_added_stresses':comparison['pass_all_count'],
            'r1_spectral_candidates_rejected_by_r2':len(comparison['r1_spectral_cannot_advance_keys']),
            'r2_stable_and_spectral_candidates':comparison['stable_and_spectral_candidate_keys'],
            'source_and_psd_primary_native_bitstreams_reproduced':len(PSD_KEYS),
            'independent_primary_numeric_replays':numerical,
            'independent_20k_and_40k_tonal_replays':tonal_replays,
            'raw_dsd_0p5to1m_and_1to2m_deltas_db_vs_clans7':psd_deltas,
            'limits':['No qualifying DAC transfer function or independent media',
                      'No candidate-specific 3600s, guard, holdout, ISA or throughput qualification',
                      'Offline evidence verification does not reconstruct omitted native bitstreams',
                      'No production coefficient, P19, guard or waiver changes']}

if __name__=='__main__':
    try:
        print(json.dumps(verify(),indent=2,sort_keys=True,allow_nan=False))
    except (OSError,KeyError,AssertionError,ValueError,TypeError,RuntimeError) as err:
        print('R2 EVIDENCE FAIL',type(err).__name__,err,file=sys.stderr)
        sys.exit(2)
