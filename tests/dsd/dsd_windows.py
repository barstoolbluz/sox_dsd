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
    return dict(file=Path(path).name, channels=fast['channels'], frames=fast['frames'],
                rate=fast['rate'], bit_identical_to_oracle=bool(same))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-check', type=Path, required=True,
                    help='a small DSF file to check against the slow oracle')
    a = ap.parse_args()
    import json
    result = self_check(a.self_check)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['bit_identical_to_oracle'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
