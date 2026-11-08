#!/usr/bin/env python3
"""P21 multichannel/offset regression with deterministic synthetic audio.

Unit checks need only Python. With --sox and --reference, additionally encode
independent four/six-channel input, decode each with SoX and FFmpeg, inspect
all runtime decoder rows, and apply P21 audio and negative-control gates.
The actual test is not commercial-media qualification.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from p21_independent_reader import (
    REFERENCE_OFFSET_NATIVE_FRAMES, compare, decode_ours, decode_reference,
    judge, native_dsd_channels, native_dsd_rate)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fake_metrics(n, shift=REFERENCE_OFFSET_NATIVE_FRAMES, cross=0.0):
    return dict(channel_count=n, reference_shift_native_frames=shift,
                control_pearson_r=[0.0] * n,
                channels=[dict(channel=k, pearson_r=0.99999,
                               cross_channel_pearson_r=cross,
                               level_delta_db=0.0,
                               max_window_rms_residual=0.001)
                          for k in range(n)])


def unit():
    for n in (2, 4, 6):
        good = fake_metrics(n)
        require(judge(good)[0], f'valid {n}-channel metrics must pass')
        require(not judge(fake_metrics(n, shift=-38.5))[0],
                'two-native-frame shift must fail even when residual is small')
        require(not judge(fake_metrics(n, cross=.999))[0],
                'channel-swapped/wrong-source match must fail identity gate')
        missing = fake_metrics(n)
        missing['control_pearson_r'] = [0.0] * (n - 1)
        require(not judge(missing)[0], 'missing negative-control channel must fail')
        missing = fake_metrics(n)
        missing['channels'] = missing['channels'][:-1]
        require(not judge(missing)[0], 'missing decoder metric channel must fail')
    for n in (1, 7):
        require(not judge(fake_metrics(n))[0], 'unsupported channel count must fail')


def wav(path, channels, other=False):
    rate, frames = 176400, round(.65 * 176400)
    freqs = ([1801, 2141, 2897, 3271, 3719, 4327] if other else
             [997, 1237, 1709, 2081, 2741, 3121])
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(channels)
        out.setsampwidth(4)
        out.setframerate(rate)
        data = bytearray()
        for i in range(frames):
            envelope = min(1.0, i / (rate * .02), (frames - 1 - i) / (rate * .02))
            for ch in range(channels):
                x = 0.22 * envelope * math.sin(2 * math.pi * freqs[ch] * i / rate)
                data.extend(struct.pack('<i', int(x * (2**31 - 1))))
        out.writeframes(data)


def execute(sox, ref, root):
    rows = []
    for n, hz, ext, profile in ((4, 22579200, 'dff', None),
                                (6, 45158400, 'dff', 'mastering')):
        samples = []
        for k in (0, 1):
            src = root / f'{n}ch-{k}.wav'
            dst = root / f'{n}ch-{k}.{ext}'
            wav(src, n, other=bool(k))
            roles = ('FL,FR,BL,BR' if n == 4 else 'FL,FR,FC,LFE,BL,BR')
            p = subprocess.run([str(sox), str(src), '--dsd-layout', roles,
                                '-r', str(hz), str(dst)],
                               capture_output=True, text=True, timeout=120)
            require(p.returncode == 0, f'{n}ch encode failed: {p.stderr[-800:]}')
            require(native_dsd_channels(dst, ext) == n, 'native header channel count mismatch')
            require(native_dsd_rate(dst, ext) == hz, 'native header rate mismatch')
            samples.append(dst)
        out_hz = 176400
        ours = root / f'{n}ch-ours.f64'
        ref_pcm = root / f'{n}ch-ref.f64'
        control = root / f'{n}ch-control.f64'
        report = root / f'{n}ch-report.json'
        rc, err = decode_ours(sox, samples[0], profile, out_hz, n, ours,
                               0.0, .5, 120, report)
        require(rc == 0, f'{n}ch SoX decode failed: {err}')
        decoder = json.loads(report.read_text())['processing']['decoder']
        expected = f'decode.mastering.{"v2" if profile else "v1"}.dsd{hz//44100}'
        require(len(decoder) == n and all(x['profile_id'] == expected for x in decoder),
                f'{n}ch wrong runtime decoder rows: {decoder}')
        rc, err = decode_reference(ref, samples[0], out_hz, n, ref_pcm,
                                   0.0, .5, 120)
        require(rc == 0, f'{n}ch FFmpeg decode failed: {err}')
        rc, err = decode_reference(ref, samples[1], out_hz, n, control,
                                   0.0, .5, 120)
        require(rc == 0, f'{n}ch FFmpeg negative control failed: {err}')
        metrics, why = compare(ours, ref_pcm, control, out_hz, hz, n, .5)
        require(metrics is not None, f'{n}ch compare failed: {why}')
        passed, reasons = judge(metrics)
        require(passed, f'{n}ch P21 fail: {reasons}, metrics {metrics}')
        if n == 4:
            import numpy as np
            broken = root/'4ch-silent-reference.f64'
            frames = np.fromfile(ref_pcm, dtype='<f8').reshape(-1, n)
            frames[:, 2] = 0.
            frames.tofile(broken)
            invalid, reason = compare(ours, broken, control, out_hz, hz, n, .5)
            require(invalid is None and reason and
                    'independent reference has no usable' in reason,
                    'silent reference channel must fail closed with a stable reason')
        rows.append(dict(channels=n, native_hz=hz, decoder_id=expected,
                         reference_shift_native_frames=metrics['reference_shift_native_frames'],
                         min_pearson=min(row['pearson_r'] for row in metrics['channels']),
                         status='PASS'))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sox', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--results', type=Path)
    args = parser.parse_args()
    unit()
    receipt = dict(unit='PASS', multichannel=[])
    if args.sox is not None or args.reference is not None:
        if not args.sox or not args.reference:
            parser.error('--sox and --reference must be provided together')
        with tempfile.TemporaryDirectory(prefix='sox-p21-multichannel-') as folder:
            receipt['multichannel'] = execute(args.sox.resolve(),
                                               args.reference.resolve(), Path(folder))
    if args.results:
        args.results.parent.mkdir(parents=True, exist_ok=True)
        args.results.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
