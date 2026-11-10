#!/usr/bin/env python3
"""Independent file-level CLI acceptance for the SoX DSD usability interface.

Fixtures are authored from known bit chronology, not by invoking the encoder.
Audio comparisons are byte/bit comparisons; no subjective quality claim.
Run from any directory with --sox <built binary>.
"""
from __future__ import annotations

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from reference import fixtures

RATES = (64, 128, 256, 512, 1024)


def check(c, why):
    if not c:
        raise AssertionError(why)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(exe, *args, ok=True, timeout=90):
    proc = subprocess.run([str(exe), *map(str, args)], capture_output=True,
                          text=True, timeout=timeout,
                          env={**os.environ, 'OMP_NUM_THREADS':'1'})
    check((proc.returncode == 0) == ok,
          f'{args}: unexpected exit {proc.returncode}: {proc.stderr[-1200:]}')
    return proc


def plan(exe, *args):
    return json.loads(run(exe, '--plan', *args).stdout)


def info(path):
    with wave.open(str(path), 'rb') as f:
        return f.getparams(), f.readframes(f.getnframes())


def payload_dsf(path, nch, frames):
    b = path.read_bytes()
    check(b[:4] == b'DSD ' and b[80:84] == b'data', 'invalid DSF container')
    blocks = (frames + 32767) // 32768
    buf = b[92:]
    check(len(buf) >= 4096 * nch * blocks, 'truncated DSF payload')
    per = (frames + 7) // 8
    return tuple(b''.join(buf[(i*nch+ch)*4096:(i*nch+ch)*4096+4096]
                          for i in range(blocks))[:per] for ch in range(nch))


def oracle_dsf(timeline):
    return tuple(bytes(fixtures.pack_byte(ch, i, oldest_msb=False)
                       for i in range(0, len(ch), 8)) for ch in timeline)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--results', type=Path)
    a = ap.parse_args()
    exe = a.sox.resolve()
    check(exe.exists(), f'missing executable: {exe}')
    records = []
    with tempfile.TemporaryDirectory(prefix='sox-dsd-cli-') as td:
        d = Path(td)
        source = fixtures.bits(16384, 2, 'distinct')
        for mult in RATES:
            (d / f'dsd{mult}.dsf').write_bytes(
                fixtures.make_dsf(source, rate=44100*mult))
        (d / 'input.dff').write_bytes(fixtures.make_dff(source))
        with wave.open(str(d/'input.wav'), 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b''.join(struct.pack('<hh',
                round(4000*math.sin(i*2*math.pi*997/44100)),
                round(3000*math.sin(i*2*math.pi*1531/44100))) for i in range(512)))

        def case(name, fn):
            row={'name':name, 'status':'PASS'}
            try:
                detail = fn()
                if detail is not None:
                    row['detail'] = detail
            except Exception as e:
                row['status'] = 'FAIL'
                row['error'] = f'{type(e).__name__}: {e}'
            records.append(row)
            print(row['status'], name, row.get('error',''), flush=True)

        def help_checks():
            for opt, required in (('--help', 'GLOBAL OPTIONS'),
                                  ('--help-dsd', 'input.dsf'),
                                  ('--help-effect', 'dsdpcm')):
                args = (opt,'dsdpcm') if opt=='--help-effect' else (opt,)
                check(required in run(exe,*args).stdout, f'{opt} content')
        case('help, DSD help, effect help', help_checks)

        def pcm_legacy():
            normal=d/'pcm-default.wav'; altered=d/'pcm-altered.wav'
            run(exe,d/'input.wav',normal)
            run(exe,d/'input.wav',altered,'gain','-6')
            before, data=info(d/'input.wav')
            same, copied=info(normal)
            check(before[:4] == same[:4] and copied == data, 'PCM copy changed')
            check(info(altered)[1]!=data, 'legacy gain did not act')
            resampled=d/'pcm-48.wav'
            run(exe,d/'input.wav','-r','48k',resampled)
            check(info(resampled)[0].framerate==48000, '-r 48k changed meaning')
            return {'pcm_copy_sha256':sha(normal)}
        case('PCM-only SoX copy, rate, gain legacy semantics', pcm_legacy)

        def abbreviated_encoding_compatibility():
            # SoX's getopt accepts long-option prefixes. Adding --encode must
            # not steal the historically unambiguous --encoding spellings.
            baseline = d / 'input.wav'
            for spelling in ('--enc', '--enco', '--encod', '--encoding', '-e'):
                out = d / ('pcm-' + spelling.lstrip('-') + '.wav')
                run(exe, baseline, spelling, 'signed-integer', out)
                check(info(out)[1] == info(baseline)[1],
                      f'{spelling} no longer configures ordinary PCM encoding')
                check(info(out)[0].sampwidth == 2,
                      f'{spelling} unexpectedly changed sample precision')
            out = d / 'pcm-encod-equals.wav'
            run(exe, baseline, '--encod=signed-integer', out)
            check(info(out)[1] == info(baseline)[1],
                  '--encod=NAME no longer sets SoX encoding')
        case('legacy --encoding abbreviated spellings coexist with --encode',
             abbreviated_encoding_compatibility)

        def other_legacy_abbreviations():
            # Prefixes previously unique for traditional long options.
            baseline = d / 'input.wav'
            for old, full, argument in (
                ('--rep', '--replay-gain', 'off'),
                ('--pla', '--play-rate-arg', '-a')):
                results = []
                for spelling in (old, full):
                    out = d / ('pcm-' + spelling.lstrip('-') + '.wav')
                    run(exe, spelling, argument, baseline, out)
                    results.append(sha(out))
                check(results[0] == results[1],
                      f'{old} and {full} no longer have the same effect')
            # Headless build has no default audio device: both forms must
            # fail at device selection, not at option parsing.
            old = run(exe, '--de', '--version', ok=False)
            full = run(exe, '--default-device', '--version', ok=False)
            check(old.stdout == full.stdout and old.stderr == full.stderr and
                  'no default audio device configured' in old.stderr,
                  '--de no longer selects the traditional default device')
        case('other legacy unique long-option prefixes remain valid',
             other_legacy_abbreviations)

        for mult in RATES:
            def dec(mult=mult):
                src=d/f'dsd{mult}.dsf'; out=d/f'decoded{mult}.wav'
                expected_hz=88200 if mult==64 else 176400
                doc=plan(exe, src, out)
                check(doc['output']['domain']=='PCM_AUDIO', 'decoder route')
                check(doc['output']['rate_hz']==expected_hz, 'default PCM clock')
                check(doc['decoder']['id']==f'decode.mastering.v1.dsd{mult}', 'default decoder identity')
                check(doc['output']['bits_per_sample']==24, 'default PCM precision')
                check(not out.exists(), '--plan created audio')
                run(exe,src,out)
                wav,_=info(out)
                check(wav.framerate==expected_hz and wav.sampwidth==3,
                      'decoded PCM stream is not expected 24-bit clock')
                return {'pcm_hz':wav.framerate, 'frames':wav.nframes}
            case(f'DSD{mult} automatic PCM decode and plan', dec)

        for mult in RATES:
            def enc(mult=mult):
                dest=d/f'encoded{mult}.dsf'
                doc=plan(exe,d/'input.wav','-r',f'dsd{mult}',dest)
                ident=f'encode.mastering.v1.dsd{mult}'
                check(doc['output']['domain']=='DSD_NATIVE', 'encoder route')
                check(doc['output']['rate_hz']==44100*mult, 'named native rate')
                check(doc['encoder']['id']==ident, 'qualified encoder mismatch')
                check(doc['executable'], 'qualified encoder not executable')
                run(exe,d/'input.wav','-r',f'dsd{mult}',dest)
                check(dest.stat().st_size>92, 'empty encoded DSD')
                return {'encoder_id':ident, 'bytes':dest.stat().st_size}
            case(f'PCM to DSD{mult} named rate and qualified encoder', enc)

        def direct_default():
            out=d/'default-native.dsf'
            doc=plan(exe,d/'input.wav',out)
            check(doc['output']['rate_hz']==2822400, 'PCM to DSD default is not DSD64')
            run(exe,d/'input.wav',out)
        case('PCM to DSD without explicit rate defaults to DSD64', direct_default)

        def rate_aliases():
            for label in ('DSD64','DSD128','DSD256','DSD512','DSD1024'):
                native=44100*int(label[3:])
                named=plan(exe,d/'input.wav','-r',label,d/'case-rate.dsf')
                numeric=plan(exe,d/'input.wav','-r',str(native),d/'numeric-rate.dsf')
                check(named['output']['rate_hz']==numeric['output']['rate_hz']==native,
                      f'case-insensitive named rate {label} differs from numeric rate')
        case('case-insensitive DSD clock names retain numeric rate meanings',rate_aliases)

        def default_profile():
            src=d/'dsd64.dsf'
            for name, flag in (('automatic',()), ('mastering',('--decode','mastering')),
                               ('v1',('--decode','decode.mastering.v1.dsd64'))):
                run(exe,*flag,src,d/f'{name}.wav')
            check(sha(d/'automatic.wav')==sha(d/'mastering.wav')==sha(d/'v1.wav'),
                  'automatic, mastering alias and exact v1 must match')
            check(plan(exe,'--decode','mastering',src,d/'check-v1.wav')['decoder']['id'] ==
                  'decode.mastering.v1.dsd64', 'named mastering must select v1')
            logged=d/'reported.wav'; report=d/'decoder-report.json'
            run(exe,'--report',report,'--decode','mastering',src,logged)
            check(logged.read_bytes()==(d/'mastering.wav').read_bytes(),
                  'report changed mastering decoder output')
            rows=json.loads(report.read_text())['processing']['decoder']
            check(rows and all(row['profile_id']=='decode.mastering.v1.dsd64'
                               and row['candidate_unqualified'] is False for row in rows),
                  'runtime report did not confirm standard v1 decoder')
            for removed in ('conservative','legacy','decode.mastering.v2.dsd64'):
                dest=d/f'removed-{removed}.wav'
                run(exe,'--decode',removed,src,dest,ok=False)
                check(not dest.exists(), 'removed decoder spelling produced output')
        case('mastering default, exact v1 and runtime report agree',default_profile)

        def explicit_decoder_inherits_global():
            # Global selection, effect-local -p and exact profile pins must
            # reach the same FIR; an incompatible explicit selection fails.
            for mult in (64, 128):
                src=d/f'dsd{mult}.dsf'
                opts=('-R','-D')
                global_pcm=d/f'explicit-global-wide-{mult}.wav'
                local_pcm=d/f'explicit-local-wide-{mult}.wav'
                default_pcm=d/f'explicit-default-v1-{mult}.wav'
                pinned_pcm=d/f'explicit-pinned-wide-{mult}.wav'
                logged_pcm=d/f'explicit-reported-wide-{mult}.wav'
                report=d/f'explicit-wide-{mult}.json'
                doc=plan(exe,'--decode','wideband',src,
                         d/f'explicit-plan-wide-{mult}.wav','dsdpcm')
                ident=f'decode.wideband.v1.dsd{mult}'
                check(doc['decoder']['id']==ident and
                      doc['graph_decoder_count']==1 and doc['executable'],
                      'explicit dsdpcm plan did not select wideband')
                run(exe,*opts,'--decode','wideband',src,global_pcm,'dsdpcm')
                run(exe,*opts,src,local_pcm,'dsdpcm','-p','wideband')
                run(exe,*opts,src,default_pcm,'dsdpcm')
                run(exe,*opts,'--decode',ident,src,pinned_pcm,'dsdpcm')
                check(global_pcm.read_bytes()==local_pcm.read_bytes()==
                      pinned_pcm.read_bytes(),
                      f'DSD{mult}: global wideband did not execute explicit effect')
                check(sha(global_pcm)!=sha(default_pcm),
                      f'DSD{mult}: selected wideband silently executed mastering')
                run(exe,*opts,'--decode','wideband','--report',report,
                    src,logged_pcm,'dsdpcm')
                check(logged_pcm.read_bytes()==global_pcm.read_bytes(),
                      f'DSD{mult}: report changed explicit decoder audio')
                rows=json.loads(report.read_text())['processing']['decoder']
                check(rows and all(row['profile_id']==ident for row in rows),
                      f'DSD{mult}: report did not observe executed wideband')
                conflict=d/f'explicit-conflict-profile-{mult}.wav'
                run(exe,'--decode','wideband',src,conflict,
                    'dsdpcm','-p','mastering',ok=False)
                check(not conflict.exists(), 'conflicting decoder created output')
                wrong=d/f'explicit-wrong-pin-{mult}.wav'
                other=128 if mult==64 else 64
                run(exe,'--decode',f'decode.wideband.v1.dsd{other}',
                    src,wrong,'dsdpcm',ok=False)
                check(not wrong.exists(), 'wrong pinned decoder clock created output')
        case('global wideband reaches explicit dsdpcm at DSD64/128',
             explicit_decoder_inherits_global)

        def explicit_level_inherits_global():
            for mult in (64, 128):
                src=d/f'dsd{mult}.dsf'
                opts=('-R','-D')
                global_pcm=d/f'explicit-global-sacd-{mult}.wav'
                local_pcm=d/f'explicit-local-sacd-{mult}.wav'
                default_pcm=d/f'explicit-default-preserve-{mult}.wav'
                combined_pcm=d/f'explicit-combined-sacd-{mult}.wav'
                combined_local=d/f'explicit-combined-local-{mult}.wav'
                logged_pcm=d/f'explicit-reported-sacd-{mult}.wav'
                report=d/f'explicit-sacd-{mult}.json'
                doc=plan(exe,'--dsd-level','sacd',src,
                         d/f'explicit-plan-sacd-{mult}.wav','dsdpcm')
                check(doc['decoder']['gain']==2 and
                      doc['graph_decoder_count']==1 and doc['executable'],
                      'explicit dsdpcm plan did not select SACD gain')
                run(exe,*opts,'--dsd-level','sacd',src,global_pcm,'dsdpcm')
                run(exe,*opts,src,local_pcm,'dsdpcm','-l','sacd')
                run(exe,*opts,src,default_pcm,'dsdpcm')
                check(global_pcm.read_bytes()==local_pcm.read_bytes(),
                      f'DSD{mult}: global SACD level did not reach dsdpcm')
                check(sha(global_pcm)!=sha(default_pcm),
                      f'DSD{mult}: global SACD level silently preserved gain')
                run(exe,*opts,'--dsd-level','sacd','--report',report,
                    src,logged_pcm,'dsdpcm')
                check(logged_pcm.read_bytes()==global_pcm.read_bytes(),
                      f'DSD{mult}: report changed explicit SACD reconstruction')
                rows=json.loads(report.read_text())['processing']['decoder']
                check(rows and all(row['gain_mapping']['applied_linear_gain']==2
                                   for row in rows),
                      f'DSD{mult}: report did not observe executed SACD gain')
                # A locally pinned decoder must not suppress inheritance of
                # an independently selected global level.
                run(exe,*opts,'--dsd-level','sacd',src,combined_pcm,
                    'dsdpcm','-p','mastering')
                run(exe,*opts,src,combined_local,
                    'dsdpcm','-p','mastering','-l','sacd')
                check(combined_pcm.read_bytes()==combined_local.read_bytes(),
                      f'DSD{mult}: local profile suppressed global level')
                conflict=d/f'explicit-conflict-level-{mult}.wav'
                run(exe,'--dsd-level','sacd',src,conflict,
                    'dsdpcm','-l','preserve',ok=False)
                check(not conflict.exists(), 'conflicting level created output')
        case('global SACD level reaches explicit dsdpcm at DSD64/128',
             explicit_level_inherits_global)

        def mastering_strict():
            src=d/'dsd64.dsf';dest=d/'conservative-strict.wav'
            opts=('--decode','mastering','--dsd-bandwidth','strict',
                  src,'-r','44100')
            doc=plan(exe,*opts,d/'not-created.wav')
            check(doc['executable'] and doc['decoder']['id']==
                  'decode.mastering.v1.dsd64', 'v1 strict plan mismatch')
            run(exe,*opts,dest)
            check(info(dest)[0].framerate==44100,
                  'executable v1 strict plan failed to produce PCM')
        case('v1 strict plan executes with the selected v1 filter',mastering_strict)

        def legacy_mixed_clocks():
            srcs=(d/'dsd64.dsf',d/'dsd128.dsf')
            a=d/'mixed-auto.wav';l=d/'mixed-legacy.wav';n=d/'mixed-native.wav'
            args=('-m',*srcs,'-r','176400','-b','24')
            doc=plan(exe,'--dsd-mode','legacy',*args,d/'mixed-planned.wav')
            check(doc['input_decoder_count']==2 and doc['executable'],
                  'legacy mix was not authorized for per-input reconstruction')
            run(exe,*args,a)
            run(exe,'--dsd-mode','legacy',*args,l)
            check(a.read_bytes()==l.read_bytes(),
                  'legacy mixed clocks did not use the qualified common PCM route')
            run(exe,'--dsd-mode','native',*args,n,ok=False)
            check(not n.exists(), 'native-only mode accepted incompatible clocks')
        case('legacy-mode mixed native clocks follow common PCM plan',legacy_mixed_clocks)

        def encode_override():
            automatic=d/'encauto.dsf'; named=d/'encmaster.dsf'; version=d/'encv1.dsf'
            for flags,out in (((),automatic), (('--encode','mastering'),named),
                              (('--encode','encode.mastering.v1.dsd128'),version)):
                run(exe,*flags,d/'input.wav','-r','dsd128',out)
            check(sha(automatic)==sha(named)==sha(version),
                  'explicit and unpinned qualified encoding disagree')
        case('explicit qualified encoder equals default bitstream',encode_override)

        def native_repack():
            src=d/'dsd64.dsf'; dff=d/'native-repack.dff'; rt=d/'native-roundtrip.dsf'
            doc=plan(exe,src,dff)
            check(doc['output']['domain']=='DSD_NATIVE', 'native output route')
            check(doc['graph_decoder_count']==doc['encoder_count']==0, 'native repack did DSP')
            run(exe,src,dff)
            run(exe,dff,rt)
            exp=oracle_dsf(source)
            check(payload_dsf(src,2,16384)==exp,'oracle fixture mismatch')
            check(payload_dsf(rt,2,16384)==exp,'native DSD bitstream changed')
            return {'native_dsf_payload_sha256': hashlib.sha256(b''.join(exp)).hexdigest()}
        case('DSF to DFF to DSF native pulse preservation',native_repack)

        def dop():
            src=d/'dsd64.dsf'; dest=d/'dop-auto.wav'; other=d/'dop-explicit.wav'
            doc=plan(exe,'--dop',src,dest)
            check(doc['output']['domain']=='DOP_TRANSPORT' and doc['output']['rate_hz']==176400,
                  'DoP rate or domain')
            check(doc['dop_count']==1 and not doc['encoder_count'] and not doc['graph_decoder_count'],
                  'DoP applied DSP')
            run(exe,'--dop',src,dest)
            run(exe,src,other,'dop')
            check(sha(dest)==sha(other),'--dop and terminal dop effect differ')
            wav,body=info(dest)
            check((wav.sampwidth,wav.framerate,wav.nchannels)==(3,176400,2),
                  'DoP header rate, encoding or channels')
            expected=bytes(v for frame in fixtures.dop_words(source)
                           for word in frame for v in word.to_bytes(3,'little'))
            check(body==expected,'DoP chronological bits or 05/FA markers differ')
        case('DoP correct carriers, native payload and existing effect',dop)

        for mult in (128,256,512,1024):
            def transport(mult=mult):
                src=d/f'dsd{mult}.dsf'; out=d/f'dop{mult}.wav'
                doc=plan(exe,'--dop',src,out)
                check(doc['output']['rate_hz']==(44100*mult)//16,'DoP high rate')
                run(exe,'--dop',src,out)
                check(info(out)[0].framerate==44100*mult//16, 'DoP carrier WAV')
            case(f'DSD{mult} DoP transport', transport)

        def report_invariance():
            src=d/'dsd64.dsf'; plain=d/'report-off.wav'; logged=d/'report-on.wav'; report=d/'result.json'
            run(exe,src,plain)
            run(exe,'--report',report,src,logged)
            check(plain.read_bytes()==logged.read_bytes(), 'report changed audio bytes')
            j=json.loads(report.read_text())
            check(j.get('status')=='complete','report completion status')
            check(j['processing'], 'missing processing report')
            planpath=d/'plan-report.json'; noaudio=d/'never-created.wav'
            p=run(exe,'--plan','--report',planpath,src,noaudio)
            check(p.stdout=='', 'plan unexpectedly duplicated report on stdout')
            check(not noaudio.exists(), 'plan with report converted audio')
            check(json.loads(planpath.read_text())['schema']=='sox.dsd.plan.v1', 'plan report schema')
            return {'pcm_sha256':sha(plain)}
        case('report output invariance and plan non-execution',report_invariance)

        def report_all_routes():
            # Reports are observers, never additional DSP stages.
            checks=(
                ('encode', (d/'input.wav','-r','dsd64'),'.dsf'),
                ('native', (d/'dsd64.dsf',),'.dff'),
                ('dop', ('--dop',d/'dsd64.dsf'),'.wav'),
            )
            records={}
            for name,prefix,extension in checks:
                plain=d/f'plain-{name}{extension}'
                reported=d/f'reported-{name}{extension}'
                report=d/f'report-{name}.json'
                run(exe,*prefix,plain)
                run(exe,'--report',report,*prefix,reported)
                check(plain.read_bytes()==reported.read_bytes(),
                      f'{name}: report modified output bytes')
                data=json.loads(report.read_text())
                check(data.get('status')=='complete',f'{name}: report not completed')
                records[name]=sha(reported)
            return {'sha256':records}
        case('report cannot change encode, native repack, or DoP payloads',report_all_routes)

        def mixed_dsd_pcm_effects():
            src=d/'dsd64.dsf'; out=d/'effects-output.wav'
            doc=plan(exe,src,out,'gain','-6')
            check(doc['graph_decoder_count']==1, 'effects path must reconstruct DSD')
            run(exe,src,out,'gain','-6')
            check(out.stat().st_size>44, 'effects path failed to output audio')
            # Post-DSP conversion to native DSD must not pass native pulses
            # through the ordinary PCM effects graph as pseudo-audio.
            native=d/'effects-native.dsf'
            run(exe,src,native,'gain','-6')
            check(native.stat().st_size>92,'re-encoding after gain failed')
        case('DSD reconstruction, PCM effect, and re-encoding pipeline',mixed_dsd_pcm_effects)

        def rate_errors():
            for flags in ((d/'input.wav','-r','dsd128',d/'invalid.wav'),
                          ('-r','dsd128',d/'input.wav',d/'invalid2.dsf')):
                run(exe,*flags,ok=False)
            run(exe,'--decode','decode.mastering.v1.dsd128',d/'dsd64.dsf',d/'wrong-dec.wav',ok=False)
            run(exe,'--encode','encode.mastering.v1.dsd64',d/'input.wav','-r','dsd128',d/'wrong-enc.dsf',ok=False)
            run(exe,'--decode','nonexistent',d/'dsd64.dsf',d/'bad-dec.wav',ok=False)
            for f in ('invalid.wav','invalid2.dsf','wrong-dec.wav','wrong-enc.dsf','bad-dec.wav'):
                check(not (d/f).exists(), f'failed preflight created {f}')
        case('misplaced or incompatible rate and profile options fail',rate_errors)

        def unconsumed_profile_errors():
            # A requested qualified profile is not a no-op setting: every
            # valid request must result in a matching processing stage.
            bad=(
                ('--decode','mastering',d/'input.wav',d/'unused-dec-pcm.wav'),
                ('--encode','mastering',d/'input.wav',d/'unused-enc-pcm.wav'),
                ('--encode','mastering',d/'dsd64.dsf',d/'unused-enc-dec.wav'),
                ('--decode','mastering',d/'input.wav',d/'unused-dec-enc.dsf'),
                ('--decode','mastering',d/'dsd64.dsf',d/'unused-dec-native.dff'),
                ('--encode','mastering',d/'dsd64.dsf',d/'unused-enc-native.dff'),
                ('--decode','mastering','--dop',d/'dsd64.dsf',d/'unused-dec-dop.wav'),
            )
            for args in bad:
                run(exe,*args,ok=False)
                check(not Path(args[-1]).exists(),
                      f'unused profile created output {args[-1]}')
        case('unused explicit profiles fail rather than silently disappearing',unconsumed_profile_errors)

        def report_alias_errors():
            src=d/'dsd64.dsf'; before=sha(src)
            run(exe,'--report',src,src,d/'bad-report-input.wav',ok=False)
            check(sha(src)==before,'report path corrupted audio input')
            output=d/'same-report-output.wav'
            run(exe,'--report',output,src,output,ok=False)
            check(not output.exists(),'report path alias created audio output')
        case('report destination cannot overwrite its input or audio output',report_alias_errors)

        def dop_errors():
            src=d/'dsd64.dsf'
            for args in (('--dop',src,'-b','16',d/'bad-dop-16.wav'),
                         ('--dop',src,'-r','96k',d/'bad-dop-rate.wav'),
                         ('--dop',src,d/'bad-dop.dsf'),
                         ('--dop',d/'input.wav',d/'bad-dop-pcm.wav'),
                         ('--dop',src,d/'bad-dop-twice.wav','dop')):
                run(exe,*args,ok=False)
            for name in ('bad-dop-16.wav','bad-dop-rate.wav','bad-dop.dsf',
                         'bad-dop-pcm.wav','bad-dop-twice.wav'):
                check(not (d/name).exists(),f'failed DoP command created {name}')
        case('DoP rejects 16-bit, wrong carrier, native target, PCM and duplicate',dop_errors)

        def safety():
            # Legacy DSD endpoints now take the qualified graph; those
            # positive route checks are above. PCM-only report stays invalid.
            run(exe,'--report',d/'pcm-report.json',d/'input.wav',d/'pcm-report.wav',ok=False)
            check(not (d/'pcm-report.wav').exists(),'report changed PCM-only route')
            run(exe,'--plan',d/'dsd64.dsf',d/'never.wav')
            check(not (d/'never.wav').exists(),'plan created output')
        case('PCM-only report rejected and plan does not create audio',safety)

        def legacy_clock_routing():
            # The old bypass resampled DSD64 pulse values as if they were
            # PCM when the destination requested a different DSD clock.
            src=d/'dsd64.dsf'
            hashes={}
            for label in ('dsd128','5644800'):
                root='legacy-clock-'+label
                plain=d/(root+'-auto.dsf')
                legacy=d/(root+'-legacy.dsf')
                reported=d/(root+'-reported.dsf')
                report=d/(root+'.json')
                doc=plan(exe,'--dsd-mode','legacy',src,'-r',label,
                         d/(root+'-planned.dsf'))
                check(doc['mode']=='legacy' and doc['graph_decoder_count']==1 and
                      doc['encoder_count']==1 and
                      doc['decoder']['id']=='decode.mastering.v1.dsd64',
                      'legacy clock plan omitted qualified reconstruction/modulation')
                check(not (d/(root+'-planned.dsf')).exists(),
                      'planning created native DSD audio')
                run(exe,src,'-r',label,plain)
                run(exe,'--dsd-mode','legacy',src,'-r',label,legacy)
                run(exe,'--dsd-mode','legacy','--report',report,src,
                    '-r',label,reported)
                check(plain.read_bytes()==legacy.read_bytes()==reported.read_bytes(),
                      'legacy DSD clock change or reporting changed qualified audio')
                j=json.loads(report.read_text())
                check(j['status']=='complete' and j['processing']['decoder'] and
                      j['processing']['encoder'],
                      'legacy clock report lacks executed decoder or encoder')
                hashes[label]=sha(plain)
            check(hashes['dsd128']==hashes['5644800'],
                  'named and numeric DSD128 clocks do not agree')
            return {'sha256':hashes}
        case('legacy DSD clock changes use planned reconstruction and encoding',
             legacy_clock_routing)

        def legacy_pcm_report_invariance():
            src=d/'dsd64.dsf'
            for label,effects in (('plain',()),('gain',('gain','-6'))):
                root='legacy-pcm-'+label
                default=d/(root+'-auto.wav')
                old=d/(root+'-legacy.wav')
                logged=d/(root+'-reported.wav')
                report=d/(root+'.json')
                doc=plan(exe,'--dsd-mode','legacy',src,
                         d/(root+'-planned.wav'),*effects)
                check(doc['graph_decoder_count']==1 and
                      doc['encoder_count']==0 and
                      doc['output']['domain']=='PCM_AUDIO',
                      'legacy reconstruction plan inconsistent with target')
                run(exe,src,default,*effects)
                run(exe,'--dsd-mode','legacy',src,old,*effects)
                run(exe,'--dsd-mode','legacy','--report',report,
                    src,logged,*effects)
                check(default.read_bytes()==old.read_bytes()==logged.read_bytes(),
                      f'{label}: --report or legacy changed reconstructed PCM')
                j=json.loads(report.read_text())
                check(j['status']=='complete' and j['processing']['decoder'],
                      'legacy PCM report did not observe the active decoder')
        case('legacy reconstruction, PCM effects, and reports use the same graph',
             legacy_pcm_report_invariance)

        def legacy_encoder_profiles():
            src=d/'input.wav'
            baseline=d/'legacy-encode-auto.dsf'
            unpinned=d/'legacy-encode-selected.dsf'
            explicit=d/'legacy-encode-pinned.dsf'
            logged=d/'legacy-encode-report.dsf'
            report=d/'legacy-encode.json'
            doc=plan(exe,'--dsd-mode','legacy','--encode','mastering',src,
                     d/'legacy-encode-planned.dsf')
            check(doc['encoder_count']==1 and
                  doc['encoder']['id']=='encode.mastering.v1.dsd64',
                  'legacy encoder plan did not honor explicit qualified profile')
            run(exe,src,baseline)
            run(exe,'--dsd-mode','legacy','--encode','mastering',src,unpinned)
            run(exe,'--dsd-mode','legacy','--encode',
                'encode.mastering.v1.dsd64',src,explicit)
            run(exe,'--dsd-mode','legacy','--report',report,src,logged)
            check(baseline.read_bytes()==unpinned.read_bytes()==
                  explicit.read_bytes()==logged.read_bytes(),
                  'legacy mode emitted unqualified PCM-to-DSD samples')
            j=json.loads(report.read_text())
            check(j['status']=='complete' and j['processing']['encoder'] and
                  j['processing']['encoder'][0]['profile_id']==
                    'encode.mastering.v1.dsd64',
                  'legacy report did not observe mastering encoder')
        case('legacy PCM to DSD selects qualified profile and stable reporting',
             legacy_encoder_profiles)

        def legacy_unused_selectors():
            src=d/'dsd64.dsf'; pcm=d/'input.wav'
            attempts=(
                ('--decode','mastering',src,d/'legacy-unused-dec.dff'),
                ('--encode','mastering',src,d/'legacy-unused-enc.dff'),
                ('--decode','mastering',pcm,d/'legacy-unused-dec-encode.dsf'),
                ('--encode','mastering',src,d/'legacy-unused-enc-decode.wav'),
                ('--encode','mastering',pcm,d/'legacy-unused-lowlevel.dsf',
                 'rate','-v','sdm'),
            )
            for i,args in enumerate(attempts):
                for reporting in (False, True):
                    report=d/f'legacy-rejected-{i}.json'
                    command=(('--report',report) if reporting else ())
                    run(exe,'--dsd-mode','legacy',*command,*args,ok=False)
                    output=next(Path(x) for x in args if str(x).endswith(
                        ('.dsf','.dff','.wav')) and str(x).startswith(str(d/'legacy-unused')))
                    check(not output.exists(),
                          f'ignored profile created {output}')
                    check(not report.exists(),
                          'rejected profile created a report before preflight')
        case('legacy profile selectors are honored or rejected before output',
             legacy_unused_selectors)

        def legacy_native_repack_report():
            src=d/'dsd64.dsf'; plain=d/'legacy-native-plain.dff'
            legacy=d/'legacy-native-old.dff'; logged=d/'legacy-native-logged.dff'
            report=d/'legacy-native.json'
            doc=plan(exe,'--dsd-mode','legacy',src,d/'legacy-native-planned.dff')
            check(doc['output']['domain']=='DSD_NATIVE' and
                  doc['graph_decoder_count']==doc['encoder_count']==0,
                  'legacy repack plan introduced unnecessary DSP')
            run(exe,src,plain)
            run(exe,'--dsd-mode','legacy',src,legacy)
            run(exe,'--dsd-mode','legacy','--report',report,src,logged)
            check(plain.read_bytes()==legacy.read_bytes()==logged.read_bytes(),
                  'legacy repack lost native payload identity')
            j=json.loads(report.read_text())
            check(j['status']=='complete' and not j['processing']['decoder'] and
                  not j['processing']['encoder'],
                  'native repack report invented a DSP stage')
        case('legacy native repacking and reporting preserve payload',
             legacy_native_repack_report)

        def advanced():
            src=d/'dsd64.dsf'
            strict=d/'strict.wav'
            # Wideband's 35.28 kHz DSD64 passband cannot fit at 44.1k;
            # the standard mastering filter (20 kHz) can.
            run(exe,'--decode','wideband','--dsd-bandwidth','strict',src,'-r','44.1k',strict,ok=False)
            run(exe,'--dsd-bandwidth','strict',src,'-r','44.1k',d/'strict-v1.wav')
            run(exe,'--dsd-bandwidth','adapt',src,'-r','44.1k',d/'adapt.wav')
            check(info(d/'adapt.wav')[0].framerate==44100,'adapt missing')
            run(exe,'--dsd-mode','native',src,d/'native.dff')
            run(exe,'--dsd-mode','native',src,d/'native-pcm.wav',ok=False)
        case('strict versus adapt bandwidth and native-only mode',advanced)

    result={'schema':'sox.dsd.cli.acceptance.v1', 'cases':records,
            'passed':sum(x['status']=='PASS' for x in records),
            'failed':sum(x['status']=='FAIL' for x in records)}
    print(json.dumps({'passed':result['passed'],'failed':result['failed']}))
    if a.results:
        a.results.mkdir(parents=True,exist_ok=True)
        (a.results/'cli-acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    return 1 if result['failed'] else 0


if __name__=='__main__':
    raise SystemExit(main())
