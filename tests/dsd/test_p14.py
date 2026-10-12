#!/usr/bin/env python3
"""P14 observable, versioned report/native-bit integration contract.

Sources are hand-built from chronological bits; no audio library is used to
create reference DSD. Tests never compare a codec to itself as sole oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import signal
import time

from reference import fixtures

ROOT=pathlib.Path(__file__).resolve().parents[2]
SCHEMA=ROOT/'tests/dsd/reference/p14_report_schema_v1.json'
GOLDEN=ROOT/'tests/dsd/reference/p14_report_golden.json'


def require(condition, explanation):
    if not condition:
        raise AssertionError(explanation)


def run(sox, *args, env=None, timeout=90, cwd=None):
    p=subprocess.run([str(sox),*map(str,args)],stdin=subprocess.DEVNULL,
                     capture_output=True,text=True,timeout=timeout,cwd=cwd,
                     env={**os.environ,'OMP_NUM_THREADS':'1',**(env or {})})
    return p


def oracle(timeline):
    n=len(timeline)
    windows=[sum(timeline[i:i+28]) for i in range(max(0,n-27))]
    excursions=[i for i,v in enumerate(windows) if v<4 or v>24]
    r=0;last=None;longest=0
    for x in timeline:
        r=r+1 if x==last else 1
        longest=max(longest,r);last=x
    return dict(frames=str(n),one_bits=str(sum(timeline)),zero_bits=str(n-sum(timeline)),
                complete_28_bit_windows=str(len(windows)),
                **{'28_bit_excursions':str(len(excursions)),
                   'first_excursion_start_frame':str(excursions[0]) if excursions else None,
                   'min_ones_28':min(windows) if windows else None,
                   'max_ones_28':max(windows) if windows else None,
                   'longest_identical_bit_run':str(longest)})


def valid_report(doc, status='complete'):
    import jsonschema
    jsonschema.validate(doc,json.loads(SCHEMA.read_text()))
    require(doc['status']==status,f"expected {status}, got {doc['status']}")
    require(doc['schema_version']==1,'schema version mutation')
    require(doc['build']['source_baseline']=='d940cc93','baseline not recorded')
    require(doc['build']['build_source_digest'] is None,'invented unavailable digest')
    # Counter/unknown contracts are type-checked by JSON Schema; no NaN tokens.
    return True


def ch0(i): return 1 if 12<=i<55 else int(i%5==0)
def ch1(i): return 0 if 29<=i<72 else int(i%7<3)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=pathlib.Path,required=True)
    ap.add_argument('--unit',type=pathlib.Path,required=True)
    ap.add_argument('--candidate',type=pathlib.Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--results',type=pathlib.Path,required=True)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    records=[]
    with tempfile.TemporaryDirectory(prefix='p14-report-') as td:
        d=pathlib.Path(td)
        sox=args.sox.resolve();unit=args.unit.resolve()
        bits=tuple(bytes(fn(i) for i in range(128)) for fn in (ch0,ch1))
        src=d/'in.dsf';src.write_bytes(fixtures.make_dsf(bits))
        original=hashlib.sha256(src.read_bytes()).hexdigest()
        plain=d/'plain.dsf';effect=d/'effect.dsf';analysis=d/'analysis.dsf'
        r0=d/'plain.json';r1=d/'effect.json';ra=d/'analysis.json'
        def case(name,fn):
            try:
                rec=dict(name=name,status='PASS',detail=fn())
                print('PASS',name,flush=True)
            except Exception as e:
                rec=dict(name=name,status='FAIL',error=f'{type(e).__name__}: {e}')
                print('FAIL',name,str(e),flush=True)
            records.append(rec)
            (args.results/'integration-p14.json').write_text(json.dumps(dict(
                schema='sox.dsd.P14.integration.v1',cases=records,
                summary=dict(passed=sum(x['status']=='PASS' for x in records),
                             failed=sum(x['status']=='FAIL' for x in records))),
                indent=2,sort_keys=True,allow_nan=False)+'\n')
        def unit_golden():
            expected=json.loads(GOLDEN.read_text())
            p=subprocess.run([str(unit),'--json','128','basic'],capture_output=True,text=True,timeout=20)
            require(p.returncode==0,p.stderr)
            got=json.loads(p.stdout)
            require(got['frames']=='128' and got['channel_count']==2,'synthetic C source')
            require(got['channels']==expected['channels'],'golden bit counter mismatch')
            for c in (0,1):
                require(got['channels'][c]==oracle(bits[c]),'independent Python bit count mismatch')
            for n in (0,1,27,28,29,43):
                check=subprocess.run([str(unit),'--json',str(n),'basic'],capture_output=True,text=True,timeout=20)
                require(check.returncode==0,check.stderr)
                rows=json.loads(check.stdout)['channels']
                for c in (0,1):
                    require(rows[c]==oracle(bits[c][:n]),f'boundary length {n} channel {c}')
            huge=subprocess.run([str(unit),'--large'],capture_output=True,text=True,timeout=20)
            require(huge.returncode==0,'large integer formatter exited nonzero')
            require(json.loads(huge.stdout)==str((1<<63)+12345),
                    'lossy large integer or nonstandard JSON serialization')
            return dict(frames_checked=[0,1,27,28,29,43,128],
                        large_integer=str((1<<63)+12345),
                        golden='reference/p14_report_golden.json')
        case('bit_exact_chunk_continuity_and_golden',unit_golden)

        def native_passthrough():
            variants=[(plain,r0,[]),(effect,r1,['dsdstat']),
                      (analysis,ra,['dsdstat','-a'])]
            docs=[];digests=[]
            for dst,rep,effects in variants:
                p=run(sox,'--dsd-mode','native','--dsd-report',rep,'-D',src,dst,*effects)
                require(p.returncode==0,p.stderr[-900:])
                digests.append(hashlib.sha256(dst.read_bytes()).hexdigest())
                doc=json.loads(rep.read_text());valid_report(doc)
                require(doc['output']['domain']=='DSD_NATIVE','output domain')
                require(doc['output']['native_completed_frames']=='128','native completion')
                require(doc['source'][0]['channel_roles']==['FL','FR'],'role identity')
                require(doc['source'][0]['physical_bit_order'] in (1,8),'physical bit ordering')
                for c in (0,1):
                    require(doc['source'][0]['native_statistics']['channels'][c]==oracle(bits[c]),
                            f'native source oracle ch{c}')
                if effects:
                    require('one bits=' in p.stderr and '28-bit windows=' in p.stderr,
                            'standalone dsdstat omitted required stderr counters')
                    est=doc['dsdstat'];require(est['analysis_enabled']==bool(len(effects)>1),
                                                'dsdstat -a activation')
                    for c in (0,1):
                        require(all(est['channels'][c][k]==v for k,v in oracle(bits[c]).items()),
                                f'effect bit count ch{c}')
                else:require(doc['dsdstat'] is None,'no implicit effect')
                docs.append(doc)
            require(len(set(digests))==1,'dsdstat modified audio bytes')
            require(hashlib.sha256(src.read_bytes()).hexdigest()==original,'source mutated')
            for c in range(2):
                require(docs[0]['source'][0]['native_statistics']['channels'][c]==
                        docs[1]['source'][0]['native_statistics']['channels'][c],
                        'native statistics differ when optional analyzer enabled')
            require('measurement' not in docs[1]['dsdstat']['channels'][0],
                    'basic path unexpectedly invoked spectral measurements')
            return dict(native_sha256=digests[0],outputs_equal=True,
                        native_windows=101,analysis_qualifier='SACD-style, not certified')
        case('native_audio_bit_hash_unchanged_with_dsdstat_and_a',native_passthrough)

        def schema_stability():
            duplicate=d/'repeat.dsf';report=d/'repeat.json'
            p=run(sox,'--dsd-mode','native','--dsd-report',report,'-D',src,duplicate,'dsdstat')
            require(p.returncode==0,p.stderr)
            require(report.read_bytes()==r1.read_bytes(),'report depends on output/report path or wall time')
            valid_report(json.loads(report.read_text()))
            return dict(bytes_identical=True,schema_version=1)
        case('schema_order_and_repeatability',schema_stability)

        def stdout_policies():
            p=run(sox,'--dsd-mode','native','--dsd-report','-','-q','-D',src,d/'stdout-audio.dsf','dsdstat')
            require(p.returncode==0,p.stderr)
            valid_report(json.loads(p.stdout));require(p.stdout.startswith('{'),'other text on stdout')
            p2=run(sox,'--dsd-mode','native','--dsd-report','-','-D',src,
                   '-t','dsf','-','dsdstat')
            require(p2.returncode!=0,'audio and report both writing to stdout')
            require('conflict' in p2.stderr.lower(),f'missing stdout conflict diagnostic: {p2.stderr}')
            require(not p2.stdout,'audio escaped before conflict check')
            for report_path,out_path in (('-', '/dev/stdout'),('/dev/stdout','-')):
                aliased=run(sox,'--dsd-mode','native','--dsd-report',report_path,
                            '-D',src,'-t','dsf',out_path)
                require(aliased.returncode!=0 and 'stdout' in aliased.stderr.lower(),
                        'stream-alias conflict not rejected')
                require(not aliased.stdout,'audio or JSON escaped before alias-conflict check')
            return dict(json_stdout_parseable=True,mixed_audio_stdout_rejected=True,
                        path_aliases_guarded=True)
        case('stdout_report_and_audio_conflict',stdout_policies)

        def file_policy():
            target=d/'overwrite-input.json'
            source_before=src.read_bytes()
            p=run(sox,'--dsd-mode','native','--dsd-report',src,'-D',src,d/'danger-a.dsf')
            require(p.returncode!=0,'report could overwrite input carrier')
            require(src.read_bytes()==source_before,'input source corrupted')
            existing=d/'existing.json';existing.write_bytes(b'PREEXISTING\n')
            p=run(sox,'--no-clobber','--dsd-mode','native','--dsd-report',existing,
                  '-D',src,d/'safe-a.dsf')
            require(p.returncode!=0,'report silently overwrote --no-clobber target')
            require(existing.read_bytes()==b'PREEXISTING\n','--no-clobber file mutated')
            dest=d/'collision.dsf'
            p=run(sox,'--dsd-mode','native','--dsd-report',dest,'-D',src,dest)
            require(p.returncode!=0,'report accepted same audio destination')
            hardlink=d/'original-hardlink.json'
            os.link(src,hardlink)
            p=run(sox,'--dsd-mode','native','--dsd-report',hardlink,'-D',src,d/'hardlink-a.dsf')
            require(p.returncode!=0,'report accepted input hardlink')
            require(hashlib.sha256(src.read_bytes()).hexdigest()==original,'hardlink modified input')
            return dict(input_protection=True,no_clobber=True,output_collision=True,hardlink_guard=True)
        case('named_report_path_and_overwrite_policy',file_policy)

        def plan_report_destination_policy():
            source=d/'plan-input.dsf';source.write_bytes(src.read_bytes())
            source_digest=hashlib.sha256(source.read_bytes()).hexdigest()
            output=d/'plan-output.dsf'
            args0=('--dsd-plan','--dsd-mode','native','-D',source,output)
            invalid=run(sox,'--dsd-plan','--dsd-mode','native',
                        '--dsd-report',source,'-D',source,output)
            require(invalid.returncode!=0,'plan report overwrote the input carrier')
            require('input carrier' in invalid.stderr.lower(),
                    f'plan missing input-alias diagnostic: {invalid.stderr[-500:]}')
            require(hashlib.sha256(source.read_bytes()).hexdigest()==source_digest,
                    'plan-only report changed source bytes')
            require(not output.exists(),'plan-only command opened an audio output')
            existing=d/'plan-existing.json';existing.write_bytes(b'UNCHANGED\n')
            denied=run(sox,'--no-clobber','--dsd-plan','--dsd-mode','native',
                       '--dsd-report',existing,'-D',source,output)
            require(denied.returncode!=0,'plan ignored --no-clobber')
            require(existing.read_bytes()==b'UNCHANGED\n','plan changed existing report')
            baseline=run(sox,*args0)
            require(baseline.returncode==0,baseline.stderr)
            distinct=d/'plan-report.json'
            named=run(sox,'--dsd-plan','--dsd-mode','native',
                      '--dsd-report',distinct,'-D',source,output)
            require(named.returncode==0 and distinct.is_file(),
                    f'valid plan-only named report failed: {named.stderr[-500:]}')
            plan=json.loads(baseline.stdout)
            require(json.loads(distinct.read_text())==plan,
                    'plan report changed the existing P05 planning schema or fields')
            dash=run(sox,'--dsd-plan','--dsd-mode','native',
                     '--dsd-report','-','-D',source,output,cwd=d)
            require(dash.returncode==0 and json.loads(dash.stdout)==plan,
                    f'plan stdout does not match P05 schema: {dash.stderr[-500:]}')
            require(not (d/'-').exists(),'plan-only stdout request created file named dash')
            require(not output.exists(),'plan-only command opened output audio')
            return dict(input_unchanged=True,no_clobber=True,
                        plan_schema_preserved=True,stdout_dash=True)
        case('plan_only_report_destination_safety',plan_report_destination_policy)

        def uncreated_output_path_aliases():
            before=hashlib.sha256(src.read_bytes()).hexdigest()
            output=d/'alias-uncreated.dsf'
            alias=str(d)+'/./alias-uncreated.dsf'
            require(not output.exists(),'alias precondition violated')
            rejected=run(sox,'--dsd-mode','native','--dsd-report',alias,
                         '-D',src,output)
            require(rejected.returncode!=0,'./ alias replaced completed audio with JSON')
            require('audio output' in rejected.stderr.lower(),
                    f'alias diagnostic absent: {rejected.stderr[-500:]}')
            require(not output.exists(),'failed alias conversion retained partial audio')
            relative='relative-output.dsf'
            require(not (d/relative).exists(),'relative alias precondition violated')
            rejected=run(sox,'--dsd-mode','native','--dsd-report',
                         str(d/relative),'-D',src,relative,cwd=d)
            require(rejected.returncode!=0,'absolute/relative alias accepted')
            require(not (d/relative).exists(),'absolute/relative alias retained audio')
            distinct=d/'safe-destination.dsf';report=d/'safe-report.json'
            accepted=run(sox,'--dsd-mode','native','--dsd-report',report,
                         '-D',src,distinct)
            require(accepted.returncode==0,accepted.stderr[-500:])
            require(distinct.read_bytes()==plain.read_bytes(),
                    'separate JSON report changed native audio')
            valid_report(json.loads(report.read_text()))
            require(hashlib.sha256(src.read_bytes()).hexdigest()==before,
                    'alias rejection changed input source')
            return dict(relative_alias_rejected=True,absolute_alias_rejected=True,
                        no_partial_output=True,distinct_audio_bit_identical=True)
        case('uncreated_output_aliases_do_not_replace_audio',uncreated_output_path_aliases)

        def rejects_pcm():
            import wave,struct
            wav=d/'pcm.wav'
            with wave.open(str(wav),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(88200)
                w.writeframes(struct.pack('<512h',*([0]*512)))
            p=run(sox,'--dsd-report',d/'pcm-fail.json','-D',wav,d/'not-native.wav','dsdstat')
            require(p.returncode!=0,'PCM input accepted by native-only effect')
            require('native' in p.stderr.lower() or 'dsd' in p.stderr.lower(),
                    'domain-specific error absent')
            return dict(rejected=True)
        case('dsdstat_rejects_pcm_without_implicit_modulation',rejects_pcm)

        def decoder_actual_kernel():
            mono=d/'decoder.dsf';mono.write_bytes(fixtures.make_dsf((fixtures.bits(32768,1,'69')[0],)))
            output=d/'decoded.wav';report=d/'decoded.json'
            p=run(sox,'--dsd-mode','auto','--dsd-report',report,'-D',mono,
                  '-r','88200',output,'dsdpcm','-p','mastering','88200',
                  env={'SOX_DSD_KERNEL_FIR':'scalar'})
            require(p.returncode==0,p.stderr[-900:])
            doc=json.loads(report.read_text());valid_report(doc)
            require(doc['processing']['decoder'],'missing observed decoder')
            facts=doc['processing']['decoder'][0]
            require(facts['fir_kernel_actual']=='scalar',f'forced kernel misreported: {facts}')
            require(len(facts['coefficients']['bank_halfband_sha256'])==64,'halfband hash missing')
            require(len(facts['coefficients']['bank_last_sha256'])==64,'last stage hash missing')
            require(facts['profile_id'].startswith('decode.mastering.'),'profile identity missing')
            require(float(facts['gain_mapping']['applied_linear_gain'])==1,'preserve mapping')
            require(facts['frames_produced']!='0','missing decoder output counters')
            return dict(kernel=facts['fir_kernel_actual'],profile=facts['profile_id'],
                        bank_last_sha256=facts['coefficients']['bank_last_sha256'])
        case('actual_forced_decoder_profile_coefficient_kernel',decoder_actual_kernel)

        def pcm_source_representation():
            if not args.candidate.is_file():
                return dict(status='UNRUN',reason='P10 candidate not built')
            import struct,wave
            descriptions=[]
            for bits_per_sample, fmt, scale in ((16,'h',32767),(32,'i',2147483647)):
                path=d/f'pcm-{bits_per_sample}.wav'
                with wave.open(str(path),'wb') as w:
                    w.setnchannels(1);w.setsampwidth(bits_per_sample//8)
                    w.setframerate(88200)
                    w.writeframes(b''.join(struct.pack('<'+fmt,int(.08*scale))
                                          for _ in range(2048)))
                report=d/f'pcm-{bits_per_sample}.json'
                output=d/f'pcm-{bits_per_sample}.dsf'
                cp=run(args.candidate.resolve(),'--dsd-mode','auto',
                       '--dsd-report',report,'-D',path,'-r','2822400',output)
                require(cp.returncode==0,cp.stderr[-600:])
                doc=json.loads(report.read_text());valid_report(doc)
                facts=doc['source'][0]
                require(facts['domain']=='PCM_AUDIO' and facts['container']=='wav',
                        f'actual PCM source container not reported: {facts}')
                require(facts['sample_rate_hz']==88200 and facts['native_hz'] is None,
                        f'PCM sample clock confused with DSD native clock: {facts}')
                require(facts['encoding']=='Signed Integer PCM',
                        f'input encoding unavailable: {facts}')
                require(facts['bits_per_sample']==bits_per_sample,
                        f'actual PCM source width misreported: {facts}')
                descriptions.append((facts['encoding'],facts['bits_per_sample']))
            require(descriptions[0]!=descriptions[1],
                    'different signed PCM input widths produced identical representation')
            native=json.loads(r0.read_text())['source'][0]
            require(native['domain']=='DSD_NATIVE' and native['sample_rate_hz'] is None,
                    'native bit clock mislabeled a PCM sampling rate')
            require(native['native_hz']==str(fixtures.DSD64) and
                    native['physical_bit_order'] in (1,8),
                    'native rate or DSF physical bit order lost')
            return dict(encoding='Signed Integer PCM',widths=[16,32],
                        pcm_clock_hz=88200,native_bit_order_preserved=True)
        case('pcm_source_encoding_clock_and_container',pcm_source_representation)

        def decoder_latency_breakdown():
            for native_rate,output_rate,delay in ((fixtures.DSD64,88200,1348),
                                                 (fixtures.DSD64,44100,1348),
                                                 (fixtures.DSD64*2,176400,1636)):
                name=f'lat-{native_rate}-{output_rate}'
                inp=d/(name+'.dsf')
                inp.write_bytes(fixtures.make_dsf(
                    (fixtures.bits(65536,1,'69')[0],),rate=native_rate))
                dest=d/(name+'.wav');report=d/(name+'.json')
                cmd=('--dsd-mode','auto','-D',inp,'-r',str(output_rate),dest,
                     'dsdpcm','-p','mastering',str(output_rate))
                cp=run(sox,'--dsd-report',report,*cmd)
                require(cp.returncode==0,cp.stderr[-700:])
                facts=json.loads(report.read_text())['processing']['decoder'][0]
                latency=facts['latency']
                require(latency['front_end_lookahead_native_frames']==str(delay),
                        f'wrong FIR delay {name}: {latency}')
                require(abs(latency['front_end_lookahead_seconds']-
                            delay/native_rate)<1e-15,'FIR seconds timebase wrong')
                uses_src=output_rate!=(native_rate//32)
                require(latency['final_src_active']==uses_src,
                        f'SRC bypass state wrong: {name}')
                if uses_src:
                    require(latency['final_src_lookahead_seconds'] is None and
                            latency['final_src_lookahead_intermediate_frames'] is None and
                            latency['final_src_lookahead_note'],
                            'active SRC claimed unsupported delay or omitted explanation')
                else:
                    require(latency['final_src_lookahead_seconds']==0 and
                            latency['final_src_lookahead_intermediate_frames']=='0' and
                            latency['final_src_lookahead_note'] is None,
                            'bypassed SRC did not report exact zero lookahead')
                require(latency['buffering_latency_seconds'] is None and
                        latency['buffering_latency_note'] and
                        latency['total_latency_seconds'] is None and
                        latency['total_latency_note'],
                        'unknown buffering/total latency misrepresented as measured')
                unreported=d/(name+'-no-report.wav')
                cp2=run(sox,'--dsd-mode','auto','-D',inp,'-r',str(output_rate),
                        unreported,'dsdpcm','-p','mastering',str(output_rate))
                require(cp2.returncode==0,cp2.stderr[-700:])
                require(dest.read_bytes()==unreported.read_bytes(),
                        f'report changed decoder payload {name}')
            return dict(master64_delay=1348,master128_delay=1636,
                        bypass_src_zero=True,active_src_unknown_explained=True,
                        audio_bit_identical=True)
        case('decoder_latency_components_and_byte_identity',decoder_latency_breakdown)

        def failure_status():
            high=d/'high.dsf';high.write_bytes(fixtures.make_dsf(fixtures.bits(32768,1,'ones')))
            output=d/'clipping-output.wav';report=d/'clipping.json'
            p=run(sox,'--dsd-clip','error','--dsd-report',report,'-D',high,output,
                  'dsdpcm','-l','sacd','88200','gain','-3')
            require(p.returncode!=0,'clipping policy erroneously succeeded')
            require(report.is_file(),'no final failure report')
            doc=json.loads(report.read_text());valid_report(doc,'failed')
            require(not output.exists(),'failed audio file retained')
            require(doc['source'][0]['native_statistics'] is not None,'failure discarded source evidence')
            return dict(exit_code=p.returncode,status=doc['status'],
                        audio_removed=not output.exists(),
                        diagnostic='clip error' in p.stderr.lower())
        case('fatal_clipping_status_and_partial_output_cleanup',failure_status)

        def dop_report():
            dest=d/'dop.wav';report=d/'dop.json'
            p=run(sox,'--dsd-report',report,'-D',src,'-e','signed-integer','-b','24',dest,'dop')
            require(p.returncode==0,p.stderr[-800:])
            doc=json.loads(report.read_text());valid_report(doc)
            require(doc['output']['domain']=='DOP_TRANSPORT',f'wrong DoP domain: {doc["output"]}')
            require(doc['output']['transport_frames'] not in (None,'0'),'DoP transport frames absent')
            return dict(transport_frames=doc['output']['transport_frames'])
        case('dop_transport_completion_accounting',dop_report)

        def candidate_complete():
            if not args.candidate.is_file():
                return dict(status='UNRUN',reason='GNU link-time candidate test executable unavailable')
            import wave,struct
            pcm=d/'encoder-input.wav';frames=2048
            with wave.open(str(pcm),'wb') as w:
                w.setnchannels(1);w.setsampwidth(4);w.setframerate(88200)
                w.writeframes(b''.join(struct.pack('<i',int(.1*2147483647)) for _ in range(frames)))
            dst=d/'encoded.dsf';report=d/'encoded.json'
            p=run(args.candidate.resolve(),'--dsd-mode','auto','--dsd-report',report,
                  '-D',pcm,'-r','2822400',dst)
            require(p.returncode==0,p.stderr[-800:])
            doc=json.loads(report.read_text());valid_report(doc)
            enc=doc['processing']['encoder'];require(len(enc)==1,'missing actual encoder')
            facts=enc[0]
            require(facts['sdm_kernel_actual']=='scalar',
                    f'expected inherited automatic scalar SDM, got {facts["sdm_kernel_actual"]}')
            require(facts['profile_id']=='encode.mastering.v1.dsd64','wrong encoder ID')
            require(len(facts['coefficient_certificate_sha256'])==64,'missing certificate')
            require(facts['committed_native_frames']==str(frames*32),'encoder output count')
            require(facts['monitor']['first_overload_frame'] is None,'fabricated overload')
            return dict(mastering_release_promoted=False,profile=facts['profile_id'],
                        actual_kernel=facts['sdm_kernel_actual'],
                        logical_native_frames=facts['committed_native_frames'])
        case('test_candidate_actual_encoder_and_monitor_provenance',candidate_complete)

        def candidate_overload():
            if not args.candidate.is_file():
                return dict(status='UNRUN',reason='GNU link-time candidate test executable unavailable')
            import wave,struct
            pcm=d/'encoder-overload.wav';frames=32768
            with wave.open(str(pcm),'wb') as w:
                w.setnchannels(1);w.setsampwidth(4);w.setframerate(88200)
                w.writeframes(b''.join(struct.pack('<i',2147483646 if i>=frames//2
                              else -2147483646) for i in range(frames)))
            dst=d/'encoder-overload.dsf';report=d/'encoder-overload.json'
            p=run(args.candidate.resolve(),'--dsd-mode','auto','--dsd-report',report,
                  '-D',pcm,'-r','2822400',dst)
            require(p.returncode!=0,'interpolation overload silently accepted')
            require('overload' in p.stderr,'missing P10 overload diagnostic')
            require(not dst.exists(),'partial output remains after encoder overload')
            require(report.exists(),'no report after encoder overload')
            doc=json.loads(report.read_text());valid_report(doc,'failed')
            enc=doc['processing']['encoder'];require(len(enc)==1,'no failed encoder facts')
            facts=enc[0]
            require(facts['failure_code']!=0,'missing encoder failure event')
            require(facts['first_error_frame'] is not None,'missing first overload/error index')
            require(facts['committed_native_frames']=='0','failed block published')
            require(facts['sdm_kernel_actual']=='scalar','wrong failed kernel')
            # The P10 monitor's state overloads are distinct from P10
            # interpolation saturation. Neither may be silently conflated.
            require(int(facts['monitor']['overloads'])==0,
                    'input overload improperly relabeled as SDM state overload')
            return dict(failed=True,first_interpolation_error_frame=facts['first_error_frame'],
                        actual_sdm_state_overloads=facts['monitor']['overloads'])
        case('test_candidate_encoder_failure_and_first_event',candidate_overload)

        def cancellation_status():
            if not hasattr(signal,'SIGINT'):
                return dict(status='UNRUN',reason='SIGINT not exposed by Python host')
            # 2.5 million hand-built original bits. The analysis pass makes
            # the interruption deterministic on ordinary development hosts.
            count=2500000
            sequence=bytes((0,1,1,0,1,0,0,1))*(count//8)
            inp=d/'cancel-in.dsf';inp.write_bytes(fixtures.make_dsf((sequence,)))
            out=d/'cancel-out.dsf';report=d/'cancel.json'
            cmd=[str(sox),'--dsd-mode','native','--dsd-report',str(report),
                 '-D',str(inp),str(out),'dsdstat','-a']
            p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            started=time.monotonic()
            while not out.exists() and p.poll() is None and time.monotonic()-started<15:
                time.sleep(.002)
            if p.poll() is not None:
                stdout,stderr=p.communicate(timeout=20)
                raise AssertionError(f'conversion exited before interruption: {stderr[-200:]}')
            time.sleep(.01)
            p.send_signal(signal.SIGINT)
            stdout,stderr=p.communicate(timeout=50)
            require(p.returncode!=0,'interrupted conversion returned success')
            require(report.is_file(),'interrupted conversion lost final report')
            doc=json.loads(report.read_text());valid_report(doc,'cancelled')
            require(not out.exists(),'partial audio retained on cancellation')
            frames=int(doc['source'][0]['native_statistics']['frames'])
            require(0<=frames<count,'cancelled source count invented or finished')
            require(doc['dsdstat'] is not None,'cancelled dsdstat evidence lost')
            return dict(status='cancelled',observed_source_frames=frames,
                        logical_frames=count,partial_audio_removed=True)
        case('sigint_cancellation_preserves_final_status',cancellation_status)

    result=dict(schema='sox.dsd.P14.integration.v1',cases=records,
                summary=dict(passed=sum(x['status']=='PASS' for x in records),
                             failed=sum(x['status']=='FAIL' for x in records)),
                note='Commands executed on temporary files; published data contains no absolute machine paths.')
    (args.results/'integration-p14.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    return int(result['summary']['failed']!=0)


if __name__=='__main__':
    raise SystemExit(main())
