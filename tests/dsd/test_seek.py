#!/usr/bin/env python3
"""P03 seek-contract matrix: independently assembled inputs, public API probes.

The C observer compares every seeked sample with a sequential decode. The
existing P00/P02 fixture/reference tests separately constrain the sequential
chronology, so this test does not make the corrected reader its own oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import wave

from reference import fixtures

ROOT = Path(__file__).resolve().parents[2]


def invoke(argv):
    began = time.monotonic()
    try:
        p = subprocess.run([str(x) for x in argv], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=90, cwd=ROOT)
        return {'argv': [str(x) for x in argv], 'exit': p.returncode,
                'stdout': p.stdout.decode(errors='replace'),
                'stderr': p.stderr.decode(errors='replace'),
                'seconds': time.monotonic() - began}
    except subprocess.TimeoutExpired as ex:
        return {'argv': [str(x) for x in argv], 'exit': None,
                'stdout': '', 'stderr': f'timed out: {ex}',
                'seconds': time.monotonic() - began}


def make_wav(path, channels, frames=513):
    samples = [((frame * 227 + channel * 9007 + (frame * channel * 37)) % 60000) - 30000
               for frame in range(frames) for channel in range(channels)]
    payload = struct.pack(f'<{len(samples)}h', *samples)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(payload)
    return payload


def make_smp(path, frames=513):
    """Construct a SampleVision v2.1 mono stream without using the SoX writer."""
    samples = [((frame * 227) % 60000) - 30000 for frame in range(frames)]
    header = (b'SOUND SAMPLE DATA ' + b'2.1 ' +
              b' ' * 60 + b'P03 INDEPENDENT SMP'.ljust(30, b' '))
    assert len(header) == 112
    audio = struct.pack(f'<{frames}h', *samples)
    loops = (struct.pack('<IIBH', 0, 0, 0, 0)) * 8
    markers = (b' ' * 10 + struct.pack('<I', 0)) * 8
    trailer = (struct.pack('<H', 0) + loops + markers +
               struct.pack('<bIII', 60, 44100, 0, 0xffffffff))
    assert len(trailer) == 215
    path.write_bytes(header + struct.pack('<I', frames) + audio + trailer)


def make_prc_alaw(path, frames=513):
    """Construct a Psion ReCord A-law stream with explicit record offsets."""
    header = bytes.fromhex(
        '37000010 6d000010 7e000010 cfac0855 14000000'
        '04 52000010 34000000 89000010 25000000 7e000010')
    assert len(header) == 41
    name = b'record.app'
    assert len(name) == 10
    audio = bytes((frame * 73 + 0x55) & 255 for frame in range(frames))
    metadata = (struct.pack('<IIHBBII', frames, 0, 0, 5, 0, 0, frames))
    path.write_bytes(header + bytes([(len(name) << 2) | 2]) + name +
                     metadata + audio)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--probe', default=str(ROOT/'test/dsd_test_seek_contract'))
    p.add_argument('--sox', default=str(ROOT/'src/sox'))
    p.add_argument('--results', default=str(ROOT/'tests/dsd/results/P03/seek'))
    args = p.parse_args()
    results = Path(args.results)
    results.mkdir(parents=True, exist_ok=True)
    records, unrun = [], []
    with tempfile.TemporaryDirectory(prefix='p03-seek-contract-') as tmp:
        work = Path(tmp)

        def check(name, path, channels, mode='auto', behavior='supported'):
            observed = invoke([args.probe, path, mode, channels, behavior])
            try:
                parsed = json.loads(observed['stdout'])
            except ValueError:
                parsed = None
            result_names = {'supported': 'pass', 'unsupported': 'unsupported',
                            'empty-dff': 'empty-dff'}
            correct = (observed['exit'] == 0 and parsed is not None and
                       parsed.get('result') == result_names[behavior])
            entry = {'name': name, 'result': 'PASS' if correct else 'FAIL',
                     'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'observed': parsed, 'command': observed}
            records.append(entry)
            print(f"{'PASS' if correct else 'FAIL'} {name}", flush=True)

        for channels in range(1, 7):
            # Distinguish channel positions with independent bit vectors.
            for kind in ('dsf-lsb', 'dsf-msb', 'dff', 'wsd'):
                frames = 73 if kind.startswith('dsf') else 80
                timeline = fixtures.bits(frames, channels, 'distinct')
                if kind.startswith('dsf'):
                    raw = fixtures.make_dsf(timeline, bps=8 if kind == 'dsf-msb' else 1)
                    suffix = '.dsf'
                elif kind == 'dff':
                    raw = fixtures.make_dff(timeline)
                    suffix = '.dff'
                else:
                    raw = fixtures.make_wsd(timeline)
                    suffix = '.wsd'
                path = work/f'{kind}-{channels}ch{suffix}'
                path.write_bytes(raw)
                check(f'{kind}-{channels}ch', path, channels)

            pcm_wav = work/f'pcm-{channels}ch.wav'
            pcm = make_wav(pcm_wav, channels)
            check(f'wav-pcm-{channels}ch', pcm_wav, channels)
            rawfile = work/f'raw-{channels}ch.raw'
            rawfile.write_bytes(pcm)
            check(f'raw-pcm-{channels}ch', rawfile, channels, mode='raw')
            if channels == 2:
                # MSU1 has a fixed 8-byte header, 16-bit stereo little-endian.
                msu = work/'msu-stereo.pcm'
                msu.write_bytes(b'MSU1' + struct.pack('<I', 0) + pcm)
                check('msu-stereo', msu, 2)
            if channels == 1:
                smp = work/'samplevision-mono.smp'
                make_smp(smp)
                check('smp-mono', smp, 1)
                prc = work/'psion-record-alaw-mono.prc'
                make_prc_alaw(prc)
                check('prc-alaw-mono', prc, 1)
                for frames in (0, 1, 7, 9, 32769):
                    timeline = fixtures.bits(frames, 1, 'distinct')
                    file = work/f'dsf-{frames}-frames.dsf'
                    file.write_bytes(fixtures.make_dsf(timeline))
                    check(f'dsf-{frames}-frames', file, 1)
                for frames in (0, 8):
                    timeline = fixtures.bits(frames, 1, 'distinct')
                    file = work/f'dff-{frames}-frames.dff'
                    file.write_bytes(fixtures.make_dff(timeline))
                    check(f'dff-{frames}-frames', file, 1)

        # DFF with zero declared audio length is not an unknown-length stream.
        # MANF bytes following the empty DSD chunk must never become samples.
        # The probe asserts zero output, rather than using a defective
        # sequential read of the same handler as its expected result.
        for channels in (1, 2, 6):
            for with_manf in (False, True):
                file = work/f'dff-empty-{channels}ch-{int(with_manf)}-manf.dff'
                file.write_bytes(fixtures.make_dff(fixtures.bits(0, channels),
                                                   trailing_manf=with_manf))
                check(f'dff-empty-{channels}ch-{"manf" if with_manf else "no-manf"}',
                      file, channels, behavior='empty-dff')
            file = work/f'dff-eight-{channels}ch-manf.dff'
            file.write_bytes(fixtures.make_dff(fixtures.bits(8, channels),
                                               trailing_manf=True))
            check(f'dff-eight-{channels}ch-manf-control', file, channels)

        # The existing GSM WAV reader does not reconstruct its predictive
        # decoder state for random access. P03 expressly permits rejection.
        source = work/'pcm-1ch.wav'
        gsm = work/'gsm.wav'
        encoded = invoke([args.sox, source, '-e', 'gsm', gsm])
        if encoded['exit'] == 0 and gsm.exists():
            check('wav-gsm-unsupported-without-movement', gsm, 1, behavior='unsupported')
        else:
            unrun.append({'name': 'wav-gsm', 'reason': 'GSM encoding not available',
                          'command': encoded})

        # Optional codecs use their own *sequential* decode as the comparison.
        # The frozen PCM source is still independent of the SoX writer.
        # VPATH builds generate soxconfig.h beside the configured executable,
        # not in the immutable source tree. Inspect the exact binary's config.
        config_path = Path(args.sox).resolve().parent/'soxconfig.h'
        if not config_path.is_file():
            raise AssertionError('configured build header missing: '+str(config_path))
        config = config_path.read_text()
        for name, macros, suffix, options in [
            ('flac', ('HAVE_FLAC',), '.flac', []),
            ('vorbis', ('HAVE_VORBIS', 'HAVE_VORBISENC', 'HAVE_VORBISFILE'), '.ogg', []),
            ('opus', ('HAVE_OPUS', 'HAVE_OPUSENC'), '.opus', []),
            ('wavpack', ('HAVE_WAVPACK',), '.wv', []),
        ]:
            if not any(f'#define {m} 1' in config for m in macros):
                unrun.append({'name': name, 'reason': 'optional codec unavailable in configured build'})
                continue
            target = work / ('optional-' + name + suffix)
            command = invoke([args.sox, work/'pcm-2ch.wav', *options, target])
            if command['exit'] == 0 and target.exists():
                check(f'optional-{name}-2ch', target, 2)
                if name == 'opus':
                    # More than one internal 4096-byte decoded buffer.  The
                    # C probe compares alternating seeks, rewinds and exact
                    # EOF to a full sequential decode, including after a
                    # rejected out-of-range seek with unread cache data.
                    long_source = work/'opus-long-stereo.wav'
                    make_wav(long_source, 2, frames=12345)
                    long_target = work/'optional-opus-long.opus'
                    long_encode = invoke([args.sox, long_source, long_target])
                    if long_encode['exit'] == 0 and long_target.exists():
                        check('optional-opus-long-buffered-2ch', long_target, 2)
                    else:
                        unrun.append({'name': 'opus-long',
                                      'reason': 'optional Opus encoder could not produce long fixture',
                                      'command': long_encode})
            else:
                unrun.append({'name': name, 'reason': 'optional encoder could not produce fixture',
                              'command': command})

        # The first-effect trim uses the seek shortcut. A preceding unity
        # effect forces the nonoptimized, sequential reference path.
        for channels in (1, 2, 6):
            pcm = (work/f'raw-{channels}ch.raw').read_bytes()
            start, count = 13, 60
            direct, sequential = work/f'fast-{channels}ch.raw', work/f'slow-{channels}ch.raw'
            common = [args.sox, work/f'pcm-{channels}ch.wav', '-e', 'signed-integer',
                      '-b', '16', '-L', '-t', 'raw']
            a = invoke([*common, direct, 'trim', f'{start}s', f'{count}s'])
            b = invoke([*common, sequential, 'gain', '0', 'trim', f'{start}s', f'{count}s'])
            expected = pcm[2 * channels * start: 2 * channels * (start + count)]
            correct = (a['exit'] == b['exit'] == 0 and direct.exists() and
                       sequential.exists() and direct.read_bytes() == sequential.read_bytes() == expected)
            records.append({'name': f'cli-wav-optimized-trim-{channels}ch',
                            'result': 'PASS' if correct else 'FAIL',
                            'expected_sha256': hashlib.sha256(expected).hexdigest(),
                            'optimized': a, 'sequential': b})
            print(f"{'PASS' if correct else 'FAIL'} cli-wav-optimized-trim-{channels}ch", flush=True)

    failed = [r['name'] for r in records if r['result'] != 'PASS']
    report = {'phase': 'P03', 'pass': len(records) - len(failed), 'fail': len(failed),
              'unrun_optional': unrun, 'failures': failed, 'cases': records}
    (results/'seek.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'pass': report['pass'], 'fail': report['fail'],
                      'unrun_optional': [r['name'] for r in unrun]}, sort_keys=True))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
