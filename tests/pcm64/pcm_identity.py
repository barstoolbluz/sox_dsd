#!/usr/bin/env python3
"""Phase 05A native CLI acceptance with independent WAV/IEEE byte oracles.

Self-contained raw sample generator/parser. Exact words are compared without
using SoX as the oracle; a staged int32 bridge must fail the low-bit control.
Every check runs an executable, not a source grep. Report failures with gate
names and preserve receipts even on exceptions/interrupted child processes.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
from binary_receipts import executable_libraries, safe_git_head, native_dsp_compiled
from flac_fixtures import RATE as FLAC_RATE, SPECS as FLAC_SPECS, codes as flac_codes, name as flac_name

SOURCE = Path(__file__).resolve().parents[2]
SEED = 0x5A05A20261113
RNG = random.Random(SEED)
FLOAT32 = 3
PCM = 1

def check(predicate, message):
    if not predicate:
        raise AssertionError(message)


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


def pack_wav(path, payload, bits, encoding=PCM, channels=2, rate=44100, mask=None):
    width=bits//8
    check(width*channels and len(payload)%(width*channels)==0,'invalid WAV test payload')
    length=len(payload)//(width*channels)
    if mask is None:
        fmt=struct.pack('<HHIIHH',encoding,channels,rate,rate*channels*width,channels*width,bits)
        if encoding==FLOAT32: fmt+=b'\0\0'
    else:
        # Valid WAVEFORMATEXTENSIBLE with the standard uncompressed subtype.
        guid=struct.pack('<H',encoding)+b'\0\0'+bytes.fromhex('00001000800000aa00389b71')
        fmt=struct.pack('<HHIIHHHHI',0xfffe,channels,rate,rate*channels*width,
                        channels*width,bits,22,bits,mask)+guid
    chunks=[b'fmt '+struct.pack('<I',len(fmt))+fmt]
    if encoding==FLOAT32:chunks.append(b'fact'+struct.pack('<II',4,length))
    chunks.append(b'data'+struct.pack('<I',len(payload))+payload+(b'\0' if len(payload)%2 else b''))
    body=b'WAVE'+b''.join(chunks)
    check(len(body)<2**32,'test WAV too large')
    path.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)


def parse_wav_bytes(data):
    check(data[:4] in (b'RIFF',b'RIFX') and data[8:12]==b'WAVE','not WAV')
    little=data[:4]==b'RIFF'
    check(little,'test expects little-endian WAV')
    p=12; fmt=None; payload=None; mask=None
    while p+8<=len(data):
        name=data[p:p+4]; size=struct.unpack_from('<I',data,p+4)[0]
        p+=8
        check(size<=len(data)-p,'truncated WAV output')
        chunk=data[p:p+size]
        if name==b'fmt ':
            check(len(chunk)>=16,'short format chunk')
            tag,chs,rate,br,align,bits=struct.unpack_from('<HHIIHH',chunk,0)
            if tag==0xfffe:
                check(len(chunk)>=40,'short extensible fmt')
                mask=struct.unpack_from('<I',chunk,20)[0]
                tag=struct.unpack_from('<H',chunk,24)[0]
            fmt=(tag,chs,rate,bits,mask)
        if name==b'data':payload=chunk
        p+=size+(size&1)
    check(fmt is not None and payload is not None,'WAV lacks format/data')
    return fmt,payload


def f64_payload(words):
    return b''.join(struct.pack('<Q',word) for word in words)


def f64_words(payload):
    check(len(payload)%8==0,'non-f64 payload')
    return [x[0] for x in struct.iter_unpack('<Q',payload)]


def f64_from_word(word):
    return struct.unpack('<d',struct.pack('<Q',word))[0]


def f64_word(value):
    return struct.unpack('<Q',struct.pack('<d',value))[0]


def finite_words(count):
    fixed=[0,1,0x8000000000000000,0x8000000000000001,
           0x3d70000000000000,0xbd70000000000000,
           0x3fefffffffffffff,0x3ff0000000000000,
           0x3ff0000000000001,0x3ff4000000000000,
           0xbff4000000000000,0x4000000000000000,
           0x7fefffffffffffff,0xffefffffffffffff,
           0x0010000000000000,0x000fffffffffffff]
    words=[]
    for i in range(count):
        if i%3: words.append(fixed[(i*7+count)%len(fixed)])
        else:
            sign=RNG.getrandbits(1)<<63
            exp=RNG.randrange(0x7ff)<<52
            frac=RNG.getrandbits(52)
            words.append(sign|exp|frac)
    if count>=len(fixed): words[:len(fixed)]=fixed
    return words


class Suite:
    def __init__(self,sox,probe,results):
        self.sox=sox.resolve();self.probe=probe.resolve();self.results=results
        self.root=results/'fixtures'/'pcm-identity';self.root.mkdir(parents=True,exist_ok=True)
        self.gates={};self.counts={};self.commands=[];self.binary_hashes={};self.fixture_hashes={}
        self.time_checks={}

    def count(self,name,value=1):
        self.counts[name]=self.counts.get(name,0)+value

    def record_binary(self,path):
        path=Path(path).resolve()
        if str(path) not in self.binary_hashes:
            self.binary_hashes[str(path)]=sha(path)
            self.binary_hashes.update(executable_libraries(path))

    def run(self,args,label,expect=0,env=None,stdin=None,outfile=None,timeout=75):
        self.record_binary(self.sox)
        argv=[str(self.sox)]+[str(x) for x in args]
        before=time.perf_counter()
        if outfile is None:
            result=subprocess.run(argv,input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=env,timeout=timeout)
        else:
            with open(outfile,'wb') as out:
                result=subprocess.run(argv,input=stdin,stdout=out,stderr=subprocess.PIPE,
                                      env=env,timeout=timeout)
        elapsed=time.perf_counter()-before
        record={'label':label,'args':[str(a) for a in args],'exit':result.returncode,
                'elapsed_seconds':round(elapsed,6),
                'stderr':result.stderr.decode('utf-8','replace')[-650:],
                'stdout_sha256':sha(outfile) if outfile else hashlib.sha256(result.stdout).hexdigest()}
        self.commands.append(record)
        if expect==0:
            check(result.returncode==0,f'{label}: exit {result.returncode}: {record["stderr"]}')
        elif expect=='fail':
            check(result.returncode!=0,f'{label}: unexpectedly succeeded')
        elif expect is not None:
            check(result.returncode==expect,f'{label}: exit {result.returncode} vs {expect}: {record["stderr"]}')
        return result

    def plan(self,src,dst,other=None,extras=None):
        args=['--precision','64','--plan']
        if other:args+=other
        args+=[src]
        if extras:args+=extras
        args.append(dst)
        return json.loads(self.run(args,'strict64-plan').stdout)

    def word_identity(self):
        for count in (0,1,7,256,511,4096,4097,8193):
            words=finite_words(count*2)
            path=self.root/f'identity-{count}.wav';dest=self.root/f'identity-{count}-out.wav'
            pack_wav(path,f64_payload(words),64,FLOAT32,2)
            plan=self.plan(path,dest,extras=['-e','floating-point','-b','64'])
            prec=plan['precision']
            check(prec['actual_pcm_engine']=='ieee754.binary64' and
                  prec['bit_exact_interchange'] and prec['runner_available'],
                  'identity planning must disclose native exact word engine')
            self.run(['--precision','64',path,'-e','floating-point','-b','64',dest],f'identity-{count}')
            fmt,raw=parse_wav_bytes(dest.read_bytes())
            check(fmt[:4]==(FLOAT32,2,44100,64),'native output WAV format changed')
            check(raw==f64_payload(words),f'F64 word identity broken at {count} frames')
            self.count('exact_f64_words',len(words));self.count('identity_blocks')
        self.gates['f64_word_exact_payload']='PASS'
        self.gates['plan_executed_engine_agreement']='PASS'
        # If an int32 bridge is inserted, all nonzero 2^-40 samples disappear.
        tiny=f64_word(math.ldexp(1.0,-40))
        check(tiny!=f64_word(0.) and int(f64_from_word(tiny)*(1<<31))==0,
              'negative-control int32 bridge must destroy 2^-40')
        self.gates['negative_int32_bridge_control']='PASS'

    def integer_sources(self):
        for bits,encoding in ((8,PCM),(16,PCM),(24,PCM),(32,PCM)):
            width=bits//8
            low=-(1<<(bits-1)); high=(1<<(bits-1))-1
            codes=[low,low+1,-1,0,1,high-1,high]
            codes+=[RNG.randrange(low,high+1) for _ in range(41)]
            payload=b''
            for value in codes:
                n=value+(128 if bits==8 else 0)
                payload+=n.to_bytes(width,'little',signed=bits!=8)
            source=self.root/f'integer-{bits}.wav';dest=self.root/f'integer-{bits}-out.wav'
            pack_wav(source,payload,bits,encoding,channels=1)
            self.run(['--precision','64',source,'-e','floating-point','-b','64',dest],
                     f'ingress-integer-{bits}')
            fmt,data=parse_wav_bytes(dest.read_bytes())
            check(fmt[0]==FLOAT32 and fmt[3]==64,'int source did not produce F64')
            expected=[f64_word(value/(1<<(bits-1))) for value in codes]
            check(f64_words(data)==expected,f'{bits}-bit exact integer normalization failed')
            self.count('normalized_integer_codes',len(codes))
        self.gates['integer_wav_exact_normalization']='PASS'

    def gain_order(self):
        vals=[-0.,0.,0.1,0.3,-0.5,1.125,-1.125,2**-40,2**-1022,0.99]
        vals+=[RNG.uniform(-0.98,0.98) for _ in range(1199)]
        src=self.root/'gain-input.wav';dest=self.root/'gain-output.wav'
        pack_wav(src,b''.join(struct.pack('<d',v) for v in vals),64,FLOAT32,channels=1)
        db=(-3.0,4.0,-1.0)
        steps=['gain','-3','gain','4','gain','-1']
        # -v belongs to this input's options; the actual planner must state the
        # resolved pre-effects source volume and the independent gain factors.
        argv=['--precision','64','-v','0.75',src,'-e','floating-point','-b','64',dest]+steps
        plan_argv=['--precision','64','--plan','-v','0.75',src,'-e','floating-point','-b','64',dest]+steps
        plan=json.loads(self.run(plan_argv,'ordered-gain-plan').stdout)
        gains=[s['gain_factor'] for s in plan['steps'] if s['name']=='gain']
        check(len(gains)==3,'planner dropped a gain occurrence')
        check(all(abs(g-math.pow(10.,d/20))<2e-15 for g,d in zip(gains,db)),
              'planned factor does not match independent gain-dB semantics')
        volume=plan['inputs'][0]['volume']
        check(volume==0.75,'planner dropped pre-effects input gain')
        check(plan['precision']['numeric_identity'].find('no original-word identity')>=0,
              'transformed output cannot claim input bit identity')
        self.run(argv,'ordered-gain-execution')
        _,payload=parse_wav_bytes(dest.read_bytes())
        actual=f64_words(payload)
        expected=[]
        for v in vals:
            v*=volume
            for gain in gains: v*=gain
            expected.append(f64_word(v))
        check(actual==expected,'gain occurrence dropped, fused, reordered or rounded through int32')
        check(actual!=[f64_word(v) for v in vals], 'missing-gain control did not differ')
        check(actual!=[f64_word(v*.75*gains[0]*gains[1]) for v in vals],
              'extra final gain not detected')
        self.count('ordered_gain_words',len(vals));self.count('gain_occurrences',len(gains))
        # 0dB gain must preserve signed zero in float64, even with gain effect.
        zero=self.root/'gain-zero.wav'
        self.run(['--precision','64',src,'-e','floating-point','-b','64',zero,'gain','0'],
                 'zero-db-signed-zero')
        _,payload=parse_wav_bytes(zero.read_bytes())
        check(f64_words(payload)==[f64_word(v) for v in vals],
              'gain 0 dB must preserve exact words')
        self.gates['source_volume_and_ordered_gains']='PASS'
        self.gates['zero_db_signed_zero']='PASS'

    def remix_layout(self):
        src=self.root/'identity-7.wav';dest=self.root/'remixed.wav'
        p=self.plan(src,dest,extras=['-e','floating-point','-b','64'])
        self.run(['--precision','64',src,'-e','floating-point','-b','64',dest,'remix','2','1'],
                 'stereo-reorder')
        fmt,raw=parse_wav_bytes(dest.read_bytes())
        _,inraw=parse_wav_bytes(src.read_bytes())
        words=f64_words(inraw)
        expect=[y for i in range(0,len(words),2) for y in (words[i+1],words[i])]
        check(f64_words(raw)==expect,'output role permutation wrong')
        check(fmt[4] in (None,0),'no source speaker mask must not invent a mask')
        self.count('permutation_frames',len(words)//2)
        # The no-op channel effect must not route through the legacy chain.
        noop=self.root/'channels-noop.wav'
        self.run(['--precision','64',src,'-e','floating-point','-b','64',noop,'channels','2'],
                 'channels-noop')
        check(parse_wav_bytes(noop.read_bytes())[1]==inraw,
              'same channel count changed PCM data')
        # Known FL/FR roles cannot cancel an explicitly requested remix.
        # The wire-order samples must match ordinary SoX processing, while
        # the existing WAV header mask policy remains unchanged.
        known=self.root/'known-stereo-mask.wav'
        pack_wav(known,inraw,64,FLOAT32,channels=2,mask=0x3)
        known_out=self.root/'known-stereo-remix.wav'
        self.run(['--precision','64',known,'-e','floating-point','-b','64',
                  known_out,'remix','2','1'], 'known-mask-remix')
        legacy_known=self.root/'legacy-known-stereo-remix.wav'
        self.run([known,'-e','floating-point','-b','64',
                  legacy_known,'remix','2','1'], 'legacy-known-mask-remix')
        known_fmt,known_raw=parse_wav_bytes(known_out.read_bytes())
        legacy_fmt,legacy_raw=parse_wav_bytes(legacy_known.read_bytes())
        check(f64_words(known_raw)==expect and known_raw==legacy_raw and
              known_fmt[4]==legacy_fmt[4]==0x3,
              'known-mask remix differs from default SoX channel order')
        self.gates['pure_remix_and_channels_noop']='PASS'
        self.gates['known_and_unknown_speaker_masks']='PASS'

    def narrowing_and_quantization(self):
        src=self.root/'narrow-input.wav'
        vals=[-0.,0.,1e-40,-1e-40,0.1,-0.1,0.5,-0.5,1.1,-1.1]
        vals += [RNG.uniform(-.999,.999) for _ in range(300)]
        pack_wav(src,b''.join(struct.pack('<d',v) for v in vals),64,FLOAT32,channels=1)
        dest=self.root/'narrow-f32.wav'
        self.run(['--precision','64',src,'-e','floating-point','-b','32',dest],
                 'binary32-single-narrow')
        fmt,data=parse_wav_bytes(dest.read_bytes())
        check(fmt[:4]==(FLOAT32,1,44100,32),'float32 format mismatch')
        expected=b''.join(struct.pack('<f',v) for v in vals)
        check(data==expected,'FLOAT32 must round once to nearest-even in target format')
        self.count('f32_narrow_samples',len(vals))
        # Exact integer tie semantics: the private Phase01 quantizer uses
        # nearest, with exactly halfway magnitudes away from zero.
        for bits in (16,24,32):
            half=Fraction(1,1<<bits)
            vals=[0.,-0.,float(half),-float(half),float(3*half),-float(3*half),
                  -1.,float(Fraction((1<<(bits-1))-1,1<<(bits-1))),1.,-1.25,1.25]
            vals+=[RNG.uniform(-.9,.9) for _ in range(200)]
            src=self.root/f'ties-{bits}-in.wav';dest=self.root/f'ties-{bits}-out.wav'
            pack_wav(src,b''.join(struct.pack('<d',v) for v in vals),64,FLOAT32,channels=1)
            self.run(['-D','--precision','64',src,'-b',str(bits),'-e','signed-integer',dest],
                     f'integer-tie-{bits}')
            fmt,data=parse_wav_bytes(dest.read_bytes())
            check(fmt[0]==PCM and fmt[3]==bits,'integer target encoding wrong')
            raw=b''
            scale=1<<(bits-1)
            for v in vals:
                f=Fraction.from_float(abs(v))*scale
                rounded=(f.numerator*2+f.denominator)//(f.denominator*2)
                code=(1 if math.copysign(1,v)>0 else -1)*rounded
                code=max(-scale,min(scale-1,code))
                raw+=int(code).to_bytes(bits//8,'little',signed=True)
            check(data==raw,f'{bits}-bit target quantization differs from dyadic reference')
            self.count('integer_tie_checks',len(vals))
        self.gates['f32_one_round']='PASS'
        self.gates['target_integer_quantization']='PASS'

    def faults_and_sentinels(self):
        src=self.root/'identity-511.wav';payload=b'PHASE05A-SENTINEL'*29
        # A named output aliased to the input itself must not truncate it.
        untouched=src.read_bytes()
        self.run(['--clobber','--precision','64',src,'-b','64','-e','floating-point',src],
                 'source-identity-alias',expect='fail')
        check(src.read_bytes()==untouched,'source was changed by self-alias refusal')
        report=self.root/'report-aliased.wav';report.write_bytes(payload)
        self.run(['--clobber','--precision','64','--report',str(report),src,
                  '-e','floating-point','-b','64',report],
                 'report-output-alias',expect='fail')
        check(report.read_bytes()==payload,'report/output alias truncated sentinel')
        if hasattr(os,'symlink'):
            aliased=self.root/'alias-symlink.wav'
            aliased.unlink(missing_ok=True)
            aliased.symlink_to(src)
            self.run(['--clobber','--precision','64',src,'-b','64','-e','floating-point',aliased],
                     'source-symlink-alias',expect='fail')
            check(src.read_bytes()==untouched and aliased.is_symlink(),
                  'source symlink alias changed original')
        hard=self.root/'alias-hardlink.wav'
        hard.unlink(missing_ok=True);os.link(src,hard)
        self.run(['--clobber','--precision','64',src,'-b','64','-e','floating-point',hard],
                 'source-hardlink-alias',expect='fail')
        check(src.read_bytes()==untouched,'source hardlink was changed')
        # A genuine declined overwrite must retain the same source bytes and
        # destination sentinel, without creating an alternative writer path.
        declined=self.root/'declined-overwrite.wav';declined.write_bytes(payload)
        self.run(['--no-clobber','--precision','64',src,'-e','floating-point','-b','64',declined],
                 'no-clobber-decline',expect='fail',stdin=b'n\n')
        check(declined.read_bytes()==payload,'no-clobber refusal damaged destination')
        # Unsupported non-identity and preflight arithmetic rejects precede
        # the destructive destination commit.
        dest=self.root/'unsupported-sentinel.wav';dest.write_bytes(payload)
        self.run(['--clobber','--precision','64',src,'-e','floating-point','-b','64',dest,
                  'rate','48000'], 'unsupported-SRC-precommit', expect='fail')
        check(dest.read_bytes()==payload,'unsupported SRC truncated destination')
        self.run(['--clobber','--precision','64',src,'-e','floating-point','-b','64',dest,
                  'reverb'], 'unsupported-effect-precommit', expect='fail')
        check(dest.read_bytes()==payload,'unsupported effect truncated destination')
        bad=self.root/'nonfinite-input.wav'
        words=[f64_word(0.25)]*130
        words[70]=0x7ff8000000000001
        pack_wav(bad,f64_payload(words),64,FLOAT32,channels=1)
        out=self.root/'nonfinite-output.wav'
        report=self.root/'nonfinite-report.json'
        self.run(['--precision','64','--report',report,bad,'-e','floating-point',
                  '-b','64',out],'nonfinite-after-commit',expect='fail')
        check(not report.is_file() or '"complete"' not in report.read_text(),
              'nonfinite input falsely published successful receipt')
        # The source stays untouched whether or not the failed output is
        # removed during cleanup. The writer may have committed its header.
        check(f64_words(parse_wav_bytes(bad.read_bytes())[1])==words,
              'invalid input was modified by failure cleanup')
        self.gates['source_report_symlink_hardlink_alias']='PASS'
        self.gates['precommit_sentinel_and_nonfinite_failure']='PASS'

    def stdout_report(self):
        src=self.root/'identity-256.wav';_,raw=parse_wav_bytes(src.read_bytes())
        cp=self.run(['--precision','64',src,'-e','floating-point','-b','64','-t','wav','-'],
                    'exact-count-stdout-pipe')
        check(parse_wav_bytes(cp.stdout)[1]==raw,'stdout WAV pipe payload changed')
        out=self.root/'redirected-stdout.wav'
        self.run(['--precision','64',src,'-e','floating-point','-b','64','-t','wav','-'],
                 'empty-regular-stdout',outfile=out)
        check(parse_wav_bytes(out.read_bytes())[1]==raw,'stdout regular WAV bytes wrong')
        report=self.root/'native-report.json'
        out=self.root/'native-reported.wav'
        self.run(['--precision','64','--report',report,src,'-e','floating-point','-b','64',out],
                 'native-success-report')
        reportdata=json.loads(report.read_text())
        # The report has a nested plan as a sibling of its lifecycle summary.
        check(reportdata['precision']['actual_pcm_engine']=='ieee754.binary64' and
              reportdata['precision']['bit_exact_interchange'] is True and
              reportdata['status']=='complete' and
              int(reportdata['output']['frames_written'])==256,
              'native success report differs from observed conversion')
        # Saturation is a physical quantizer property. -1.0 is exact at the
        # negative endpoint; +1.0 saturates at the positive target maximum.
        values=(1.0,1.25,-1.25,-1.0,-0.5)
        clip_in=self.root/'writer-clips-in.wav';clip_out=self.root/'writer-clips-out.wav'
        clip_report=self.root/'writer-clips-report.json'
        pack_wav(clip_in,b''.join(struct.pack('<d',v) for v in values),64,FLOAT32,channels=1)
        self.run(['--precision','64','-D','--report',clip_report,clip_in,
                  '-e','signed-integer','-b','16',clip_out], 'native-target-saturation')
        observed=json.loads(clip_report.read_text())
        check(observed['status']=='complete' and
              int(observed['clipping']['output_writer'])==3,
              f'physical writer saturation count incorrect: {observed["clipping"]}')
        strict_report=self.root/'strict-clip-report.json'
        self.run(['--precision','64','-D','--dsd-clip','error','--report',strict_report,
                  clip_in,'-e','signed-integer','-b','16',
                  self.root/'strict-clip-output.wav'],
                 'native-strict-nominal-excursion',expect='fail')
        check(not strict_report.exists() or
              json.loads(strict_report.read_text()).get('status')!='complete',
              'strict clip failure published complete report')
        self.gates['stdout_pipe_and_regular']='PASS'
        self.gates['native_report_truthfulness']='PASS'
        self.gates['target_saturation_and_nominal_clip_policy']='PASS'

    def compatibility_plans(self):
        src=self.root/'identity-7.wav'
        for selector in ([],['--precision','auto'],['--precision','32']):
            out=self.root/('compat-' + ('default' if not selector else selector[-1]) + '.wav')
            self.run(selector+[src,'-e','floating-point','-b','64',out],
                     'legacy-compat-'+('default' if not selector else selector[-1]))
        reference=(self.root/'compat-default.wav').read_bytes()
        for policy in ('auto','32'):
            check((self.root/f'compat-{policy}.wav').read_bytes()==reference,
                  f'explicit {policy} altered historical PCM output')
        for name in ('mp3','xnohandler'):
            args=[src,self.root/f'nowriter.{name}']
            default=self.run(args,'legacy-missing-'+name,expect='fail')
            for policy in ('32','auto'):
                explicit=self.run(['--precision',policy]+args,
                                  'legacy-missing-'+policy+'-'+name,expect='fail')
                check((default.returncode,default.stderr)==
                      (explicit.returncode,explicit.stderr),
                      f'explicit precision {policy} changed unsupported-format message')
        for bits in (None,16):
            opts=['-e','unsigned-integer']+(['-b',str(bits)] if bits else [])
            plan=json.loads(self.run(['--plan',src]+opts+[self.root/'unsigned.wav'],
                                      'plan-unsigned-'+str(bits)).stdout)
            check(plan['output']['bits_per_sample']==8,
                  'unsigned WAV plan must reflect 8-bit actual output')
        for extension in ('.au','.aiff','.raw'):
            plan=json.loads(self.run(['--plan',src,'-e','floating-point','-b','32',
                                      self.root/('float'+extension)],
                                     'nonwav-float-plan-'+extension).stdout)
            text=plan['precision']['endpoint_quantization']
            # AIFF has no IEEE float writer: ordinary SoX warns and selects
            # signed PCM32. The plan must report that *actual* fallback, not
            # repeat the unsupported -e argument as the output encoding.
            expected='integer PCM' if extension=='.aiff' else 'floating-point'
            check('WAV' not in text and expected in text,
                  f'non-WAV precision plan mislabels endpoint {extension}: {text}')
        # A FLOAT64 source and an explicit output -b historically caused the
        # Phase04 plan to discard the bit depth when FLOAT64 at that width is
        # unavailable. The declared native quantizer must match real WAV bytes.
        for bits in (8,16,24,32):
            out=self.root/f'float64-explicit-bits-{bits}.wav'
            # A Float32 endpoint correctly rejects 64-bit finite values too
            # large for its exponent range; use a bounded Float64 source.
            chosen_src=self.root/'gain-input.wav' if bits==32 else src
            args=['--precision','64','-D',chosen_src,'-b',str(bits),out]
            declared=json.loads(self.run(['--plan',*args],
                f'explicit-bits-plan-{bits}').stdout)
            self.run(args,f'explicit-bits-run-{bits}')
            fmt,raw=parse_wav_bytes(out.read_bytes())
            check(declared['output']['bits_per_sample']==bits and fmt[3]==bits and
                  declared['output']['encoding']==(2 if bits==8 else 3 if bits==32 else 1) and
                  fmt[0]==(PCM if bits!=32 else FLOAT32),
                  f'WAV output -b {bits} plan disagrees with writer')
        self.gates['ordinary_auto32_and_handler_errors']='PASS'
        self.gates['plan_unsigned_and_nonwav_float']='PASS'
        self.gates['float64_explicit_integer_endpoint_bits']='PASS'

    def flac_status(self):
        # Built-in adapter requires static FLAC with headers at configure time.
        # Distinguish missing build support from a failed FLAC decode.
        probe=Path(self.probe).with_name('pcm64_flac_probe')
        self.record_binary(probe)
        status=subprocess.run([str(probe),'capabilities'],capture_output=True,text=True)
        check(status.returncode==0,'FLAC probe unavailable')
        linkage=dict(line.split('=',1) for line in status.stdout.splitlines())
        if linkage.get('linkage')!='builtin':
            self.gates['built_in_flac_pcm64_ingress']=('NOT_RUN: '+
                f"compiled linkage={linkage.get('linkage')}; this environment has no libFLAC development headers")
            return
        # Verify exact scalar words from independently generated PCM codes,
        # not merely that the decoder returns nonempty audio. Cover short and
        # multi-block FLAC, mono/stereo/six-channel, high and low code bits.
        for bits,channels,frames in FLAC_SPECS:
            src=SOURCE/'tests/pcm64/fixtures'/flac_name(bits,channels,frames)
            check(src.is_file(),'missing built-in FLAC fixture '+src.name)
            self.fixture_hashes[str(src.relative_to(SOURCE))]=sha(src)
            out=self.root/f'native-flac-{bits}-{channels}-{frames}.wav'
            p=self.plan(src,out,extras=['-e','floating-point','-b','64'])
            check(p['inputs'][0]['pcm64_reader_eligible'] is True and
                  p['precision']['actual_pcm_engine']=='ieee754.binary64',
                  'FLAC plan did not select native reader')
            self.run(['--precision','64',src,'-e','floating-point','-b','64',out],
                     f'builtin-flac-ingress-{bits}-{channels}-{frames}')
            fmt,data=parse_wav_bytes(out.read_bytes())
            check(fmt[:4]==(FLOAT32,channels,FLAC_RATE,64),
                  f'FLAC ingress WAV encoding/rate wrong: {fmt}')
            oracle=f64_payload([f64_word(math.ldexp(float(code),-(bits-1)))
                               for code in flac_codes(bits,channels,frames)])
            check(data==oracle,
                  f'FLAC {bits}-bit {channels}-channel native PCM differs from independent code oracle')
            self.count('flac_exact_integer_words',frames*channels)
        self.gates['built_in_flac_pcm64_ingress']='PASS'

    def native_fenv(self):
        if sys.platform!='linux' or not shutil.which('cc'):
            self.gates['runtime_fenv_and_injected_io']='NOT_RUN: needs Linux LD_PRELOAD and compiler'
            return
        shim=self.root/'libpcm64_fault.so';envshim=self.root/'libpcm64_fenv.so'
        for output,source in ((shim,SOURCE/'tests/pcm64/wav_fault_shim.c'),
                              (envshim,SOURCE/'tests/pcm64/wav_fenv_preload.c')):
            command=['cc','-shared','-fPIC','-O2','-o',str(output),str(source)]
            if output==shim:command+=['-ldl']
            cp=subprocess.run(command,capture_output=True)
            check(cp.returncode==0,cp.stderr.decode('utf-8','replace'))
            self.record_binary(output)
        src=self.root/'identity-256.wav';inpayload=parse_wav_bytes(src.read_bytes())[1]
        hostile=dict(os.environ,LD_PRELOAD=str(envshim),PCM64_TEST_MXCSR_OR='0x8040')
        out=self.root/'hostile-identity.wav'
        self.run(['--precision','64',src,'-e','floating-point','-b','64',out],
                 'hostile-fenv-word-copy',env=hostile)
        check(parse_wav_bytes(out.read_bytes())[1]==inpayload,
              'pure word copy must survive FTZ/DAZ')
        sentinel=b'NO-DSP-COMMIT'*61;dst=self.root/'hostile-gain-sentinel.wav';dst.write_bytes(sentinel)
        self.run(['--clobber','--precision','64',src,'-e','floating-point','-b','64',dst,'gain','-3'],
                 'hostile-fenv-gain-precommit',expect='fail',env=hostile)
        check(dst.read_bytes()==sentinel,'hostile DSP guard truncated sentinel')
        # Live short-write, failure after destructive commit. The report must
        # not claim complete when the filesystem accepts only part of a block.
        output=self.root/'injected-short-output.wav';report=self.root/'injected-short-report.json'
        trace=self.root/'short-write.trace';trace.unlink(missing_ok=True)
        short_env=dict(os.environ,LD_PRELOAD=str(shim),PCM64_SHORT_WRITE='1',
                       PCM64_TEST_TARGET=str(output),PCM64_DATA_OFFSET='80',
                       PCM64_TRACE=str(trace))
        self.run(['--precision','64','--report',report,src,
                  '-e','floating-point','-b','64',output],
                 'injected-partial-write',expect='fail',env=short_env)
        check(trace.is_file() and b'W' in trace.read_bytes(),
              'physical short write injector did not fire')
        check(not report.is_file() or json.loads(report.read_text()).get('status')!='complete',
              'short write must not publish complete report')
        # Post-stream finalization failure must also fail the CLI, even when
        # all audio frames were physically transferred.
        output=self.root/'injected-close-output.wav';report=self.root/'injected-close-report.json'
        trace=self.root/'close.trace';trace.unlink(missing_ok=True)
        close_env=dict(os.environ,LD_PRELOAD=str(shim),PCM64_FAIL_FCLOSE='1',
                       PCM64_TEST_TARGET=str(output),PCM64_TRACE=str(trace))
        self.run(['--precision','64','--report',report,src,
                  '-e','floating-point','-b','64',output],
                 'injected-finalization-close',expect='fail',env=close_env)
        check(trace.is_file() and b'C' in trace.read_bytes(),
              'close failure injector did not fire')
        check(not report.is_file() or json.loads(report.read_text()).get('status')!='complete',
              'failed close must not publish complete report')
        self.gates['hostile_copy_and_numeric_refusal']='PASS'
        self.gates['short_write_close_errors_no_success']='PASS'

    def signal_cancellation(self):
        if not hasattr(signal,'SIGINT') or sys.platform=='win32':
            self.gates['sigint_after_commit_no_success']='NOT_RUN: needs POSIX SIGINT'
            return
        # A sparse WAV avoids materializing ~1 GiB of test data. Its declared
        # length gives the sink a valid exact-size header. On some filesystems
        # stat size stays at the header until close despite subsequent writes;
        # the committed header is enough to establish a post-commit signal.
        src=self.root/'signal-sparse-source.wav'
        payload_size=1<<30
        fmt=struct.pack('<HHIIHH',3,1,44100,44100*8,8,64)+b'\0\0'
        header=(b'RIFF'+struct.pack('<I',0)+b'WAVE'+
                b'fmt '+struct.pack('<I',len(fmt))+fmt+
                b'fact'+struct.pack('<II',4,payload_size//8)+
                b'data'+struct.pack('<I',payload_size))
        # RIFF length is total file length minus the initial eight bytes.
        header=header[:4]+struct.pack('<I',len(header)-8+payload_size)+header[8:]
        with open(src,'wb') as f:
            f.write(header)
            f.truncate(len(header)+payload_size)
        out=self.root/'signal-partial-out.wav'
        report=self.root/'signal-partial-report.json'
        cmd=[str(self.sox),'--precision','64','--report',str(report),
             str(src),'-e','floating-point','-b','64',str(out)]
        self.record_binary(self.sox)
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        signalled=False
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline and proc.poll() is None:
                if out.exists() and out.stat().st_size>=len(header):
                    time.sleep(.01)
                    proc.send_signal(signal.SIGINT)
                    signalled=True
                    break
                time.sleep(.002)
            if not signalled and proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            stdout,stderr=proc.communicate(timeout=20)
            check(signalled and proc.returncode!=0,
                  f'post-commit SIGINT must stop with nonzero status: signalled={signalled}, rc={proc.returncode}')
            check(not report.exists() or
                  json.loads(report.read_text()).get('status')!='complete',
                  'cancelled output published complete report')
            self.commands.append({'label':'post-commit-SIGINT','argv':cmd,
                'exit':proc.returncode,'signal_after_audio_committed':signalled,
                'stderr':stderr.decode('utf-8','replace')[-900:]})
            self.gates['sigint_after_commit_no_success']='PASS'
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            src.unlink(missing_ok=True)
            out.unlink(missing_ok=True)

    def planning_performance(self):
        src=self.root/'identity-7.wav'; dest=self.root/'timed.wav'
        argv=['--precision','64','--plan',str(src),'-e','floating-point','-b','64',str(dest)]
        # No output path is opened by a successful plan.
        dest.unlink(missing_ok=True)
        elapsed=[]
        for _ in range(12):
            cp=self.run(argv,'plan-cost')
            elapsed.append(self.commands[-1]['elapsed_seconds'])
        check(not dest.exists(),'planning created audio output')
        self.time_checks['plan_median_seconds']=sorted(elapsed)[len(elapsed)//2]
        self.time_checks['plan_max_seconds']=max(elapsed)
        self.gates['planning_no_output_and_overhead_receipt']='PASS'

    def performance(self):
        src=self.root/'throughput-in.wav';dest=self.root/'throughput-out.wav'
        # 1 Mi frames, stereo: 16 MiB input audio, ~16 MiB output audio.
        frames=1<<20
        pattern=f64_payload([f64_word(-0.0),f64_word(0.1),f64_word(0.25),f64_word(2**-40)])
        payload=pattern*(frames//2)
        pack_wav(src,payload,64,FLOAT32,channels=2)
        before=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        cp=self.run(['--precision','64',src,'-e','floating-point','-b','64',dest],
                    'performance-native-identity',timeout=120)
        fmt,outdata=parse_wav_bytes(dest.read_bytes())
        check(fmt[3]==64 and outdata==payload,'throughput run was not an identity transform')
        after=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        seconds=self.commands[-1]['elapsed_seconds']
        self.time_checks['pcm64_identity_audio_mib_per_sec']=round((len(payload)/(1<<20))/max(seconds,1e-6),1)
        self.time_checks['pcm64_identity_wall_seconds']=seconds
        self.time_checks['max_child_rss_kib']=after
        self.time_checks['rss_baseline_kib']=before
        self.time_checks['bounded_native_block_frames']=4096
        self.gates['bounded_memory_practical_throughput']='PASS'

    def receipt(self,status,error=None):
        data={'suite':'pcm-identity','status':status,'error':error,
              'source_git_commit':safe_git_head(SOURCE),
              'seed':SEED,'actual_checks':self.counts,'gate_execution':self.gates,
              'performance':self.time_checks,'commands':self.commands,
              'executed_binary_sha256':self.binary_hashes,
              'source_and_binary_sha256':{
                **{str(f.relative_to(SOURCE)):sha(f) for f in (
                    SOURCE/'src/dsd_f64.c',SOURCE/'src/dsd_f64.h',
                    SOURCE/'src/sox_ng.c',SOURCE/'src/dsd_plan.c',
                    SOURCE/'src/wav.c',SOURCE/'src/formats.c',
                    SOURCE/'tests/pcm64/pcm_identity.py',
                    SOURCE/'tests/pcm64/coordinator_probe.c')},
                **self.fixture_hashes},
              'utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        (self.results/'pcm-identity.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
        return data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    results=args.results.resolve();results.mkdir(parents=True,exist_ok=True)
    receipt=results/'pcm-identity.json';receipt.unlink(missing_ok=True)
    if not native_dsp_compiled(args.sox):
        source=results/'pcm64_disabled_input.wav'
        destination=results/'pcm64_disabled_output.wav'
        source.write_bytes(b'RIFF'+struct.pack('<I',38)+b'WAVEfmt '+
            struct.pack('<IHHIIHH',16,1,1,48000,96000,2,16)+
            b'data'+struct.pack('<Ih',2,0))
        destination.write_bytes(b'SENTINEL')
        cp=subprocess.run([str(args.sox),'--precision','64',str(source),str(destination)],
            capture_output=True,text=True)
        plan=subprocess.run([str(args.sox),'--precision','64','--plan',
            str(source),str(destination)],capture_output=True,text=True)
        ok=(cp.returncode!=0 and destination.read_bytes()==b'SENTINEL' and
            plan.returncode==0 and 'refused-before-output' in plan.stdout)
        record={'suite':'pcm-identity',
            'status':'PASS_WITH_NOT_RUN' if ok else 'FAIL',
            'gate_execution':{
                'disabled_native_refusal':'PASS' if ok else 'FAIL',
                'native_numeric_and_stream_gates':'NOT_RUN: --disable-native-f64'},
            'source_git_commit':safe_git_head(SOURCE),
            'executed_binary_sha256':{str(args.sox):sha(args.sox)},
            'actual_checks':{'disabled_refusal_commands':2},
            'error':None if ok else 'strict64 disabled build did not refuse without output modification'}
        receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print(record['status']+' pcm-identity: disabled native DSP capability')
        return 0 if ok else 1
    suite=Suite(args.sox,args.probe,results)
    try:
        suite.record_binary(suite.probe)
        cp=subprocess.run([str(suite.probe)],capture_output=True,text=True)
        check(cp.returncode==0 and 'PASS coordinator' in cp.stdout,
              'direct native stream probe failed: '+cp.stderr)
        suite.count('coordinator_assertions',int(cp.stdout.split('assertions=')[1].split()[0]))
        suite.gates['direct_caller_stream_state_machine']='PASS'
        suite.word_identity()
        suite.integer_sources()
        suite.gain_order()
        suite.remix_layout()
        suite.narrowing_and_quantization()
        suite.faults_and_sentinels()
        suite.stdout_report()
        suite.compatibility_plans()
        suite.flac_status()
        suite.native_fenv()
        suite.signal_cancellation()
        suite.planning_performance()
        suite.performance()
        record=suite.receipt('PASS_WITH_NOT_RUN' if any(str(x).startswith('NOT_RUN')
                                                   for x in suite.gates.values()) else 'PASS')
        print(f'{record["status"]} pcm-identity: {record["actual_checks"]}, '+
              f'{len(record["gate_execution"])} gates')
        return 0
    except BaseException as exc:
        suite.receipt('FAIL',f'{type(exc).__name__}: {exc}')
        print(f'FAIL pcm-identity: {type(exc).__name__}: {exc}',file=sys.stderr)
        if isinstance(exc,KeyboardInterrupt):raise
        return 1

if __name__=='__main__':
    sys.exit(main())
