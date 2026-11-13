#!/usr/bin/env python3
"""Phase 05A D-01..D-03: real writer negotiation, masks and WAV options.

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
import struct
import subprocess
import sys
from pathlib import Path

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
                require(reordered[5]==mask and rd==payload,
                        'known-role permutation failed canonical output-order restoration')
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

    def execute(self):
        inputs=self.matrix()
        self.strict64(inputs[0])
        self.layout()
        self.endianness_and_subtype()
        self.auto32(inputs[1])
        return {'suite':'output-formats',
                'status':('PASS_WITH_NOT_RUN' if any(v.startswith('NOT_RUN') for v in self.gates.values()) else 'PASS'),
                'source_git_commit':subprocess.run(['git','-C',str(SOURCE),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip(),
                'executed_binary_sha256':{str(self.binary):sha256(self.binary)},
                'source_and_binary_sha256':{str(p.relative_to(SOURCE)):sha256(p) for p in
                    (SOURCE/'tests/pcm64/output_formats.py',SOURCE/'src/formats.c',
                     SOURCE/'src/sox_ng.c',SOURCE/'src/wav.c',SOURCE/'src/pcm_f64_io.h')},
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
    try:
        receipt=test.execute()
    except BaseException as exc:
        receipt={'suite':'output-formats','status':'FAIL','error':f'{type(exc).__name__}: {exc}',
                 'actual_checks':test.counters,'gate_execution':test.gates,
                 'commands_executed':test.commands,
                 'source_git_commit':subprocess.run(['git','-C',str(SOURCE),'rev-parse','HEAD'],
                     capture_output=True,text=True).stdout.strip()}
        path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        print(f'FAIL output-formats: {exc}',file=sys.stderr)
        return 1
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(f'{receipt["status"]} output-formats: {receipt["actual_checks"]}; {test.commands} commands')
    return 0


if __name__=='__main__':
    sys.exit(main())
