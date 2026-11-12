#!/usr/bin/env python3
"""Phase 04: executable pre-output precision decisions, legacy preservation,
RF64 native parity, and both deliberately approved legacy exceptions.

A command succeeds only when the checked actual process/JSON/bytes do; source
text is never substituted for a runtime test. Descriptor-dependent native
writer assertions remain NOT_RUN until a native runner is implemented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from binary_receipts import executable_libraries


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(ok, message):
    if not ok:
        raise AssertionError(message)


def little_wave(path, frames=71, bits=24, channels=2):
    width=bits//8
    data=b''.join(((i*1234567)%(1<<bits)).to_bytes(width,'little')
                  for i in range(frames*channels))
    fmt=struct.pack('<HHIIHH',1,channels,44100,44100*channels*width,channels*width,bits)
    body=b'fmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(data))+data
    path.write_bytes(b'RIFF'+struct.pack('<I',len(body)+4)+b'WAVE'+body)


def sparse_rf64(path, data_bytes):
    fmt=struct.pack('<HHIIHH',1,1,8000,8000,1,8)
    ds64=struct.pack('<QQQI',data_bytes+72,data_bytes,data_bytes,0)
    header=(b'RF64'+struct.pack('<I',0xffffffff)+b'WAVE'+
            b'ds64'+struct.pack('<I',len(ds64))+ds64+
            b'fmt '+struct.pack('<I',16)+fmt+
            b'data'+struct.pack('<I',0xffffffff))
    with open(path,'wb') as f:
        f.write(header)
        f.truncate(len(header)+data_bytes+(data_bytes&1))
    return len(header)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    results=args.results.resolve();results.mkdir(parents=True,exist_ok=True)
    receipt=results/'routing.json';receipt.unlink(missing_ok=True)
    source=Path(__file__).resolve().parents[2]
    fixture=Path(__file__).resolve().parent/'fixtures'/'phase04'
    sox=args.sox.resolve();probe=args.probe.resolve()
    commands=[];checks={};gates={}
    caps=subprocess.run([str(probe),'capabilities'],capture_output=True,text=True,timeout=10)
    check(caps.returncode==0,f'native probe capability failed: {caps.stderr}')
    capabilities=dict(x.split('=',1) for x in caps.stdout.splitlines() if '=' in x)
    native_ready=capabilities.get('native_build')=='ENABLED' and capabilities.get('native_dsp')=='OK'
    if capabilities.get('native_build')=='ENABLED' and capabilities.get('native_host')=='SUPPORTED':
        check(native_ready,'enabled/supported native arithmetic guard failed (must not silently skip)')
    gates['native_probe_capability']=capabilities
    try:
        with tempfile.TemporaryDirectory(prefix='pcm64-phase04-') as tmp:
            work=Path(tmp);wav=work/'source.wav';little_wave(wav)
            dsd=fixture/'short-dsd64-stereo.dsf'
            check(dsd.is_file(),'missing persistent DSD fixture')
            def run(name,argv,expect=None,stdin=None,program=None):
                cmd=[str(program or sox),*map(str,argv)]
                before=time.monotonic_ns()
                cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  input=stdin,timeout=35,check=False)
                c={'name':name,'argv':cmd,'rc':cp.returncode,
                   'elapsed_ns':time.monotonic_ns()-before,
                   'stdout':cp.stdout.decode('utf-8','replace')[-65536:],
                   'stderr':cp.stderr.decode('utf-8','replace')[-65536:]}
                commands.append(c)
                if expect is not None:check(cp.returncode==expect,
                    f'{name}: exit {cp.returncode} != {expect}; stderr {c["stderr"][-1200:]}')
                return cp
            def plan(name,argv,policy=None,eligible=None,reason=None,steps=None,pcm=None):
                cp=run(name,['--plan',*argv],0)
                try: obj=json.loads(cp.stdout)
                except ValueError as err: raise AssertionError(f'{name}: invalid JSON: {err}; {cp.stdout[-1200:]}')
                commands[-1]['parsed_plan']=obj
                prec=obj['precision']
                if policy is not None:check(prec['requested']==policy,f'{name}: policy: {prec}')
                if eligible is not None:check(prec['graph_eligible'] is eligible,
                    f'{name}: graph eligibility: {prec}')
                if pcm is not None:check(prec['pcm_present'] is pcm,f'{name}: pcm: {prec}')
                if reason is not None:check(reason in (prec['fallback_or_refusal_reason'] or ''),
                    f'{name}: wrong first refusal: {prec}')
                if steps is not None:check([s['name'] for s in obj['steps']]==steps,
                    f'{name}: wrong ordered steps: {[s["name"] for s in obj["steps"]]}')
                check(prec['runner_available'] is False,'Phase04 must not claim runner')
                check(prec['actual_pcm_engine'] != 'binary64',
                      'Phase04 must not claim actual binary64 engine')
                check('actual descriptor' in prec['output_descriptor'] or
                      'descriptor' in prec['output_descriptor'] or
                      'symlink' in prec['output_descriptor'] or
                      'destination' in prec['output_descriptor'],
                      'descriptor preflight must be provisional')
                return obj
            # Exact comparison of supplied RF64/RIFF samples through native
            # query and dump, not simply an acceptance-status comparison.
            pairs=[('libsndfile-float32.rf64','libsndfile-float32.wav'),
                   ('rf64-pcm-ds64-table-entry.wav','riff-pcm-table-case-same-audio.wav'),
                   ('rf64-pcm-nofact-ds64count0.wav','riff-pcm-same-audio.wav'),
                   ('rf64-pcm-nofact-ds64count8.wav','riff-pcm-same-audio.wav')]
            for left,right in (pairs if native_ready else []):
                outputs=[]
                for fname in (left,right):
                    path=fixture/fname
                    check(path.is_file(),f'absent RF64 fixture {fname}')
                    query=subprocess.run([str(probe),'query',str(path)],capture_output=True,timeout=10)
                    dump=subprocess.run([str(probe),'dump',str(path)],capture_output=True,timeout=10)
                    check(query.returncode==0 and dump.returncode==0,
                          f'{fname}: native probe failed: {query.stderr!r}; {dump.stderr!r}')
                    outputs.append((query.stdout,dump.stdout))
                    commands.append({'name':'rf64-native-'+fname,'argv':[str(probe),'query/dump',str(path)],
                                     'query_rc':query.returncode,'dump_rc':dump.returncode,
                                     'query_stdout':query.stdout.decode('utf-8','replace')[-3000:],
                                     'dump_sha256':hashlib.sha256(dump.stdout).hexdigest(),
                                     'source_sha256':sha(path)})
                check(outputs[0][1]==outputs[1][1],f'RF64/RIFF decoded audio differs: {left}')
                checks['native_rf64_pair_'+left]='PASS'
            gates['native_rf64_supplied_pairs']='PASS' if native_ready else (
                'NOT_RUN: native probe unavailable (disabled build or unsupported host)')
            # Two approved compatibility exceptions are tested by executing
            # real SoX behavior, not by checking source strings.
            for value in (0x7ffff000,0x7fffffff,0xffffffff):
                path=work/f'legacy-ds64-{value:08x}.wav'
                sparse_rf64(path,value)
                cp=run(f'legacy-ds64-exact-{value:08x}',['-s',path],0,
                       program=sox.parent/'soxi')
                check(cp.stdout.strip()==str(value).encode(),
                      f'ds64 {value:#x}: reported {cp.stdout!r} instead of exact size')
                checks[f'legacy_ds64_exact_{value:08x}']='PASS'
                path.unlink()
            gates['approved_legacy_rf64_ds64_sizes']='PASS'
            # This gate is executed by io-flac in an uninstalled plugin build.
            # Do not conflate static library / unavailable headers with plugin success.
            gates['approved_single_ld_library_path_plugin']='NOT_RUN: no libFLAC plugin in this build; io-flac plugin topology validates actual dlopen'
            # Actual strict/auto routing and first refusal reasons.
            output=work/'new-output.wav'
            base=['-D',dsd,'-b','24',output]
            plan('dsd-explicit-decoder-gain',['--precision','64',*base,'dsdpcm','96000','gain','-3'],
                 policy='64',eligible=True,steps=['dsdpcm','gain'],pcm=True)
            plan('dsd-implicit-residual-src',['--precision','64','-D',dsd,'-r','96000','-b','24',output,'gain','-3'],
                 policy='64',eligible=False,reason='implicit_pcm_rate',
                 steps=['implicit_dsdpcm','gain','implicit_pcm_rate'])
            p=plan('dsd-ordered-gains',['--precision','64',*base,'dsdpcm','96000','gain','-3','gain','-6'],
                   policy='64',eligible=True,steps=['dsdpcm','gain','gain'])
            factors=[s['gain_factor'] for s in p['steps'] if s['name']=='gain']
            check(len(factors)==2 and math.isclose(factors[0],10**(-3/20),rel_tol=1e-14)
                  and math.isclose(factors[1],10**(-6/20),rel_tol=1e-14),
                  f'gain factors were changed or folded: {factors}')
            checks['separate_ordered_gain_factors']='PASS'
            vol=plan('dsd-input-volume',['--precision','64','-D','-v','0.5',dsd,
                       '-b','24',output],policy='64',pcm=True)
            check(math.isclose(vol['inputs'][0]['volume'],0.5,rel_tol=0,abs_tol=1e-16),
                  'source volume not retained at original position')
            check(vol['input_decoder_count']+vol['graph_decoder_count']==1,
                  'input decode must not be counted twice')
            checks['volume_decode_once']='PASS'
            p=plan('pcm-copy',['--precision','64',wav,'-b','24',output],policy='64',eligible=True,steps=[],pcm=True)
            p=plan('pcm-gain',['--precision','64','-D',wav,'-b','24',output,'gain','-3'],
                   policy='64',eligible=True,steps=['gain'])
            p=plan('pcm-auto',['--precision','auto',wav,'-b','24',output],policy='auto',pcm=True)
            check(p['precision']['actual_route']=='legacy-effects', 'PCM auto must be legacy')
            p=plan('pcm-32',['--precision','32',wav,'-b','24',output],policy='32',pcm=True)
            check(p['precision']['actual_route']=='legacy-effects', 'PCM32 must be legacy')
            p=plan('dsd-auto',['--precision','auto',*base,'dsdpcm','96000'],policy='auto')
            check(p['precision']['actual_route']=='legacy-effects','DSD auto not authorized for native')
            p=plan('dsd-32',['--precision','32',*base,'dsdpcm','96000'],policy='32')
            check(p['precision']['actual_route']=='legacy-effects','DSD32 must be legacy')
            pure=work/'native-copy.dff'
            p=plan('dsd-bit-domain',['--precision','64',dsd,pure],policy='64',pcm=False,steps=[])
            check(p['precision']['actual_pcm_engine']=='none' and not p['precision']['refused'],
                  'native DSD bit copy must not demand PCM runner')
            run('native-dsd-bit-repack',['--precision','64',dsd,pure],0)
            check(pure.is_file() and pure.stat().st_size>0,'bit copy produced no DFF')
            commands[-1]['output_sha256']=sha(pure)
            checks['pure_dsd_bit_domain_execution']='PASS'
            refusals=[
                ('unsupported-rate',['--precision','64','-D',wav,'-r','48000',output],'implicit_pcm_rate'),
                ('conventional-effect',['--precision','64','-D',wav,output,'highpass','300'],'conventional'),
                ('explicit-rate',['--precision','64','-D',wav,output,'rate','96000'],'conventional'),
                ('explicit-vol',['--precision','64','-D',wav,output,'vol','0.3'],'conventional'),
                ('scanning-gain',['--precision','64','-D',wav,output,'gain','-n'],'gain requires scanning'),
                ('auto-dither',['--precision','64',wav,'-b','16',output,'gain','-3'],'automatic dither'),
                ('explicit-dither',['--precision','64','-D',wav,output,'dither'],'conventional'),
                ('guard',['--precision','64','-G',wav,output],'-G/--norm'),
                ('norm',['--precision','64','--norm',wav,output],'-G/--norm'),
                ('remix',['--precision','64','-D',wav,output,'remix','1'],'channel'),
                ('unsupported-output',['--precision','64','-D',wav,work/'unsupported.aiff'],'native PCM output'),
                ('unsupported-source',['--precision','64','-D','-t','raw','-r','44100','-c','2',
                                       '-e','floating-point','-b','64',wav,'-b','24',output],
                 'actual input handler/header'),
                ('multi-input',['--precision','64','-D',wav,wav,output],'exactly one input')]
            for name,argv,want in refusals:
                target=next((Path(x) for x in argv if str(x).endswith(('new-output.wav','unsupported.aiff'))),None)
                check(target is not None,name+' target missing')
                target.write_bytes(b'SENTINEL\x00\xff'+name.encode())
                before=sha(target)
                cp=run('strict-refusal-'+name,argv,2)
                check(sha(target)==before,f'{name} truncated pre-existing destination')
                check(want in cp.stderr.decode('utf-8','replace'),
                      f'{name}: wrong first refusal: {cp.stderr[-600:]}')
                commands[-1]['destination_sha256_before_after']=before
                checks['strict_refusal_'+name]='PASS'
                target.unlink()
            # Eligible-but-unimplemented refusal before output, for both
            # existing and nonexistent destinations (no destructive write).
            for existing in (False,True):
                dest=work/('strict-existing.wav' if existing else 'strict-new.wav')
                if existing:dest.write_bytes(b'PRESERVE-STRICT-PCM')
                before=sha(dest) if existing else None
                cp=run('runner-unavailable-existing='+str(existing),
                       ['--precision','64','-D',wav,'-b','24',dest,'gain','-3'],2)
                check(('runner unavailable' if native_ready else 'arithmetic/backend')
                      in cp.stderr.decode('utf-8','replace'),
                      f'wrong unavailable-runner reason: {cp.stderr[-500:]}')
                check((sha(dest)==before if existing else not dest.exists()),
                      f'runner unavailable altered destination (existing={existing})')
                checks['strict_runner_unavailable_existing='+str(existing)]='PASS'
            # Path inspection must be static and must not claim fstat/seek.
            if hasattr(os,'mkfifo'):
                fifo=work/'sink.fifo';os.mkfifo(fifo)
                p=plan('fifo-native-ineligible',['--precision','64','-D',wav,'-t','wav',fifo,'gain','-3'],
                       policy='64',eligible=False,reason='FIFO')
                checks['static_fifo_rejected']='PASS'
            real=work/'linked.wav';real.write_bytes(b'ALIAS-SENTINEL')
            symlink=work/'target-symlink.wav';symlink.symlink_to(real)
            p=plan('symlink-regular-provisional',['--precision','64','-D',wav,'-t','wav',symlink,'gain','-3'],
                   policy='64',eligible=True)
            check('symlink' in p['precision']['output_descriptor'],
                  'symlink target not correctly classified')
            dest_broken=work/'dangling.wav';dest_broken.symlink_to(work/'not-there.wav')
            p=plan('symlink-dangling-ineligible',['--precision','64','-D',wav,'-t','wav',dest_broken,'gain','-3'],
                   policy='64',eligible=False,reason='dangling')
            cp=run('strict-dangling-no-clobber',['--precision','64','-D',wav,'-t','wav',dest_broken,'gain','-3'],2)
            check(dest_broken.is_symlink() and not dest_broken.exists(),
                  'dangling symlink was followed/clobbered')
            checks['path_classification']='PASS'
            # No-output inspection never creates an absent destination.
            no_output=work/'plan-must-not-create.wav'
            plan('no-output-plan',['--precision','64','-D',wav,no_output,'gain','-3'],
                 policy='64',eligible=True)
            check(not no_output.exists(),'--plan unexpectedly created output')
            for bad in ('float64','f64','AUTO',''):
                cp=run('invalid-precision-'+repr(bad),['--precision',bad,wav,work/'invalid.wav'])
                check(cp.returncode!=0 and not (work/'invalid.wav').exists(),
                      f'invalid precision {bad!r} accepted/wrote output')
                checks['invalid_precision_'+repr(bad)]='PASS'
            # Compare actual default / --precision32 / --precision auto
            # output bytes, not merely route labels.
            for suffix,options in (('default',[]),('explicit32',['--precision','32']),
                                   ('explicit_auto',['--precision','auto'])):
                target=work/('legacy-'+suffix+'.wav')
                run('legacy-audio-'+suffix,[*options,'-R','-D',wav,'-b','24',target,'gain','-3'],0)
                commands[-1]['output_sha256']=sha(target)
            hashes=[sha(work/('legacy-'+x+'.wav')) for x in ('default','explicit32','explicit_auto')]
            check(len(set(hashes))==1,f'legacy PCM output changed with policy: {hashes}')
            checks['legacy_pcm_default_32_auto_bit_identical']='PASS'
            dsd_outputs=[]
            for label,policy in (('default',[]),('explicit32',['--precision','32']),
                                 ('explicit-auto',['--precision','auto'])):
                dest=work/('dsd-legacy-'+label+'.wav')
                rpt=work/('dsd-legacy-'+label+'.json')
                argv=['-R','-D',*policy,'--report',rpt,dsd,'-b','24',dest,
                      'dsdpcm','88200']
                run('legacy-dsd-audio-'+label,argv,0)
                check(rpt.exists() and dest.exists(), 'DSD report/audio missing')
                r=json.loads(rpt.read_text())
                check(r['precision']['actual_pcm_engine']=='sox_sample_t.int32'
                      and r['precision']['binary64_pcm_processing'] is False and
                      r['precision']['runner_available'] is False,
                      'DSD execution report falsely identifies native binary64')
                check(r['precision']['requested']==(policy[1] if policy else 'auto'),
                      'report policy does not match CLI request')
                commands[-1]['parsed_report']=r
                commands[-1]['output_sha256']=sha(dest)
                dsd_outputs.append(sha(dest))
            check(len(set(dsd_outputs))==1,
                  'DSD auto / explicit32 outputs or report enabled routes differ')
            checks['legacy_dsd_default_auto_32_audio_and_reports_equal']='PASS'
            # Encoder + decoder remain structurally visible, but still no
            # executable PCM64 coordinator, and old graph executes on auto/32.
            enc=plan('dsd-encoder',['--precision','64','-D',wav,work/'encode.dsf'],policy='64',pcm=True)
            check(enc['encoder_count']>=1,'encoder missing from plan')
            dec=plan('dsd-implicit-decoder',['--precision','64','-D',dsd,'-b','24',output],policy='64')
            check(dec['graph_decoder_count']+dec['input_decoder_count']==1,
                  'decoder count missing')
            checks['decoder_encoder_counts']='PASS'
            # Preserve only exact, proven permutations as role maps. A weighted
            # remix has the same channel count and is NOT a permutation.
            good=plan('pure-channel-role-map',['--precision','64','-D',wav,'-b','24',output,
                       'remix','2','1'],policy='64',eligible=True,steps=['remix'])
            check(good['steps'][0]['native_permutation'] and
                  good['steps'][0]['native_permutation_map']==[1,0],
                  'correct source-order mapping missing')
            checks['pure_role_map_order']='PASS'
            for label,arguments in (('weighted',['1v0.5','2v0.5']),
                                    ('combined',['1,2','1,2'])):
                invalid=plan('nonpermutation-'+label,['--precision','64','-D',wav,
                             '-b','24',output,'remix',*arguments],policy='64',
                             eligible=False,reason='pure output-role permutation')
                check(invalid['steps'][0]['native_permutation'] is False,
                      'weighted channel mixing was certified as a pure map')
                checks['nonpermutation_'+label]='PASS'
            p=plan('role-map-not-terminal',['--precision','64','-D',wav,
                   '-b','24',output,'remix','2','1','gain','-3'],
                   policy='64',eligible=False,reason='terminal output-role mapping')
            checks['role_mapping_must_be_terminal']='PASS'
            for name,op in (('restart','restart'),('newfile','newfile'),('colon',':')):
                p=plan('multiple-effects-chains-'+name,['--precision','64','-D',wav,
                       '-b','24',output,'gain','-3',op,'gain','-6'],policy='64',
                       eligible=False,reason='one effects chain')
                checks['multiple_effects_chains_'+name]='PASS'
            p=plan('pcm64-encoding-not-engine',['--precision','auto','-D',wav,
                   '-e','floating-point','-b','64',output,'gain','-3'],policy='auto')
            check(p['precision']['actual_pcm_engine']=='sox_sample_t.int32',
                  '-b 64 mistakenly selected binary64 graph execution')
            checks['b64_not_processing_precision']='PASS'
            # The static decision is not a descriptor validation. Native PCM
            # writer cannot be exercised by --precision64 in Phase04.
            gates['native_actual_descriptor_precommit']='NOT_RUN: required64 PCM runner intentionally unavailable until Phase05'
            gates['native_symlink_retarget_hardlink_alias_stdout_pipe']='NOT_RUN: native PCM runner intentionally unavailable until Phase05'
            gates['native_report_actual_execution']='NOT_RUN: native PCM runner intentionally unavailable until Phase05'
            gates['legacy_pcm_byte_compatibility']='PASS'
            gates['strict_static_refusals_and_sentinels']='PASS'
        status='PASS_WITH_NOT_RUN' if any(str(x).startswith('NOT_RUN') for x in gates.values()) else 'PASS'
        result={'suite':'routing','status':status,'source_git_commit':None,
                'checks':checks,'gate_execution':gates,'commands':commands,
                'binary_sha256':sha(sox),'probe_sha256':sha(probe),
                'source_and_binary_sha256':{
                    **{str(p.relative_to(source)):sha(p) for p in
                       (source/'src/dsd_plan.c',source/'src/sox_ng.c',
                        source/'src/pcm_f64_io.c',source/'src/formats.c',
                        source/'src/wav.c',source/'tests/pcm64/routing.py')},
                    'src/sox':sha(sox),'test/pcm64_wav_probe':sha(probe)},
                'executed_binary_sha256':{str(sox):sha(sox),str(probe):sha(probe)},
                'runtime_libraries':executable_libraries(sox),
                'host':platform.platform(),'python':sys.version,
                'test_count':len(checks),'command_count':len(commands),
                'native_probe_capabilities':capabilities}
        try:
            commit=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],
                capture_output=True,text=True,timeout=5)
            if commit.returncode==0:result['source_git_commit']=commit.stdout.strip()
        except (OSError,subprocess.TimeoutExpired): pass
        receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(status,'routing',len(checks),'checks',len(commands),'commands')
        return 0
    except Exception as e:
        receipt.write_text(json.dumps({'suite':'routing','status':'FAIL',
            'error':f'{type(e).__name__}: {e}','checks':checks,
            'gate_execution':gates,'commands':commands},indent=2)+'\n')
        print('FAIL routing:',type(e).__name__,str(e),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
