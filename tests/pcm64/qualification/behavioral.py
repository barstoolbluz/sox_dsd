#!/usr/bin/env python3
"""Production-behavior qualification at observable boundaries, not source fingerprints.

The expected digests were frozen after an independent admitted-word/kernel
recurrence check on the accepted f40966c build. They are not generated from
this checkout or regenerated when its accepted-source pin changes. Tests here
exercise real executables, real container bytes, the primitive API and a
real faulted output descriptor. No production code is instrumented beyond the
existing opt-in Phase 08 admission observer.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
from encode import make_wav, dsf_bits, dff_bits
from decode import parse_wav
from reconstruction_reference import check_unified_reconstruction_format

REF=HERE/'reference'/'accepted-physical-behavior.json'
RATE=2822400
CHANNELS=2


def insist(ok,reason):
    if not ok: raise AssertionError(reason)


def digest(data):return hashlib.sha256(data).hexdigest()


def wav_frames(name):
    if name=='overrange':
        rate,n=44100,1537
        def value(i,c):
            return ((1.27*math.sin(2*math.pi*(977+c*103)*i/rate)
                     if (i//129)%2==0 else
                     .02*math.sin(2*math.pi*1403*i/rate))
                    +(1.31 if i%173==7 else -1.39 if i%191==5 else 0.))
        effects=[]
    elif name=='gain_effect':
        rate,n=44100,1537
        def value(i,c):
            return ((.171 if c==0 else -.231)*
                    math.sin(2*math.pi*(997+c*137)*i/rate)+
                    (.035 if c==0 else -.025))
        effects=['gain','-6']
    elif name=='dff_nonbyte':
        rate,n=48000,31
        def value(i,c):
            return (.21 if c==0 else -.14)*math.sin(2*math.pi*997*i/rate)
        effects=[]
    else:
        raise AssertionError('unreviewed behavioral test scenario: '+name)
    return rate, [[value(i,c) for c in range(CHANNELS)] for i in range(n)],effects


def relative_command(argv,base):
    return [str(a).replace(str(base),'<RESULTS>') for a in argv]


def run_audio(sox,folder,golden):
    rows=[]
    for name in ('overrange','gain_effect','dff_nonbyte'):
        reference=golden['target_cases'][name]
        rate,frames,effects=wav_frames(name)
        key=f'{name}'
        raw=make_wav(folder/(key+'.source.wav'),frames,CHANNELS,rate)
        insist(digest(raw)==reference['source_pcm_words_sha256'],
               f'{key}: changed stimulus source words, not approved by reference')
        n=(len(frames)*RATE*2+rate)//(2*rate)
        insist(n==reference['native_frames'],f'{key}: wrong native source-derived count')
        ext='.dff' if name=='dff_nonbyte' else '.dsf'
        output=folder/(key+ext)
        report=folder/(key+'.report.json')
        prefix=folder/(key+'.admitted')
        fenv=folder/(key+'.fenv.json')
        argv=[str(sox),'-R','--precision','64','--headroom','0',
              '--dsd-clip','warn','--report',str(report),
              str(folder/(key+'.source.wav')),'-r',str(RATE),str(output),*effects]
        env={**os.environ,'SOX_P08_ADMITTED_PREFIX':str(prefix),
             'SOX_P08_FENV_PATH':str(fenv)}
        result=subprocess.run(argv,capture_output=True,env=env,timeout=120)
        insist(result.returncode==0 and output.is_file() and report.is_file(),
               f'{key}: real CLI failed status={result.returncode}: {result.stderr[-900:]!r}')
        from build_context import read_fenv
        read_fenv(fenv)
        bits=(dff_bits if ext=='.dff' else dsf_bits)(output.read_bytes(),n,CHANNELS,RATE)
        measured=digest(bits)
        insist(measured==reference['physical_dsd_bits_sha256'],
               f'{key}: actual physical DSD decisions differ from fixed independently accepted stream')
        info=json.loads(report.read_text())
        insist(info['status']=='complete' and
               info['precision']['actual_route']=='native-binary64-encode' and
               int(info['output']['frames_written'])==n and
               int(info['output']['native_completed_frames'])==n,
               f'{key}: wrong actual native DSD count/route; DFF padding may not add logical frames')
        enc=info['processing']['encoder']
        insist(len(enc)==CHANNELS and all(int(e['committed_native_frames'])==n for e in enc),
               f'{key}: incorrect physical channel/frame count')
        clipped=[int(e['clipped_interpolated_samples']) for e in enc]
        insist((all(v>0 for v in clipped) if name=='overrange'
                else all(v==0 for v in clipped)),
               f'{key}: wrong real clipping state')
        actual=[]
        for ch in range(CHANNELS):
            p=Path(str(prefix)+f'.ch{ch}.f64')
            insist(p.is_file() and p.stat().st_size==n*8,
                   f'{key}: missing actual modulator input words ch{ch}')
            h=digest(p.read_bytes())
            insist(h==reference['actual_postclip_sha256'][ch],
                   f'{key}: real admitted words ch{ch} differ from frozen independent boundary')
            actual.append(h)
        decoder_words=None
        if name=='gain_effect':
            # Real CLI native-DFF/DSF -> binary64 reconstruction, not the
            # shared-library API oracle used elsewhere for interface parity.
            decoded=folder/'gain_effect.reconstructed.wav'
            dec_report=folder/'gain_effect.decode.json'
            dec_command=[str(sox),'-R','--precision','64','--report',str(dec_report),
                         str(output),'-r',str(rate),'-e','floating-point','-b','64',
                         str(decoded)]
            cp=subprocess.run(dec_command,capture_output=True,timeout=120)
            insist(cp.returncode==0 and decoded.is_file() and dec_report.is_file(),
                   f'{name}: actual native64 decoder failed: {cp.stderr[-500:]!r}')
            decoder_record=json.loads(dec_report.read_text())
            insist(decoder_record['status']=='complete' and
                   decoder_record['precision']['actual_route']=='native-binary64-pcm' and
                   int(decoder_record['output']['frames_written'])==len(frames),
                   f'{name}: real decoder count/route differs from approved output')
            decoder_payload,_=parse_wav(decoded,len(frames),CHANNELS,rate)
            decoder_words=digest(decoder_payload)
            backend=decoder_record['processing']['decoder'][0]['fir_kernel_actual']
            reconstructed_numeric=check_unified_reconstruction_format(decoder_payload,backend)
        rows.append({'case':name,'cli_command':relative_command(argv,folder),
            'cli_exit':result.returncode,'source_pcm_words_sha256':digest(raw),
            'physical_dsd_bits_sha256':measured,'actual_postclip_sha256':actual,
            'native_frames':n,'clipped_samples':clipped,
            'reconstructed_float64_words_sha256':decoder_words,
            'reconstruction_numerical_check':reconstructed_numeric if decoder_words else None,
            'report_sha256':digest(report.read_bytes()),
            'executed_executable_sha256':digest(Path(sox).read_bytes())})
    return rows


def primitive_numeric(primitive):
    """Independent rational decisions, with half-step under-rounding controls."""
    tests=[]
    for bits in (8,16,24,32):
        half=math.ldexp(1.0,-bits)
        tests.extend((bits,x) for x in (
            math.nextafter(half,0.0), half,
            -math.nextafter(half,0.0),-half,
            math.nextafter(3*half,0.0),3*half,
            -math.nextafter(3*half,0.0),-3*half,
            math.nextafter(.5,0.0), math.nextafter(-.5,0.0)))
    script=''.join(f'Q {bits} {struct.unpack("<Q",struct.pack("<d",x))[0]:016x}\n'
                   for bits,x in tests).encode('ascii')
    cp=subprocess.run([str(primitive),'--stream'],input=script,
                      capture_output=True,timeout=15)
    insist(cp.returncode==0 and len(cp.stdout.splitlines())==len(tests),
           'compiled numerical primitive did not consume fixed half-step controls')
    for (bits,value),line in zip(tests,cp.stdout.decode().splitlines()):
        limit=1<<(bits-1)
        exact=Fraction.from_float(abs(value))*limit
        rounded=(2*exact.numerator+exact.denominator)//(2*exact.denominator)
        sign=-1 if math.copysign(1,value)<0 else 1
        saturated=rounded>=limit if sign>0 else rounded>limit
        code=max(-limit,min(limit-1,sign*rounded))
        aligned=code<<(32-bits)
        expected=f'Q {aligned&0xffffffff:08x} {int(saturated)} {int(value>=1. or value < -1.)}'
        insist(line==expected,
               f'compiled {bits}-bit quantizer disagrees with exact rational half-step: '
               f'{value.hex()} got={line} expected={expected}')
    return {'fractional_oracle':'Fraction.from_float, exact dyadic arithmetic',
            'checked_words':len(tests),'word_stream_sha256':digest(cp.stdout)}


def primitive_guard(primitive):
    reports=[]
    for command,mark in (('--selftest',b'SELFTEST assertions='),
                         ('--environment',b'ENV workers=')):
        cp=subprocess.run([str(primitive),command],capture_output=True,timeout=30)
        expected_status=b'status=PASS' if command=='--selftest' else b'status=OK'
        insist(cp.returncode==0 and mark in cp.stdout and expected_status in cp.stdout,
               f'compiled primitive failed independent {command} gate: '
               f'{cp.returncode}: {cp.stderr[-900:]!r}, {cp.stdout[-900:]!r}')
        if command=='--environment' and platform.machine() in ('x86_64','i386','i686'):
            insist(b'mxcsr=PASS x87=PASS' in cp.stdout,
                   'x86 hostile FENV register guard not exercised')
        reports.append({'command':command,'stdout':cp.stdout.decode().strip()})
    return reports


def close_failure(sox,folder,fixture):
    if platform.system()!='Linux':
        return {'status':'NOT_RUN','reason':'Linux LD_PRELOAD /proc fd test only'}
    compiler=shutil.which('cc')
    insist(compiler is not None,'no C compiler for live output-close fault injection')
    src=SOURCE/'tests/pcm64/wav_fault_shim.c'
    shim=folder/'output-fault.so'
    built=subprocess.run([compiler,'-shared','-fPIC','-o',str(shim),str(src),'-ldl'],
                         capture_output=True,timeout=30)
    insist(built.returncode==0 and shim.is_file(),
           f'output descriptor fault injector build failed: {built.stderr!r}')
    output=folder/'injected-close.dsf'
    report=folder/'injected-close-report.json'
    trace=folder/'injected-close.trace'
    argv=[str(sox),'--precision','64','--headroom','0',
          '--dsd-clip','warn','--report',str(report),
          str(folder/'gain_effect.source.wav'),'-r',str(RATE),str(output)]
    env={**os.environ,'LD_PRELOAD':str(shim),'PCM64_FAIL_FCLOSE':'1',
         'PCM64_TEST_TARGET':str(output),'PCM64_TRACE':str(trace)}
    cp=subprocess.run(argv,capture_output=True,env=env,timeout=90)
    insist(trace.is_file() and b'C' in trace.read_bytes(),
           'output-close fault injection did not actually reach physical writer')
    insist(cp.returncode!=0,
           'real SoX CLI incorrectly accepted a descriptor close error')
    insist(not report.exists() or json.loads(report.read_text()).get('status')!='complete',
           'real SoX CLI published complete status after descriptor close error')
    insist(not output.exists(),
           'failed physical output was retained after close refusal')
    return {'status':'PASS','fault':'fclose after successful physical writes',
            'trace_sha256':digest(trace.read_bytes()),
            'exit_status':cp.returncode,'report_status':
             json.loads(report.read_text())['status'] if report.exists() else None,
            'output_removed':not output.exists()}


def check(sox,primitive,results):
    sox,primitive=Path(sox).resolve(),Path(primitive).resolve()
    results=Path(results).resolve()
    fixture=json.loads(REF.read_text())
    insist(fixture['schema']=='phase08-approved-physical-behavior/1' and
           set(fixture['target_cases'])=={'overrange','gain_effect','dff_nonbyte'} and
           len(fixture['short_cases'])==18,'unreviewed or incomplete independent behavioral fixture')
    results.mkdir(parents=True,exist_ok=True)
    evidence=results/'behavioral-qualification.json'
    evidence.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='phase08-behavior-',dir=results) as t:
        folder=Path(t)
        numeric=primitive_numeric(primitive)
        guard=primitive_guard(primitive)
        audio=run_audio(sox,folder,fixture)
        close=close_failure(sox,folder,fixture)
        record={'schema':'phase08-built-executable-behavior/1','status':'PASS',
                'scope':'bounded physical and numeric runtime negative controls',
                'baseline_fixture_sha256':digest(REF.read_bytes()),
                'real_sox_sha256':digest(sox.read_bytes()),
                'primitive_sha256':digest(primitive.read_bytes()),
                'numeric':numeric,'arithmetic_environment':guard,
                'physical_audio':audio,'injected_close':close}
        evidence.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        return record


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sox',type=Path,required=True)
    p.add_argument('--primitive',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    a=p.parse_args()
    try: record=check(a.sox,a.primitive,a.results)
    except Exception as error:
        print(f'FAIL behavioral: {type(error).__name__}: {error}',file=sys.stderr)
        return 1
    print(f'PASS behavioral: {record["numeric"]["checked_words"]} primitive '
          f'half-step inputs, 3 real native DSD streams, '
          'actual PCM admissions, hostile FENV and output close')
    return 0

if __name__=='__main__': raise SystemExit(main())
