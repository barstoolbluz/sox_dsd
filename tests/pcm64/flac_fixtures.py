#!/usr/bin/env python3
"""Independent deterministic signed-PCM input words for Phase 02B FLAC.

The oracle is constructed from integer codes, not libSoX or libFLAC output.
The vendored flac 1.5.0 CLI encodes these raw words once; the checked-in FLAC
files let a no-network test host run the decode checks without a FLAC encoder.
Use --generate with the encoder only to recreate the fixtures.
"""
from __future__ import annotations
import argparse
import random
import subprocess
from pathlib import Path

RATE = 48000
SEED = 0x2026111102
SPECS = ((8, 1, 127), (8, 2, 5073), (16, 1, 191),
         (16, 6, 4497), (24, 2, 4973), (24, 6, 5123),
         (32, 1, 8193), (32, 2, 5193), (32, 6, 4113))


def name(bits: int, channels: int, frames: int) -> str:
    return f"signed-{bits}bit-{channels}ch-{frames}frames.flac"


def codes(bits: int, channels: int, frames: int) -> list[int]:
    lim = 1 << (bits - 1)
    edges = (-lim, -lim+1, -lim+2, -lim//2, -2, -1, 0, 1,
             2, lim//2, lim-3, lim-2, lim-1)
    r = random.Random(SEED ^ (bits << 18) ^ (channels << 10) ^ frames)
    out = [r.randrange(-lim, lim) for _ in range(frames*channels)]
    for anchor in (0, 1, 64, 4094, 4095, 4096, 4097, frames-3, frames-1):
        for offset, value in enumerate(edges):
            idx = anchor*channels + offset
            if 0 <= idx < len(out):
                out[idx] = value
    # Explicit very-low-bit cases for every channel, including 32-bit extrema.
    for c in range(channels):
        for k, v in enumerate((-lim, -lim+1, -1, 0, 1, lim-1)):
            idx = k*channels + c
            if idx < len(out):
                out[idx] = v
    return out


def raw_pcm(bits: int, values: list[int]) -> bytes:
    n = bits // 8
    return b''.join(v.to_bytes(n, 'little', signed=True) for v in values)


def generate(folder: Path, encoder: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for bits, channels, frames in SPECS:
        dest = folder/name(bits, channels, frames)
        raw = folder/(dest.stem+'.raw')
        raw.write_bytes(raw_pcm(bits, codes(bits, channels, frames)))
        args = [encoder, '--force-raw-format', '--endian=little', '--sign=signed',
                f'--channels={channels}', f'--bps={bits}', f'--sample-rate={RATE}',
                '--blocksize=4096', '--no-padding', '--silent', '--force',
                f'--output-name={dest}', str(raw)]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
            if proc.returncode:
                raise RuntimeError(f'{dest.name}: {proc.stderr}')
        finally:
            raw.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true', required=True)
    parser.add_argument('--flac', default='flac')
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('fixtures'))
    options = parser.parse_args()
    generate(options.output, options.flac)
