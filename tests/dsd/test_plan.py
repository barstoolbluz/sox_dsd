#!/usr/bin/env python3
"""Executable P05 plan contract matrix using independent DSD/PCM fixtures.

The plan-only path must never create output. Unsupported execution must reject
before output-header creation. Fixture chronology and PCM samples are generated
without involving a SoX writer. Result records contain no machine paths.
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import wave

from reference import fixtures

ROOT = pathlib.Path(__file__).resolve().parents[2]


def pcm(path: pathlib.Path, rate: int, channels: int) -> None:
    with wave.open(str(path), 'wb') as f:
        f.setparams((channels, 2, rate, 64, 'NONE', 'not compressed'))
        f.writeframes(b'\x00\x00' * 64 * channels)


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', type=pathlib.Path, default=ROOT/'src/sox_ng')
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P05/plan')
    args=ap.parse_args()
    sox=args.sox.resolve()
    args.results.mkdir(parents=True,exist_ok=True)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='sox-p05-') as d:
        tmp=pathlib.Path(d)
        sources={}
        for mul in (1,2,4):
            path=tmp/f'dsd{mul*64}.dsf'
            path.write_bytes(fixtures.make_dsf(fixtures.bits(128,2),fixtures.DSD64*mul))
            sources[f'dsd{mul*64}']=path
        source=tmp/'same.dff'
        source.write_bytes(fixtures.make_dff(fixtures.bits(128,2)))
        sources['dff']=source
        from test_layout import dff as custom_dff
        alt=tmp/'alternate_roles.dff'
        alt.write_bytes(custom_dff([b'C000',b'C001'],fixtures.bits(128,2)))
        sources['dff_alt']=alt
        for rate in (44100,88200,96000,176400):
            path=tmp/f'pcm{rate}.wav';pcm(path,rate,2)
            sources[f'pcm{rate}']=path
        # These are independent 16-bit PCM inputs *already* at a DSD clock.
        # Low-level sdm and precision-one dither must not claim to interpolate.
        for rate in (2822400,5644800,11289600):
            path=tmp/f'pcm{rate}.wav';pcm(path,rate,2)
            sources[f'pcm{rate}']=path
        mono=tmp/'mono.wav';pcm(mono,88200,1)
        sources['pcm_mono']=mono

        def normalize(text: str) -> str:
            return text.replace(str(tmp),'<temp>').replace(str(ROOT),'<tree>').replace(str(sox),'<sox>')
        def run(name: str, arguments: list[str], ok: bool=True,
                inspect=None, error: str|None=None, plan: bool=True,
                env: dict|None=None, suffix='.wav'):
            dst=tmp/(name+suffix)
            prepared=[a.replace('@OUT@',str(dst)) for a in arguments]
            cmd=[str(sox)]+(['--dsd-plan'] if plan else [])+prepared
            overrides=os.environ.copy()
            overrides.update(LC_ALL='C',SOX_OPTS='')
            if env:overrides.update(env)
            t0=time.perf_counter()
            p=subprocess.run(cmd,cwd=tmp,capture_output=True,text=True,
                             timeout=30,env=overrides)
            ms=round((time.perf_counter()-t0)*1000,3)
            item=dict(name=name,arguments=[x.replace(str(tmp),'<temp>') for x in cmd[1:]],
                      phase='plan' if plan else 'execute',returncode=p.returncode,
                      elapsed_ms=ms,stderr=normalize(p.stderr),status='pass')
            try:
                if ok and p.returncode != 0:
                    raise AssertionError(f'exit={p.returncode}: {p.stderr[:500]}')
                if not ok and p.returncode == 0:
                    raise AssertionError('invalid request succeeded')
                if error and error.lower() not in p.stderr.lower():
                    raise AssertionError(f'missing diagnostic {error!r}: {p.stderr[:500]}')
                if plan:
                    if dst.exists():
                        raise AssertionError('plan-only created an output file')
                    if ok:
                        if p.stdout.strip():
                            tree=json.loads(p.stdout)
                        elif env and env.get('REPORT_OVERRIDE'):
                            tree=json.loads(pathlib.Path(env['REPORT_OVERRIDE']).read_text())
                        else:
                            raise AssertionError('plan-only did not emit JSON')
                        if inspect:inspect(tree)
                        item['plan']=tree
                    elif p.stdout.strip():
                        raise AssertionError('invalid request emitted a success plan')
                else:
                    if ok and not dst.is_file():
                        raise AssertionError('successful execution missing output')
                    if not ok and dst.exists():
                        raise AssertionError('unsupported execution created an output')
                    if ok:item['output_bytes']=dst.stat().st_size
            except Exception as exc:
                item['status']='fail';item['assertion']=str(exc)
                print(f'FAIL {name}: {exc}',file=sys.stderr)
            rows.append(item)
        ds=str(sources['dsd64']); dd=str(sources['dff']);ds128=str(sources['dsd128']);ds256=str(sources['dsd256'])
        w88=str(sources['pcm88200']);w96=str(sources['pcm96000']);w44=str(sources['pcm44100'])
        def expect(**want):
            def check(obj):
                for field,value in want.items():
                    found=obj
                    for part in field.split('__'):
                        found=found[part] if isinstance(found,dict) else found[int(part)]
                    if isinstance(value,float):
                        assert abs(found-value)<1.e-8,(field,found,value)
                    else:assert found==value,(field,found,value)
            return check
        def sequence(obj):
            assert obj['schema']=='sox.dsd.sequence.v1'
            assert len(obj['segments'])==2
            assert all(x['input_decoder_count']==0 for x in obj['segments'])
            assert [x['inputs'][0]['native_rate_hz'] for x in obj['segments']]==[2822400,5644800]
        def rate_stages(obj):
            steps=obj['steps'];assert len(steps)>=2
            assert steps[0]['name']=='implicit_dsdpcm' and steps[0]['rate_out_hz']==88200
            assert steps[1]['name']=='rate' and steps[1]['rate_in_hz']==88200
        def processed(obj):
            assert obj['graph_decoder_count']==1 and obj['encoder_count']==1
            assert [x['name'] for x in obj['steps']]==['implicit_dsdpcm','gain','implicit_pcmdsd']
            assert obj['encoder']['modulator_input_scale']==1
        def per_input(obj):
            assert obj['combiner']['domain']=='PCM_AUDIO'
            assert obj['input_decoder_count']==2 and obj['graph_decoder_count']==0
            assert [x['input_index'] for x in obj['steps'][:2]]==[0,1]
            assert all(x['decoder_before_combiner'] and x['volume_consumed_by_decoder'] for x in obj['inputs'])
        def steps_are(*names):
            def check(obj):
                actual=[x['name'] for x in obj['steps']]
                assert actual==list(names),(actual,names)
            return check
        def check_steps(*names, **properties):
            def check(obj):
                steps_are(*names)(obj)
                expect(**properties)(obj)
            return check

        # Plain paths remain native and preserve channel/layout identity.
        for name,src in (('native_dsf',ds),('native_dff',dd),('native128',ds128),('native256',ds256)):
            run(name,[src,'@OUT@'],inspect=expect(executable=True,output__domain='DSD_NATIVE',
                graph_decoder_count=0,encoder_count=0),suffix='.dsf')
        run('noop_channels',[ds,'@OUT@','channels','2'],
            inspect=expect(executable=True,layout_identity_preserved=True),suffix='.dsf')
        run('native_trim',[ds,'@OUT@','trim','0','0.00001'],
            inspect=expect(executable=True,native_trim_seek=True),suffix='.dff')
        run('native_legacy_profile',['--dsd-decode','legacy',ds,'@OUT@'],
            inspect=expect(executable=True,output__domain='DSD_NATIVE'),suffix='.dsf')
        run('native_only_mode',['--dsd-mode','native',ds,'@OUT@'],
            inspect=expect(executable=True),suffix='.dsf')
        run('native_actual_dff',['--dsd-mode','native',ds,'@OUT@'],plan=False,suffix='.dff')
        run('native_actual_dsf',['--dsd-mode','native',dd,'@OUT@'],plan=False,suffix='.dsf')
        run('pcm_unchanged_opt_in',['--dsd-mode','auto',w88,'@OUT@'],plan=False)
        run('pcm_only_plan',[w88,'@OUT@'],inspect=expect(
            executable=True,output__domain='PCM_AUDIO',graph_decoder_count=0))

        # P08 activates the existing binary64 decoder for planned graph boundaries.
        for name,src,expected in (('master64',ds,88200),('master128',ds128,176400),
                                  ('master256',ds256,176400)):
            run(name,[src,'@OUT@'],inspect=expect(executable=True,needs_unimplemented_dsp=False,
                decoder__intermediate_hz=expected,output__bits_per_sample=24,
                graph_decoder_count=1))
        run('wideband256',['--dsd-decode','wideband',ds256,'@OUT@'],
            inspect=expect(decoder__id='decode.wideband.v1.dsd256',decoder__pass_hz=141120,
                decoder__stop_hz=176400,decoder__intermediate_hz=352800,output__rate_hz=352800))
        run('legacy_decoder',['--dsd-decode','legacy',ds,'@OUT@'],
            inspect=expect(decoder__id='decode.legacy.generic',decoder__pass_hz=0,
                policy__decode='legacy',decoder__intermediate_hz=88200))
        run('legacy_strict',['--dsd-decode','legacy','--dsd-bandwidth','strict',
            ds,'@OUT@'],ok=False,error='cannot certify')
        run('float_fallback',['--dsd-layout-loss','warn',ds,'@OUT@'],
            inspect=expect(output__bits_per_sample=32,output__encoding=3),suffix='.f32')
        run('sacd_gain',['--dsd-level','sacd',ds,'@OUT@'],
            inspect=expect(decoder__gain=2.,level_reference=.5))
        run('clip_error_policy',['--dsd-clip','error',ds,'@OUT@'],
            inspect=expect(policy__clip='error'))
        run('wideband_downsample',['--dsd-decode','wideband',ds,'-r','44100','@OUT@'],
            inspect=expect(decoder__effective_bandwidth_hz=20947.5,output__rate_hz=44100))
        run('strict_bandwidth',['--dsd-decode','wideband','--dsd-bandwidth','strict',ds,
            '-r','44100','@OUT@'],ok=False,error='strict bandwidth')
        run('explicit_dsdpcm',[ds,'@OUT@','dsdpcm','-p','wideband','176400'],
            inspect=expect(graph_decoder_count=1,decoder__id='decode.wideband.v1.dsd64',
                           decoder__effective_bandwidth_hz=35280))
        run('explicit_versioned',[ds,'@OUT@','dsdpcm','-p','decode.mastering.v1.dsd64'],
            inspect=expect(decoder__id='decode.mastering.v1.dsd64'))
        run('mismatched_profile',[ds,'@OUT@','dsdpcm','-p','decode.mastering.v1.dsd128'],
            ok=False,error='different native DSD clock')
        run('profile_precedence',['--dsd-decode','wideband',ds,'@OUT@','dsdpcm','-p','mastering'],
            ok=False,error='conflicting')
        run('profile_inherit',['--dsd-decode','wideband',ds,'@OUT@','dsdpcm'],
            inspect=expect(decoder__id='decode.wideband.v1.dsd64'))
        run('sacd_precedence',['--dsd-level','sacd',ds,'@OUT@','dsdpcm','-l','preserve'],
            ok=False,error='conflicting')
        run('bad_fraction_pcm',[ds,'@OUT@','dsdpcm','88200.5'],ok=False,error='invalid dsdpcm')
        run('bad_pcm_rate',[ds,'@OUT@','dsdpcm','88201'],ok=False,error='supported integer')
        run('duplicate_decode',[ds,'@OUT@','dsdpcm','dsdpcm'],ok=False,error='duplicates')
        run('decode_after_pcm',[ds,'@OUT@','gain','-3','dsdpcm'],ok=False,error='duplicates')
        run('leading_rate',[ds,'@OUT@','rate','-v','176400'],inspect=rate_stages)
        run('preflight_execute_decode',['--dsd-mode','auto',ds,'@OUT@'],plan=False)
        run('overdrive',[ds,'@OUT@','overdrive'],inspect=expect(graph_decoder_count=1))
        run('native_mode_reject',['--dsd-mode','native',ds,'@OUT@','gain','-3'],
            ok=False,error='native mode')
        run('gain_and_reencode',[ds,'@OUT@','gain','-3'],inspect=processed,suffix='.dsf')
        run('native_rate_change',[ds,'-r','5644800','@OUT@'],
            inspect=expect(output__rate_hz=5644800,graph_decoder_count=1,encoder_count=1),suffix='.dsf')
        run('no_header_on_gain',['--dsd-mode','auto',ds,'@OUT@','gain','-3'],plan=False,ok=False,
            error='P05 preflight',suffix='.dsf')
        run('channels_mix',[ds,'@OUT@','channels','1'],
            inspect=expect(graph_decoder_count=1,encoder_count=1),suffix='.dsf')
        run('native_layout_unknown',['--dsd-layout','L,R,Q',ds,'@OUT@'],ok=False,
            error='dsd-layout',suffix='.dsf')

        # Gain and mixing occur BEFORE add_effects; every DSD source has its own decoder.
        run('input_half',['-v','0.5',ds,'@OUT@'],
            inspect=expect(inputs__0__volume=.5,input_decoder_count=1,
                           inputs__0__volume_consumed_by_decoder=True))
        run('input_half_native',['--dsd-mode','native','-v','0.5',ds,'@OUT@'],
            ok=False,error='native mode',suffix='.dsf')
        for c in ('mix','mix-power','merge','multiply'):
            run('combine_'+c,['--combine',c,ds,ds,'@OUT@'],inspect=per_input)
        run('mixed_dsd_clocks',['--combine','mix',ds,ds128,'@OUT@'],
            inspect=expect(input_decoder_count=2,combiner__rate_hz=176400,
                inputs__0__decoder_id='decode.mastering.v1.dsd64',
                inputs__1__decoder_id='decode.mastering.v1.dsd128'))
        run('mixed_dsd_clocks_native_ambiguous',['--combine','mix',ds,ds128,'@OUT@'],
            ok=False,error='explicit native output rate',suffix='.dsf')
        run('mixed_dsd_clocks_native_pinned',['--combine','mix',ds,ds128,
            '-r','5644800','@OUT@'],
            inspect=expect(input_decoder_count=2,encoder_count=1,output__rate_hz=5644800),
            suffix='.dsf')
        run('mix_dsd_pcm',['--combine','mix',ds,w88,'@OUT@'],
            inspect=expect(input_decoder_count=1,combiner__rate_hz=88200,level_reference=.5))
        run('mix_dsd_pcm_96',['--combine','mix',ds,w96,'@OUT@'],
            inspect=expect(input_decoder_count=1,combiner__rate_hz=96000))
        run('mix_pcm_rates',['--combine','mix',w88,w96,'@OUT@'],
            ok=False,error='input files must have the same sample-rate')
        run('native_concat',['--combine','concatenate',ds,ds,'@OUT@'],
            inspect=expect(combiner__domain='DSD_NATIVE',input_decoder_count=0),suffix='.dff')
        run('concat_matching_dff',['--combine','concatenate',dd,dd,'@OUT@'],
            inspect=expect(executable=True,input_decoder_count=0),suffix='.dff')
        run('concat_identity_conflict',['--combine','concatenate',dd,
            str(sources['dff_alt']),'@OUT@'],ok=False,
            error='identical ordered channel identities',suffix='.dff')
        run('different_native_concat',['--combine','concatenate',ds,ds128,'@OUT@'],
            ok=False,error='same sample-rate',suffix='.dsf')
        run('sequence_same',['--combine','sequence',ds,ds,'-r','88200','@OUT@'],
            inspect=lambda x: (x['schema']=='sox.dsd.sequence.v1') or (_ for _ in ()).throw(AssertionError(x)))
        run('sequence_rates',['--combine','sequence',ds,ds128,'-r','88200','@OUT@'],inspect=sequence)
        run('sequence_incompatible',['--combine','sequence',ds,ds128,'@OUT@'],
            ok=False,error='single output header')
        run('sequence_failure_early',['--dsd-mode','auto','--combine','sequence',w88,ds,'@OUT@'],
            ok=False,error='segment',plan=False)

        # DoP is transport, not PCM audio; terminal ordering and rate are strict.
        run('dop_terminal',[ds,'@OUT@','dop'],inspect=expect(output__domain='DOP_TRANSPORT',
            output__rate_hz=176400,output__bits_per_sample=24,dop_count=1))
        run('dop_explicit',['-r','176400','-b','24',ds,'@OUT@','dop'],
            inspect=expect(executable=True,dop_count=1))
        run('dop_wrong_rate',[ds,'-r','88200','@OUT@','dop'],ok=False,error='DoP output rate')
        run('dop_wrong_bits',[ds,'-b','16','@OUT@','dop'],ok=False,error='precision conflicts')
        run('dop_mid_chain',[ds,'@OUT@','dop','gain','-3'],ok=False,error='terminal')
        run('dop_repeated',[ds,'@OUT@','dop','dop'],ok=False,error='exactly once')
        run('dop_native_destination',[ds,'@OUT@','dop'],ok=False,error='24-bit PCM-capable',suffix='.dsf')
        run('dop_repack_actual',['--dsd-mode','native','-r','176400','-b','24',ds,'@OUT@','dop'],
            plan=False)
        run('native_to_dop_zero_cost',['--dsd-mode','native',ds,'@OUT@','dop'],
            inspect=expect(executable=True,input_decoder_count=0,graph_decoder_count=0))

        # Explicit modulation and header conflicts are planning failures.
        run('pcm_to_dsd',[w88,'@OUT@'],
            inspect=expect(output__rate_hz=2822400,encoder_count=1),suffix='.dsf')
        run('pcm_explicit_mod',[w88,'-r','5644800','@OUT@','pcmdsd','-p','mastering','5644800'],
            inspect=expect(encoder_count=1,output__rate_hz=5644800),suffix='.dsf')
        run('pcm_mod_conflict',[w88,'@OUT@','pcmdsd','5644800'],
            ok=False,error='conflicts',suffix='.dsf')
        run('pcm_double_mod',[w88,'-r','5644800','@OUT@','pcmdsd','5644800','pcmdsd','5644800'],
            ok=False,error='duplicates',suffix='.dsf')
        run('mod_then_pcm',[w88,'@OUT@','pcmdsd','2822400'],
            ok=False,error='explicit dsdpcm boundary')
        run('explicit_references',[w88,'-r','5644800','@OUT@','pcmdsd','--reference','dsd','5644800'],
            inspect=expect(encoder__modulator_input_scale=1),suffix='.dsf')
        run('pcm_ref_default',[w88,'-r','5644800','@OUT@','pcmdsd','5644800'],
            inspect=expect(encoder__modulator_input_scale=.5),suffix='.dsf')
        run('explicit_bad_kernel',['--dsd-mode','native',ds,'@OUT@'],
            ok=False,error='kernel tier',env={'SOX_DSD_KERNEL_FIR':'avx512'},suffix='.dsf')

        # Independent corrective regressions: explicit decoder selection before
        # input scaling / balance_input, never an after-combiner second decode.
        run('leading_preinput_gain',['-v','0.5',ds,'@OUT@','dsdpcm','96000'],
            inspect=check_steps('input_dsdpcm',input_decoder_count=1,
                graph_decoder_count=0,combiner__rate_hz=96000,
                inputs__0__volume=.5,inputs__0__volume_consumed_by_decoder=True))
        run('leading_preinput_profile',['-v','0.5',ds,'@OUT@','dsdpcm','-p','wideband','-l','sacd','96000'],
            inspect=expect(input_decoder_count=1,graph_decoder_count=0,
                inputs__0__decoder_id='decode.wideband.v1.dsd64',inputs__0__decoder_gain=2.,
                inputs__0__effective_rate_hz=96000))
        run('leading_preinput_pinned',['-v','0.5',ds,'@OUT@','dsdpcm',
            '-p','decode.mastering.v1.dsd64'],
            inspect=expect(input_decoder_count=1,graph_decoder_count=0,
                inputs__0__decoder_id='decode.mastering.v1.dsd64'))
        run('leading_preinput_bad_pin',['-v','0.5',ds,'@OUT@','dsdpcm',
            '-p','decode.mastering.v1.dsd128'],ok=False,error='different native DSD clock')
        run('leading_preinput_conflict',['--dsd-decode','mastering','-v','0.5',
            ds,'@OUT@','dsdpcm','-p','wideband'],ok=False,error='conflicting')
        run('leading_mix_native',['--combine','mix',ds,ds,'@OUT@','dsdpcm','96000'],
            inspect=check_steps('input_dsdpcm','input_dsdpcm',input_decoder_count=2,
                graph_decoder_count=0,combiner__rate_hz=96000))
        run('leading_merge_native',['--combine','merge',ds,ds128,'@OUT@','dsdpcm','352800'],
            inspect=expect(input_decoder_count=2,combiner__rate_hz=352800,
                graph_decoder_count=0))
        run('leading_mix_native_default_wide',['--combine','mix',ds,ds256,'@OUT@',
            'dsdpcm','-p','wideband'],
            inspect=expect(input_decoder_count=2,combiner__rate_hz=352800))
        run('leading_mix_bad_pin',['--combine','mix',ds,ds128,'@OUT@',
            'dsdpcm','-p','decode.mastering.v1.dsd64'],ok=False,
            error='different native DSD clock')
        run('leading_mix_pcm',['--combine','mix',ds,w96,'@OUT@','dsdpcm','96000'],
            inspect=expect(input_decoder_count=1,graph_decoder_count=0,
                combiner__rate_hz=96000,level_reference=.5))
        run('leading_mix_pcm_inherit',['--combine','mix',ds,w88,'@OUT@','dsdpcm'],
            inspect=expect(input_decoder_count=1,combiner__rate_hz=88200))
        run('leading_mix_pcm_conflict',['--combine','mix',ds,w88,'@OUT@','dsdpcm','96000'],
            ok=False,error='mixed PCM input clock')

        # Terminal modulation changes the native clock. A subsequent decoder
        # is legal only when explicitly named and must use that *stage* clock.
        run('mod_gain_rejected',[w88,'-r','2822400','@OUT@',
            'pcmdsd','2822400','gain','-3'],ok=False,error='explicit dsdpcm boundary',suffix='.dsf')
        run('mod_decode_gain',[w88,'@OUT@','pcmdsd','2822400',
            'dsdpcm','88200','gain','-3'],
            inspect=check_steps('pcmdsd','dsdpcm','gain',encoder_count=1,
                graph_decoder_count=1,decoder__id='decode.mastering.v1.dsd64'))
        run('mod_decode_wrong_pin',[w88,'@OUT@','pcmdsd','2822400',
            'dsdpcm','-p','decode.mastering.v1.dsd128'],ok=False,
            error='different native DSD clock')
        run('mod_to_128_decode',[w88,'@OUT@','pcmdsd','5644800','dsdpcm','176400'],
            inspect=expect(encoder_count=1,graph_decoder_count=1,
                decoder__id='decode.mastering.v1.dsd128',decoder__intermediate_hz=176400))
        run('mod64_decode_mod128_decode',[ds,'@OUT@','dsdpcm','88200',
            'pcmdsd','5644800','dsdpcm','176400'],
            inspect=expect(encoder_count=1,graph_decoder_count=2,
                decoder__id='decode.mastering.v1.dsd128'))
        run('mod64_decode_mod128_pin',[ds,'@OUT@','dsdpcm','88200',
            'pcmdsd','5644800','dsdpcm','-p','decode.mastering.v1.dsd128'],
            inspect=expect(decoder__id='decode.mastering.v1.dsd128'))
        run('mod_mod_rejected',[w88,'-r','2822400','@OUT@',
            'pcmdsd','2822400','pcmdsd','2822400'],ok=False,error='duplicates',suffix='.dsf')
        run('mod_native_noop',[w88,'-r','2822400','@OUT@','pcmdsd','2822400',
            'channels','2'],inspect=expect(encoder_count=1,graph_decoder_count=0),suffix='.dsf')

        # DoP reads the immediately preceding native stage, including DSD128
        # and DSD256 produced by an explicit composite modulator.
        for rate in (2822400,5644800,11289600):
            for requested in (False,True):
                transport=rate//16
                run(f'dop_mod_{rate}_{"explicit" if requested else "implicit"}',
                    [w88]+(['-r',str(transport)] if requested else [])+
                    ['@OUT@','pcmdsd',str(rate),'dop'],
                    inspect=expect(encoder_count=1,dop_count=1,
                        output__domain='DOP_TRANSPORT',output__rate_hz=transport,
                        output__bits_per_sample=24))
            run(f'dop_mod_bad_rate_{rate}',
                [w88,'-r','176400' if rate!=2822400 else '352800',
                 '@OUT@','pcmdsd',str(rate),'dop'],
                ok=False,error='DoP output rate')
        run('dop_mod_bad_bits',[w88,'-b','16','@OUT@','pcmdsd','5644800','dop'],
            ok=False,error='precision conflicts')
        run('dop_native_128',[ds128,'@OUT@','dop'],
            inspect=expect(output__rate_hz=352800,dop_count=1))

        # Endpoint conversion invalidates native trim/seek eligibility, even
        # without any other user-specified PCM effect.
        run('trim_native_stays_native',[ds,'@OUT@','trim','0','0.00001'],
            inspect=check_steps('trim',native_trim_seek=True),suffix='.dsf')
        run('trim_to_pcm_timebase',[ds,'@OUT@','trim','0','0.00001'],
            inspect=check_steps('implicit_dsdpcm','trim',native_trim_seek=False,
                steps__1__rate_in_hz=88200))
        run('trim_to_pcm_gain',[ds,'@OUT@','trim','0','0.00001','gain','-3'],
            inspect=check_steps('implicit_dsdpcm','trim','gain',native_trim_seek=False))
        run('trim_explicit_pcm',[ds,'@OUT@','dsdpcm','96000','trim','0','0.00001'],
            inspect=check_steps('dsdpcm','trim',steps__1__rate_in_hz=96000))
        run('trim_native_rate_change',[ds,'-r','5644800','@OUT@','trim','0','0.00001'],
            inspect=check_steps('implicit_dsdpcm','trim','implicit_pcmdsd',
                native_trim_seek=False),suffix='.dsf')

        # Auto channels is PCM processing, before native modulation; P04 owns
        # resulting named-role negotiation and may require layout-loss policy.
        run('implicit_mono_to_stereo',[str(sources['pcm_mono']),'-c','2','@OUT@'],
            inspect=check_steps('implicit_pcm_channels','implicit_pcmdsd',
                output__channels=2,encoder_count=1),suffix='.dsf')
        run('implicit_stereo_to_mono',['--dsd-layout-loss','warn',ds,
            '-c','1','@OUT@'],
            inspect=check_steps('implicit_dsdpcm','implicit_pcm_channels','implicit_pcmdsd',
                output__channels=1,graph_decoder_count=1,encoder_count=1,
                layout_identity_preserved=False),suffix='.dsf')
        run('implicit_native_mode_reject',['--dsd-mode','native',ds,
            '-c','1','@OUT@'],ok=False,error='native mode',suffix='.dsf')
        run('implicit_channel_noop',[ds,'-c','2','@OUT@'],
            inspect=expect(executable=True,graph_decoder_count=0,encoder_count=0),suffix='.dsf')
        run('implicit_channel_explicit_roles',['--dsd-layout','FL,FR',
            str(sources['pcm_mono']),'-c','2','@OUT@'],
            inspect=expect(output__channels=2,encoder_count=1),suffix='.dsf')
        run('implicit_channel_bad_roles',['--dsd-layout','L,R,Q',
            str(sources['pcm_mono']),'-c','2','@OUT@'],
            ok=False,error='dsd-layout',suffix='.dsf')

        # Existing low-level effects produce bits at their incoming rate. Do
        # not invent interpolation or a qualified composite mastering profile.
        raw64=str(sources['pcm2822400'])
        run('ordinary_dither',[w88,'@OUT@','dither','-p','16'],
            inspect=expect(encoder_count=0,output__domain='PCM_AUDIO'))
        run('precision_one_valid',[raw64,'-r','2822400','@OUT@','dither','-p','1'],
            inspect=expect(encoder_count=1,encoder__id='encode.legacy.dither-p1',
                encoder__modulator_input_scale=1,graph_decoder_count=0),suffix='.dsf')
        run('precision_one_actual',['--dsd-mode','auto',raw64,'-r','2822400',
            '@OUT@','dither','-p','1'],plan=False,suffix='.dsf')
        run('precision_one_rate_mismatch',[w88,'-r','2822400','@OUT@',
            'dither','-p','1'],ok=False,error='rate-preserving',suffix='.dsf')
        run('precision_one_duplicate',[raw64,'-r','2822400','@OUT@',
            'dither','-p','1','pcmdsd','2822400'],ok=False,error='duplicates',suffix='.dsf')
        run('sdm_valid',[raw64,'-r','2822400','@OUT@','sdm','-f','sdm-5'],
            inspect=expect(encoder_count=1,encoder__id='encode.legacy.sdm',
                encoder__lowlevel_filter='sdm-5'),suffix='.dsf')
        run('sdm_actual',['--dsd-mode','auto',raw64,'-r','2822400','@OUT@',
            'sdm','-f','sdm-5'],plan=False,suffix='.dsf')
        run('sdm_default',[raw64,'-r','2822400','@OUT@','sdm'],
            inspect=expect(encoder_count=1,encoder__id='encode.legacy.sdm'),suffix='.dsf')
        run('sdm_rate_mismatch',[w88,'-r','2822400','@OUT@','sdm','-f','sdm-5'],
            ok=False,error='rate-preserving',suffix='.dsf')
        run('sdm_bad_filter',[raw64,'-r','2822400','@OUT@','sdm','-f','not-a-filter'],
            ok=False,error='filter is not available',suffix='.dsf')
        run('sdm_duplicate',[raw64,'-r','2822400','@OUT@',
            'sdm','-f','sdm-5','sdm','-f','sdm-5'],ok=False,error='duplicates',suffix='.dsf')

        # Automatic --norm is an actual PCM node.  -G alone represents a
        # conditional guard, not a mandatory reconstructed processing chain.
        run('norm_dsd_pcm',['--norm',ds,'@OUT@'],
            inspect=check_steps('implicit_dsdpcm','auto_normalize',
                policy__normalizing=True,graph_decoder_count=1))
        run('norm_dsd_native',['--norm',ds,'@OUT@'],
            inspect=check_steps('implicit_dsdpcm','auto_normalize','implicit_pcmdsd',
                encoder_count=1,graph_decoder_count=1),suffix='.dsf')
        run('guard_dsd_native',['-G',ds,'@OUT@'],
            inspect=check_steps(policy__guarded=True,policy__normalizing=False,
                executable=True),suffix='.dsf')
        run('norm_gain_dsd',['--norm',ds,'@OUT@','gain','-3'],
            inspect=check_steps('implicit_dsdpcm','gain','auto_normalize',
                steps__2__implicit=True))
        run('norm_pcm',['--norm',w88,'@OUT@'],
            inspect=check_steps('auto_normalize',policy__normalizing=True,
                graph_decoder_count=0,encoder_count=0))
        run('norm_pcm_actual',['--dsd-mode','auto','--norm',w88,'@OUT@'],plan=False)
        # SoX's add_effects() inserts automatic gain before explicit dither,
        # but after low-level sdm.  P05 must retain the correct PCM-first plan
        # while blocking execution of that mismatched effects chain *before*
        # creating an audio output, with and without automatic dither.
        raw64=str(sources['pcm2822400'])
        sdm_norm_reason='automatic normalization before low-level sdm is not supported by the current effects pipeline'
        for name,flags in (('norm_sdm',[]),('norm_no_dither_sdm',['-D'])):
            cmd=['--dsd-mode','auto','--norm']+flags+[raw64,'-r','2822400',
                '@OUT@','sdm','-f','sdm-5']
            run(name+'_plan',cmd,
                inspect=check_steps('auto_normalize','sdm',executable=False,
                    needs_unimplemented_dsp=False,unavailable_reason=sdm_norm_reason,
                    encoder_count=1,encoder__id='encode.legacy.sdm'),suffix='.dsf')
            run(name+'_reject',cmd,plan=False,ok=False,
                error='automatic normalization before low-level sdm',suffix='.dsf')
        # The existing modulation effects remain available when placement is
        # realizable; the new guard must not classify sdm as missing DSP.
        run('norm_dither_one_plan',['--norm',raw64,'-r','2822400',
            '@OUT@','dither','-p','1'],
            inspect=check_steps('auto_normalize','dither',executable=True,
                encoder_count=1,encoder__id='encode.legacy.dither-p1'),suffix='.dsf')
        run('norm_dither_one_actual',['--dsd-mode','auto','--norm',raw64,
            '-r','2822400','@OUT@','dither','-p','1'],plan=False,suffix='.dsf')
        run('norm_dither_before_sdm',['--norm',raw64,'-r','2822400',
            '@OUT@','dither','-p','16','sdm','-f','sdm-5'],
            inspect=check_steps('auto_normalize','dither','sdm',
                executable=True,encoder_count=1),suffix='.dsf')
        run('norm_dither_before_sdm_actual',['--dsd-mode','auto','--norm',raw64,
            '-r','2822400','@OUT@','dither','-p','16','sdm','-f','sdm-5'],
            plan=False,suffix='.dsf')
        run('norm_dsd_rate',['--norm',ds,'-r','96000','@OUT@'],
            inspect=check_steps('implicit_dsdpcm','auto_normalize',
                output__rate_hz=96000,steps__0__rate_out_hz=96000))
        run('norm_native_no_header',['--dsd-mode','auto','--norm',ds,'@OUT@'],
            plan=False,ok=False,error='P05 preflight',suffix='.dsf')
        run('norm_dop_native',['--norm',ds,'@OUT@','dop'],
            inspect=check_steps('implicit_dsdpcm','auto_normalize','implicit_pcmdsd','dop',
                encoder_count=1,graph_decoder_count=1,
                output__domain='DOP_TRANSPORT',output__rate_hz=176400))
        run('norm_dop_mod',['--norm',w88,'@OUT@','pcmdsd','5644800','dop'],
            inspect=check_steps('auto_normalize','pcmdsd','dop',
                encoder_count=1,output__rate_hz=352800))
        run('norm_before_mod_native_identity',['--norm',w88,'-r','2822400',
            '@OUT@','pcmdsd','2822400','channels','2'],
            inspect=check_steps('auto_normalize','pcmdsd','channels',
                encoder_count=1,graph_decoder_count=0),suffix='.dsf')
        run('norm_after_explicit_remod_decode',['--norm',w88,'@OUT@',
            'pcmdsd','2822400','dsdpcm','88200'],
            inspect=check_steps('pcmdsd','dsdpcm','auto_normalize',
                encoder_count=1,graph_decoder_count=1))
        run('guard_native_actual',['--dsd-mode','auto','-G',ds,'@OUT@'],
            plan=False,suffix='.dff')

        # A failing report or unsupported request must not create the audio file.
        report_file=tmp/'report.json'
        run('report_native',['--dsd-mode','native','--dsd-report',str(report_file),ds,'@OUT@'],
            inspect=expect(executable=True),env={'REPORT_OVERRIDE':str(report_file)},suffix='.dsf')
        try:
            assert report_file.is_file() and json.loads(report_file.read_text())['executable']
        except Exception as exc:
            rows.append(dict(name='report_native_written',status='fail',assertion=str(exc)))
        else:
            rows.append(dict(name='report_native_written',status='pass'))

    passed=sum(r['status']=='pass' for r in rows)
    failed=len(rows)-passed
    summary=dict(schema='sox.dsd.P05.plan-tests.v1',passed=passed,failed=failed,cases=rows)
    (args.results/'plan.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(f'P05 CLI plan: {passed} pass, {failed} fail, {len(rows)} total')
    return int(failed>0)


if __name__=='__main__':sys.exit(main())
