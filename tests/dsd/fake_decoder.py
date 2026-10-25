#!/usr/bin/env python3
"""Deterministic file-format stand-in for offline gate orchestration tests.

Not a DSD decoder; do not use its output as real qualification evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

import numpy as np


def generate(source, output, hz, seconds):
    digest = hashlib.sha256(Path(source).read_bytes()).digest()
    freqs = [191 + int.from_bytes(digest[:2], 'little') % 490,
             911 + int.from_bytes(digest[2:4], 'little') % 490]
    count = int(round(float(seconds) * int(hz)))
    t = np.arange(count, dtype=np.float64) / float(hz)
    channels = [0.33 * np.sin(2*np.pi*freq*t) +
                0.10 * np.sin(2*np.pi*(freq*4 + 41)*t) for freq in freqs]
    samples = np.stack(channels, axis=1)
    mutation = os.getenv('FAKE_MUTATION') if Path(sys.argv[0]).name == 'sox' else None
    if mutation == 'gain':
        samples *= 1.05
    elif mutation == 'swap':
        samples = samples[:, ::-1]
    elif mutation == 'shift':
        samples = np.roll(samples, 64, axis=0)
    elif mutation == 'noise':
        samples = np.random.default_rng(3).normal(0, samples.std(), samples.shape)
    elif mutation == 'truncate':
        samples = samples[:count // 2]
    elif mutation == 'dropout':
        samples[count//2:count//2+max(1, count//100)] = 0
    if mutation == 'control-fail':
        pass
    samples.astype('<f8').tofile(output)


def dff_chunk(name, data):
    return name + struct.pack('>Q', len(data)) + data + (b'\0' if len(data) % 2 else b'')


def encode_fake_dsd(destination, raw, requested):
    """Write real DSF/DFF clock fields, not playable audio, for gate tests."""
    native = 22579200 if os.getenv('FAKE_WRONG_CLOCK') == '1' else requested
    source = ('fixed' if os.getenv('FAKE_COLLIDE_SOURCES') == '1'
              else hashlib.sha256(Path(raw).read_bytes()).hexdigest())
    payload = json.dumps({'pcm_sha': source, 'requested_clock': requested}).encode()
    if destination.suffix == '.dsf':
        fmt = struct.pack('<4sQIIIIIIQII', b'fmt ', 52, 1, 0, 2, 2,
                          native, 1, 0, 4096, 0)
        data = b'data' + struct.pack('<Q', 12 + len(payload)) + payload
        header = struct.pack('<4sQQQ', b'DSD ', 28, 28 + len(fmt) + len(data), 0)
        destination.write_bytes(header + fmt + data)
    else:
        prop = b'SND ' + dff_chunk(b'FS  ', struct.pack('>I', native))
        form = (b'DSD ' + dff_chunk(b'FVER', b'\x01\x05\x00\x00') +
                dff_chunk(b'PROP', prop) + dff_chunk(b'DSD ', payload))
        destination.write_bytes(b'FRM8' + struct.pack('>Q', len(form)) + form)


def main():
    argv = sys.argv[1:]
    if '-version' in argv:
        print('ffmpeg test double v1')
        return 0
    if '--i' in argv:
        if os.getenv('FAKE_PROBE_ERROR') == '1':
            return 9
        print(22579200)
        return 0
    if '-i' in argv:
        source = argv[argv.index('-i') + 1]
        if os.getenv('FAKE_CONTROL_ERROR') == '1' and argv[-2].endswith('-ctl.f64'):
            return 9
        generate(source, argv[-2], int(argv[argv.index('-ar')+1]),
                 float(argv[argv.index('-t')+1]))
        return 0
    if 'trim' in argv:
        # The decode form has '-D INPUT' and the encode's input is a raw file.
        source = argv[argv.index('-D')+1]
        output = argv[argv.index('trim')-1]
        if (os.getenv('FAKE_EXTRACT_FAIL') == '1' and
                Path(output).name.startswith('src')):
            return 9
        hz = int(argv[argv.index('-r')+1])
        seconds = float(argv[argv.index('trim')+2])
        generate(source, output, hz, seconds)
        return 0
    # Encode raw PCM to a deterministic stand-in with native container headers.
    if '-t' in argv:
        raw = argv[argv.index('-c')+2]
        encode_fake_dsd(Path(argv[-1]), raw, int(argv[-2]))
        return 0
    return 10


if __name__ == '__main__':
    raise SystemExit(main())
