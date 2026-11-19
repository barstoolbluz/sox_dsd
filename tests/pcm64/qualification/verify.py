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
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

import numpy as np

# Decode/encode are sibling qualification drivers, not the physical stimulus
# or expected-signal recipe. Keep their import path independent of the cwd.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audited_spectrum import (BANDS as REFERENCE_BANDS, BETAS as REFERENCE_BETAS,
                              FS_POWER as REFERENCE_FS_POWER,
                              analyze as reference_bandpower, compare as compare_spectrum)
from attestation import (digest as sha256, verify as verify_accepted_source,
                         physical_contract, approved_behavior)
from build_context import read_fenv
from decode import parse_wav, checked_rate
from encode import dsf_bits


def demand(ok,message):
    if not ok:raise AssertionError(message)


def native_window(bits,channels,channel,start,length):
    """Interpret observed physical decisions using the audited +/-0.5 scale.

    Never import the producer's native_window(), which is itself one of the
    semantics this independent physical verifier is meant to protect.
    """
    values=np.frombuffer(bits,dtype=np.uint8)
    demand(values.size%channels==0 and np.all(values<=1),
           'non-binary physical DSD stream')
    chunk=values.reshape(-1,channels)[start:start+length,channel]
    demand(chunk.size==length,'missing physical DSD window bits')
    return chunk.astype('float64')-.5


def check(root,record,source=None,sox=None,probe=None,oracle=None):
    source=(Path(source) if source is not None else Path(__file__).resolve().parents[3]).resolve()
    pin=verify_accepted_source(source)
    contract=physical_contract()
    fixed_cases=contract['short']['cases']
    accepted_words=approved_behavior()['short_cases']
    demand(set(accepted_words)==set(fixed_cases),'incomplete frozen physical behavioral reference')
    source_rate=contract['source_rate_hz']
    channels=contract['channels']
    window_n=contract['short']['window_length_frames']
    demand(window_n==8192 and REFERENCE_FS_POWER==.125,
           'changed audited short-window duration or nominal DSD full scale')
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
    bound_binary('/src/sox_p08_qualification',sox)
    probe_binary=bound_binary('/test/pcm64_encode_probe',probe)
    oracle_binary=bound_binary('/test/pcm64_decode_api_oracle',oracle)
    head=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],
        capture_output=True,text=True,check=False)
    if not (source/'.git').exists():
        # Provenance without Git must still be tied to the accepted source
        # inventory; the pin check above covers all 286 tracked src/ C/H files.
        demand(record.get('accepted_production_revision')==pin['accepted_production_revision'],
               'missing accepted revision in source-free receipt')
    else:
        demand(head.returncode==0 and head.stdout.strip()==record.get('source_git_commit'),
               'stale source revision')
    demand(record['status']=='PASS' and record['schema']=='sox-native64-qualification/2',
           'receipt status/schema unavailable')
    demand(record['scope']=='FINITE_MEASUREMENTS_ONLY_NOT_RELEASE_CERTIFICATION',
           'false release claim')
    demand(record['full_scale']==
           'nominal DSD = +/-0.5; sinusoidal full-scale RMS power 0.125',
           'changed nominal one-bit full-scale convention')
    demand(record['case_count']==18 and record['window_count']==108 and
           record['spectral_rows']==1944 and len(record['cases'])==18 and
           len(record['windows'])==216,'missing/extra physical cases or windows')
    demand(tuple(record['betas'])==REFERENCE_BETAS and
           {k:tuple(v) for k,v in record['bands_half_open_hz'].items()}==REFERENCE_BANDS,
           'changed beta or spectral band contract')
    demand(record['no_free_gain_or_shift_fits'] is True,
           'free gain/shift compensation silently enabled')
    observed=set(); expected=set(fixed_cases)
    physical_cache={}
    for case in record['cases']:
        cid=case['id']
        demand(cid not in observed and cid in expected,'extra/duplicate case: '+cid)
        observed.add(cid)
        frozen=fixed_cases[cid]
        hz=case['rate_hz']; pattern=case['pattern']; ch=case['channels']
        demand(cid==f'dsd{hz//44100}-{pattern}' and
               case['source_rate_hz']==source_rate and
               case['source_frames']==frozen['source_frames'] and
               hz==frozen['rate_hz'] and ch==channels,
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
        for stage in ('encode','decode'):
            witness=case['same_process_fenv'][stage]
            p=Path(root)/witness['path']
            demand(p.resolve().is_relative_to(root.resolve()) and p.is_file(),
                   f'{cid}: escaped/missing CLI process FENV witness')
            fresh=read_fenv(p)
            demand(all(fresh[k]==witness[k] for k in fresh if k!='path'),
                   f'{cid}: altered CLI process FENV data')
        source_bytes,_=parse_wav(source,frozen['source_frames'],channels,source_rate)
        words_sha=hashlib.sha256(source_bytes).hexdigest()
        demand(words_sha==frozen['source_pcm_words_sha256'] and
               words_sha==case['source_pcm_words_sha256'],
               f'{cid}: source words differ from frozen accepted physical contract')
        n=(2*frozen['source_frames']*hz+source_rate)//(2*source_rate)
        demand(case['native_frames']==n==frozen['native_frames'],
               f'{cid}: native rate/count mismatch')
        physical=dsf_bits(dsf.read_bytes(),n,ch,hz)
        want_words=accepted_words[cid]
        demand(hashlib.sha256(physical).hexdigest()==want_words['physical_dsd_bits_sha256'],
               f'{cid}: actual physical DSD bits deviate from accepted independent decision stream')
        demand(hashlib.sha256(physical).hexdigest()==case['physical_dsd_bits_sha256'],
               f'{cid}: physical bits corrupted or remapped')
        n_pcm=checked_rate(n,hz,source_rate)
        demand(case['reconstructed_frames']==n_pcm,'reconstructed rate/count mismatch')
        payload,_=parse_wav(recon,n_pcm,ch,source_rate)
        demand(hashlib.sha256(payload).hexdigest()==case['reconstructed_float64_words_sha256'],
               f'{cid}: actual reconstructed binary64 words changed')
        demand(hashlib.sha256(payload).hexdigest()==want_words['reconstructed_float64_words_sha256'],
               f'{cid}: actual reconstructed FLOAT64 payload deviates from accepted independent words')
        # Observe the *actual* CLI's admission trace, not merely the private
        # probe's forecast. Recompute the independent probe expectation from
        # the exact physical source WAV words, then demand byte equality for
        # both channels and native frame order, even when emitted bits match.
        paths=case['actual_admitted_paths']
        demand(len(paths)==ch and len(case['post_clip_admitted_sha256'])==ch and
               len(case['actual_admitted_sha256'])==ch and
               case['admitted_frames_per_channel']==[n]*ch,
               f'{cid}: missing real admitted-word counts')
        traces=[]
        for channel,relative in enumerate(paths):
            trace=Path(root)/relative
            demand(trace.resolve().is_relative_to(root.resolve()) and trace.is_file(),
                   f'{cid}: real admission trace absent')
            raw=trace.read_bytes()
            demand(len(raw)==8*n and
                   hashlib.sha256(raw).hexdigest()==case['actual_admitted_sha256'][channel],
                   f'{cid}: actual CLI admission word count/hash changed')
            demand(hashlib.sha256(raw).hexdigest()==want_words['actual_admitted_sha256'][channel],
                   f'{cid}: actual modulator input words deviate from accepted independent words')
            traces.append(raw)
        with tempfile.TemporaryDirectory(prefix='p08-reprobe-') as tmp:
            prefix=str(Path(tmp)/'expected')
            args=[str(probe_binary),'--encode',str(source_rate),str(hz),str(ch),
                  '256','512','1','1.0','0.5',prefix]
            cp=subprocess.run(args,input=source_bytes,capture_output=True,timeout=90)
            demand(cp.returncode==0 and cp.stdout==physical,
                   f'{cid}: independent encoder decision stream changed')
            meta=json.loads(cp.stderr)
            demand(int(meta['native_frames'])==n and
                   int(meta['source_frames'])==frozen['source_frames'] and
                   int(meta['channels'])==ch,
                   f'{cid}: independent encoder counts changed')
            for channel in range(ch):
                expected_words=Path(prefix+f'.ch{channel}.f64').read_bytes()
                demand(expected_words==traces[channel] and
                       hashlib.sha256(expected_words).hexdigest()==
                           case['post_clip_admitted_sha256'][channel],
                       f'{cid} channel {channel}: real admitted words differ from independent probe')
            demand([int(x['recovery_entries']) for x in meta['record']]==
                   case['recovery_entries'],f'{cid}: independent recovery accounting changed')
            oracle_raw=Path(root)/case['public_decoder_raw_path']
            demand(oracle_raw.resolve().is_relative_to(root.resolve()) and
                   oracle_raw.is_file() and
                   sha256(oracle_raw)==case['public_decoder_raw_sha256'],
                   f'{cid}: missing/corrupted independent reconstruction witness')
            dc=case['public_decoder_config']
            demand(dc['profile']=='mastering-v2' and dc['level']=='preserve' and
                   dc['bandwidth']=='adapt' and dc['kernel'] in
                   ('scalar','sse2','avx1','avx2','avx512'),
                   f'{cid}: altered public decoder configuration')
            api_out=Path(tmp)/'oracle.f64'
            api=subprocess.run([str(oracle_binary),str(dsf),str(api_out),str(source_rate),
                 dc['profile'],dc['level'],dc['bandwidth'],dc['kernel']],
                 capture_output=True,timeout=90)
            demand(api.returncode==0 and b'finish=done' in api.stdout and
                   api_out.is_file() and api_out.read_bytes()==payload and
                   oracle_raw.read_bytes()==payload,
                   f'{cid}: CLI FLOAT64 reconstructed words disagree with independent public decoder')
        er=json.loads(report.read_text()); dr=json.loads(decode_report.read_text())
        demand(er['status']=='complete' and dr['status']=='complete' and
               er['precision']['actual_route']=='native-binary64-encode' and
               dr['precision']['actual_route']=='native-binary64-pcm' and
               int(er['output']['frames_written'])==n and
               int(dr['output']['frames_written'])==n_pcm,
               f'{cid}: actual route or reported count incorrect')
        decoder=dr['processing']['decoder'][0]
        demand(decoder['profile_id']==f'decode.mastering.v2.dsd{hz//44100}' and
               decoder['gain_mapping']['mode']=='preserve' and
               decoder['fir_kernel_actual']==case['public_decoder_config']['kernel'],
               f'{cid}: real decoder report does not bind reference options')
        encoder=er['processing']['encoder']
        demand(len(encoder)==ch and all(e['profile_id']==case['profile_id'] and
               e['sdm_kernel_actual']=='resonator' and
               int(e['committed_native_frames'])==n and
               int(e['clipped_interpolated_samples'])==0 for e in encoder),
               f'{cid}: unexpected real encoder profile, clip or committed count')
        expected_starts=frozen['window_starts']
        demand(len(expected_starts)==3 and len(set(expected_starts))==3 and
               all(0<=s<=n-window_n for s in expected_starts),
               f'{cid}: invalid accepted window starts')
        demand(case['analysis_starts']==expected_starts and
               case['profile_id']==f'encode.mastering.v3.dsd{hz//44100}' and
               case['recovery_entries']==[int(e['recovery_entries'])
                                         for e in er['processing']['encoder']],
               f'{cid}: wrong physical profile, window plan, recovery counters')
        physical_cache[cid]=(physical,n,hz,expected_starts,traces)
    demand(observed==expected,'missing synthetic signal classes')
    window_keys=set()
    for rec in record['windows']:
        cid=rec['case']; channel=rec['channel'];start=rec['start_frame']
        beta=rec['window_kaiser_beta']
        key=(cid,channel,start,beta)
        demand(cid in physical_cache and channel in (0,1) and
               rec['duration_frames']==window_n and beta in REFERENCE_BETAS and
               start in physical_cache[cid][3] and key not in window_keys,
               f'wrong/repeated window {key}')
        window_keys.add(key)
        bits,n,hz,_,traces=physical_cache[cid]
        q=native_window(bits,channels,channel,start,window_n)
        x=np.frombuffer(traces[channel],dtype='<f8',count=window_n,offset=start*8)
        compare_spectrum(rec,reference_bandpower(q-x,hz,beta),f'{cid} window {start}')
    demand(len(window_keys)==18*2*3*2,'zero or missing window combinations')
    return len(physical_cache), len(window_keys)


def negative_controls(root,record,source=None,sox=None,probe=None,oracle=None):
    """Each control perturbs the signed receipt or physical files in a tmp root.

    These are verifier-integrity tests, not replacements for existing
    independent FENV/close-error oracles in foundation/I/O suites.
    """
    import tempfile
    import shutil
    cases=[]
    def reject(name,mutate,detector=None):
        changed=copy.deepcopy(record)
        with tempfile.TemporaryDirectory(prefix='p08-neg-') as temp:
            shadow=Path(temp)
            # Link unchanged immutable physical files, copy only any changed file.
            (shadow/'native64-family').mkdir()
            for case in record['cases']:
                for key in ('source_path','dsf_path','reconstructed_path',
                            'encode_report_path','decode_report_path',
                            'public_decoder_raw_path'):
                    p=Path(case[key]);dst=shadow/p
                    if not dst.exists(): shutil.copyfile((root/p).resolve(),dst)
                    # A copy works even when TMPDIR is a distinct filesystem.
                for stage in ('encode','decode'):
                    p=Path(case['same_process_fenv'][stage]['path']);dst=shadow/p
                    if not dst.exists():shutil.copyfile((root/p).resolve(),dst)
                for p in case['actual_admitted_paths']:
                    dst=shadow/p
                    if not dst.exists(): shutil.copyfile((root/p).resolve(),dst)
                    # A copy works even when TMPDIR is a distinct filesystem.
            fault=mutate(changed,shadow)
            try: check(shadow,changed,source,sox,probe,oracle)
            except (AssertionError,KeyError,ValueError,TypeError,IndexError, OSError) as exc:
                seen=str(exc)
                if detector is not None:
                    demand(detector in seen,
                           f'{name}: wrong detector ({seen!r}); physical fault unproven')
                case={'control':name,'status':'REJECTED','detector':seen[:220]}
                if fault is not None:case['physical_fault']=fault
                cases.append(case)
            else: raise AssertionError(f'{name}: mutation falsely verified')
    reject('deleted_case',lambda d,s:d['cases'].pop())
    reject('duplicate_case',lambda d,s:d['cases'].__setitem__(1,copy.deepcopy(d['cases'][0])))
    reject('stale_source_manifest',lambda d,s:d['cases'][0].__setitem__('source_wav_sha256','0'*64))
    reject('false_legacy_route',lambda d,s:d['cases'][0].__setitem__('profile_id','encode.legacy'))
    reject('missing_analysis_window',lambda d,s:d['windows'].pop())
    reject('duplicate_analysis_window',lambda d,s:d['windows'].__setitem__(1,copy.deepcopy(d['windows'][0])))
    reject('wrong_alignment_window_start',lambda d,s:d['windows'][0].__setitem__('start_frame',d['windows'][0]['start_frame']+1))
    reject('mutated_window_dc',lambda d,s:d['windows'][0].__setitem__('weighted_dc',.123))
    reject('wrong_window_normalization',lambda d,s:d['windows'][0]['bands']['20_20k'].__setitem__('dbfs',d['windows'][0]['bands']['20_20k']['dbfs']+3.01029995664))
    reject('reduced_precision_power',lambda d,s:d['windows'][0]['bands']['20_20k'].__setitem__('power',d['windows'][0]['bands']['20_20k']['power']*1.01))
    reject('band_endpoint_overlap',lambda d,s:d['bands_half_open_hz'].__setitem__('20_20k',[20,20001]))
    reject('beta_sensitivity_suppressed',lambda d,s:d.__setitem__('betas',[30.,30.]))
    reject('false_complete',lambda d,s:d.__setitem__('status','RUNNING'))
    reject('stale_output_hash',lambda d,s:d['cases'][0].__setitem__('physical_dsf_sha256','f'*64))
    reject('false_reconstruction',lambda d,s:d['cases'][0].__setitem__('reconstructed_float64_words_sha256','a'*64))
    # Retain the original 25 receipt/physical-storage corruptions, and add
    # three genuine physical-stream mutations below. These two are deliberately
    # labeled *metadata* faults, not evidence of altered channel/tail audio.
    reject('tail_frame_miscount',lambda d,s:d['cases'][0].__setitem__('native_frames',d['cases'][0]['native_frames']-1))
    reject('channel_swapped_metadata',lambda d,s:d['cases'][0].__setitem__('channels',1))
    reject('stale_case_recovery',lambda d,s:d['cases'][0].__setitem__('recovery_entries',[9,9]))
    reject('altered_fir_certificate',lambda d,s:d['source_artifacts_sha256'].__setitem__('src/pcmdsd.c','0'*64))
    reject('changed_qualification_source',lambda d,s:d['source_artifacts_sha256'].__setitem__('tests/pcm64/qualification.py','f'*64))
    def stale_binary(d,s):
        key=next(k for k in d['executed_binary_sha256'] if k.endswith('/src/sox_p08_qualification'))
        d['executed_binary_sha256'][key]='f'*64
    reject('stale_sox_binary',stale_binary)
    def physical_flip(d,s):
        path=Path(d['cases'][0]['dsf_path']);dest=s/path
        original=(root/path).read_bytes()
        dest.unlink();dest.write_bytes(original[:-1]+bytes([original[-1]^1]))
    reject('corrupted_dsf_storage',physical_flip)
    reject('altered_probe_admission_hash',
           lambda d,s:d['cases'][0]['post_clip_admitted_sha256'].__setitem__(0,'0'*64))
    def quiet_admission_mutant(d,s):
        # Change a genuinely quiet admitted binary64 word by 2^-40, but
        # update its own storage hash to test a coherent forged trace.
        case=d['cases'][0];p=Path(case['actual_admitted_paths'][0]);dest=s/p
        raw=bytearray((root/p).read_bytes());old=struct.unpack_from('<d',raw,0)[0]
        struct.pack_into('<d',raw,0,old+2.**-40)
        dest.unlink();dest.write_bytes(raw)
        case['actual_admitted_sha256'][0]=hashlib.sha256(raw).hexdigest()
    reject('coherent_quiet_2pow_minus40_admission_mutation',quiet_admission_mutant)
    def zero_reconstruction_mutant(d,s):
        case=next(c for c in d['cases'] if c['id']=='dsd64-dc')
        p=Path(case['reconstructed_path']);dest=s/p
        raw=bytearray((root/p).read_bytes());at=raw.index(b'data')+8
        # Replace the actual WAV payload, retain a valid F64 header and count.
        length=struct.unpack_from('<I',raw,at-4)[0]
        raw[at:at+length]=b'\0'*length
        dest.unlink();dest.write_bytes(raw)
        case['reconstructed_wav_sha256']=hashlib.sha256(raw).hexdigest()
        case['reconstructed_float64_words_sha256']=hashlib.sha256(b'\0'*length).hexdigest()
    reject('zeroed_dc_reconstruction_with_updated_hashes',zero_reconstruction_mutant)

    def physical_native_mutant(d,s,kind):
        case=next(c for c in d['cases'] if c['id']=='dsd64-tone')
        p=Path(case['dsf_path']);raw=bytearray((root/p).read_bytes())
        n=case['native_frames'];hz=case['rate_hz'];ch=case['channels']
        demand(ch==2 and n>2,'need distinct, nonempty stereo native stream')
        before=dsf_bits(raw,n,ch,hz)
        if kind=='channel_swap':
            demand(before[::2]!=before[1::2], 'channel-swap stimulus is symmetric')
            for offset in range(92,len(raw),8192):
                left=bytes(raw[offset:offset+4096]);right=bytes(raw[offset+4096:offset+8192])
                raw[offset:offset+4096]=right
                raw[offset+4096:offset+8192]=left
            new_n=n
            wanted=bytes(v for i in range(0,len(before),2)
                         for v in (before[i+1],before[i]))
        else:
            delta=-1 if kind=='drop_tail' else 1
            new_n=n+delta
            demand((new_n+32767)//32768==(n+32767)//32768,
                   'DSF mutation needs only the existing storage blocks')
            struct.pack_into('<Q',raw,64,new_n)  # coherent logical native count
            wanted=before[:-ch] if delta<0 else before+before[-ch:]
            if delta>0:
                # Write a *real* additional logical native bit for both channels.
                for channel,bit in enumerate(before[-ch:]):
                    offset=92+(n//32768)*ch*4096+channel*4096+(n//8)%4096
                    mask=1<<(n%8)
                    raw[offset]=(raw[offset]&~mask)|(mask if bit else 0)
            else:
                # The frame removed from the logical stream is padding now.
                for channel in range(ch):
                    f=n-1
                    offset=92+(f//32768)*ch*4096+channel*4096+(f//8)%4096
                    raw[offset]&=~(1<<(f%8))
        after=dsf_bits(raw,new_n,ch,hz)
        demand(after==wanted and after!=before,
               f'{kind}: actual physical native payload did not change as intended')
        (s/p).write_bytes(raw)
        case['native_frames']=new_n
        case['physical_dsf_sha256']=hashlib.sha256(raw).hexdigest()
        case['physical_dsd_bits_sha256']=hashlib.sha256(after).hexdigest()
        return {'before_native_frames':n,'mutated_native_frames':new_n,
                'mutated_bits_sha256':case['physical_dsd_bits_sha256'],
                'mutated_storage_sha256':case['physical_dsf_sha256']}

    reject('physical_stereo_channel_swap',
           lambda d,s:physical_native_mutant(d,s,'channel_swap'),
           detector='actual physical DSD bits deviate from accepted independent decision stream')
    reject('physical_dropped_native_tail',
           lambda d,s:physical_native_mutant(d,s,'drop_tail'),
           detector='native rate/count mismatch')
    reject('physical_duplicated_native_tail',
           lambda d,s:physical_native_mutant(d,s,'duplicate_tail'),
           detector='native rate/count mismatch')

    # Coherent generator/receipt revisions: recompute the affected numerical
    # readings and update the mutated file's own checksums. The independent
    # reviewed contract, rather than the generator or a stale hash, must fail.
    def reread_window(d,w,beta,start):
        case=next(c for c in d['cases'] if c['id']==w['case'])
        n=case['native_frames'];hz=case['rate_hz'];ch=w['channel']
        bits=dsf_bits((root/case['dsf_path']).read_bytes(),n,case['channels'],hz)
        trace=(root/case['actual_admitted_paths'][ch]).read_bytes()
        size=d['windows'][0]['duration_frames']
        q=native_window(bits,case['channels'],ch,start,size)
        x=np.frombuffer(trace,dtype='<f8',count=size,offset=start*8)
        dc,bands=reference_bandpower(q-x,hz,beta)
        w.update(start_frame=start,window_kaiser_beta=beta,
                 weighted_dc=dc,bands=bands)

    def changed_beta_family(d,s):
        d['betas']=[30.,33.]
        for w in d['windows']:
            if w['window_kaiser_beta']==34.:
                reread_window(d,w,33.,w['start_frame'])
        demand(sum(w['window_kaiser_beta']==33. for w in d['windows'])==108,
               'beta-mutant observations not regenerated')
    reject('coherent_beta_34_to_33_remeasured',changed_beta_family,
           detector='changed beta or spectral band contract')

    def changed_quiet_source(d,s):
        case=next(c for c in d['cases'] if c['id']=='dsd64-quiet')
        p=Path(case['source_path'])
        raw=bytearray((root/p).read_bytes());start=raw.index(b'data')+8
        old=struct.unpack_from('<d',raw,start)[0]
        struct.pack_into('<d',raw,start,old+2.**-40)
        (s/p).write_bytes(raw)
        case['source_wav_sha256']=hashlib.sha256(raw).hexdigest()
        size=struct.unpack_from('<I',raw,start-4)[0]
        case['source_pcm_words_sha256']=hashlib.sha256(raw[start:start+size]).hexdigest()
    reject('coherent_quiet_source_2pow_minus40',changed_quiet_source,
           detector='source words differ from frozen accepted physical contract')

    def changed_window_plan(d,s):
        case=next(c for c in d['cases'] if c['id']=='dsd64-quiet')
        old=case['analysis_starts'][0];new=old+1
        case['analysis_starts'][0]=new
        for w in d['windows']:
            if w['case']==case['id'] and w['start_frame']==old:
                reread_window(d,w,w['window_kaiser_beta'],new)
        demand(sum(w['case']==case['id'] and w['start_frame']==new
                   for w in d['windows'])==4,
               'window-plan-mutant readings not regenerated')
    reject('coherent_window_start_remeasured',changed_window_plan,
           detector='wrong physical profile, window plan, recovery counters')
    demand(len(cases)==31,'physical/receipt/contract negative controls missing')
    return cases


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--negative-controls',action='store_true')
    parser.add_argument('--source',type=Path)
    parser.add_argument('--sox',type=Path)
    parser.add_argument('--probe',type=Path)
    parser.add_argument('--oracle',type=Path)
    args=parser.parse_args()
    root=args.results.resolve()
    record=json.loads((root/'qualification.json').read_text())
    a,b=check(root,record,args.source,args.sox,args.probe,args.oracle)
    negatives=negative_controls(root,record,args.source,args.sox,args.probe,args.oracle) if args.negative_controls else []
    print(json.dumps({'status':'PASS','physical_cases':a,'beta_windows':b,
          'negative_controls':len(negatives),'controls':negatives},indent=2))

if __name__=='__main__':main()
