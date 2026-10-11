#!/usr/bin/env python3
"""Vectorised DSD bitstream reader and 28-bit window statistics.

The authority for DSF/DSDIFF layout is `reference/verify.py`, whose decoders
walk the container one bit at a time. That is correct but far too slow for the
hundreds of millions of frames a real recording produces, so this module reads
the same layouts with numpy. `--self-check` proves the two agree bit for bit on
a caller-supplied file; run it before trusting any measurement from here.
"""
from __future__ import annotations
import argparse
import struct
from pathlib import Path
import numpy as np

WINDOW = 28


def dsf_channel_bits(blob: bytes) -> dict:
    """Per-channel chronological bits of a DSF file, as uint8 0/1 arrays."""
    if blob[:4] != b'DSD ' or blob[28:32] != b'fmt ':
        raise ValueError('not a DSF stream')
    (fs, version, fmt, typ, channels, rate, bps, frames, block,
     reserved) = struct.unpack_from('<QIIIIIIQII', blob, 32)
    if blob[80:84] != b'data':
        raise ValueError('DSF data chunk missing')
    blocks = (frames + block * 8 - 1) // (block * 8)
    data = np.frombuffer(blob, dtype=np.uint8, count=blocks * block * channels,
                         offset=92).reshape(blocks, channels, block)
    order = 'little' if bps == 1 else 'big'
    bits = [np.unpackbits(np.ascontiguousarray(data[:, ch, :]).ravel(),
                          bitorder=order)[:frames] for ch in range(channels)]
    return dict(channels=channels, rate=rate, frames=frames, bps=bps, bits=bits)


def window_ones(bits: np.ndarray, width: int = WINDOW, chunk: int = 1 << 26):
    """Exact min/max ones over every complete `width`-bit window.

    Chunked so the running sums stay in int32 and memory stays bounded; chunks
    overlap by width-1 bits so no window straddling a boundary is missed.
    """
    n = bits.size
    if n < width:
        return None, None, 0
    lo, hi = width, 0
    start = 0
    while start + width <= n:
        stop = min(n, start + max(chunk, width) + width - 1)
        seg = bits[start:stop]
        cs = np.zeros(seg.size + 1, dtype=np.int32)
        np.cumsum(seg, dtype=np.int32, out=cs[1:])
        w = cs[width:] - cs[:-width]
        lo = min(lo, int(w.min()))
        hi = max(hi, int(w.max()))
        start = stop - width + 1
    return lo, hi, n - width + 1


def dsf_window_statistics(path: Path, *, chunk_blocks: int = 128) -> dict:
    """Verify a DSF payload and count ALL complete chronological bit windows.

    Process interleaved channel blocks from disk in bounded batches. Preserve
    the last 27 *valid* bits across batches, including non-byte-aligned final
    frames. No full-file `read_bytes` or frame-sized NumPy allocation is used.
    """
    if not 1 <= chunk_blocks <= 4096:
        raise ValueError('chunk_blocks must be between 1 and 4096')
    with open(path, 'rb') as stream:
        header = stream.read(92)
        if len(header) != 92 or header[:4] != b'DSD ' or header[28:32] != b'fmt ' \
                or header[80:84] != b'data':
            raise ValueError('invalid DSF header')
        _, _, _, _, channels, rate, bps, frames, block, _ = struct.unpack_from(
            '<QIIIIIIQII', header, 32)
        size = struct.unpack_from('<Q', header, 84)[0]
        if not 1 <= channels <= 64 or not 1 <= block <= 65536 or bps not in (1, 8):
            raise ValueError('invalid DSF sample layout')
        blocks = (frames + block * 8 - 1) // (block * 8)
        payload = blocks * block * channels
        if size < 12 or size - 12 < payload:
            raise ValueError('truncated DSF declared data chunk')
        totals = [dict(channel=c, windows=0, min_ones=None, max_ones=None,
                       one_bits=0, ones_fraction=0.) for c in range(channels)]
        carried = [np.empty(0, dtype=np.uint8) for _ in range(channels)]
        consumed = 0
        # A caller-supplied chunk limit must not multiply a large valid block
        # size and channel count into multi-gigabyte temporary arrays. The
        # per-batch raw payload is capped at 4 MiB; even unpacked bits fit in
        # bounded working memory (one channel at a time).
        max_batch = max(1, (4 << 20) // (block * channels))
        batch_limit = min(chunk_blocks, max_batch)
        for first in range(0, blocks, batch_limit):
            batch = min(batch_limit, blocks - first)
            nbytes = batch * block * channels
            data = stream.read(nbytes)
            if len(data) != nbytes:
                raise ValueError('truncated DSF sample data')
            interleaved = np.frombuffer(data, dtype=np.uint8).reshape(
                batch, channels, block)
            valid = min(batch * block * 8, frames - consumed)
            for c in range(channels):
                samples = np.unpackbits(np.ascontiguousarray(
                    interleaved[:, c, :]).ravel(),
                    bitorder='little' if bps == 1 else 'big')[:valid]
                stat = totals[c]
                stat['one_bits'] += int(np.count_nonzero(samples))
                if carried[c].size:
                    samples = np.concatenate((carried[c], samples))
                if samples.size >= WINDOW:
                    accum = np.empty(samples.size + 1, dtype=np.int32)
                    accum[0] = 0
                    np.cumsum(samples, dtype=np.int32, out=accum[1:])
                    windows = accum[WINDOW:] - accum[:-WINDOW]
                    stat['windows'] += int(windows.size)
                    low, high = int(windows.min()), int(windows.max())
                    stat['min_ones'] = low if stat['min_ones'] is None else min(
                        low, stat['min_ones'])
                    stat['max_ones'] = high if stat['max_ones'] is None else max(
                        high, stat['max_ones'])
                carried[c] = samples[-(WINDOW - 1):].copy()
            consumed += valid
        if consumed != frames:
            raise ValueError('DSF sample count mismatch')
        expected = max(0, frames - WINDOW + 1)
        for stat in totals:
            if stat['windows'] != expected:
                raise ValueError('DSF bit-window count mismatch')
            stat['ones_fraction'] = stat['one_bits'] / frames if frames else 0.
        return dict(channels=channels, rate=rate, frames=frames,
                    bps=bps, windows_per_channel=expected,
                    per_channel=totals)


def self_check(path: Path) -> dict:
    """Compare against reference/verify.decode_dsf bit for bit."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from reference import verify
    blob = Path(path).read_bytes()
    oracle = verify.decode_dsf(blob)
    fast = dsf_channel_bits(blob)
    same = (oracle['channels'] == fast['channels'] and
            oracle['frames'] == fast['frames'] and
            oracle['rate'] == fast['rate'] and
            all(np.array_equal(np.frombuffer(oracle['timeline'][c], dtype=np.uint8),
                               fast['bits'][c]) for c in range(oracle['channels'])))
    streamed = dsf_window_statistics(path, chunk_blocks=1)
    stream_same = (streamed['channels'] == fast['channels'] and
                   streamed['rate'] == fast['rate'] and
                   streamed['frames'] == fast['frames'] and
                   all((s['min_ones'], s['max_ones'], s['windows'], s['one_bits']) ==
                       (*window_ones(fast['bits'][c]), int(np.count_nonzero(fast['bits'][c])))
                       for c, s in enumerate(streamed['per_channel'])))
    return dict(file=Path(path).name, channels=fast['channels'], frames=fast['frames'],
                rate=fast['rate'], bit_identical_to_oracle=bool(same),
                stream_stats_identical_to_oracle=bool(stream_same))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-check', type=Path, required=True,
                    help='a small DSF file to check against the slow oracle')
    a = ap.parse_args()
    import json
    result = self_check(a.self_check)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['bit_identical_to_oracle'] and result['stream_stats_identical_to_oracle'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
