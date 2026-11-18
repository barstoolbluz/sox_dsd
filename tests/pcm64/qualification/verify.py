#!/usr/bin/env python3
"""Read-only Phase 08 physical-family verifier with deliberate negative controls.

Verify actual WAV/DSF payloads, every selected window and their identities.
The instrumented/private kernel recurrence is checked by the producing suite;
this verifier independently checks the *published* physical evidence.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

from collections import Counter
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qualification import (PATTERNS, RATES, SOURCE_RATE, CHANNELS, FRAMES, BETAS,
    BANDS, WINDOW_LENGTH, stimulus, sha256, bandpower, native_window, plan_windows,
    demand)
from decode import parse_wav, checked_rate
from encode import dsf_bits, float_words


def check(root,record,source=None,sox=None,probe=None):
    source=(Path(source) if source is not None else Path(__file__).resolve().parents[3]).resolve()
    binaries=record.get('executed_binary_sha256',{})
    demand(isinstance(binaries,dict) and binaries and
           isinstance(record.get('source_artifacts_sha256'),dict) and
           len(record['source_artifacts_sha256'])>=6,
           'missing source or executable identities')
    for relative,expected_hash in record['source_artifacts_sha256'].items():
        path=source/relative
        demand(path.resolve().is_relative_to(source) and path.is_file() and
               sha256(path)==expected_hash,
               'changed source or certificate: '+relative)
    def bound_binary(name,explicit):
        matches=[Path(p) for p in binaries if p.endswith(name)]
        demand(len(matches)==1, 'ambiguous/missing binary identity '+name)
        path=Path(explicit) if explicit is not None else matches[0]
        demand(path.is_file() and sha256(path)==binaries[str(matches[0])],
               'stale executable: '+name)
        return path
    bound_binary('/src/sox',sox)
    bound_binary('/test/pcm64_encode_probe',probe)
    head=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],
        capture_output=True,text=True,check=False)
    if (source/'.git').exists():
        demand(head.returncode==0 and head.stdout.strip()==record.get('source_git_commit'),
               'stale source revision')
    demand(record['status']=='PASS' and record['schema']=='sox-native64-qualification/1',
           'receipt status/schema unavailable')
    demand(record['scope']=='FINITE_MEASUREMENTS_ONLY_NOT_RELEASE_CERTIFICATION',
           'false release claim')
    demand(record['case_count']==18 and record['window_count']==108 and
           record['spectral_rows']==864 and len(record['cases'])==18 and
           len(record['windows'])==216,'missing/extra physical cases or windows')
    demand(tuple(record['betas'])==BETAS and
           {k:tuple(v) for k,v in record['bands_half_open_hz'].items()}==BANDS,
           'changed beta or spectral band contract')
    demand(record['no_free_gain_or_shift_fits'] is True,
           'free gain/shift compensation silently enabled')
    observed=set(); expected={(f'dsd{hz//44100}-{p}') for hz in RATES for p in PATTERNS}
    physical_cache={}
    for case in record['cases']:
        cid=case['id']
        demand(cid not in observed and cid in expected,'extra/duplicate case: '+cid)
        observed.add(cid)
        hz=case['rate_hz']; pattern=case['pattern']; ch=case['channels']
        demand(cid==f'dsd{hz//44100}-{pattern}' and
               case['source_rate_hz']==SOURCE_RATE and
               case['source_frames']==FRAMES and ch==CHANNELS,
               'case identity/rate/channel metadata changed')
        source=Path(root)/case['source_path']
        dsf=Path(root)/case['dsf_path']
        recon=Path(root)/case['reconstructed_path']
        report=Path(root)/case['encode_report_path']
        decode_report=Path(root)/case['decode_report_path']
        demand(all(p.is_file() and p.resolve().is_relative_to(root.resolve())
                   for p in (source,dsf,recon,report,decode_report)),
               'missing/escaped physical file')
        for path,field in ((source,'source_wav_sha256'),(dsf,'physical_dsf_sha256'),
                           (recon,'reconstructed_wav_sha256'),
                           (report,'encoder_report_sha256'),
                           (decode_report,'decoder_report_sha256')):
            demand(sha256(path)==case[field],f'{cid}: corrupted {field}')
        source_bytes,_=parse_wav(source,FRAMES,CHANNELS,SOURCE_RATE)
        expected_bytes=float_words(stimulus(pattern))
        demand(source_bytes==expected_bytes and
               hashlib.sha256(source_bytes).hexdigest()==case['source_pcm_words_sha256'],
               f'{cid}: source words differ from independently generated recipe')
        n=(2*FRAMES*hz+SOURCE_RATE)//(2*SOURCE_RATE)
        demand(case['native_frames']==n,'native rate/count mismatch')
        physical=dsf_bits(dsf.read_bytes(),n,ch,hz)
        demand(hashlib.sha256(physical).hexdigest()==case['physical_dsd_bits_sha256'],
               f'{cid}: physical bits corrupted or remapped')
        n_pcm=checked_rate(n,hz,SOURCE_RATE)
        demand(case['reconstructed_frames']==n_pcm,'reconstructed rate/count mismatch')
        payload,_=parse_wav(recon,n_pcm,ch,SOURCE_RATE)
        demand(hashlib.sha256(payload).hexdigest()==case['reconstructed_float64_words_sha256'],
               f'{cid}: actual reconstructed binary64 words changed')
        er=json.loads(report.read_text()); dr=json.loads(decode_report.read_text())
        demand(er['status']=='complete' and dr['status']=='complete' and
               er['precision']['actual_route']=='native-binary64-encode' and
               dr['precision']['actual_route']=='native-binary64-pcm' and
               int(er['output']['frames_written'])==n and
               int(dr['output']['frames_written'])==n_pcm,
               f'{cid}: actual route or reported count incorrect')
        expected_starts=plan_windows(n)
        demand(case['analysis_starts']==expected_starts and
               case['profile_id']==f'encode.mastering.v3.dsd{hz//44100}' and
               case['recovery_entries']==[int(e['recovery_entries'])
                                         for e in er['processing']['encoder']],
               f'{cid}: wrong physical profile, window plan, recovery counters')
        physical_cache[cid]=(physical,n,hz,expected_starts)
    demand(observed==expected,'missing synthetic signal classes')
    window_keys=set()
    for rec in record['windows']:
        cid=rec['case']; channel=rec['channel'];start=rec['start_frame']
        beta=rec['window_kaiser_beta']
        key=(cid,channel,start,beta)
        demand(cid in physical_cache and channel in (0,1) and
               rec['duration_frames']==WINDOW_LENGTH and beta in BETAS and
               start in physical_cache[cid][3] and key not in window_keys,
               f'wrong/repeated window {key}')
        window_keys.add(key)
        bits,n,hz,_=physical_cache[cid]
        q=native_window(bits,CHANNELS,channel,start,WINDOW_LENGTH)
        dc, bands=bandpower(q,hz,beta)
        demand(math.isclose(rec['weighted_dc'],dc,abs_tol=1e-14),
               f'{cid} window {start}: weighted DC mutated')
        demand(rec['bands'].keys()==bands.keys(),f'{cid}: missing band')
        for name, value in bands.items():
            have=rec['bands'][name]
            demand(have['bins']==value['bins'] and
                   math.isclose(have['power'],value['power'],rel_tol=5e-12,abs_tol=1e-20) and
                   math.isclose(have['dbfs'],value['dbfs'],rel_tol=0,abs_tol=5e-8),
                   f'{cid} window {start}: altered band {name}')
    demand(len(window_keys)==18*2*3*2,'zero or missing window combinations')
    return len(physical_cache), len(window_keys)


def negative_controls(root,record,source=None,sox=None,probe=None):
    """Each control perturbs the signed receipt or physical files in a tmp root.

    These are verifier-integrity tests, not replacements for existing
    independent FENV/close-error oracles in foundation/I/O suites.
    """
    import tempfile
    import shutil
    cases=[]
    def reject(name,mutate):
        changed=copy.deepcopy(record)
        with tempfile.TemporaryDirectory(prefix='p08-neg-') as temp:
            shadow=Path(temp)
            # Link unchanged immutable physical files, copy only any changed file.
            (shadow/'native64-family').mkdir()
            for case in record['cases']:
                for key in ('source_path','dsf_path','reconstructed_path',
                            'encode_report_path','decode_report_path'):
                    p=Path(case[key]);dst=shadow/p
                    if not dst.exists(): os.link((root/p).resolve(),dst)
            mutate(changed,shadow)
            try: check(shadow,changed,source,sox,probe)
            except (AssertionError,KeyError,ValueError,TypeError,IndexError, OSError) as exc:
                cases.append({'control':name,'status':'REJECTED','detector':str(exc)[:220]})
            else: raise AssertionError(f'{name}: mutation falsely verified')
    reject('deleted_case',lambda d,s:d['cases'].pop())
    reject('duplicate_case',lambda d,s:d['cases'].__setitem__(1,copy.deepcopy(d['cases'][0])))
    reject('stale_source_manifest',lambda d,s:d['cases'][0].__setitem__('source_wav_sha256','0'*64))
    reject('false_legacy_route',lambda d,s:d['cases'][0].__setitem__('profile_id','encode.legacy'))
    reject('missing_analysis_window',lambda d,s:d['windows'].pop())
    reject('duplicate_analysis_window',lambda d,s:d['windows'].__setitem__(1,copy.deepcopy(d['windows'][0])))
    reject('wrong_alignment_window_start',lambda d,s:d['windows'][0].__setitem__('start_frame',d['windows'][0]['start_frame']+1))
    reject('mutated_window_dc',lambda d,s:d['windows'][0].__setitem__('weighted_dc',.123))
    reject('wrong_window_normalization',lambda d,s:d['windows'][0]['bands']['20-20k'].__setitem__('dbfs',d['windows'][0]['bands']['20-20k']['dbfs']+3.01029995664))
    reject('reduced_precision_power',lambda d,s:d['windows'][0]['bands']['20-20k'].__setitem__('power',d['windows'][0]['bands']['20-20k']['power']*1.01))
    reject('band_endpoint_overlap',lambda d,s:d['bands_half_open_hz'].__setitem__('20-20k',[20,20001]))
    reject('beta_sensitivity_suppressed',lambda d,s:d.__setitem__('betas',[30.,30.]))
    reject('false_complete',lambda d,s:d.__setitem__('status','RUNNING'))
    reject('stale_output_hash',lambda d,s:d['cases'][0].__setitem__('physical_dsf_sha256','f'*64))
    reject('false_reconstruction',lambda d,s:d['cases'][0].__setitem__('reconstructed_float64_words_sha256','a'*64))
    reject('tail_frame_miscount',lambda d,s:d['cases'][0].__setitem__('native_frames',d['cases'][0]['native_frames']-1))
    reject('channel_swapped_metadata',lambda d,s:d['cases'][0].__setitem__('channels',1))
    reject('stale_case_recovery',lambda d,s:d['cases'][0].__setitem__('recovery_entries',[9,9]))
    reject('altered_fir_certificate',lambda d,s:d['source_artifacts_sha256'].__setitem__('src/pcmdsd.c','0'*64))
    reject('changed_qualification_source',lambda d,s:d['source_artifacts_sha256'].__setitem__('tests/pcm64/qualification.py','f'*64))
    def stale_binary(d,s):
        key=next(k for k in d['executed_binary_sha256'] if k.endswith('/src/sox'))
        d['executed_binary_sha256'][key]='f'*64
    reject('stale_sox_binary',stale_binary)
    def physical_flip(d,s):
        path=Path(d['cases'][0]['dsf_path']);dest=s/path
        original=(root/path).read_bytes()
        dest.unlink();dest.write_bytes(original[:-1]+bytes([original[-1]^1]))
    reject('corrupted_dsf_storage',physical_flip)
    demand(len(cases)==22,'negative controls missing')
    return cases


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--negative-controls',action='store_true')
    parser.add_argument('--source',type=Path)
    parser.add_argument('--sox',type=Path)
    parser.add_argument('--probe',type=Path)
    args=parser.parse_args()
    root=args.results.resolve()
    record=json.loads((root/'qualification.json').read_text())
    a,b=check(root,record,args.source,args.sox,args.probe)
    negatives=negative_controls(root,record,args.source,args.sox,args.probe) if args.negative_controls else []
    print(json.dumps({'status':'PASS','physical_cases':a,'beta_windows':b,
          'negative_controls':len(negatives),'controls':negatives},indent=2))

if __name__=='__main__':main()
