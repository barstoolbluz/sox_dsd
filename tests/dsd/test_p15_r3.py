#!/usr/bin/env python3
"""P15-R3 candidate CLI/report/stream-count/selection regression; not release proof.

All audio cases are actually executed. The three v2 bank/cascade spectral
certificates are independently computed by certify_p15_r3_filters.py. This
suite cannot replace full source-bandwidth/SRC metrology or physical testing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave

from reference import fixtures

ROOT=Path(__file__).resolve().parents[2]
META=ROOT/'tests/dsd/reference/p15_r3_coefficients.json'
RATES=(2822400,5644800,11289600)
OUTPUTS=(44100,48000,88200,96000,176400,192000,352800,384000,705600)
POLICY={2822400:(25000,40000,88200,'master64_v2'),
        5644800:(48000,60000,176400,'master128_v2'),
        11289600:(66000,80000,176400,'master256_v2')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    exe=a.sox.resolve()
    if not exe.is_file():ap.error('executable not found')
    meta=json.loads(META.read_text())
    a.results.mkdir(parents=True,exist_ok=True)
    results=a.results/'selection-and-audio.json'
    rows=[]
    def save():
        overall='PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL'
        results.write_text(json.dumps({'schema':'sox-ng/p15-r3-integration/1',
          'status':overall, 'release_status':'BLOCKED',
          'limits':'selection/routing/counts/report identity; neither full SRC spectral proof nor physical benchmarking',
          'summary':{'passed':sum(row['status']=='PASS' for row in rows),
                     'failed':sum(row['status']=='FAIL' for row in rows)},
          'cases':rows},indent=2,sort_keys=True,allow_nan=False)+'\n')
    def case(name,fn):
        try:rows.append({'name':name,'status':'PASS','detail':fn()})
        except Exception as e:
            print('FAIL',name,str(e)[:350],flush=True)
            rows.append({'name':name,'status':'FAIL','error':f'{type(e).__name__}: {e}'})
        save()
    def expect(value,msg):
        if not value:raise AssertionError(msg)
    def run(*args):
        return subprocess.run([str(exe),*map(str,args)],stdin=subprocess.DEVNULL,
            capture_output=True,text=True,timeout=100,env={**os.environ,
            'SOX_OPTS':'','OMP_NUM_THREADS':'1','LC_ALL':'C'})
    def plan(*args):
        result=run('--dsd-plan',*args)
        expect(result.returncode==0,f'plan error: {result.stderr[-300:]}')
        return json.loads(result.stdout)
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='p15r3-') as work:
        t=Path(work)
        src={}
        for rate in RATES:
            src[rate]=t/f'dsd{rate//44100}.dsf'
            src[rate].write_bytes(fixtures.make_dsf(fixtures.bits(65536,2,'distinct'),rate))
        # Covers every v2 native/target clock with observed PCM and exact
        # profile ID, fixed response metadata, selected output rate and hash.
        for rate in RATES:
            P,S,R,bank=POLICY[rate]
            ident=f'decode.mastering.v2.dsd{rate//44100}'
            for out_hz in OUTPUTS:
                def execute(rate=rate,P=P,S=S,R=R,bank=bank,ident=ident,out_hz=out_hz):
                    dest=t/'out.wav';report=t/'report.json'
                    decision=plan('--dsd-decode',ident,src[rate],'-r',out_hz,dest)
                    dec=decision['decoder']
                    expect(dec['id']==ident,'profile ID collapsed to v1 in planner')
                    expect((dec['pass_hz'],dec['stop_hz'],dec['intermediate_hz'])==(P,S,R),
                        f'wrong P/S/R in plan: {dec}')
                    eff=P if out_hz==R else min(P,0.475*min(R,out_hz))
                    expect(abs(dec['effective_bandwidth_hz']-eff)<1e-8,'wrong effective passband')
                    expect(decision['output']['rate_hz']==out_hz,'wrong planned output clock')
                    expect(decision['executable'],'candidate cannot execute explicitly')
                    result=run('--dsd-mode','auto','--dsd-decode',ident,'--dsd-report',report,
                        '-D',src[rate],'-r',out_hz,'-e','signed-integer','-b',32,dest)
                    expect(result.returncode==0, f'actual v2 decode failed: {result.stderr[-350:]}')
                    with wave.open(str(dest),'rb') as f:
                        count=f.getnframes();channels=f.getnchannels();hz=f.getframerate()
                    expected=(65536*out_hz+rate//2)//rate
                    expect((count,channels,hz)==(expected,2,out_hz),
                           f'wrong WAV header/count {(count,channels,hz)}, expected {expected}')
                    data=json.loads(report.read_text())
                    # Decoders appear under "decoders" in the machine report.
                    items=data.get('processing',{}).get('decoder',[])
                    expect(len(items)==2,f'expected two per-channel decoder records: {len(items)}')
                    d=items[0]
                    expect(all(item['profile_id']==ident and item['coefficients']==d['coefficients']
                               for item in items),'channel identity or bank mismatch')
                    expect(d['profile_id']==ident,'actual decoder mislabeled v2 or switched bank')
                    expect(d['coefficients']['bank_last_sha256']==meta['banks'][bank]['rounded_hex_sha256'],
                        'actual decoder bank hash does not match v2 header')
                    expect(d['effective_passband_hz']==eff,'actual effective passband not reported')
                    expect(d['candidate_unqualified'] is True,'report incorrectly indicates qualification')
                    expect(int(d['filter_delay_native_frames'])==meta['profiles'][ident]['delay_native_frames'],
                        'report delay does not reflect new taps')
                    return dict(input_hz=rate,requested_pcm_hz=out_hz,
                        selected_pcm_hz=hz,frames=count,profile_id=ident,
                        pcm_sha256=sha(dest),bank_sha256=d['coefficients']['bank_last_sha256'])
                case(f'v2_actual_{rate//44100}_{out_hz}',execute)
            def default_rate(rate=rate,R=R,ident=ident):
                p=plan('--dsd-decode',ident,src[rate],t/'implicit.wav')
                expect(p['output']['rate_hz']==R,'implicit final PCM clock differs from policy')
                expect(p['output']['requested_rate_hz'] is None,'missing rate not recorded as implicit')
                return {'implicit_output_hz':R}
            case(f'v2_implicit_final_rate_{rate//44100}',default_rate)
            def wrong_pin(rate=rate):
                other=next(v for v in RATES if v!=rate)
                pin=f'decode.mastering.v2.dsd{other//44100}'
                x=run('--dsd-plan','--dsd-decode',pin,src[rate],t/'wrong.wav')
                expect(x.returncode!=0 and 'different native DSD clock' in x.stderr,
                       'wrong-clock v2 pin was not rejected')
                y=run('--dsd-mode','auto',src[rate],t/'wrong.wav','dsdpcm','-p',pin)
                expect(y.returncode!=0 and not (t/'wrong.wav').exists(),
                       'wrong-clock effect-level pin was not rejected')
                return {'wrong_pinned_id':pin,'cli_exit':x.returncode,'effect_exit':y.returncode}
            case(f'v2_wrong_native_rejected_{rate//44100}',wrong_pin)
            def strict(rate=rate,ident=ident):
                p=plan('--dsd-decode',ident,'--dsd-bandwidth','adapt',src[rate],'-r',44100,t/'low.wav')
                expect(p['decoder']['effective_bandwidth_hz']<POLICY[rate][0],
                       'adapt must narrow low-rate effective bandwidth')
                x=run('--dsd-plan','--dsd-decode',ident,'--dsd-bandwidth','strict',
                      src[rate],'-r',44100,t/'low.wav')
                expect(x.returncode!=0 and 'strict bandwidth rejects' in x.stderr,
                       'strict did not reject incompatible low rate')
                return {'adapt_effective_hz':p['decoder']['effective_bandwidth_hz']}
            case(f'v2_low_rate_adapt_strict_{rate//44100}',strict)
            def old_profiles(rate=rate):
                base='decode.mastering.v1.dsd'+str(rate//44100)
                wide='decode.wideband.v1.dsd'+str(rate//44100)
                expected={'mastering':base,'conservative':base,base:base,
                          'wideband':wide,wide:wide}
                hashes={}
                for alias,id in expected.items():
                    p=plan('--dsd-decode',alias,src[rate],t/'old.wav')
                    expect(p['decoder']['id']==id,'v1 alias was remapped')
                    dest=t/('old_'+alias.replace('.','_')+'.wav')
                    x=run('--dsd-mode','auto','--dsd-decode',alias,'-D',src[rate],
                          '-r',POLICY[rate][2],'-e','signed-integer','-b',32,dest)
                    expect(x.returncode==0,x.stderr[-300:]);hashes[alias]=sha(dest)
                expect(hashes[base]==hashes['mastering']==hashes['conservative'],
                       'v1 conservative aliases not byte-identical')
                expect(hashes[wide]==hashes['wideband'],'wideband v1 aliases diverged')
                return {'v1_mastering_sha256':hashes[base],
                        'v1_wideband_sha256':hashes[wide]}
            case(f'v1_pinned_conservative_wideband_{rate//44100}',old_profiles)
            def explicit_effect(rate=rate,ident=ident):
                dest=t/'effect.wav'
                p=plan('--dsd-mode','auto',src[rate],dest,'dsdpcm','-p',ident)
                expect(p['decoder']['id']==ident,'effect v2 ID collapsed')
                x=run('--dsd-mode','auto','-D',src[rate],dest,'dsdpcm','-p',ident)
                expect(x.returncode==0,x.stderr[-300:])
                return {'effect_id':ident,'actual_output_sha256':sha(dest)}
            case(f'v2_explicit_effect_{rate//44100}',explicit_effect)
            def conflicts(rate=rate,ident=ident):
                p=run('--dsd-plan','--dsd-decode',ident,src[rate],t/'conflict.wav',
                     'dsdpcm','-p','conservative')
                expect(p.returncode!=0 and 'conflicting' in p.stderr,
                       'conflicting global/explicit versions accepted')
                return {'conflict_exit':p.returncode}
            case(f'v2_vs_conservative_conflict_{rate//44100}',conflicts)
        for bad in ('decode.mastering.v0.dsd64','decode.mastering.v2.dsd512',
                    'decode.wideband.v2.dsd64'):
            def unknown(bad=bad):
                x=run('--dsd-plan','--dsd-decode',bad,src[2822400],t/'bad.wav')
                expect(x.returncode!=0,'unimplemented ID accepted')
                return {'id':bad,'exit_code':x.returncode}
            case('reject_unknown_'+bad,unknown)
        # Multichannel and non-multiple-of-decimation source lengths.
        for channels in (1,2,6):
            for frames in (1,32769,65539):
                for rate in RATES:
                    def edges(channels=channels,frames=frames,rate=rate):
                        input=t/'edge.dsf';dest=t/'edge.wav'
                        input.write_bytes(fixtures.make_dsf(fixtures.bits(frames,channels),rate))
                        ident=f'decode.mastering.v2.dsd{rate//44100}'
                        out_hz=POLICY[rate][2]
                        x=run('--dsd-mode','auto','--dsd-decode',ident,'-D',input,
                              '-r',out_hz,'-e','signed-integer','-b',32,dest)
                        expect(x.returncode==0,x.stderr[-350:])
                        with wave.open(str(dest),'rb') as wav:
                            # SoX leaves a RIFF unknown-size placeholder when
                            # zero PCM frames were emitted; inspect actual data
                            # bytes rather than trusting its 0xffffffff hint.
                            physical=len(wav.readframes(max(2,(frames*out_hz+rate//2)//rate+2)))
                            actual=(physical//(wav.getsampwidth()*wav.getnchannels()),
                                    wav.getnchannels(),wav.getframerate())
                        expected=((frames*out_hz+rate//2)//rate,channels,out_hz)
                        expect(actual==expected,f'edge WAV count/channels {actual} != {expected}')
                        return {'actual':actual,'frames_in':frames}
                    case(f'v2_boundary_{rate//44100}_{channels}ch_{frames}native',edges)
        # Bit-copy native path does not call any decoder, even when selected.
        def native_copy():
            original=t/'native_old.dsf';candidate=t/'native_v2.dsf'
            for target,args in ((original,()),(candidate,('--dsd-decode','decode.mastering.v2.dsd64'))):
                x=run('--dsd-mode','native',*args,src[2822400],target)
                expect(x.returncode==0,x.stderr[-350:])
            expect(sha(original)==sha(candidate),'native copy changed by decoder-only option')
            return {'native_output_sha256':sha(candidate)}
        case('native_dsd_repacking_unchanged',native_copy)
    save()
    final=json.loads(results.read_text())
    print('P15-R3 actual candidate integration:',final['status'],final['summary'],results)
    return 0 if final['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
