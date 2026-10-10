#!/usr/bin/env python3
"""P10 actual CLI-graph contracts, including the fail-closed release boundary.

The uninstalled candidate executable uses two link-time wrappers to exercise
unqualified code. No user-visible flag, profile alias, or environment override
can activate the release executable. All fixtures originate independently of
SoX writers; candidate output parsing uses the inherited independent oracle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import tempfile
import wave
import numpy as np
from reference import fixtures, verify
from p10_corpus import RATES, SOURCES, stimulus
try:
    import resource
except ImportError:
    resource = None
ROOT=Path(__file__).resolve().parents[2]


def wav(path,rate,channels=1,frames=2003,peak=.3,kind='tone'):
    t=np.arange(frames)/rate
    if kind=='step':y=np.where(t<t[-1]/2,-peak,peak)
    else:y=peak*np.sin(2*np.pi*997*t)
    samples=np.column_stack([np.rint(y*(2**31-1)*(1-.1*c)) for c in range(channels)]).astype('<i4')
    with wave.open(str(path),'wb') as out:
        out.setnchannels(channels);out.setsampwidth(4);out.setframerate(rate)
        out.writeframes(samples.tobytes())
    return samples


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,default=ROOT/'src/sox_ng')
    ap.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    ap.add_argument('--baseline-sox',type=Path)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args();a.results.mkdir(parents=True,exist_ok=True)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='p10-graph-') as temp:
        tmp=Path(temp)
        def clean(text):
            return str(text).replace(str(tmp),'<fixture>').replace(str(ROOT),'<tree>')
        def record(name,fn):
            try:
                row=dict(name=name,status='pass');row.update(fn() or {})
            except Exception as error:
                row=dict(name=name,status='fail',reason=clean(error));print('FAIL',name,clean(error),flush=True)
            rows.append(row)
            summary={s:sum(r['status']==s for r in rows) for s in ('pass','fail','unrun')}
            path=a.results/'cli.json';partial=path.with_suffix('.tmp')
            partial.write_text(json.dumps(dict(schema='P10/CLI-graph/1',release_qualified=False,
                candidate_access='uninstalled test executable with explicit GNU link-time wrappers only',
                rows=rows,summary=summary),sort_keys=True,indent=2)+'\n');partial.replace(path)
        def invoke(args,*,exe=None,limit=None,automatic=True):
            def set_limit():
                signal.signal(signal.SIGXFSZ,signal.SIG_IGN)
                resource.setrlimit(resource.RLIMIT_FSIZE,(limit,limit))
            cp=subprocess.run([str((exe or a.candidate).resolve()),'-V3',
                *(['--dsd-mode','auto'] if automatic else []),'--dsd-layout-loss','warn',
                *map(str,args)],capture_output=True,text=True,timeout=120,
                env={**os.environ,'OMP_NUM_THREADS':'2'},preexec_fn=set_limit if limit is not None else None)
            return cp
        def encode(src,dst,rate=2822400,extra=(),glob=('-D',),output=(),exe=None,ok=True):
            cp=invoke([*glob,src,'-r',rate,*output,dst,*extra],exe=exe)
            assert (cp.returncode==0)==ok,(cp.returncode,cp.stderr[-1800:])
            if ok:assert dst.exists(),cp.stderr
            else:assert not dst.exists(),('failed conversion retained output',cp.stderr)
            return cp
        def read_dsf(path):return verify.decode_dsf(path.read_bytes())
        pcm=tmp/'pcm.wav';wav(pcm,88200)
        for source in SOURCES:
            src=tmp/f'pcm-{source}.wav';wav(src,source)
            for native in RATES:
                def case(source=source,native=native,src=src):
                    dst=tmp/f'matrix-{source}-{native}.dsf'
                    cp=encode(src,dst,native)
                    info=read_dsf(dst);expected=(2003*native+source//2)//source
                    assert info['frames']==expected,(info['frames'],expected)
                    assert info['rate']==native and info['channels']==1
                    assert len(re.findall(r'effects chain: pcmdsd',cp.stderr))==1,cp.stderr
                    assert not re.search(r'effects chain: (rate|dither)\s',cp.stderr),cp.stderr
                    return dict(source_hz=source,native_hz=native,native_frames=expected,
                        native_bits_sha256=info['chronological_bits_sha256'],exit_code=cp.returncode)
                record(f'rate_matrix_{source}_{native}',case)
        base=tmp/'base.dsf';encode(pcm,base)
        def explicit():
            dst=tmp/'explicit.dsf';cp=encode(pcm,dst,extra=('pcmdsd','2822400'))
            assert dst.read_bytes()==base.read_bytes()
            return dict(sha256=digest(dst),exit_code=cp.returncode)
        record('explicit_matches_automatic',explicit)
        for reference,scale in (('auto',.5),('pcm',.5),('dsd',1.)):
            def reference_case(reference=reference,scale=scale):
                destination=tmp/f'reference-{reference}.dsf'
                cp=encode(pcm,destination,extra=('pcmdsd','--reference',reference,'2822400'))
                with wave.open(str(pcm),'rb') as f:
                    samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i4').astype(np.float64)/(2**31-1)
                raw=tmp/'reference.f64le';raw.write_bytes(samples.astype('<f8').tobytes())
                packed=tmp/'reference.bits';report=tmp/'reference.json'
                check=subprocess.run([str(ROOT/'test/dsd_test_p10'),'--render','88200','2822400',
                    'encode.mastering.v1.dsd64',str(scale),'guarded',str(raw),str(packed),str(report)],
                    capture_output=True,text=True,timeout=120)
                assert check.returncode==0,check.stderr
                actual=read_dsf(destination)
                expected=np.unpackbits(np.frombuffer(packed.read_bytes(),dtype=np.uint8))[:actual['frames']].tobytes()
                assert actual['timeline'][0]==expected,reference
                return dict(reference=reference,scale=scale,native_bits_sha256=actual['chronological_bits_sha256'])
            record('explicit_reference_'+reference,reference_case)
        def generated_pcm():
            destination=tmp/'generated.dsf'
            cp=invoke(['-D','-r','88200','-n','-r','2822400',destination,
                'synth','0.02','sine','997','gain','-20'])
            assert cp.returncode==0,cp.stderr
            info=read_dsf(destination)
            assert info['frames']==56448,info['frames']
            chain=re.findall(r'effects chain: (\w+)',cp.stderr)
            assert chain.count('pcmdsd')==1 and chain.index('gain')<chain.index('pcmdsd'),chain
            return dict(native_frames=info['frames'],chain=chain)
        record('generated_PCM_through_single_composite',generated_pcm)
        def dither():
            dst=tmp/'default-dither.dsf';cp=encode(pcm,dst,glob=())
            assert dst.read_bytes()==base.read_bytes()
            assert not re.search(r'effects chain: dither\s',cp.stderr)
            return dict(sha256=digest(dst),exit_code=cp.returncode)
        record('D_does_not_change_modulation_or_add_dither',dither)
        for channels in (1,2,6):
            src=tmp/f'channels-{channels}.wav';wav(src,88200,channels,frames=513)
            def channelcase(channels=channels,src=src):
                hashes=[]
                for size,threads in ((32,'--single-threaded'),(257,'--single-threaded'),
                                     (8192,'--single-threaded'),(8192,'--multi-threaded')):
                    dst=tmp/f'channels-{channels}-{size}-{threads}.dsf'
                    cp=encode(src,dst,glob=('-D','--buffer',str(size),threads,*(['--dsd-layout','FL,FR,FC,LFE,BL,BR'] if channels==6 else [])))
                    info=read_dsf(dst);assert info['frames']==513*32 and info['channels']==channels
                    hashes.append(digest(dst))
                assert len(set(hashes))==1,hashes
                return dict(channels=channels,sha256=hashes[0],buffer_bytes=[32,257,8192],
                    thread_flags=['single','multi'],openmp_configured='-fopenmp' in (ROOT/'src/Makefile').read_text())
            record(f'channel_buffer_invariance_{channels}',channelcase)
        # Empty/short finite files and container-specific last-byte completion.
        for n in (0,1,2,17,257):
            src=tmp/f'endpoint-{n}.wav';wav(src,48000,frames=n)
            def endpoint(n=n,src=src):
                dst=tmp/f'endpoint-{n}.dsf';encode(src,dst)
                info=read_dsf(dst);expected=(n*2822400+24000)//48000
                assert info['frames']==expected,(info['frames'],expected)
                return dict(source_frames=n,native_frames=expected)
            record(f'finite_endpoint_{n}',endpoint)
        src=tmp/'completion.wav';wav(src,48000,frames=257)
        reference=tmp/'completion.dsf';encode(src,reference)
        native=read_dsf(reference)
        def dff():
            dst=tmp/'completion.dff';encode(src,dst)
            info=verify.decode_dff(dst.read_bytes());n=native['frames']
            assert info['frames']==(n+7)//8*8,(info['frames'],n)
            assert info['timeline'][0][:n]==native['timeline'][0]
            return dict(logical_native_frames=n,container_native_frames=info['frames'])
        record('DFF_final_byte_completion',dff)
        def dop():
            dst=tmp/'completion.raw'
            cp=invoke(['-D',src,'-t','raw','-e','signed-integer','-b','24',dst,'pcmdsd','2822400','dop'])
            assert cp.returncode==0,cp.stderr
            n=native['frames'];info=verify.decode_dop(dst.read_bytes(),1,n)
            assert info['timeline'][0]==native['timeline'][0]
            return dict(logical_native_frames=n,container_bytes=dst.stat().st_size)
        record('DoP_final_word_completion',dop)
        for mode in ('auto','explicit','experimental'):
            def gate(mode=mode):
                dst=tmp/f'public-{mode}.dsf'
                extra=() if mode=='auto' else ('pcmdsd',*(['-p','experimental'] if mode=='experimental' else []),'2822400')
                cp=encode(pcm,dst,extra=extra,exe=a.sox,ok=False)
                assert 'unqualified' in cp.stderr or 'unavailable' in cp.stderr or 'no qualified composite' in cp.stderr,cp.stderr
                return dict(exit_code=cp.returncode,output_created=False,diagnostic=clean(cp.stderr))
            record(f'release_gate_{mode}',gate)
        def plan():
            cp=invoke(['--dsd-plan','-D',pcm,'-r','2822400',tmp/'plan.dsf'],exe=a.sox)
            assert cp.returncode==0,cp.stderr
            data=json.loads(cp.stdout)
            encoded=[s for s in data['steps'] if s['name']=='implicit_pcmdsd']
            assert len(encoded)==1
            assert data['encoder']['qualified'] is False and data['encoder']['prefilter_design_hz']==88200,data
            return dict(plan=json.loads(clean(json.dumps(data))))
        record('release_plan_discloses_unqualified_profile',plan)
        # Reconstruct a candidate tone, then independently re-encode those graph
        # samples with the resolved inverse decoder reference. This checks the
        # DSD provenance scale, not just two spellings of automatic routing.
        for reference_name,scale in (('preserve',1.),('sacd',.5)):
            for gain in (0,-3):
                def origin(reference_name=reference_name,scale=scale,gain=gain):
                    prefix=f'origin-{reference_name}-{gain}';decoded=tmp/(prefix+'.raw')
                    flags=['--dsd-level',reference_name]
                    gain_args=['gain',str(gain)]
                    cp=invoke(['-D',*flags,base,'-r','88200','-t','raw','-e','signed-integer','-b','32',decoded,*gain_args])
                    assert cp.returncode==0,cp.stderr
                    f64=tmp/(prefix+'.f64le')
                    values=np.frombuffer(decoded.read_bytes(),dtype='<i4').astype(np.float64)/(2**31-1)
                    f64.write_bytes(values.astype('<f8').tobytes())
                    packed=tmp/(prefix+'.bits');report=tmp/(prefix+'.json')
                    p=subprocess.run([str(ROOT/'test/dsd_test_p10'),'--render','88200','2822400',
                        'encode.mastering.v1.dsd64',str(scale),'guarded',str(f64),str(packed),str(report)],
                        capture_output=True,text=True,timeout=120)
                    assert p.returncode==0,p.stderr
                    out=tmp/(prefix+'.dsf');encode(base,out,extra=gain_args,glob=('-D',*flags))
                    actual=read_dsf(out)
                    expected=np.unpackbits(np.frombuffer(packed.read_bytes(),dtype=np.uint8))[:actual['frames']].tobytes()
                    assert actual['timeline'][0]==expected,('reference scale mismatch',reference_name,gain)
                    return dict(decoder_reference=reference_name,gain_db=gain,resolved_encoder_scale=scale,
                        native_frames=actual['frames'],native_bits_sha256=actual['chronological_bits_sha256'])
                record(f'DSD_origin_{reference_name}_{gain}',origin)
        def mixed_reference():
            mixed=tmp/'mixed-reference.raw'
            cp=invoke(['-D','-m',base,pcm,'-r','88200','-t','raw',
                '-e','signed-integer','-b','32',mixed])
            assert cp.returncode==0,cp.stderr
            raw=tmp/'mixed-reference.f64le'
            values=np.frombuffer(mixed.read_bytes(),dtype='<i4').astype(np.float64)/(2**31-1)
            raw.write_bytes(values.astype('<f8').tobytes())
            packed=tmp/'mixed-reference.bits';report=tmp/'mixed-reference.json'
            check=subprocess.run([str(ROOT/'test/dsd_test_p10'),'--render','88200','2822400',
                'encode.mastering.v1.dsd64','.5','guarded',str(raw),str(packed),str(report)],
                capture_output=True,text=True,timeout=120)
            assert check.returncode==0,check.stderr
            dst=tmp/'mixed-reference.dsf'
            cp=invoke(['-D','--dsd-layout','MONO','-m',base,pcm,'-r','2822400',dst])
            assert cp.returncode==0,cp.stderr
            actual=read_dsf(dst)
            expected=np.unpackbits(np.frombuffer(packed.read_bytes(),dtype=np.uint8))[:actual['frames']].tobytes()
            assert actual['timeline'][0]==expected,'mixed-source encoder must use the PCM reference scale'
            return dict(resolved_encoder_scale=.5,native_frames=actual['frames'],
                native_bits_sha256=actual['chronological_bits_sha256'])
        record('mixed_DSD_PCM_reference_policy',mixed_reference)
        def fractional():
            dst=tmp/'fractional.dsf';cp=encode(pcm,dst,extra=('speed','1.00001','pcmdsd','2822400'),ok=False)
            assert 'integer' in cp.stderr,cp.stderr
            return dict(exit_code=cp.returncode,diagnostic=clean(cp.stderr))
        record('fractional_source_clock_rejected',fractional)
        overload=tmp/'overload.wav';wav(overload,88200,2,frames=32768,peak=1.,kind='step')
        for glob in (('-D',),('-D','--buffer','32'),('-D','--multi-threaded')):
            def over(glob=glob):
                dst=tmp/'overload.dsf';cp=encode(overload,dst,glob=glob,ok=False)
                assert 'interpolation overload' in cp.stderr and 'attenuation' in cp.stderr,cp.stderr
                assert 'clipped' not in cp.stderr and 'Done.' not in cp.stderr,cp.stderr
                return dict(exit_code=cp.returncode,output_removed=True,diagnostic=clean(cp.stderr))
            record('fatal_interpolation_'+str(len(rows)),over)
        def attenuation():
            dst=tmp/'attenuated.dsf';cp=encode(overload,dst,extra=('gain','-6'))
            assert read_dsf(dst)['frames']==32768*32
            return dict(exit_code=cp.returncode,explicit_gain_db=-6.)
        record('explicit_attenuation_retry',attenuation)
        def second_channel_overload():
            src=tmp/'second-channel-overload.wav'
            values=wav(src,88200,2,frames=4096,peak=1.,kind='step')
            values[:,1]=values[:,0];values[:,0]=0
            with wave.open(str(src),'wb') as f:
                f.setnchannels(2);f.setsampwidth(4);f.setframerate(88200);f.writeframes(values.tobytes())
            destination=tmp/'second-channel-overload.dsf'
            cp=encode(src,destination,glob=('-D','--multi-threaded'),ok=False)
            assert 'interpolation overload' in cp.stderr and 'channel 1,' in cp.stderr,cp.stderr
            return dict(exit_code=cp.returncode,first_bad_channel=1,output_removed=True,diagnostic=clean(cp.stderr))
        record('second_channel_failure_discards_multichannel_output',second_channel_overload)
        # Normalization must stay in PCM; an unsupported full-scale result must
        # fail the encoder envelope rather than normalize native pulses.
        def norm():
            dst=tmp/'norm.dsf';cp=invoke(['--norm=-9','-D',pcm,'-r','2822400',dst,'pcmdsd','2822400'])
            assert cp.returncode==0,cp.stderr
            chain=re.findall(r'effects chain: (\w+)',cp.stderr)
            assert chain.count('pcmdsd')==1 and chain.index('gain')<chain.index('pcmdsd'),chain
            assert 'gain' not in chain[chain.index('pcmdsd')+1:],chain
            return dict(chain=chain,exit_code=cp.returncode)
        record('normalization_before_explicit_encoder',norm)
        if resource is not None and hasattr(resource,'RLIMIT_FSIZE'):
            for limit in (128,5000,20000):
                def failure(limit=limit):
                    dst=tmp/f'limited-{limit}.dsf'
                    cp=invoke(['-D',overload,'-r','2822400',dst,'gain','-6'],limit=limit)
                    assert cp.returncode!=0 and not dst.exists(),(cp.returncode,cp.stderr)
                    assert 'write failed' in cp.stderr or 'finalization failed' in cp.stderr,cp.stderr
                    return dict(exit_code=cp.returncode,size_limit=limit,output_removed=True,diagnostic=clean(cp.stderr))
                record(f'output_failure_{limit}',failure)
        def devfull():
            full=Path('/dev/full')
            if not full.exists():return dict(status='unrun',reason='/dev/full unavailable')
            before=full.stat();cp=invoke(['-D',pcm,'-r','2822400','-t','dsf',full])
            assert cp.returncode!=0 and full.stat().st_ino==before.st_ino,(cp.returncode,cp.stderr)
            return dict(exit_code=cp.returncode,device_retained=True)
        record('output_device_failure',devfull)
        if a.baseline_sox:
            raw=tmp/'native-pcm.wav';wav(raw,2822400,frames=32768,peak=.25)
            for profile in ('clans-4','sdm-8'):
                def manual(profile=profile):
                    dests=[]
                    for exe,label in ((a.sox,'current'),(a.baseline_sox,'baseline')):
                        dst=tmp/f'manual-{profile}-{label}.dsf'
                        cp=invoke(['-D',raw,dst,'sdm','-f',profile],exe=exe,automatic=False)
                        assert cp.returncode==0,cp.stderr;dests.append(dst)
                    assert dests[0].read_bytes()==dests[1].read_bytes()
                    return dict(profile=profile,sha256=digest(dests[0]))
                record('manual_sdm_compatibility_'+profile,manual)
    summary={s:sum(r['status']==s for r in rows) for s in ('pass','fail','unrun')}
    print(json.dumps(summary,sort_keys=True));return int(summary['fail']>0)
if __name__=='__main__':raise SystemExit(main())
