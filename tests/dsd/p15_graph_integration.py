#!/usr/bin/env python3
"""Optional P15 graph-path corroboration: genuine DSF, SoX PCM, threads, clip.

This is intentionally distinct from the binary64 numerical instrument. The
public SoX graph quantizes to signed int32 and therefore MUST NOT replace the
independent F64 sample/spectral oracle. Inputs are written by the independent
P00 fixture builder, not by the production codec under test.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import wave

import numpy as np
from reference import fixtures


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dsf_payload(bits: np.ndarray,native: int) -> bytes:
    b=np.asarray(bits,dtype=np.uint8)
    if b.ndim!=2 or b.shape[1] not in (1,2,5,6) or np.any(b>1):
        raise ValueError('graph test requires genuine supported one-bit streams')
    return fixtures.make_dsf(tuple(np.ascontiguousarray(b[:,i]).tobytes()
                                   for i in range(b.shape[1])),rate=native)


def invoke(sox: Path, argv: list[str], threads: int=1, timeout: int=180) -> dict:
    run=subprocess.run([str(sox.resolve()),*map(str,argv)],capture_output=True,
                       text=True,timeout=timeout,
                       env={**os.environ,'OMP_NUM_THREADS':str(threads),
                            'SOX_DSD_KERNEL_FIR':'scalar','LC_ALL':'C'})
    # Do not retain console text with temporary or machine-specific paths.
    return dict(returncode=run.returncode,
                stderr_contains_clip='clip' in run.stderr.lower(),
                stderr_contains_error='error' in run.stderr.lower())


def measure(sox: Path, native: int, pcm: int, profile: str,
            bits: np.ndarray, *, reference_f64: np.ndarray,
            raw_dir: Path | None = None, raw_prefix: str | None = None) -> dict:
    if not sox.is_file():
        raise ValueError('SoX graph binary missing')
    if (raw_dir is None)!=(raw_prefix is None):
        raise ValueError('graph raw capture requires both output directory and relative locator')
    if raw_prefix is not None and (not re.fullmatch(r'graph-raw/[A-Za-z0-9._/-]+',raw_prefix) or
       '..' in Path(raw_prefix).parts):
        raise ValueError('unsafe graph raw receipt path')
    n=bits.shape[0]
    expected=(n*pcm+native//2)//native
    pinned=f'decode.{profile}.v1.dsd{native//44100}'
    with tempfile.TemporaryDirectory(prefix='p15-graph-') as workspace:
        t=Path(workspace)
        source=t/'source.dsf';source.write_bytes(dsf_payload(bits,native))
        results=[]
        for mode in ('one_thread_tiny_chunks','two_threads_large_chunks'):
            destination=t/(mode+'.wav')
            argv=['--dsd-mode','auto','--dsd-decode',pinned,
                  '--dsd-level','preserve','--dsd-clip','error',
                  '--buffer','64' if mode.startswith('one') else '4096']
            if mode.startswith('one'):
                argv+=['--single-threaded']
            argv+=['-D',source,'-r',str(pcm),'-e','signed-integer','-b','32',destination]
            cmd=invoke(sox,argv,threads=1 if mode.startswith('one') else 2)
            if cmd['returncode']!=0 or not destination.is_file():
                raise AssertionError(f'graph conversion unsuccessful: {mode}; '+repr(cmd))
            with wave.open(str(destination),'rb') as wav:
                if wav.getnchannels()!=bits.shape[1] or wav.getframerate()!=pcm or \
                   wav.getsampwidth()!=4 or wav.getnframes()!=expected:
                    raise AssertionError('graph PCM header/count does not match original native timeline')
                actual=np.frombuffer(wav.readframes(expected),dtype='<i4').reshape(
                    expected,bits.shape[1]).astype(np.int64)
            # SoX's graph clips/rounds even when WAV would accept floats.
            # Keep the broad 1-int32-LSB convention; do not imply the float
            # intermediate and graph PCM have bit-identical representations.
            wanted=np.asarray(reference_f64,dtype=np.float64)
            if wanted.shape!=actual.shape:
                raise AssertionError('F64/graph shape mismatch')
            expected_pcm=np.rint(np.clip(wanted,-1.,1.)*(2**31-1)).astype(np.int64)
            difference=int(np.max(np.abs(actual-expected_pcm),initial=0))
            if difference>1:
                raise AssertionError(f'graph rounding vs public F64 exceeded one LSB: {difference}')
            results.append(dict(mode=mode,frames=expected,
                                output_pcm_sha256=sha(destination.read_bytes()),
                                maximum_int32_lsb_delta=difference,
                                exit_code=cmd['returncode']))
        if results[0]['output_pcm_sha256']!=results[1]['output_pcm_sha256']:
            raise AssertionError('graph buffer/thread switching changes PCM audio/container bytes')
        # Separate assured-clipping stream: an all-positive DSD input followed
        # by explicit SACD x2 gain; no hidden limiter may convert an expected
        # fatal graph crossing into a successful write.
        high=t/'all-positive.dsf'
        high.write_bytes(dsf_payload(np.ones((max(32768,n//4),1),dtype=np.uint8),native))
        blocked=t/'must-not-survive.wav'
        common=['--dsd-mode','auto','--dsd-decode',pinned,
                '--dsd-level','sacd','-D',high,'-r',str(pcm),
                '-e','signed-integer','-b','32',blocked]
        error=invoke(sox,['--dsd-clip','error',*common])
        if error['returncode']==0 or blocked.is_file() or not error['stderr_contains_clip']:
            raise AssertionError('explicit clip-error request failed to reject unsafe graph')
        warning_file=t/'clipped-with-warning.wav'
        warn=invoke(sox,['--dsd-clip','warn',*common[:-1],warning_file])
        if warn['returncode']!=0 or not warning_file.is_file() or not warn['stderr_contains_clip']:
            raise AssertionError('warn mode did not report graph saturation')
        raw_graph=[]
        if raw_dir is not None:
            # Publish complete graph evidence only *after* every graph policy
            # assertion passes. Interrupted, orphaned captures cannot become
            # committed measurements without a checksum-bound cell row.
            raw_dir.mkdir(parents=True,exist_ok=True)
            for original in (source,t/'one_thread_tiny_chunks.wav',
                             t/'two_threads_large_chunks.wav',warning_file):
                destination=raw_dir/original.name
                data=original.read_bytes()
                fd,tmp=tempfile.mkstemp(dir=raw_dir,prefix=destination.name+'.',suffix='.tmp')
                try:
                    with os.fdopen(fd,'wb') as f:
                        f.write(data);f.flush();os.fsync(f.fileno())
                    os.replace(tmp,destination)
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)
                raw_graph.append(dict(file=raw_prefix+'/'+destination.name,
                                      sha256=sha(data),bytes=len(data)))
        return dict(status='PASS',graph_results=results,threaded_vs_serial_pcm_identical=True,
                    native_bit_input_sha256=sha(dsf_payload(bits,native)),
                    clip_error_rejected=True,clip_warning_reported=True,
                    raw_graph=raw_graph,
                    level_policy='native bit stream, explicit SACD gain twice preserve',
                    note='public int32 graph; not substituted for independent F64 numerical oracle')
