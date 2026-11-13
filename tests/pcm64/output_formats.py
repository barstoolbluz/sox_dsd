#!/usr/bin/env python3
"""Phase 05A D-01..D-04: output negotiation and ordered PCM graph plans.

Compares *executed* headers (SoX's separate input probe and independently
parsed WAV bytes) with the precommit plan. No mock of set_output_format().
Only successful legacy codec pairs enter the plan-versus-output matrix.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import random
import re
import struct
import subprocess
import sys
from pathlib import Path
from binary_receipts import safe_git_head, native_dsp_compiled

SOURCE = Path(__file__).resolve().parents[2]
ENCODING_BY_NAME = {
    'Signed Integer PCM': 1,
    'Unsigned Integer PCM': 2,
    'Floating Point PCM': 3,
    'FLAC': 5,
    'u-law': 9,
    'A-law': 10,
}


def require(ok, detail):
    if not ok:
        raise AssertionError(detail)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wav(path, samples, bits=16, encoding=1, channels=1, mask=None):
    width=bits//8
    require(len(samples)%channels==0, 'non-whole frames')
    payload=b''
    for value in samples:
        if encoding==3:
            payload+=struct.pack('<f' if bits==32 else '<d',value)
        elif bits==8:
            payload+=int(value+128).to_bytes(1,'little')
        else:
            payload+=int(value).to_bytes(width,'little',signed=True)
    fmt=struct.pack('<HHIIHH',0xfffe if mask is not None else encoding,
                    channels,48000,48000*channels*width,channels*width,bits)
    if mask is not None:
        fmt+=struct.pack('<HHI',22,bits,mask)
        fmt+=struct.pack('<H',encoding)+bytes.fromhex('000000001000800000aa00389b71')
    elif encoding==3:
        fmt+=struct.pack('<H',0)
    body=b'fmt '+struct.pack('<I',len(fmt))+fmt
    if encoding==3:
        body+=b'fact'+struct.pack('<II',4,len(samples)//channels)
    body+=b'data'+struct.pack('<I',len(payload))+payload+(b'\0' if len(payload)&1 else b'')
    body=b'WAVE'+body
    path.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)


def wav_contents(path):
    data=path.read_bytes()
    require(data[:4] in (b'RIFF',b'RIFX') and data[8:12]==b'WAVE',f'not RIFF/RIFX {path}')
    endian='<' if data[:4]==b'RIFF' else '>'
    offset=12; fmt=None; payload=None
    while offset+8<=len(data):
        tag=data[offset:offset+4]
        length=struct.unpack_from(endian+'I',data,offset+4)[0]
        offset+=8
        require(length<=len(data)-offset,f'truncated {path}')
        part=data[offset:offset+length]
        if tag==b'fmt ':
            require(len(part)>=16, 'short fmt')
            codec,channels,rate,_,_,bits=struct.unpack_from(endian+'HHIIHH',part)
            mask=None
            if codec==0xfffe:
                require(len(part)>=40, 'short extensible fmt')
                mask=struct.unpack_from(endian+'I',part,20)[0]
                actual=struct.unpack_from(endian+'H',part,24)[0]
            else: actual=codec
            fmt=(codec,actual,channels,rate,bits,mask)
        if tag==b'data': payload=part
        offset+=length+(length&1)
    require(fmt is not None and payload is not None,f'no WAV samples {path}')
    require(len(payload)%(fmt[2]*fmt[4]//8)==0,'incomplete sample frame')
    return data[:4],fmt,payload


class Test:
    def __init__(self, binary, results):
        self.binary=binary.resolve()
        self.results=results.resolve()
        self.root=self.results/'fixtures'/'output-formats'
        self.root.mkdir(parents=True,exist_ok=True)
        self.counters={};self.gates={};self.skips={}
        self.commands=0

    def run(self,args,expect=True):
        result=subprocess.run([str(self.binary),*map(str,args)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        self.commands+=1
        if expect:
            require(result.returncode==0,
                f'command failed {args}: {result.stderr.decode(errors="replace")[-1200:]}')
        return result

    def count(self,name,count=1):
        self.counters[name]=self.counters.get(name,0)+count

    def plan(self,args):
        r=self.run(['--plan',*args]);return json.loads(r.stdout)['output']

    def matrix(self):
        r=random.Random(0x05A20261113)
        inputs=[]
        for bits in (16,24,32):
            limit=1<<(bits-1)
            samples=[-limit,-limit+1,-2000,-1,0,1,2000,limit-1]
            samples +=[r.randrange(-limit,limit) for _ in range(24)]
            src=self.root/f'signed{bits}.wav'
            wav(src,samples,bits)
            inputs.append(src)
        for bits in (32,64):
            samples=[0.,-0.,-0.75,0.75,1/(1<<23),-1/(1<<25)]
            samples +=[r.random()*1.6-0.8 for _ in range(28)]
            src=self.root/f'float{bits}.wav'
            wav(src,samples,bits,3)
            inputs.append(src)
        formats=('wav','aiff','au','sox','flac')
        options=((),('-b','8'),('-b','16'),('-b','24'),('-b','32'),
                 ('-b','64'),('-e','signed-integer'),
                 ('-e','floating-point','-b','16'),
                 ('-e','floating-point','-b','32'),
                 ('-e','unsigned-integer','-b','8'),
                 ('-e','unsigned-integer','-b','16'))
        for src in inputs:
            for typ in formats:
                for j,opts in enumerate(options):
                    target=self.root/f'matrix-{src.stem}-{typ}-{j}.{typ}'
                    args=[src,*opts,target]
                    executed=self.run(args,expect=False)
                    if executed.returncode:
                        self.count('unsupported_legacy_pairs')
                        if typ=='flac':
                            self.skips.setdefault('flac_writer','FLAC output handler unavailable or refused requested format')
                        continue
                    declared=self.plan(args)
                    enc_result=self.run(['--i','-e',target]).stdout.decode().strip()
                    bits_result=self.run(['--i','-b',target]).stdout.decode().strip()
                    require(enc_result in ENCODING_BY_NAME,
                            f'unknown executed encoding {target}: {enc_result}')
                    expected=(ENCODING_BY_NAME[enc_result],int(bits_result))
                    actual=(declared['encoding'],declared['bits_per_sample'])
                    require(actual==expected,
                        f'{src.name} {typ} {opts}: plan={actual} vs writer={expected}')
                    self.count('plan_execution_pairs')
                    if typ=='flac':self.count('flac_plan_execution_pairs')
        require(self.counters.get('plan_execution_pairs',0)>=150,
                'matrix missing successful real-codec pairs')
        self.gates['codec_output_selection_matches_execution']='PASS'
        self.gates['FLAC_codec_output_selection']=('PASS' if self.counters.get('flac_plan_execution_pairs',0)>=15
            else 'NOT_RUN: FLAC output handler not available in this build')
        return inputs

    def strict64(self,source):
        dst=self.root/'signed16-to-float64.wav'
        args=['--precision','64',source,'-b','64',dst]
        output=self.plan(['--precision','64',source,'-b','64',dst])
        require((output['encoding'],output['bits_per_sample'])==(3,64),'bad strict64 plan')
        self.run(args)
        _,fmt,raw=wav_contents(dst)
        require(fmt[1]==3 and fmt[4]==64,'-b64 failed to select FLOAT64 native writer')
        original=[-32768,-32767,-2000,-1,0,1,2000,32767]
        expected=[struct.pack('<d',v/32768.) for v in original]
        require([raw[i:i+8] for i in range(0,8*len(original),8)]==expected,
                'strict64 signed16 normalization lost precision')
        gain_dest=self.root/'signed16-gain-to-float64.wav'
        self.run(['--precision','64',source,'-b','64',gain_dest,'gain','-6'])
        _,gf,gd=wav_contents(gain_dest)
        require(gf[1]==3 and gf[4]==64 and len(gd)==len(raw),
                'strict64 gain silently narrowed output')
        got=struct.unpack('<'+str(len(gd)//8)+'d',gd)
        require(any(abs(a-b)>1e-10 for a,b in zip(got,struct.unpack('<'+str(len(raw)//8)+'d',raw))),
                'gain did not modify samples')
        self.count('float64_numeric_words',len(raw)//8)
        self.gates['strict64_width_and_gain']='PASS'
        failures=[('-e','floating-point','-b','16'),
                  ('-e','unsigned-integer','-b','16'),
                  ('-e','signed-integer','-b','64')]
        sentinel=b'PRESERVE PRECOMMIT WAV DESTINATION '\
                 b'\x80\x00\x01\xff' * 9
        for j,opts in enumerate(failures):
            target=self.root/f'strict64-refusal-{j}.wav'
            target.write_bytes(sentinel)
            args=['--precision','64',source,*opts,target]
            p=self.run(['--precision','64','--plan',source,*opts,target])
            info=json.loads(p.stdout)['precision']
            require(info['actual_route']=='refused-before-output',
                    f'unsupported strict64 request not refused in plan: {opts}: {info}')
            result=self.run(args,expect=False)
            require(result.returncode!=0 and target.read_bytes()==sentinel,
                    f'unsupported strict64 options modified sentinel: {opts}')
            self.count('precommit_sentinels')
        self.gates['strict64_unsupported_options_precommit_refused']='PASS'

    def layout(self):
        for n in (4,6,8):
            vals=[((i*3499)%60000)-30000 for i in range(n*37)]
            src=self.root/f'unknown-{n}ch.wav'
            wav(src,vals,16,1,n)
            target=self.root/f'unknown-{n}ch-native.wav'
            self.run(['--precision','64',src,'-e','signed-integer','-b','24',target])
            _,fmt,raw=wav_contents(target)
            require(fmt[0]==0xfffe and fmt[5]==0 and fmt[2]==n,
                    f'{n}-channel unknown roles were invented: {fmt}')
            codes=[int.from_bytes(raw[i:i+3],'little',signed=True) for i in range(0,len(raw),3)]
            require(codes==[v*256 for v in vals],f'{n}-channel samples reordered or changed')
            legacy=self.root/f'unknown-{n}ch-legacy.wav'
            self.run([src,'-e','signed-integer','-b','24',legacy])
            _,old_fmt,_=wav_contents(legacy)
            require(old_fmt[5]=={4:0x33,6:0x3f,8:0x63f}[n],
                    f'legacy {n}-channel mask unexpectedly changed')
            float_source=self.root/f'unknown-f64-{n}ch.wav'
            wav(float_source,[v/32768. for v in vals],64,3,n)
            float_target=self.root/f'unknown-f64-{n}ch-native.wav'
            self.run(['--precision','64',float_source,'-e','signed-integer',
                      '-b','24',float_target])
            _,ff,fd=wav_contents(float_target)
            require(ff[5]==0 and ff[0]==0xfffe and len(fd)==n*37*3,
                    f'unknown FLOAT64 {n}-channel source acquired mask: {ff}')
            self.count('unknown_role_frame_cases',37*2)
            self.count('unchanged_legacy_masks')
        known={4:0x33,6:0x3f,8:0x63f}
        for n,mask in known.items():
            src=self.root/f'known-{n}ch.wav'
            vals=[((i*1237)%55000)-27500 for i in range(n*19)]
            wav(src,vals,16,1,n,mask)
            target=self.root/f'known-{n}ch-native.wav'
            self.run(['--precision','64',src,'-e','signed-integer','-b','24',target])
            _,fmt,payload=wav_contents(target)
            require(fmt[5]==mask and fmt[2]==n, f'known {n}-channel roles lost: {fmt}')
            require([int.from_bytes(payload[i:i+3],'little',signed=True)
                     for i in range(0,len(payload),3)]==[v*256 for v in vals],
                    'known layout changed sample order')
            self.count('known_mask_cases')
            if n==6:
                shuffled=self.root/'known-six-remix.wav'
                self.run(['--precision','64',src,'-e','signed-integer','-b','24',
                          shuffled,'remix','2','1','3','4','5','6'])
                _,reordered,rd=wav_contents(shuffled)
                # The historical D-02 fixture assumed that P04 canonical
                # speaker sorting would undo the user's remix.  The Phase 05A
                # return explicitly requires the audio samples to match the
                # ordinary executed SoX remix, not that obsolete expectation.
                legacy_remix=self.root/'known-six-remix-legacy.wav'
                self.run([src,'-e','signed-integer','-b','24',
                          legacy_remix,'remix','2','1','3','4','5','6'])
                _,legacy_fmt,legacy_payload=wav_contents(legacy_remix)
                require(reordered[5]==mask and reordered[2]==n and
                        legacy_fmt[2]==n and rd==legacy_payload and rd!=payload,
                        'known-role remix did not reorder samples as legacy SoX does')
                self.count('known_role_permutation_cases')
                sentinel=self.root/'known-mask-wavpcm-sentinel.wav'
                sentinel.write_bytes(b'PRESERVE KNOWN LAYOUT' * 7)
                blocked=self.run(['--precision','64',src,'-t','wavpcm',
                                  '-e','signed-integer','-b','24',sentinel],expect=False)
                require(blocked.returncode!=0 and sentinel.read_bytes()==b'PRESERVE KNOWN LAYOUT'*7,
                        'classic WAV silently discarded known mask or modified sentinel')
                self.count('precommit_sentinels')
        self.gates['unknown_layout_zero_mask_and_legacy_unchanged']='PASS'
        self.gates['known_masks_and_role_permutation']='PASS'

    def endianness_and_subtype(self):
        for n in (1,6):
            vals=[i/1024. for i in range(-10,10)]
            samples=[vals[i%len(vals)] for i in range(n*16)]
            src=self.root/f'byte-order-{n}ch.wav'
            wav(src,samples,64,3,n)
            for big in (False,True):
                for subtype in ('wav','wavpcm'):
                    target=self.root/f'byte-order-{n}ch-{big}-{subtype}.wav'
                    args=['--precision','64',src,*(['-B'] if big else []),
                          '-t',subtype,'-e','floating-point','-b','64',target]
                    self.run(args)
                    magic,fmt,payload=wav_contents(target)
                    require(magic==(b'RIFX' if big else b'RIFF'),
                            f'output byte order ignored: {args}')
                    require(fmt[0]==3 and fmt[1]==3 and fmt[4]==64,
                            'classic float tag or sample precision incorrect')
                    actual=struct.unpack(('>' if big else '<')+str(len(samples))+'d',payload)
                    require(tuple(actual)==tuple(samples),'FLOAT64 bytes incorrect for selected endian')
                    # A float source has no layout: classic subtype stays
                    # classic even when many channels are present.
                    self.count('float64_endian_and_subtype_cases')
            signed=self.root/f'byte-order-signed-{n}ch.wav'
            codes=[((i*491)%50000)-25000 for i in range(n*11)]
            wav(signed,codes,16,1,n)
            for big in (False,True):
                for subtype in ('wav','wavpcm'):
                    target=self.root/f'byte-order-signed-{n}ch-{big}-{subtype}.wav'
                    opts=['--precision','64',signed,*(['-B'] if big else []),
                          '-t',subtype,'-e','signed-integer','-b','24',target]
                    plan=self.plan(opts)
                    require((plan['encoding'],plan['bits_per_sample'])==(1,24),
                            'plan lost selected signed24 endpoint')
                    self.run(opts)
                    magic,fmt,data=wav_contents(target)
                    require(magic==(b'RIFX' if big else b'RIFF') and fmt[4]==24,
                            'wrong byte-order tag or bit depth')
                    require(fmt[0]==(1 if subtype=='wavpcm' else 0xfffe),
                            'wavpcm classic subtype ignored, or default WAV changed')
                    order='big' if big else 'little'
                    actual=[int.from_bytes(data[i:i+3],order,signed=True)
                            for i in range(0,len(data),3)]
                    require(actual==[v*256 for v in codes],
                            'big-endian signed24 sample serialization incorrect')
                    self.count('integer_endian_and_subtype_cases')
        self.gates['endian_rifx_riff_and_classic_subtype']='PASS'

    def auto32(self,source):
        for extension in ('wav','aiff','au','sox'):
            opts=['-e','signed-integer','-b','24']
            legacy=self.root/f'compat-ordinary.{extension}'
            self.run([source,*opts,legacy])
            reference=legacy.read_bytes()
            for policy in ('auto','32'):
                target=self.root/f'compat-{policy}.{extension}'
                self.run(['--precision',policy,source,*opts,target])
                require(target.read_bytes()==reference,
                        f'{policy} changed ordinary {extension} output bytes')
                self.count('legacy_byte_compat_cases')
        self.gates['auto32_and_legacy_output_bytes']='PASS'

    def implicit_endpoints(self):
        """Compare ordered plan steps against SoX's real -V3 effects chain.

        Input is a 48 kHz stereo WAV. Forced mono/rate formats, requested
        fallbacks, downmix/upmix and explicit effects are all ordinary PCM.
        """
        src=self.root/'implicit-48000-stereo.wav'
        wav(src,[((i*97)%32000)-16000 for i in range(2*7200)],16,1,2)
        # case: label, extension, output options, user effects, expected
        # ordered conversion names, final rate/channels, requested rate.
        cases=(
            ('cdr-selected-rate','cdr',(),(),('rate',),44100,2,None),
            ('wve-selected-rate-mono','wve',(),(),('channels','rate'),8000,1,None),
            ('prc-selected-rate-mono','prc',(),(),('channels','rate'),8000,1,None),
            ('lpc10-selected-rate-mono','lpc10',(),(),('channels','rate'),8000,1,None),
            ('hcom-selected-rate-mono','hcom',(),(),('channels','rate'),22050,1,None),
            ('gsm-explicit-rate-overridden','gsm',('-r','44100'),(),('rate',),8000,2,44100),
            ('wav-downmix-before-rate','wav',('-r','8000','-c','1'),(),('channels','rate'),8000,1,8000),
            ('wav-upmix-after-rate','wav',('-r','8000','-c','4'),(),('rate','channels'),8000,4,8000),
            ('wav-no-change','wav',(),(),(),48000,2,None),
            ('wav-explicit-same-endpoints','wav',('-r','48000','-c','2'),(),(),48000,2,48000),
            ('wav-only-rate','wav',('-r','44100'),(),('rate',),44100,2,44100),
            ('wav-only-downmix','wav',('-c','1'),(),('channels',),48000,1,None),
            ('wav-user-rate','wav',(),('rate','8000'),('rate',),8000,2,None),
            ('wav-user-channels','wav',(),('channels','1'),('channels',),48000,1,None),
            ('wav-user-channels-then-rate','wav',(),('channels','1','rate','8000'),('channels','rate'),8000,1,None),
            ('wav-user-rate-then-channels','wav',(),('rate','8000','channels','1'),('rate','channels'),8000,1,None),
            ('wav-gain-then-auto','wav',('-r','8000','-c','1'),('gain','-6'),('channels','rate'),8000,1,8000),
            ('wav-auto-before-user-dither','wav',('-r','8000','-c','1'),('dither',),('channels','rate'),8000,1,8000),
        )
        trace=re.compile(r'effects chain:\s+(\w+)\s+([0-9.]+)Hz\s+(\d+) channels')
        for name,typ,options,effects,expected,rate,channels,requested in cases:
            dst=self.root/f'implicit-{name}.{typ}'
            args=[src,*options,dst,*effects]
            planning=self.run(['--plan',*args])
            declared=json.loads(planning.stdout)
            execution=self.run(['-V3',*args])
            actual_trace=[(n,float(r),int(c)) for n,r,c in trace.findall(
                execution.stderr.decode(errors='replace'))]
            require(actual_trace and actual_trace[0][0]=='input' and
                    actual_trace[-1][0]=='output',
                    f'{name}: missing actual input/output effects chain: {execution.stderr[-1200:]}')
            actual=[]
            previous=actual_trace[0][1:]
            for n,out_rate,out_channels in actual_trace[1:]:
                if n in ('rate','channels'):
                    actual.append((n,*previous,out_rate,out_channels))
                previous=(out_rate,out_channels)
            planned=[]
            for step in declared['steps']:
                if step['name'] in ('rate','channels','implicit_pcm_rate','implicit_pcm_channels'):
                    n=step['name'].replace('implicit_pcm_','')
                    planned.append((n,step['rate_in_hz'],step['channels_in'],
                                    step['rate_out_hz'],step['channels_out']))
            require(tuple(s[0] for s in actual)==expected,
                    f'{name}: unexpected actual chain {actual}; expected {expected}')
            require(planned==actual,
                    f'{name}: planned conversions {planned} != executed chain {actual}')
            require((declared['output']['rate_hz'],declared['output']['channels'])==
                    (rate,channels)==actual_trace[-1][1:],
                    f'{name}: incorrect final endpoint vs output effect')
            require(declared['output']['requested_rate_hz']==requested,
                    f'{name}: requested_rate_hz not preserved: {declared["output"]}')
            if 'dither' in effects:
                dither_step=next((i for i,step in enumerate(declared['steps'])
                    if step['name']=='dither'),None)
                require(dither_step is not None and all(i<dither_step for i,step in
                    enumerate(declared['steps']) if step['name'].startswith('implicit_pcm_')),
                    f'{name}: automatic endpoint step placed after explicit dither')
            if effects and effects[0] in ('rate','channels'):
                require(sum(not step['implicit'] for step in declared['steps']
                    if step['name'] in ('rate','channels'))>=1,
                    f'{name}: explicit conversion misidentified as automatic')
            self.count('implicit_plan_execution_pairs')
            self.count('implicit_plan_steps',len(planned))
        self.gates['ordered_automatic_PCM_endpoints_match_executed_chain']='PASS'

    def cvsd_writer_endpoints(self):
        """The CVSD/DVMS writer chooses bitrate before setting PCM rate to 8k.

        Compare the metadata-only plan to the actual -V3 processing chain;
        also require byte identity among omitted/auto/32 precision routes.
        """
        traces=re.compile(r'effects chain:\s+(\w+)\s+([0-9.]+)Hz\s+(\d+) channels')
        rate_report=re.compile(r'cvsd: bit rate (\d+)bit/s')
        for in_channels in (1,2):
            src=self.root/f'cvsd-source-{in_channels}ch.wav'
            samples=[((i*1477)%55000)-27500 for i in range(7200*in_channels)]
            wav(src,samples,16,1,in_channels)
            for typ in ('cvs','cvsd','dvms','vms'):
                for requested in (None,16000,32000):
                    options=['-r',str(requested)] if requested else []
                    target=self.root/f'cvsd-{in_channels}ch-{typ}-{requested}.{typ}'
                    args=[src,*options,target]
                    sentinel=b'PRESERVE CVSD PLAN TARGET' * 3
                    target.write_bytes(sentinel)
                    plan=json.loads(self.run(['--plan',*args]).stdout)
                    require(target.read_bytes()==sentinel,
                            f'{typ}: --plan modified existing destination')
                    target.unlink()
                    self.run(['--plan',*args])
                    require(not target.exists(),f'{typ}: --plan created destination')
                    self.count('cvsd_plan_no_mutation_cases')
                    declared=plan['output']
                    require((declared['rate_hz'],declared['channels'],
                             declared['encoding'],declared['bits_per_sample'])==
                            (8000,1,28,1),
                            f'{typ}: wrong effective CVSD endpoint {declared}')
                    require(declared['requested_rate_hz']==requested,
                            f'{typ}: requested rate overwritten: {declared}')
                    expected_names=(('channels','rate') if in_channels==2
                                    else ('rate',))
                    expected_steps=[]
                    rate=48000;channels=in_channels
                    if in_channels==2:
                        expected_steps.append(('channels',48000,2,48000,1))
                        channels=1
                    expected_steps.append(('rate',rate,channels,8000,1))
                    planned=[(step['name'].replace('implicit_pcm_',''),
                              step['rate_in_hz'],step['channels_in'],
                              step['rate_out_hz'],step['channels_out'])
                             for step in plan['steps']
                             if step['name'].startswith('implicit_pcm_')]
                    require(tuple(s[0] for s in planned)==expected_names and
                            planned==expected_steps,
                            f'{typ}: wrong planned auto steps {planned}, expected {expected_steps}')
                    execution=self.run(['-R','-V3',*args])
                    detail=execution.stderr.decode(errors='replace')
                    chain=[(name,float(hz),int(ch)) for name,hz,ch
                           in traces.findall(detail)]
                    require(chain and chain[0][0]=='input' and
                            chain[-1]==('output',8000.,1),
                            f'{typ}: missing executed chain {detail[-1500:]}')
                    actual=[];before=chain[0][1:]
                    for name,hz,ch in chain[1:]:
                        if name in ('channels','rate'):
                            actual.append((name,*before,hz,ch))
                        before=(hz,ch)
                    require(actual==planned,
                            f'{typ}: planned {planned}, executed {actual}')
                    bitrates=rate_report.findall(detail)
                    expected_bitrate=16000 if requested==16000 else 32000
                    require(bitrates and int(bitrates[-1])==expected_bitrate,
                            f'{typ}: CVSD bitrate selection changed: {detail[-1500:]}')
                    baseline_bytes=target.read_bytes()
                    for precision in ('auto','32'):
                        target.unlink()
                        self.run(['-R','--precision',precision,*args])
                        require(target.read_bytes()==baseline_bytes,
                                f'{typ}: {precision} changed CVSD/DVMS output bytes')
                        self.count('cvsd_auto32_byte_compat_cases')
                    self.count('cvsd_plan_execution_pairs')
                    self.count(f'cvsd_{expected_bitrate}_bps_cases')
        # CVU shares CVSD encoding, but does NOT use the CVSD/DVMS writer.
        cvu=self.root/'cvsd-control-unfiltered.cvu'
        src=self.root/'cvsd-source-1ch.wav'
        cvu_plan=self.plan([src,'-r','16000','-t','cvu',cvu])
        require((cvu_plan['rate_hz'],cvu_plan['channels'])==(16000,1),
                'unrelated CVU writer erroneously forced to 8 kHz')
        self.gates['CVSD_DVMS_writer_endpoint_plans_and_bitrate_selection']='PASS'
        self.gates['CVSD_DVMS_legacy_auto32_byte_identical']='PASS'
        # Strict64 cannot use CVSD/DVMS output: refuse before any write.
        for typ in ('cvs','cvsd','dvms','vms'):
            target=self.root/f'cvsd-strict64-refusal.{typ}'
            sentinel=b'NO NATIVE CVSD OUTPUT' * 7
            target.write_bytes(sentinel)
            requested=['--precision','64',src,target]
            info=json.loads(self.run(['--plan',*requested]).stdout)
            require(info['precision']['actual_route']=='refused-before-output',
                    f'{typ}: strict64 unexpectedly eligible')
            result=self.run(requested,expect=False)
            require(result.returncode!=0 and target.read_bytes()==sentinel,
                    f'{typ}: strict64 touched destination or unexpectedly succeeded')
            self.count('cvsd_strict64_precommit_refusals')
        self.gates['CVSD_DVMS_not_eligible_for_native_PCM64']='PASS'

    def execute(self):
        inputs=self.matrix()
        self.strict64(inputs[0])
        self.layout()
        self.endianness_and_subtype()
        self.auto32(inputs[1])
        self.implicit_endpoints()
        self.cvsd_writer_endpoints()
        return {'suite':'output-formats',
                'status':('PASS_WITH_NOT_RUN' if any(v.startswith('NOT_RUN') for v in self.gates.values()) else 'PASS'),
                'source_git_commit':safe_git_head(SOURCE),
                'executed_binary_sha256':{str(self.binary):sha256(self.binary)},
                'source_and_binary_sha256':{str(p.relative_to(SOURCE)):sha256(p) for p in
                    (SOURCE/'tests/pcm64/output_formats.py',SOURCE/'src/formats.c',
                     SOURCE/'src/sox_ng.c',SOURCE/'src/dsd_plan.c',SOURCE/'src/dsd.h',
                     SOURCE/'src/wav.c',SOURCE/'src/pcm_f64_io.h')},
                'actual_checks':self.counters,'gate_execution':self.gates,
                'not_run_reasons':self.skips,'commands_executed':self.commands,
                'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',required=True,type=Path)
    parser.add_argument('--results',required=True,type=Path)
    args=parser.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    test=Test(args.sox,args.results)
    path=args.results/'output-formats.json'
    path.unlink(missing_ok=True)
    if not native_dsp_compiled(args.sox):
        source=test.root/'disabled_input.wav'
        destination=test.root/'disabled_output.wav'
        wav(source,[0,1234,-1234],bits=16)
        destination.write_bytes(b'SENTINEL')
        cp=test.run(['--precision','64',source,destination],expect=False)
        plan=test.run(['--precision','64','--plan',source,destination],expect=False)
        ok=(cp.returncode!=0 and destination.read_bytes()==b'SENTINEL' and
            plan.returncode==0 and b'refused-before-output' in plan.stdout)
        record={'suite':'output-formats',
                'status':'PASS_WITH_NOT_RUN' if ok else 'FAIL',
                'gate_execution':{'disabled_native_refusal':'PASS' if ok else 'FAIL',
                    'native_output_format_matrix':'NOT_RUN: --disable-native-f64'},
                'source_git_commit':safe_git_head(SOURCE),
                'executed_binary_sha256':{str(args.sox):sha256(args.sox)},
                'actual_checks':{'disabled_refusal_commands':2},
                'commands_executed':test.commands}
        path.write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
        print(record['status']+' output-formats: disabled native DSP capability')
        return 0 if ok else 1
    try:
        receipt=test.execute()
    except BaseException as exc:
        receipt={'suite':'output-formats','status':'FAIL','error':f'{type(exc).__name__}: {exc}',
                 'actual_checks':test.counters,'gate_execution':test.gates,
                 'commands_executed':test.commands,
                 'source_git_commit':safe_git_head(SOURCE)}
        path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        print(f'FAIL output-formats: {exc}',file=sys.stderr)
        return 1
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(f'{receipt["status"]} output-formats: {receipt["actual_checks"]}; {test.commands} commands')
    return 0


if __name__=='__main__':
    sys.exit(main())
