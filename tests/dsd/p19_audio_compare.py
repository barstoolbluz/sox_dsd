#!/usr/bin/env python3
"""Experimental DSD1024 v1/v2 same-source PCM-reconstruction noise comparison.

Uses the public in-tree frozen mastering FIR coefficients in an independent
SciPy upfirdn decimation chain. Does NOT constitute a separate audio oracle,
a listener/device test, or high-rate encoder certificate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import numpy as np
from scipy.signal import upfirdn
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
import p10_corpus
RESULT=ROOT/'tests/dsd/results/P19_DSD1024_CORRECTION/audio-v1-v2-comparison.json'
COEFF=ROOT/'src/dsd_coeffs.h'
SAMPLE_HZ=176400
RATE=45158400
FACTOR=RATE//SAMPLE_HZ

def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):return sha(Path(path).read_bytes())

def coefficients(bank):
    m=re.search(r'\blsx_dsd_coeff_'+bank+r'\[\d+\]\s*=\s*\{(.*?)\};',
        COEFF.read_text(),re.S)
    if not m:raise RuntimeError('missing coeff bank '+bank)
    return np.asarray([float.fromhex(v.strip()) for v in m.group(1).split(',') if v.strip()],dtype=np.float64)

def decode(path,h,master):
    src=Path(path).read_bytes()
    sequence=np.unpackbits(np.frombuffer(src,dtype=np.uint8),bitorder='big')
    # bit chronology: scalar P10 private render emits MSB-first packed bits.
    pcm=sequence.astype(np.float64)
    del sequence
    pcm=pcm*2.-1.
    for stage in range(8):
        pcm=upfirdn(master if stage==7 else h,pcm,up=1,down=2)
    return pcm

def regression(y):
    start=int(.4*SAMPLE_HZ);stop=int(1.2*SAMPLE_HZ)
    y=y[start:stop]
    n=np.arange(start,stop,dtype=np.float64)
    phase=2*np.pi*997.*n/SAMPLE_HZ
    # Residual includes harmonics, reconstruction-filter errors, and noise,
    # but removes a fitted sinusoidal fundamental/DC and filter delay/gain.
    basis=np.column_stack((np.sin(phase),np.cos(phase),np.ones(len(n))))
    coefficients=np.linalg.lstsq(basis,y,rcond=None)[0]
    residual=y-basis@coefficients
    amp=float(np.hypot(coefficients[0],coefficients[1]))
    rms=float(np.sqrt(np.mean(residual**2,dtype=np.float64)))
    return dict(fundamental_peak=amp,fundamental_rms=amp/np.sqrt(2.),
        residual_rms=rms,residual_dbfs_rms=float(20*np.log10(max(rms*np.sqrt(2.),1e-300))),
        fundamental_to_residual_db=float(20*np.log10(max(amp/(np.sqrt(2.)*rms),1e-300))),
        fitted_dc=float(coefficients[2]),analyzed_pcm_frames=len(y),
        clipping_count=int(np.count_nonzero(abs(y)>.5+2/(2**31-1))))

def write_result_once(path, data):
    encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError(
                f'Refusing to overwrite differing P19 evidence: {path}. '
                'Use --results PATH to store this independent replay separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=RESULT,
                        help='JSON diagnostic path (existing differing evidence is never overwritten)')
    args = parser.parse_args()
    h=coefficients('halfband');master=coefficients('master64_256')
    case=next(c for c in p10_corpus.holdout_cases(11289600) if c['name']=='tone-997--6')
    raw,stimulus=p10_corpus.stimulus(case)
    result=dict(schema='P19/SDM-v1-v2-independent-FIR-decimation/1',native_hz=RATE,
        output_hz=SAMPLE_HZ,original_source_sha256=sha(raw),
        stimulus=stimulus,candidate_qualified=False,
        comparison_only=True,
        reference_coeff_sha256=file_sha(COEFF),
        method='upfirdn cascade 7 halfbands and one mastering, 256:1; fitted fundamental and DC over 0.4..1.2 sec',
        source_kernel='scalar',versions={})
    with tempfile.TemporaryDirectory(prefix='p19-audio-') as t:
        t=Path(t);(t/'input.f64le').write_bytes(raw)
        for v in ('v1','v2'):
            target=t/f'{v}.packed';monitor=t/f'{v}.json'
            cmd=[str(ROOT/'test/dsd_test_p10'),'--render',str(SAMPLE_HZ),str(RATE),
                f'encode.mastering.{v}.dsd1024','.5','training',str(t/'input.f64le'),
                str(target),str(monitor)]
            started=time.monotonic()
            cp=subprocess.run(cmd,cwd=ROOT,env={'LSX_DSD_SDM_KERNEL':'scalar'},
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
            if cp.returncode:raise RuntimeError(v+' failed '+cp.stderr.decode(errors='replace'))
            r=json.loads(monitor.read_text());frames=r['committed_native_frames']
            if frames!=round(case['seconds']*RATE) or r['failure'] or r['nonfinite_states']:
                raise RuntimeError('unexpected modulator failure '+v)
            decoded=decode(target,h,master)
            result['versions'][v]=dict(encoded_sha256=file_sha(target),
                output_bytes=target.stat().st_size,output_native_frames=frames,
                numeric_profile_id=f'encode.mastering.{v}.dsd1024',
                renderer_sha256=file_sha(ROOT/'test/dsd_test_p10'),
                binary_cpu_seconds=r['cpu_seconds'],
                observed_elapsed_seconds=time.monotonic()-started,
                diagnostic=regression(decoded),max_abs_state=r['max_abs_state'],
                excursions28=r['excursions28'])
    # Do not certify an arbitrary noise threshold; report reproducible raw facts.
    try:
        write_result_once(args.results, result)
    except RuntimeError as exc:
        print('P19 AUDIO COMPARISON REFUSED:', exc, file=sys.stderr)
        return 2
    for k,v in result['versions'].items():
        print(k,v['diagnostic'],'native',v['output_native_frames'],flush=True)
    print('P19 AUDIO COMPARISON DIAGNOSTIC ONLY',args.results)
    return 0
if __name__=='__main__':raise SystemExit(main())
