#!/usr/bin/env python3
"""Construct DSD containers from bit chronology, without running SoX.

All sequences are indexed [chronological frame][channel], never by public
SoX interleaved-sample counts. No native writer output is used as reference.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path

SEED = 0x5D640126
DSD64 = 2_822_400
RATES = (DSD64, 2 * DSD64, 4 * DSD64)
UINT64_MAX = (1 << 64) - 1
BLOCK = 4096


def checked_u64(v: int) -> int:
    if not isinstance(v, int) or not 0 <= v <= UINT64_MAX:
        raise ValueError('value does not fit uint64')
    return v


def sample_count(frames: int, channels: int) -> int:
    checked_u64(frames)
    if not isinstance(channels, int) or not 1 <= channels <= UINT64_MAX:
        raise ValueError('invalid channel count')
    return checked_u64(frames * channels)


def complete_frames(samples: int, channels: int) -> tuple[int, int]:
    checked_u64(samples)
    if not isinstance(channels, int) or not 1 <= channels <= UINT64_MAX:
        raise ValueError('invalid channel count')
    return divmod(samples, channels)  # frames, incomplete interleaved samples


def span(payload_size: int) -> int:
    return checked_u64(12 + checked_u64(payload_size) + (payload_size & 1))


def bits(frames: int, channels: int, pattern: str = 'distinct') -> tuple[bytes, ...]:
    """Each channel has one byte containing 0 or 1 per chronological frame."""
    sample_count(frames, channels)
    if pattern == 'random':
        r = random.Random(SEED ^ (frames << 7) ^ channels)
        return tuple(bytes(r.getrandbits(1) for _ in range(frames)) for _ in range(channels))
    if pattern == '69':
        # 0x69 is MSB-first chronology 0,1,1,0,1,0,0,1.
        seq = (0, 1, 1, 0, 1, 0, 0, 1)
        return tuple(bytes(seq[(i + 3 * ch) % 8] for i in range(frames)) for ch in range(channels))
    if pattern == 'zeros':
        return tuple(bytes(frames) for _ in range(channels))
    if pattern == 'ones':
        return tuple(bytes([1]) * frames for _ in range(channels))
    if pattern == 'distinct':
        return tuple(bytes(int((i * 3 + ch * 5 + i // 7) % 11 < 5)
                           for i in range(frames)) for ch in range(channels))
    raise ValueError(pattern)


def chronology_sha256(channels_bits: tuple[bytes, ...]) -> str:
    return hashlib.sha256(bytes(bit for frame in zip(*channels_bits) for bit in frame)).hexdigest()


def pack_byte(channel: bytes, offset: int, oldest_msb: bool, completion: int = 0) -> int:
    result = 0
    for j in range(8):
        bit = channel[offset + j] if offset + j < len(channel) else ((completion >> (7 - j)) & 1)
        result |= bit << (7 - j if oldest_msb else j)
    return result


def make_dsf(channels_bits: tuple[bytes, ...], rate: int = DSD64,
             bps: int = 1, channel_type: int | None = None) -> bytes:
    nch = len(channels_bits)
    frames = len(channels_bits[0])
    assert 1 <= nch <= 6 and all(len(v) == frames for v in channels_bits)
    assert bps in (1, 8)
    ctype = channel_type if channel_type is not None else (nch + (nch > 4))
    num_blocks = (frames + 8 * BLOCK - 1) // (8 * BLOCK)
    payload = bytearray(num_blocks * BLOCK * nch)
    for block in range(num_blocks):
        for ch, timeline in enumerate(channels_bits):
            for byte in range(BLOCK):
                start = block * BLOCK * 8 + byte * 8
                if start >= frames:
                    break
                offset = (block * nch + ch) * BLOCK + byte
                payload[offset] = pack_byte(timeline, start, oldest_msb=bps == 8)
    whole_file = 28 + 52 + 12 + len(payload)
    return (b'DSD ' + struct.pack('<QQQ', 28, whole_file, 0) +
            b'fmt ' + struct.pack('<QIIIIIIQII', 52, 1, 0, ctype, nch, rate,
                                   bps, frames, BLOCK, 0) +
            b'data' + struct.pack('<Q', 12 + len(payload)) + payload)


def chunk(identifier: bytes, data: bytes) -> bytes:
    assert len(identifier) == 4
    return identifier + struct.pack('>Q', len(data)) + data + b'\x00' * (len(data) & 1)


def make_dff(channels_bits: tuple[bytes, ...], rate: int = DSD64,
             trailing_manf: bool = False) -> bytes:
    nch = len(channels_bits)
    frames = len(channels_bits[0])
    assert 1 <= nch <= 6 and all(len(v) == frames for v in channels_bits)
    num_bytes = (frames + 7) // 8
    payload = bytes(pack_byte(channels_bits[ch], b * 8, oldest_msb=True, completion=0x69)
                    for b in range(num_bytes) for ch in range(nch))
    ids = [b'SLFT', b'SRGT'] if nch == 2 else [f'C{ch:03d}'.encode('ascii') for ch in range(nch)]
    name = b'not compressed'
    assert len(name) == 14
    prop = (b'SND ' + chunk(b'FS  ', struct.pack('>I', rate)) +
            chunk(b'CHNL', struct.pack('>H', nch) + b''.join(ids)) +
            chunk(b'CMPR', b'DSD ' + bytes([len(name)]) + name))
    children = (chunk(b'FVER', bytes.fromhex('01050000')) +
                chunk(b'PROP', prop) + chunk(b'DSD ', payload))
    if trailing_manf:
        children += chunk(b'MANF', b'TEST' + b'\xaa' * 20)
    return chunk(b'FRM8', b'DSD ' + children)


def make_wsd(channels_bits: tuple[bytes, ...], rate: int = DSD64) -> bytes:
    """WSD v1.1 headers are big-endian; 0x800 is its declared data start."""
    nch = len(channels_bits)
    frames = len(channels_bits[0])
    assert 1 <= nch <= 6 and frames % 8 == 0
    audio = bytes(pack_byte(channels_bits[ch], i, True)
                  for i in range(0, frames, 8) for ch in range(nch))
    end = 0x800 + len(audio)
    header = (b'1bit' + struct.pack('>I', 0) + bytes([0x11, 0, 0, 0]) +
              struct.pack('>IIIII', end & 0xffffffff, end >> 32, 0x80, 0x800, 0) +
              struct.pack('>III', 0, rate, 0) + bytes([nch, 0, 0, 0]) +
              struct.pack('>IIIII', 0, 0, 0, 0, 0) + struct.pack('>I', 0))
    if len(header) > 0x800:
        raise ValueError('header overflow')
    return header + bytes(0x800 - len(header)) + audio


def dop_words(channels_bits: tuple[bytes, ...]) -> list[list[int]]:
    """DoP 1.1 transport in 24-bit PCM: 16 time-ordered DSD bits + marker.

    Return PCM words in chronological [transport-frame][channel] order.
    In a little-endian signed 24-bit WAV they are [payload LSB, MSB, marker].
    """
    frames = len(channels_bits[0])
    return [[((0x05 if i % 2 == 0 else 0xFA) << 16) |
             sum(((ch[16 * i + k] if 16 * i + k < frames else
                  ((0x6969 >> (15 - k)) & 1)) << (15 - k)) for k in range(16))
             for ch in channels_bits]
            for i in range((frames + 15) // 16)]


def fixture_record(path: Path, data: bytes, rate: int, timeline: tuple[bytes, ...],
                   kind: str, expected: str, **extra: object) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return dict(file=path.name, kind=kind, sha256=hashlib.sha256(data).hexdigest(),
                source='hand-constructed by reference/fixtures.py', license='CC0-1.0',
                native_rate=rate, logical_frames=len(timeline[0]),
                interleaved_samples=sample_count(len(timeline[0]), len(timeline)),
                channels=len(timeline), channel_order=list(range(len(timeline))),
                chronological_bits_sha256=chronology_sha256(timeline),
                expected_operation=expected, **extra)


def generate(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict] = {}
    dsf_cases = [
        ('mono_96', 96, 1, 1, None), ('stereo_96', 96, 2, 1, None),
        ('msb_stereo_96', 96, 2, 8, None),
        ('type4_quad_96', 96, 4, 1, 4), ('type5_quad_96', 96, 4, 1, 5),
        ('five_96', 96, 5, 1, 6), ('six_96', 96, 6, 1, 7),
        ('empty', 0, 1, 1, 1), ('one', 1, 1, 1, 1),
        ('seven', 7, 1, 1, 1), ('nine', 9, 1, 1, 1),
        ('block_minus_1', 32767, 2, 1, 2),
        ('block_plus_1', 32769, 2, 1, 2),
        ('mono_32_dop', 32, 1, 1, 1),
    ]
    for name, frames, nch, bps, ctype in dsf_cases:
        ch_bits = bits(frames, nch, '69' if name == 'mono_32_dop' else 'distinct')
        data = make_dsf(ch_bits, bps=bps, channel_type=ctype)
        entries[name + '.dsf'] = fixture_record(out / (name + '.dsf'), data, DSD64,
             ch_bits, 'dsf', 'read chronological one-bit samples', bps=bps, channel_type=ctype)
    dff_cases = [
        ('one_cluster', 8, 1, False), ('mono_9', 9, 1, False),
        ('mono_16', 16, 1, False), ('mono_128_manf', 128, 1, True),
        ('stereo_128', 128, 2, False), ('four_16', 16, 4, False),
        ('five_16', 16, 5, False), ('six_16', 16, 6, False),
    ]
    for name, frames, nch, manf in dff_cases:
        ch_bits = bits(frames, nch)
        entries[name + '.dff'] = fixture_record(out / (name + '.dff'),
            make_dff(ch_bits, trailing_manf=manf), DSD64, ch_bits, 'dff',
            'walk spans and read chronological samples', trailing_manf=manf)
    for name, frames, nch in [('mono_16', 16, 1), ('stereo_32', 32, 2)]:
        ch_bits = bits(frames, nch)
        entries[name + '.wsd'] = fixture_record(out / (name + '.wsd'),
            make_wsd(ch_bits), DSD64, ch_bits, 'wsd', 'read chronological samples')
    for frames in (1, 15, 16, 17, 32, 33):
        ch_bits = bits(frames, 2, '69')
        words = dop_words(ch_bits)
        raw = bytes(b for transport_frame in words for word in transport_frame
                    for b in (word & 0xff, word >> 8 & 0xff, word >> 16 & 0xff))
        name = f'dop_stereo_{frames}.pcm24le'
        entries[name] = fixture_record(out / name, raw, DSD64, ch_bits,
            'dop-pcm24le', '16 DSD frames per PCM frame; 0x05/0xFA markers',
            transport_frames=len(words), expected_transport_words=words)
    # Raw PCM sources are fixtures only: not an independent quality oracle.
    pcm_frames = 4096
    for rate, freq, level in [(88200, 997, -6.0), (352800, 1000, -20.0), (705600, 997, -60.0)]:
        samples = [max(-32768, min(32767, int(round(32767 * 10 ** (level / 20) *
                         math.sin(2 * math.pi * freq * n / rate)))))
                   for n in range(pcm_frames)]
        name = f'pcm_sine_{rate}.wav'
        target = out / name
        with wave.open(str(target), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(struct.pack('<' + 'h' * len(samples), *samples))
        entries[name] = dict(file=name, kind='pcm-wav16', source='analytic 997/1000 Hz sine',
                             license='CC0-1.0', sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                             sample_rate=rate, frames=pcm_frames, channels=1,
                             frequency_hz=freq, nominal_peak_dbfs=level,
                             expected_operation='metrology scaffold, no DSD quality claim')
    manifest = dict(schema='dsd-fixtures/1', generator_seed=SEED,
                    chronology='oldest frame first; interleaved samples = frames * channels',
                    fixtures=entries)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'fixtures')
    args = ap.parse_args()
    print(json.dumps(dict(files=len(generate(args.out)['fixtures']), directory=str(args.out))))
