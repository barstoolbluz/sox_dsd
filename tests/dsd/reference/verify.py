"""Independent strict readers/checkers for reference fixtures.

Do not import fixture encoder algorithms here. This parser checks physical
chunk boundaries and reconstructs chronology from stored representation.
"""
from __future__ import annotations

import hashlib
import struct


class StructureError(ValueError):
    pass


def check(value: bool, reason: str) -> None:
    if not value:
        raise StructureError(reason)


def chunks(blob: bytes, start: int, end: int) -> list[dict]:
    out = []
    check(0 <= start <= end <= len(blob), 'enclosing extent')
    cursor = start
    while cursor < end:
        check(end - cursor >= 12, 'truncated chunk header')
        n = struct.unpack_from('>Q', blob, cursor + 4)[0]
        pad = n % 2
        finish = cursor + 12 + n + pad
        check(finish <= end, 'chunk exceeds enclosing span')
        check(not pad or blob[finish - 1] == 0, 'nonzero external pad')
        out.append(dict(tag=blob[cursor:cursor+4].decode('ascii'), start=cursor,
                        payload_start=cursor+12, payload_end=cursor+12+n,
                        payload_size=n, end=finish, pad=pad))
        cursor = finish
    check(cursor == end, 'unconsumed span')
    return out


def decode_dff(blob: bytes) -> dict:
    check(blob[:4] == b'FRM8' and len(blob) >= 16, 'missing FRM8')
    parent = struct.unpack_from('>Q', blob, 4)[0]
    check(parent + 12 == len(blob), 'FRM8 size mismatches physical file')
    check(blob[12:16] == b'DSD ', 'wrong FRM8 form')
    top = chunks(blob, 16, len(blob))
    check([c['tag'] for c in top].count('PROP') == 1, 'PROP missing')
    check([c['tag'] for c in top].count('DSD ') == 1, 'audio missing')
    prop = next(c for c in top if c['tag'] == 'PROP')
    check(blob[prop['payload_start']:prop['payload_start']+4] == b'SND ', 'wrong PROP')
    sub = chunks(blob, prop['payload_start']+4, prop['payload_end'])
    fields = {c['tag']: blob[c['payload_start']:c['payload_end']] for c in sub}
    check(all(k in fields for k in ('FS  ', 'CHNL', 'CMPR')), 'required property missing')
    check(len(fields['CHNL']) >= 2, 'short CHNL')
    nch = struct.unpack_from('>H', fields['CHNL'])[0]
    check(1 <= nch <= 1000 and len(fields['CHNL']) == 2 + 4 * nch, 'CHNL size invalid')
    check(fields['CMPR'] == b'DSD ' + bytes([14]) + b'not compressed', 'CMPR count/payload invalid')
    check(len(fields['FS  ']) == 4, 'FS size invalid')
    audio_chunk = next(c for c in top if c['tag'] == 'DSD ')
    raw = blob[audio_chunk['payload_start']:audio_chunk['payload_end']]
    check(len(raw) % nch == 0, 'incomplete channel cluster')
    channel_bits = [bytearray() for _ in range(nch)]
    for offset in range(0, len(raw), nch):
        for ch in range(nch):
            byte = raw[offset + ch]
            channel_bits[ch].extend((byte >> (7-k)) & 1 for k in range(8))
    return dict(channels=nch, frames=len(raw)*8//nch, rate=struct.unpack('>I', fields['FS  '])[0],
                chronological_bits_sha256=chronology_sha256(channel_bits),
                timeline=[bytes(b) for b in channel_bits], top=top, prop=sub,
                audio=audio_chunk)


def chronology_sha256(timeline) -> str:
    return hashlib.sha256(bytes(v for frame in zip(*timeline) for v in frame)).hexdigest()


def decode_dsf(blob: bytes) -> dict:
    check(len(blob) >= 92 and blob[:4] == b'DSD ', 'short DSF')
    hsize, size, meta = struct.unpack_from('<QQQ', blob, 4)
    check(hsize == 28 and size == len(blob) and meta == 0, 'DSF header span')
    check(blob[28:32] == b'fmt ', 'DSF fmt missing')
    (fs, version, fmt, typ, channels, rate, bps, frames, block, reserved) = struct.unpack_from('<QIIIIIIQII', blob, 32)
    check(fs == 52 and version == 1 and fmt == 0 and reserved == 0, 'DSF fmt invalid')
    check(1 <= channels <= 6 and bps in (1, 8), 'DSF encoding invalid')
    check(0 < block <= 1 << 20, 'DSF block invalid')
    check(blob[80:84] == b'data', 'DSF data missing')
    declared = struct.unpack_from('<Q', blob, 84)[0]
    num_blocks = (frames + block * 8 - 1) // (block * 8)
    check(declared == 12 + num_blocks * block * channels, 'DSF data extent')
    check(80 + declared == len(blob), 'DSF physical data span')
    timeline = [bytearray() for _ in range(channels)]
    for i in range(frames):
        bidx, bitidx = divmod(i, 8)
        group, inblock = divmod(bidx, block)
        for ch in range(channels):
            byte = blob[92 + (group * channels + ch) * block + inblock]
            timeline[ch].append((byte >> (bitidx if bps == 1 else 7 - bitidx)) & 1)
    return dict(channels=channels, frames=frames, rate=rate, bps=bps,
                channel_type=typ, chronological_bits_sha256=chronology_sha256(timeline),
                timeline=[bytes(b) for b in timeline])


def decode_dop(raw: bytes, nch: int, original_frames: int) -> dict:
    check(nch > 0 and len(raw) % (nch * 3) == 0, 'DoP transport words')
    rows = len(raw) // (nch * 3)
    timeline = [bytearray() for _ in range(nch)]
    for frame in range(rows):
        for ch in range(nch):
            pos = (frame * nch + ch) * 3
            lo, hi, marker = raw[pos:pos+3]
            check(marker == (0x05 if frame % 2 == 0 else 0xFA), 'DoP marker continuity')
            payload = lo | hi << 8
            timeline[ch].extend((payload >> (15-i)) & 1 for i in range(16))
    check(0 <= original_frames <= rows * 16, 'invalid DoP frames')
    timeline = [bytes(v[:original_frames]) for v in timeline]
    return dict(channels=nch, frames=original_frames,
                chronological_bits_sha256=chronology_sha256(timeline), timeline=timeline)
