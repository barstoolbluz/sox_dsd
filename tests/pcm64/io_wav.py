#!/usr/bin/env python3
"""Phase 02A: independent RIFF/RIFX fixtures, exact dyadic oracle and FD fault gates.

The WAV fixture encoder and parser here do not use libSoX, and all assertions
compare the native interface with independently constructed sample words.
Never rewrite this suite to compare SoX with itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
from fractions import Fraction
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import random
import resource
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time

SEED = 0x2026110902
GUID_TAIL = bytes.fromhex('000000001000800000aa00389b71')
UINT64_MAX = (1 << 64) - 1


def digest(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def insist(condition, detail):
    if not condition:
        raise AssertionError(detail)


def fmt_code(code):
    return (3 if code in ('f32', 'f64') else 1,
            int(code[1:]) if code.startswith('i') else int(code[1:]))


def wave_bytes(payload, channels=2, rate=44100, code='f64', big=False,
               extensible=False, mask=0, valid=None, tail=GUID_TAIL,
               extra=False, block_override=None, byte_rate_override=None):
    prefix = '>' if big else '<'
    word = lambda n: struct.pack(prefix+'I', n)
    tag, bits = fmt_code(code)
    align = channels * (bits // 8) if block_override is None else block_override
    byte_rate = rate * align if byte_rate_override is None else byte_rate_override
    subformat = (struct.pack(prefix+'H', tag) + tail)
    if extensible:
        wformat = 0xfffe
        details = struct.pack(prefix+'HI', bits if valid is None else valid, mask) + subformat
        fmt = struct.pack(prefix+'HHIIHHH', wformat,channels,rate,byte_rate,align,bits,22) + details
    else:
        fmt = struct.pack(prefix+'HHIIHH',tag,channels,rate,byte_rate,align,bits)
        if tag==3:
            fmt += struct.pack(prefix+'H',0)
    chunks = [(b'fmt ',fmt)]
    if extra:
        chunks += [(b'JUNK',b'odd'),(b'LIST',b'abcde')]
    if tag==3 or extensible:
        chunks += [(b'fact',word(len(payload)//(channels*(bits//8))))]
    chunks += [(b'data',payload)]
    body = bytearray()
    for name,data in chunks:
        body.extend(name + word(len(data)) + data + (b'\0' if len(data)&1 else b''))
    return (b'RIFX' if big else b'RIFF') + word(len(body)+4) + b'WAVE' + body


def parse_wave(path):
    raw = path.read_bytes()
    insist(len(raw)>=12 and raw[:4] in (b'RIFF',b'RIFX') and raw[8:12]==b'WAVE',
           'invalid emitted WAV header: '+str(path))
    big=raw[:4]==b'RIFX'
    prefix='>' if big else '<'
    rsize=struct.unpack_from(prefix+'I',raw,4)[0]
    insist(rsize+8==len(raw),f'RIFF extent mismatch for {path}: {rsize+8} != {len(raw)}')
    pos=12
    chunks={}
    while pos<len(raw):
        insist(pos+8<=len(raw), 'truncated chunk header')
        key=raw[pos:pos+4]
        size=struct.unpack_from(prefix+'I',raw,pos+4)[0]
        begin=pos+8
        insist(begin+size<=len(raw),'truncated chunk payload')
        insist(key not in chunks,'duplicate chunk '+repr(key))
        chunks[key]=(begin,raw[begin:begin+size])
        pos=begin+size+(size&1)
    insist(pos==len(raw) and b'fmt ' in chunks and b'data' in chunks,
           'malformed chunk inventory')
    fields=chunks[b'fmt '][1]
    tag,ch,rate,br,align,bits=struct.unpack_from(prefix+'HHIIHH',fields)
    valid=bits
    mask=None
    guid=None
    if tag==0xfffe:
        insist(len(fields)>=40,'short extended format')
        cb=struct.unpack_from(prefix+'H',fields,16)[0]
        insist(cb>=22,'short extended format size')
        valid,mask=struct.unpack_from(prefix+'HI',fields,18)
        guid=fields[24:40]
    return {'bytes': raw, 'big': big, 'chunks':chunks, 'tag':tag, 'channels':ch,
            'rate':rate, 'byte_rate':br,'block_align':align,'bits':bits,
            'valid':valid,'mask':mask,'guid':guid,'data':chunks[b'data'][1],
            'data_offset':chunks[b'data'][0]}


def ieee_f64_bits(x):
    return struct.unpack('<Q',struct.pack('<d',x))[0]


def raw_double_words(words):
    return b''.join(struct.pack('<Q',w) for w in words)


def enc_float_words(words, bits, big):
    prefix='>' if big else '<'
    return b''.join(struct.pack(prefix+('Q' if bits==64 else 'I'),w) for w in words)


def integer_bytes(codes,bits,big):
    # Signed two's-complement except unsigned, offset-binary PCM8.
    nbytes=bits//8
    return b''.join((q if bits==8 else q % (1<<bits)).to_bytes(nbytes,'big' if big else 'little')
                    for q in codes)


def quant(bits,x):
    f=Fraction.from_float(x)
    lim=1<<(bits-1)
    sign=-1 if math.copysign(1.0,x)<0 else 1
    scaled=abs(f)*lim
    n,r=divmod(scaled.numerator,scaled.denominator)
    code=sign*(n+(2*r>=scaled.denominator))
    return max(-lim,min(lim-1,code))


def float_words():
    rng=random.Random(SEED)
    out={0,1,(1<<52)-1,1<<52,(1<<52)+1,(1<<63),
         0x3fdfffffffffffff,0x3fe0000000000000,0x3fe0000000000001,
         0x3ff0000000000000,0x3ff0000000000001,0x7fefffffffffffff}
    for power in (-1074,-1022,-1021,-50,-40,-32,-31,-25,-24,-17,-16,-9,-8,-2,-1,0,1,2,31,500,1023):
        n=math.ldexp(1.0,power)
        for v in (n,math.nextafter(n,0),math.nextafter(n,math.inf)):
            if math.isfinite(v): out.add(ieee_f64_bits(v))
    for exponent in range(0x7ff):
        out.add((exponent<<52)|rng.getrandbits(52))
        out.add((exponent<<52)|((1<<52)-1))
    for _ in range(400):
        out.add((rng.randrange(0x7ff)<<52)|rng.getrandbits(52))
    out |= {u|(1<<63) for u in tuple(out)}
    insist(len(out)>8000,'insufficient exponent coverage')
    return sorted(out)


def f32_words():
    rng=random.Random(SEED^0x32)
    out={0,1,(1<<23)-1,1<<23,0x3f800000,0x3f000000,0x7f7fffff,1<<31}
    for e in range(0xff):
        out.add((e<<23)|rng.getrandbits(23))
    for _ in range(150):
        out.add((rng.randrange(0xff)<<23)|rng.getrandbits(23))
    out |= {x|(1<<31) for x in tuple(out)}
    return sorted(out)


def read_double_words(buf):
    insist(len(buf)%8==0,'dump emitted incomplete double')
    return [v[0] for v in struct.iter_unpack('<Q',buf)]


class CaseRunner:
    def __init__(self,sox,probe,results):
        self.sox=sox
        self.probe=probe
        self.results=results
        self.root=results/'fixtures'/'io-wav'
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self.counts={}
        self.commands=[]
        self.artifacts={}
        self.shim=None
        self.fenv=None
        self.gates={}
        self.rng=random.Random(SEED)

    def tick(self,group,n=1):
        self.counts[group]=self.counts.get(group,0)+n

    def file(self,name,data):
        dest=self.root/name
        dest.write_bytes(data)
        self.artifacts[name]=digest(dest)
        return dest

    def invoke(self,args,*,expect=0,env=None,output=None,stdin=None,preexec_fn=None, label=None, stdout_pipe=False):
        command=[str(self.probe)]+[str(x) for x in args]
        started=time.perf_counter()
        runenv=os.environ.copy()
        if env: runenv.update({str(k):str(v) for k,v in env.items()})
        if stdout_pipe:
            p=subprocess.run(command,cwd=self.root,env=runenv,stdin=stdin,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             timeout=50,preexec_fn=preexec_fn)
            stdout=p.stdout
        else:
            with (output.open('wb') if output else tempfile.TemporaryFile()) as fout:
                p=subprocess.run(command,cwd=self.root,env=runenv,stdin=stdin,
                                 stdout=fout,stderr=subprocess.PIPE,timeout=50,
                                 preexec_fn=preexec_fn)
                fout.seek(0)
                stdout=fout.read()
        record={'label':label or args[0], 'argv':command,'exit':p.returncode,
                'stdout_sha256':hashlib.sha256(stdout).hexdigest(),
                'stdout_bytes':len(stdout),
                'wall_seconds':round(time.perf_counter()-started,6),
                'stderr':p.stderr.decode('utf-8','replace')[:4096],
                'env':{k:v for k,v in (env or {}).items() if k.startswith('PCM64_')}}
        self.commands.append(record)
        insist((p.returncode==0) == (expect==0),
               f'command {label or args[0]} unexpected exit {p.returncode}, expected {expect}; '
               f'arguments={command} stderr={record["stderr"]}')
        return stdout,p.stderr.decode('utf-8','replace')

    def reject(self,args,*,sentinels=(), env=None, label=None, stderr_contains=None,
               preexec_fn=None, stdout_pipe=False, trace_event=None):
        trace=None
        if trace_event:
            trace=self.root/('injected-'+str(label)+'.events')
            trace.unlink(missing_ok=True)
            env={**(env or {}),'PCM64_TRACE':str(trace)}
        prior={str(x):x.read_bytes() for x in sentinels}
        output,err=self.invoke(args,expect=1,env=env,label=label,preexec_fn=preexec_fn,stdout_pipe=stdout_pipe)
        for path in sentinels:
            insist(path.read_bytes()==prior[str(path)],
                   f'precommit refusal modified sentinel: {label}: {path}')
        if trace_event:
            insist(trace.is_file() and trace_event.encode() in trace.read_bytes(),
                   f'fault hook {trace_event!r} did not actually execute for {label}')
            self.tick('observed_fault_hook_events')
        if stderr_contains:
            insist(stderr_contains.lower() in err.lower(),
                   f'{label}: expected diagnostic {stderr_contains!r}, got {err!r}')
        self.tick('refusals')
        return err

    def query(self,file,*,frames,channels,bits,big=False,mask=None):
        stdout,_=self.invoke(['query',file],label='query-'+file.name)
        s=stdout.decode()
        for label,v in {'frames':frames,'channels':channels,'bits':bits,'big':int(big)}.items():
            insist(f'{label}={v}' in s,f'query did not report {label}={v}: {s}')
        if mask is not None:
            insist(f'mask={mask:08x}' in s, f'query lost mask {mask:x}: {s}')
        self.tick('metadata_queries')

    def dump(self,file,count,expected_words,*,block=23):
        b,_=self.invoke(['dump',file,block],label='dump-'+file.name+'-'+str(block))
        insist(len(b)==count*8, f'bad binary64 sample count: {file} {len(b)//8} != {count}')
        got=read_double_words(b)
        insist(got==expected_words,
               f'exact native decode mismatch: {file}, block={block}; sample=' +
               str(next((i for i,(a,v) in enumerate(zip(got,expected_words)) if a!=v), '?')))
        self.tick('decoded_words',len(got))
        self.tick('independent_dump_checks')

    def native_copy(self,inp,out,code='f64',big=False,block=23):
        self.invoke(['copy',inp,out,code,'B' if big else 'L',block],
                    label='copy-'+out.name)
        self.tick('native_copies')
        return parse_wave(out)

    def native_generate(self,raw,out,code,big,channels,rate,declared,actual=None,
                        *, expect=0, extra_args=(), env=None,label=None):
        self.invoke(['generate',raw,out,code,'B' if big else 'L',channels,rate,
                     declared,actual if actual is not None else declared,*extra_args],
                    expect=expect,env=env,label=label or 'generate-'+out.name)
        self.tick('native_generate_calls')

    def formats(self):
        words=float_words()
        self.tick('distinct_finite_f64_words',len(words))
        for ch,big,ext in ((1,False,False),(2,False,False),(6,False,True),
                           (2,True,False),(6,True,True),(2,False,True)):
            n=(len(words)//ch)*ch
            chosen=words[:n]
            data=enc_float_words(chosen,64,big)
            src=self.file(f'f64-in-{ch}-{int(big)}-{int(ext)}.wav',
                          wave_bytes(data,channels=ch,code='f64',big=big,
                                     extensible=ext,mask=0x3f if ch==6 else (3 if ext else 0),extra=True))
            self.query(src,frames=n//ch,channels=ch,bits=64,big=big,
                       mask=0x3f if ch==6 else (3 if ext else 0))
            for block in (1,7,257):
                self.dump(src,n,chosen,block=block)
            dst=self.root/f'f64-copy-{ch}-{int(big)}-{int(ext)}.wav'
            parsed=self.native_copy(src,dst,'f64',not big,block=7)
            # A copied file may change the header, not the IEEE payload.
            insist(parsed['data']==enc_float_words(chosen,64,not big),
                   f'F64 payload changed on copy: {src.name}')
            if ext:
                insist(parsed['mask']==(0x3f if ch==6 else 3),
                       'canonical source speaker mask not preserved')
                insist(parsed['guid'][2:]==GUID_TAIL,
                       'noncanonical EXTENSIBLE GUID writer')
            self.dump(dst,n,chosen,block=1)
            self.invoke(['mixed',src],label='mixed-access-'+src.name)
            self.tick('mixed_seek_eof_state_checks')
            self.tick('f64_roundtrip_samples',n)
        # F32: each possible exponent class, both signs, and subnormal tails.
        for ch,big,ext in ((1,False,False),(2,True,False),(6,False,True)):
            words32=f32_words()
            words32=words32[:len(words32)//ch*ch]
            data=enc_float_words(words32,32,big)
            src=self.file(f'f32-in-{ch}-{int(big)}.wav',
                          wave_bytes(data,channels=ch,code='f32',big=big,
                                     extensible=ext,mask=0x3f if ext else 0,extra=True))
            want=[ieee_f64_bits(struct.unpack('<f',struct.pack('<I',w))[0]) for w in words32]
            self.query(src,frames=len(words32)//ch,channels=ch,bits=32,big=big)
            self.dump(src,len(words32),want,block=1)
            out=self.root/f'f32-copy-{ch}.wav'
            parsed=self.native_copy(src,out,'f32',not big,block=7)
            insist(parsed['data']==enc_float_words(words32,32,not big),
                   f'float32 exact widening/narrowing changed native words {ch}')
            self.tick('f32_roundtrip_samples',len(words32))
        # All four integer PCM widths; exact fraction-to-double on ingress.
        for bits in (8,16,24,32):
            scale=1<<(bits-1)
            qset={-scale,-scale+1,-scale//2,-1,0,1,scale//2,scale-2,scale-1}
            qset|={self.rng.randrange(-scale,scale) for _ in range(350)}
            qlist=sorted(qset)
            for ch,big,ext in ((1,False,False),(2,True,False),(6,False,True)):
                codes=(qlist*((ch+len(qlist)-1)//len(qlist)))[:(len(qlist)//ch)*ch]
                if bits==8: encoded=[q+128 for q in codes]
                else: encoded=codes
                name=f'i{bits}-in-{ch}-{int(big)}.wav'
                source=self.file(name,wave_bytes(integer_bytes(encoded,bits,big),channels=ch,
                         code=f'i{bits}',big=big,extensible=ext,mask=0x3f if ext else 0,extra=True))
                want=[ieee_f64_bits(float(Fraction(q,scale))) for q in codes]
                self.query(source,frames=len(codes)//ch,channels=ch,bits=bits,big=big)
                self.dump(source,len(codes),want,block=7)
                dst=self.root/f'i{bits}-copy-{ch}-{int(big)}.wav'
                parsed=self.native_copy(source,dst,f'i{bits}',not big,block=1)
                insist(parsed['data']==integer_bytes(encoded,bits,not big),
                       f'integer decoded/quantized value diverged at {bits} bits')
                self.tick('integer_roundtrip_samples',len(codes))
        # Distinguish binary64 from an int32 bridge: finite nonunity and tiny
        # values must not be clamped, quantized or reconstituted as zeros.
        bridge_words=[ieee_f64_bits(x) for x in (2.0,-1.5,math.ldexp(1.0,-40),
                      math.ldexp(1.0,-500),math.nextafter(1.0,2.0),-0.0)]
        clipped=[ieee_f64_bits(float(Fraction(quant(32,struct.unpack('<d',struct.pack('<Q',w))[0]),1<<31))) for w in bridge_words]
        insist(bridge_words!=clipped,'int32-bridge mutation was not detected')
        self.tick('int32_bridge_negative_controls')

    def daz_guard(self):
        # DAZ affects SSE FLOAT32 -> binary64 widening, not bitwise FLOAT64
        # transfer. Exercise the *actual* reader under both MXCSR settings.
        if platform.machine().lower() not in ('x86_64', 'amd64'):
            self.gates['f32_daz_read_guard']='NOT_RUN: requires x86-64 SSE2'
            return
        f32 = [0x00000001, 0x80000001, 0x007fffff, 0x807fffff,
               0x00012345, 0x80054321, 0x00800000, 0x80800000,
               0x3f800000, 0xbf800000, 0x00000000, 0x80000000]
        src = self.file('daz-subnormal-f32.wav',wave_bytes(
            enc_float_words(f32,32,False),channels=2,code='f32'))
        want = [ieee_f64_bits(struct.unpack('<f',struct.pack('<I',w))[0])
                for w in f32]
        actual,_ = self.invoke(['daz',src,'off'],label='f32-daz-disabled')
        insist(read_double_words(actual)==want,
               'FLOAT32 subnormal widening changed with DAZ disabled')
        rejected,_ = self.invoke(['daz',src,'on'],label='f32-daz-refused-and-latched')
        insist(rejected==b'', 'DAZ rejection published decoded FLOAT32 samples')
        self.tick('f32_daz_off_exact_samples',len(f32))
        self.tick('f32_daz_on_refusals_latched_and_unpublished')
        f64 = [0x0000000000000000, 0x8000000000000000,
               0x0000000000000001, 0x8000000000000001,
               0x000fffffffffffff, 0x800fffffffffffff,
               0x0010000000000000, 0x3ff0000000000000]
        src64 = self.file('daz-identity-f64.wav',wave_bytes(
            enc_float_words(f64,64,False),channels=2,code='f64'))
        actual64,_ = self.invoke(['daz',src64,'on'],label='f64-daz-on-identity')
        insist(read_double_words(actual64)==f64,
               'FLOAT64 bitwise ingress changed under DAZ')
        self.tick('f64_daz_on_identity_samples',len(f64))
        self.gates['f32_daz_read_guard']='PASS'

    def quantization(self):
        # Independent ties-away and exact pre-half-step neighboring values.
        for bits in (8,16,24,32):
            scale=1<<(bits-1)
            half=math.ldexp(1.0,-bits)
            values=[-2.0,-1.0,-0.0,0.0,1.0,1.5,
                    half,-half,math.nextafter(half,0),
                    math.nextafter(half,math.inf),
                    math.nextafter(-half,0),math.nextafter(-half,-math.inf),
                    math.ldexp(1.0,-40),math.ldexp(-1.0,-40)]
            values += [float(Fraction(self.rng.randrange(-scale,scale),scale))
                       for _ in range(110)]
            inp=self.file(f'quant-input-{bits}.raw64',b''.join(struct.pack('<d',v) for v in values))
            dest=self.root/f'quant-output-{bits}.wav'
            self.native_generate(inp,dest,f'i{bits}',False,1,44100,len(values))
            p=parse_wave(dest)
            expected=integer_bytes([quant(bits,v)+(128 if bits==8 else 0) for v in values],bits,False)
            insist(p['data']==expected, f'fractional rational quantizer mismatch for {bits} bits')
            self.tick('exact_quantizer_cases',len(values))
            if bits in (24,32):
                old=int(math.floor(abs(math.nextafter(half,0))*scale+.5))
                insist(old==1 and quant(bits,math.nextafter(half,0))==0,
                       f'quantizer old-route divergence missing for {bits}')
                self.tick('old_bridge_rounding_negative_controls')
        # F32 writer rounding including signed zero, subnormals and ties.
        float_values=[0.0,-0.0,1.0,-1.0,math.ldexp(1.0,-149),
                      math.ldexp(1.0,-150),math.nextafter(1.0,2.0),
                      math.ldexp(1.0,-40),2.0,3.141592653589793,
                      -math.ldexp(1.0,128)/2]
        inp=self.file('f32-write-input.raw64',b''.join(struct.pack('<d',v) for v in float_values))
        for big in (False,True):
            out=self.root/f'f32-write-{int(big)}.wav'
            self.native_generate(inp,out,'f32',big,1,44100,len(float_values))
            p=parse_wave(out)
            insist(p['data']==b''.join(struct.pack('>f' if big else '<f',v)
                                        for v in float_values), 'binary32 RNE conversion mismatch')
            self.tick('float32_narrowing_samples',len(float_values))

    def malformed(self):
        good=self.file('invalid-baseline.wav',wave_bytes(struct.pack('<d',1.0),channels=1,code='f64',extensible=True,mask=4))
        b=good.read_bytes()
        data_offset=parse_wave(good)['data_offset']
        cases={}
        # Invalid canonical GUID and header canonicality; do not assume
        # legacy parser itself rejects malformed headers at open.
        cases['float-infinity']=lambda x:x.__setitem__(slice(data_offset,data_offset+8),struct.pack('<d',math.inf))
        cases['float-nan']=lambda x:x.__setitem__(slice(data_offset,data_offset+8),struct.pack('<Q',0x7ff8000000000010))
        # Fixed synthetic variants. Addressing bytes via parsed fmt chunk.
        fmt_off=parse_wave(good)['chunks'][b'fmt '][0]
        cases['guid-tail']=lambda x:x.__setitem__(fmt_off+26,0xff)
        cases['valid-bits']=lambda x:x.__setitem__(fmt_off+18,56)
        cases['byte-rate']=lambda x:x.__setitem__(slice(fmt_off+8,fmt_off+12),b'\0\0\0\0')
        cases['block-align']=lambda x:x.__setitem__(slice(fmt_off+12,fmt_off+14),b'\x01\0')
        for title,mutate in cases.items():
            payload=bytearray(b)
            mutate(payload)
            dst=self.file(f'bad-{title}.wav',bytes(payload))
            if title in ('float-nan','float-infinity'):
                self.reject(['dump',dst,1],label=title,stderr_contains='frame 0 channel 0')
            else:
                self.reject(['query',dst],label=title)
            self.tick('invalid_headers_or_nonfinite_inputs')
        invalid_mask=self.file('mismatched-speaker-mask.wav',wave_bytes(
            struct.pack('<d',1.0)*2,channels=2,code='f64',
            extensible=True,mask=0x4))
        self.reject(['query',invalid_mask],label='mismatched-speaker-mask')
        self.tick('invalid_headers_or_nonfinite_inputs')
        # FLOAT32 nonfinite input with channel-indexed failure, separately
        # from FLOAT64 and with a format parser not derived from libSoX.
        f32_bad=self.file('nonfinite-f32.wav',wave_bytes(
            struct.pack('<f',0.0)+struct.pack('<I',0x7f800001),
            channels=2,code='f32'))
        self.reject(['dump',f32_bad,1],label='float32-snan',
                    stderr_contains='frame 0 channel 1')
        self.tick('invalid_headers_or_nonfinite_inputs')
        # Native writers must also reject input infinities, NaNs, and a
        # finite binary64 value that overflows the destination FLOAT32.
        for title,values,encoding,diagnostic in (
            ('write-f64-inf',[math.inf],'f64','frame 0 channel 0'),
            ('write-f64-qnan',[math.nan],'f64','frame 0 channel 0'),
            ('write-f64-second-channel',[0.0,-math.inf],'f64','frame 0 channel 1'),
            ('write-f32-overflow',[sys.float_info.max],'f32','frame 0 channel 0')):
            raw=self.file(title+'.raw64',b''.join(struct.pack('<d',v) for v in values))
            out=self.root/(title+'.wav')
            self.reject(['generate',raw,out,encoding,'L',len(values),44100,1,1],
                        label=title,stderr_contains=diagnostic)
            self.tick('nonfinite_output_refusals')
        # Truncated physical bytes despite a declared full frame, with
        # correct outer RIFF length to keep the parser in the data section.
        trunc=self.file('truncated-payload.wav',wave_bytes(struct.pack('<d',0.5)*2,
                                                           channels=1,code='f64'))
        arr=bytearray(trunc.read_bytes())
        # Remove last few physical bytes without repairing header size.
        trunc.write_bytes(arr[:-3])
        self.artifacts[trunc.name]=digest(trunc)
        self.reject(['dump',trunc,1],label='physically-truncated-input')
        self.tick('truncated_inputs')
        # Declared WAV data size must contain only complete PCM frames.
        incomplete=self.file('incomplete-frame.wav',wave_bytes(b'1234567',
                                                              channels=1,code='f64'))
        self.reject(['query',incomplete],label='incomplete-frame')
        self.tick('incomplete_frame_refusals')
        zero=self.file('zero-frame-input.wav',wave_bytes(b'',channels=1,code='f64'))
        self.query(zero,frames=0,channels=1,bits=64)
        self.dump(zero,0,[],block=1)
        self.tick('zero_frame_input_checks')
        # Reject foreign metadata overrides (not a blind trust in sox signal).
        self.reject(['query',good,48000],label='rate-override')
        self.tick('metadata_override_refusals')

    def safety(self):
        raw=self.file('safety-input.raw64',struct.pack('<d',0.5))
        source=self.file('safety-source.wav',wave_bytes(struct.pack('<d',0.25),1,code='f64'))
        existing=self.file('safety-existing.wav',b'SENTINEL-preserve-original-bytes-'*10)
        prior=existing.read_bytes()
        # All these errors must occur before any open/truncation.
        self.reject(['generate',raw,existing,'f64','L',1,44100,UINT64_MAX,1],
                    sentinels=(existing,),label='unknown-length')
        self.reject(['generate',raw,existing,'f64','L',1,44100,1<<35,1],
                    sentinels=(existing,),label='RF64-refusal')
        self.reject(['generate',raw,existing,'f64','L',1,44100,1,1,'deny'],
                    sentinels=(existing,),label='overwrite-denial')
        self.reject(['generate',raw,existing,'f64','L',1,44100,1,1,'allow',existing],
                    sentinels=(existing,),label='report-alias')
        report_hardlink=self.root/'report-hardlink.log'
        os.link(existing,report_hardlink)
        self.reject(['generate',raw,existing,'f64','L',1,44100,1,1,'allow',report_hardlink],
                    sentinels=(existing,report_hardlink),label='report-hardlink-alias')
        self.reject(['generate',raw,existing,'f64','L',1,4294967295,1,1],
                    sentinels=(existing,),label='byte-rate-overflow')
        self.reject(['generate',raw,existing,'i8','L',1,44100,1<<32,1],
                    sentinels=(existing,),label='fact/RIFF-overflow')
        # Existing hardlink alias to input must fail with original bytes intact.
        self.reject(['copy',source,source,'f64','L'],
                    sentinels=(source,),label='source-same-path-alias')
        in_link=self.root/'alias-to-input.wav'
        os.link(source,in_link)
        self.reject(['copy',source,in_link,'f64','L'],
                    sentinels=(source,in_link),label='source-hardlink-alias')
        symlink=self.root/'source-symlink.wav'
        symlink.symlink_to(source)
        self.reject(['copy',source,symlink,'f64','L'],
                    sentinels=(source,symlink),label='source-symlink-alias')
        # A stable symlink to a different regular file is accepted and retained.
        target=self.file('stable-target.wav',b'OLD-symlink-target'*13)
        stable=self.root/'stable-link.wav'
        stable.symlink_to(target)
        self.native_generate(raw,stable,'f64',False,1,44100,1)
        insist(stable.is_symlink() and stable.resolve()==target.resolve(),
               'native writer replaced stable symlink')
        insist(parse_wave(target)['data']==struct.pack('<d',0.5),
               'stable symlink target was not populated correctly')
        self.artifacts[target.name]=digest(target)
        self.tick('stable_symlinks')
        # Reject special files before opening, and do not block on FIFO.
        fifo=self.root/'named-fifo.wav'
        os.mkfifo(fifo)
        self.reject(['generate',raw,fifo,'f64','L',1,44100,1,1],label='fifo-refusal')
        self.reject(['generate',raw,self.root,'f64','L',1,44100,1,1],label='directory-refusal')
        if Path('/dev/null').exists():
            self.reject(['generate',raw,'/dev/null','f64','L',1,44100,1,1],label='device-refusal')
        dangling=self.root/'dangling-link.wav'
        dangling.symlink_to(self.root/'uncreated')
        self.reject(['generate',raw,dangling,'f64','L',1,44100,1,1],label='dangling-refusal')
        insist(dangling.is_symlink(),'dangling symlink was unlinked')
        fresh=self.root/'new-exclusive.wav'
        self.native_generate(raw,fresh,'f64',False,1,44100,1)
        insist(fresh.is_file() and parse_wave(fresh)['data']==struct.pack('<d',0.5),
               'exclusive creation failed')
        self.tick('exclusive_creations')
        # Late writer under- and over-run: output may be partial, but must fail.
        short=self.root/'writer-underrun.wav'
        self.reject(['generate',raw,short,'f64','L',1,44100,2,1],label='writer-underrun')
        self.tick('writer_count_failures')
        overflow=self.root/'writer-overflow.wav'
        self.reject(['generate',raw,overflow,'f64','L',1,44100,0,1],label='writer-overflow')
        self.tick('writer_count_failures')
        # Zero frame output, odd byte padding and one-frame edge cases.
        empty=self.root/'empty.wav'
        self.native_generate(raw,empty,'f64',False,1,44100,0,0)
        insist(parse_wave(empty)['data']==b'','empty WAV data chunk missing')
        oddinput=self.file('odd-samples.raw64',struct.pack('<d',0.0)*3)
        odd=self.root/'odd-i8.wav'
        self.native_generate(oddinput,odd,'i8',False,1,44100,3)
        insist(len(parse_wave(odd)['data'])==3 and len(odd.read_bytes())%2==0,
               'odd data-chunk pad not written')
        self.tick('zero_one_odd_frames',3)
        # The stdout FILE* path may be used only when the exact descriptor is
        # an inspectable regular file. Verify no second path-open is involved.
        stdfile=self.root/'stdout-regular.wav'
        with stdfile.open('wb') as fout:
            proc=subprocess.run([str(self.probe),'generate',str(raw),'-',
                                 'f64','L','1','44100','1','1'],stdout=fout,
                                stderr=subprocess.PIPE,timeout=15)
        insist(proc.returncode==0 and parse_wave(stdfile)['data']==struct.pack('<d',0.5),
               'stdout regular file denied or corrupted')
        self.tick('stdout_regular_descriptor_checks')
        # stdout is allowed for inspectable regular descriptors, but never
        # blindly write to a pipe or FIFO. Shell redirection is outside guarantee.
        self.reject(['generate',raw,'-','f64','L',1,44100,1,1],label='stdout-pipe-refusal',stdout_pipe=True)
        # Inject failure at exact descriptor handoff, before existing-file truncate.
        if self.shim:
            preload={'LD_PRELOAD':str(self.shim)}
            self.reject(['generate',raw,existing,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_FAIL_FDOPEN':'1'},sentinels=(existing,),label='fdopen-refusal',
                        trace_event='D')
            self.reject(['generate',raw,existing,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_FAIL_SETVBUF':'1','PCM64_TEST_TARGET':str(existing)},
                        sentinels=(existing,),label='setvbuf-refusal',trace_event='V')
            new=self.root/'fdopen-created-fail.wav'
            self.reject(['generate',raw,new,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_FAIL_FDOPEN':'1'},label='failed-new-create',
                        trace_event='D')
            insist(not new.exists(),'failed precommit exclusive creation left a path')
            target_new=self.file('symlink-race-target.wav',b'RACE TARGET-SENTINEL'*10)
            race=self.root/'symlink-race.wav'
            race.symlink_to(existing)
            self.reject(['generate',raw,race,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_SWAP_PATH':str(race),
                             'PCM64_SWAP_TO':str(target_new)},
                        sentinels=(existing,target_new),label='symlink-retarget-race',trace_event='S')
            # Read short chunks that are not frame-aligned: 3-byte underlying reads.
            sr=self.file('short-read-input.wav',wave_bytes(struct.pack('<d',0.125)*13,1,code='f64'))
            p=parse_wave(sr)
            short_trace=self.root/'short-read-events'
            short_trace.unlink(missing_ok=True)
            out,_=self.invoke(['dump',sr,7],
                              env={**preload,'PCM64_TRACE':str(short_trace),'PCM64_SHORT_READ':'1',
                                   'PCM64_TEST_TARGET':str(sr),
                                   'PCM64_DATA_OFFSET':str(p['data_offset'])},
                              label='unaligned-short-reads')
            insist(read_double_words(out)==[ieee_f64_bits(0.125)]*13,
                   'short underlying reads changed frame samples')
            insist(short_trace.exists() and b'R' in short_trace.read_bytes(),
                   'short-read shim was not actually invoked')
            self.tick('observed_fault_hook_events')
            self.tick('short_read_fault_injections')
            # Late write and close failures: can mutate new output and must
            # propagate nonzero rather than silently mark success.
            late=self.root/'late-short-write.wav'
            self.reject(['generate',raw,late,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_SHORT_WRITE':'1',
                             'PCM64_TEST_TARGET':str(late),
                             'PCM64_DATA_OFFSET':str(parse_wave(fresh)['data_offset'])},
                        label='late-short-write',trace_event='W')
            lateclose=self.root/'late-close-failure.wav'
            self.reject(['generate',raw,lateclose,'f64','L',1,44100,1,1],
                        env={**preload,'PCM64_FAIL_FCLOSE':'1',
                             'PCM64_TEST_TARGET':str(lateclose)},label='late-close-failure',
                        trace_event='C')
            self.tick('late_write_or_close_failure',2)
        self.permission_denial()
        insist(prior==b'SENTINEL-preserve-original-bytes-'*10,'internal test sentinel mutation')

    def permission_denial(self):
        # Use a self-contained fixture under /tmp: the caller's --results
        # ancestors may be mode 0700 under umask 077 and inaccessible after
        # dropping privileges. Do not relax permissions on those ancestors.
        gate = 'permission_error_real_eacces'
        negative_gate = 'permission_unreadable_input_negative_control'
        def skip(reason):
            self.gates[gate] = 'NOT_RUN: ' + reason
            self.gates[negative_gate] = 'NOT_RUN: ' + reason
        if os.name != 'posix':
            skip('requires POSIX file permissions')
            return
        if not Path('/tmp').is_dir():
            skip('no system /tmp for UID-accessible fixture')
            return
        is_root = os.geteuid() == 0
        if is_root and not all(hasattr(os, name) for name in ('setgroups', 'setgid', 'setuid')):
            skip('UID/GID transition unavailable on this host')
            return

        def drop_identity():
            os.setgroups([])
            os.setgid(65534)
            os.setuid(65534)

        child_identity = drop_identity if is_root else None
        self.gates[gate] = 'FAIL: native output-acquisition EACCES not demonstrated'
        writer_error = 'native WAV: nontruncating open failed: Permission denied'
        sentinel = b'LOCKED-SENTINEL' * 6
        with tempfile.TemporaryDirectory(prefix='pcm64-eacces-', dir='/tmp') as tmp:
            fixture = Path(tmp)
            fixture.chmod(0o755)
            readable = fixture / 'input.raw64'
            readable.write_bytes(raw_double_words([ieee_f64_bits(0.5)]))
            readable.chmod(0o644)
            restricted = fixture / 'unwritable.wav'
            restricted.write_bytes(sentinel)
            restricted.chmod(0o400)

            args = ['generate', readable, restricted, 'f64', 'L', 1, 44100, 1, 1]
            try:
                err = self.reject(args, sentinels=(restricted,), label='EACCES',
                                  stderr_contains=writer_error, env={'LC_ALL': 'C'},
                                  preexec_fn=child_identity)
            except subprocess.SubprocessError as exc:
                if is_root and 'preexec_fn' in str(exc):
                    skip('could not drop child to UID/GID 65534')
                    return
                raise
            insist('FAIL safe open: no format handle' in err,
                   'EACCES: the probe did not reach native output acquisition')

            # Negative control: a raw-input EACCES must never qualify as the
            # writer refusal, even though it also exits nonzero and contains
            # the words "Permission denied".
            unreadable = fixture / 'unreadable.raw64'
            unreadable.write_bytes(readable.read_bytes())
            unreadable.chmod(0o000)
            _, negative = self.invoke(
                ['generate', unreadable, restricted, 'f64', 'L', 1, 44100, 1, 1],
                expect=1, label='EACCES-unreadable-input-negative-control',
                env={'LC_ALL': 'C'}, preexec_fn=child_identity)
            insist('raw input: Permission denied' in negative,
                   'EACCES negative control did not exercise unreadable input')
            insist(writer_error not in negative and 'FAIL safe open:' not in negative,
                   'EACCES negative control falsely looks like a writer refusal')
            insist(restricted.read_bytes() == sentinel,
                   'EACCES negative control modified the destination')

        self.tick('permission_error_real_eacces')
        self.tick('permission_unreadable_input_negative_control')
        self.gates[gate] = 'PASS'
        self.gates['permission_unreadable_input_negative_control'] = 'PASS'

    def writer_environment(self):
        # The native preflight must happen before opening any destination.
        # Test both entry points (generation and native copy), each supported
        # arithmetic output and both pre-existing and absent destinations.
        if self.fenv is None:
            self.gates['writer_environment_preflight']='NOT_RUN: requires x86 SSE2'
            self.gates['source_environment_preflight']='NOT_RUN: requires x86 SSE2'
            return
        raw=self.file('fenv-native-input.raw64',raw_double_words([
            ieee_f64_bits(0.25),ieee_f64_bits(-0.5),ieee_f64_bits(0.75),ieee_f64_bits(0.0)]))
        source=self.root/'fenv-native-source.wav'
        self.native_generate(raw,source,'f64',False,2,48000,2)
        existing=self.root/'fenv-native-existing.wav'
        absent=self.root/'fenv-native-absent.wav'
        for mode in ('generate','copy'):
            for code in ('f32','i32','i24','i16','i8','f64'):
                for setting in (0x40,0x8000,0x2000,0x4000,0x6000):
                    env={'LD_PRELOAD':str(self.fenv),'PCM64_TEST_MXCSR_OR':hex(setting)}
                    for name,dest in (('existing',existing),('absent',absent)):
                        dest.unlink(missing_ok=True)
                        if name=='existing':
                            dest.write_bytes(b'PRESERVE-EXISTING-WAV'*5)
                        args=(['generate',raw,dest,code,'L',2,48000,2,2]
                              if mode=='generate' else ['copy',source,dest,code,'L'])
                        label=f'fenv-{mode}-{code}-{setting:x}-{name}'
                        if code=='f64':
                            self.invoke(args,env=env,label=label)
                            insist(parse_wave(dest)['data']==raw.read_bytes(),
                                   f'FLOAT64 identity changed by MXCSR setting: {label}')
                            self.tick('writer_environment_f64_unaffected')
                        else:
                            self.reject(args,env=env,label=label,
                                        sentinels=(dest,) if name=='existing' else (),
                                        stderr_contains='native WAV arithmetic environment unsupported')
                            insist(name=='existing' or not dest.exists(),
                                   f'rejected native writer created an output file: {label}')
                            self.tick('writer_environment_preopen_refusals')
        # A safe f64 destination cannot bypass the reader's FLOAT32 widening
        # requirements. The source handle is available before output open.
        source32=self.root/'fenv-native-source-f32.wav'
        self.native_generate(raw,source32,'f32',False,2,48000,2)
        converted=self.root/'fenv-f32-to-f64-safe.wav'
        self.native_copy(source32,converted,'f64',False)
        insist(parse_wave(converted)['data']==raw.read_bytes(),
               'safe FLOAT32-to-FLOAT64 native copy changed exact dyadic samples')
        self.tick('source_environment_safe_copies')
        for setting in (0x40,0x8000,0x2000,0x4000,0x6000):
            env={'LD_PRELOAD':str(self.fenv),'PCM64_TEST_MXCSR_OR':hex(setting)}
            for name,dest in (('existing',existing),('absent',absent)):
                dest.unlink(missing_ok=True)
                if name=='existing':
                    dest.write_bytes(b'PRESERVE-F32-SOURCE'*9)
                label=f'fenv-f32-source-f64-dest-{setting:x}-{name}'
                self.reject(['copy',source32,dest,'f64','L'],env=env,label=label,
                            sentinels=(dest,) if name=='existing' else (),
                            stderr_contains='native WAV: source arithmetic environment unsupported')
                insist(name=='existing' or not dest.exists(),
                       f'rejected FLOAT32 source created an output: {label}')
                self.tick('source_environment_preopen_refusals')
        self.gates['source_environment_preflight']='PASS'
        self.gates['writer_environment_preflight']='PASS'

    def preopen_input_checks(self):
        # Argument errors and physical source exhaustion are known before
        # sample transfer.  Neither may acquire or alter an output pathname.
        raw=self.file('preopen-two-frames.raw64',raw_double_words([
            ieee_f64_bits(0.25),ieee_f64_bits(-0.25),
            ieee_f64_bits(0.5),ieee_f64_bits(0.0)]))
        source=self.root/'preopen-source-f64.wav'
        self.native_generate(raw,source,'f64',False,2,48000,2)
        f32=self.root/'preopen-source-f32.wav'
        self.native_generate(raw,f32,'f32',False,2,48000,2)
        truncated=self.file('preopen-truncated-f32.wav',f32.read_bytes()[:-10])
        # Legacy accepts certain metadata variants which private native
        # access must refuse.  A copy must not create output for such input.
        invalid_header=self.file('preopen-bad-extensible.wav',wave_bytes(
            struct.pack('<d',0.25)*2,channels=2,code='f64',
            extensible=True,mask=0x4))
        cases=[
            ('copy-zero-block',['copy',source,'DEST','f64','L','0'],2,None),
            ('copy-large-block',['copy',source,'DEST','f64','L','300'],2,None),
            ('copy-abc-block',['copy',source,'DEST','f64','L','abc'],2,'bad integer'),
            ('generate-bad-count',['generate',raw,'DEST','f64','L',2,48000,2,'abc'],2,'bad integer'),
            ('generate-short-input',['generate',raw,'DEST','f64','L',2,48000,4,4],1,'short raw input'),
            ('copy-truncated-f32',['copy',truncated,'DEST','f64','L'],1,
                'source data extent exceeds'),
            ('copy-invalid-header',['copy',invalid_header,'DEST','f64','L'],1,
                'native WAV unsupported'),
            ('generate-bad-endian',['generate',raw,'DEST','f64','broken',2,48000,2,2],2,None),
            ('generate-overflow-rate',['generate',raw,'DEST','f64','L',2,1<<32,2,2],2,None),
        ]
        for title,args,expected,diagnostic in cases:
            for state in ('existing','absent'):
                dst=self.root/f'preopen-{title}-{state}.wav'
                sentinel=b'PRESERVE-WHOLE-ORIGINAL-FILE'*7
                if state=='existing': dst.write_bytes(sentinel)
                else: dst.unlink(missing_ok=True)
                actual=[str(dst) if x=='DEST' else x for x in args]
                _,err=self.invoke(actual,expect=expected,label=title+'-'+state)
                if diagnostic:
                    insist(diagnostic.lower() in err.lower(),
                           f'{title}: missing preopen diagnostic: {err}')
                if state=='existing':
                    insist(dst.read_bytes()==sentinel,
                           f'{title} overwrote a pre-existing destination')
                else:
                    insist(not dst.exists(),f'{title} created a rejected destination')
                self.tick('preopen_input_argument_refusals')
        # Deliberately mismatching declared and supplied writer frames remains
        # a *runtime* writer-count error, not a preflight rejection.
        self.gates['preopen_input_argument_validation']='PASS'

    def streaming(self):
        # A duration-independent heap limit: 350k x 6 frames with a 96 MiB
        # process virtual-address cap. Test content is constructed and
        # checked independently; no full-array allocation in the C process.
        ch=6
        frames=350000
        pattern=[0x8000000000000000,0x1,0x3cb0000000000000,
                 0x3ff0000000000000,0x4000000000000000,0x7fefffffffffffff]
        raw=self.root/'stream-input.raw64'
        block=raw_double_words(pattern)*1024
        with raw.open('wb') as f:
            for _ in range(frames//1024): f.write(block)
            f.write(raw_double_words(pattern)*(frames%1024))
        out=self.root/'stream-output.wav'
        lim=96*1024*1024
        def capped():
            resource.setrlimit(resource.RLIMIT_AS,(lim,lim))
        self.invoke(['generate',raw,out,'f64','L',ch,44100,frames,frames],
                    preexec_fn=capped,label='long-stream-96MiB-address-space')
        parsed=parse_wave(out)
        insist(len(parsed['data'])==frames*ch*8 and
               hashlib.sha256(parsed['data']).hexdigest()==digest(raw),
               'long streaming writer altered binary64 words')
        self.tick('streaming_frames',frames)
        self.tick('streaming_samples',frames*ch)
        self.tick('streaming_address_space_cap_mib',96)
        self.tick('streaming_bytes',frames*ch*8)

    def compatibility(self):
        # Check that a normal CLI WAV writer still uses the original public
        # route and that an ordinary WAV roundtrip remains functional.
        stdin=self.file('legacy-normal.wav',wave_bytes(struct.pack('<h',1234)*53,
                              channels=1,code='i16'))
        target=self.root/'legacy-output.wav'
        p=subprocess.run([str(self.sox),str(stdin),str(target)],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        self.commands.append({'label':'legacy-sox-wav-copy',
                              'argv':[str(self.sox),str(stdin),str(target)],
                              'exit':p.returncode,'stderr':p.stderr.decode('utf-8','replace')[:2000]})
        insist(p.returncode==0,'legacy SoX WAV conversion regression')
        parsed=parse_wave(target)
        insist(parsed['data']==struct.pack('<h',1234)*53,'ordinary CLI WAV payload regression')
        self.tick('legacy_cli_wav_smoke')

    def prepare_shim(self):
        source=Path(__file__).with_name('wav_fault_shim.c')
        if sys.platform!='linux':
            raise AssertionError('02A deterministic FD fault gates require Linux host')
        so=subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra',
                           '-o',str(self.root/'libwav_fault.so'),str(source),'-ldl'],
                          capture_output=True,text=True)
        insist(so.returncode==0,f'shim could not compile: {so.stderr}')
        self.shim=self.root/'libwav_fault.so'
        self.tick('fault_shim_builds')
        if platform.machine().lower() in ('x86_64','amd64','i386','i686'):
            source=Path(__file__).with_name('wav_fenv_preload.c')
            so=subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra',
                               '-o',str(self.root/'libwav_fenv.so'),str(source)],
                              capture_output=True,text=True)
            insist(so.returncode==0,f'fenv preload could not compile: {so.stderr}')
            self.fenv=self.root/'libwav_fenv.so'
            self.tick('fenv_shim_builds')

    def execute(self):
        insist(self.sox.is_file() and self.probe.is_file(),'missing binaries')
        self.prepare_shim()
        self.formats()
        self.daz_guard()
        self.quantization()
        self.malformed()
        self.safety()
        self.writer_environment()
        self.preopen_input_checks()
        self.streaming()
        self.compatibility()
        return {
            'suite':'io-wav',
            'status':'PASS_WITH_NOT_RUN' if any(
                value.startswith('NOT_RUN') for value in self.gates.values()) else 'PASS',
            'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'git_commit':git_commit(Path(__file__).resolve().parents[2]),
            'source_and_binary_sha256':{
                str(x):digest(x) for x in [self.sox,self.probe,
                   Path(__file__),Path(__file__).with_name('wav_io_probe.c'),
                   Path(__file__).with_name('wav_fault_shim.c')]},
            'seed':SEED,
            'oracles':'independent Python struct RIFF+RIFX parser/writer and Fraction rational nearest ties-away',
            'checks':self.counts,
            'gate_execution':self.gates,
            'commands':self.commands,
            'fixture_sha256':self.artifacts,
            'platform':sys.platform,
        }


def git_commit(base):
    try:
        p=subprocess.run(['git','-C',str(base),'rev-parse','HEAD'],
                         capture_output=True,text=True,timeout=10)
        return p.stdout.strip() if p.returncode==0 else None
    except FileNotFoundError:
        return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',required=True,type=Path)
    parser.add_argument('--probe',required=True,type=Path)
    parser.add_argument('--results',required=True,type=Path)
    args=parser.parse_args()
    results=args.results.resolve()
    results.mkdir(parents=True,exist_ok=True)
    receipt=results/'io-wav.json'
    receipt.unlink(missing_ok=True)
    runner=CaseRunner(args.sox.resolve(),args.probe.resolve(),results)
    try:
        record=runner.execute()
    except Exception as exc:
        record={'suite':'io-wav','status':'FAIL',
                'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'error':f'{type(exc).__name__}: {exc}',
                'completed_checks':runner.counts,
                'gate_execution':runner.gates,
                'commands':runner.commands}
        receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print('FAIL io-wav:',record['error'],file=sys.stderr)
        return 1
    receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(record['status']+' io-wav:',json.dumps(record['checks'],sort_keys=True))
    return 0


if __name__=='__main__':
    sys.exit(main())
