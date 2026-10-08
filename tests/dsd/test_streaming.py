#!/usr/bin/env python3
"""P02 independent whole-frame/read-state/extent/pipe/CLI regression matrix.

Inputs and expected chronology come only from the handwritten Python fixture
builder and bit lists; never from the native SoX reader or writer under test.
The C probe exposes counts, chronological first/last samples and a rolling
checksum, without defining its expected result.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import time

from reference import fixtures

ROOT = Path(__file__).resolve().parents[2]
OFFSET = 0xcbf29ce484222325
PRIME = 0x100000001b3
MASK = (1 << 64) - 1


def chronological(bits):
    return bytes(b for frame in zip(*bits) for b in frame)


def completed(bits):
    """DFF's original chronological 0x69 last-byte completion, hand-derived."""
    frames = len(bits[0])
    target = ((frames + 7) // 8) * 8
    return tuple(ch + bytes((0x69 >> (7 - (i % 8))) & 1
                            for i in range(frames, target)) for ch in bits)


def fnv(data):
    h = OFFSET
    for v in data:
        h = ((h ^ v) * PRIME) & MASK
    return f'{h:016x}'


class Matrix:
    def __init__(self, args):
        self.args = args
        self.records = []
        self.failures = []

    def execute(self, argv, *, timeout=30, input=None):
        began = time.monotonic()
        try:
            proc = subprocess.run([str(x) for x in argv], cwd=ROOT, input=input,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout)
            return dict(argv=[str(x) for x in argv], exit=proc.returncode,
                        stdout=proc.stdout.decode(errors='replace'),
                        stderr=proc.stderr.decode(errors='replace'),
                        elapsed=time.monotonic()-began)
        except subprocess.TimeoutExpired as exc:
            return dict(argv=[str(x) for x in argv], exit=None, stdout='',
                        stderr=f'timeout: {exc}', elapsed=time.monotonic()-began)

    def verify(self, name, ok, details):
        self.records.append(dict(name=name, correct=bool(ok), **details))
        if not ok:
            self.failures.append(name)
            print(f'FAIL {name}: {str(details)[:350]}', flush=True)

    def probe(self, path, samples, *, first=0, seek=None, fixed=False,
              zero_first=False, expected=None, expected_open=True, name='',
              expected_stderr=None):
        args = [self.args.probe, 'read-zero-first' if zero_first else 'read', path,
                samples, first, '-' if seek is None else seek, int(fixed)]
        result = self.execute(args)
        try:
            obj = json.loads(result['stdout']) if result['exit'] == 0 else {}
        except ValueError:
            obj = {}
        correct = result['exit'] == 0 and obj.get('open') is expected_open
        if expected_open and correct:
            correct = (obj.get('remaining_returned') == len(expected) and
                       obj.get('head_bits') == ''.join(map(str, expected[:8192])) and
                       obj.get('tail_bits') == ''.join(map(str, expected[-128:])) and
                       obj.get('fnv64') == fnv(expected))
        if expected_stderr is not None:
            lines = [line for line in result['stderr'].splitlines() if line.strip()]
            if expected_stderr:
                correct = correct and len(lines) == 1 and expected_stderr in lines[0]
            else:
                correct = correct and not lines
        self.verify(name, correct, dict(observed=obj, command=result))
        return obj


def run_matrix(m, td):
    for channels in range(1, 7):
        for kind in ('dsf-lsb', 'dsf-msb', 'dff', 'wsd'):
            frames = 29 if kind.startswith('dsf') else 32
            source = fixtures.bits(frames, channels, 'distinct')
            if kind.startswith('dsf'):
                raw = fixtures.make_dsf(source, bps=8 if kind.endswith('msb') else 1)
                extension = '.dsf'
                expected = chronological(source)
            elif kind == 'dff':
                raw = fixtures.make_dff(source)
                extension = '.dff'
                expected = chronological(source)
            else:
                raw = fixtures.make_wsd(source)
                extension = '.wsd'
                expected = chronological(source)
            path = td/f'matrix-{kind}-{channels}{extension}'
            path.write_bytes(raw)
            for frames_per_call in range(18):
                for remainder in (0, channels - 1) if channels > 1 and frames_per_call in (1, 7, 17) else (0,):
                    cap = frames_per_call * channels + remainder
                    outcome = expected if frames_per_call else b''
                    m.probe(path, cap, expected=outcome,
                            name=f'{kind}-{channels}ch-cap-{cap}')
            m.probe(path, channels, zero_first=True, expected=expected,
                    name=f'{kind}-{channels}ch-zero-before-read')

        # Exercise all seven partial-byte last-block endpoints and zero frames.
        for tail in range(8):
            for bps in (1, 8):
                data = fixtures.bits(tail, channels, 'random')
                file = td/f'tail-{channels}-{tail}-bps{bps}.dsf'
                file.write_bytes(fixtures.make_dsf(data, bps=bps))
                m.probe(file, channels, expected=chronological(data),
                        name=f'dsf-{channels}ch-{tail}frame-tail-bps{bps}')
            data = fixtures.bits(tail, channels, '69')
            file = td/f'tail-{channels}-{tail}.dff'
            file.write_bytes(fixtures.make_dff(data))
            m.probe(file, channels, expected=chronological(completed(data)),
                    name=f'dff-{channels}ch-{tail}frame-tail')
        # Cached cluster must be discarded after mono public seek. Multi-
        # channel public seek units are deliberately owned by P03.
        if channels == 1:
            for ext in ('dsf', 'dff', 'wsd'):
                file = td/f'matrix-{"dsf-lsb" if ext == "dsf" else ext}-1.{ext}'
                sequence = fixtures.bits(29 if ext == 'dsf' else 32, 1, 'distinct')
                m.probe(file, 3, first=5, seek=8, fixed=True,
                        expected=chronological(sequence)[8:],
                        name=f'{ext}-cache-discard-after-seek')


def run_multiblock(m, td):
    frames = 4096 * 8 + 17
    for channels in (1, 2, 6):
        bits = fixtures.bits(frames, channels, '69')
        expected = chronological(bits)
        for bps in (1, 8):
            path = td/f'multiblock-{channels}-bps{bps}.dsf'
            path.write_bytes(fixtures.make_dsf(bits, bps=bps))
            for per_call in (1, 17, 8192 // channels):
                m.probe(path, per_call * channels, expected=expected,
                        name=f'dsf-{channels}ch-bps{bps}-multiblock-{per_call}')


def custom_dff(source, *, missing=None, extra=False):
    chunks = []
    if missing != 'FS':
        chunks.append(fixtures.chunk(b'FS  ', struct.pack('>I', fixtures.DSD64)))
    if missing != 'CHNL':
        chunks.append(fixtures.chunk(b'CHNL', struct.pack('>H', 1) + b'C000'))
    if missing != 'CMPR':
        chunks.append(fixtures.chunk(b'CMPR', b'DSD ' + b'\x0e' + b'not compressed'))
    prop = b'SND ' + (fixtures.chunk(b'JUNK', b'abc') if extra else b'') + b''.join(chunks)
    group = [fixtures.chunk(b'FVER', b'\x01\x05\x00\x00')]
    if extra:
        group.append(fixtures.chunk(b'JUNK', b'abc'))
    group += [fixtures.chunk(b'PROP', prop), fixtures.chunk(b'DSD ', source)]
    return fixtures.chunk(b'FRM8', b'DSD ' + b''.join(group))


def run_extents(m, td):
    program = bytes.fromhex('96')  # asymmetric, MSB chronological 10010110
    known = bytes([1, 0, 0, 1, 0, 1, 1, 0])
    good = custom_dff(program, extra=True)
    compact = custom_dff(program)
    assert len(compact) == 128  # 127 without the final external audio pad
    valid = {'extra-unknown-chunks':good,
             'odd-payload-legacy-pad-absent': good[:-1],
             'odd-payload-legacy-pad-absent-no-metadata': compact[:-1],
             'empty-audio':custom_dff(b''),
             'single-byte-cluster':compact}
    for name, blob in valid.items():
        path=td/f'valid-{name}.dff'; path.write_bytes(blob)
        expected = b'' if name == 'empty-audio' else known
        warning = ('missing its required external pad byte at EOF'
                   if 'legacy-pad-absent' in name else '')
        m.probe(path, 1, expected=expected, expected_stderr=warning,
                name=f'extent-valid-{name}')

    broken = {
        'missing-FS': custom_dff(program, missing='FS'),
        'missing-CHNL': custom_dff(program, missing='CHNL'),
        'missing-CMPR': custom_dff(program, missing='CMPR'),
        'audio-truncated': custom_dff(b'\x96\x3d')[:-2],
        'no-frames-in-parent': bytearray(custom_dff(program)),
        'overlong-parent': bytearray(custom_dff(program)),
        'invalid-PROP-size': bytearray(custom_dff(program)),
        'incomplete-CHNL-ids': bytearray(custom_dff(program)),
        'bad-rate': bytearray(custom_dff(program)),
    }
    # FRM8 size: big endian u64 at offset 4.
    broken['no-frames-in-parent'][4:12] = struct.pack('>Q', 4)
    broken['overlong-parent'][4:12] = struct.pack('>Q', len(broken['overlong-parent']) + 1024)
    prop_offset = broken['invalid-PROP-size'].index(b'PROP')
    original_prop = struct.unpack_from('>Q', broken['invalid-PROP-size'], prop_offset + 4)[0]
    struct.pack_into('>Q', broken['invalid-PROP-size'], prop_offset + 4, original_prop - 4)
    chnl = broken['incomplete-CHNL-ids'].index(b'CHNL')
    struct.pack_into('>Q', broken['incomplete-CHNL-ids'], chnl + 4, 2)
    fs = broken['bad-rate'].index(b'FS  ')
    struct.pack_into('>I', broken['bad-rate'], fs + 12, 0)
    for name, blob in broken.items():
        path=td/f'bad-{name}.dff'; path.write_bytes(blob)
        m.probe(path, 10, expected_open=False, name=f'extent-reject-{name}')

    # DSF validates physical blocks, logical frames and dimensions before read.
    from_good = fixtures.make_dsf(fixtures.bits(8,2,'distinct'))
    dsf_bad = {
        'block-zero':bytearray(from_good),
        'insufficient-payload':bytearray(from_good),
        'wrong-file-size':bytearray(from_good),
        'invalid-bit-depth':bytearray(from_good),
        'truncated-audio':bytearray(from_good[:-1]),
    }
    struct.pack_into('<I', dsf_bad['block-zero'], 72, 0)
    struct.pack_into('<Q', dsf_bad['insufficient-payload'], 84, 12)
    struct.pack_into('<Q', dsf_bad['wrong-file-size'], 12, 91)
    struct.pack_into('<I', dsf_bad['invalid-bit-depth'], 60, 16)
    for name, blob in dsf_bad.items():
        path=td/f'bad-dsf-{name}.dsf'; path.write_bytes(blob)
        m.probe(path, 10, expected_open=False, name=f'dsf-reject-{name}')


def run_pipes(m, td):
    for fmt, frames in (('dsf',13),('dff',16),('wsd',16)):
        source = fixtures.bits(frames,2,'distinct')
        data = (fixtures.make_dsf(source) if fmt == 'dsf' else
                fixtures.make_dff(source) if fmt == 'dff' else
                fixtures.make_wsd(source))
        fifo=td/f'forward-only.{fmt}'
        os.mkfifo(fifo)
        error=[]
        def write():
            try:
                with fifo.open('wb') as fd:
                    fd.write(data)
            except Exception as exc:
                error.append(repr(exc))
        t=threading.Thread(target=write,daemon=True)
        t.start()
        m.probe(fifo, 2, expected=chronological(source),
                name=f'{fmt}-forward-only-2ch')
        t.join(timeout=30)
        if t.is_alive() or error:
            m.verify(f'{fmt}-fifo-producer',False,dict(error=error,alive=t.is_alive()))
        fifo.unlink()


def run_cli(m, td):
    for nch in (1, 2, 6):
        source = fixtures.bits(96,nch,'distinct')
        inputfile=td/f'cli-in-{nch}.dsf'
        outputfile=td/f'cli-out-{nch}.dff'
        inputfile.write_bytes(fixtures.make_dsf(source))
        command=[m.args.sox, '--buffer', '32', inputfile, outputfile]
        p=m.execute(command,timeout=60)
        ok=p['exit'] == 0 and outputfile.exists()
        if ok:
            # Reference parser, independent of native read or write.
            from reference import verify
            data=verify.decode_dff(outputfile.read_bytes())
            ok=chronological(data['timeline']) == chronological(source)
        m.verify(f'cli-buffer32-dsf-to-dff-{nch}ch',ok,dict(command=p))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--probe',type=Path,default=ROOT/'test/dsd_test_io')
    parser.add_argument('--sox',type=Path,default=ROOT/'src/sox_ng')
    parser.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P02/streaming')
    args=parser.parse_args()
    args.probe=args.probe.resolve()
    args.sox=args.sox.resolve()
    args.results.mkdir(parents=True,exist_ok=True)
    m=Matrix(args)
    with tempfile.TemporaryDirectory(prefix='sox-ng-p02-') as temp:
        td=Path(temp)
        run_matrix(m,td)
        run_multiblock(m,td)
        run_extents(m,td)
        run_pipes(m,td)
        run_cli(m,td)
    summary=dict(verdict='pass' if not m.failures else 'fail',
                 total=len(m.records),passed=len(m.records)-len(m.failures),
                 failed=len(m.failures),failed_names=m.failures,records=m.records)
    output=args.results/'streaming.json'
    output.write_text(json.dumps(summary,indent=2)+'\n')
    print(f"P02 streaming/extent/forward-only/CLI: {summary['passed']}/{summary['total']} PASS, "
          f"{summary['failed']} FAIL; {output}")
    return 0 if not m.failures else 1


if __name__=='__main__':
    raise SystemExit(main())
