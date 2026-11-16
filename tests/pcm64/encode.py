#!/usr/bin/env python3
"""Phase 06A direct source-binary64 -> certified composite -> DSF/DFF.

The public CLI, private bounded coordinator, independently translated Python
frozen recurrence, and physically parsed container bytes must all agree. The
admission oracle uses the exact post-warn-clip doubles observed inside the
production composite, rather than an assumed source-level amplitude.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time

SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE/'tests/dsd'))
from test_resonator import load_constants, oracle

UINT64=(1<<64)-1
CERT_LIMIT=.5+2**-28
RATES=(2_822_400,5_644_800)
CHANNEL_ROLES={6:'FL,FR,FC,LFE,BL,BR'}


def demand(v,desc):
    if not v:raise AssertionError(desc)


def digest(data):return hashlib.sha256(data).hexdigest()


def file_digest(path):return digest(path.read_bytes())


def make_wav(path,frames,channels,rate,kind='f64'):
    """Minimal nonextended RIFF WAV, with exact little-endian sample words."""
    vals=[v for frame in frames for v in frame]
    if kind=='f64':
        fmt,precision,raw=3,64,struct.pack('<%dd'%len(vals),*vals)
    elif kind=='f32':
        fmt,precision,raw=3,32,struct.pack('<%df'%len(vals),*vals)
    else:
        precision=int(kind[1:]);fmt=1
        raw=b''.join((int(v)+(128 if precision==8 else 0)).to_bytes(
            precision//8,'little',signed=precision!=8) for v in vals)
    framebytes=channels*precision//8
    info=struct.pack('<HHIIHH',fmt,channels,rate,rate*framebytes,framebytes,precision)
    if fmt==3:info+=b'\0\0'  # WAVEFORMATEX extra-bytes length
    chunks=b'fmt '+struct.pack('<I',len(info))+info
    chunks+=b'data'+struct.pack('<I',len(raw))+raw
    chunks+=b'\0' if len(raw)%2 else b''
    path.write_bytes(b'RIFF'+struct.pack('<I',4+len(chunks))+b'WAVE'+chunks)
    return raw


def float_words(frames):
    return struct.pack('<%dd'%sum(map(len,frames)),
                       *(x for frame in frames for x in frame))


def source_samples(n,channels,rate):
    return [[.64*math.sin(2*math.pi*(399+171*ch)*frame/rate)+
             .051*math.sin(2*math.pi*1871*frame/rate+ch*.4)
             for ch in range(channels)] for frame in range(n)]


def dsf_bits(raw,nframes,nch,rate):
    demand(raw[:4]==b'DSD ' and raw[28:32]==b'fmt ' and raw[80:84]==b'data',
           'DSF physical headers absent')
    demand(struct.unpack_from('<Q',raw,12)[0]==len(raw),
           'DSF reported physical size mismatch')
    demand(struct.unpack_from('<Q',raw,32)[0]==52 and
           struct.unpack_from('<II',raw,52)==(nch,rate),
           'DSF reported rate/channels mismatch')
    exact=struct.unpack_from('<Q',raw,64)[0]
    demand(exact==nframes,'DSF header does not carry exact logical bit count')
    block=struct.unpack_from('<I',raw,72)[0]
    demand(block==4096 and raw[84:92]==struct.pack('<Q',len(raw)-80),
           'DSF block/header extent mismatch')
    blocks=(nframes+32767)//32768
    demand(len(raw)==92+blocks*4096*nch,'DSF padded block storage mismatch')
    bits=bytearray(nframes*nch)
    for f in range(nframes):
        byte=(f//8)%4096
        first=92+(f//32768)*nch*4096
        for c in range(nch):
            bits[f*nch+c]=(raw[first+c*4096+byte]>>(f%8))&1
    return bytes(bits)


def dff_bits(raw,nframes,nch,rate):
    demand(raw[:4]==b'FRM8' and raw[12:16]==b'DSD ',
           'DFF FRM8 header absent')
    frm8=struct.unpack_from('>Q',raw,4)[0]
    demand(frm8==len(raw)-12,'DFF parent physical extent wrong')
    cursor=16
    audio=None
    while cursor+12<=len(raw):
        tag=raw[cursor:cursor+4]
        sz=struct.unpack_from('>Q',raw,cursor+4)[0]
        start=cursor+12
        demand(start+sz<=len(raw),'DFF child chunk runs beyond end of file')
        if tag==b'DSD ':
            demand(audio is None,'DFF duplicate audio chunks')
            audio=raw[start:start+sz]
        cursor=start+sz+(sz%2)
    demand(cursor==len(raw) and audio is not None,'DFF physical chunks incomplete')
    expected_bytes=((nframes+7)//8)*nch
    demand(len(audio)==expected_bytes,'DFF stored padded bytes wrong')
    bits=bytearray(nframes*nch)
    for f in range(nframes):
        cluster=(f//8)*nch
        for c in range(nch):
            bits[f*nch+c]=(audio[cluster+c]>>(7-f%8))&1
    return bytes(bits)


class Suite:
    def __init__(self,sox,probe,results,tmp):
        self.sox=Path(sox).resolve();self.probe=Path(probe).resolve()
        self.results=Path(results);self.tmp=Path(tmp)
        self.gates={};self.commands=[];self.counts={};self.witness={}
        self.timings={};self.start=time.perf_counter()
        self.constants={hz:load_constants(SOURCE/f'src/resonator/dsd{hz//44100}/src/constants.h')
                        for hz in RATES}

    def record(self,name,delta=1):self.counts[name]=self.counts.get(name,0)+delta

    def command(self,args,*,input=None,outfile=None,expect=0,timeout=90,label=None,env=None):
        argv=[str(self.sox),*map(str,args)]
        before=time.perf_counter()
        if outfile:
            with open(outfile,'wb') as f:
                p=subprocess.run(argv,input=input,stdout=f,stderr=subprocess.PIPE,
                    env={**os.environ,**(env or {})},timeout=timeout)
        else:
            p=subprocess.run(argv,input=input,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,env={**os.environ,**(env or {})},timeout=timeout)
        self.commands.append(dict(label=label or str(args[-1]),
            exit=p.returncode,elapsed_seconds=round(time.perf_counter()-before,5),
            argv=list(map(str,args)),stderr_tail=p.stderr.decode(errors='replace')[-700:]))
        if expect==0:demand(p.returncode==0,f'{label or args}: exit {p.returncode}, stderr {p.stderr[-400:]!r}')
        elif expect=='fail':demand(p.returncode!=0,f'{label or args}: unexpectedly succeeded')
        else:demand(p.returncode==expect,f'{label or args}: exit {p.returncode} instead of {expect}')
        return p

    def cli(self,src,output,rate,*,clip=None,headroom=None,prepend=(),effects=(),report=None):
        args=['--precision','64',*prepend]
        if clip:args+=['--dsd-clip',clip]
        if headroom is not None:args+=['--headroom',str(headroom)]
        if report:args+=['--report',str(report)]
        args += [str(src),'-r',str(rate),str(output),*effects]
        return self.command(args,label=f'{rate}-{Path(output).suffix}',timeout=90)

    def probe_stream(self,frames,source_rate,nch,native_rate,*,
                     iblock=256,oblock=512,clip=True,attenuation=1.,ref=.5,
                     traces=True):
        payload=float_words(frames)
        prefix=str(self.tmp/'probe') if traces else '-'
        argv=[str(self.probe),'--encode',str(source_rate),str(native_rate),
              str(nch),str(iblock),str(oblock),str(int(clip)),
              repr(attenuation),repr(ref),prefix]
        cp=subprocess.run(argv,input=payload,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=90)
        demand(cp.returncode==0,f'private encoder failed {cp.returncode}: {cp.stderr[-600:]!r}')
        stats=json.loads(cp.stderr)
        expected=(len(frames)*native_rate*2+source_rate)//(source_rate*2)
        demand(len(cp.stdout)==expected*nch and
               int(stats['native_frames'])==expected and
               int(stats['source_frames'])==len(frames),
               'source-derived count or interleaved bitstream length failed')
        admission=[]
        if traces:
            for ch in range(nch):
                path=Path(prefix+f'.ch{ch}.f64')
                raw=path.read_bytes()
                demand(len(raw)==8*expected,f'channel {ch}: admission has wrong bit count')
                admission.append(struct.unpack(f'<{expected}d',raw))
                path.unlink()
        self.record('probe_streams')
        return cp.stdout,stats,admission

    def frozen_oracle(self,rate,stream,stats,admission,*,negative=False):
        nch=int(stats['channels']);nframes=int(stats['native_frames'])
        demand(stats['native_rate']==rate,'frozen oracle rate mismatch')
        for ch,xs in enumerate(admission):
            demand(len(xs)==nframes and all(math.isfinite(x) and abs(x)<=CERT_LIMIT for x in xs),
                   'actual post-clip input violated the frozen certificate')
            signs,entries,steps=oracle(self.constants[rate],xs)
            demand(signs==stream[ch::nch],
                   f'channel {ch}: production one-bit stream differs from independent recurrence')
            r=stats['record'][ch]
            demand(int(r['admitted'])==nframes and
                   int(r['recovery_entries'])==entries and
                   int(r['recovery_steps'])==steps and
                   r['profile']==f'encode.mastering.v3.dsd{rate//44100}' and
                   r['kernel']=='resonator',
                   f'channel {ch}: profile or recovery counter differs from frozen oracle')
            self.record('oracle_admitted_binary64_words',len(xs))
        self.record('independent_kernel_oracle_cases')
        if negative and nframes:
            corrupted=list(admission[0]);corrupted[nframes//2]=.5+2**-25
            try:
                demand(all(abs(x)<=CERT_LIMIT for x in corrupted),
                       'negative omitted-admission control')
            except AssertionError:self.record('omitted_admission_negative_controls')
            else:raise AssertionError('mutated out-of-certificate admission falsely passed')
            altered={k:(v[:] if isinstance(v,list) else v) for k,v in self.constants[rate].items()}
            altered['feedback'][0]+=0.01
            bad,_,_=oracle(altered,admission[0])
            demand(bad!=stream[0::nch],
                   'mutated frozen coefficient produced same decisions')
            self.record('coefficient_negative_controls')

    def container_check(self,path,rate,nch,expected,oracle_stream,report):
        raw=path.read_bytes()
        measured=dsf_bits(raw,expected,nch,rate) if path.suffix=='.dsf' else \
                 dff_bits(raw,expected,nch,rate)
        demand(measured==oracle_stream,
               f'{path.suffix}: physical packed bits differ from independent source-rate oracle')
        receipt=json.loads(report.read_text())
        demand(receipt['status']=='complete' and
               receipt['precision']['actual_route']=='native-binary64-encode' and
               receipt['precision']['actual_pcm_engine']=='ieee754.binary64' and
               receipt['precision']['runner_available'] and
               receipt['output']['domain']=='DSD_NATIVE' and
               int(receipt['output']['frames_written'])==expected and
               int(receipt['output']['native_completed_frames'])==expected,
               'successful container report falsely describes a different route/count')
        enc=receipt['processing']['encoder']
        demand(len(enc)==nch and all(
             int(e['committed_native_frames'])==expected and
             e['profile_id']==f'encode.mastering.v3.dsd{rate//44100}' and
             e['sdm_kernel_actual']=='resonator' and
             int(e['recovery_entries'])>=0 and int(e['recovery_steps'])>=0 and
             e['failure_code']==0 for e in enc),
             'selected production encoder or channel count/report wrong')
        self.record('container_bit_exact_oracle_comparisons')
        self.witness[str(path.name)]=dict(source_frames=int(enc[0]['source_frames']),
            native_bits=expected,channels=nch,rate=rate,bytes=len(raw),
            file_sha256=digest(raw),interleaved_bits_sha256=digest(measured),
            admitted_peak=[e['peak_modulator_input'] for e in enc],
            clipped=[int(e['clipped_interpolated_samples']) for e in enc],
            recovery=[[int(e['recovery_entries']),int(e['recovery_steps'])] for e in enc])
        return enc

    def core_and_container(self):
        p=subprocess.run([str(self.probe),'--selftest'],capture_output=True,timeout=25)
        demand(p.returncode==0 and b'PASS encode-probe assertions=' in p.stdout,
               'coordinator state machine selftest failed: '+repr(p.stderr))
        self.gates['direct_coordinator_backpressure_and_state']='PASS'
        self.record('coordinator_assertions',int(p.stdout.split(b'assertions=')[1].split()[0]))
        for rate,nch,src_hz,frames in (
             (RATES[0],1,44100,0),(RATES[0],1,44100,1),
             (RATES[0],1,48000,7),(RATES[0],2,44100,257),
             (RATES[1],1,44100,1),(RATES[1],2,44100,257),
             (RATES[1],6,48000,17)):
            samples=source_samples(frames,nch,src_hz)
            source=self.tmp/f'certified-{rate}-{nch}-{src_hz}-{frames}.wav'
            make_wav(source,samples,nch,src_hz)
            bits,stats,admitted=self.probe_stream(samples,src_hz,nch,rate,
               iblock=7,oblock=13)
            self.frozen_oracle(rate,bits,stats,admitted,negative=frames==257)
            for ext in ('.dsf','.dff'):
                out=self.tmp/f'{rate}-{nch}-{src_hz}-{frames}{ext}'
                report=self.tmp/f'{rate}-{nch}-{src_hz}-{frames}{ext}.json'
                opts=['--dsd-layout',CHANNEL_ROLES[nch]] if nch in CHANNEL_ROLES else []
                self.cli(source,out,rate,prepend=opts,report=report)
                self.container_check(out,rate,nch,int(stats['native_frames']),bits,report)
                if frames == 513:
                    out2=self.tmp/f'buffer4096-{rate}-{nch}{ext}'
                    rep2=self.tmp/f'buffer4096-{rate}-{nch}{ext}.json'
                    self.cli(source,out2,rate,prepend=['--buffer','4096'],report=rep2)
                    self.container_check(out2,rate,nch,int(stats['native_frames']),bits,rep2)
                    self.record('cli_4096_byte_buffer_cases')
            for ib,ob in [(1,1),(1,7),(7,1),(256,512),(111,9),(256,1),(255,511),(256,512)]:
                split,meta,_=self.probe_stream(samples,src_hz,nch,rate,
                    iblock=ib,oblock=ob,traces=False)
                demand(split==bits and int(meta['native_frames'])==int(stats['native_frames']),
                       f'input/output partition {ib}/{ob} changed one-bit decisions')
                self.record('partition_invariance_cases')
        self.gates['frozen_resonator_admitted_word_and_recovery_oracle']='PASS'
        self.gates['source_derived_count_and_split_invariance']='PASS'
        self.gates['DSF_DFF_packing_and_channel_roles']='PASS'

    def integer_and_f32(self):
        source_rate=44100
        base=[[(.21*math.sin((i+ch)*.5)) for ch in range(2)] for i in range(257)]
        for kind in ('f32','i8','i16','i24','i32'):
            precision=int(kind[1:]);kind_values=[];norm=[]
            for pair in base:
                if kind.startswith('i'):
                    lim=1<<(precision-1)
                    code=[max(-lim,min(lim-1,int(round(v*lim)))) for v in pair]
                    kind_values.append(code);norm.append([x/lim for x in code])
                else:
                    kind_values.append(pair)
                    norm.append([struct.unpack('<f',struct.pack('<f',x))[0] for x in pair])
            path=self.tmp/f'source-{kind}.wav'
            make_wav(path,kind_values,2,source_rate,kind)
            bits,stats,admission=self.probe_stream(norm,source_rate,2,RATES[0])
            self.frozen_oracle(RATES[0],bits,stats,admission)
            out=self.tmp/f'{kind}.dsf'; report=self.tmp/f'{kind}.json'
            self.cli(path,out,RATES[0],report=report)
            self.container_check(out,RATES[0],2,int(stats['native_frames']),bits,report)
            self.record('integer_or_f32_exact_ingress_cases')
        self.gates['integer_power_two_and_float32_ingress']='PASS'

    def gain_headroom_and_clip(self):
        src_hz=44100;native=RATES[0]
        samples=source_samples(173,2,src_hz)
        src=self.tmp/'gain-source.wav';make_wav(src,samples,2,src_hz)
        output=self.tmp/'gain-output.dsf';report=self.tmp/'gain-report.json'
        steps=('gain','-3','gain','4','gain','-1')
        opt=['-v','0.75']
        plan=json.loads(self.command(['--precision','64','--plan',*opt,src,
                         '-r',str(native),output,*steps],label='encode-gain-plan').stdout)
        factors=[s['gain_factor'] for s in plan['steps'] if s['name']=='gain']
        demand(plan['precision']['actual_route']=='native-binary64-encode' and
               len(factors)==3 and plan['inputs'][0]['volume']==.75,
               'native gain graph no longer retains ordered factors')
        processed=[]
        for frame in samples:
            new=[]
            for x in frame:
                x*=.75
                for f in factors:x*=f
                new.append(x)
            processed.append(new)
        bits,stats,adm=self.probe_stream(processed,src_hz,2,native)
        self.frozen_oracle(native,bits,stats,adm)
        self.cli(src,output,native,prepend=opt,effects=steps,report=report)
        self.container_check(output,native,2,int(stats['native_frames']),bits,report)
        self.gates['source_volume_and_ordered_gain']='PASS'
        strict=self.tmp/'fixed-strict.dff';fixed_report=self.tmp/'fixed-strict.json'
        self.cli(src,strict,native,clip='error',headroom=3.,report=fixed_report)
        att=10**(-3./20)
        bits2,stat2,adm2=self.probe_stream(samples,src_hz,2,native,
                                            clip=False,attenuation=att)
        self.frozen_oracle(native,bits2,stat2,adm2)
        self.container_check(strict,native,2,int(stat2['native_frames']),bits2,fixed_report)
        fixed=json.loads(fixed_report.read_text())
        demand(all(abs(e['headroom_applied_db']-3)<1e-9 and
               e['clip_ceiling_applied'] is None for e in fixed['processing']['encoder']),
               'fixed headroom or strict admission was not reported')
        self.gates['post_interpolation_fixed_headroom_admission']='PASS'
        # Overshooting a legal PCM word is expected to clip in WARN mode.
        hot=[[1.5 if i%3 else -1.5] for i in range(257)]
        hot_src=self.tmp/'hot.wav';make_wav(hot_src,hot,1,src_hz)
        hot_bits,hot_stats,hot_adm=self.probe_stream(hot,src_hz,1,native,clip=True)
        self.frozen_oracle(native,hot_bits,hot_stats,hot_adm,negative=True)
        demand(int(hot_stats['record'][0]['clipped'])>0 and
               max(map(abs,hot_adm[0]))==.5,
               'warn clipping was absent at exact resonator admission')
        hot_file=self.tmp/'hot.dsf';hot_rep=self.tmp/'hot.json'
        self.cli(hot_src,hot_file,native,clip='warn',report=hot_rep)
        hot_receipt=self.container_check(hot_file,native,1,
            int(hot_stats['native_frames']),hot_bits,hot_rep)
        demand(int(hot_receipt[0]['clipped_interpolated_samples'])==
               int(hot_stats['record'][0]['clipped']),
               'CLI clipped count differs from internal post-clip oracle')
        sentinel=self.tmp/'strict-overshoot.dsf';sentinel.write_bytes(b'KEEP-STRICT'*13)
        fail_rep=self.tmp/'strict-overshoot.json'
        self.command(['--precision','64','--dsd-clip','error',
            '--report',fail_rep,hot_src,'-r',str(native),sentinel],
            expect='fail',label='strict-overshoot')
        if fail_rep.exists():
            state=json.loads(fail_rep.read_text())
            demand(state['status']!='complete' and state['failure_reason'],
                   'strict native overload falsely marked successful')
        self.gates['warn_clip_and_strict_nonfinite_refusal']='PASS'

    def no_clobber_and_alias(self):
        src=self.tmp/'safety-source.wav'
        make_wav(src,source_samples(257,1,44100),1,44100)
        original=src.read_bytes();sentinel=b'PHASE06A-UNMODIFIED-INPUT-AND-REPORT'
        # Output symlink/hardlink -> source; inode identity must be checked
        # against the acquired descriptor before any writer can truncate it.
        for kind in ('hardlink','symlink'):
            dst=self.tmp/f'{kind}.dsf'
            if kind=='hardlink':os.link(src,dst)
            else:dst.symlink_to(src)
            self.command(['--precision','64',src,'-r','dsd64',dst],
                 expect='fail',label=f'aliased-{kind}')
            demand(src.read_bytes()==original,'DSF output damaged its source via inode alias')
            dst.unlink()
            self.record('descriptor_alias_refusals')
        dest=self.tmp/'report-alias.dsf';dest.write_bytes(sentinel)
        self.command(['--precision','64','--report',dest,src,'-r','dsd64',dest],
             expect='fail',label='output-report-selfalias')
        demand(dest.read_bytes()==sentinel,'report and output alias overwrote a sentinel')
        for path in ('report-audio-inode','source-report'):
            report=self.tmp/f'{path}.json'
            os.link(src,report)
            self.command(['--precision','64','--report',report,src,'-r','dsd64',
                self.tmp/f'{path}.dsf'],expect='fail',label=path)
            demand(src.read_bytes()==original,'hardlink report clobbered source')
            report.unlink()
        dest=self.tmp/'overwrite-decline.dsf';dest.write_bytes(sentinel)
        self.command(['--no-clobber','--precision','64',src,'-r','dsd64',dest],
             input=b'n\n',expect='fail',label='overwrite-decline')
        demand(dest.read_bytes()==sentinel,'declined overwrite damaged output')
        # Nonregular outputs must fail promptly; do not block opening a FIFO.
        if hasattr(os,'mkfifo'):
            fifo=self.tmp/'output.fifo';os.mkfifo(fifo)
            self.command(['--precision','64',src,'-r','dsd64','-t','dsf',fifo],
                expect='fail',timeout=5,label='named-output-fifo')
            demand(fifo.is_fifo(),'FIFO was replaced or unlinked')
        if Path('/dev/null').exists():
            self.command(['--precision','64',src,'-r','dsd64','-t','dsf','/dev/null'],
                expect='fail',timeout=5,label='device-output')
        dangling=self.tmp/'dangling.dsf';dangling.symlink_to(self.tmp/'missing-target')
        self.command(['--precision','64',src,'-r','dsd64',dangling],
            expect='fail',label='dangling-output-symlink')
        demand(dangling.is_symlink() and not (self.tmp/'missing-target').exists(),
               'dangling symlink target was created')
        self.gates['same_descriptor_no_clobber_and_alias_safety']='PASS'

    def stdout_dsd(self):
        src=self.tmp/'stdout-source.wav'
        make_wav(src,source_samples(7,2,44100),2,44100)
        for ext in ('dsf','dff'):
            args=['--precision','64',src,'-r','dsd64','-t',ext,'-']
            self.command(args,expect='fail',label=f'pipe-stdout-{ext}')
            out=self.tmp/f'stdout-regular.{ext}'
            with out.open('w+b') as f:
                p=subprocess.run([str(self.sox),*map(str,args)],
                    stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE,timeout=20)
            demand(p.returncode==0,f'seekable redirected stdout must succeed: {p.stderr!r}')
            n=7*64
            bits=dsf_bits(out.read_bytes(),n,2,RATES[0]) if ext=='dsf' else \
                dff_bits(out.read_bytes(),n,2,RATES[0])
            demand(len(bits)==n*2,'redirected stdout writes incorrect bit count')
            self.record('regular_stdout_outputs')
        self.gates['seekable_stdout_and_pipe_rejection']='PASS'

    def strict_refusals(self):
        src=self.tmp/'refusal-source.wav';make_wav(src,source_samples(7,1,44100),1,44100)
        for opt in (['--auto-headroom'],['--encode','encode.mastering.v2.dsd512'],
                    ['--dsd-clip','error']):
            if opt[-1]=='error':continue
            dst=self.tmp/f'refused-{len(opt)}-{opt[0][2:]}.dsf'
            destdata=b'REFUSAL-KEEP';dst.write_bytes(destdata)
            args=['--precision','64',*opt,src,'-r','dsd64',dst]
            plan=self.command(['--plan',*args],expect=('fail' if '--encode' in opt else 0),
                              label='strict64-plan-refusal')
            if plan.returncode==0:
                j=json.loads(plan.stdout)
                demand(j['precision']['actual_route']=='refused-before-output' and
                       not j['precision']['runner_available'],
                       'plan wrongly promises unsupported profile/AUTO')
            self.command(args,expect='fail',label='strict64-execution-refusal')
            demand(dst.read_bytes()==destdata,'unsupported graph clobbered output')
        # Prevent DSD -> DSD composition in this phase.
        valid=self.tmp/'baseline.dsf'
        self.command([src,'-r','dsd64',valid],label='ordinary-generate-native')
        target=self.tmp/'unsupported-composition.dff'
        self.command(['--precision','64',valid,'-r','dsd128',target],
                     expect='fail',label='dsd-dsd-composition')
        demand(not target.exists(),'strict64 composed DSD-to-DSD without 06B')
        # Ordinary path under --precision auto remains available.
        ordinary=self.tmp/'ordinary.dsf'
        self.command([src,'-r','dsd64',ordinary],label='ordinary-auto')
        demand(ordinary.exists(),'ordinary default DSD encode regressed')
        self.gates['AUTO_and_DSD_to_DSD_fail_closed']='PASS'
        self.gates['legacy_default_route_still_available']='PASS'

    def nonfinite_and_report_failure(self):
        for kind in ('nan','positive_inf','negative_inf'):
            vals=source_samples(513,2,44100)
            vals[289][1]={'nan':math.nan,'positive_inf':math.inf,
                          'negative_inf':-math.inf}[kind]
            src=self.tmp/f'{kind}.wav';make_wav(src,vals,2,44100)
            out=self.tmp/f'{kind}.dsf';report=self.tmp/f'{kind}.json'
            self.command(['--precision','64','--report',report,src,'-r','dsd64',out],
                         expect='fail',label=f'nonfinite-{kind}')
            if report.exists():
                j=json.loads(report.read_text())
                demand(j['status']!='complete' and j['failure_reason'],
                       f'nonfinite {kind} falsely reported complete')
            self.record('nonfinite_reader_or_composite_refusals')
        self.gates['nonfinite_fail_closed_and_truthful_report']='PASS'

    def flac_ingress(self):
        # The native FLAC reader is available only in a built-in FLAC build.
        # A working plugin codec can still write/read FLAC via legacy PCM.
        values=[[int(12000*math.sin(.2*i+ch)) for ch in range(2)] for i in range(113)]
        src=self.tmp/'flac-input.wav';make_wav(src,values,2,44100,'i16')
        flac=self.tmp/'integer.flac'
        check=subprocess.run([str(self.sox),'-D',str(src),str(flac)],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if check.returncode!=0:
            self.gates['builtin_integer_FLAC_ingress']='NOT_RUN: FLAC codec not built/available'
            return
        flac_probe=self.probe.with_name('pcm64_flac_probe')
        demand(flac_probe.is_file(),'actual FLAC handler linkage probe missing')
        capability=subprocess.run([str(flac_probe),'capabilities'],
                         capture_output=True,text=True,timeout=30)
        demand(capability.returncode==0,
               f'FLAC handler capability probe failed: {capability.stderr}')
        lines=[line.split('=',1) for line in capability.stdout.splitlines()]
        demand(len(lines)==2 and all(len(x)==2 for x in lines) and
               set(k for k,_ in lines)=={'linkage','native_dsp'},
               f'unexpected FLAC capability receipt: {capability.stdout!r}')
        linkage=dict(lines)['linkage']
        demand(linkage in ('builtin','plugin','absent'),
               f'unknown FLAC handler linkage: {linkage!r}')
        if linkage!='builtin':
            # Verify a plugin cannot be mistaken for native binary64 ingress.
            if linkage=='plugin':
                plan=json.loads(self.command(['--precision','64','--plan',flac,
                    '-r','dsd64',self.tmp/'plugin-not-native.dsf'],
                    label='plugin-flac-native-plan').stdout)
                demand(not plan['precision']['runner_available'] and
                       plan['precision']['actual_route']=='refused-before-output',
                       'FLAC plugin incorrectly admitted to the native DSD runner')
                self.gates['plugin_FLAC_native_route_refusal']='PASS'
            self.gates['builtin_integer_FLAC_ingress']=(
                f'NOT_RUN: actual FLAC handler linkage={linkage}; native requires built-in')
            return
        # Both DSD clocks and writer formats must preserve the independent
        # integer WAV reference, channel order and source-derived bit counts.
        for rate in RATES:
            expected=113*(rate//44100)
            for ext in ('dsf','dff'):
                wav=self.tmp/f'wav-{rate}.{ext}'
                dst=self.tmp/f'flac-{rate}.{ext}'
                wrep=self.tmp/f'wav-{rate}.{ext}.json'
                rep=self.tmp/f'flac-{rate}.{ext}.json'
                self.cli(src,wav,rate,report=wrep)
                self.cli(flac,dst,rate,report=rep)
                parse=dsf_bits if ext=='dsf' else dff_bits
                demand(parse(wav.read_bytes(),expected,2,rate)==
                       parse(dst.read_bytes(),expected,2,rate),
                       f'{rate} {ext}: FLAC integer bits differ from exact WAV source')
                j=json.loads(rep.read_text())
                demand(j['precision']['actual_route']=='native-binary64-encode' and
                       j['source'][0]['container']=='flac' and
                       int(j['output']['frames_written'])==expected and
                       int(j['output']['native_completed_frames'])==expected and
                       len(j['processing']['encoder'])==2 and
                       all(int(c['source_frames'])==113 and
                           int(c['committed_native_frames'])==expected
                           for c in j['processing']['encoder']),
                       f'{rate} {ext}: wrong FLAC route, channel order or bit count')
                self.record('FLAC_integer_bits_compared',expected*2)
                self.record('FLAC_integer_container_cases')
        self.gates['builtin_integer_FLAC_ingress']='PASS'

    def receipt(self,status):
        head=subprocess.run(['git','-C',str(SOURCE),'rev-parse','HEAD'],
             capture_output=True,text=True)
        files=['src/dsd_f64.c','src/dsd_plan.c','src/pcmdsd.c','src/formats.c',
               'src/dsf.c','src/dsdiff.c','tests/pcm64/encode.py',
               'tests/pcm64/encode_probe.c','src/resonator/dsd64/src/dsd64_iq.c',
               'src/resonator/dsd128/src/dsd128_iq.c']
        inputs={f:file_digest(SOURCE/f) for f in files if (SOURCE/f).exists()}
        return dict(suite='encode',status=status,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_git_commit=head.stdout.strip() if head.returncode==0 else None,
            source_and_binary_sha256={**inputs,'src/sox':file_digest(self.sox),
                                      'test/pcm64_encode_probe':file_digest(self.probe)},
            executed_binary_sha256={str(self.sox):file_digest(self.sox),
                                    str(self.probe):file_digest(self.probe)},
            gates=self.gates,gate_execution=self.gates,counts=self.counts,
            duration_seconds=round(time.perf_counter()-self.start,3),
            witnesses=self.witness,commands=self.commands)


def main(sox,probe,results):
    results=Path(results).resolve();results.mkdir(parents=True,exist_ok=True)
    outfile=results/'encode.json'
    outfile.unlink(missing_ok=True)
    sox=Path(sox).resolve();probe=Path(probe).resolve()
    with tempfile.TemporaryDirectory(prefix='encode-',dir=results) as d:
        suite=Suite(sox,probe,results,d)
        try:
            # First assert the real execution graph is enabled. A disabled
            # arithmetic configuration should test its truthful refusal and
            # state its unrun numerical gates explicitly.
            src=suite.tmp/'arithmetic-gate.wav'
            make_wav(src,source_samples(1,1,44100),1,44100)
            plan=json.loads(suite.command(['--precision','64','--plan',src,
                '-r','dsd64',suite.tmp/'arithmetic-gate.dsf'],
                label='arithmetic-gate-plan').stdout)
            if not plan['precision']['runner_available']:
                demand(plan['precision']['actual_route']=='refused-before-output',
                       'arithmetic-disabled planner promised a hidden runner')
                dst=suite.tmp/'disabled-output.dsf';dst.write_bytes(b'KEEP')
                suite.command(['--precision','64',src,'-r','dsd64',dst],
                              expect='fail',label='native-disabled-refusal')
                demand(dst.read_bytes()==b'KEEP','disabled native truncates output')
                suite.gates['disabled_native_encode_refusal']='PASS'
                suite.gates['certified_encode']='NOT_RUN: compiled arithmetic backend unavailable'
            else:
                suite.core_and_container()
                suite.integer_and_f32()
                suite.gain_headroom_and_clip()
                suite.no_clobber_and_alias()
                suite.stdout_dsd()
                suite.strict_refusals()
                suite.nonfinite_and_report_failure()
                suite.flac_ingress()
            state='PASS_WITH_NOT_RUN' if any(str(x).startswith('NOT_RUN')
                             for x in suite.gates.values()) else 'PASS'
            record=suite.receipt(state)
        except BaseException as exc:
            record=suite.receipt('FAIL')
            record['error']=f'{type(exc).__name__}: {exc}'
            outfile.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
            print('FAIL encode:',record['error'],file=sys.stderr)
            return 1
    outfile.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(f'{record["status"]} encode: {sum(suite.counts.values())} measured assertions, '
          f'{len(record["gates"])} gates, {record["duration_seconds"]} s')
    return 0

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    sys.exit(main(a.sox,a.probe,a.results))
