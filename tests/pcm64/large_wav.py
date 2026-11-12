#!/usr/bin/env python3
"""Phase 03 native WAV qualification: independent RIFF/RF64 oracle.

Header parser uses Python's struct and checked file offsets, not libSoX.
Actual 4 GiB cases use seekable zero-filled sparse extents and a native
sample-writing tail crossing the boundary. Only small byte ranges are read.
No enormous
raw PCM fixture, fake header success, or float-duration count oracle.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import stat
import struct
import subprocess
import sys
import time

from binary_receipts import executable_libraries

U32=(1<<32)-1
U64=(1<<64)-1

def insist(test, msg):
    if not test:
        raise AssertionError(msg)

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def read_at(f, offset, count):
    f.seek(offset)
    data=f.read(count)
    insist(len(data)==count, f'offset {offset}: wanted {count}, got {len(data)}')
    return data

def parse_wave_file(path):
    """Independent bounded parser, never reading a potentially huge data chunk."""
    path=Path(path)
    size=path.stat().st_size
    with path.open('rb') as f:
        lead=read_at(f,0,12)
        kind=lead[:4]
        insist(kind in (b'RIFF',b'RIFX',b'RF64') and lead[8:]==b'WAVE',
               f'bad WAVE magic: {path}')
        big=kind==b'RIFX'
        endian='>' if big else '<'
        unpack16=lambda bs:struct.unpack(endian+'H',bs)[0]
        unpack32=lambda bs:struct.unpack(endian+'I',bs)[0]
        riff32=unpack32(lead[4:8])
        pos=12
        chunks={}
        ds64=None
        data_offset=None
        data_length=None
        first=None
        for _ in range(64):
            insist(pos+8<=size, f'missing chunk at {pos}')
            header=read_at(f,pos,8)
            name=header[:4]
            body32=unpack32(header[4:])
            body_start=pos+8
            if first is None:
                first=name
            insist(name not in chunks, f'duplicate chunk {name!r}')
            if kind==b'RF64' and name==b'data':
                insist(ds64 is not None and body32==U32,
                       'RF64 data sentinel/ds64 missing')
                length=ds64['data']
            else:
                length=body32
            insist(body_start<=size and length<=size-body_start,
                   f'chunk {name!r} exceeds actual file extent')
            chunks[name]={'offset':pos,'body':body_start,'length':length,
                          'raw_size':body32}
            if name==b'ds64':
                insist(kind==b'RF64' and length==28, 'bad ds64 chunk size')
                data=read_at(f,body_start,28)
                riff64,data64,frames,table=struct.unpack('<QQQI',data)
                insist(table==0,'unexpected ds64 table')
                ds64={'riff':riff64,'data':data64,'frames':frames,
                      'table':table}
            if name==b'data':
                data_offset=body_start
                data_length=length
                pos=body_start+length+(length&1)
                break
            pos=body_start+length+(length&1)
        else:
            raise AssertionError('too many WAV chunks')
        insist(pos==size, f'chunk inventory did not cover final extent: {pos} != {size}')
        insist(b'fmt ' in chunks and data_offset is not None,'missing fmt or data')
        fmt=chunks[b'fmt ']
        insist(fmt['length'] in (16,18,40),f'fmt bytes invalid: {fmt}')
        base=read_at(f,fmt['body'],min(fmt['length'],40))
        tag,ch,rate,byte_rate,block,bits=struct.unpack_from(endian+'HHIIHH',base)
        mask=None
        valid=bits
        guid=None
        if tag==0xfffe:
            insist(len(base)==40 and unpack16(base[16:18])==22,
                   'malformed extensible format')
            valid,mask=struct.unpack_from(endian+'HI',base,18)
            guid=base[24:40]
        elif fmt['length']==18:
            insist(base[16:18]==b'\0\0','malformed standard float extension')
        insist(ch>0 and block==ch*(bits//8) and bits in (8,16,24,32,64),
               'invalid block align or sample count')
        insist(byte_rate==rate*block,'incorrect byte rate')
        insist(data_length%block==0,'partial final audio frame')
        frames=data_length//block
        if kind==b'RF64':
            insist(first==b'ds64' and riff32==U32 and ds64 is not None,
                   'noncanonical RF64 RIFF header')
            insist(ds64['riff']==size-8 and ds64['data']==data_length and
                   ds64['frames']==frames,'inconsistent RF64 ds64 counts')
        else:
            insist(riff32==size-8 and riff32<U32,
                   'noncanonical small WAV RIFF length')
            if not big:
                insist(first==b'JUNK' and chunks[first]['length']==28 and
                       read_at(f,chunks[first]['body'],28)==b'\0'*28,
                       'reserved 28-byte JUNK was not fully written')
        if tag in (3,0xfffe):
            insist(b'fact' in chunks and chunks[b'fact']['length']==4,
                   'float/extensible WAV missing fact')
            fact=unpack32(read_at(f,chunks[b'fact']['body'],4))
            insist(fact==(U32 if kind==b'RF64' else frames),
                   'fact count disagrees with exact frames')
        else:
            fact=None
        return {'kind':kind.decode('ascii'), 'riff_size':size-8,
                'data_size':data_length,'data_offset':data_offset,'frames':frames,
                'header_sha256':hashlib.sha256(read_at(f,0,data_offset)).hexdigest(),
                'chunks':{k.decode('latin1'):v for k,v in chunks.items()},
                'format':{'tag':tag,'channels':ch,'rate':rate,'byte_rate':byte_rate,
                          'block_align':block,'bits':bits,'valid':valid,'mask':mask,
                          'guid':guid.hex() if guid else None,'fact':fact},
                'file_size':size}

class LargeWav:
    def __init__(self, sox, probe, results):
        self.sox=Path(sox).resolve()
        self.probe=Path(probe).resolve().parent/'pcm64_wav_probe'
        self.results=Path(results).resolve()
        self.dir=self.results/'fixtures'/'large-wav'
        if self.dir.exists(): shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self.counts={}
        self.gates={}
        self.cases=[]
        self.commands=[]
        self.executed={}
        self.sparse_files=[]
        self.performance={}
        self.shim=None

    def tick(self, label, count=1):
        self.counts[label]=self.counts.get(label,0)+count

    def record(self, binary):
        p=Path(binary).resolve()
        if str(p) not in self.executed:
            self.executed[str(p)]=sha_file(p)
            self.executed.update(executable_libraries(p))

    def command(self, args, *, label='', exit=0, env=None, stdout_path=None,
                limit_memory=False, timeout=35):
        self.record(self.probe)
        argv=[str(self.probe),*map(str,args)]
        e=os.environ.copy()
        if env:
            e.update({str(k):str(v) for k,v in env.items()})
            if 'LD_PRELOAD' in env: self.record(env['LD_PRELOAD'])
        t=time.perf_counter()
        def cap_address_space():
            resource.setrlimit(resource.RLIMIT_AS,(96<<20,96<<20))
        with (Path(stdout_path).open('wb') if stdout_path else subprocess.DEVNULL if False else io.BytesIO()) as target:
            # Keep test stdout separate from output payload; never capture a
            # large file into memory. PIPE is for deliberately short cases.
            file_target=target if stdout_path else subprocess.PIPE
            proc=subprocess.run(argv,stdin=subprocess.DEVNULL,
                  stdout=file_target,stderr=subprocess.PIPE,env=e,timeout=timeout,
                  preexec_fn=cap_address_space if limit_memory and sys.platform=='linux' else None)
            wire=b'' if stdout_path else proc.stdout
        t=time.perf_counter()-t
        row={'label':label or args[0],'argv':argv,'exit':proc.returncode,
             'stderr':proc.stderr.decode('utf-8','replace')[:1500],
             'output_bytes':len(wire),
             'output_sha256':hashlib.sha256(wire).hexdigest(),
             'seconds':round(t,6)}
        self.commands.append(row)
        insist(proc.returncode==exit,
               f'{label}: exit {proc.returncode}, wanted {exit}; {row["stderr"]}')
        return wire,row['stderr']

    def case(self, title, **record):
        self.cases.append({'case':title,'status':'PASS',**record})
        self.tick('cases')

    def file(self,title,data):
        path=self.dir/title
        path.write_bytes(data)
        return path
    def planner(self):
        # The oracle is ordinary arbitrary-precision Python integer arithmetic,
        # never the C function or a floating duration. The C probe is a
        # separately compiled invocation of the actual writer's size planner.
        rows=0
        for frames in (0,1,(1<<32)-1,1<<32,(1<<32)+1,
                       (1<<53)-1,1<<53,(1<<53)+1,(1<<53)+127,
                       (1<<64)-1):
            for channels,bits,kind,ext in ((1,8,'little',0),
                                           (2,64,'float',0),
                                           (6,64,'float',1),
                                           (1,8,'big',0)):
                align=channels*(bits//8)
                fmt=40 if ext else (18 if kind=='float' else 16)
                fact=bool(ext) or kind=='float'
                header=12+(0 if kind=='big' else 36)+8+fmt+(12 if fact else 0)+8
                data=frames*align
                fsize=header+data+(data&1)
                riff=fsize-8
                rf64=(riff>=U32 or data>=U32 or (fact and frames>=U32))
                can=(fsize<1<<64 and (kind!='big' or not rf64))
                output,_=self.command(['plan',frames,channels,bits,kind,ext],
                                     label=f'plan-{frames}-{channels}-{bits}-{kind}-{ext}')
                decoded=output.decode('ascii').strip()
                if not can:
                    insist(decoded=='REFUSED',f'unrepresentable plan admitted: {decoded}')
                    self.tick('virtual_size_refusals')
                else:
                    fields=dict(x.split('=',1) for x in decoded.split())
                    truth={'frames':frames,'data':data,'riff':riff,
                           'file':fsize,'header':header,'rf64':int(rf64)}
                    insist({k:int(v) for k,v in fields.items()}==truth,
                           f'large integer planner mismatch: {truth} != {fields}')
                    self.tick('virtual_exact_64bit_plans')
                rows+=1
        self.case('integer-planner-32bit-53bit-and-overflow',total=rows)
        self.gates['virtual_integer_count_oracle']='PASS'

    def small(self):
        raw=self.file('f64-words.raw64',struct.pack('<dddddd',
                           0.125,-0.25,0.375,-0.5,0.625,-0.75))
        for name,typ,endian,ch,declared,actual in (
                ('f64-2-known','f64','L',2,3,3),
                ('f64-2-unknown','f64','L',2,U64,3),
                ('f64-2-zero','f64','L',2,0,0),
                ('f64-1-known','f64','L',1,3,3),
                ('f64-1-rifx','f64','B',1,3,3),
                ('i8-1-odd','i8','L',1,3,3),
                ('i8-1-rifx','i8','B',1,3,3)):
            if typ!='f64' and not self.native_integer_available:
                self.gates['integer_pcm64_writes']=(
                    'NOT_RUN: arithmetic conversion disabled at configure time')
                continue
            target=self.dir/(name+'.wav')
            self.command(['generate',raw,target,typ,endian,ch,44100,declared,actual],
                         label=name)
            header=parse_wave_file(target)
            expected=actual*ch*(int(typ[1:])//8)
            insist(header['data_size']==expected and header['frames']==actual and
                   header['format']['channels']==ch and
                   header['data_offset']==(58 if endian=='B' and typ=='f64' else
                        44 if endian=='B' else header['data_offset']),
                   f'{name}: wrong offset/count')
            with target.open('rb') as f:
                data=read_at(f,header['data_offset'],expected)
            if typ=='f64':
                truth=raw.read_bytes()[:actual*ch*8]
                if endian=='B':
                    truth=b''.join(truth[i:i+8][::-1] for i in range(0,len(truth),8))
                insist(data==truth,f'{name}: payload differs from raw IEEE words')
            if typ=='i8':
                insist(data==bytes([144,96,176]),f'{name}: quantized i8 mismatch: {data!r}')
                insist(target.stat().st_size%2==0,'odd i8 data not padded')
            self.case(name,header=header,payload_sha256=hashlib.sha256(data).hexdigest())
            self.tick('small_payload_hash_comparisons')
        # Writer remains a private API: compare byte-level legacy headers to
        # accepted Phase 02 behavior for an ordinary SoX copy.
        from io_wav import wave_bytes
        legacy_src=self.file('legacy-source.wav',wave_bytes(struct.pack('<h',1234)*17,
                                                              channels=1,code='i16'))
        legacy_out=self.dir/'legacy-output.wav'
        self.record(self.sox)
        cp=subprocess.run([str(self.sox),str(legacy_src),str(legacy_out)],
                          capture_output=True,timeout=20)
        self.commands.append({'label':'ordinary-legacy-WAV-copy',
            'argv':[str(self.sox),str(legacy_src),str(legacy_out)],
            'exit':cp.returncode,'stderr':cp.stderr.decode('utf-8','replace')[:1000]})
        insist(cp.returncode==0 and legacy_out.read_bytes()==legacy_src.read_bytes(),
               'ordinary byte-compatible WAV path changed')
        self.case('ordinary-legacy-WAV-byte-compatibility',
                  sha256=sha_file(legacy_out))
        # WAVE_FORMAT_EXTENSIBLE with a six-channel role mask must retain the
        # channel identity all the way through native read -> native write.
        payload=struct.pack('<d',0.25)*12
        multi_src=self.file('six-channel-mask-input.wav',wave_bytes(
                payload,channels=6,rate=48000,code='f64',extensible=True,mask=0x3f))
        multi=self.dir/'six-channel-mask-output.wav'
        self.command(['copy',multi_src,multi,'f64','L'],label='six-channel-mask-copy')
        h=parse_wave_file(multi)
        insist(h['format']['tag']==0xfffe and h['format']['channels']==6 and
               h['format']['mask']==0x3f and h['format']['valid']==64,
               'native output lost six-channel mask or 64-bit valid bits')
        with multi.open('rb') as f:
            insist(read_at(f,h['data_offset'],len(payload))==payload,
                   'native masked output changed float payload')
        self.case('six-channel-extensible-mask',header=h,
                  payload_sha256=hashlib.sha256(payload).hexdigest())
        self.gates['small_native_and_legacy_compatibility']='PASS'

    def stdout(self):
        for ch in (1,2,6):
            raw=self.file(f'stdout-raw-{ch}.raw64',struct.pack('<d',0.125)*(ch*3))
            wire,_=self.command(['generate',raw,'-','f64','L',ch,48000,3,3],
                                label=f'stdout-known-{ch}-channels')
            target=self.file(f'stdout-actual-pipe-{ch}.wav',wire)
            hdr=parse_wave_file(target)
            insist(hdr['kind']=='RIFF' and hdr['frames']==3 and
                   hdr['data_size']==ch*3*8 and
                   wire[hdr['data_offset']:hdr['data_offset']+ch*3*8]==raw.read_bytes(),
                   'stdout pipe header/count/payload inaccurate')
            self.case(f'known-stdout-actual-pipe-{ch}ch',header=hdr)
        for ch in (1,2,6):
            raw=self.file(f'stdout-unknown-raw-{ch}.raw64',struct.pack('<d',0.125)*ch)
            output,error=self.command(['generate',raw,'-','f64','L',ch,48000,U64,1],
                                      label=f'unknown-stdout-refusal-{ch}',exit=1)
            insist(not output and 'known-length pipe' in error,
                   'unknown pipe leaked bytes or hid admission failure')
            self.case(f'unknown-stdout-refusal-{ch}ch',error=error)
        raw=self.file('stdout-underrun.raw64',struct.pack('<d',0.25))
        for declared,actual in ((2,1),(0,1)):
            output,error=self.command(['generate',raw,'-','f64','L',1,48000,
                                       declared,actual],exit=1,
                                      label=f'stdout-count-mismatch-{declared}-{actual}')
            insist('FAIL' in error and len(output)<200,
                   'count mismatch returned ambiguous success or wrote an unbounded pipe')
            if declared==0:
                # Overrun is refused before a single audio byte is accepted.
                self.tick('pipe_overrun_attempt_refusals')
            else:
                self.tick('pipe_underrun_close_refusals')
            self.case(f'stdout-count-mismatch-{declared}-{actual}',
                      produced_bytes=len(output),stderr=error)
        # At a >4 GiB declaration the small header itself must announce RF64
        # and exact ds64 values, even if the following under-run forces failure.
        self.command(['generate',raw,'-','f64','L',1,48000,
                      ((U32//8)+20),0],exit=1,label='known-large-pipe-header-only')
        rows=self.commands[-1]
        # Capture header for inspection on a second invocation, not from a
        # fabricated finished large file; the pipe MUST exit nonzero here.
        wire,_=self.command(['generate',raw,'-','f64','L',1,48000,
                             ((U32//8)+20),0],exit=1,
                            label='known-large-pipe-header-probe')
        insist(wire[:4]==b'RF64' and struct.unpack_from('<I',wire,4)[0]==U32 and
               wire[12:16]==b'ds64' and
               struct.unpack_from('<Q',wire,28)[0]==((U32//8)+20)*8,
               'large declared pipe header is not canonical RF64')
        self.case('known-large-pipe-underflow-header-only',header_prefix=wire.hex(),
                  exit_code=1)
        # Regular stdout redirection has a different FD type; its header is
        # seekable, and unknown length is allowed.
        target=self.dir/'stdout-regular-unknown.wav'
        self.command(['generate',raw,'-','f64','L',1,48000,U64,1],
                     stdout_path=target,label='stdout-regular-redirect-unknown')
        h=parse_wave_file(target)
        insist(h['frames']==1 and h['kind']=='RIFF',
               'regular redirect incorrectly treated as pipe')
        self.case('stdout-regular-file-unknown-length',header=h)
        # Drive an actual pipe with small reader-side chunks and more than one
        # pipe-buffer's worth of PCM. This checks bounded backpressure and
        # header/payload alignment without capturing unbounded output.
        ch=6
        frames=4096
        raw=self.file('stdout-fragmented-raw.raw64',struct.pack('<d',-0.125)*(ch*frames))
        self.record(self.probe)
        argv=[str(self.probe),'generate',str(raw),'-','f64','L',str(ch),'48000',
              str(frames),str(frames)]
        started=time.perf_counter()
        proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        buffer=bytearray()
        assert proc.stdout is not None
        while True:
            block=proc.stdout.read(79)
            if not block: break
            buffer.extend(block)
            insist(len(buffer)<1<<21,'pipe test unexpectedly grew beyond bounded workload')
        proc.stdout.close()
        proc.stdout=None
        _,err=proc.communicate(timeout=30)
        self.commands.append({'label':'stdout-fragmented-small-reader',
              'argv':argv,'exit':proc.returncode,'stdout_bytes':len(buffer),
              'seconds':round(time.perf_counter()-started,6),
              'stderr':err.decode('utf-8','replace')[:1024]})
        insist(proc.returncode==0,'fragmented pipe reader failed: '+repr(err))
        path=self.file('stdout-fragmented.wav',buffer)
        header=parse_wave_file(path)
        insist(header['frames']==frames and header['format']['channels']==ch and
               buffer[header['data_offset']:]==raw.read_bytes(),
               'fragmented anonymous pipe changed WAV output or count')
        self.case('stdout-fragmented-6channel-stream',header=header,
                  reader_chunk_bytes=79)
        self.gates['stdout_descriptor_and_counts']='PASS'
    def sparse(self):
        # Capability check: seek-to-4GiB plus a last-byte write must consume
        # little physical space, or this suite will not attempt real 4 GiB
        # cases. The virtual integer oracle above still runs without sparse.
        candidate=self.dir/'sparse-support-probe'
        try:
            with candidate.open('wb') as f:
                f.seek(1<<32)
                f.write(b'\0')
            st=candidate.stat()
            supported=(st.st_size==(1<<32)+1 and
                       st.st_blocks*512 <= (2<<20))
        except (OSError, OverflowError, AttributeError) as exc:
            supported=False
            self.gates['real_4gib_sparse_file']='NOT_RUN: filesystem sparse test failed: '+str(exc)
        finally:
            candidate.unlink(missing_ok=True)
        if not supported:
            self.gates.setdefault('real_4gib_sparse_file',
                                  'NOT_RUN: filesystem does not support compact 4 GiB holes')
            self.case('sparse-filesystem-unavailable',status='NOT_RUN')
            return
        # Derive the boundary independently from a measured small header and
        # pure integer division; never ask the writer what its cutoff is.
        small=self.dir/'sparse-header-reference.wav'
        self.command(['sparse-zero',small,'f64','L',2,176400,1,1],
                     label='small-header-reference')
        ref=parse_wave_file(small)
        align=2*8
        initial_header=ref['data_offset']
        baseline=(U32-(initial_header-8))//align
        assert initial_header==94
        # The maximal representable RIFF size is even; the 0xffffffff marker
        # is odd. Hence the case at the representability boundary has length
        # 0xfffffffe, and its immediate successor must already be RF64.
        cases=(('last-small',baseline-1,baseline-1,'RIFF'),
               ('at-riff-limit',baseline,baseline,'RIFF'),
               ('first-large',baseline+1,baseline+1,'RF64'),
               ('large-unknown-declaration',U64,baseline+2,'RF64'))
        start=time.perf_counter()
        header_dir=self.results/'headers'/'large-wav'
        header_dir.mkdir(parents=True,exist_ok=True)
        for name,declared,actual,expect_kind in cases:
            target=self.dir/(name+'.wav')
            self.command(['sparse-zero',target,'f64','L',2,176400,declared,actual],
                         label='real-sparse-'+name,limit_memory=True)
            st=target.stat()
            h=parse_wave_file(target)
            insist(h['kind']==expect_kind and h['frames']==actual and
                   h['data_size']==actual*align and
                   h['file_size']==h['data_offset']+actual*align,
                   f'{name}: real writer finalized wrong sparse extent')
            insist(h['data_offset']==initial_header,
                   f'{name}: native writer moved data during RF64 promotion')
            insist(st.st_blocks*512 <= 4<<20,
                   f'{name}: 4GiB test allocated physical payload unexpectedly')
            # Zero-filled holes are semantically real payload; check at
            # beginning, around 2/4 GiB, and final sample without 4 GiB RSS.
            with target.open('rb') as f:
                for offset in (0,8,128,2<<30,3<<30,max(0,h['data_size']-4096)):
                    n=min(4096,h['data_size']-offset)
                    if n>0:
                        insist(read_at(f,h['data_offset']+offset,n)==b'\0'*n,
                               f'{name}: sparse payload contains nonzero bytes at {offset}')
                header_bytes=read_at(f,0,h['data_offset'])
            (header_dir/(name+'.header.bin')).write_bytes(header_bytes)
            self.case('real-sparse-'+name,header=h,
                      actual_frames=actual,declared=declared,
                      allocated_disk_bytes=st.st_blocks*512,
                      sparse_sampled_zero_offsets=[0,8,128,2<<30,3<<30,
                                                   max(0,h['data_size']-4096)])
            self.tick('real_sparsed_4gib_cases')
            self.sparse_files.append(str(target))
            target.unlink()
        if self.native_integer_available:
            # A sparse prefix establishes the actual file position, then
            # three nonzero frames pass through the ordinary native writer
            # across RIFF's 32-bit size boundary. Verify the written tail,
            # the sparse prefix and the finalized RF64 counts independently.
            target=self.dir/'native-samples-cross-4g.wav'
            prefix=baseline-1
            tail=3
            self.command(['sparse-zero',target,'f64','L',2,176400,
                          prefix+tail,prefix,tail],
                         label='real-native-write-across-4g',limit_memory=True)
            h=parse_wave_file(target)
            st=target.stat()
            expected=b''.join(struct.pack('<dd',i*0.125,-i*0.125)
                              for i in range(1,tail+1))
            insist(h['kind']=='RF64' and h['frames']==prefix+tail and
                   h['data_offset']==initial_header and
                   h['data_size']==(prefix+tail)*align and
                   st.st_blocks*512 <= 4<<20,
                   'normal native sample write did not cross 4 GiB correctly')
            with target.open('rb') as f:
                insist(read_at(f,h['data_offset']+prefix*align,len(expected))==expected,
                       'native sample payload after 4 GiB mismatch')
                insist(read_at(f,h['data_offset']+prefix*align-1024,1024)==b'\0'*1024,
                       'sparse prefix before real native frames changed')
            self.case('real-native-write-across-4g',header=h,
                      prefix_frames=prefix,native_written_frames=tail,
                      native_written_tail_sha256=hashlib.sha256(expected).hexdigest(),
                      allocated_disk_bytes=st.st_blocks*512)
            self.tick('real_native_write_4g_crossings')
            self.gates['real_native_write_4g_crossing']='PASS'
            self.sparse_files.append(str(target))
            target.unlink()
        else:
            self.gates['real_native_write_4g_crossing']=(
                'NOT_RUN: arithmetic-dependent native sample writer disabled')
        self.performance['four_sparse_gib_header_and_finalize_seconds']=round(
            time.perf_counter()-start,6)
        self.performance['four_sparse_gib_payload_bytes_written_physically']=0
        self.performance['writer_sparse_runtime_rss_limit_bytes']=96<<20
        if self.native_integer_available:
            # 0xffffffff EXACT payload bytes is possible for signed 8-bit PCM,
            # even though the RIFF extent must already be RF64. Pad is excluded
            # from ds64 data size and included in riff size.
            n=U32
            target=self.dir/'exact-u32-data.wav'
            self.command(['sparse-zero',target,'i8','L',1,48000,n,n],
                         label='real-sparse-exact-u32-payload',limit_memory=True)
            h=parse_wave_file(target)
            insist(h['kind']=='RF64' and h['data_size']==U32 and
                   h['frames']==U32 and h['file_size']==h['data_offset']+U32+1,
                   'exact 0xffffffff payload or odd pad counted incorrectly')
            with target.open('rb') as f:
                insist(read_at(f,h['data_offset']+U32,1)==b'\0',
                       'odd padding after huge data not physically written')
            self.case('real-sparse-exact-u32-payload-and-odd-pad',header=h)
            self.tick('real_sparsed_4gib_cases')
            self.sparse_files.append(str(target))
            target.unlink()
            self.gates['real_sparse_odd_u32_data']='PASS'
        else:
            self.gates['real_sparse_odd_u32_data']=(
                'NOT_RUN: arithmetic-dependent 8-bit native writer disabled')
        self.gates['real_4gib_sparse_file']='PASS'
        self.gates['sparse_data_offset_stability']='PASS'

    def refusals(self):
        raw=self.file('refusal-input.raw64',struct.pack('<d',0.25))
        marker=b'NEVER-TRUNCATE-THIS-DESTINATION'*19
        for label,typ,endian,ch,rate,declared,actual in (
            ('known-large-rifx','f64','B',2,44100,(1<<33),1),
            ('representability-overflow','f64','L',2,44100,U64-1,1),
            ('byte-rate-overflow','f64','L',1,U32,1,1),
            ('block-align-overflow','f64','L',65535,44100,1,1),
        ):
            target=self.file('refuse-'+label+'.wav',marker)
            _,error=self.command(['generate',raw,target,typ,endian,ch,rate,
                                  declared,actual],label='refuse-'+label,exit=1)
            insist(target.read_bytes()==marker,
                   f'{label}: precommit refusal destroyed existing sentinel')
            self.case('precommit-'+label,stderr=error,
                      preserved_sha256=sha_file(target))
            self.tick('precommit_refusals')
        # A named FIFO and source/destination alias have different risks,
        # and neither may become an opened or deleted output handle.
        fifo=self.dir/'named-fifo.wav'
        if hasattr(os,'mkfifo'):
            os.mkfifo(fifo)
            _,error=self.command(['generate',raw,fifo,'f64','L',1,48000,1,1],
                                 label='reject-named-FIFO',exit=1)
            insist(stat.S_ISFIFO(fifo.stat().st_mode),
                   'refused named FIFO was replaced/deleted')
            self.case('named-fifo-untouched',stderr=error)
        else:
            self.gates['named_FIFO_refusal']='NOT_RUN: no mkfifo'
        target=self.dir/'symlink-target.wav'
        target.write_bytes(marker)
        link=self.dir/'regular-symlink.wav'
        link.symlink_to(target)
        self.command(['generate',raw,link,'f64','L',1,48000,1,1],
                     label='accept-regular-symlink')
        insist(link.is_symlink() and link.resolve()==target.resolve() and
               parse_wave_file(target)['frames']==1,
               'stable regular symlink was replaced instead of followed')
        self.case('stable-regular-symlink-preserved')
        raw_out=self.file('raw-alias.wav',struct.pack('<d',0.25))
        before=sha_file(raw_out)
        self.command(['generate',raw_out,raw_out,'f64','L',1,48000,1,1],
                     exit=1,label='reject-source-output-alias')
        insist(sha_file(raw_out)==before,'same-file input/output alias altered bytes')
        self.case('source-output-alias-preservation')
        # A plausible normal-size target may be rejected by overwrite policy;
        # this must be a precommit refusal and preserve the old bytes.
        denied=self.file('denied-overwrite.wav',marker)
        self.command(['generate',raw,denied,'f64','L',1,48000,1,1,'deny'],
                     exit=1,label='denied-overwrite')
        insist(denied.read_bytes()==marker,'overwrite denial destroyed bytes')
        self.case('overwrite-denial-preserves-sentinel')
        self.gates['refusal_and_same_descriptor_safety']='PASS'
    def rf64_read_validation(self):
        # Construct a valid, small RF64 using a native RIFF source solely as a
        # byte-layout template. Each RF64 number comes from this independent
        # parser, not from the SoX implementation. This exercises RF64 facts
        # without needing a decoder to traverse 4 GiB of physical bytes.
        raw=self.file('rf64-read-source.raw64',struct.pack('<d',0.125)*3)
        src=self.dir/'rf64-source-small.wav'
        self.command(['generate',raw,src,'f64','L',1,48000,3,3],
                     label='rf64-small-template')
        h=parse_wave_file(src)
        data=bytearray(src.read_bytes())
        assert data[12:20]==b'JUNK\x1c\x00\x00\x00'
        data[0:4]=b'RF64'
        data[4:8]=struct.pack('<I',U32)
        data[12:16]=b'ds64'
        data[20:48]=struct.pack('<QQQI',len(data)-8,h['data_size'],3,0)
        fact_offset=h['chunks']['fact']['body']
        data_size_offset=h['chunks']['data']['offset']+4
        data[fact_offset:fact_offset+4]=struct.pack('<I',U32)
        data[data_size_offset:data_size_offset+4]=struct.pack('<I',U32)
        val=self.file('rf64-valid-small.wav',data)
        r,_=self.command(['query',val],label='strict-valid-RF64-read')
        insist(r.decode('ascii').strip().startswith('rate=48000 channels=1 frames=3'),
               f'valid RF64 reader failed to disclose three exact frames: {r!r}')
        self.case('valid-RF64-native-facts',query=r.decode('ascii').strip())
        # The 32-bit fact field may also hold the exact count when it fits.
        # A valid exact count is not a malformed sentinel.
        exact_fact=bytearray(data)
        exact_fact[fact_offset:fact_offset+4]=struct.pack('<I',3)
        exact_path=self.file('rf64-valid-exact-fact.wav',exact_fact)
        exact,_=self.command(['query',exact_path],label='RF64-exact-fact-count')
        insist(exact==r, 'RF64 exact fact lost declared frame count')
        self.case('valid-RF64-exact-fact',query=exact.decode('ascii').strip())
        # Extensible PCM, including what ffmpeg 7.x emits for 24-bit stereo,
        # does not require a fact chunk. Build a format-extensible RF64 and
        # its byte-identical RIFF analogue without using the writer under
        # test. Validate BOTH admission and decoded contents via native dump.
        if self.native_integer_available:
            from io_wav import wave_bytes
            for channels,mask in ((2,0x3),(6,0x3f)):
                words=[(-0x400000+(i%8)*0x100011) for i in range(channels*4)]
                payload=b''.join(int(word).to_bytes(3,'little',signed=True)
                                 for word in words)
                riff=bytearray(wave_bytes(payload,channels=channels,rate=48000,
                    code='i24',extensible=True,mask=mask))
                start=riff.index(b'fact')
                insist(riff[start+4:start+8]==struct.pack('<I',4),
                       'unexpected fact fixture from independent RIFF builder')
                del riff[start:start+12]
                riff[4:8]=struct.pack('<I',len(riff)-8)
                riff_path=self.file(f'extensible-pcm-{channels}-riff.wav',riff)
                native_body=bytearray(riff[12:])
                at=native_body.index(b'data')+4
                native_body[at:at+4]=struct.pack('<I',U32)
                total=12+36+len(native_body)
                rf64=(b'RF64'+struct.pack('<I',U32)+b'WAVE'+
                      b'ds64'+struct.pack('<IQQQI',28,total-8,len(payload),4,0)+
                      native_body)
                rf64_path=self.file(f'extensible-pcm-{channels}-rf64-no-fact.wav',rf64)
                a,_=self.command(['query',riff_path],label=f'RIFF-PCM-{channels}-no-fact')
                b,_=self.command(['query',rf64_path],label=f'RF64-PCM-{channels}-no-fact')
                insist(a==b and b'frames=4' in b,
                       'RF64/RIFF native query mismatch for fact-optional PCM')
                x,_=self.command(['dump',riff_path],label=f'RIFF-dump-{channels}-no-fact')
                y,_=self.command(['dump',rf64_path],label=f'RF64-dump-{channels}-no-fact')
                insist(x==y and len(y)==channels*4*8,
                       'RF64/RIFF native PCM samples disagree')
                self.case(f'RF64-extensible-{channels}-channel-without-fact',
                          query=b.decode('ascii').strip(),
                          decoded_sha256=hashlib.sha256(y).hexdigest())
            self.gates['valid_fact_optional_extensible_PCM_RF64']='PASS'
        else:
            self.gates['valid_fact_optional_extensible_PCM_RF64']=(
                'NOT_RUN: native integer arithmetic disabled')
        variants={}
        def mutate(name,offset,blob):
            b=bytearray(data)
            b[offset:offset+len(blob)]=blob
            variants[name]=bytes(b)
        mutate('no-ds64',12,b'JUNK')
        mutate('bad-ds64-length',16,struct.pack('<I',16))
        mutate('nonzero-ds64-table',44,struct.pack('<I',1))
        mutate('riff-length-disagrees',20,struct.pack('<Q',len(data)-7))
        mutate('data-length-disagrees',28,struct.pack('<Q',h['data_size']+1))
        mutate('frame-count-disagrees',36,struct.pack('<Q',4))
        mutate('bad-fact-count',fact_offset,struct.pack('<I',2))
        mutate('bad-data-sentinel',data_size_offset,struct.pack('<I',h['data_size']))
        mutate('bad-top-riff-sentinel',4,struct.pack('<I',len(data)-8))
        for name,b in variants.items():
            path=self.file('bad-rf64-'+name+'.wav',b)
            _,error=self.command(['query',path],exit=1,label='bad-rf64-'+name)
            insist('native WAV unsupported' in error or 'FAIL open input' in error,
                   f'{name}: rejected for an unrelated reason: {error}')
            self.case('bad-RF64-'+name,stderr=error)
            self.tick('malformed_RF64_refusals')
        self.gates['RF64_reader_facts_and_malformed_refusals']='PASS'

    def failures(self):
        if sys.platform!='linux' or shutil.which('cc') is None:
            self.gates['injected_header_payload_and_close_faults']=(
                'NOT_RUN: Linux C compiler and LD_PRELOAD required')
            return
        shim=self.dir/'liblarge_wav_fault.so'
        source=Path(__file__).with_name('wav_fault_shim.c')
        args=['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-o',str(shim),
              str(source),'-ldl']
        cmd=subprocess.run(args,capture_output=True,text=True)
        insist(cmd.returncode==0,f'could not compile fault shim: {cmd.stderr}')
        self.shim=shim
        self.record(shim)
        raw=self.file('fault-input.raw64',struct.pack('<d',0.125)*4)
        for name,envvar,expected_trace,use_sparse,declared,actual in (
            ('initial-header-short','PCM64_SHORT_WRITE','W',False,4,4),
            ('payload-short','PCM64_SHORT_WRITE','W',False,4,4),
            ('rewrite-seek','PCM64_FAIL_REWRITE_SEEK','H',False,U64,4),
            ('rewrite-write','PCM64_FAIL_REWRITE_WRITE','J',False,U64,4),
            ('buffered-flush','PCM64_FAIL_FINAL_FLUSH','F',False,U64,4),
            ('final-close','PCM64_FAIL_FCLOSE','C',False,U64,4),
            ('sparse-tail','PCM64_FAIL_SPARSE_TAIL','Z',True,U64,4)):
            for run_index in (0,1):
                target=self.dir/(f'fault-{name}-{run_index}.wav')
                trace=self.dir/(f'fault-{name}-{run_index}.trace')
                trace.unlink(missing_ok=True)
                env={'LD_PRELOAD':str(shim),'PCM64_TEST_TARGET':str(target),
                     'PCM64_TRACE':str(trace),envvar:'1'}
                if envvar=='PCM64_SHORT_WRITE':
                    env['PCM64_DATA_OFFSET']='0' if name=='initial-header-short' else '94'
                command=(['sparse-zero',target,'f64','L',1,48000,declared,actual]
                         if use_sparse else
                         ['generate',raw,target,'f64','L',1,48000,declared,actual])
                _,error=self.command(command,exit=1,
                     label=f'fault-{name}-{run_index}',env=env)
                observed=trace.read_text() if trace.exists() else ''
                insist(expected_trace in observed,
                       f'{name}: expected injection {expected_trace!r} never fired: {observed!r}')
                insist(target.exists() or name=='initial-header-short',
                       f'{name}: failure incorrectly unlinked committed destination')
                self.case('injected-'+name+'-'+str(run_index),
                          hook_trace=observed,stderr=error,
                          remaining_file_bytes=target.stat().st_size if target.exists() else None)
                self.tick('verified_failure_hooks')
        # Actual nonseekable stdout: fail a payload fwrite after a valid
        # header. The interposer's trace proves a partial fwrite happened.
        pipe_src=self.file('fault-pipe-raw.raw64',struct.pack('<d',0.25)*12)
        for attempt in (0,1):
            trace=self.dir/f'fault-stdout-pipe-{attempt}.trace'
            env={'LD_PRELOAD':str(shim),'PCM64_TRACE':str(trace),
                 'PCM64_FAIL_STDOUT_PAYLOAD_WRITE':'94'}
            output,error=self.command(['generate',pipe_src,'-','f64','L',2,48000,6,6],
                  env=env,exit=1,label=f'actual-pipe-partial-fwrite-{attempt}')
            observed=trace.read_text() if trace.exists() else ''
            insist('P' in observed and output[:4]==b'RIFF' and
                   len(output)<94+6*2*8,
                   f'pipe partial fwrite failed to inject: {observed!r}, {error}')
            self.case('actual-pipe-partial-write-'+str(attempt),
                      hook_trace=observed,wire_size=len(output),stderr=error)
            self.tick('verified_failure_hooks')
        self.gates['injected_header_payload_and_close_faults']='PASS'
    def execute(self):
        insist(self.sox.is_file() and self.probe.is_file(),
               'missing built SoX or native WAV probe binary')
        raw,_=self.command(['capabilities'],label='native-build-capability')
        lines=raw.decode('ascii').splitlines()
        insist(len(lines)==3 and all('=' in line for line in lines),
               f'invalid native capability output: {raw!r}')
        capabilities=dict(line.split('=',1) for line in lines)
        insist(len(capabilities)==3 and set(capabilities)==
               {'native_build','native_host','native_dsp'} and
               capabilities['native_build'] in ('ENABLED','DISABLED') and
               capabilities['native_host'] in ('SUPPORTED','UNSUPPORTED') and
               capabilities['native_dsp'] in ('OK','UNSUPPORTED','NUMERIC'),
               f'incomplete or invalid native capability: {capabilities!r}')
        self.capabilities=capabilities
        # The compile-time arithmetic flag does NOT disable binary64 identity
        # transport. Exercise its full RF64/sparse/fault matrix in every build;
        # only integer quantization and the 8-bit odd-payload example need
        # native DSP. An unsafe runtime guard in an enabled build is a FAIL.
        self.native_integer_available=(capabilities['native_build']=='ENABLED')
        if capabilities['native_host']!='SUPPORTED' or (
                self.native_integer_available and capabilities['native_dsp']!='OK'):
            self.gates['native_writer_eligibility']=(
                'FAIL: enabled native arithmetic or IEEE storage precondition: '+
                str(capabilities))
            raise AssertionError(self.gates['native_writer_eligibility'])
        self.gates['native_writer_eligibility']='PASS: binary64 identity path'
        self.planner()
        if not self.native_integer_available:
            self.gates['native_integer_arithmetic']=(
                'NOT_RUN: --disable-native-f64')
            source=self.file('disabled-raw.raw64',struct.pack('<d',0.25))
            dest=self.file('disabled-precommit-sentinel.wav',b'UNCHANGED-SENTINEL')
            self.command(['generate',source,dest,'i8','L',1,48000,1,1],
                         exit=1,label='native-disabled-integer-refusal')
            insist(dest.read_bytes()==b'UNCHANGED-SENTINEL',
                   'disabled native integer writer mutated an existing destination')
            self.case('native-disabled-integer-precommit-refusal')
            self.gates['native_disabled_integer_refusal']='PASS'
        for phase in (self.small,self.stdout,self.refusals,
                      self.rf64_read_validation,self.failures,self.sparse):
            phase()
        self.gates['header_parser_independent']='PASS'
        self.gates['bounded_memory_sparse_emission']='PASS' if (
            self.gates.get('real_4gib_sparse_file')=='PASS') else (
            'NOT_RUN: requires a sparse-capable filesystem')
        source=Path(__file__).resolve().parents[2]
        from io_flac import source_git_head
        return {
            'suite':'large-wav',
            'status':'PASS_WITH_NOT_RUN' if any(
                 v.startswith('NOT_RUN') for v in self.gates.values()) else 'PASS',
            'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'source_git_commit':source_git_head(source),
            'checks':self.counts,'gate_execution':self.gates,
            'native_capabilities':self.capabilities,
            'case_results':self.cases,'commands':self.commands,
            'performance':self.performance,
            'executed_binary_sha256':self.executed,
            'source_and_binary_sha256':{
                 str(p.relative_to(source)):sha_file(p) for p in (
                    source/'src/wav.c',source/'src/wav-size.h',
                    source/'src/formats.c',source/'src/pcm_f64_io.h',
                    source/'tests/pcm64/large_wav.py',
                    source/'tests/pcm64/wav_io_probe.c',
                    source/'tests/pcm64/wav_fault_shim.c')},
            'oracle':('Python arbitrary-precision integer arithmetic, independent '
                      'RIFF/RF64 seek-only parser and raw IEEE word buffers'),
            'sparse_io_explanation':(
                'The private native WAV writer creates real sparse file extents '
                'containing zeros, appends actual native-written samples across '
                'the 4GiB boundary and executes the normal close/RIFF-to-RF64 '
                'header rewrite. No entire 4GiB region is allocated or read. '
                'Individual byte ranges at several offsets and source byte '
                'payload hashes are checked independently.'),
        }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    output=args.results/'large-wav.json'
    output.unlink(missing_ok=True)
    runner=LargeWav(args.sox,args.probe,args.results)
    try:
        record=runner.execute()
    except Exception as exc:
        record={'suite':'large-wav','status':'FAIL',
                'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'error':f'{type(exc).__name__}: {exc}',
                'completed_checks':runner.counts,
                'gate_execution':runner.gates,'case_results':runner.cases,
                'commands':runner.commands,
                'executed_binary_sha256':runner.executed,
                'performance':runner.performance}
        output.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print('FAIL large-wav:',record['error'],file=sys.stderr)
        return 1
    output.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(record['status'],'large-wav:',record['checks'])
    return 0

if __name__=='__main__':
    sys.exit(main())
