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
            output = root / f'out-{native}.dsf'
            report = root / 'run.json'
            rate = f'dsd{native}'
            planned = json.loads(accepted(run(sox, '--plan', '--auto-headroom',
                                              hot, '-r', rate, output), 'plan').stdout)
            assert planned['policy']['headroom_mode'] == 'auto'
            assert planned['policy']['headroom_db'] is None
            assert not output.exists(), '--plan opened an audio output'

            default = accepted(run(sox, hot, '-r', rate, output), 'default warn')
            assert b'clipped' in default.stderr, 'loud default did not warn'
            default_hash = digest(output)
            accepted(run(sox, '--report', report, hot, '-r', rate, output),
                     'default with report')
            record = json.loads(report.read_text())
            clipped = [int(e['clipped_interpolated_samples'])
                       for e in record['processing']['encoder']]
            assert clipped[0] > 0 and clipped[1] == 0, clipped
            assert int(record['clipping']['encoder_interpolation']) == sum(clipped)
            assert any('interpolation clipped' in w for w in record['warnings'])
            assert digest(output) == default_hash, 'report changed default clipping'
            accepted(run(sox, '--headroom', '0', hot, '-r', rate, output),
                     'zero fixed headroom')
            assert digest(output) == default_hash, '--headroom 0 changed the audio'
            assert declined(run(sox, '--dsd-clip', 'error', hot, '-r', rate,
                                output), 'strict').returncode == 2
            assert not output.exists(), 'failed strict conversion left a partial file'

            accepted(run(sox, '--report', report, '--headroom', '2',
                         hot, '-r', rate, output), 'fixed 2dB')
            fixed = encoders(report)
            assert int(json.loads(report.read_text())['clipping']['encoder_interpolation']) == 0
            assert all(int(e['clipped_interpolated_samples']) == 0 for e in fixed)
            assert all(abs(e['headroom_applied_db'] - 2) < 1e-10 for e in fixed)
            assert digest(output) != default_hash, 'fixed headroom changed no audio'

            accepted(run(sox, '--report', report, '--auto-headroom',
                         '--dsd-clip', 'error', hot, '-r', rate, output), 'auto strict')
            auto = encoders(report)
            assert all(int(e['clipped_interpolated_samples']) == 0 for e in auto)
            cuts = [e['headroom_applied_db'] for e in auto]
            assert abs(cuts[0] - cuts[1]) < 1e-12, 'channels received different gains'
            assert 0.01 < cuts[0] < 2., f'headroom was not minimal: {cuts}'
            peak = max(e['peak_modulator_input'] for e in auto)
            assert abs(peak - 0.5) < 1e-9, f'measured cut was not tight: {peak}'
            auto_hash = digest(output)
            accepted(run(sox, '--auto-headroom', '--dsd-clip', 'error',
                         hot, '-r', rate, output), 'auto without report')
            assert digest(output) == auto_hash, 'report changed headroom audio'
            assert digest(hot) == source_hash, 'scanning modified the input'
            print(f'PASS DSD{native}: clip/warn, refusal, fixed, stereo measured, report invariance')

        output = root/'quiet.dsf'
        accepted(run(sox, quiet, output), 'quiet ordinary')
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
