#!/usr/bin/env python3
"""Offline subprocess lifecycle regression for URL inputs (no network).

Validates that a downloader's final status, not merely its audio bytes,
governs SoX conversion completion. Uses only the stdlib.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave


def verify(sox: Path):
    results = []
    with tempfile.TemporaryDirectory(prefix='sox-dsd-url-child-') as scratch:
        root = Path(scratch)
        sample = root / 'input.wav'
        with wave.open(str(sample), 'wb') as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            handle.writeframes(b'\0\0' * 512)
        child = root / 'wget'
        child.write_text('''#!/bin/sh
if [ "$1" = "--version" ]; then exit 0; fi
last=''
for arg in "$@"; do last="$arg"; done
printf '%s' "$last" > "$SYNC_CAPTURE_URL"
if [ "$SYNC_STATUS" != 'empty' ]; then cat "$SYNC_SAMPLE" || exit 71; fi
if [ "$SYNC_STATUS" = 'empty' ]; then exit 8; fi
exit "$SYNC_STATUS"
''')
        child.chmod(0o755)
        env = os.environ.copy()
        env.update(PATH=str(root) + os.pathsep + env.get('PATH', ''),
                   SYNC_SAMPLE=str(sample), SYNC_CAPTURE_URL=str(root/'captured'))
        url = "http://offline.invalid/o'hare $branch;&x.wav"
        for status in ('0', '9', 'empty'):
            env['SYNC_STATUS'] = status
            out = root / f'out-{status}.wav'
            command = [str(sox.resolve()), url, str(out)]
            got = subprocess.run(command, env=env, cwd=root, text=True,
                                 capture_output=True, timeout=20)
            if (root/'captured').read_text() != url:
                raise AssertionError(f'URL argv was changed by shell parsing: {status}')
            if status == '0':
                if got.returncode != 0 or not out.exists():
                    raise AssertionError(f'valid downloader failed: {got.stderr[-600:]}')
                with wave.open(str(out), 'rb') as wf:
                    if wf.getnframes() != 512:
                        raise AssertionError('valid downloader changed audio length')
            else:
                if got.returncode == 0 or out.exists():
                    raise AssertionError(f'failed downloader published output: {status}')
                if status == 'empty' and 'Server issued an error response' not in got.stderr:
                    raise AssertionError(f'empty download misdiagnosed: {got.stderr[-600:]}')
            results.append({'downloader_exit': status, 'sox_exit': got.returncode,
                            'output_exists': out.exists(),
                            'url_argv_preserved': True})

        # A valid finite WAV can have container metadata *after* the audio
        # payload. Closing the downloader after the last sample, instead of
        # draining to real EOF, causes self-induced SIGPIPE and false failure.
        # Use 8 MiB so the trailing RIFF chunk cannot fit into the pipe.
        import struct
        trailer = root/'with-trailing-junk.wav'
        original = sample.read_bytes()
        extra = b'JUNK' + struct.pack('<I', 8 * 1024 * 1024) + b'Z'*(8 * 1024 * 1024)
        trailer.write_bytes(original[:4] + struct.pack('<I', len(original) + len(extra) - 8)
                            + original[8:] + extra)
        with wave.open(str(trailer), 'rb') as wf:
            if wf.getnframes() != 512 or wf.readframes(512) != b'\0\0'*512:
                raise AssertionError('trailing-metadata fixture is not a valid WAV')
        env['SYNC_SAMPLE'] = str(trailer)
        local_output = root/'local-trailer.wav'
        local = subprocess.run([str(sox.resolve()),str(trailer),str(local_output)],
                               env=env, cwd=root, capture_output=True,text=True,timeout=30)
        if local.returncode != 0:
            raise AssertionError('local RIFF/JUNK fixture was rejected')
        for status in ('0','9'):
            env['SYNC_STATUS'] = status
            out = root/f'trailer-{status}.wav'
            got = subprocess.run([str(sox.resolve()),'http://offline.invalid/trailer.wav',
                                  str(out)],env=env,cwd=root,capture_output=True,
                                 text=True, timeout=35)
            if status == '0':
                if got.returncode or not out.is_file() or out.read_bytes()!=local_output.read_bytes():
                    raise AssertionError('valid RIFF/JUNK URL rejected or PCM changed: '
                                         +got.stderr[-800:])
            elif not got.returncode or out.exists():
                raise AssertionError('RIFF/JUNK downloader exit 9 was accepted')
            results.append({'source':'RIFF/WAV 8MiB trailing JUNK',
                            'downloader_exit':status,'sox_exit':got.returncode,
                            'output_exists':out.exists(),
                            'decoded_output_matches_local':status=='0'})
        env['SYNC_SAMPLE'] = str(sample)

        # A completed native DSD stream must not be marked successful in the
        # structured report until the downloader's final exit status is known.
        dsf = root/'source.dsf'
        synth = subprocess.run([str(sox.resolve()), '-n', '-r', '2822400',
                                '-c', '1', str(dsf), 'synth', '0.02', 'sine',
                                '1000'], cwd=root, text=True,
                               capture_output=True, timeout=20)
        if synth.returncode or not dsf.is_file():
            raise AssertionError(f'DSF test fixture generation failed: {synth.stderr[-600:]}')
        env['SYNC_SAMPLE'] = str(dsf)
        for status in ('0', '9'):
            env['SYNC_STATUS'] = status
            out = root/f'native-{status}.dsf'
            report = root/f'native-{status}.json'
            got = subprocess.run([str(sox.resolve()), '--dsd-mode', 'native',
                                  '--dsd-report', str(report),
                                  'http://offline.invalid/native.dsf', str(out)],
                                 env=env, cwd=root, capture_output=True,
                                 text=True, timeout=30)
            if not report.is_file():
                raise AssertionError('DSD report not published for ' + status)
            receipt = json.loads(report.read_text())
            wanted = 'complete' if status == '0' else 'failed'
            if receipt['status'] != wanted:
                raise AssertionError(f'downloader exit {status} produced DSD '
                                     f'report status {receipt["status"]}, expected {wanted}')
            if status == '0' and (got.returncode != 0 or not out.is_file()):
                raise AssertionError('successful DSD downloader failed')
            if status == '9' and (got.returncode == 0 or out.exists()):
                raise AssertionError('failed DSD downloader published output')
            results.append({'source': 'DSD/native',
                            'downloader_exit': status,
                            'sox_exit': got.returncode,
                            'output_exists': out.exists(),
                            'report_status': receipt['status']})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({'status':'PASS', 'cases':verify(args.sox)}, sort_keys=True))


if __name__ == '__main__':
    main()
