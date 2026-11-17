#!/usr/bin/env python3
"""Phase 07 qualified binary64 AUTO scan/replay acceptance.

Uses the production encoder and spool in a private C oracle. Its independent
stage observers compare each unattenuated native sample *bit for bit* across
scan and replay, including EOF drain, without modifying certified kernels.
The CLI layer validates real on-disk/streaming carriers and report semantics.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import struct
import subprocess
import tempfile
import time
from binary_receipts import native_dsp_compiled, executable_libraries, safe_git_head

SOURCE=Path(__file__).resolve().parents[2]
CEILING=0.5  # qualified v3 DSD64/128 owner override, not old v1 0.45
SEED='P07-20261117-native-unchanged'


def demand(condition,why):
    if not condition:
        raise AssertionError(why)


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<18),b''):
            h.update(block)
    return h.hexdigest()


def run(args,input_bytes=None,timeout=95):
    return subprocess.run([str(x) for x in args],input=input_bytes,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)


def wave_f64(path,frames,rate=48000,channels=2,pattern='mix'):
    """Write a real WAVE_FORMAT_IEEE_FLOAT 64-bit carrier without int32 PCM."""
    samples=[]
    for i in range(frames):
        for c in range(channels):
            if pattern=='silence':v=0.0
            elif pattern=='quiet':v=(-1 if c else 1)*math.ldexp(1.,-41)
            elif pattern=='strong':v=(-1 if c else 1)*(.91 if i!=frames//2 else 1.19)
            elif pattern=='tail':v=(-1 if c else 1)*(.99 if i==frames-1 else 0.)
            else:
                v=math.sin(2*math.pi*(i+1)*(c+1)*451./rate)*(.31 if c else .42)
                if i%37==0:v=math.ldexp(1.,-41)*(c+1)
            samples.append(v)
    payload=struct.pack('<'+'d'*len(samples),*samples)
    fmt=b'fmt '+struct.pack('<IHHIIHH',16,3,channels,rate,
                            rate*channels*8,channels*8,64)
    data=b'data'+struct.pack('<I',len(payload))+payload
    riff=b'WAVE'+fmt+data
    path.write_bytes(b'RIFF'+struct.pack('<I',len(riff))+riff)
    return len(payload)


def dff_roles(path):
    b=path.read_bytes()
    pos=b.find(b'CHNL')
    demand(pos>=0,'DFF output channel-role chunk missing')
    count=int.from_bytes(b[pos+12:pos+14],'big')
    return tuple(b[pos+14+4*i:pos+18+4*i].decode('ascii')
                 for i in range(count))


class Suite:
    def __init__(self,sox,probe,results,work):
        self.sox=Path(sox).resolve()
        self.probe=Path(probe).resolve()
        self.results=Path(results)
        self.work=Path(work)
        self.cases=[]
        self.cli=[]
        self.gates={}
        self.raw_perf=[]

    def probe_case(self,name,source,native,ch,frames,bs1,bs2,reference,pattern):
        command=[self.probe,source,native,ch,frames,bs1,bs2,reference,pattern,0,'run']
        p=run(command,timeout=120)
        demand(p.returncode==0,
               f'{name}: production scan/replay probe failed rc={p.returncode} '
               f'{p.stderr[-1400:]!r} {p.stdout[-500:]!r}')
        record=json.loads(p.stdout)
        demand(record['status']=='PASS','probe case did not have PASS receipt')
        demand(record['trace_words']==record['native_frames']*ch,
               'native trace omitted channel(s) or samples')
        expected=(2*frames*native+source)//(2*source)
        demand(record['native_frames']==expected,
               'independent source-derived count violated')
        demand(record['reference']==(1. if reference else .5),
               'actual reference policy mismatch')
        demand(0<record['gain']<=1 and record['peak']>=0,
               'nonfinite or boosting auto headroom')
        self.cases.append({'name':name,**record})

    def stage_oracle(self):
        # All selected frontend rate branches, two certified native clocks,
        # zero and one frame, noninteger ratios, variable channel counts,
        # float64 subnormals, -0 and below-int32 data.
        cases=[
            ('empty',44100,2822400,1,0,1,1,1,1),
            ('silence',48000,2822400,2,17,1,31,0,1),
            ('one-frame-tail',48000,2822400,2,1,1,11,1,2),
            ('one-frame-start',44100,2822400,1,1,1,255,0,3),
            ('noninteger-48-64',48000,2822400,2,113,7,31,0,0),
            ('noninteger-96-64',96000,2822400,3,257,17,1,1,0),
            ('dyadic-44-64',44100,2822400,2,511,211,256,1,2),
            ('dyadic-88-128',88200,5644800,2,513,13,251,0,0),
            ('noninteger-192-128',192000,5644800,4,31,31,1,1,0),
            ('noninteger-48-128',48000,5644800,2,4095,89,97,0,0),
            ('noninteger-96-128',96000,5644800,2,257,5,17,1,0),
            ('dyadic-176-128',176400,5644800,1,1,1,13,1,2),
            ('channels-asymmetric',88200,5644800,6,511,211,33,1,2),
            ('multichannel-drain',192000,5644800,6,8191,11,255,0,0),
        ]
        for name,source,native,ch,frames,bs1,bs2,reference,pattern in cases:
            self.probe_case(name,source,native,ch,frames,bs1,bs2,reference,pattern)
        # Repeat selected input exactly with disjoint block subdivisions,
        # including all-channel peak changes and EOF-only tail extrema.
        for name,rate,native,ch,n,pat in (
                ('fragmented-noninteger',48000,2822400,2,257,0),
                ('drain-only-peak',48000,2822400,2,1,2),
                ('asymmetric-DSD128',88200,5644800,6,31,2)):
            for bs1,bs2 in ((1,1),(7,251),(256,3)):
                self.probe_case(f'{name}-{bs1}-{bs2}',rate,native,ch,n,
                                bs1,bs2,1,pat)
        self.gates['all_channel_native_pregain_tap_bit_exact']='PASS'
        self.gates['frontend_profiles_finite_input_and_EOF_tails']='PASS'
        self.gates['independent_frame_counts_and_gain_formula']='PASS'

    def mutations_and_faults(self):
        faults=run([self.probe,'--faults'],timeout=20)
        demand(faults.returncode==0 and
               json.loads(faults.stdout)['status']=='PASS',
               f'spool sticky-fault cases failed: {faults.stderr[-700:]!r}')
        self.gates['spool_short_read_write_rewind_close_sticky']='PASS'
        for name,args,diagnostic in (
                ('int32_quantization',[48000,2822400,2,113,7,31,0,0,1,'run'],
                 'mutation detected: int32 spool'),
                ('missing_eof_tail',[48000,2822400,2,1,1,7,1,2,2,'run'],
                 'mutation detected: omitted EOF tail')):
            p=run([self.probe,*args],timeout=35)
            demand(p.returncode!=0 and diagnostic.encode() in p.stderr,
                   f'{name}: deliberate mutant escaped or failed for unrelated reason '
                   f'{p.returncode}: {p.stderr[-900:]!r}')
            self.gates['mutant_'+name+'_rejected']='PASS'

    def cli_case(self,name,source,args,dest,report,*,stream=None,expected_route=None):
        start=time.perf_counter()
        before=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        p=run([self.sox,'--precision','64','--auto-headroom',
               '--report',report,*args],input_bytes=stream,timeout=145)
        sec=time.perf_counter()-start
        demand(p.returncode==0,
               f'{name}: real CLI conversion failed rc={p.returncode} '
               f'{p.stderr[-1600:]!r}')
        demand(dest.is_file() and dest.stat().st_size>100,
               f'{name}: no complete physical DSD output')
        r=json.loads(report.read_text())
        demand(r['status']=='complete' and r['precision']['actual_pcm_engine']==
               'ieee754.binary64',f'{name}: incorrect completion or arithmetic route')
        if expected_route:
            demand(r['precision']['actual_route']==expected_route,
                   f'{name}: wrong precision route')
        h=r['processing'].get('headroom_scan')
        demand(h and h['method']=='source-rate-interleaved-binary64-two-pass',
               f'{name}: no actual binary64 two-pass evidence')
        gain=h['common_applied_gain'];peak=h['measured_scaled_peak']
        target=CEILING*(1.-1e-12)/peak if peak>CEILING else 1.
        demand(gain==target and 0<gain<=1,
               f'{name}: incorrect common attenuation {gain} vs {target}')
        demand(h['temporary_pcm_bytes']==str(
            int(h['captured_source_frames'])*h['channels']*8),
            f'{name}: spool bytes not source-rate binary64')
        demand(h['scan_native_frames']==r['output']['frames_written'],
               f'{name}: scan bit count and replay count disagree')
        demand(h['scan_seconds']>=0 and h['replay_seconds']>=0 and
               h['profile_id'] and h['backend'],
               f'{name}: missing model identity or pass timing')
        demand(r['processing']['encoder'] and all(
            e['source_frames']==h['captured_source_frames'] and
            e['committed_native_frames']==h['scan_native_frames'] and
            e['failure_code']==0 for e in r['processing']['encoder']),
            f'{name}: incorrect replay per-channel counts or failure flags')
        demand(max(float(e['headroom_applied_db']) for e in
            r['processing']['encoder'])-
            min(float(e['headroom_applied_db']) for e in
            r['processing']['encoder'])<1e-12,
            f'{name}: channel-dependent headroom')
        self.cli.append({'name':name,'report_sha256':sha256(report),
            'output_sha256':sha256(dest),'source_sha256':sha256(source) if source else None,
            'input_bytes':len(stream) if stream else
                         (source.stat().st_size if source else None),
            'output_bytes':dest.stat().st_size,
            'spool_bytes':int(h['temporary_pcm_bytes']),
            'native_frames':int(h['scan_native_frames']),
            'source_frames':int(h['captured_source_frames']),
            'source_rate':h['source_rate_hz'],'channels':h['channels'],
            'profile':h['profile_id'],'backend':h['backend'],
            'measured_peak':peak,'common_gain':gain,
            'scan_seconds':h['scan_seconds'],'replay_seconds':h['replay_seconds'],
            'wall_seconds':sec,'ru_maxrss_kb':resource.getrusage(
                resource.RUSAGE_CHILDREN).ru_maxrss,
            'previous_maxrss_kb':before})
        return r

    def cli_coverage(self):
        pcm=self.work/'source.wav'
        wave_f64(pcm,1027,48000,2,'mix')
        self.cli_case('stereo-DSD64',pcm,[pcm,'-r','dsd64',
            self.work/'stereo64.dff'],self.work/'stereo64.dff',
            self.work/'stereo64.json',expected_route='native-binary64-encode')
        silent=self.work/'silence.wav'
        wave_f64(silent,128,48000,2,'silence')
        r=self.cli_case('silence-unity',silent,[silent,'-r','dsd64',
            self.work/'silent.dff'],self.work/'silent.dff',
            self.work/'silent.json')
        demand(r['processing']['headroom_scan']['common_applied_gain']==1,
               'silence unexpectedly boosted or cut')
        small=self.work/'sub-int32.wav'
        wave_f64(small,514,96000,1,'quiet')
        self.cli_case('sub-int32-DSD128',small,[small,'-r','dsd128',
            self.work/'subint32.dsf'],self.work/'subint32.dsf',
            self.work/'subint32.json')
        strong=self.work/'strong.wav'
        wave_f64(strong,1031,48000,2,'strong')
        r=self.cli_case('fullscale-scan',strong,[strong,'-r','dsd64',
            self.work/'strong.dff'],self.work/'strong.dff',
            self.work/'strong.json')
        demand(r['processing']['headroom_scan']['common_applied_gain']<1,
               'peak above ceiling did not lower gain')
        # clip=error must not abort after a complete AUTO peak measurement.
        clip_dest=self.work/'clip-error.dff';clip_report=self.work/'clip-error.json'
        r=self.cli_case('auto-strict-clipping',strong,
            ['--dsd-clip','error',strong,'-r','dsd64',clip_dest],
            clip_dest,clip_report)
        demand(r['clipping']['encoder_interpolation']=='0',
               'AUTO attenuation still clipped in strict mode')
        # DSD64-to-DSD128: reconstruct ONCE into spool then replay encoder.
        seed=self.work/'seed.dff'
        p=run([self.sox,'-R',pcm,'-r','dsd64',seed]);demand(
            p.returncode==0, f'cannot generate DSD source: {p.stderr[-600:]!r}')
        output=self.work/'dsd-transcode.dff'
        r=self.cli_case('DSD64-DSD128-roles',seed,
            [seed,'-r','dsd128',output,'remix','2','1'],
            output,self.work/'dsd-transcode.json',
            expected_route='native-binary64-transcode')
        demand(dff_roles(output)==('SRGT','SLFT'),
               'DSD-to-DSD rate-changing remix lost physical channel identity')
        demand(len(r['processing']['decoder'])==1,
               'DSD-to-DSD source decoder was absent')
        out_sacd=self.work/'dsd-sacd.dff'
        self.cli_case('DSD64-sacd-reference',seed,
            ['--dsd-level','sacd',seed,'-r','dsd128',out_sacd,
             'gain','0','remix','2','1'],out_sacd,self.work/'dsd-sacd.json')
        demand(dff_roles(out_sacd)==('SRGT','SLFT'),
               'DSD-to-DSD explicit SACD level changed output speaker order')
        # An unseekable original source is processed once, not reread between
        # passes. The source-rate intermediate spool alone supports replay.
        pipe_out=self.work/'pipe-source.dff'
        r=self.cli_case('nonseekable-DFF-source',seed,
            ['-t','dff','-','-r','dsd128',pipe_out],pipe_out,
            self.work/'nonseekable.json',stream=seed.read_bytes())
        demand(r['processing']['headroom_scan']['captured_source_frames']!=None,
               'nonseekable input lacks finite captured source count')
        self.gates['real_wav64_intact_auto_input_and_unknown_length_DFF']='PASS'
        self.gates['real_pcm_and_DSD_transcode_two_pass_and_reporting']='PASS'
        self.gates['common_gain_fullscale_tail_and_silence']='PASS'
        self.gates['channel_roles_explicit_reference_and_strict_clip']='PASS'

    def safety_and_compatibility(self):
        seed=self.work/'seed.dff'
        target=self.work/'protected.dff'
        sentinel=b'Phase 07 source/output protection sentinel'
        target.write_bytes(sentinel)
        # No native operation is permitted to overwrite its source. Neither
        # a pre-existing destination nor a named FIFO can be edited on refusal.
        for label,args,protected in (
            ('same-source',[seed,'-r','dsd128',seed],seed),
            ('explicit-unsupported-effect',[seed,'-r','dsd128',target,
                                            'reverse'],target)):
            before=protected.read_bytes()
            p=run([self.sox,'--precision','64','--auto-headroom',*args])
            demand(p.returncode!=0 and protected.read_bytes()==before,
                   f'{label}: strict F64 failure mutated an existing path')
            self.gates['precommit_'+label]='PASS'
        legacy=self.work/'legacy-1.dff';legacy2=self.work/'legacy-2.dff'
        for dest in (legacy,legacy2):
            p=run([self.sox,'-R',seed,'-r','dsd128',dest,'gain','0',
                   'remix','2','1'])
            demand(p.returncode==0 and dff_roles(dest)==('SRGT','SLFT'),
                   'unchanged legacy path failed')
        demand(sha256(legacy)==sha256(legacy2),
               'legacy DSD-to-DSD route is not deterministic')
        self.gates['legacy_auto_native_policy_unchanged']='PASS'
        if os.name=='posix' and hasattr(os,'mkfifo'):
            fifo=self.work/'unsafe.fifo';os.mkfifo(fifo)
            p=run([self.sox,'--precision','64','--auto-headroom',seed,
                   '-r','dsd128',fifo],timeout=10)
            demand(p.returncode!=0,'AUTO accepted an unsupported named FIFO destination')
            self.gates['refuse_special_destination']='PASS'
        else:self.gates['refuse_special_destination']='NOT_RUN: POSIX FIFOs unavailable'

    def write(self,status,error=None):
        receipt={
            'suite':'headroom','status':status,'timestamp_utc':dt.datetime.now(
                dt.timezone.utc).isoformat(),'seed':SEED,
            'source_git_commit':safe_git_head(SOURCE),
            'executed_binary_sha256':{str(p):sha256(p) for p in
                (self.sox,self.probe) if p.exists()},
            'test_script_sha256':sha256(Path(__file__)),
            'runtime_shared_libraries':executable_libraries(self.sox),
            'gate_execution':self.gates,'test_cases':self.cases,
            'cli_executions':self.cli,'error':error,
        }
        (self.results/'headroom.json').write_text(json.dumps(receipt,indent=2,
                                                sort_keys=True)+'\n')
        print(status,'headroom:',len(self.cases),'native exactness cases,',
              len(self.cli),'CLI cases',flush=True)


def main(sox,probe,results):
    results=Path(results).resolve();results.mkdir(parents=True,exist_ok=True)
    (results/'headroom.json').unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='phase07-headroom-',dir=results) as tmp:
        suite=Suite(sox,probe,results,tmp)
        try:
            if not native_dsp_compiled(sox):
                # Executing a linked native C probe in this configuration can
                # only fail. Verify CLI capability semantics instead.
                from transcode import native_disabled_preflight
                native_disabled_preflight(sox,results)
                suite.gates['native_headroom_exactness']='NOT_RUN: native F64 compiled out'
                suite.gates['native_auto_CLI']='NOT_RUN: native F64 compiled out'
                suite.gates['disabled_build_source_and_output_safety']='PASS'
                suite.write('PASS_WITH_NOT_RUN')
                return 0
            suite.stage_oracle()
            suite.mutations_and_faults()
            suite.cli_coverage()
            suite.safety_and_compatibility()
            status='PASS_WITH_NOT_RUN' if any(str(v).startswith('NOT_RUN') for v in
                                               suite.gates.values()) else 'PASS'
            suite.write(status)
            return 0
        except Exception as exc:
            suite.write('FAIL',repr(exc))
            raise
