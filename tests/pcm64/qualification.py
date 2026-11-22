#!/usr/bin/env python3
"""Phase 08: distinct bounded native64 synthetic family, not release certification.

This module runs the real SoX CLI and the preexisting private, independently
reproduced encoder recurrence. It retains native physical outputs and the
actual reconstructed FLOAT64 words. It does not relabel old harness jobs.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).with_name('qualification')))

import numpy as np
from binary_receipts import executable_libraries, safe_git_head
from decode import parse_wav, checked_rate
from encode import Suite as EncoderSuite, make_wav, dsf_bits, float_words
from build_context import read_fenv, build_context
from reconstruction_reference import check_unified_reconstruction_format

SOURCE = Path(__file__).resolve().parents[2]
SOURCE_RATE = 44100
FRAMES = 1537
CHANNELS = 2
RATES = (2822400, 5644800)
BETAS = (30.0, 34.0)
BANDS = {'20_20k':(20,20000),'20_30k':(20,30000),
         '20_40k':(20,40000),'20_50k':(20,50000),
         '20k_30k':(20000,30000),'30k_50k':(30000,50000),
         '50k_100k':(50000,100000),'100k_500k':(100000,500000),
         '500k_1m':(500000,1000000)}
PATTERNS = ('quiet','tone','near-rail','multitone','dc','silence',
            'impulse','transient','recovery')
WINDOW_LENGTH = 8192
FULL_SCALE_POWER = 0.125  # 0.5 maximum native DSD amplitude, sine RMS^2


def demand(condition, message):
    if not condition: raise AssertionError(message)


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1<<20),b''): h.update(b)
    return h.hexdigest()


def stimulus(pattern, n=FRAMES):
    # Distinct channel carriers avoid accidental channel-swap tolerance.
    out=[]
    for i in range(n):
        frame=[]
        for channel in range(CHANNELS):
            t=i/SOURCE_RATE
            sign=1 if channel==0 else -1
            if pattern=='quiet':
                x=sign*math.ldexp(1.,-40)*(1.+.25*math.sin(2*math.pi*439*t))
                if i%47==0: x=math.nextafter(x,math.inf)
            elif pattern=='tone':x=sign*.24*math.sin(2*math.pi*(997+channel*313)*t)
            elif pattern=='near-rail':x=sign*.489*math.sin(2*math.pi*(1103+channel*143)*t)
            elif pattern=='multitone':
                x=sign*(.15*math.sin(2*math.pi*(631+channel*131)*t)+
                        .11*math.sin(2*math.pi*(1663+channel*171)*t)+
                        .09*math.sin(2*math.pi*(4313+channel*97)*t))
            elif pattern=='dc':x=sign*.07
            elif pattern=='silence':x=-0.0 if channel else 0.0
            elif pattern=='impulse':x=sign*.42 if i==n//2 else 0.0
            elif pattern=='transient':
                x=sign*(.36 if n//4 <= i < n//4+128 else
                        -.22 if n//2 <= i < n//2+256 else 0.0)
            elif pattern=='recovery':
                x=(sign*(.49 if (i//79)%2==0 else -.49) if i<n//2
                   else sign*.18*math.sin(2*math.pi*(769+channel*199)*t))
            else: raise ValueError(pattern)
            demand(math.isfinite(x),'nonfinite stimulus')
            frame.append(x)
        out.append(frame)
    return out


def bandpower(values, rate, beta):
    # Preserve the audited half-open bands and weighted DC treatment.
    n=len(values)
    demand(n==WINDOW_LENGTH,'wrong analysis window')
    w=np.kaiser(n,beta)
    w2=w*w
    dc=float(np.sum(values*w2,dtype=np.float64)/np.sum(w2,dtype=np.float64))
    y=(values-dc)*w
    z=np.fft.rfft(y)
    power=(z.real*z.real+z.imag*z.imag)/(n*float(np.sum(w2,dtype=np.float64)))
    power[1:-1]*=2
    freqs=np.fft.rfftfreq(n,1/rate)
    bands={}
    for band,(lo,hi) in BANDS.items():
        left=int(np.searchsorted(freqs,lo,side='left'))
        right=int(np.searchsorted(freqs,hi,side='left'))
        band_power=float(np.sum(power[left:right],dtype=np.float64))
        demand(right>left and band_power>=0 and math.isfinite(band_power),
               'empty or invalid band: '+band)
        bands[band]={'power':band_power,
                     'dbfs':10*math.log10(max(band_power/FULL_SCALE_POWER,1e-300)),
                     'bins':[left,right]}
    return dc,bands


def plan_windows(native_frames):
    margin=4096
    n=WINDOW_LENGTH
    demand(native_frames>=3*n+2*margin,'cannot select independent windows')
    first=margin
    last=native_frames-margin-n
    starts=[first, (first+last)//2, last]
    demand(len(set(starts))==3 and all(0<=s<=native_frames-n for s in starts),
           'missing/overlapping window selection')
    return starts


def native_window(bits,channels,channel,start,length):
    return np.fromiter((.5 if bits[(f*channels)+channel] else -.5
                        for f in range(start,start+length)),
                       dtype=np.float64,count=length)


def run_cli(argv,timeout=120,env=None):
    cp=subprocess.run(list(map(str,argv)),capture_output=True,timeout=timeout,env=env)
    demand(cp.returncode==0,
           f'{argv}: status {cp.returncode}, stderr {cp.stderr[-1000:]!r}')
    return {'argv':list(map(str,argv)), 'exit_status':cp.returncode,
            'stdout_sha256':hashlib.sha256(cp.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(cp.stderr).hexdigest()}


def run_family(sox,probe,decode_oracle,results):
    results=Path(results).resolve()
    receipt=results/'qualification.json'
    receipt.unlink(missing_ok=True)
    sox=Path(sox).resolve();probe=Path(probe).resolve()
    decode_oracle=Path(decode_oracle).resolve()
    demand(decode_oracle.is_file(),'independent public decoder API oracle is required')
    family=results/'native64-family'
    family.mkdir(parents=True,exist_ok=True)
    # Never mistake incomplete or previous run outputs for current evidence.
    for old in family.iterdir():
        demand(not old.is_file() and not old.is_dir(),
               f'results root must be new and empty: {old}')
    from attestation import verify as verify_accepted_source
    verify_accepted_source(SOURCE)
    cases=[];windows=[];commands=[]
    with tempfile.TemporaryDirectory(prefix='q08-private-') as temp:
        from attestation import REFERENCE
        suite=EncoderSuite(sox,probe,results,Path(temp),
                           phase08_frozen_constants=REFERENCE)
        for hz in RATES:
            for pattern in PATTERNS:
                key=f'dsd{hz//44100}-{pattern}'
                frames=stimulus(pattern)
                wav=family/f'{key}.source.wav'
                dsf=family/f'{key}.encoded.dsf'
                recon=family/f'{key}.reconstructed.wav'
                enc_report=family/f'{key}.encode.json'
                dec_report=family/f'{key}.decode.json'
                original_words=make_wav(wav,frames,CHANNELS,SOURCE_RATE)
                source_hash=hashlib.sha256(original_words).hexdigest()
                # This variable works only in an expressly instrumented SoX
                # build. A plain production binary must fail, not generate an
                # unobserved admission hash from an independent probe.
                admission_prefix=family/f'{key}.admitted'
                encode_fenv=family/f'{key}.encode-fenv.json'
                decode_fenv=family/f'{key}.decode-fenv.json'
                commands.append(run_cli([sox,'--precision','64','--report',enc_report,
                                         wav,'-r',hz,dsf],
                    env={**os.environ,'SOX_P08_ADMITTED_PREFIX':str(admission_prefix),
                         'SOX_P08_FENV_PATH':str(encode_fenv)}))
                actual_encode_fenv=read_fenv(encode_fenv)
                expected_frames=(len(frames)*hz*2+SOURCE_RATE)//(2*SOURCE_RATE)
                physical=dsf_bits(dsf.read_bytes(),expected_frames,CHANNELS,hz)
                probe_bits,stats,admission=suite.probe_stream(frames,SOURCE_RATE,
                    CHANNELS,hz,ref=.5,clip=True,attenuation=1.)
                demand(physical==probe_bits,'physical bits differ from actual post-clip oracle')
                suite.frozen_oracle(hz,physical,stats,admission)
                actual_trace=[]
                for channel in range(CHANNELS):
                    path=Path(f'{admission_prefix}.ch{channel}.f64')
                    demand(path.is_file(),f'{key} channel {channel}: real CLI admission trace absent')
                    words=path.read_bytes()
                    expected_words=struct.pack(f'<{expected_frames}d',*admission[channel])
                    demand(len(words)==8*expected_frames and words==expected_words,
                           f'{key} channel {channel}: CLI post-clipping words disagree with probe')
                    actual_trace.append((path,words,expected_words))
                enc=json.loads(enc_report.read_text())
                demand(enc.get('status')=='complete' and
                       enc['precision']['actual_route']=='native-binary64-encode' and
                       int(enc['output']['frames_written'])==expected_frames and
                       len(enc['processing']['encoder'])==CHANNELS,
                       f'{key}: invalid real encoder report')
                commands.append(run_cli([sox,'--precision','64','--report',dec_report,
                                         dsf,'-b','64','-e','floating-point',
                                         '-r',SOURCE_RATE,recon],
                                         env={**os.environ,'SOX_P08_FENV_PATH':str(decode_fenv)}))
                actual_decode_fenv=read_fenv(decode_fenv)
                n_recon=checked_rate(expected_frames,hz,SOURCE_RATE)
                reconstructed,mask=parse_wav(recon,n_recon,CHANNELS,SOURCE_RATE)
                demand(n_recon>0 and len(reconstructed)==n_recon*CHANNELS*8,
                       'missing real F64 reconstruction')
                dec=json.loads(dec_report.read_text())
                demand(dec.get('status')=='complete' and
                       dec['precision']['actual_route']=='native-binary64-pcm' and
                       int(dec['output']['frames_written'])==n_recon,
                       f'{key}: decoder did not use genuine binary64 route')
                decoder=dec['processing']['decoder'][0]
                # CLI/API equality is an interoperability witness, not a second
                # FIR implementation. D16 keeps the historical v2 sample
                # words as a predecessor only; independent unified-decoder
                # numerical checks live in make check-phase08.
                check_unified_reconstruction_format(reconstructed,decoder['fir_kernel_actual'])
                demand(decoder['profile_id']==f'decode.mastering.dsd{hz//44100}' and
                       decoder['gain_mapping']['mode']=='preserve' and
                       decoder['fir_kernel_actual'] in ('scalar','sse2','avx1','avx2','avx512'),
                       f'{key}: unexpected decoder level/profile/backend')
                oracle_raw=family/f'{key}.public-oracle.f64'
                oracle_args=[decode_oracle,dsf,oracle_raw,SOURCE_RATE,
                             'mastering','preserve','adapt',decoder['fir_kernel_actual']]
                commands.append(run_cli(oracle_args))
                independent=oracle_raw.read_bytes()
                demand(independent==reconstructed,
                       f'{key}: real FLOAT64 reconstruction differs from public API oracle')
                starts=plan_windows(expected_frames)
                for channel in range(CHANNELS):
                    for start in starts:
                        q=native_window(physical,CHANNELS,channel,start,WINDOW_LENGTH)
                        for beta in BETAS:
                            x=np.frombuffer(actual_trace[channel][1],dtype='<f8',count=WINDOW_LENGTH,offset=start*8)
                            dc,metrics=bandpower(q-x,hz,beta)
                            windows.append({'case':key,'channel':channel,'start_frame':start,
                                'duration_frames':WINDOW_LENGTH,'window_kaiser_beta':beta,
                                'weighted_dc':dc,'bands':metrics})
                cases.append({'id':key,'rate_hz':hz,'source_rate_hz':SOURCE_RATE,
                    'pattern':pattern,'channels':CHANNELS,'source_frames':len(frames),
                    'native_frames':expected_frames,'reconstructed_frames':n_recon,
                    'source_pcm_words_sha256':source_hash,
                    'source_wav_sha256':sha256(wav),'physical_dsf_sha256':sha256(dsf),
                    'physical_dsd_bits_sha256':hashlib.sha256(physical).hexdigest(),
                    'reconstructed_float64_words_sha256':hashlib.sha256(reconstructed).hexdigest(),
                    'reconstructed_wav_sha256':sha256(recon),
                    'encoder_report_sha256':sha256(enc_report),
                    'decoder_report_sha256':sha256(dec_report),
                    # Expected words from an independent probe are *separate*
                    # from actual CLI bytes captured at lsx_pcmdsd_modulate.
                    'post_clip_admitted_sha256':[
                        hashlib.sha256(t[2]).hexdigest() for t in actual_trace],
                    'actual_admitted_sha256':[
                        hashlib.sha256(t[1]).hexdigest() for t in actual_trace],
                    'actual_admitted_paths':[
                        str(t[0].relative_to(results)) for t in actual_trace],
                    'admitted_frames_per_channel':[len(t[1])//8 for t in actual_trace],
                    'public_decoder_raw_sha256':hashlib.sha256(independent).hexdigest(),
                    'public_decoder_raw_path':str(oracle_raw.relative_to(results)),
                    'public_decoder_config':{
                        'profile':'mastering','level':'preserve','bandwidth':'adapt',
                        'kernel':decoder['fir_kernel_actual']},
                    'profile_id':enc['processing']['encoder'][0]['profile_id'],
                    'recovery_entries':[int(e['recovery_entries']) for e in enc['processing']['encoder']],
                    'peak_native':[e['peak_modulator_input'] for e in enc['processing']['encoder']],
                    'same_process_fenv':{'encode':{**actual_encode_fenv,
                        'path':str(encode_fenv.relative_to(results))},
                        'decode':{**actual_decode_fenv,
                        'path':str(decode_fenv.relative_to(results))}},
                    'source_path':str(wav.relative_to(results)),
                    'dsf_path':str(dsf.relative_to(results)),
                    'reconstructed_path':str(recon.relative_to(results)),
                    'encode_report_path':str(enc_report.relative_to(results)),
                    'decode_report_path':str(dec_report.relative_to(results)),
                    'analysis_starts':starts})
    demand(len(cases)==18 and len(windows)==108*2,'missing physical runs or spectral rows')
    source_files=['src/pcmdsd.c','src/dsd_f64.c','src/sox_ng.c',
                  'src/resonator/dsd64/src/constants.h',
                  'src/resonator/dsd128/src/constants.h',
                  'tests/pcm64/qualification.py',
                  'tests/pcm64/qualification/verify.py',
                  'tests/pcm64/qualification/fir_reference.py',
                  'tests/pcm64/qualification/independent_fir.py',
                  'tests/pcm64/qualification/fir_probe.c',
                  'tests/pcm64/qualification/reference_cascade.py',
                  'tests/pcm64/qualification/cascade_probe.c',
                  'tests/pcm64/decode/api_oracle.c', 'src/pcmdsd.h',
                  'tests/pcm64/qualification/build_context.py',
                  'tests/pcm64/qualification/attestation.py',
                  'tests/pcm64/qualification/reference/physical-source-contract.json',
                  'tests/pcm64/qualification/audited_spectrum.py',
                  'tests/pcm64/qualification/long_metrology.py',
                  'tests/pcm64/qualification/mutation_regression.py',
                  'tests/pcm64/qualification/sox_fenv_wrapper.c',
                  'tests/pcm64/qualification/behavioral.py',
                  'tests/pcm64/encode.py',
                  'tests/pcm64/qualification/reconstruction_reference.py',
                  'tests/pcm64/qualification/reference/accepted-reconstruction-sse2.zlib',
                  'tests/pcm64/qualification/reference/accepted-dsd64-constants.h',
                  'tests/pcm64/qualification/reference/accepted-dsd128-constants.h',
                  'tests/pcm64/qualification/reference/accepted-physical-behavior.json']
    record={'schema':'sox-native64-qualification/2',
        'status':'PASS',
        'scope':'FINITE_MEASUREMENTS_ONLY_NOT_RELEASE_CERTIFICATION',
        'source_git_commit':safe_git_head(SOURCE),
        'build_and_host':build_context(SOURCE),
        'accepted_production_revision':verify_accepted_source(SOURCE)['accepted_production_revision'],
        'timestamp':dt.datetime.now(dt.timezone.utc).isoformat(),
        'executed_binary_sha256':{str(sox):sha256(sox),str(probe):sha256(probe),
                                  str(decode_oracle):sha256(decode_oracle),
                                  **executable_libraries(sox)},
        'source_artifacts_sha256':{f:sha256(SOURCE/f) for f in source_files},
        'source_rate_hz':SOURCE_RATE,
        'full_scale':'nominal DSD = +/-0.5; sinusoidal full-scale RMS power 0.125',
        'measurement_signal':'native q minus actual post-clip modulator input x; no signal fitting',
        'spectrum_reference':'Audited harness dsdqual/analysis.py (nine bands; matched q-x)',
        'betas':BETAS,'bands_half_open_hz':BANDS,
        'no_free_gain_or_shift_fits':True,
        'analysis_note':'Direct physical native DSD bit windows; not a matched legacy residual. '
                        'No claim about inaudibility, DAC performance, ultrasonic release, '
                        'or numerical SRC floor.',
        'case_count':len(cases),'window_count':len(windows)//len(BETAS),
        'spectral_rows':len(windows)*len(BANDS),
        'cases':cases,'windows':windows,'commands':commands}
    receipt.write_text(json.dumps(record,indent=2,sort_keys=True,allow_nan=False)+'\n')
    return record


def main(sox,probe,decode_oracle,results):
    """The selected suite is successful only after each independent gate."""
    results=Path(results).resolve();results.mkdir(parents=True,exist_ok=True)
    receipt=results/'qualification.json'
    receipt.unlink(missing_ok=True)
    try:
        # Behaviour must reject a patched executable even when a maintainer
        # updates the accepted src/ hash inventory to match its changed files.
        # This gate observes executable results, not production-source identity.
        behavioral=[sys.executable,
            str(SOURCE/'tests/pcm64/qualification/behavioral.py'),
            '--sox',str(sox),
            '--primitive',str(Path(sox).resolve().parents[1]/'test/pcm64_probe'),
            '--results',str(results)]
        cp=subprocess.run(behavioral,capture_output=True,text=True,timeout=180,
                          env=dict(os.environ,OPENBLAS_NUM_THREADS='1'))
        demand(cp.returncode==0,'built-executable-behavior: '+cp.stderr[-1200:])
        record=run_family(sox,probe,decode_oracle,results)
        # Actual independent bit- and per-window re-reader; deliberate corruptions
        # are mandatory, not optional, in the committed qualification suite.
        gates=(
            ('physical-verifier', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/verify.py'),
                '--results',str(results),'--source',str(SOURCE),
                '--sox',str(sox),'--probe',str(probe),
                '--oracle',str(decode_oracle),'--negative-controls']),
            ('independent-fir', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/fir_reference.py'),
                '--source',str(SOURCE),'--results',str(results)]),
            ('independent-primitive-cascade', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/reference_cascade.py'),
                '--source',str(SOURCE),
                '--exporter',str(Path(sox).resolve().parents[1]/'test/dsd_test_p15_src_stage_export'),
                '--src-probe',str(Path(sox).resolve().parents[1]/'test/dsd_test_p07_reference'),
                '--cascade-probe',str(Path(sox).resolve().parents[1]/'test/pcm64_cascade_probe'),
                '--results',str(results)]),
            ('alignment', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/alignment.py'),
                '--results',str(results)]),
            ('cancellation', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/cancellation.py'),
                '--sox',str(sox), '--results',str(results/'cancellation')]),
            # Run the physical long-family kernel checks before the receiver
            # mutation fixture suite. A modified certified header must fail
            # against independent kernel words, not simply because the
            # receiver's own source patch would no longer apply.
            ('long-metrology', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/long_metrology.py'),
                '--sox',str(sox),
                '--unit',str(Path(sox).resolve().parents[1]/'test/dsd_test_p10'),
                '--results',str(results)]),
            ('receiver-mutations', [sys.executable,
                str(SOURCE/'tests/pcm64/qualification/mutation_regression.py'),
                '--mutants',str(SOURCE/'tests/pcm64/qualification/mutants'),
                '--results',str(results)]),
        )
        gate_results=[]
        for name, command in gates:
            cp=subprocess.run(command,capture_output=True,text=True,timeout=240,
                              check=False,env=dict(os.environ,OPENBLAS_NUM_THREADS='1'))
            gate_results.append({'name':name,'command':command,
                'exit_status':cp.returncode,'stdout':cp.stdout[-15000:],
                'stderr':cp.stderr[-4000:]})
            if cp.returncode:
                raise AssertionError(f'{name}: rc {cp.returncode} '+cp.stderr[-1000:])
        (results/'qualification-verification.json').write_text(json.dumps({
            'suite':'qualification-verification','status':'PASS',
            'source_git_commit':record['source_git_commit'],
            'qualification_sha256':sha256(receipt),
            'gates':gate_results},indent=2,sort_keys=True)+'\n')
    except Exception as e:
        # Never leave a PASS qualification receipt after a subsequent gate fails.
        (results/'qualification-failure.json').write_text(json.dumps({
            'suite':'qualification','status':'FAIL','error':str(e)},indent=2)+'\n')
        receipt.unlink(missing_ok=True)
        print(f'FAIL qualification: {type(e).__name__}: {e}',file=sys.stderr)
        return 1
    print(f"PASS qualification: {record['case_count']} physical cases, "
          f"{record['window_count']} windows, {record['spectral_rows']} spectral measurements; "
          "independent verifier, FIR, alignment and 20 cancellation cases")
    return 0
