#!/usr/bin/env python3
"""Prospective DSD256 P/S matched comparator, full-passband only.

The historical control's ``sinc -P`` centered its transition at the *last
passband frequency*, leading to a 6 dB mismatch at 66 kHz (mastering v2).
A correct comparator instead designs a high-rate pre-decimation FIR with
passband edge P, STOPBAND START S and *center* (P+S)/2; it must filter BEFORE
the final reduction. The legacy direct-rate initial hop is still part of the
control. A waveform comparison independently checks the entire declared P.

This is a *new immutable diagnostic receipt*. It does not change prior
benchmarks, claim physical prepared-host speedup, or independently certify
section 6.1's stringent composite transfer envelope.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from verify_dsd256_control_match import compare

ROOT=Path(__file__).resolve().parents[2]
SOURCES=('src/rate.c','src/fft4g.c','src/sinc.c','src/effects_i_dsp.c',
         'src/dsd_decode.c','src/dsd_coeffs.h','src/dsd_coeffs_v2.h',
         'tests/dsd/verify_dsd256_control_match.py')
PROFILES=(('mastering',40000,80000),('decode.mastering.v2.dsd256',66000,80000))
RATES=(176400,352800)
NATIVE=11289600
INTERMEDIATE=352800
SCHEMA='P15/new-dsd256-ps-matched-control/1'

class InvalidReceipt(ValueError): pass

def sha(data):
    return sha256(data).hexdigest()

def file_sha(path):
    return sha(path.read_bytes())

def sources():
    return {p:file_sha(ROOT/p) for p in SOURCES}

def command(sox,*,native,output,rate,pass_hz,stop_hz,wrong=False):
    center=(pass_hz+stop_hz)//2
    transition=stop_hz-pass_hz
    if transition<=0 or center>=INTERMEDIATE//2 or pass_hz>=stop_hz:
        raise InvalidReceipt('unrealizable matched control P/S')
    if wrong: center=20000
    # All filtering at 352.8 kHz, BEFORE last rate -v. The -t refers to
    # total transition WIDTH, not the passband frequency. Explicit -a180.
    return [str(sox),'-D',str(native),'-r',str(rate),'-e','floating-point','-b','64',
            str(output),'rate','-v',str(INTERMEDIATE),'sinc','-a','180','-t',
            str(transition),'-'+str(center),'rate','-v']

def run(argv):
    p=subprocess.run([str(x) for x in argv],cwd=ROOT,capture_output=True)
    if p.returncode:
        raise InvalidReceipt(f'command failed ({p.returncode}): {argv[-8:]}\n'
                             +p.stderr.decode(errors='replace')[-1800:])

def acquisition(folder,sox,candidate,seconds,wrong=False):
    if seconds<1.5 or seconds>30:
        raise InvalidReceipt('spectral fixture too short or exceeds bounded duration')
    src=folder/'noise-pcm.wav';native=folder/'noise-dsd256.dsf'
    run([sox,'-n','-r',str(INTERMEDIATE),'-b','32','-e','signed-integer',
         src,'synth',str(seconds),'whitenoise','vol','0.1'])
    run([candidate,'--dsd-layout-loss','warn',src,'-r',str(NATIVE),native,
         'pcmdsd',str(NATIVE)])
    rows=[]
    for profile,pass_hz,stop_hz in PROFILES:
        report=folder/('profile-'+profile+'.json')
        run([sox,'--dsd-report',report,'--dsd-layout-loss','warn',native,
             '-b','32','-e','signed-integer',folder/'discard-probe.wav',
             'dsdpcm','-p',profile,'-l','preserve',str(INTERMEDIATE)])
        decoded=json.loads(report.read_text())['processing']['decoder'][0]
        if decoded.get('profile_id') not in (profile, 'decode.mastering.v1.dsd256') or \
           decoded.get('effective_passband_hz')!=pass_hz:
            raise InvalidReceipt('production reported P/profile inconsistent with design')
        for rate in RATES:
            label=('v2' if 'v2' in profile else 'v1')+'-'+str(rate)
            dec=folder/('decoder-'+label+'.wav')
            ctl=folder/('control-'+label+'.wav')
            run([sox,'--dsd-layout-loss','warn',native,'-e','floating-point','-b','64',
                 dec,'dsdpcm','-p',profile,'-l','preserve',str(rate)])
            cmd=command(sox,native=native,output=ctl,rate=rate,
                         pass_hz=pass_hz,stop_hz=stop_hz,wrong=wrong)
            run(cmd)
            measured=compare(dec,ctl,pass_hz)
            if measured.get('transition_excluded_fraction')!=0 or \
               measured['comparison_band_hz'][1]!=pass_hz:
                raise InvalidReceipt('post-hoc shortened passband not admissible')
            rows.append(dict(profile=profile,reported_id=decoded['profile_id'],
                pass_hz=pass_hz,stop_hz=stop_hz,rate=rate,label=label,
                proposed_control=('sinc -a 180 -t '+str(stop_hz-pass_hz)+' -'+
                          str(20000 if wrong else (pass_hz+stop_hz)//2)),
                initial_intermediate_hz=INTERMEDIATE,
                verification=measured,
                decoder_wav_sha256=file_sha(dec),control_wav_sha256=file_sha(ctl)))
    return rows

def verify(folder,sox,candidate,*,allow_wrong=False):
    if not folder.is_dir() or folder.is_symlink():
        raise InvalidReceipt('missing/linked spectral receipt directory')
    receipt=json.loads((folder/'RECEIPT.json').read_text())
    if (receipt.get('schema')!=SCHEMA or receipt.get('source_sha256')!=sources() or
        receipt.get('executable_sha256')!=dict(sox=file_sha(sox),candidate=file_sha(candidate)) or
        receipt.get('qualified_release') is not False or
        receipt.get('initial_intermediate_hz')!=INTERMEDIATE):
        raise InvalidReceipt('receipt source/binary/schema drift')
    if (receipt.get('selftest_wrong_cutoff') is True)!=allow_wrong:
        raise InvalidReceipt('wrong-cutoff selftest not distinguishable from positive evidence')
    actual_files={p.name for p in folder.iterdir() if p.is_file()}
    expected_files=set(receipt['file_sha256'])|{'RECEIPT.json'}
    if actual_files!=expected_files or any(file_sha(folder/f)!=digest for f,digest in receipt['file_sha256'].items()):
        raise InvalidReceipt('missing/extra/modified receipt payload')
    if receipt['file_sha256']['noise-dsd256.dsf']!=receipt['native_sha256']:
        raise InvalidReceipt('native fixture provenance mismatch')
    if {(r['profile'],r['rate']) for r in receipt['rows']}!= {
          (p,rate) for p,_,_ in PROFILES for rate in RATES}:
        raise InvalidReceipt('missing P/S comparison cells')
    matched=True
    for row in receipt['rows']:
        _,p,s=next(x for x in PROFILES if x[0]==row['profile'])
        if row['pass_hz']!=p or row['stop_hz']!=s or row['initial_intermediate_hz']!=INTERMEDIATE:
            raise InvalidReceipt('control P/S not source defined')
        lbl=row['label']
        if row['decoder_wav_sha256']!=file_sha(folder/('decoder-'+lbl+'.wav')) or \
           row['control_wav_sha256']!=file_sha(folder/('control-'+lbl+'.wav')):
            raise InvalidReceipt('audio digest disagrees')
        recomputed=compare(folder/('decoder-'+lbl+'.wav'),
                           folder/('control-'+lbl+'.wav'),p)
        if row['verification']!=recomputed or recomputed['comparison_band_hz'][1]!=p or \
           recomputed['transition_excluded_fraction']!=0:
            raise InvalidReceipt('receipt spectral evidence non-reproducible or cropped')
        if row['proposed_control']!=('sinc -a 180 -t '+str(s-p)+' -'+
              str(20000 if allow_wrong else (p+s)//2)):
            raise InvalidReceipt('proposed command changed from reviewed P/S shape')
        matched &= recomputed['matched']
    if matched != receipt['spectrally_matched_on_fixture']:
        raise InvalidReceipt('result disagrees with all four rechecked cells')
    if receipt['status'] != ('SPECTRALLY_MATCHED_DIAGNOSTIC' if matched else 'CONTROL_MISMATCH'):
        raise InvalidReceipt('falsified status')
    return receipt

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=6.)
    ap.add_argument('--verify-only',action='store_true')
    ap.add_argument('--selftest-wrong-cutoff',action='store_true')
    a=ap.parse_args()
    sox=a.sox.resolve(strict=True);candidate=a.candidate.resolve(strict=True)
    output=a.output.resolve()
    if output.exists():
        report=verify(output,sox,candidate,allow_wrong=a.selftest_wrong_cutoff)
        print(json.dumps(dict(status=report['status'],reused_verified=True,
                              worst_full_band_db=max(r['verification']['max_abs_difference_db'] for r in report['rows']))))
        return 0 if report['spectrally_matched_on_fixture']!=a.selftest_wrong_cutoff else 1
    if a.verify_only: raise InvalidReceipt('no prior snapshot to verify')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
    try:
        rows=acquisition(stage,sox,candidate,a.seconds,wrong=a.selftest_wrong_cutoff)
        matched=all(r['verification']['matched'] for r in rows)
        (stage/'discard-probe.wav').unlink()
        identity={p.name:file_sha(p) for p in stage.iterdir() if p.is_file()}
        receipt=dict(schema=SCHEMA,qualified_release=False,
               status='SPECTRALLY_MATCHED_DIAGNOSTIC' if matched else 'CONTROL_MISMATCH',
               spectrally_matched_on_fixture=matched,source_sha256=sources(),
               executable_sha256=dict(sox=file_sha(sox),candidate=file_sha(candidate)),
               fixture_seconds=a.seconds,native_sha256=identity['noise-dsd256.dsf'],
               initial_intermediate_hz=INTERMEDIATE,selftest_wrong_cutoff=a.selftest_wrong_cutoff,
               rows=rows,file_sha256=identity,
               limitations=('Spectral diagnostic from SAME native one-channel broadband signal; '
                   'not a proof of absolute 0.0001 dB/-160 dB product limits. '
                   'Control configuration changed from historical timed arm; '
                   'none of the earlier 15-repetition physical speedups transfers to it.'))
        (stage/'RECEIPT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n')
        if output.exists(): raise InvalidReceipt('destination appeared while acquiring')
        stage.rename(output)
        report=verify(output,sox,candidate,allow_wrong=a.selftest_wrong_cutoff)
        print(json.dumps(dict(status=report['status'],
            worst_full_band_db=max(r['verification']['max_abs_difference_db'] for r in report['rows']))))
        return 0 if matched!=a.selftest_wrong_cutoff else 1
    finally:
        if stage.exists(): shutil.rmtree(stage)

if __name__=='__main__':raise SystemExit(main())
