#!/usr/bin/env python3
"""Executable-backed Phase 05A return controls: fixed sound, truthful reports.

Focus only on the seven return observations; leave the independent numerical
oracles and the wider codec matrix to pcm-identity and output-formats.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from binary_receipts import safe_git_head, native_dsp_compiled
from output_formats import wav, wav_contents

SOURCE=Path(__file__).resolve().parents[2]


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Case:
    def __init__(self, exe, directory):
        self.exe=Path(exe).resolve();self.root=Path(directory).resolve()/'fixtures'/'return-acceptance'
        self.root.mkdir(parents=True,exist_ok=True)
        self.counts={};self.gates={};self.skips={};self.commands=0

    def call(self, args, data=None, success=True):
        cp=subprocess.run([str(self.exe),*map(str,args)],input=data,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35)
        self.commands+=1
        if success is True:
            require(cp.returncode==0,f'{args}: rc={cp.returncode} {cp.stderr[-450:]}')
        elif success is False:
            require(cp.returncode!=0,f'{args}: unexpected success')
        return cp

    def plan(self,args,data=None):
        cp=self.call(['--plan',*args],data=data)
        try:
            return json.loads(cp.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f'not a plan: {exc}; {cp.stdout[:150]}') from exc

    def gate(self,name,cases):
        self.gates[name]='PASS';self.counts[name]=cases

    def run(self):
        if not native_dsp_compiled(self.exe):
            src=self.root/'disabled-in.wav';dst=self.root/'disabled-out.wav'
            wav(src,[0,1,-1],16);dst.write_bytes(b'SENTINEL')
            p=self.plan(['--precision','64',src,dst])
            self.call(['--precision','64',src,dst],success=False)
            require(dst.read_bytes()==b'SENTINEL' and
                    p['precision']['actual_route']=='refused-before-output',
                    'disabled runner accepted strict64 or clobbered output')
            self.gate('disabled_strict64_refusal',2)
            self.gates['native_return_gates']='NOT_RUN: --disable-native-f64'
            return
        # Exact sample-order comparison for masked signed24 and high-channel
        # inputs. Compare payloads, not RIFF headers, which intentionally vary.
        for name,channels,mask in [('stereo',2,0x3),('six',6,0x3f),('thirtythree',33,None)]:
            vals=[((k*21193)%8000000)-4000000 for k in range(channels*9)]
            src=self.root/f'masked-{name}.wav';wav(src,vals,24,1,channels,mask)
            swap=list(range(1,channels+1));swap[0],swap[1]=swap[1],swap[0]
            effects=['remix',*map(str,swap)]
            a=self.root/f'native-{name}.wav';b=self.root/f'legacy-{name}.wav'
            p=self.plan(['--precision','64','-D',src,a,*effects])
            require(p['precision']['actual_route']=='native-binary64-pcm',
                    f'{name}: planner refused pure channel permutation')
            self.call(['--precision','64','-D',src,'-b','24',a,*effects])
            self.call(['-D',src,'-b','24',b,*effects])
            _,af,ap=wav_contents(a);_,bf,bp=wav_contents(b)
            require(af[2]==bf[2]==channels and ap==bp,
                    f'{name}: native channel order differs from legacy output')
            require(ap != wav_contents(src)[2],f'{name}: output did not reorder samples')
        self.gate('masked_and_33channel_audio_order',3)
        stereo=self.root/'volume-in.wav'
        wav(stereo,[4000,-12000,-16000,9000,12000,-20000],16,1,2)
        vol=self.root/'negative-volume.wav'
        p=self.plan(['--precision','64','-v','-1',stereo,'-e','floating-point','-b','64',vol])
        require(p['precision']['actual_route']=='native-binary64-pcm',
                'negative source volume not planned as executable')
        self.call(['--precision','64','-v','-1',stereo,'-e','floating-point','-b','64',vol])
        _,f,payload=wav_contents(vol)
        got=struct.unpack('<'+str(len(payload)//8)+'d',payload)
        require(f[2:5]==(2,48000,64) and
                tuple(got)==tuple(-v/32768. for v in [4000,-12000,-16000,9000,12000,-20000]),
                'negative source volume did not execute in binary64')
        mix=self.root/'gain-remix.wav';only=self.root/'gain-only.wav'
        self.call(['--precision','64','-D',stereo,'-b','64',only,'gain','-3'])
        p=self.plan(['--precision','64','-D',stereo,'-b','64',mix,'gain','-3','remix','2','1'])
        require(p['precision']['actual_route']=='native-binary64-pcm',
                'gain then remix is incorrectly refused')
        self.call(['--precision','64','-D',stereo,'-b','64',mix,'gain','-3','remix','2','1'])
        _,_,base=wav_contents(only);_,_,changed=wav_contents(mix)
        srcwords=[base[i:i+8] for i in range(0,len(base),8)]
        actual=[changed[i:i+8] for i in range(0,len(changed),8)]
        require(actual==[v for i in range(0,len(srcwords),2) for v in (srcwords[i+1],srcwords[i])],
                'preceding gain changed the pure remix mapping')
        for channels in (2,33):
            source=(stereo if channels==2 else self.root/'masked-thirtythree.wav')
            dest=self.root/f'channels-noop-{channels}.wav'
            p=self.plan(['--precision','64','-D',source,dest,'channels',str(channels)])
            require(p['precision']['actual_route']=='native-binary64-pcm',
                    f'{channels}: no-op channels refused')
            self.call(['--precision','64','-D',source,dest,'channels',str(channels)])
            require(wav_contents(dest)[2]==wav_contents(source)[2],
                    f'{channels}: no-op channels changed sample count or order')
        self.gate('negative_volume_gain_then_remix_and_noop_channels',4)
        # A piped WAV may be readable by legacy SoX, but cannot enter the
        # seekable input-descriptor native reader. Planning must say so.
        piped=self.root/'piped-destination.wav';piped.write_bytes(b'SENTINEL')
        incoming=stereo.read_bytes()
        args=['--precision','64','-t','wav','-',piped]
        p=self.plan(args,data=incoming)
        require(p['precision']['actual_route']=='refused-before-output' and
                'regular' in (p['precision']['fallback_or_refusal_reason'] or '').lower(),
                'piped WAV plan claims native eligibility or wrong refusal')
        self.call(args,data=incoming,success=False)
        require(piped.read_bytes()==b'SENTINEL','piped WAV run clobbered destination')
        self.gate('piped_wav_plan_and_run_agree',1)
        # Erroring report paths are tested before touching any audio output.
        for tag in ('missing-parent','directory','readonly'):
            target=self.root/f'report-error-{tag}.wav';target.write_bytes(b'SENTINEL')
            path=(self.root/'missing-subdirectory'/'report.json' if tag=='missing-parent'
                  else self.root/'report-as-directory' if tag=='directory'
                  else self.root/'report-readonly.json')
            if tag=='directory':path.mkdir(exist_ok=True)
            if tag=='readonly':path.write_text('unchanged');path.chmod(0o444)
            try:
                self.call(['--precision','64','--report',path,stereo,target],success=False)
                require(target.read_bytes()==b'SENTINEL',
                        f'{tag}: report precommit refusal damaged audio output')
            finally:
                if tag=='readonly':path.chmod(0o644)
        self.gate('report_precommit_sentinels',3)
        clip=self.root/'clip-in.wav';wav(clip,[32767,-32768,25000,-25000]*100,16)
        rpt=self.root/'clip-report.json';out=self.root/'clip-out.wav'
        cp=self.call(['--precision','64','--report',rpt,clip,'-b','24',out,'gain','12'])
        observed=json.loads(rpt.read_text())
        precision=observed['precision'];warnings=observed.get('warnings',[])
        require(observed['status']=='complete' and
                'actual retained' in precision['output_descriptor'] and
                warnings and any(w.encode() in cp.stderr for w in warnings),
                'successful report omits real acquired descriptor or printed warnings')
        self.gate('success_report_real_descriptor_and_warnings',1)
        large=self.root/'too-large-f64.wav';wav(large,[1.5e38,-1.5e38,0.,1.],64,3)
        failed=self.root/'failed-report.json';fout=self.root/'failed-float32.wav'
        cp=self.call(['--precision','64','--report',failed,large,'-e',
                      'floating-point','-b','32',fout,'gain','12'],success=False)
        got=json.loads(failed.read_text());reason=got.get('failure_reason') or ''
        require(got['status']=='failed' and 'numeric' in reason.lower() and
                'numeric' in cp.stderr.decode('utf-8','replace').lower() and
                'short' not in reason.lower(),
                'float32 overflow was falsely described as a physical write failure')
        self.gate('numeric_overflow_truthful_failure_report',1)
        streamrpt=self.root/'stdout-report.json'
        cp=self.call(['--precision','64','--report',streamrpt,stereo,
                      '-e','floating-point','-b','64','-t','wav','-'])
        stdout_report=json.loads(streamrpt.read_text())
        desc=stdout_report['precision']['output_descriptor']
        require(stdout_report['status']=='complete' and
                desc.startswith('actual ') and 'unresolved' not in desc and
                wav_contents_bytes(cp.stdout),
                'successful streaming report advertises a provisional descriptor')
        self.gate('stdout_execution_descriptor',1)


def wav_contents_bytes(data):
    # Validate the stream without storing an unbounded output in the fixture.
    return data[:4] in (b'RIFF',b'RIFX',b'RF64') and data[8:12]==b'WAVE'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',required=True,type=Path)
    parser.add_argument('--results',required=True,type=Path)
    args=parser.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    receipt=args.results/'return-acceptance.json';receipt.unlink(missing_ok=True)
    t=Case(args.sox,args.results)
    error=None
    try:
        t.run()
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}'
    record={'suite':'return-acceptance','status':'FAIL' if error else
            ('PASS_WITH_NOT_RUN' if any(str(v).startswith('NOT_RUN') for v in t.gates.values()) else 'PASS'),
            'error':error,'commands_executed':t.commands,'actual_checks':t.counts,
            'gate_execution':t.gates,'source_git_commit':safe_git_head(SOURCE),
            'executed_binary_sha256':{str(t.exe):sha(t.exe.read_bytes())}}
    receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(record['status']+' return-acceptance: '+str(t.counts))
    return 1 if error else 0


if __name__=='__main__':
    sys.exit(main())
