#!/usr/bin/env python3
"""Acquire phase-periodic P15 private-SRC impulse observations, not a proof.

The source audited implementation must *independently* establish the finite
operator and a numerical error bound before these observations can become a
continuum certificate. A binary64 impulse probe alone cannot prove that its
very small tails are zero or that its effective taps match generated words.
This file never publishes PASS, regardless of the observed residual.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import numpy as np

P07_STATUS = re.compile(r'^P07 F64 exported: (\d+) samples, ratio (\d+)/(\d+)$')
ROOT = Path(__file__).resolve().parents[2]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def impulse(probe: Path, input_hz: int, output_hz: int,
            frames: int, at: int, timeout=120):
    if not 0 <= at < frames:
        raise ValueError('impulse outside finite input')
    args = [str(probe.resolve()), '--impulse', str(input_hz),
            str(output_hz), str(frames), str(at)]
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    expected = (frames * output_hz + input_hz//2)//input_hz
    match = P07_STATUS.fullmatch(proc.stderr.decode(errors='replace').strip())
    if (proc.returncode != 0 or not match or
        tuple(map(int, match.groups())) != (expected, output_hz, input_hz) or
        len(proc.stdout) != 8*expected):
        raise RuntimeError('production P07 F64 impulse export invalid')
    out = np.frombuffer(proc.stdout, dtype='<f8').copy()
    if not np.isfinite(out).all():
        raise RuntimeError('nonfinite production SRC impulse response')
    return out, sha(proc.stdout)


def derive_observations(probe: Path, input_hz: int, output_hz: int,
                        frames: int = 32768, *, max_phase_count: int = 1024) -> tuple[dict, np.ndarray]:
    """Obtain all input residue classes of an *observed* rational operator.

    U output frames correspond to V input frames.  Shifting an input
    impulse by V and the output by U should commute away from file edges.
    This checks one necessary condition of a time-periodic operator; it is
    not an independent derivation of W from rate.c.
    """
    if (not probe.is_file() or not (8000 <= input_hz <= 1000000) or
        not (8000 <= output_hz <= 1000000) or frames < 8192):
        raise ValueError('invalid probe/clock/length')
    g = math.gcd(input_hz, output_hz)
    u, v = output_hz // g, input_hz // g
    if v > max_phase_count or u > max_phase_count:
        raise ValueError('ratio requires more phases than configured resource cap')
    target = (frames * output_hz + input_hz//2)//input_hz
    if frames > 1048576 or v*target > 30000000:
        raise ValueError('operator capture exceeds explicit storage budget')
    # Keep impulse and shifted control well clear of stream boundaries.
    anchor = (frames//2//v)*v
    if not frames//4 < anchor < 3*frames//4-v:
        raise ValueError('finite stream does not leave sufficient phase margin')
    nref = anchor*u//v
    receipt = []
    waveforms = []
    for phase in range(v):
        data, h = impulse(probe, input_hz, output_hz, frames, anchor+phase)
        waveforms.append(data)
        receipt.append(dict(phase=phase, impulse_at=anchor+phase,
                            f64_sha256=h, output_frames=len(data)))
    extra, extra_hash = impulse(probe, input_hz, output_hz, frames, anchor+v)
    delta = waveforms[0][:-u] - extra[u:]
    # Do not promote measured small differences to the source-audited finite
    # operator rounding bound. Record the full residual as a diagnostic.
    residual = dict(max_abs=float(np.max(np.abs(delta))),
                    rms=float(np.sqrt(np.mean(delta*delta))),
                    shifted_control_f64_sha256=extra_hash)
    # Store all binary64 phase responses, *not* sparse taps selected by an
    # invented truncation epsilon; subthreshold taps may add coherently.
    array = np.stack(waveforms).astype('<f8', copy=False)
    info = dict(schema='P15/private-src-operator-observations/1',
                status='OBSERVED_UNCERTIFIED', qualified=False,
                input_hz=input_hz, output_hz=output_hz, input_frames=frames,
                ratio_output_frames=u, ratio_input_frames=v,
                expected_output_frames=int(array.shape[1]),
                input_anchor=anchor, output_anchor=nref,
                phase_shift_residual=residual,
                phases=receipt,
                exporter_binary_sha256=sha(probe.read_bytes()),
                exporter_source_sha256=sha((ROOT/'tests/dsd/test_p07_reference.c').read_bytes()),
                source_sha256={name:sha((ROOT/name).read_bytes()) for name in
                               ('src/rate.c','src/rate_filters.h',
                                'src/rate_half_fir.h','src/dft_filter.c','src/fft4g.c')},
                limitations=('Impulse outputs are produced by the implementation under test. '
                             'They do not independently bind the generated SoX stage coefficients, '
                             'all phase/interpolation schedules, numerical error propagation, '
                             'finite support, continuous spectra or the complete native FIR+SRC. '
                             'No release PASS can be issued from this evidence.'))
    return info,array


def write_new(directory: Path, info: dict, observed: np.ndarray) -> None:
    """Publish a SHA-bound pair atomically, refusing conflicting replays.

    Stage both files in a sibling directory and rename the *directory* only
    after both files are durable. Never expose a half-written receipt.
    """
    serialized = io.BytesIO()
    np.save(serialized, observed, allow_pickle=False)
    payload = serialized.getvalue()
    receipt = dict(info, phase_array_sha256=sha(payload))
    if directory.exists():
        if not directory.is_dir():
            raise FileExistsError('output path is not a directory')
        json_file = directory/'operator-observations.json'
        numpy_file = directory/'phase-f64.npy'
        if (set(x.name for x in directory.iterdir()) !=
            {'operator-observations.json','phase-f64.npy'}):
            raise FileExistsError('incomplete existing SRC observation; choose a new output path')
        previous = json.loads(json_file.read_text())
        if (previous != receipt or sha(numpy_file.read_bytes()) != receipt['phase_array_sha256']):
            raise FileExistsError('existing SRC observation differs from requested acquisition')
        return
    directory.parent.mkdir(parents=True,exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + directory.name + '-',
                                    dir=directory.parent))
    try:
        array_file=staging/'phase-f64.npy'
        with array_file.open('wb') as stream:
            stream.write(payload)
            stream.flush(); os.fsync(stream.fileno())
        receipt_file=staging/'operator-observations.json'
        with receipt_file.open('w') as stream:
            json.dump(receipt,stream,indent=2,sort_keys=True,allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(staging, os.O_RDONLY | getattr(os,'O_DIRECTORY',0))
        try: os.fsync(fd)
        finally: os.close(fd)
        if directory.exists():
            raise FileExistsError('output path appeared during staging')
        os.rename(staging,directory)
        fd = os.open(directory.parent,os.O_RDONLY | getattr(os,'O_DIRECTORY',0))
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def check_existing(directory: Path, probe: Path, input_hz: int,
                   output_hz: int, frames: int) -> dict | None:
    """Validate and reuse an already complete capture before running probes.

    This is an integrity and source-binding reuse test, NOT independent
    verification of the mathematical operator. A bad receipt is never
    overwritten or silently discarded to obtain a fresh looking success.
    """
    if not directory.exists():
        return None
    try:
        if not directory.is_dir() or {p.name for p in directory.iterdir()} != {
                'operator-observations.json', 'phase-f64.npy'}:
            raise ValueError('existing observation is incomplete')
        receipt = json.loads((directory/'operator-observations.json').read_text())
        g = math.gcd(input_hz, output_hz)
        phases = input_hz // g
        expected = (frames * output_hz + input_hz//2)//input_hz
        if not (receipt.get('schema') == 'P15/private-src-operator-observations/1' and
                receipt.get('status') == 'OBSERVED_UNCERTIFIED' and
                receipt.get('qualified') is False and
                receipt.get('input_hz') == input_hz and
                receipt.get('output_hz') == output_hz and
                receipt.get('input_frames') == frames and
                receipt.get('ratio_input_frames') == phases and
                receipt.get('ratio_output_frames') == output_hz//g and
                receipt.get('expected_output_frames') == expected and
                receipt.get('exporter_binary_sha256') == sha(probe.read_bytes()) and
                receipt.get('exporter_source_sha256') == sha(
                    (ROOT/'tests/dsd/test_p07_reference.c').read_bytes()) and
                receipt.get('source_sha256') == {
                    name:sha((ROOT/name).read_bytes()) for name in (
                        'src/rate.c','src/rate_filters.h','src/rate_half_fir.h',
                        'src/dft_filter.c','src/fft4g.c')}
                ):
            raise ValueError('existing observation source/clock/identity differs')
        array = directory/'phase-f64.npy'
        if sha(array.read_bytes()) != receipt.get('phase_array_sha256'):
            raise ValueError('existing observation array SHA differs')
        data = np.load(array, allow_pickle=False, mmap_mode='r')
        if data.dtype != np.dtype('<f8') or data.shape != (phases,expected) or \
                not np.isfinite(data).all() or len(receipt['phases']) != phases:
            raise ValueError('existing observation shape or values differ')
        anchor = receipt['input_anchor']
        if anchor < frames//4 or anchor >= 3*frames//4-phases:
            raise ValueError('existing observation anchor is unsafe')
        for i,row in enumerate(receipt['phases']):
            if not (row['phase'] == i and row['impulse_at'] == anchor+i and
                    row['output_frames'] == expected and
                    row['f64_sha256'] == sha(data[i].tobytes())):
                raise ValueError('existing observation per-phase SHA differs')
        residual = receipt['phase_shift_residual']['max_abs']
        if type(residual) not in (int,float) or not math.isfinite(residual) or residual < 0:
            raise ValueError('existing observation phase residual is invalid')
        return receipt
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError('refusing invalid/mismatched prior SRC observation: ' + str(exc)) from exc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',required=True,type=Path)
    parser.add_argument('--input-hz',type=int,required=True)
    parser.add_argument('--output-hz',type=int,required=True)
    parser.add_argument('--frames',type=int,default=32768)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    previous=check_existing(args.output,args.probe,args.input_hz,
                            args.output_hz,args.frames)
    if previous is not None:
        print(json.dumps(dict(status=previous['status'], reused_verified_capture=True,
                              input_hz=previous['input_hz'],
                              output_hz=previous['output_hz'])))
        return 2
    info, observed=derive_observations(args.probe,args.input_hz,
                                      args.output_hz,frames=args.frames)
    write_new(args.output, info, observed)
    print(json.dumps(dict(status=info['status'], input_hz=info['input_hz'],
                          output_hz=info['output_hz'],
                          period_output=info['ratio_output_frames'],
                          period_input=info['ratio_input_frames'],
                          measured_phase_shift_max_abs=info['phase_shift_residual']['max_abs'])))
    return 2  # explicit incomplete evidence, never a spectral/release PASS


if __name__=='__main__':raise SystemExit(main())
