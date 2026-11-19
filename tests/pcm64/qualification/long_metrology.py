#!/usr/bin/env python3
"""Phase 08 physical 0.5s audio metrology and recovery-active kernel metrology.

The nine analysis bands, weighted DC, one-sided spectrum, half-open bins,
Kaiser 30/34, and nominal 0.5 one-bit amplitude match the audited historical
harness. Audio metrics are measurements, not universal release thresholds.
Physical CLI clipping remains separate from actual certified-kernel recovery.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

import numpy as np

SELF=Path(__file__).resolve().parent
sys.path.insert(0,str(SELF.parent))
sys.path.insert(0,str(SELF))
sys.path.insert(0,str(SELF.parents[2]/'tests/dsd'))
from qualification import stimulus, sha256, demand, SOURCE_RATE, RATES, CHANNELS, PATTERNS
from encode import make_wav, dsf_bits
from decode import parse_wav
from audited_spectrum import analyze, compare, BANDS, BETAS
from attestation import verify as accepted, REFERENCE, physical_contract, approved_behavior
from build_context import read_fenv, build_context
import test_resonator as resmod

LONG_FRAMES=35280       # 0.8 seconds, giving a >=0.1s boundary margin
LONG_PATTERNS=(*PATTERNS,'clipping')
WIN_SECONDS=.5
LONG_SCHEMA='sox-p08-physical-halfsecond/1'


def finite_frames(pattern):
    if pattern!='clipping':
        return stimulus(pattern,n=LONG_FRAMES)
    return [[(1 if ch==0 else -1)*1.08*math.sin(
        2*math.pi*997*i/SOURCE_RATE) for ch in range(CHANNELS)]
        for i in range(LONG_FRAMES)]


def observe_bits(physical,channel,start,n):
    arr=np.frombuffer(physical,dtype=np.uint8)
    demand(arr.size%CHANNELS==0 and np.all(arr[0::CHANNELS]<=1) and
           np.all(arr[1::CHANNELS]<=1),'invalid physical DSD bits')
    return arr.reshape(-1,CHANNELS)[start:start+n,channel].astype('float64')-0.5


def run(args,results):
    results=Path(results).resolve()
    family=results/'long-halfsecond'
    demand(not family.exists(),'long metrology results must be a new root')
    family.mkdir(parents=True)
    source=SELF.parents[2]
    pin=accepted(source)
    binaries={str(Path(x).resolve()):sha256(x) for x in (args.sox,args.unit)}
    cases=[]; windows=[]
    with tempfile.TemporaryDirectory(prefix='p08-long-native-',dir=results) as workspace:
        work=Path(workspace)
        for hz in RATES:
            window_n=int(round(hz*WIN_SECONDS))
            total_n=LONG_FRAMES*hz//SOURCE_RATE
            demand(total_n-window_n >=int(.2*hz), 'insufficient 0.1s margins')
            start=(total_n-window_n)//2
            for pattern in LONG_PATTERNS:
                key=f'dsd{hz//44100}-{pattern}'
                source_wav=family/f'{key}.source.wav'
                output=family/f'{key}.physical.dsf'
                report=family/f'{key}.encode.json'
                frames=finite_frames(pattern)
                written=make_wav(source_wav,frames,CHANNELS,SOURCE_RATE)
                prefix=work/f'{key}.actual-admitted'
                fenv=family/f'{key}.fenv.json'
                command=[str(args.sox),'-R','--precision','64',
                         '--headroom','0','--dsd-clip','warn',
                         '--report',str(report),str(source_wav),'-r',str(hz),str(output)]
                cp=subprocess.run(command,capture_output=True,timeout=180,
                    env={**os.environ,'SOX_P08_ADMITTED_PREFIX':str(prefix),
                         'SOX_P08_FENV_PATH':str(fenv)})
                demand(cp.returncode==0 and output.is_file() and report.is_file(),
                      f'{key}: physical CLI failed {cp.returncode}: {cp.stderr[-1200:]!r}')
                actual_fenv=read_fenv(fenv)
                r=json.loads(report.read_text())
                enc=r['processing']['encoder']
                demand(r['status']=='complete' and
                       r['precision']['actual_route']=='native-binary64-encode' and
                       int(r['output']['frames_written'])==total_n and len(enc)==CHANNELS,
                       f'{key}: physical run failed to use native64 route')
                clips=[int(e['clipped_interpolated_samples']) for e in enc]
                recover=[int(e['recovery_entries']) for e in enc]
                demand(all(x>0 for x in clips) if pattern=='clipping' else
                       all(x==0 for x in clips),
                       f'{key}: clipping stimulus/control did not isolate clipping')
                demand(all(x==0 for x in recover),
                       f'{key}: unexpected kernel recovery; audio clipping and recovery conflated')
                physical=dsf_bits(output.read_bytes(),total_n,CHANNELS,hz)
                clip_fracs=[x/total_n for x in clips]
                actual=[]
                for ch in range(CHANNELS):
                    full=Path(f'{prefix}.ch{ch}.f64')
                    demand(full.is_file() and full.stat().st_size==8*total_n,
                           f'{key} channel {ch}: no real CLI admitted x')
                    raw=full.read_bytes()
                    full_hash=hashlib.sha256(raw).hexdigest()
                    observed=raw[start*8:(start+window_n)*8]
                    demand(len(observed)==8*window_n,'incomplete 0.5s admitted window')
                    relative=family/f'{key}.ch{ch}.admitted-window.f64.zlib'
                    relative.write_bytes(zlib.compress(observed,level=3))
                    full.unlink()   # full trace is not a measured-window fixture
                    x=np.frombuffer(observed,dtype='<f8')
                    q=observe_bits(physical,ch,start,window_n)
                    err=q-x
                    demand(np.all(np.isfinite(err)),'nonfinite q-x residual')
                    for beta in BETAS:
                        dc,spectrum=analyze(err,hz,beta)
                        windows.append({'case':key,'channel':ch,
                            'start_frame':start,'length_frames':window_n,
                            'window_seconds':WIN_SECONDS,'beta':beta,
                            'weighted_dc':dc,'bands':spectrum})
                    actual.append({'full_real_cli_admitted_sha256':full_hash,
                        'full_real_cli_admitted_frames':total_n,
                        'window_sha256':hashlib.sha256(observed).hexdigest(),
                        'compressed_sha256':sha256(relative),
                        'window_path':str(relative.relative_to(results))})
                cases.append({'id':key,'rate_hz':hz,'pattern':pattern,
                    'source_rate_hz':SOURCE_RATE,'channels':CHANNELS,
                    'source_frames':LONG_FRAMES,'native_frames':total_n,
                    'source_pcm_words_sha256':hashlib.sha256(written).hexdigest(),
                    'source_sha256':sha256(source_wav),
                    'source_path':str(source_wav.relative_to(results)),
                    'dsf_sha256':sha256(output),
                    'dsf_path':str(output.relative_to(results)),
                    'same_process_fenv':{**actual_fenv,
                        'path':str(fenv.relative_to(results))},
                    'report_sha256':sha256(report),
                    'report_path':str(report.relative_to(results)),
                    'physical_bits_sha256':hashlib.sha256(physical).hexdigest(),
                    'actual_cli_admitted':actual,
                    'clipped_samples':clips,'clipped_fraction':clip_fracs,
                    'recovery_entries':recover,'peak_native':[
                        e['peak_modulator_input'] for e in enc],
                    'window_start_frame':start,'window_length_frames':window_n,
                    'window_boundary_margin_s':min(start,total_n-(start+window_n))/hz,
                    'command':command,'exit_status':cp.returncode,
                    'stderr_sha256':hashlib.sha256(cp.stderr).hexdigest(),
                    'stdout_sha256':hashlib.sha256(cp.stdout).hexdigest()})
    demand(len(cases)==2*len(LONG_PATTERNS) and
           len(windows)==len(cases)*CHANNELS*len(BETAS),'long family incomplete')
    record={'schema':LONG_SCHEMA,'status':'PASS',
        'scope':'FINITE_MEASUREMENTS_ONLY_NOT_RELEASE_CERTIFICATION',
        'source_git_commit':git_head(source),
        'build_and_host':build_context(source),
        'accepted_production_revision':pin['accepted_production_revision'],
        'executed_binary_sha256':binaries,
        'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'full_scale':'nominal native DSD +/-0.5; full-scale sine RMS power 0.125',
        'analysis':'matched q - actual post-clip x; no gain/shift fitting;'
                   ' 0.5s windows; weighted DC; one-sided; N sum(w^2); nine half-open bands',
        'clip_policy':'source F64 1.08 input clipped only for `clipping` pattern;'
                      ' all 9 other patterns have zero clipping; no recurrence recovery',
        'recovery_policy':'separate independent certified DSD64/DSD128 kernel proof;'
                          ' ordinary recovery-candidate audio alone does not force recovery',
        'source_frames_per_case':LONG_FRAMES,'window_duration_s':WIN_SECONDS,
        'patterns':LONG_PATTERNS,'rates_hz':RATES,'betas':BETAS,'bands_half_open_hz':BANDS,
        'case_count':len(cases),'spectral_window_count':len(windows),
        'spectral_band_rows':len(windows)*len(BANDS),
        'cases':cases,'windows':windows}
    (results/'long-metrology.json').write_text(json.dumps(record,indent=2,
        sort_keys=True,allow_nan=False)+'\n')
    return record


def git_head(source):
    # An ordinary git archive is a valid source-only delivery. Without its
    # .git, accepted-source SHA identities and executable/receipt hashes are
    # the provenance; do not pretend a Git commit was observed in that export.
    source=Path(source)
    if not (source/'.git').exists():
        return None
    cp=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],
                      capture_output=True,text=True,timeout=10)
    demand(cp.returncode==0,'declared git checkout has no readable HEAD')
    return cp.stdout.strip()


def check(results):
    results=Path(results).resolve()
    path=results/'long-metrology.json'
    record=json.loads(path.read_text())
    contract=physical_contract()
    frozen=contract['long']['cases']
    gold=approved_behavior()['long_cases']
    demand(set(gold)==set(frozen),'incomplete frozen long physical behavioral reference')
    demand(record['schema']==LONG_SCHEMA and record['status']=='PASS',
           'missing long physical receipt')
    demand(set(frozen)=={f'dsd{hz//44100}-{p}' for hz in RATES for p in LONG_PATTERNS} and
           record['patterns']==list(LONG_PATTERNS) and
           tuple(record['rates_hz'])==RATES and tuple(record['betas'])==BETAS and
           record['bands_half_open_hz']=={k:list(v) for k,v in BANDS.items()},
           'changed historical window contract')
    demand(record['source_frames_per_case']==contract['long']['source_frames_per_case'] and
           record['window_duration_s']==contract['long']['window_seconds'] and
           record['case_count']==len(RATES)*len(LONG_PATTERNS) and
           record['spectral_window_count']==len(record['cases'])*CHANNELS*len(BETAS) and
           record['spectral_band_rows']==len(record['windows'])*len(BANDS),
           'missing long spectral rows')
    pins=accepted(SELF.parents[2])
    demand(record['accepted_production_revision']==pins['accepted_production_revision'],
           'stale accepted-source attestation')
    demand(record['source_git_commit']==git_head(SELF.parents[2]),
           'different source git commit')
    # Receipt paths name the producer's machine, but the *hashes* name the
    # executables. Bind them to this extracted checkout so verification works
    # after relocation without trusting or even accessing the old paths.
    source=SELF.parents[2]
    for suffix, local in (('/src/sox_p08_qualification',source/'src/sox_p08_qualification'),
                          ('/test/dsd_test_p10',source/'test/dsd_test_p10')):
        matches=[h for path,h in record['executed_binary_sha256'].items()
                 if path.endswith(suffix)]
        demand(len(matches)==1 and local.is_file() and sha256(local)==matches[0],
               'stale or missing relocated CLI/modulator binary: '+suffix)
    found={}; expected=set(frozen)
    for case in record['cases']:
        key=case['id']; demand(key in expected and key not in found,'duplicate/unknown long case')
        found[key]=case
        fixed=frozen[key]
        hz=case['rate_hz'];n=case['native_frames']
        source_frames=contract['long']['source_frames_per_case']
        demand(hz==fixed['rate_hz'] and
               case['source_rate_hz']==contract['source_rate_hz'] and
               case['channels']==contract['channels'] and
               case['pattern']==key.split('-',1)[1] and
               case['window_length_frames']==fixed['window_length_frames'] and
               case['source_frames']==source_frames and
               n==fixed['native_frames']==source_frames*hz//contract['source_rate_hz'] and
               case['window_start_frame']==fixed['window_start_frame'] and
               case['window_boundary_margin_s']>=.1,
               f'{key}: missing 0.5 second interior window')
        paths=((case['source_path'],'source_sha256'),
               (case['dsf_path'],'dsf_sha256'),
               (case['report_path'],'report_sha256'))
        for rel,hfield in paths:
            p=results/rel
            demand(p.resolve().is_relative_to(results) and p.is_file() and
                   sha256(p)==case[hfield],f'{key}: missing/corrupt {rel}')
        payload,_=parse_wav(results/case['source_path'],source_frames,
                            contract['channels'],contract['source_rate_hz'])
        words_sha=hashlib.sha256(payload).hexdigest()
        demand(words_sha==fixed['source_pcm_words_sha256'] and
               words_sha==case['source_pcm_words_sha256'],
               f'{key}: source input words differ from frozen physical contract')
        physical=dsf_bits((results/case['dsf_path']).read_bytes(),n,CHANNELS,hz)
        demand(hashlib.sha256(physical).hexdigest()==case['physical_bits_sha256'],
               f'{key}: changed final physical bits')
        demand(hashlib.sha256(physical).hexdigest()==gold[key]['physical_dsd_bits_sha256'],
               f'{key}: physical bits deviate from frozen independently approved stream')
        witness=case['same_process_fenv']
        fp=results/witness['path']
        demand(fp.resolve().is_relative_to(results) and fp.is_file(),
               f'{key}: process FENV missing')
        fresh=read_fenv(fp)
        demand(all(fresh[k]==witness[k] for k in fresh if k!='path'),
               f'{key}: process FENV witness changed')
        enc=json.loads((results/case['report_path']).read_text())
        demand(enc['status']=='complete' and
               enc['precision']['actual_route']=='native-binary64-encode' and
               int(enc['output']['frames_written'])==n,
               f'{key}: nonphysical encoder report')
        gate=enc['processing']['encoder']; demand(len(gate)==CHANNELS,'missing encoder channels')
        counts=[int(x['clipped_interpolated_samples']) for x in gate]
        recover=[int(x['recovery_entries']) for x in gate]
        demand(counts==case['clipped_samples'] and recover==case['recovery_entries'] and
               all(x==0 for x in recover) and
               (all(x>0 for x in counts) if case['pattern']=='clipping' else
                all(x==0 for x in counts)),
               f'{key}: invalid clipping/recovery separation')
        for ch,rec in enumerate(case['actual_cli_admitted']):
            path=results/rec['window_path']
            demand(path.resolve().is_relative_to(results) and path.is_file() and
                   sha256(path)==rec['compressed_sha256'],
                   f'{key}: missing CLI admission window')
            raw=zlib.decompress(path.read_bytes(),bufsize=8*case['window_length_frames'])
            demand(len(raw)==8*case['window_length_frames'] and
                   hashlib.sha256(raw).hexdigest()==rec['window_sha256'] and
                   rec['full_real_cli_admitted_frames']==n,
                   f'{key}: missing/altered admitted words')
            demand(hashlib.sha256(raw).hexdigest()==gold[key]['admitted_window_sha256'][ch],
                   f'{key}: actual admitted native words deviate from frozen accepted stream')
            x=np.frombuffer(raw,dtype='<f8')
            q=observe_bits(physical,ch,case['window_start_frame'],len(x))
            found[key,ch]=(q-x,hz,case['window_start_frame'],len(x))
    demand({k for k in found if isinstance(k,str)}==expected,'long synthetic matrix incomplete')
    windows=set()
    for w in record['windows']:
        key=(w['case'],w['channel'],w['beta'])
        demand(key not in windows and (w['case'],w['channel']) in
               {(c,ch) for c in expected for ch in range(CHANNELS)} and
               w['beta'] in BETAS,'missing/duplicated long window')
        windows.add(key)
        err,hz,start,n=found[w['case'],w['channel']]
        demand(w['start_frame']==start and w['length_frames']==n and
               w['window_seconds']==WIN_SECONDS,'altered half-second selection')
        compare(w,analyze(err,hz,w['beta']),str(key))
    demand(len(windows)==len(expected)*CHANNELS*len(BETAS),
           'missing or extra long windows')
    return len(expected),len(windows)


def recovery_proof(unit,results):
    """Actual kernel boundary with independent recovery-active 0.5s q-x.

    Constants are loaded from accepted external fixtures, not current headers.
    The unaltered independent recurrence from the certified modulator's
    existing test file is checked against the real compiled modulator. The
    long window centers that same hostile sequence in a 0.5s native stream;
    it does not pretend a source-PCM-to-DSD CLI path triggered recovery.
    """
    results=Path(results).resolve()
    family=results/'recovery-active'
    family.mkdir(parents=True,exist_ok=True)
    rows=[]
    for rate in (64,128):
        hz=SOURCE_RATE*rate
        freeze=REFERENCE/f'accepted-dsd{rate}-constants.h'
        original=SELF.parents[2]/f'src/resonator/dsd{rate}/src/constants.h'
        demand(freeze.read_bytes()==original.read_bytes(),
               f'DSD{rate}: certified kernel header no longer matches accepted fixture')
        c=resmod.load_constants(freeze)
        xs=resmod.stimuli(rate)
        expected,entries,steps=resmod.oracle(c,xs)
        demand(entries>0 and steps>0,f'DSD{rate}: hostile stimulus has no actual recovery')
        cp=subprocess.run([str(unit),'--modulate',str(hz)],
            input=struct.pack(f'<{len(xs)}d',*xs),capture_output=True,timeout=150)
        demand(cp.returncode==0 and cp.stdout==expected,
               f'DSD{rate}: real modulator bits disagree with frozen-constant oracle')
        state=json.loads(cp.stderr.decode().strip().splitlines()[-1])
        demand(int(state['recovery_entries'])==entries and
               int(state['recovery_steps'])==steps,
               f'DSD{rate}: real modulator recovery disagreement')

        # The original 54,000-word proof is retained unchanged. Place its
        # actual hostile words in the center of a separate full half-second
        # native window; the rest of the window is deterministic silence.
        window_n=hz//2
        demand(len(xs)<window_n and window_n==int(hz*.5),
               'recovery analysis must use the audited half-second duration')
        lead=(window_n-len(xs))//2
        window_x=[0.0]*lead+xs+[0.0]*(window_n-lead-len(xs))
        window_bytes=np.asarray(window_x,dtype='<f8').tobytes()
        ideal_bits,window_entries,window_steps=resmod.oracle(c,window_x)
        demand(window_entries>0 and window_steps>0,
               f'DSD{rate}: measured 0.5s interval has no actual recovery')
        physical_run=subprocess.run([str(unit),'--modulate',str(hz)],
            input=window_bytes,capture_output=True,timeout=150)
        demand(physical_run.returncode==0 and physical_run.stdout==ideal_bits,
               f'DSD{rate}: recovery-active physical bits differ from frozen recurrence')
        measured=json.loads(physical_run.stderr.decode().strip().splitlines()[-1])
        demand(int(measured['recovery_entries'])==window_entries and
               int(measured['recovery_steps'])==window_steps,
               f'DSD{rate}: recovery counters disagree inside the measured span')
        x=np.frombuffer(window_bytes,dtype='<f8')
        q=np.frombuffer(physical_run.stdout,dtype='u1').astype('float64')-.5
        demand(q.size==x.size==window_n,'missing real recovery-active physical bit')
        err=q-x
        spectra=[]
        for beta in BETAS:
            dc,bands=analyze(err,hz,beta)
            spectra.append({'beta':beta,'weighted_dc':dc,'bands':bands})
        input_path=family/f'dsd{rate}.admitted-native.f64.zlib'
        bits_path=family/f'dsd{rate}.physical-decisions.u8.zlib'
        input_path.write_bytes(zlib.compress(window_bytes,level=3))
        bits_path.write_bytes(zlib.compress(physical_run.stdout,level=3))
        active={'native_frames':window_n,'window_start_frame':0,
            'window_seconds':.5,'nominal_full_scale':.5,
            'residual':'actual frozen-kernel physical bit q minus admitted native input x',
            'actual_recovery_entries':window_entries,
            'actual_recovery_steps':window_steps,
            'native_input_sha256':hashlib.sha256(window_bytes).hexdigest(),
            'physical_decisions_sha256':hashlib.sha256(physical_run.stdout).hexdigest(),
            'native_input_path':str(input_path.relative_to(results)),
            'native_input_zlib_sha256':sha256(input_path),
            'physical_decisions_path':str(bits_path.relative_to(results)),
            'physical_decisions_zlib_sha256':sha256(bits_path),
            'spectra':spectra}
        rows.append({'rate_hz':hz,'native_input_frames':len(xs),
            'hostile_admitted_native_input_sha256':hashlib.sha256(struct.pack(
                f'<{len(xs)}d',*xs)).hexdigest(),
            'physical_modulator_decisions_sha256':hashlib.sha256(cp.stdout).hexdigest(),
            'actual_recovery_entries':entries,'actual_recovery_steps':steps,
            'certified_constants_fixture_sha256':sha256(freeze),
            'actual_unit_sha256':sha256(unit),
            'unit_exit_status':cp.returncode,
            'recovery_active_window':active})
    receipt={'schema':'sox-p08-certified-recovery/2','status':'PASS',
        'scope':'actual isolated certified kernel and half-second q-x; not a PCM SRC/CLI path',
        'source_git_commit':git_head(SELF.parents[2]),
        'stimulus':'existing hostile native .5 rails and resumed program, centered in 0.5s; no CLI clipping',
        'cases':rows}
    (results/'certified-recovery.json').write_text(json.dumps(receipt,indent=2,
        sort_keys=True)+'\n')
    return receipt


def verify_recovery(results):
    # A verification step that re-runs both independent recurrence and real
    # binary, rather than accepting counters copied from an earlier JSON.
    p=Path(results)/'certified-recovery.json'
    saved=json.loads(p.read_text())
    demand(saved['status']=='PASS' and saved['schema']=='sox-p08-certified-recovery/2'
           and len(saved['cases'])==2 and
           saved['source_git_commit']==git_head(SELF.parents[2]),
           'stale/incomplete recovered kernel receipt')
    unit=SELF.parents[2]/'test/dsd_test_p10'
    with tempfile.TemporaryDirectory(prefix='p08-recovery-') as t:
        fresh=recovery_proof(unit,Path(t))
    demand({row['rate_hz'] for row in saved['cases']}=={SOURCE_RATE*64,SOURCE_RATE*128},
           'missing or duplicated recovery-active rate')
    for row,other in zip(saved['cases'],fresh['cases']):
        demand({k:v for k,v in row.items() if k!='recovery_active_window'}==
               {k:v for k,v in other.items() if k!='recovery_active_window'},
               'kernel recovery counts, provenance or bits changed')
        actual=row['recovery_active_window'];expected=other['recovery_active_window']
        demand({k:v for k,v in actual.items() if k!='spectra'}==
               {k:v for k,v in expected.items() if k!='spectra'} and
               actual['actual_recovery_entries']>0 and
               actual['native_frames']==row['rate_hz']//2 and
               actual['window_seconds']==.5 and
               len(actual['spectra'])==len(BETAS),
               'changed or absent recovery-active physical window')
        raw=[]
        for path_key,compressed_key,digest_key,size in (
            ('native_input_path','native_input_zlib_sha256','native_input_sha256',
             8*actual['native_frames']),
            ('physical_decisions_path','physical_decisions_zlib_sha256',
             'physical_decisions_sha256',actual['native_frames'])):
            p=Path(results)/actual[path_key]
            demand(p.resolve().is_relative_to(Path(results).resolve()) and
                   p.is_file() and sha256(p)==actual[compressed_key],
                   'recovery-active physical fixture missing or altered')
            data=zlib.decompress(p.read_bytes())
            demand(len(data)==size and hashlib.sha256(data).hexdigest()==actual[digest_key],
                   'recovery-active input/physical decision bytes changed')
            raw.append(data)
        x=np.frombuffer(raw[0],dtype='<f8')
        q=np.frombuffer(raw[1],dtype='u1')
        demand(np.all(q<=1),'nonbinary recovery-active decision stream')
        residual=q.astype('float64')-.5-x
        for index,beta in enumerate(BETAS):
            w=actual['spectra'][index]
            demand(w['beta']==beta,'changed recovery-active Kaiser beta')
            compare(w,analyze(residual,row['rate_hz'],beta),
                    f'recovery-active DSD{row["rate_hz"]//SOURCE_RATE}, beta {beta}')
    return 2


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=Path)
    ap.add_argument('--unit',type=Path)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--verify-only',action='store_true')
    a=ap.parse_args();a.results.mkdir(parents=True,exist_ok=True)
    try:
        if a.verify_only:
            cases,windows=check(a.results)
            recover=verify_recovery(a.results)
        else:
            demand(a.sox is not None and a.unit is not None,'missing actual CLI/kernel binary')
            run(a,a.results)
            recovery_proof(a.unit,a.results)
            cases,windows=check(a.results)
            recover=verify_recovery(a.results)
    except Exception as e:
        (a.results/'long-metrology-failure.json').write_text(json.dumps({
            'status':'FAIL','reason':f'{type(e).__name__}: {e}'},indent=2)+'\n')
        (a.results/'long-metrology.json').unlink(missing_ok=True)
        (a.results/'certified-recovery.json').unlink(missing_ok=True)
        print(f'FAIL long metrology: {type(e).__name__}: {e}',file=sys.stderr)
        return 1
    print(f'PASS 0.5s q-x metrology: {cases} physical cases, {windows} beta/channel windows, '
          f'{windows*len(BANDS)} nine-band rows; {recover} independent recovery cases')
    return 0

if __name__=='__main__':raise SystemExit(main())
