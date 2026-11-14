#!/usr/bin/env python3
"""Executable-backed Phase 05A return controls: fixed sound, truthful reports.

Focus only on the seven return observations; leave the independent numerical
oracles and the wider codec matrix to pcm-identity and output-formats.
"""
import argparse
import hashlib
import json
import math
import os
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

    def ordinary_effect_lifetimes(self):
        # These are ordinary SoX commands. A failed getopts/start must not
        # call a chain-owned stop() or release a private pointer twice.
        src=self.root/'ordinary-input.wav'
        wav(src,[1500,-3000,4000,-5000,6000,-7000],16,1,2)
        cases=[(('delay','abc'),1,b'cannot parse position'),
               (('delay','1x'),1,b'cannot parse position'),
               (('synth','1e999','sine','440'),1,b'cannot parse length'),
               (('stretch','1.1','1e999'),2,b'malloc size overflow')]
        for i,(fx,rc,reason) in enumerate(cases):
            dest=self.root/f'ordinary-error-{i}.wav'
            cp=self.call([src,dest,*fx],success=None)
            require(cp.returncode==rc and reason in cp.stderr,
                    f'ordinary effect {fx}: expected rc={rc} and {reason!r}; '
                    f'got {cp.returncode}, {cp.stderr[-400:]}')
        self.gate('ordinary_getopts_and_start_failures',len(cases))

    def returned_regressions(self):
        # WAVEFORMATEXTENSIBLE speaker masks are advisory. The native reader
        # must not require that bit count equals the actual channel count.
        cases=[('mask-stereo-one',2,0x4,24,1),
               ('mask-stereo-three',2,0x7,24,1),
               ('mask-six-two',6,0x3,24,1),
               ('mask-f64-high',2,0x80000000,64,3)]
        for name,channels,mask,bits,encoding in cases:
            if encoding==3:
                vals=[0.5 if j%2==0 else -0.25 for j in range(channels*9)]
            else:
                vals=[((j*38341)%2000000)-1000000 for j in range(channels*9)]
            src=self.root/f'{name}.wav';wav(src,vals,bits,encoding,channels,mask)
            for effect in ([],['remix','2','1',*map(str,range(3,channels+1))],
                           ['channels',str(channels)],
                           ['gain','-3','remix','2','1',*map(str,range(3,channels+1))]):
                if effect and effect[0]=='channels' and encoding==3:continue
                suffix='-'.join(effect)[:45] or 'copy'
                nat=self.root/f'native-{name}-{suffix}.wav'
                leg=self.root/f'legacy-{name}-{suffix}.wav'
                opts=['-D','-b','24']
                args=[src,*opts,nat,*effect]
                route=self.plan(['--precision','64',*args])['precision']
                require(route['actual_route']=='native-binary64-pcm',
                        f'{name} {effect}: native plan rejected: {route}')
                self.call(['--precision','64',*args])
                self.call(['-D',src,*opts,leg,*effect])
                nf,ns,np=wav_contents(nat);lf,ls,lp=wav_contents(leg)
                require(ns[2:5]==ls[2:5] and len(np)==len(lp),
                        f'{name} {effect}: channel/header/sample length disagrees')
                # Without gain, both routes represent the same integer audio
                # and are required to preserve each channel's sample order.
                if not effect or effect[0] in ('remix','channels'):
                    require(np==lp,f'{name} {effect}: channel payload differs from default route')
                else:
                    # Both paths apply the same gain, but a legacy int32
                    # boundary can differ by a least significant output bit.
                    n=[int.from_bytes(np[k:k+3],'little',signed=True) for k in range(0,len(np),3)]
                    l=[int.from_bytes(lp[k:k+3],'little',signed=True) for k in range(0,len(lp),3)]
                    require(all(abs(a-b)<=3 for a,b in zip(n,l)),
                            f'{name} {effect}: gained samples differ materially from default')
        self.gate('odd_speaker_mask_audio_and_terminal_operations',len(cases)*4-1)

        # Layout is an *audio* permutation in addition to WAV metadata. Test
        # two and six distinct samples per frame against default SoX.
        for channels,roles in ((2,'FR,FL'),(6,'FR,FL,FC,LFE,BL,BR')):
            samples=[(j*12361)%2000000-1000000 for j in range(5*channels)]
            src=self.root/f'role-input-{channels}.wav';wav(src,samples,24,1,channels)
            nat=self.root/f'role-native-{channels}.wav';leg=self.root/f'role-legacy-{channels}.wav'
            args=['--dsd-layout',roles,src,'-D','-b','24',nat]
            route=self.plan(['--precision','64',*args])['precision']
            require(route['actual_route']=='native-binary64-pcm',f'{channels}: refused layout')
            self.call(['--precision','64',*args]);self.call(['--dsd-layout',roles,src,'-D','-b','24',leg])
            actual=wav_contents(nat)[2];expected=wav_contents(leg)[2]
            require(actual==expected and actual!=wav_contents(src)[2],
                    f'{channels}: binary64 role assignment did not reorder audio as legacy')
        self.gate('explicit_role_mapping_matches_legacy_audio',2)

        # Classic wavpcm deliberately has no speaker mask, including when its
        # extensible source had no mask or an inconsistent one.
        for mask in (0,0x4):
            src=self.root/f'wavpcm-extensible-mask{mask}.wav'
            wav(src,[v*1000 for v in (1,-2,3,-4,5,-6)],24,1,2,mask)
            nat=self.root/f'wavpcm-native-{mask}.wav'
            leg=self.root/f'wavpcm-legacy-{mask}.wav'
            args=[src,'-D','-t','wavpcm',nat]
            route=self.plan(['--precision','64',*args])['precision']
            require(route['actual_route']=='native-binary64-pcm',
                    f'wavpcm mask={mask}: plan rejected {route}')
            self.call(['--precision','64',*args])
            self.call([src,'-D','-t','wavpcm',leg])
            require(wav_contents(nat)[2]==wav_contents(leg)[2] and
                    wav_contents(nat)[1][0]!=0xfffe,
                    f'wavpcm mask={mask}: output payload or classic header wrong')
        self.gate('wavpcm_extensible_sources',2)

        # Known 64-channel bound must be named in the refusal; generic
        # handler errors obscure the actual Phase 05A native-reader limit.
        src=self.root/'input-65ch.wav';wav(src,list(range(65*3)),16,1,65)
        out=self.root/'rejected-65ch.wav';out.write_bytes(b'SENTINEL')
        args=['--precision','64',src,out]
        p=self.plan(args)['precision'];reason=p['fallback_or_refusal_reason'] or ''
        require(p['actual_route']=='refused-before-output' and '64 channels' in reason,
                f'65-channel limit incorrectly reported: {reason}')
        cp=self.call(args,success=False)
        require(reason.encode() in cp.stderr and out.read_bytes()==b'SENTINEL',
                '65-channel runtime disagreeing with plan or clobbering destination')
        self.gate('reader_64_channel_limit_diagnostic',1)

        # Symlink to an uncreated report target and /dev/stdout into a pipe
        # are valid report destinations, independent from the audio stream.
        src=self.root/'report-valid-in.wav';wav(src,[200,-300,400,-500],16,1,2)
        out=self.root/'report-valid-output.wav'
        link=self.root/'report-dangling-link.json';target=self.root/'report-created-target.json'
        link.unlink(missing_ok=True);target.unlink(missing_ok=True)
        link.symlink_to(target.name)
        self.call(['--precision','64','--report',link,src,out])
        require(link.is_symlink() and target.is_file() and
                json.loads(target.read_text())['status']=='complete',
                'report symlink to uncreated target was not followed')
        if Path('/dev/stdout').exists():
            cp=self.call(['--precision','64','--report','/dev/stdout',src,out])
            require(json.loads(cp.stdout)['status']=='complete',
                    '/dev/stdout into a pipe did not receive valid JSON')
        self.gate('report_valid_symlink_and_stdout_pipe',2)

        # Planner may inspect metadata but must never open or alter the
        # output; output acquisition repeats the same alias/access checks.
        inp=self.root/'alias-original.wav';wav(inp,[100,-100,200,-200],16,1,2)
        before=inp.read_bytes()
        hard=self.root/'alias-hard.wav';soft=self.root/'alias-soft.wav'
        hard.unlink(missing_ok=True);soft.unlink(missing_ok=True)
        os.link(inp,hard);soft.symlink_to(inp.name)
        readonly=self.root/'output-readonly.wav';readonly.write_bytes(b'SENTINEL')
        readonly.chmod(0o444)
        rodir=self.root/'directory-readonly';rodir.mkdir(exist_ok=True);rodir.chmod(0o555)
        nodir=self.root/'directory-not-created'/'out.wav'
        cases=[(inp,inp,'aliases input'),(inp,hard,'aliases input'),
               (inp,soft,'aliases input'),(inp,readonly,'not readable and writable'),
               (inp,rodir/'out.wav','not writable'),
               (inp,nodir,'does not exist')]
        try:
            for source,dest,phrase in cases:
                before_dest=dest.read_bytes() if dest.exists() else None
                args=['--precision','64',source,dest]
                precision=self.plan(args)['precision']
                reason=precision['fallback_or_refusal_reason'] or ''
                require(precision['actual_route']=='refused-before-output' and phrase in reason,
                        f'{dest}: plan incorrectly accepted or wrong refusal: {reason}')
                require((dest.read_bytes() if dest.exists() else None)==before_dest,
                        f'{dest}: plan unexpectedly changed output')
                cp=self.call(args,success=False)
                require(reason.encode() in cp.stderr,
                        f'{dest}: run refusal differs from plan: {cp.stderr}')
                require((dest.read_bytes() if dest.exists() else None)==before_dest and
                        inp.read_bytes()==before,
                        f'{dest}: failed run destroyed an existing destination')
        finally:
            rodir.chmod(0o755);readonly.chmod(0o644)
        self.gate('planner_output_alias_permission_and_parent_refusals',len(cases))

        # A planner refusal is not an incomplete or claimed executable run.
        rpt=self.root/'refused-report.json';rout=self.root/'refused-output.wav'
        rpt.unlink(missing_ok=True);rout.write_bytes(b'SENTINEL')
        cp=self.call(['--precision','64','--report',rpt,src,rout,'vol','0.5'],success=False)
        doc=json.loads(rpt.read_text())
        reason=doc['precision']['fallback_or_refusal_reason']
        require(doc['status']=='refused' and doc['executable'] is False and
                doc['precision']['refused'] and
                doc['precision']['actual_route']=='refused-before-output' and
                'unsupported effect' in reason and
                reason.encode() in cp.stderr and
                doc['failure_reason'] and reason in doc['failure_reason'] and
                rout.read_bytes()==b'SENTINEL',
                f'refused report omitted real outcome: {str(doc)[:1500]}')
        self.gate('refused_report_status_route_reason_sentinel',1)

        # A getopts failure happens before a plan can exist. It must still
        # publish the parser's actual failure and may not claim it ran.
        early=self.root/'getopts-failed-report.json'
        early.unlink(missing_ok=True)
        cp=self.call(['--precision','64','--report',early,src,rout,
                      'delay','abc'],success=False)
        doc=json.loads(early.read_text())
        require(cp.returncode==1 and doc['status']=='failed' and
                doc['executable'] is False and doc['precision'] is None and
                'cannot parse position' in (doc['failure_reason'] or '') and
                rout.read_bytes()==b'SENTINEL',
                f'getopts failure report claims a plan or loses error: {doc}')
        self.gate('preplan_getopts_failure_report',1)

    def early_input_failure_reports(self):
        src=self.root/'early-report-input.wav';wav(src,[100,-200,300,-400],16)
        missing=self.root/'early-report-absent.wav';missing.unlink(missing_ok=True)
        malformed=self.root/'early-report-malformed.wav'
        malformed.write_bytes(b'RIFF\x0c\x00\x00\x00WAVEfmt BAD\x00\x00\x00')
        for tag,inputs,cause in [('missing-first',[missing],'No such file'),
                                  ('malformed',[malformed],'truncated'),
                                  ('missing-second',[src,missing],'No such file')]:
            report=self.root/f'early-{tag}.json';report.unlink(missing_ok=True)
            output=self.root/f'early-{tag}-output.wav';output.write_bytes(b'SENTINEL')
            cp=self.call(['--precision','64','--report',report,*inputs,output],
                         success=False)
            require(cp.returncode==2 and report.is_file(),
                    f'{tag}: input open failed without a report: {cp.stderr}')
            doc=json.loads(report.read_text());reason=doc.get('failure_reason') or ''
            require(doc['status']=='failed' and doc['executable'] is False and
                    doc['precision'] is None and cause.lower() in reason.lower() and
                    inputs[-1].name in reason and output.read_bytes()==b'SENTINEL',
                    f'{tag}: missing or inaccurate early failure: {doc}')
            if tag=='missing-second':
                sources=doc['source']
                require(len(sources)==2 and sources[0]['sample_rate_hz']==48000 and
                        sources[1]['sample_rate_hz'] is None,
                        f'second input failure lost partial acquisition: {sources}')
        self.gate('input_open_failure_reports_and_untouched_output',3)

    def file_option_failure_reports(self):
        # File-specific option validation exits before input acquisition.
        # The report must capture the original diagnostic without opening
        # or modifying the requested audio destination.
        src=self.root/'option-error-input.wav';wav(src,[100,-200,300,-400],16)
        cases=[('volume',lambda out:[src,'-v','0.5',out],
                b'-v can only be given for an input file'),
               ('ignore-length',lambda out:[src,'--ignore-length',out],
                b'--ignore-length can only be given for an input file'),
               ('compression',lambda out:['-C','5',src,out],
                b'a compression factor can be given only for an output file')]
        for tag,command,cause in cases:
            report=self.root/f'option-error-{tag}.json';report.unlink(missing_ok=True)
            output=self.root/f'option-error-{tag}-output.wav'
            output.write_bytes(b'SENTINEL')
            args=command(output)
            ordinary=self.call(args,success=False)
            cp=self.call(['--precision','64','--report',report,*args],success=False)
            require(cp.returncode==ordinary.returncode==1 and
                    cp.stderr==ordinary.stderr and cause in cp.stderr and
                    cp.stdout==ordinary.stdout==b'',
                    f'{tag}: exit status or terminal diagnostic changed: {cp.stderr}')
            require(report.is_file(),f'{tag}: missing failure report')
            doc=json.loads(report.read_text())
            require(doc['status']=='failed' and
                    cause.decode() in (doc.get('failure_reason') or '') and
                    output.read_bytes()==b'SENTINEL',
                    f'{tag}: wrong failure reason or output changed: {doc}')
        self.gate('file_option_failure_reports',len(cases))

    def missing_report_aliases(self):
        src=self.root/'alias-report-source.wav';wav(src,[200,-300,400,-500],16)
        sub=self.root/'alias-report-subdir';sub.mkdir(exist_ok=True)
        cases=[('relative',self.root/'link-relative.json',
                self.root/'alias-output-relative.wav','alias-output-relative.wav'),
               ('absolute',self.root/'link-absolute.json',
                self.root/'alias-output-absolute.wav',
                str(self.root/'alias-output-absolute.wav')),
               ('normalized',sub/'link-normalized.json',
                sub/'..'/'alias-output-normalized.wav','../alias-output-normalized.wav')]
        for tag,link,output,destination in cases:
            link.unlink(missing_ok=True);output.unlink(missing_ok=True)
            link.symlink_to(destination)
            for plan in (True,False):
                cp=self.call(['--precision','64',*(['--plan'] if plan else []),
                              '--report',link,src,output],success=False)
                require(cp.returncode==2 and b'--report' in cp.stderr and
                        b'audio output' in cp.stderr and not output.exists() and
                        link.is_symlink() and not cp.stdout,
                        f'{tag} plan={plan}: report alias accepted or audio touched: {cp.stderr}')
        self.gate('dangling_report_symlink_audio_alias_plan_and_run',6)

        for tag,absolute in [('relative',False),('absolute',True)]:
            link=self.root/f'valid-{tag}-link.json'
            target=self.root/f'valid-{tag}-target.json'
            output=self.root/f'valid-{tag}-audio.wav'
            for path in (link,target,output):path.unlink(missing_ok=True)
            link.symlink_to(str(target) if absolute else target.name)
            self.call(['--precision','64','--plan','--report',link,src,output])
            require(not output.exists() and
                    json.loads(target.read_text())['precision']['actual_route']==
                    'native-binary64-pcm',
                    f'{tag}: valid report link was rejected or plan opened audio')
            self.call(['--precision','64','--report',link,src,output])
            require(link.is_symlink() and output.is_file() and
                    json.loads(target.read_text())['status']=='complete',
                    f'{tag}: valid dangling report link failed during run')
        self.gate('separate_missing_report_targets_plan_and_run',4)

        hard=self.root/'report-input-hardlink.json';hard.unlink(missing_ok=True)
        os.link(src,hard);before=src.read_bytes()
        sentinel=self.root/'report-input-alias-output.wav';sentinel.write_bytes(b'SENTINEL')
        cp=self.call(['--precision','64','--report',hard,src,sentinel],success=False)
        require(cp.returncode==2 and b'input carrier' in cp.stderr and
                src.read_bytes()==before and sentinel.read_bytes()==b'SENTINEL',
                'early report validation missed an input hardlink')
        self.gate('unopened_input_report_identity_alias',1)

    def quiet_failure_reports(self):
        src=self.root/'quiet-overflow-in.wav'
        wav(src,[1.5e38,-1.5e38,0.,1.],64,3)
        reasons=[]
        for quiet in (False,True):
            tag='quiet' if quiet else 'normal'
            report=self.root/f'overflow-{tag}-report.json'
            output=self.root/f'overflow-{tag}-out.wav';report.unlink(missing_ok=True)
            cp=self.call([*(['-V0'] if quiet else []),'--precision','64',
                          '--report',report,src,'-e','floating-point','-b','32',
                          output,'gain','12'],success=False)
            doc=json.loads(report.read_text());reason=doc.get('failure_reason') or ''
            require(cp.returncode==2 and doc['status']=='failed' and
                    'numeric' in reason.lower() and 'represent' in reason.lower(),
                    f'{tag}: numeric failure absent from report: {doc}')
            if quiet:require(not cp.stderr and not cp.stdout,
                             f'-V0 leaked terminal diagnostics: {cp.stderr}')
            else:require(b'numeric' in cp.stderr.lower(),
                         'normal verbosity lost numeric diagnostic')
            reasons.append(reason)
        require(reasons[0]==reasons[1],
                f'verbosity changed reported failure cause: {reasons}')
        self.gate('quiet_numeric_failure_reason_matches_normal',2)

        valid=self.root/'quiet-success-report.json'
        self.call(['-V0','--precision','64','--report',valid,
                   self.root/'alias-report-source.wav',
                   self.root/'quiet-success-audio.wav'])
        doc=json.loads(valid.read_text())
        require(doc['status']=='complete' and doc['failure_reason'] is None,
                'quiet successful run invented a failure reason')
        self.gate('quiet_success_no_false_failure',1)

        refused=self.root/'quiet-refusal-report.json'
        cp=self.call(['-V0','--precision','64','--report',refused,
                      self.root/'alias-report-source.wav',
                      self.root/'quiet-refusal-audio.wav','vol','0.5'],success=False)
        doc=json.loads(refused.read_text())
        require(cp.returncode==2 and not cp.stderr and doc['status']=='refused' and
                'unsupported effect' in (doc.get('failure_reason') or ''),
                'quiet refusal lost its actual cause')
        self.gate('quiet_refusal_has_failure_reason',1)

    def run(self):
        self.ordinary_effect_lifetimes()
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
        self.returned_regressions()
        self.early_input_failure_reports()
        self.file_option_failure_reports()
        self.missing_report_aliases()
        self.quiet_failure_reports()


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
