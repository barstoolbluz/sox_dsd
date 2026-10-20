#!/usr/bin/env python3
"""P15 CLI profile-ID, release activation, reference, and explicit legacy regressions.

Only test measured/executed behavior. This is not a replacement for frozen
analysis-v1, independent source corpora, long soaks or physical host benches.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

from reference import fixtures

RATES=(2822400,5644800,11289600)
PCM=(44100,48000,88200,96000,176400,192000,352800,384000,705600)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    sox=a.sox.resolve()
    if not sox.is_file():ap.error('sox executable does not exist')
    a.results.mkdir(parents=True,exist_ok=True)
    outfile=a.results/'cli-qualification.json'
    rows=[]
    def save():
        status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL'
        obj=dict(schema='P15/cli-qualification/1',status=status,
                 acceptance='CLI only; no physical/long-duration quality qualification',
                 summary=dict(passed=sum(r['status']=='PASS' for r in rows),
                              failed=sum(r['status']!='PASS' for r in rows)), cases=rows)
        tmp=outfile.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
        tmp.replace(outfile)
    def case(name,fn):
        try:
            detail=fn()
            rows.append(dict(name=name,status='PASS',detail=detail))
        except Exception as e:
            rows.append(dict(name=name,status='FAIL',error=f'{type(e).__name__}: {e}'))
            print('FAIL',name,e,flush=True)
        save()
    def run(*parts):
        cmd=[str(sox),*map(str,parts)]
        cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,
            text=True,timeout=55,env={**os.environ,'SOX_OPTS':'','OMP_NUM_THREADS':'1','LC_ALL':'C'})
        return cp
    def expected(cond,msg):
        if not cond:raise AssertionError(msg)
    def plan(*parts):
        cp=run('--dsd-plan',*parts)
        expected(cp.returncode==0,f'plan exit {cp.returncode}: {cp.stderr[:400]}')
        return json.loads(cp.stdout)
    with tempfile.TemporaryDirectory(prefix='p15-cli-') as scratch:
        t=Path(scratch)
        dsd={}
        for rate in RATES:
            path=t/f'dsd{rate//44100}.dsf'
            path.write_bytes(fixtures.make_dsf(fixtures.bits(65536,2),rate))
            dsd[rate]=path
        wav=t/'src.wav'
        with wave.open(str(wav),'wb') as f:
            f.setnchannels(1);f.setframerate(88200);f.setsampwidth(4)
            x=np.arange(16384,dtype=np.float64)
            f.writeframes(np.rint((2**31-1)*.125*np.sin(2*np.pi*x*997/88200)).astype('<i4').tobytes())

        # This checks every first-release native/input-rate/profile/output-rate
        # selection without assuming that preflight passes imply spectra pass.
        for rate,source in dsd.items():
            for profile in ('mastering','wideband'):
                ident=f'decode.{profile}.v1.dsd{rate//44100}'
                for hz in PCM:
                    def decode_plan(rate=rate,source=source,profile=profile,ident=ident,hz=hz):
                        p=plan('--dsd-decode',ident,source,'-r',hz,t/'plan.wav')
                        expected(p['decoder']['id']==ident,'wrong pinned decoder')
                        expected(p['policy']['decode']==profile,'policy profile mismatch')
                        expected(p['decoder']['gain']==1,'preserve decoder silently gained')
                        expected(p['output']['rate_hz']==hz,'PCM destination clock mismatch')
                        expected(p['executable'] is True,'qualified decoder unavailable')
                        expected(not (t/'plan.wav').exists(),'plan-only created audio')
                        return dict(native_hz=rate,pcm_hz=hz,profile_id=ident,
                                    bandwidth_hz=p['decoder']['effective_bandwidth_hz'])
                    case(f'versioned_decode_plan_{rate//44100}_{profile}_{hz}',decode_plan)
                    # Execute both paths, not merely their plans. A pinned CLI
                    # ID must not silently select another decoder, rate, or
                    # PCM reference when used for actual output.
                    def decode_wav(rate=rate,source=source,profile=profile,ident=ident,hz=hz):
                        pinned=t/'pinned.wav';human=t/'human.wav'
                        common=('--dsd-mode','auto','-D',source,'-r',hz,
                                '-e','signed-integer','-b',32)
                        p=run('--dsd-decode',ident,*common,pinned)
                        q=run('--dsd-decode',profile,*common,human)
                        expected(p.returncode==0 and q.returncode==0,
                            f'actual decode failed: {p.stderr[-350:]} {q.stderr[-350:]}')
                        with wave.open(str(pinned),'rb') as f:
                            frames=f.getnframes()
                            expected(f.getframerate()==hz and f.getnchannels()==2,
                                'pinned versioned output header mismatch')
                        expected(frames>0,'versioned conversion emitted no PCM frames')
                        expected(sha(pinned)==sha(human),
                            'versioned and human CLI aliases produced different PCM bytes')
                        return dict(rate_hz=hz,frames_per_channel=frames,
                                    pcm_sha256=sha(pinned),decode_profile=ident)
                    case(f'versioned_decode_audio_{rate//44100}_{profile}_{hz}',decode_wav)
                def equivalent(rate=rate,source=source,profile=profile,ident=ident):
                    q=plan('--dsd-decode',profile,source,'-r',88200,t/'plan.wav')
                    r=plan('--dsd-decode',ident,source,'-r',88200,t/'plan.wav')
                    expected(q['decoder']==r['decoder'],'versioned ID differs from human alias')
                    return dict(id=ident)
                case(f'human_versioned_parity_{rate//44100}_{profile}',equivalent)
                def wrong_clock(rate=rate,source=source,profile=profile):
                    other=next(x for x in RATES if x!=rate)
                    ident=f'decode.{profile}.v1.dsd{other//44100}'
                    cp=run('--dsd-plan','--dsd-decode',ident,source,t/'bad.wav')
                    expected(cp.returncode!=0,'wrong native clock accepted')
                    expected('different native DSD clock' in cp.stderr,cp.stderr[:350])
                    expected(not (t/'bad.wav').exists(),'rejected request created output')
                    return dict(requested=ident,exit=cp.returncode)
                case(f'versioned_decode_wrong_clock_{rate//44100}_{profile}',wrong_clock)

        for rate in RATES:
            ident=f'encode.mastering.v1.dsd{rate//44100}'
            def encode_plan(rate=rate,ident=ident):
                p=plan('--dsd-encode',ident,wav,'-r',rate,t/'planned.dsf')
                expected(p['encoder']['id']==ident,'wrong versioned encoder identity')
                expected(p['encoder']['modulator_input_scale']==.5,'PCM reference scale mutated')
                # The 2026-10-20 operator release activated qualified P10
                # mastering modulation in the production command. Plans must
                # report this accurately while remaining side-effect-free.
                expected(p['executable'] is True,'released encoder is unavailable')
                expected(not p['needs_unimplemented_dsp'],'release still marked unimplemented')
                expected(not (t/'planned.dsf').exists(),'preflight wrote output')
                return dict(id=ident,activated=True)
            case(f'versioned_encode_plan_{rate//44100}',encode_plan)
            def encode_audio(rate=rate,ident=ident):
                out=t/f'{ident}.dsf'
                cp=run('--dsd-mode','auto','--dsd-encode',ident,wav,'-r',rate,out)
                expected(cp.returncode==0 and out.is_file(),
                         f'released versioned encoder failed: {cp.stderr[-400:]}')
                from reference import verify
                dsd=verify.decode_dsf(out.read_bytes())
                expected(dsd['rate']==rate and dsd['channels']==1,
                         'released encoder output header mismatch')
                expected(dsd['frames']>0,'released encoder emitted empty audio')
                return dict(id=ident,native_frames=dsd['frames'],
                            bitstream_sha256=dsd['chronological_bits_sha256'])
            case(f'versioned_encode_audio_{rate//44100}',encode_audio)
            def wrong_encode(rate=rate):
                other=next(x for x in RATES if x!=rate)
                ident=f'encode.mastering.v1.dsd{other//44100}'
                cp=run('--dsd-plan','--dsd-encode',ident,wav,'-r',rate,t/'bad.dsf')
                expected(cp.returncode!=0,'wrong encoder rate accepted')
                expected('different native DSD clock' in cp.stderr,cp.stderr[:400])
                expected(not (t/'bad.dsf').exists(),'rejected request wrote audio')
                return dict(requested=ident,exit=cp.returncode)
            case(f'versioned_encode_wrong_clock_{rate//44100}',wrong_encode)

        for decode_id in ('decode.mastering.v0.dsd64','decode.mastering.v1.dsd512','decode.wideband.v1.dsd999'):
            def bad_id(decode_id=decode_id):
                cp=run('--dsd-plan','--dsd-decode',decode_id,dsd[RATES[0]],t/'bad.wav')
                expected(cp.returncode!=0,'unknown decoder version accepted')
                expected('--dsd-decode requires' in cp.stderr,'unknown decoder diagnostic')
                return dict(id=decode_id,exit=cp.returncode)
            case('unknown_decode_'+decode_id,bad_id)
        def conflict():
            cp=run('--dsd-plan','--dsd-decode','decode.mastering.v1.dsd64',dsd[RATES[0]],t/'bad.wav',
                   'dsdpcm','-p','decode.wideband.v1.dsd64')
            expected(cp.returncode!=0,'opposed explicit profiles accepted')
            expected('conflicting' in cp.stderr,cp.stderr[:350])
            return dict(exit=cp.returncode)
        case('conflicting_versioned_decoder_options',conflict)
        def different_pins():
            cp=run('--dsd-plan','--dsd-decode','decode.mastering.v1.dsd64',dsd[RATES[0]],t/'bad.wav',
                   'dsdpcm','-p','decode.mastering.v1.dsd128')
            expected(cp.returncode!=0,'conflicting clock pins accepted')
            expected('conflicting versioned' in cp.stderr,cp.stderr[:350])
            return dict(exit=cp.returncode)
        case('conflicting_versioned_decoder_clocks',different_pins)

        def legacy_repack():
            src=dsd[RATES[0]];out=t/'default.dsf';explicit=t/'legacy.dsf'
            a=run('-D',src,out);b=run('--dsd-mode','legacy','-D',src,explicit)
            expected(a.returncode==0 and b.returncode==0,
                     f'default/legacy native failure: {a.stderr[:200]} {b.stderr[:200]}')
            expected(sha(out)==sha(explicit),'unrequested native default differs from legacy')
            return dict(dsf_sha256=sha(out),both_modes='same native bits')
        case('default_native_repack_equals_explicit_legacy',legacy_repack)

        def default_legacy_pcm():
            source=dsd[RATES[0]];dest=t/'default.wav';old=t/'legacy.wav'
            a=run('-D',source,'-r',88200,'-e','signed-integer','-b',32,dest,'rate','-v')
            b=run('--dsd-mode','legacy','-D',source,'-r',88200,'-e','signed-integer','-b',32,old,'rate','-v')
            expected(a.returncode==0 and b.returncode==0,
                f'explicit legacy decode failed: {a.stderr[-200:]} {b.stderr[-200:]}')
            expected(sha(dest)==sha(old),'default legacy PCM changed')
            return dict(wav_sha256=sha(dest))
        case('default_pcm_matches_explicit_legacy',default_legacy_pcm)

        def level_measure():
            source=dsd[RATES[0]]
            files={}
            for name in ('preserve','sacd'):
                target=t/(name+'.wav')
                cp=run('--dsd-mode','auto','--dsd-level',name,'-D',source,
                       '-r',88200,'-e','signed-integer','-b',32,target)
                expected(cp.returncode==0,cp.stderr[-400:])
                with wave.open(str(target),'rb') as f:
                    files[name]=np.frombuffer(f.readframes(f.getnframes()),dtype='<i4').astype(np.int64)
            a,b=files['preserve'],files['sacd']
            expected(a.size>0 and np.max(np.abs(a))>512,'insufficient reference signal')
            err=int(np.max(np.abs(b-2*a)))
            expected(err<=2,f'SACD must be a 2x explicit gain, max LSB delta {err}')
            return dict(preserve_peak=int(np.max(np.abs(a))),sacd_peak=int(np.max(np.abs(b))),max_2x_lsb_error=err)
        case('explicit_sacd_gain_is_2x_default_preserve',level_measure)

    save()
    obj=json.loads(outfile.read_text())
    print('P15 CLI qualification',obj['status'],obj['summary'],outfile)
    return 0 if obj['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
