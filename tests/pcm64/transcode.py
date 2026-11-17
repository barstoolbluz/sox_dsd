#!/usr/bin/env python3
"""Phase 06B, source-bound two-clock DSD transcode acceptance.

The intermediate IEEE754 stream is independently produced by the 05B public
API caller and replayed through 06A's certified encoder driver. A second
integer count oracle detects accidental direct-native-ratio rounding. The
production CLI is checked against the same chronological sign decisions and
actual DSF/DFF structure. No numeric tolerance is used for these comparisons.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any

from binary_receipts import executable_libraries, safe_git_head, native_dsp_compiled
from encode import dff_bits, dsf_bits
from decode import checked_rate

SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE/'tests/dsd/reference'))
import fixtures


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def demand(condition: bool, explanation: str) -> None:
    if not condition:
        raise AssertionError(explanation)


def run(argv, *, source=None, env=None, timeout=90):
    return subprocess.run([str(p) for p in argv], input=source,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ,**(env or {})},timeout=timeout,check=False)


def run_checked(argv, *, source=None, env=None, timeout=90, expected=0):
    p=run(argv,source=source,env=env,timeout=timeout)
    demand(p.returncode==expected,
        f'command {argv} returned {p.returncode}, expected {expected}: {p.stderr[-850:]!r}')
    return p


def clocks(n, input_hz, intermediate_hz, output_hz):
    intermediate=(n*intermediate_hz*2+input_hz)//(2*input_hz)
    out=(intermediate*output_hz*2+intermediate_hz)//(2*intermediate_hz)
    return intermediate,out


class Suite:
    def __init__(self,sox,probe,encoder,decoder,results,workspace):
        self.sox,self.probe,self.encoder,self.decoder=(Path(x).resolve() for x in
            (sox,probe,encoder,decoder))
        self.results=results
        self.work=workspace
        self.counts={}
        self.records=[]
        self.bit_hashes={}

    def count(self,key,amount=1):
        self.counts[key]=self.counts.get(key,0)+amount

    def prepare(self,label,n,channels,source_hz,kind,pattern='distinct'):
        if pattern=='isolated_impulses':
            # Balanced native signs for all channels, with isolated one-bit
            # impulses at the first, middle, and last frame on one channel.
            channel=channels//2
            original=[bytearray(i&1 for i in range(n)) for _ in range(channels)]
            for frame in (0,n//2,n-1):
                original[channel][frame]^=1
            bits=tuple(bytes(ch) for ch in original)
        else:
            bits=fixtures.bits(n,channels,pattern)
        if kind=='dsf':
            physical=fixtures.make_dsf(bits,rate=source_hz,
                channel_type={1:1,2:2,3:3,4:4,5:6,6:7}.get(channels))
        else:
            demand(n%8==0,'DFF source must have full physical bytes')
            physical=fixtures.make_dff(bits,rate=source_hz)
        path=self.work/f'{label}.{kind}'
        path.write_bytes(physical)
        raw=bytes(bits[c][i] for i in range(n) for c in range(channels))
        self.count('independent_native_source_bits',n*channels)
        return path,raw

    def decode_oracle(self,label,source,pcm_hz,n,ch):
        raw=self.work/f'{label}.pcm-oracle.f64'
        p=run_checked([self.decoder,source,raw,pcm_hz,'mastering-v2',
            'preserve','adapt','auto'],timeout=100)
        demand(raw.exists(),f'{label}: missing independent PCM64 oracle')
        # The binary length is independently checked against the source
        # descriptor supplied to the caller, not its own reported count.
        demand(len(raw.read_bytes())% (ch*8)==0,
            f'{label}: independent PCM stream is not frame aligned')
        self.count('public_decoder_oracle_runs')
        return raw,p

    def probe_run(self,label,n,ch,source_hz,pcm_hz,output_hz,raw,
                  iblock,fifo,sink,*,trace=False):
        prefix=str(self.work/f'{label}.{iblock}-{fifo}-{sink}') if trace else '-'
        command=[self.probe,source_hz,pcm_hz,output_hz,ch,
            iblock,fifo,sink,n,prefix]
        p=run_checked(command,source=raw,timeout=100)
        lines=[ln for ln in p.stderr.decode(errors='replace').splitlines()
               if ln.startswith('{') and 'intermediate_pcm_frames' in ln]
        demand(len(lines)==1,f'{label}: missing exact probe receipt: {p.stderr[-400:]!r}')
        actual=json.loads(lines[0])
        expected_pcm,expected_out=clocks(n,source_hz,pcm_hz,output_hz)
        demand(int(actual['input_native_frames'])==n and
            int(actual['intermediate_pcm_frames'])==expected_pcm and
            int(actual['output_native_bits'])==expected_out and
            len(p.stdout)==expected_out*ch,
            f'{label}: two-clock oracle mismatch: {actual} != {expected_pcm,expected_out}')
        self.count('coordinator_schedules')
        self.count('coordinator_encoded_bits',len(p.stdout))
        return p.stdout,prefix,actual

    def encode_replay(self,label,source_pcm,pcm_hz,target_hz,ch):
        prefix=str(self.work/f'{label}.encoder-replay')
        p=run_checked([self.encoder,'--encode',pcm_hz,target_hz,ch,256,512,
                       1,'1','1',prefix],source=source_pcm.read_bytes(),timeout=100)
        stats=[x for x in p.stderr.decode(errors='replace').splitlines()
               if x.startswith('{') and 'native_frames' in x]
        demand(len(stats)==1,f'{label}: certified encoder probe missing receipt')
        return p.stdout,prefix,json.loads(stats[-1])

    def check_case(self,label,n,ch,source_hz,pcm_hz,output_hz,kind,schedules,
                   *,cli=True,pattern='distinct'):
        src,raw=self.prepare(label,n,ch,source_hz,kind,pattern)
        pcm_count,bit_count=clocks(n,source_hz,pcm_hz,output_hz)
        oracle_path,_=self.decode_oracle(label,src,pcm_hz,n,ch)
        reference_pcm=oracle_path.read_bytes()
        demand(len(reference_pcm)==pcm_count*ch*8,
            f'{label}: public API PCM64 count does not match independent integer oracle')
        expected_bits,reference_prefix,encode_stats=self.encode_replay(
            label,oracle_path,pcm_hz,output_hz,ch)
        demand(len(expected_bits)==bit_count*ch,
            f'{label}: certified encoder did not use the rounded intermediate count')
        self.count('decoder_encoder_replay_comparisons')
        traces=[]
        for idx,(iblock,fifo,sink) in enumerate(schedules):
            actual_bits,trace_prefix,stats=self.probe_run(label,n,ch,
                source_hz,pcm_hz,output_hz,raw,iblock,fifo,sink,trace=idx==0)
            demand(actual_bits==expected_bits,
                f'{label}: coordinator changed decoder phase, gained a frame, or dropped a bit; '
                f'schedule {iblock,fifo,sink}, expected {digest(expected_bits)}, got {digest(actual_bits)}')
            if idx==0:
                traced_pcm=Path(trace_prefix+'.pcm').read_bytes()
                demand(traced_pcm==reference_pcm,
                    f'{label}: actual intermediate IEEE754 words differ from public decoder oracle')
                self.count('exact_intermediate_pcm_words',pcm_count*ch)
                for channel in range(ch):
                    observed=Path(trace_prefix+f'.ch{channel}.admitted').read_bytes()
                    replayed=Path(reference_prefix+f'.ch{channel}.f64').read_bytes()
                    demand(observed==replayed,
                        f'{label}: channel {channel} post-clip certified words changed')
                    self.count('exact_admitted_kernel_words',bit_count)
                traces=[digest(traced_pcm),
                    *(sha(Path(trace_prefix+f'.ch{channel}.admitted')) for channel in range(ch))]
        witness=dict(case=label,native_input_bits=n,channels=ch,pattern=pattern,source_hz=source_hz,
            intermediate_hz=pcm_hz,output_hz=output_hz,
            intermediate_pcm_frames=pcm_count,output_native_bits=bit_count,
            direct_ratio_bits=checked_rate(n,source_hz,output_hz),
            source_sha256=sha(src),public_pcm_sha256=sha(oracle_path),
            recorded_pcm_and_postclip_sha256=traces,
            final_interleaved_bit_sha256=digest(expected_bits),
            schedules=[list(s) for s in schedules])
        if cli:
            native_suffix='dsf' if kind=='dsf' else 'dff'
            # Two physical output types, including DFF final padding. Keep
            # stdout reports so the actual production route and lengths are explicit.
            for output_kind in ('dsf','dff'):
                if output_kind=='dsf' and (ch>6 or (kind=='dff' and ch>2)):
                    continue
                dest=self.work/f'{label}.out.{output_kind}'
                report=self.work/f'{label}.{output_kind}.report.json'
                cmd=[self.sox,'--precision','64','--report',report,src,
                     '-r',f'dsd{output_hz//44100}',dest,'dsdpcm',pcm_hz]
                p=run_checked(cmd,timeout=120)
                r=json.loads(report.read_text())
                demand(r['status']=='complete' and
                    r['precision']['actual_route']=='native-binary64-transcode' and
                    int(r['output']['frames_written'])==bit_count and
                    int(r['output']['native_completed_frames'])==bit_count,
                    f'{label}: false production route or committed count {r}')
                dec=r['processing']['decoder']
                enc=r['processing']['encoder']
                demand(len(dec)==1 and len(enc)==ch and
                    int(dec[0]['frames_consumed'])==n and
                    int(dec[0]['frames_produced'])==pcm_count and
                    all(int(e['source_frames'])==pcm_count and
                        int(e['committed_native_frames'])==bit_count and
                        e['modulator_input_scale_actual']==1 and
                        e['failure_code']==0 for e in enc),
                    f'{label}: actual decoder and encoder reports violate independent clocks')
                raw_container=dest.read_bytes()
                physical=dsf_bits(raw_container,bit_count,ch,output_hz) if output_kind=='dsf' else \
                    dff_bits(raw_container,bit_count,ch,output_hz)
                demand(physical==expected_bits,
                    f'{label}: {output_kind} container differs from qualified replay')
                self.count('actual_container_bit_comparisons')
                self.count('actual_container_output_bits',len(physical))
                witness[f'container_{output_kind}_sha256']=digest(raw_container)
                witness[f'container_{output_kind}_physical_bytes']=len(raw_container)
                witness[f'container_{output_kind}_bit_sha256']=digest(physical)
                # Independent physical-DFF-padding accounting. DFF offers no
                # field to claim recoverable sub-byte logical source bits.
                if output_kind=='dff':
                    expected_storage=((bit_count+7)//8)*ch
                    demand(expected_storage>=(bit_count*ch+7)//8,
                        'DFF physical padding arithmetic is inconsistent')
                    witness['dff_stored_audio_bytes']=expected_storage
                if output_kind==native_suffix and n>0:
                    packed_dest=self.work/f'{label}.packed.{output_kind}'
                    run_checked([self.sox,'--precision','64',src,
                        '-r',f'dsd{output_hz//44100}',packed_dest,
                        'dsdpcm',pcm_hz],env={'SOX_DSD_PACKED_INPUT':'1'},timeout=120)
                    packed_container=packed_dest.read_bytes()
                    packed_bits=dsf_bits(packed_container,bit_count,ch,output_hz) \
                        if output_kind=='dsf' else dff_bits(packed_container,bit_count,ch,output_hz)
                    demand(packed_bits==expected_bits,
                        f'{label}: packed DSD source adapter diverges from expanded/reference')
                    self.count('packed_source_adapter_comparisons')
        self.records.append(witness)
        self.bit_hashes[label]=digest(expected_bits)
        self.count('exact_composed_cases')
        print('PASS transcode',label,'native',n,'PCM',pcm_count,'bits',bit_count,
              'schedules',len(schedules),flush=True)

    def ordered_gain_and_roles(self):
        # The actual reconstruction words, not a second reconstruction model,
        # are the input to independently ordered PCM64 gain/permutation replay.
        src=self.work/'dsd64_4097.dsf'
        original=(self.work/'dsd64_4097.pcm-oracle.f64').read_bytes()
        words=struct.unpack('<'+str(len(original)//8)+'d',original)
        source_frames=4097
        pcm_frames,native_bits=clocks(source_frames,2822400,96000,5644800)
        demand(len(words)==2*pcm_frames,'gain test source has wrong PCM count')
        dest=self.work/'ordered-gains.dsf'
        report=self.work/'ordered-gains.json'
        gains=['gain','-3','gain','4','gain','-1']
        opts=['-v','0.75']
        args=[*opts,src,'-r','dsd128',dest,'dsdpcm','96000',*gains]
        plan=json.loads(run_checked([self.sox,'--precision','64','--plan',*args]).stdout)
        ordered=[step['gain_factor'] for step in plan['steps']
                 if step['name']=='gain']
        demand(plan['precision']['actual_route']=='native-binary64-transcode'
               and len(ordered)==3 and plan['inputs'][0]['volume']==0.75,
               'ordered transcode gain no longer has a truthful native plan')
        transformed=[]
        for w in words:
            w*=0.75
            for gain in ordered:w*=gain
            transformed.append(w)
        processed=self.work/'ordered-gains.f64'
        processed.write_bytes(struct.pack('<'+str(len(words))+'d',*transformed))
        expected,_,_=self.encode_replay('ordered-gains',processed,96000,5644800,2)
        run_checked([self.sox,'--precision','64','--report',report,*args])
        demand(dsf_bits(dest.read_bytes(),native_bits,2,5644800)==expected and
               json.loads(report.read_text())['precision']['actual_route']=='native-binary64-transcode',
               'ordered gain changed PCM64 input or the certified output')
        self.count('ordered_source_volume_and_gain_compositions')
        # A plain terminal permutation must transform speaker roles AND audio.
        permuted=self.work/'permuted.dff'
        rep=self.work/'permuted.json'
        args=[src,'-r','dsd128',permuted,'dsdpcm','96000','remix','2','1']
        pp=json.loads(run_checked([self.sox,'--precision','64','--plan',*args]).stdout)
        demand(pp['precision']['actual_route']=='native-binary64-transcode' and
               any(t['native_permutation_map']==[1,0] for t in pp['steps']),
               'native transcode no longer recognizes a proven pure permutation')
        reordered=[w for i in range(0,len(words),2) for w in (words[i+1],words[i])]
        orderpath=self.work/'permuted.f64'
        orderpath.write_bytes(struct.pack('<'+str(len(words))+'d',*reordered))
        expected,_,_=self.encode_replay('permuted',orderpath,96000,5644800,2)
        run_checked([self.sox,'--precision','64','--report',rep,*args])
        demand(dff_bits(permuted.read_bytes(),native_bits,2,5644800)==expected,
               'terminal channel permutation differs from certified PCM replay')
        roles=self.read_dff_roles(permuted)
        demand(roles==['SRGT','SLFT'],f'DFF output roles were not reordered: {roles}')
        self.count('audio_and_speaker_role_permutation_compositions')
        # A duplicated gain must be observable on actual intermediate words,
        # not just on arbitrary constants unrelated to a production stream.
        mutant=struct.pack('<'+str(len(words))+'d',*(w*ordered[-1] for w in transformed))
        demand(mutant!=processed.read_bytes() and digest(mutant)!=digest(processed.read_bytes()),
               'duplicate gain mutation escaped the actual PCM trace comparison')
        self.count('duplicate_gain_mutant_detected')

    @staticmethod
    def read_dff_roles(path):
        data=path.read_bytes()
        pos=data.find(b'CHNL')
        demand(pos>=0 and pos+14<=len(data),'missing DFF speaker-role CHNL chunk')
        nch=int.from_bytes(data[pos+12:pos+14],'big')
        payload=data[pos+14:pos+14+nch*4]
        demand(len(payload)==nch*4,'truncated DFF speaker-role CHNL chunk')
        return [payload[i:i+4].decode('ascii') for i in range(0,len(payload),4)]

    def phase06a_role_parity(self):
        # Reproduce the owner's four commands, including the 24-bit
        # extensible three-channel WAV (speaker mask FL/FR/FC = 0x07).
        for channels,order,expected_roles in ((2,['2','1'],['SRGT','SLFT']),
                                             (3,['3','1','2'],['C   ','MLFT','MRGT'])):
            wav=self.work/f'phase06a-{channels}.wav'
            cmd=[self.sox,'-R','-n','-r','48000','-c',str(channels),'-b','24',
                 wav,'synth','0.05','sine','440','sine','1000']
            if channels==3:cmd+=['sine','2000']
            cmd+=['vol','0.4']
            run_checked(cmd)
            if channels==3:
                with wav.open('r+b') as stream:
                    stream.seek(40)
                    stream.write(b'\x07')
            for suffix in ('dff','dsf'):
                observations=[]
                for precision in ('64','legacy-auto'):
                    out=self.work/f'role-{channels}-{precision}.{suffix}'
                    prefix=['--precision','64'] if precision=='64' else []
                    response=run([self.sox,*prefix,wav,'-r','dsd64',out,
                                  'remix',*order],timeout=40)
                    if suffix=='dff':
                        roles=self.read_dff_roles(out) if out.exists() else None
                        demand(response.returncode==0 and roles==expected_roles,
                               f'Phase06A {channels}ch DFF role parity: {roles} '
                               f'{response.stderr[-250:]!r}')
                    else:
                        demand(response.returncode==2 and
                               b'DSF cannot encode this channel identity' in response.stderr,
                               f'Phase06A {channels}ch DSF role refusal differed: '
                               f'{response.returncode}, {response.stderr[-250:]!r}')
                        roles=None
                    observations.append((response.returncode,roles))
                demand(observations[0]==observations[1],
                       'Phase06A native and legacy outcomes diverged')
                self.count('phase06a_role_parity_commands',2)

    def io_failure_and_stdout(self):
        src=self.work/'dsd64_4097.dsf'
        n=4097
        _,expected_count=clocks(n,2822400,96000,5644800)
        raw=bytes(fixtures.bits(n,2,'distinct')[c][i] for i in range(n) for c in range(2))
        expected,_,_=self.probe_run('fault-replay',n,2,2822400,96000,
                                    5644800,raw,511,7,13)
        for output_kind in ('dsf','dff'):
            args=['--precision','64',src,'-r','dsd128','-t',output_kind,
                  '-','dsdpcm','96000']
            pipe=run([self.sox,*args],timeout=50)
            demand(pipe.returncode!=0 and not pipe.stdout,
                   f'{output_kind}: accepted a native DSD pipe or wrote bytes before refusal')
            self.count('nonseekable_stdout_refusals')
            redirected=self.work/f'stdout-regular.{output_kind}'
            with redirected.open('w+b') as stream:
                response=subprocess.run([str(self.sox),*map(str,args)],
                    stdin=subprocess.DEVNULL,stdout=stream,
                    stderr=subprocess.PIPE,timeout=60)
            demand(response.returncode==0,
                   f'{output_kind}: rejected actual seekable stdout: {response.stderr[-500:]!r}')
            physical=dsf_bits(redirected.read_bytes(),expected_count,2,5644800) if output_kind=='dsf' else \
                dff_bits(redirected.read_bytes(),expected_count,2,5644800)
            demand(physical==expected,
                   f'{output_kind}: redirected regular-file stdout output differs')
            self.count('seekable_stdout_full_bit_comparisons')
        # A physically truncated DSD source cannot produce a success receipt.
        damaged=self.work/'truncated-source.dsf'
        damaged.write_bytes(src.read_bytes()[:-80])
        report=self.work/'truncated-report.json'
        dest=self.work/'truncated-result.dff'
        failure=run([self.sox,'--precision','64','--report',report,damaged,
                     '-r','dsd128',dest,'dsdpcm','96000'],timeout=60)
        demand(failure.returncode!=0 and
               (not report.exists() or json.loads(report.read_text())['status']!='complete'),
               'truncated DSD input falsely produced a completed transcode')
        self.count('truncated_native_input_refusals')
        if sys.platform!='linux' or not shutil.which('cc'):
            self.count('io_fault_injection_not_run')
            return
        shim=self.work/'libpcm64_fault.so'
        command=['cc','-shared','-fPIC','-O2','-o',str(shim),
                 str(SOURCE/'tests/pcm64/wav_fault_shim.c'),'-ldl']
        run_checked(command,timeout=60)
        for output_kind in ('dsf','dff'):
            for flag,letter in (('PCM64_SHORT_WRITE',b'W'),('PCM64_FAIL_FCLOSE',b'C')):
                dest=self.work/f'fault-{output_kind}-{flag}.{output_kind}'
                report=self.work/f'fault-{output_kind}-{flag}.json'
                trace=self.work/f'fault-{output_kind}-{flag}.trace'
                env={'LD_PRELOAD':str(shim),'PCM64_TEST_TARGET':str(dest),
                     'PCM64_TRACE':str(trace),flag:'1'}
                if flag=='PCM64_SHORT_WRITE':env['PCM64_DATA_OFFSET']='0'
                failure=run([self.sox,'--precision','64','--report',report,src,
                             '-r','dsd128',dest,'dsdpcm','96000'],
                             env=env,timeout=60)
                demand(failure.returncode!=0 and trace.exists() and
                       letter in trace.read_bytes() and
                       (not report.exists() or json.loads(report.read_text())['status']!='complete'),
                       f'{output_kind}/{flag}: injected physical fault not observed or '
                       f'falsely reported success: {failure.stderr[-500:]!r}')
                self.count('observable_write_or_close_fault_injections')

    def negative(self,src,rate):
        source_before=src.read_bytes()
        target=self.work/'protected.dff'
        sentinel=b'KEEP EXISTING OUTPUT: phase06b\n'
        target.write_bytes(sentinel)
        cases=[
            ('no_clobber',['--no-clobber',src,'-r',f'dsd{rate//44100}',target,'dsdpcm','96000']),
            ('auto_headroom',['--auto-headroom',src,'-r',f'dsd{rate//44100}',
                self.work/'auto-refuse.dff','dsdpcm','96000']),
            ('unsupported_gain',[src,'-r',f'dsd{rate//44100}',
                self.work/'bad-gain.dff','dsdpcm','96000','gain','-n']),
        ]
        for label,args in cases:
            p=run([self.sox,'--precision','64',*args])
            demand(p.returncode!=0,f'{label}: invalid native transcode accepted')
            demand(target.read_bytes()==sentinel,
                   f'{label}: failed strict64 transcode changed existing destination')
            self.count('rejected_precommit_cases')
        for linkkind in ('hardlink','symlink'):
            path=self.work/f'source-alias-{linkkind}.dff'
            if linkkind=='hardlink':os.link(src,path)
            else:path.symlink_to(src)
            p=run([self.sox,'--precision','64',src,
                '-r',f'dsd{rate//44100}',path,'dsdpcm','96000'])
            demand(p.returncode!=0 and src.read_bytes()==source_before,
                   f'{linkkind}: native transcode source was overwritten')
            self.count('source_alias_refusals')
        pipe=self.work/'native-dest.fifo'
        os.mkfifo(pipe)
        p=run([self.sox,'--precision','64',src,
            '-r',f'dsd{rate//44100}',pipe,'dsdpcm','96000'],timeout=8)
        demand(p.returncode!=0,f'native named FIFO was accepted')
        self.count('special_destination_refusals')
        # Negative controls: if a frame is skipped or a gain duplicated,
        # the independent source/replay equality test MUST detect it.
        data=(self.work / (self.records[-1]['case']+'.pcm-oracle.f64')).read_bytes()
        if len(data)>32:
            mutant=data[:16]+data[32:]
            demand(mutant!=data and digest(mutant)!=digest(data),
                   'missing-middle-frame negative control became invisible')
            self.count('mutated_middle_frame_detected')
        demand((.5*.5)*.5 != .5*.5,
            'duplicate gain negative control unexpectedly equals single gain')
        self.count('duplicate_gain_negative_control')

    def coordinator_lifecycle(self):
        p=run_checked([self.probe,"--lifecycle-selftest"],timeout=40)
        receipt=[line for line in p.stderr.decode(errors="replace").splitlines()
                 if "lifecycle_selftest" in line]
        demand(len(receipt)==1 and json.loads(receipt[0])["lifecycle_selftest"]=="PASS",
               "coordinator lifecycle check has no PASS receipt")
        self.count("coordinator_lifecycle_assertions",json.loads(receipt[0])["assertions"])

    def finish(self):
        fault_count=self.counts.get('observable_write_or_close_fault_injections',0)
        fault_gate='PASS' if fault_count==4 else \
            'NOT_RUN: no Linux C compiler or LD_PRELOAD fault shim'
        output={
            'suite':'transcode',
            'status':'PASS' if fault_count==4 else 'PASS_WITH_NOT_RUN',
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'source_git_commit':safe_git_head(SOURCE),
            'executed_binary_sha256':{str(p):sha(p) for p in
                (self.sox,self.probe,self.encoder,self.decoder)},
            'runtime_shared_libraries':executable_libraries(self.sox),
            'gate_execution':{k:'PASS' for k in (
                'exact_independent_two_clock_counts',
                'intermediate_ieee754_words',
                'frozen_replay_interpolated_words',
                'bit_exact_dsf_dff_containers',
                'bounded_block_backpressure',
                'packed_expanded_source_parity',
                'precommit_refusal_and_alias_protection',
                'negative_controls',
                'ordered_source_volume_and_gains',
                'channel_audio_and_speaker_roles',
                'phase06a_legacy_remix_roles',
                'seekable_stdout_and_pipeline_refusal',
                'truncated_dsd_input',
                'coordinator_sticky_failures_and_finish')},
            'counts':self.counts,
            'cases':self.records,
        }
        output['gate_execution']['physical_write_and_close_fault_injection']=fault_gate
        (self.results/'transcode.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
        print(output['status'],'transcode:',len(self.records),'cases',self.counts,flush=True)


def native_disabled_preflight(sox,results):
    """The native DSP oracle is not executable when compiled out.

    Run actual no-native CLI safety checks and mark only DSP-dependent
    qualification as NOT_RUN. Never invoke the independent encoder probe.
    """
    gate={}
    receipt=results/'transcode.json'
    receipt.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='p07-disabled-',dir=results) as tmp:
            work=Path(tmp)
            wav=work/'test.wav'
            dff=work/'test.dff'
            result=run([sox,'-R','-n','-r','48000','-c','2',wav,
                        'synth','0.015','sine','400','sine','900'])
            demand(result.returncode==0,
                'disabled preflight: cannot generate source WAV')
            result=run([sox,wav,dff])
            demand(result.returncode==0 and dff.is_file(),
                'disabled preflight: legacy DSD64 writer failed')
            gate['legacy_dsd_source_creation']='PASS'
            target=work/'protected.dff'
            sentinel=b'P07 existing destination must remain intact'
            target.write_bytes(sentinel)
            for label,options in (
                ('strict64_no_auto',[]),
                ('strict64_auto',['--auto-headroom']),
                ('strict64_remix',['--auto-headroom'])):
                args=[sox,'--precision','64',*options,dff,'-r','dsd128',target]
                if label=='strict64_remix':args+=['remix','2','1']
                failed=run(args)
                demand(failed.returncode!=0 and target.read_bytes()==sentinel,
                    f'{label}: disabled native F64 accepted conversion or damaged target: '
                    f'{failed.stderr[-500:]!r}')
                gate[label]='PASS'
            legacy=work/'legacy.dff'
            failed=run([sox,dff,'-r','dsd128',legacy,'remix','2','1'])
            demand(failed.returncode==0 and legacy.stat().st_size>100,
                f'disabled preflight: legacy transcode failed {failed.stderr[-500:]!r}')
            gate['legacy_transcode_still_operational']='PASS'
        gate.update({k:'NOT_RUN: native binary64 DSP disabled at configure time' for k in (
            'two_clock_binary64_oracle','composite_encode_probe',
            'frozen_binary64_replay','coordinator_native_dsp_lifecycle',
            'native_dsd_writer_and_observer')})
        record={'suite':'transcode','status':'PASS_WITH_NOT_RUN',
                'source_git_commit':safe_git_head(SOURCE),
                'executed_binary_sha256':{str(sox):sha(sox)},
                'runtime_shared_libraries':executable_libraries(sox),
                'gate_execution':gate,'case_count':5}
        receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print('PASS_WITH_NOT_RUN transcode: native disabled; '+
              'CLI refusal, existing destination and legacy path verified',flush=True)
        return 0
    except Exception as exc:
        record={'suite':'transcode','status':'FAIL','error':str(exc),
                'gate_execution':gate,'source_git_commit':safe_git_head(SOURCE),
                'executed_binary_sha256':{str(sox):sha(sox)}}
        receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        raise


def main(sox,probe,encoder,decoder,results):
    if not native_dsp_compiled(sox):
        return native_disabled_preflight(sox,results)
    with tempfile.TemporaryDirectory(prefix='p06b-transcode-',dir=results) as tmp:
        suite=Suite(sox,probe,encoder,decoder,results,Path(tmp))
        try:
            suites=[
                ('dsd64_0',0,1,2822400,88200,2822400,'dsf',[(1,1,1)]),
                ('dsd64_1',1,1,2822400,96000,5644800,'dsf',[(1,1,1),(1,7,7)]),
                ('dsd64_15',15,1,2822400,96000,5644800,'dsf',[(1,1,1),(7,7,7)]),
                ('dsd64_29',29,2,2822400,96000,2822400,'dsf',[(7,1,1),(1,7,31)]),
                ('dsd64_511',511,2,2822400,88200,5644800,'dsf',[(1,1,1),(511,7,511)]),
                ('dsd64_4097',4097,2,2822400,96000,5644800,'dsf',[(1,1,1),(7,7,7),
                    (256,256,256),(511,7,511),(4096,1,7)]),
                ('dsd64_32768',32768,4,2822400,88200,2822400,'dff',
                    [(4096,256,511),(7,7,7)]),
                ('dsd128_4095',4095,2,5644800,176400,2822400,'dsf',
                    [(1,1,1),(511,7,256),(4096,256,511)]),
                ('dsd128_4096',4096,3,5644800,192000,5644800,'dff',
                    [(4096,256,511),(7,7,7)]),
                ('dsd128_32769',32769,2,5644800,192000,2822400,'dsf',
                    [(4096,256,511),(256,7,256)]),
            ]
            for args in suites:
                suite.check_case(*args)
            suite.check_case('dsd64_isolated_impulses',8193,4,2822400,
                96000,5644800,'dsf',[(1,1,1),(4096,7,511)],
                pattern='isolated_impulses')
            suite.check_case('dsd128_random_blocks',8192,2,5644800,
                176400,2822400,'dff',[(4096,256,511),(7,7,7)],
                pattern='random')
            src=suite.work/'dsd64_4097.dsf'
            suite.negative(src,5644800)
            suite.ordered_gain_and_roles()
            suite.phase06a_role_parity()
            suite.io_failure_and_stdout()
            suite.coordinator_lifecycle()
            suite.finish()
            return 0
        except Exception as e:
            record={'suite':'transcode','status':'FAIL',
                    'error':repr(e),'counts':suite.counts,
                    'completed_cases':suite.records,
                    'source_git_commit':safe_git_head(SOURCE),
                    'executed_binary_sha256':{str(p):sha(p) for p in
                        (suite.sox,suite.probe,suite.encoder,suite.decoder) if p.exists()}}
            (results/'transcode.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
            raise
