#!/usr/bin/env python3
"""P02 native read/repack throughput samples, with paired P01 large-buffer control.

This development measurement is NOT a throughput acceptance test. A host noise
check and a prepared-host paired measurement are still required for that gate.
Synthetic DSD payloads are assembled independently of the tested SoX binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import struct
import subprocess
import tempfile
import time

from reference import fixtures
from bench_dff import dsf_bytes

ROOT = Path(__file__).resolve().parents[2]


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dff_bytes(channels, frames):
    assert frames % 8 == 0
    count = frames // 8
    # Asymmetric byte patterns in channel-interleaved, MSB-first byte clusters.
    patterns = (0x96, 0x39, 0xa5, 0x69, 0x1e, 0xc3)
    payload = bytes(patterns[c] ^ (0xff if i & 1 else 0)
                    for i in range(count) for c in range(channels))
    chnl = struct.pack('>H', channels) + b''.join(
        f'C{i:03d}'.encode('ascii') for i in range(channels))
    prop = (b'SND ' + fixtures.chunk(b'FS  ', struct.pack('>I', fixtures.DSD64))
            + fixtures.chunk(b'CHNL', chnl)
            + fixtures.chunk(b'CMPR', b'DSD ' + bytes([14]) + b'not compressed'))
    return fixtures.chunk(b'FRM8', b'DSD '
                          + fixtures.chunk(b'FVER', bytes.fromhex('01050000'))
                          + fixtures.chunk(b'PROP', prop)
                          + fixtures.chunk(b'DSD ', payload))


def run(sox, source, target, cap, output):
    args = [str(sox), '--buffer', str(cap), str(source)]
    if output == 'null':
        args += ['-t', 'null', '-']
    else:
        args += [str(target)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, cwd=ROOT)
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {'argv':args, 'exit':proc.returncode, 'wall_seconds':wall,
              'cpu_seconds':after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
              'stderr':proc.stderr.decode(errors='replace')[-2000:],
              'stdout_bytes':len(proc.stdout)}
    if output != 'null' and target.exists():
        result.update(output_size=target.stat().st_size, output_sha256=checksum(target))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline-sox', type=Path, required=True)
    p.add_argument('--sox', type=Path, default=ROOT/'src/sox_ng')
    p.add_argument('--results', type=Path,
                   default=ROOT/'tests/dsd/results/P02/bench-read')
    p.add_argument('--large-frames', type=int, default=1048576)
    p.add_argument('--small-frames', type=int, default=131072)
    p.add_argument('--pairs', type=int, default=5)
    args = p.parse_args()
    args.baseline_sox = args.baseline_sox.resolve()
    args.sox = args.sox.resolve()
    args.results.mkdir(parents=True, exist_ok=True)
    records = []
    errors = []
    rng = random.Random(0x502)
    with tempfile.TemporaryDirectory(prefix='sox-ng-p02-bench-') as tmp:
        td = Path(tmp)
        for fmt in ('dsf','dff'):
            for channels in (2,6):
                for operation in ('null', 'repack'):
                    for size, frames, cap in (('small',args.small_frames,32),
                                              ('large',args.large_frames,65536)):
                        if frames % (4096 * 8):
                            raise ValueError('frame lengths must be multiples of DSF blocks')
                        source = td/f'{fmt}-{channels}-{size}.{fmt}'
                        source.write_bytes(dsf_bytes(channels, frames)[0] if fmt == 'dsf'
                                           else dff_bytes(channels, frames))
                        input_hash = checksum(source)
                        variants = (['candidate'] if size == 'small' else
                                    ['baseline', 'candidate'] * args.pairs)
                        if size == 'large':
                            variants = [v for pair in range(args.pairs)
                                        for v in (('candidate','baseline') if rng.randrange(2)
                                                  else ('baseline','candidate'))]
                        reference_hash = None
                        for repetition, name in enumerate(variants):
                            sox = args.sox if name == 'candidate' else args.baseline_sox
                            target = td/f'output-{fmt}-{channels}-{size}-{operation}-{name}.dff'
                            if target.exists():
                                target.unlink()
                            result = run(sox, source, target, cap, operation)
                            result.update(source_format=fmt, channels=channels,
                                          operation=operation, size=size, frames=frames,
                                          buffer_samples=cap, variant=name,
                                          repetition=repetition, input_sha256=input_hash)
                            if result['exit']:
                                errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: exit {result["exit"]}')
                            if operation == 'repack':
                                if result.get('output_size',0) <= 100:
                                    errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: empty output')
                                if reference_hash is None:
                                    reference_hash = result.get('output_sha256')
                                elif reference_hash != result.get('output_sha256'):
                                    errors.append(f'{fmt}/{channels}/{operation}/{size}/{name}: output mismatch')
                            records.append(result)
                        print(f'{fmt}/{channels}ch {operation} {size}: {len(variants)} executed', flush=True)
    data = {'baseline_sox':str(args.baseline_sox), 'candidate_sox':str(args.sox),
            'baseline_sha256':checksum(args.baseline_sox),
            'candidate_sha256':checksum(args.sox),
            'host_unqualified':True,
            'purpose':'native read and transcode functionality, unqualified timing samples',
            'cases':records, 'errors':errors,
            'status':'passed-smoke-only' if not errors else 'failed'}
    dest = args.results/'bench-read.json'
    temp = dest.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n')
    os.replace(temp,dest)
    print(f'{len(records)} benchmark commands; {len(errors)} errors; {dest}')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
