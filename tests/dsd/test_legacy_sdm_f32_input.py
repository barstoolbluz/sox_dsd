#!/usr/bin/env python3
"""Prove native float32 raw input retains scalar sample and clipping semantics.

Covers the AVX1-only four-lane reader as well as the original scalar reader.
Use explicit little-endian PCM so the Python oracle is independent of SoX.
"""
import argparse
import math
import os
from pathlib import Path
import random
import re
import struct
import subprocess
import tempfile


INT_MIN = -(1 << 31)
INT_MAX = (1 << 31) - 1


def vectors():
    # Raw IEEE-754 words preserve +0/-0, near-1 boundaries and subnormals.
    edge = [0, 0x80000000, 1, 0x80000001, 0x007fffff, 0x807fffff,
            0x00800000, 0x80800000, 0x3f7fffff, 0xbf7fffff,
            0x3f800000, 0xbf800000, 0x3f800001, 0xbf800001,
            0x3f000000, 0xbf000000, 0x7f7fffff, 0xff7fffff]
    rng = random.Random(0x53D01)
    words = list(edge)
    for _ in range(9000):
        word = rng.getrandbits(32)
        # Non-finite inputs have no portable C float-to-int oracle. The
        # production reader takes its original scalar fallback for them.
        if (word & 0x7f800000) == 0x7f800000:
            word = (word & 0x80000000) | 0x7f7fffff
        words.append(word)
    for _ in range(1000):
        words.append(struct.unpack('<I', struct.pack('<f', rng.uniform(-2, 2)))[0])
    return words


def sample(word):
    f = struct.unpack('<f', struct.pack('<I', word))[0]
    x = f * (1 << 31)
    if x < INT_MIN:
        return INT_MIN, 1
    if x >= INT_MAX + 1:
        return INT_MAX, int(x > INT_MAX + 1)
    return math.trunc(x), 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sox', type=Path, required=True)
    args = p.parse_args()
    sox = args.sox.resolve(strict=True)
    rng = random.Random(0x53D02)
    all_words = vectors()
    counts = [1, 2, 3, 4, 5, 6, 7, 8, 30, 31, 32,
              8190, 8191, 8192, 8193, 8194, 9999, 10000]
    cases = 0
    env = os.environ.copy()
    env.pop('SOX_OPTS', None)
    with tempfile.TemporaryDirectory(prefix='legacy-sdm-f32-') as folder:
        tmp = Path(folder)
        for channels in (1, 2):
            for count in counts:
                if count % channels:
                    continue
                # Rotate the vector sequence so groups of four encounter
                # clipped and boundary values in every possible lane.
                off = rng.randrange(len(all_words))
                words = [all_words[(off + i) % len(all_words)] for i in range(count)]
                values = [sample(w) for w in words]
                expected = b''.join(struct.pack('<i', s) for s, _ in values)
                clips = sum(c for _, c in values)
                src, dst = tmp / 'in.f32', tmp / 'out.s32'
                src.write_bytes(b''.join(struct.pack('<I', w) for w in words))
                cmd = [str(sox), '-D', '-R', '-L', '-t', 'f32', '-r', '48000',
                       '-c', str(channels), str(src), '-L', '-t', 'raw',
                       '-e', 'signed-integer', '-b', '32', str(dst)]
                result = subprocess.run(cmd, env=env, capture_output=True, timeout=45)
                if result.returncode:
                    raise AssertionError(f'{channels}ch {count}: SoX exit {result.returncode}: {result.stderr}')
                if dst.read_bytes() != expected:
                    raise AssertionError(f'{channels}ch {count}: float32-to-int32 output differs from scalar oracle')
                stderr = result.stderr.decode(errors='replace')
                reported = re.search(r'input clipped (\d+) samples?', stderr)
                actual_clips = int(reported.group(1)) if reported else 0
                if actual_clips != clips:
                    raise AssertionError(f'{channels}ch {count}: clipped {actual_clips}, expected {clips}: {stderr}')
                cases += 1
    print(f'legacy f32 reader: {cases} scalar-oracle cases passed')


if __name__ == '__main__':
    main()
