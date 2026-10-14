#!/usr/bin/env python3
"""P15 independent probe of *actual private SRC* passband, phase and aliases.

The test-only P07 exporter supplies deterministic linear PCM tones through the
production private SRC. The oracle is a freestanding least-squares sinusoidal
fit in the *output's* sample clock, not SoX's rate backend or an encoder SDM
reference. Out-of-band tests deliberately inspect folded downsampling aliases
and interpolated upsampling images, separately from source DSD noise.

Finite-stream edges are excluded from steady-state spectral fits, but P15's
paired-bit tests check those exact edges against finite convolution separately.
This sampled tone suite is a numerical *measurement*, not interval-certified
adaptive extrema; P06's adaptive full alias-image analysis remains mandatory.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import math
from pathlib import Path
import re
import subprocess

import numpy as np

P07_STATUS = re.compile(r'^P07 F64 exported: (\d+) samples, ratio (\d+)/(\d+)$')
DB_RIPPLE_LIMIT = 1e-4
ALIAS_DB_LIMIT = -160.


def run_tone(src_binary: Path, input_hz: int, output_hz: int, n: int,
             tone: float, *, timeout: int = 180) -> tuple[np.ndarray, dict]:
    args=[str(src_binary.resolve()),'--tone',str(input_hz),str(output_hz),str(n),
          format(tone,'.15g')]
    run=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    stderr=run.stderr.decode('utf-8',errors='replace').strip()
    expected=(n*output_hz+input_hz//2)//input_hz
    match=P07_STATUS.fullmatch(stderr)
    if run.returncode!=0 or not match or tuple(map(int,match.groups()))!=(expected,output_hz,input_hz):
        raise RuntimeError('P07 private SRC exporter failed or reported incorrect rate/count: '+stderr[-250:])
    if len(run.stdout)!=expected*8:
        raise RuntimeError('private SRC exporter truncated binary64 output')
    output=np.frombuffer(run.stdout,dtype='<f8')
    if not np.all(np.isfinite(output)):
        raise RuntimeError('nonfinite production SRC output')
    return output,dict(binary64_sha256=hashlib.sha256(run.stdout).hexdigest(),
                       input_hz=input_hz,output_hz=output_hz,source_frames=n,
                       output_frames=expected,tone_hz=tone)


def tone_fit(out: np.ndarray, hz: int, fundamental: float,
             *, remove: tuple[float,...]=()) -> dict:
    """Fit a known tone while removing DC and other tones simultaneously.

    Fixed time origin is the decoded/compensated output sample frame zero.
    No FFT-bin selection or power spectral density averaging hides aliases.
    """
    arr=np.asarray(out,dtype=np.float64)
    if arr.ndim!=1 or len(arr)<256 or not np.all(np.isfinite(arr)):
        raise ValueError('insufficient/nonfinite src samples')
    if not 0 < fundamental < hz/2:
        raise ValueError('fit frequency is not strictly below output Nyquist')
    # Reject first/last quarter to remove real finite-file SRC edge response.
    # The separate complete-chain tests measure the omitted endpoints.
    edge=len(arr)//4
    ix=np.arange(edge,len(arr)-edge,dtype=np.float64)
    sample=arr[edge:-edge]
    frequency=[fundamental]+[x for x in remove if x!=fundamental]
    columns=[np.ones(len(ix),dtype=np.float64)]
    for f in frequency:
        angle=(2*math.pi*f/hz)*ix
        columns.extend((np.sin(angle),np.cos(angle)))
    matrix=np.column_stack(columns)
    coef,_,rank,_=np.linalg.lstsq(matrix,sample,rcond=None)
    if rank != len(columns):
        raise ValueError('ill-conditioned tone/alias regression')
    amplitude=math.hypot(float(coef[1]),float(coef[2]))
    dc=float(coef[0]);phase=math.atan2(float(coef[2]),float(coef[1]))
    residual=sample-matrix@coef
    return dict(peak_amplitude=amplitude,
                phase_rad=phase,dc=dc,
                amplitude_db_relative_to_input=20*math.log10(max(amplitude/.5,1e-300)),
                residual_rms=float(np.sqrt(np.mean(residual*residual))),
                interior_output_samples=len(sample))


def evaluate(src_binary: Path, intermediate_hz: int, pcm_hz: int,
             effective_pass_hz: float, *, frames: int = 131072,
             raw_dir: Path | None = None,
             raw_prefix: str | None = None) -> dict:
    """Live spectral measurements for an SRC ratio and effective P limit."""
    if pcm_hz==intermediate_hz:
        return dict(schema='P15/production-private-src-spectral-v1',
                    status='IDENTITY_BYPASS',passed=True,
                    input_hz=intermediate_hz,output_hz=pcm_hz,
                    effective_pass_hz=effective_pass_hz,
                    passband=[],aliases=[],checks=0)
    if not 0 < effective_pass_hz < min(pcm_hz,intermediate_hz)/2:
        raise ValueError('invalid effective passband')
    if frames<8192:
        raise ValueError('SRC spectral window too short')
    if (raw_dir is None) != (raw_prefix is None):
        raise ValueError('raw acquisition requires both raw directory and relative prefix')
    def record_raw(data: np.ndarray, receipt: dict, tag: str) -> None:
        if raw_dir is None:
            return
        # Result locations are only trusted relative names, not host paths.
        if not raw_prefix.startswith('src-raw/') or not re.fullmatch(
                r'[A-Za-z0-9._/-]+',raw_prefix) or '..' in Path(raw_prefix).parts:
            raise ValueError('unsafe raw receipt locator')
        raw_dir.mkdir(parents=True,exist_ok=True)
        dest=raw_dir/(tag+'.f64')
        native=np.asarray(data,dtype='<f8')
        fd,tmp=tempfile.mkstemp(dir=raw_dir,prefix=dest.name+'.',suffix='.tmp')
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(native.tobytes())
                f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        receipt['raw_f64']=dict(file=raw_prefix+'/'+dest.name,
                                sha256=hashlib.sha256(native.tobytes()).hexdigest(),
                                bytes=int(native.nbytes),format='little-endian IEEE754 binary64')
    # Numerically distinct deterministic probes including both effective P
    # and 95%-Nyquist endpoint. Denominator is the true input source clock.
    fractions=(0.02,0.12,0.35,0.62,0.84,0.96,1.0)
    tones=sorted(set(float(f*effective_pass_hz) for f in fractions))
    # All tested frequencies are noncoherent, avoiding a single-bin accident.
    pass_rows=[];alias_rows=[]
    for i,f in enumerate(tones):
        out,receipt=run_tone(src_binary,intermediate_hz,pcm_hz,frames,f)
        record_raw(out,receipt,f'pass-{i:03}')
        fit=tone_fit(out,pcm_hz,f)
        row=dict(tone_hz=f,measured=fit,receipt=receipt,
                 passband_limit_db=DB_RIPPLE_LIMIT,
                 pass_ripple=abs(fit['amplitude_db_relative_to_input'])<=DB_RIPPLE_LIMIT)
        pass_rows.append(row)
    if intermediate_hz>pcm_hz:
        # Downsampling: input f=F-f_base must fold into an output passband
        # frequency f_base. All chosen f are past output Nyquist and within
        # source Nyquist; the SRC is required to suppress these images.
        for i,fraction in enumerate((0.05,0.25,0.45)):
            folded=pcm_hz*fraction
            source=pcm_hz-folded
            if source>=intermediate_hz/2:
                continue
            out,receipt=run_tone(src_binary,intermediate_hz,pcm_hz,frames,source)
            record_raw(out,receipt,f'alias-{i:03}')
            fit=tone_fit(out,pcm_hz,folded)
            row=dict(kind='input-image-folding',source_hz=source,
                    output_alias_hz=folded,measured=fit,receipt=receipt,
                    alias_limit_db=ALIAS_DB_LIMIT,
                    pass_alias=fit['amplitude_db_relative_to_input']<=ALIAS_DB_LIMIT)
            alias_rows.append(row)
    else:
        # Upsampling: one legitimate input tone can generate output images
        # at R +/- f. Fit image + main simultaneously; never infer images
        # from the total program-noise floor of a native one-bit recording.
        for i,fraction in enumerate((0.07,0.28,0.43)):
            source=intermediate_hz*fraction
            out,receipt=run_tone(src_binary,intermediate_hz,pcm_hz,frames,source)
            record_raw(out,receipt,f'alias-{i:03}')
            for f in (intermediate_hz-source, intermediate_hz+source):
                if not 0 < f < pcm_hz/2:
                    continue
                fit=tone_fit(out,pcm_hz,f,remove=(source,))
                row=dict(kind='upsampling-replica',source_hz=source,
                         output_alias_hz=f,measured=fit,receipt=receipt,
                         alias_limit_db=ALIAS_DB_LIMIT,
                         pass_alias=fit['amplitude_db_relative_to_input']<=ALIAS_DB_LIMIT)
                alias_rows.append(row)
    good=all(x['pass_ripple'] for x in pass_rows) and all(x['pass_alias'] for x in alias_rows)
    return dict(schema='P15/production-private-src-spectral-v1',
                status='SAMPLED_PASS' if good else 'SAMPLED_FAIL',passed=good,
                input_hz=intermediate_hz,output_hz=pcm_hz,frames_input=frames,
                effective_pass_hz=effective_pass_hz,
                method='actual private SRC F64 output; independent least-squares tone fit; separate finite-boundary tests',
                limiting_note='finite sampled tones; not a proof of all extrema/images or of the full native FIR',
                threshold_policy='section 6.1 composite 0.0001 dB / -160 dB, applied only to actually tested tones/images',
                passband=pass_rows,aliases=alias_rows,
                checks=len(pass_rows)+len(alias_rows))
