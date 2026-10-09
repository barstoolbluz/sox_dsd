#!/usr/bin/env python3
"""P08 executable domain-boundary tests against explicit P07 decoding.

Fixture bit chronology is generated independently.  All PCM comparisons use
byte-identical signed 32-bit graph samples, not a lossy WAV codec.  Inherited
P05 planner tests cover requested vs resolved domains and modulation policy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import wave
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from reference import fixtures, verify

DSD=fixtures.DSD64


def raw_samples(path: Path) -> tuple[int, ...]:
    b=path.read_bytes()
    assert len(b)%4==0
    return struct.unpack('<%di'%(len(b)//4),b)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    exe=str(a.sox.resolve())
    a.results.mkdir(parents=True,exist_ok=True)
    cases=[]
    plan_results=a.results.parent/'plan-p08'
    plan_results.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dsd-p08-') as d:
        tmp=Path(d)
        bits_a=fixtures.bits(32801,1,'69')
        bits_b=fixtures.bits(16507,1,'distinct')
        bits_2=fixtures.bits(65545,2,'distinct')
        files={}
        for name,bits in [('a',bits_a),('b',bits_b),('stereo',bits_2),
                          ('one',fixtures.bits(65537,1,'ones')),
                          ('empty',fixtures.bits(0,1,'69'))]:
            files[name]=tmp/(name+'.dsf')
            files[name].write_bytes(fixtures.make_dsf(bits))
        files['d128']=tmp/'higher_rate.dsf'
        files['d128'].write_bytes(fixtures.make_dsf(
            fixtures.bits(65545,1,'distinct'),rate=2*DSD))
        files['concat']=tmp/'concat.dsf'
        files['concat'].write_bytes(fixtures.make_dsf((bits_a[0]+bits_b[0],)))
        files['dff6']=tmp/'six.dff'
        files['dff6'].write_bytes(fixtures.make_dff(fixtures.bits(32768,6,'distinct')))

        def execute(tag, args, *, ok=True, out_type='raw', extra=(), out_rate=None):
            out=tmp/(tag+('.raw' if out_type=='raw' else '.'+out_type))
            argv=[exe,'--dsd-mode','auto','--dsd-layout-loss','warn','-D',*args]
            if out_rate is not None:
                argv+=['-r',str(out_rate)]
            if out_type=='raw':
                argv+=['-t','raw','-e','signed-integer','-b','32',str(out)]
            else:argv+=[str(out)]
            argv.extend(extra)
            p=subprocess.run(argv,capture_output=True,text=True,timeout=100)
            assert (p.returncode==0)==ok,(tag,p.returncode,p.stderr[-1200:])
            if ok:assert out.is_file(),tag
            else:assert not out.exists(),('unexpected partial file',tag)
            return out,p

        def plan(name, args):
            p=subprocess.run([exe,'--dsd-plan','--dsd-mode','auto',
                '--dsd-layout-loss','warn',*args],capture_output=True,text=True,timeout=20)
            assert p.returncode==0,(name,p.stderr)
            resolved=json.loads(p.stdout)
            (plan_results/(name+'.json')).write_text(json.dumps(
                resolved,sort_keys=True,indent=2)+'\n')
            return resolved

        def run(name,fn):
            row={'name':name,'status':'pass'}
            try:
                info=fn() or {}
                row.update(info)
            except Exception as e:
                row.update(status='fail',reason=str(e))
                print('FAIL',name,str(e),flush=True)
            cases.append(row)
            return row

        # A decoder after the input combiner is identical to P07's explicit
        # mono-per-flow graph effect with an identical finite-file policy.
        direct={}
        for name in ('a','b','stereo','one','empty','dff6'):
            src=files[name]
            def case(name=name,src=src):
                explicit,_=execute(name+'_explicit',[str(src)],extra=('dsdpcm',))
                automatic,p=execute(name+'_auto',[str(src)])
                ex=raw_samples(explicit);au=raw_samples(automatic)
                assert ex==au,('automatic vs explicit decoder mismatch',name)
                channels=6 if name=='dff6' else 2 if name=='stereo' else 1
                native=(32768 if name=='dff6' else 65545 if name=='stereo'
                        else 65537 if name=='one' else 32801 if name=='a'
                        else 16507 if name=='b' else 0)
                n=(native*88200+DSD//2)//DSD
                assert len(au)==n*channels,(name,len(au),n,channels)
                direct[name]=ex
                return dict(frames=n,channels=channels,
                            pcm_sha256=hashlib.sha256(automatic.read_bytes()).hexdigest())
            run('decode_'+name,case)

        def multichannel_adapter():
            # A single-input merge deliberately selects a private input
            # decoder instead of the ordinary graph decoder.  Its observable
            # PCM must remain identical, including the six independent finite
            # filter histories and the exact final sample count.
            merged,_=execute('six_adapter_merge',
                ['--combine=merge',str(files['dff6'])])
            assert raw_samples(merged)==direct['dff6']
            snapshot=plan('six_channel_adapter_vs_graph',
                ['--combine=merge',str(files['dff6']),'-t','raw',
                 '-e','signed-integer','-b','32',str(tmp/'six-plan.raw')])
            assert snapshot['input_decoder_count']==1
            assert snapshot['graph_decoder_count']==0
            return dict(frames=32768*88200//DSD,channels=6,
                        sha256=hashlib.sha256(merged.read_bytes()).hexdigest())
        run('six_channel_private_adapter_matches_graph_decoder',multichannel_adapter)

        def nonlinear():
            for effect in [('gain','-3'),('overdrive','30'),('rate','48000'),
                           ('trim','.001','.005')]:
                tag=effect[0]
                auto,_=execute('auto_'+tag,[str(files['a'])],extra=effect)
                ref,_=execute('ref_'+tag,[str(files['a'])],extra=('dsdpcm',*effect))
                assert auto.read_bytes()==ref.read_bytes(),('nonlinear mismatch',tag)
            return {'effects':['gain','overdrive','rate','trim']}
        run('implicit_before_pcm_effects',nonlinear)

        def input_gain():
            # Input gain cannot be applied to the 1-bit graph samples.
            # No integer roundoff is introduced until *after* the double gain.
            gain,_=execute('adapter_gain',['-v','0.5',str(files['a'])])
            samples=raw_samples(gain)
            assert len(samples)==len(direct['a'])
            assert max(abs(v-round(w*.5)) for v,w in zip(samples,direct['a']))<=1
            leading,_=execute('adapter_leading',['-v','0.5',str(files['a'])],extra=('dsdpcm',))
            assert leading.read_bytes()==gain.read_bytes(), 'duplicate reconstruction or gain'
            plan_response=subprocess.run([exe,'--dsd-plan','--dsd-layout-loss','warn','-v','0.5',str(files['a']),
                '-t','raw','-e','signed-integer','-b','32',str(tmp/'not_created.raw'),'dsdpcm'],
                capture_output=True,text=True,timeout=20)
            assert plan_response.returncode==0,plan_response.stderr
            obj=json.loads(plan_response.stdout)
            assert obj['input_decoder_count']==1 and obj['graph_decoder_count']==0
            assert obj['inputs'][0]['volume_consumed_by_decoder']
            assert not (tmp/'not_created.raw').exists()
            snapshot=plan('input_volume_before_combiner',['-v','0.5',str(files['a']),
                '-t','raw','-e','signed-integer','-b','32',str(tmp/'not_created.raw'),'dsdpcm'])
            assert snapshot==obj
            return dict(samples=len(samples),max_int32_difference=1)
        run('file_gain_before_graph_quantization',input_gain)

        def clipping():
            # Maximal density can overshoot at a filter boundary; file gain
            # suppresses clipping before quantization, not afterward.
            gain,_=execute('ones_attenuated',[
                '--dsd-clip','error','-v','0.25',str(files['one'])])
            assert len(raw_samples(gain))==(65537*88200+DSD//2)//DSD
            return dict(samples=len(raw_samples(gain)))
        run('overrange_protected_by_file_gain',clipping)

        def parallel():
            for opt,name in [('-m','mix'),('-M','merge'),('--combine=multiply','multiply'),
                             ('--combine=mix-power','mix_power')]:
                # Both arms follow identical SoX combiner arithmetic;
                # only the boundary before it differs.
                first,_=execute('pcm_'+name+'_a',[str(files['a'])],extra=('dsdpcm',))
                second,_=execute('pcm_'+name+'_b',[str(files['b'])],extra=('dsdpcm',))
                # The auto arm's input adapters must equal a PCM-only
                # combiner of already-decoded inputs byte-for-byte.
                auto,_=execute('auto_'+name,[opt,str(files['a']),str(files['b'])])
                out=tmp/('explicit_'+name+'.raw')
                cmd=[exe,'-D',opt,'-r','88200','-e','signed-integer','-b','32',
                     '-c','1','-t','raw',str(first),'-r','88200',
                     '-e','signed-integer','-b','32','-c','1','-t','raw',str(second),
                     '-t','raw','-e','signed-integer','-b','32',str(out)]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
                assert p.returncode==0,(name,p.stderr[-700:])
                xa,xb=raw_samples(auto),raw_samples(out)
                assert len(xa)==len(xb),(name,len(xa),len(xb))
                gap=max((abs(x-y) for x,y in zip(xa,xb)),default=0)
                assert gap<=2,(name,'PCM combiner difference',gap,[(x,y) for x,y in zip(xa,xb) if x!=y][:8])
            return {'combiners':['mix','merge','multiply','mix-power']}
        run('parallel_combiner_pcm_equivalence_and_tails',parallel)

        def mixed_domains():
            pcm,_=execute('stereo_pcm',[str(files['stereo'])],extra=('dsdpcm',))
            auto,_=execute('mixed_domains_auto',['-m',str(files['stereo']),
                '-r','88200','-e','signed-integer','-b','32','-c','2','-t','raw',str(pcm)])
            ref=tmp/'mixed_pcm_ref.raw'
            p=subprocess.run([exe,'-D','-m','-r','88200','-e','signed-integer',
                '-b','32','-c','2','-t','raw',str(pcm),'-r','88200',
                '-e','signed-integer','-b','32','-c','2','-t','raw',str(pcm),
                '-t','raw','-e','signed-integer','-b','32',str(ref)],
                capture_output=True,text=True,timeout=100)
            assert p.returncode==0,p.stderr[-700:]
            xa,xb=raw_samples(auto),raw_samples(ref)
            assert len(xa)==len(xb)
            gap=max((abs(x-y) for x,y in zip(xa,xb)),default=0)
            assert gap<=2, ('DSD+PCM combiner difference',gap,[(x,y) for x,y in zip(xa,xb) if x!=y][:8])
        run('mixed_dsd_pcm_input_rate_and_gain',mixed_domains)

        def common_native_profile_rate():
            # Different DSD clocks with the same number of output PCM channels
            # select the largest participating decoder working rate.  A
            # one-input graph decoder cannot run after combining raw pulses.
            auto,_=execute('merged_mixed_dsd_clocks',
                ['-M',str(files['a']),str(files['d128'])])
            one,_=execute('explicit_lower_dsd_clock',[str(files['a'])],
                out_rate=176400,extra=('dsdpcm','176400'))
            two,_=execute('explicit_higher_dsd_clock',[str(files['d128'])],
                out_rate=176400,extra=('dsdpcm','176400'))
            expected=tmp/'mixed_clocks_reference.raw'
            cmd=[exe,'-D','-M']
            for f in (one,two):
                cmd.extend(['-r','176400','-e','signed-integer','-b','32',
                            '-c','1','-t','raw',str(f)])
            cmd+=['-t','raw','-e','signed-integer','-b','32',str(expected)]
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
            assert proc.returncode==0,proc.stderr[-600:]
            assert auto.read_bytes()==expected.read_bytes(),                 'mixed-clock native pulses were combined before reconstruction'
            snap=plan('mixed_dsd_clocks_common_pcm_rate',
                ['-M',str(files['a']),str(files['d128']),'-t','raw',
                 '-e','signed-integer','-b','32',str(tmp/'mixed-plan.raw')])
            assert snap['combiner']['rate_hz']==176400
            assert snap['input_decoder_count']==2
            return dict(working_rate_hz=176400,samples=len(raw_samples(auto)))
        run('different_native_dsd_clocks_merge_at_common_pcm_rate',common_native_profile_rate)

        def native_concat():
            auto,_=execute('native_concat',[str(files['a']),str(files['b'])])
            single,_=execute('merged_bits',[str(files['concat'])])
            assert auto.read_bytes()==single.read_bytes(), 'continuous native concat reset'
            assert len(raw_samples(auto))==((32801+16507)*88200+DSD//2)//DSD
        run('native_concatenation_one_continuous_filter',native_concat)

        def perfile_concat():
            auto,_=execute('perfile_concat',['-v','0.5',str(files['a']),
                '-v','0.25',str(files['b'])])
            one,_=execute('perfile_one',['-v','0.5',str(files['a'])])
            two,_=execute('perfile_two',['-v','0.25',str(files['b'])])
            assert auto.read_bytes()==one.read_bytes()+two.read_bytes(), \
                'separate finite-file adapter lifetimes not preserved'
            assert len(raw_samples(auto))==len(raw_samples(one))+len(raw_samples(two))
        run('per_input_finite_file_concatenation',perfile_concat)

        def sequence_restart():
            # Sequence mode creates a new effects chain at each input boundary,
            # unlike native concat, which has one continuous decoder lifetime.
            seq,_=execute('sequence_decoded',['--combine=sequence',
                str(files['a']),str(files['b'])])
            assert raw_samples(seq)==direct['a']+direct['b'], \
                'sequence reused preceding input decoder history'
            snapshot=plan('sequence_independent_finite_decoders',['--combine=sequence',
                str(files['a']),str(files['b']),'-t','raw','-e','signed-integer',
                '-b','32',str(tmp/'plan-sequence.raw')])
            assert len(snapshot['segments'])==2
            assert all(s['graph_decoder_count']==1 for s in snapshot['segments'])
            return {'frames':len(raw_samples(seq))}
        run('sequence_restarts_reconstruction_at_equal_native_rates',sequence_restart)

        def dither_boundary():
            # dither is the first user effect and is processed in the second
            # effects loop after SoX's automatic effects.
            auto,_=execute('auto_dither',[str(files['a'])],extra=('dither',))
            ref,_=execute('ref_dither',[str(files['a'])],extra=('dsdpcm','dither'))
            assert auto.read_bytes()==ref.read_bytes(), \
                'dither ran on native pulses or inserted decoder twice'
        run('implicit_decoder_before_first_dither',dither_boundary)

        def chosen_pcm_rate():
            auto,_=execute('auto_48000',[str(files['a'])],out_rate=48000)
            ref,_=execute('ref_48000',[str(files['a'])],out_rate=48000,extra=('dsdpcm','48000'))
            assert auto.read_bytes()==ref.read_bytes(), 'decoder ignored requested PCM rate'
            assert len(raw_samples(auto))==(32801*48000+DSD//2)//DSD,(len(raw_samples(auto)),(32801*48000+DSD//2)//DSD)
        run('explicit_final_pcm_rate_without_extra_src',chosen_pcm_rate)

        def native():
            src=files['dff6']
            out,p=execute('six_native',[str(src)],out_type='dff')
            assert 'dsdpcm' not in p.stderr
            assert out.is_file()
            # Same algorithm on the original P07 graph and P08 graph.
            snap=plan('native_repack',[str(src),str(tmp/'plan-native.dff')])
            assert snap['input_decoder_count']==snap['graph_decoder_count']==snap['encoder_count']==0
            return {'bytes':out.stat().st_size}
        run('unprocessed_native_repack_bypasses_dsp',native)

        def effects_trace(proc):
            # -V4 reports the executable graph after all implicit insertion.
            names=re.findall(r'effects chain:\s+(\w+)\s',proc.stderr)
            assert names,(proc.returncode,proc.stderr[-600:])
            return names

        guard_bits=fixtures.bits(32768,2,'distinct')
        guard_dsf=tmp/'guard-stereo.dsf'
        guard_dff=tmp/'guard-stereo.dff'
        guard_dsf.write_bytes(fixtures.make_dsf(guard_bits))
        guard_dff.write_bytes(fixtures.make_dff(guard_bits))

        def guard_native_repack():
            count=0
            for source in (guard_dsf,guard_dff):
                for kind in ('dsf','dff'):
                    tag=f'guard_{source.suffix[1:]}_to_{kind}'
                    guarded,proc=execute(tag,['-G','-V4',str(source)],out_type=kind)
                    ordinary,_=execute(tag+'_plain',[str(source)],out_type=kind)
                    assert guarded.read_bytes()==ordinary.read_bytes(),tag
                    reader=verify.decode_dsf if kind=='dsf' else verify.decode_dff
                    assert reader(guarded.read_bytes())['timeline']==list(guard_bits),tag
                    assert effects_trace(proc)==['input','output'],(tag,effects_trace(proc))
                    count+=1
                snap=plan(f'guard_native_{source.suffix[1:]}',
                    ['-G',str(source),str(tmp/('plan-native'+source.suffix))])
                assert snap['policy']['guarded']
                assert snap['steps']==[]
                assert snap['graph_decoder_count']==snap['input_decoder_count']==0
            return {'repack_routes':count,'native_decoder_count':0,'gain_effects':0}
        run('guard_native_dsf_dff_no_generic_gain',guard_native_repack)

        def guard_dop_transport():
            guarded,proc=execute('guard_dop',['-G','-V4',str(guard_dsf)],
                                 out_type='wav',extra=('dop',))
            ordinary,_=execute('dop_plain',[str(guard_dsf)],
                               out_type='wav',extra=('dop',))
            assert guarded.read_bytes()==ordinary.read_bytes()
            assert effects_trace(proc)==['input','dop','output']
            with wave.open(str(guarded),'rb') as wav:
                assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(2,3,176400)
                transport=wav.readframes(wav.getnframes())
            expected=bytes(x for row in fixtures.dop_words(guard_bits)
                           for word in row for x in (word&255,word>>8&255,word>>16&255))
            assert transport==expected,'DoP payload/markers differ from bit oracle'
            assert verify.decode_dop(transport,2,32768)['timeline']==list(guard_bits)
            snap=plan('guard_native_dop',['-G',str(guard_dsf),
                 str(tmp/'guard-dop-plan.wav'),'dop'])
            assert snap['graph_decoder_count']==snap['input_decoder_count']==0
            assert [step['name'] for step in snap['steps']]==['dop']
            return {'transport_frames':len(transport)//6,'markers':'05/fa','gain_effects':0}
        run('guard_native_dop_keeps_payload_and_markers',guard_dop_transport)

        def guard_pcm_effect():
            automatic,proc=execute('guard_pcm_auto',['-G','-V4',str(files['a'])],
                                   extra=('gain','-3'))
            explicit,explicit_proc=execute('guard_pcm_explicit',
                                          ['-G','-V4',str(files['a'])],
                                          extra=('dsdpcm','gain','-3'))
            assert automatic.read_bytes()==explicit.read_bytes(), \
                'guarded implicit decoder differs from reconstruct-first graph'
            for execution in (proc,explicit_proc):
                names=effects_trace(execution)
                assert names[0:2]==['input','dsdpcm'],names
                assert names.count('gain')==2,names
                assert names[-1]=='output',names
            snap=plan('guard_reconstruct_pcm',['-G',str(files['a']),'-t','raw',
                '-e','signed-integer','-b','32',str(tmp/'guard-plan.raw'),'gain','-3'])
            names=[step['name'] for step in snap['steps']]
            assert snap['graph_decoder_count']==1 and names.index('implicit_dsdpcm')<names.index('gain')
            return {'pcm_frames':len(raw_samples(automatic)),'executed_gain_count':2}
        run('guard_after_decoder_for_pcm_effect',guard_pcm_effect)

        def guard_normalization():
            normalized,proc=execute('guard_normalized',['--norm','-V4',str(files['a'])])
            explicit,_=execute('guard_normalized_reference',[str(files['a'])],
                               extra=('dsdpcm','gain','-nh'))
            assert normalized.read_bytes()==explicit.read_bytes(), \
                'actual normalization was dropped or ran on native pulses'
            samples=raw_samples(normalized)
            assert samples!=direct['a'] and max(map(abs,samples))>max(map(abs,direct['a'])), \
                'normalization did not apply its requested nonidentity gain'
            assert effects_trace(proc)==['input','dsdpcm','gain','output']
            snap=plan('guard_normalization',['--norm',str(files['a']),'-t','raw',
                '-e','signed-integer','-b','32',str(tmp/'norm-plan.raw')])
            assert snap['policy']['normalizing']
            assert [step['name'] for step in snap['steps']]==['implicit_dsdpcm','auto_normalize']
            return {'pcm_frames':len(raw_samples(normalized)),'normalization_applied':True}
        run('actual_normalization_preserved_after_decoder',guard_normalization)

        def guard_plan_execution_correspondence():
            # Native trim remains a native operation: no planned decoder or
            # guard gain may appear in the executed graph, even with -G.
            result,proc=execute('guard_native_trim',['-G','-V4',str(guard_dsf)],
                                out_type='dsf',extra=('trim','0'))
            assert verify.decode_dsf(result.read_bytes())['timeline']==list(guard_bits)
            names=effects_trace(proc)
            assert 'gain' not in names and 'dsdpcm' not in names,names
            snap=plan('guard_native_trim',['-G',str(guard_dsf),
                str(tmp/'guard-trim-plan.dsf'),'trim','0'])
            assert snap['graph_decoder_count']==snap['input_decoder_count']==0
            assert all(s['name'] not in ('gain','implicit_dsdpcm') for s in snap['steps'])
            return {'planned_decoder_count':0,'executed_gain_count':0}
        run('guard_native_plan_matches_executed_effects',guard_plan_execution_correspondence)

        def unavailable_encoder():
            target=tmp/'unavailable.dsf'
            args=[str(files['a']),str(target),'gain','-3']
            snapshot=plan('processed_dsd_unavailable_until_p10',args)
            assert not snapshot['executable']
            assert snapshot['encoder_count']==1 and snapshot['graph_decoder_count']==1
            p=subprocess.run([exe,'--dsd-mode','auto',*args],
                capture_output=True,text=True,timeout=20)
            assert p.returncode!=0 and not target.exists(),(p.returncode,p.stderr)
            return {'reported_encoder':snapshot['encoder']['id']}
        run('processed_dsd_requires_unavailable_pcmdsd',unavailable_encoder)

        def null_output():
            # The null sink has no precision; its placeholder 1-bit signal
            # must never cause SoX to instantiate an automatic SDM/dither.
            p=subprocess.run([exe,'--dsd-mode','auto','--dsd-layout-loss','warn',
                str(files['a']),'-t','null','-'],capture_output=True,text=True,timeout=30)
            assert p.returncode==0,p.stderr[-600:]
            assert 'sdm:' not in p.stderr
            snap=plan('auto_null_sink',[str(files['a']),'-t','null','-'])
            assert snap['encoder_count']==0 and snap['graph_decoder_count']==1
        run('null_sink_does_not_trigger_native_modulation',null_output)

        def premature_eof():
            # Pipes have no size preflight; a DSF header can announce more
            # native frames than arrive.  The private decoder must not
            # finalize a clean, shorter PCM file on physical EOF.
            source=fixtures.make_dsf(fixtures.bits(65536,1,'distinct'))
            args=[exe,'--dsd-mode','auto','--dsd-layout-loss','warn',
                  '--combine=merge','-t','dsf','-','-t','null','-']
            for size in (92,92+4096,92+4096+100):
                p=subprocess.run(args,input=source[:size],
                    capture_output=True,timeout=40)
                assert p.returncode!=0,(size,p.stderr.decode(errors='replace')[-500:])
                assert b'premature native EOF' in p.stderr, (size,p.stderr[-500:])
            p=subprocess.run(args,input=source,capture_output=True,timeout=40)
            assert p.returncode==0,p.stderr[-500:]
            return dict(declared_native_frames=65536,
                        physically_delivered_native_frames=[0,32768,32768,65536])
        run('adapter_known_length_premature_eof_fails_closed',premature_eof)

        def dop_rejection():
            out,p=execute('dop_after_pcm',['--dsd-layout-loss','warn',
                str(files['a'])],out_type='wav',extra=('gain','-3','dop'),ok=False)
            assert 'dop' in p.stderr.lower()
            return {'diagnostic':'dop requires native'}
        run('dop_after_pcm_effect_rejected_before_header',dop_rejection)

    passed=sum(r['status']=='pass' for r in cases)
    summary={'schema':'sox.dsd.P08.integration.v1','passed':passed,
             'failed':len(cases)-passed,'cases':cases}
    (a.results/'integration.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(f'P08 integration: {passed} passed, {len(cases)-passed} failed')
    return int(passed!=len(cases))

if __name__=='__main__':sys.exit(main())
