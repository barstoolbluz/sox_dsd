#!/usr/bin/env python3
"""CLI regression for overload, strict refusal and measured PCM-to-DSD headroom.

The stereo fixture has a 11025 Hz phase-shifted tone: sampled peaks stay
below 0 dBFS, but its reconstructed peak is above 0 dBFS. This avoids
relying on a random noise generator or vendor recordings.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import struct
from array import array
import sys


def fixture(path, hot):
    samples = 8820
    phase = 0.6
    # The four distinct samples of the 11025 Hz tone never exceed 0.99 FS.
    sampled_peak = max(abs(math.sin(math.pi * i / 2 + phase)) for i in range(4))
    gain = (0.99 / sampled_peak) if hot else 0.15
    pcm = bytearray()
    for i in range(samples):
        values = (gain * math.sin(math.pi * i / 2 + phase),
                  0.3 * math.sin(2 * math.pi * 997 * i / 44100))
        for value in values:
            number = round(value * ((1 << 23) - 1))
            assert abs(number) < (1 << 23)
            pcm.extend(number.to_bytes(3, 'little', signed=True))
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(44100)
        out.writeframes(pcm)


def run(sox, *args, stdin=None, threads='1'):
    return subprocess.run([str(sox), *map(str, args)], input=stdin,
                          capture_output=True, timeout=120,
                          env={**os.environ, 'OMP_NUM_THREADS': threads})


def accepted(p, label):
    assert p.returncode == 0, f'{label}: {p.returncode}: {p.stderr.decode(errors="replace")[-900:]}'
    return p


def declined(p, label):
    assert p.returncode != 0, f'{label}: unexpectedly accepted'
    return p


def encoders(report):
    data = json.loads(report.read_text())
    assert data['status'] == 'complete'
    enc = data['processing']['encoder']
    assert len(enc) == 2, f'expected stereo measurements, got {enc}'
    assert all(int(e['committed_native_frames']) > 0 for e in enc)
    return enc


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fullscale_sine(path):
    """IEEE-754 WAV, stereo 1 kHz/44.1 kHz at 0.95 FS, without DSP clipping."""
    hz, channels, frames = 44100, 2, 2 * 44100
    pcm = bytearray()
    for i in range(frames):
        value = 0.95 * math.sin(2 * math.pi * 1000 * i / hz)
        pcm.extend(struct.pack('<ff', value, value))
    header = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + len(pcm),
                         b'WAVE', b'fmt ', 16, 3, channels, hz,
                         hz * channels * 4, channels * 4, 32,
                         b'data', len(pcm))
    path.write_bytes(header + pcm)


def goertzel_amplitude(signal, frequency, hz=88200):
    """Coherent, window-free harmonic measurement with no NumPy dependency."""
    factor = 2 * math.cos(2 * math.pi * frequency / hz)
    prev, before = 0.0, 0.0
    for sample in signal:
        prev, before = sample + factor * prev - before, prev
    power = max(0.0, prev * prev + before * before - factor * prev * before)
    return 2 * math.sqrt(power) / len(signal)


def decoded_thd(sox, dsd, raw):
    accepted(run(sox, dsd, '-r', '88200', '-c', '1',
                 '-e', 'floating-point', '-b', '64', '-L', '-t', 'f64', raw),
             'DSD reconstruction for THD')
    samples = array('d')
    samples.frombytes(raw.read_bytes())
    if sys.byteorder != 'little':
        samples.byteswap()
    # Exclude transition and EOF tails; 1.5 seconds contains 1,500 cycles.
    segment = samples[88200 // 4:7 * 88200 // 4]
    assert len(segment) == 132300
    fundamental = goertzel_amplitude(segment, 1000)
    harmonics = [goertzel_amplitude(segment, 1000 * h)
                 for h in range(2, 20)]
    thd_db = 10 * math.log10(sum(h * h for h in harmonics) /
                             (fundamental * fundamental))
    return fundamental, thd_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    a = parser.parse_args()
    sox = a.sox.resolve()
    with tempfile.TemporaryDirectory(prefix='sox-dsd-loud-') as tmp:
        root = Path(tmp)
        hot = root / 'hot.wav'
        quiet = root / 'quiet.wav'
        fixture(hot, True)
        fixture(quiet, False)
        source_hash = digest(hot)
        for native in (64, 128, 256):
            # Every clock uses the same lower default clipping ceiling;
            # measured headroom targets the same value.
            ceiling = 0.45
            fixed_db = 4
            output = root / f'out-{native}.dsf'
            report = root / 'run.json'
            rate = f'dsd{native}'
            planned = json.loads(accepted(run(sox, '--plan', '--auto-headroom',
                                              hot, '-r', rate, output), 'plan').stdout)
            assert planned['policy']['headroom_mode'] == 'auto'
            assert planned['policy']['headroom_db'] is None
            assert planned['encoder']['warning_clip_ceiling'] == ceiling
            assert planned['encoder']['planned_linear_gain'] is None
            default_plan = json.loads(accepted(run(sox, '--plan', hot, '-r',
                                                   rate, output), 'default plan').stdout)
            expected_gain = 0.9
            assert abs(default_plan['encoder']['planned_linear_gain'] -
                       expected_gain) < 1e-14
            strict_plan = json.loads(accepted(run(sox, '--plan', '--dsd-clip',
                                                'error', hot, '-r', rate, output),
                                              'strict plan').stdout)
            assert strict_plan['encoder']['warning_clip_ceiling'] is None
            assert strict_plan['encoder']['planned_linear_gain'] == 1
            unavailable = json.loads(accepted(run(sox, '--plan', '--encode',
                                                  'legacy', hot, '-r', rate,
                                                  output), 'legacy plan').stdout)
            assert not unavailable['executable']
            assert unavailable['encoder']['warning_clip_ceiling'] is None
            assert unavailable['encoder']['planned_linear_gain'] is None
            assert not output.exists(), '--plan opened an audio output'

            default = accepted(run(sox, hot, '-r', rate, output), 'default warn')
            assert b'clipped' in default.stderr, 'loud default did not warn'
            default_hash = digest(output)
            accepted(run(sox, '--report', report, hot, '-r', rate, output),
                     'default with report')
            record = json.loads(report.read_text())
            clipped = [int(e['clipped_interpolated_samples'])
                       for e in record['processing']['encoder']]
            assert all(e['clip_ceiling_applied'] == ceiling
                       for e in record['processing']['encoder'])
            expected_db = -20 * math.log10(expected_gain)
            assert all(abs(e['headroom_applied_db'] - expected_db) < 1e-12
                       for e in record['processing']['encoder'])
            assert clipped[0] > 0 and clipped[1] == 0, clipped
            assert int(record['clipping']['encoder_interpolation']) == sum(clipped)
            assert any('interpolation clipped' in w for w in record['warnings'])
            assert digest(output) == default_hash, 'report changed default clipping'
            accepted(run(sox, '--headroom', '0', hot, '-r', rate, output),
                     'zero fixed headroom')
            assert digest(output) != default_hash, \
                '--headroom 0 must override implicit default attenuation'
            assert declined(run(sox, '--dsd-clip', 'error', hot, '-r', rate,
                                output), 'strict').returncode == 2
            assert not output.exists(), 'failed strict conversion left a partial file'

            accepted(run(sox, '--report', report, '--headroom', str(fixed_db),
                         hot, '-r', rate, output), 'fixed headroom')
            fixed = encoders(report)
            assert int(json.loads(report.read_text())['clipping']['encoder_interpolation']) == 0
            assert all(int(e['clipped_interpolated_samples']) == 0 for e in fixed)
            assert all(abs(e['headroom_applied_db'] - fixed_db) < 1e-10 for e in fixed)
            assert digest(output) != default_hash, 'fixed headroom changed no audio'

            accepted(run(sox, '--report', report, '--auto-headroom',
                         '--dsd-clip', 'error', hot, '-r', rate, output), 'auto strict')
            auto = encoders(report)
            assert all(int(e['clipped_interpolated_samples']) == 0 for e in auto)
            assert all(e['clip_ceiling_applied'] is None for e in auto)
            cuts = [e['headroom_applied_db'] for e in auto]
            assert abs(cuts[0] - cuts[1]) < 1e-12, 'channels received different gains'
            assert 0.01 < cuts[0] < 5., f'headroom was not minimal: {cuts}'
            peak = max(e['peak_modulator_input'] for e in auto)
            assert abs(peak - ceiling) < 1e-9, f'measured cut was not tight: {peak}'
            auto_hash = digest(output)
            accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error',
                         hot, '-r', rate, output), 'auto without report')
            assert digest(output) == auto_hash, 'report changed headroom audio'
            assert digest(hot) == source_hash, 'scanning modified the input'
            print(f'PASS DSD{native}: clip/warn, refusal, fixed, stereo measured, report invariance')

        # The high clocks share the default policy. Their eighth-order v1
        # encoder is qualified only with the 0.9 gain, so strict refusal keeps
        # it there; an explicit --headroom still replaces it.
        for native in (512, 1024):
            plan = json.loads(accepted(run(sox, '--plan', hot, '-r', f'dsd{native}',
                                           root/'high.dsf'), 'high plan').stdout)
            assert plan['encoder']['warning_clip_ceiling'] == 0.45
            assert abs(plan['encoder']['planned_linear_gain'] - 0.9) < 1e-14
            strict = json.loads(accepted(run(sox, '--plan', '--dsd-clip', 'error', hot,
                                             '-r', f'dsd{native}', root/'high.dsf'),
                                         'high strict plan').stdout)
            assert strict['encoder']['warning_clip_ceiling'] is None
            assert abs(strict['encoder']['planned_linear_gain'] - 0.9) < 1e-14
            fixed = json.loads(accepted(run(sox, '--plan', '--dsd-clip', 'error',
                                            '--headroom', '0', hot, '-r', f'dsd{native}',
                                            root/'high.dsf'), 'high fixed plan').stdout)
            assert fixed['encoder']['planned_linear_gain'] == 1
        print('PASS DSD512/1024 plans: default ceiling and gain; strict keeps the gain')

        # D-01: previously the 0.45 hard limit clipped ~21% of native
        # samples of this perfectly valid 0.95-FS sine and generated about
        # -34 dBc THD. A constant linear default gain must preserve its
        # waveform, at the cost of a clearly reported 0.915 dB level cut.
        sine = root/'sine-0.95.wav'
        fullscale_sine(sine)
        for native in (64, 128, 256):
            rate = f'dsd{native}'
            output = root/f'sine-{native}.dsf'
            report = root/f'sine-{native}.json'
            accepted(run(sox, '--report', report, sine, '-r', rate, output),
                     f'DSD{native} fullscale sine')
            enc = encoders(report)
            assert all(int(e['clipped_interpolated_samples']) == 0 for e in enc)
            assert all(abs(e['headroom_applied_db'] + 20 * math.log10(0.9)) < 1e-12
                       for e in enc)
            fundamental, distortion = decoded_thd(sox, output, root/'sine.f64')
            assert 0.42 < fundamental < 0.435, fundamental
            assert distortion < -100, f'DSD{native} THD {distortion:.1f} dBc'
            print(f'PASS DSD{native} legal 0.95-FS sine: '
                  f'0 clips, THD {distortion:.1f} dBc')

        # Unity gain is the reference: the plain default always cuts 0.9.
        output = root/'quiet.dsf'
        accepted(run(sox, '--headroom', '0', quiet, output), 'quiet unity')
        baseline = digest(output)
        accepted(run(sox, '--report', root/'quiet.json', '--auto-headroom',
                     quiet, output), 'quiet measured')
        assert digest(output) == baseline, 'measured mode changed an already safe programme'
        assert all(e['headroom_applied_db'] == 0 for e in encoders(root/'quiet.json'))
        print('PASS non-clipping signal is bit-identical with measured headroom')

        # Explicit effect policy must match the implicit effect and its plan.
        explicit = root/'explicit.dsf'
        accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error',
                     hot, '-r', 'dsd64', explicit, 'pcmdsd', '2822400'), 'explicit')
        implicit = root/'implicit.dsf'
        accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error',
                     hot, '-r', 'dsd64', implicit), 'implicit')
        assert digest(explicit) == digest(implicit), 'explicit pcmdsd differs from implicit'
        accepted(run(sox, '--dsd-mode', 'legacy', '--auto-headroom',
                     '--dsd-clip', 'error', hot, '-r', 'dsd64', explicit),
                 'legacy mode must use qualified encoder')
        assert digest(explicit) == digest(implicit), 'legacy mode bypassed the qualified path'
        print('PASS explicit, implicit and legacy-mode DSD routes agree')

        # PCM-rate spooling means even an unseekable WAV input can be scanned.
        pipe = root/'stdin.dsf'
        accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error',
                     '-t', 'wav', '-', pipe, stdin=hot.read_bytes()), 'streaming input')
        assert digest(pipe) == digest(implicit), 'pipe scan does not match regular input'
        print('PASS non-seekable input and exact finite tail replay')

        # Scheduler EOF handling: empty, single-sample, and non-block-aligned
        # streams must give identical native bitstreams on both paths.
        for frames in (0, 1, 2, 3, 7, 63, 257):
            short = root/'short.wav'
            with wave.open(str(short), 'wb') as file:
                file.setnchannels(1)
                file.setsampwidth(3)
                file.setframerate(44100)
                file.writeframes(b'\x00\x00\x00' * frames)
            plain = root/'short-plain.dsf'
            scan = root/'short-scan.dsf'
            accepted(run(sox, short, '-r', 'dsd64', plain), f'short-{frames}')
            accepted(run(sox, '--auto-headroom', short, '-r', 'dsd64', scan),
                     f'scan-{frames}')
            assert digest(plain) == digest(scan), f'short EOF mismatch at {frames}'
        print('PASS empty, single-frame and non-block-aligned EOF streams')

        # Both high-rate v2 profiles also have to clip and measure actual
        # inter-sample overloads, not just accept silent input.
        short = root/'highrate-hot.wav'
        with wave.open(str(hot), 'rb') as src:
            params = src.getparams()
            raw = src.readframes(900)
        with wave.open(str(short), 'wb') as dst:
            dst.setparams(params)
            dst.writeframes(raw)
        for rate in ('dsd512', 'dsd1024'):
            report = root/'highrate.json'
            output = root/'highrate.dsf'
            accepted(run(sox, '--report', report, short, '-r', rate, output),
                     f'{rate} warn')
            assert int(json.loads(report.read_text())['clipping']['encoder_interpolation']) > 0
            accepted(run(sox, '--report', report, '--auto-headroom',
                         '--dsd-clip', 'error', short, '-r', rate, output),
                     f'{rate} strict auto')
            assert all(int(e['clipped_interpolated_samples']) == 0
                       for e in encoders(report))
        print('PASS overload clipping and measured correction at DSD512/1024')

        # All flows receive one gain even when the scheduler uses multiple
        # threads; report enabled/disabled must never change their decisions.
        concurrent = root/'omp.dsf'
        accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error', hot,
                     '-r', 'dsd64', concurrent, threads='4'), 'threaded')
        assert digest(concurrent) == digest(implicit), 'thread count changed DSD decisions'
        print('PASS multithreaded effect flow is deterministic')

        for options in (('--headroom', '-2'), ('--headroom', 'nan'),
                        ('--headroom', '1x'), ('--headroom', '121'),
                        ('--headroom', '1', '--auto-headroom'),
                        ('--auto-headroom', '--auto-headroom')):
            declined(run(sox, *options, hot, root/'bad.dsf'), str(options))
            assert not (root/'bad.dsf').exists()
        for options, src, suffix in (
                (('--headroom','2'), quiet, '.wav'),
                (('--auto-headroom',), quiet, '.wav'),
                (('--headroom','2'), implicit, '.dsf')):
            declined(run(sox, *options, src, root/('inapplicable'+suffix)), 'non-encoder')
            assert not (root/('inapplicable'+suffix)).exists()
        print('PASS invalid/inapplicable options reject before output creation')

    print('Loud encode acceptance PASS')


if __name__ == '__main__':
    main()
