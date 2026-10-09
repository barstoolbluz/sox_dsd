#!/usr/bin/env python3
"""Exercise P07 output-error propagation on real regular files and /dev/full.

The test uses RLIMIT_FSIZE for deterministic active-write and buffered-close
errors.  SIGXFSZ is ignored only in the child so EFBIG reaches the CLI.  The
fixture is independently constructed; no SoX writer produces its input.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import wave

try:
    import resource
except ImportError:
    resource = None

from reference import fixtures


def invoke(sox: Path, argv: list[str], limit: int | None = None):
    def set_limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)

    return subprocess.run([str(sox), '-S', '-D', *map(str, argv)],
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, 'OMP_NUM_THREADS': '1'},
                          preexec_fn=set_limit if limit is not None else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    opts = parser.parse_args()
    sox = opts.sox.resolve()
    rows = []

    def record(name, valid, cp, **observations):
        rows.append(dict(name=name, status='pass' if valid else 'fail',
                         exit_code=cp.returncode, **observations))
        if not valid:
            print('FAIL', name, cp.stderr[-700:], flush=True)

    with tempfile.TemporaryDirectory(prefix='p07-output-errors-') as root:
        d = Path(root)
        src = d / 'input.dsf'
        src.write_bytes(fixtures.make_dsf(fixtures.bits(262144, 1, 'random')))
        small = d / 'small.dsf'
        small.write_bytes(fixtures.make_dsf(fixtures.bits(4096, 1, 'random')))

        # Active flow must recognize a short sox_write() even if the format's
        # error code is cleared later. These inputs force nonzero PCM blocks.
        if (resource is not None and hasattr(resource, 'RLIMIT_FSIZE')
                and hasattr(signal, 'SIGXFSZ')):
            for limit in (512, 1000, 4096, 5000, 16000, 20000):
                dest = d / ('active-%d.wav' % limit)
                cp = invoke(sox, [src, dest, 'dsdpcm', '88200'], limit)
                saw = 'output write failed' in cp.stderr
                removed = not dest.exists()
                complete = 'Done.' in cp.stderr
                record('active_write_limit_%d' % limit,
                       cp.returncode != 0 and saw and removed and not complete,
                       cp, short_write_diagnostic=saw, output_removed=removed,
                       reported_completion=complete)

            # Near the logical stream end, input EOF must not hide a fatal
            # output status from the final partially written block.
            complete = d / 'control-full.wav'
            cp = invoke(sox, [src, complete, 'dsdpcm', '88200'])
            if cp.returncode != 0 or not complete.is_file():
                raise RuntimeError('could not generate control WAV for final-block test')
            full_size = complete.stat().st_size
            complete.unlink()
            dest = d / 'last-block.wav'
            cp = invoke(sox, [src, dest, 'dsdpcm', '88200'], full_size - 128)
            fatal = ('output write failed' in cp.stderr or
                     'finalization failed' in cp.stderr)
            removed = not dest.exists()
            complete_message = 'Done.' in cp.stderr
            record('near_final_block_write_limit',
                   cp.returncode != 0 and fatal and removed and
                   not complete_message, cp, failure_diagnostic=fatal,
                   output_removed=removed, reported_completion=complete_message)

            # This small decoded stream fits stdio buffering. The write
            # succeeds during flow but its deferred flush must fail at close.
            dest = d / 'buffered-finalization.wav'
            cp = invoke(sox, [small, dest, 'dsdpcm', '88200'], 128)
            final = 'finalization failed' in cp.stderr
            short = 'output write failed' in cp.stderr
            removed = not dest.exists()
            complete = 'Done.' in cp.stderr
            record('buffered_regular_finalization_limit',
                   cp.returncode != 0 and final and not short and removed and
                   not complete, cp, finalization_diagnostic=final,
                   short_write_diagnostic=short, output_removed=removed,
                   reported_completion=complete)
        else:
            rows.append(dict(name='rlimit_failure_controls', status='unrun',
                             reason='RLIMIT_FSIZE/SIGXFSZ unavailable'))

        # Never create or unlink this device. A failed close must not remove
        # a character device, even when it was supplied as an output path.
        full = Path('/dev/full')
        try:
            before = full.stat()
        except OSError:
            before = None
        if before is not None and stat.S_ISCHR(before.st_mode):
            cp = invoke(sox, [small, '-t', 'wav', full, 'dsdpcm', '88200'])
            try:
                after = full.stat()
                retained = (stat.S_ISCHR(after.st_mode) and
                            after.st_rdev == before.st_rdev and
                            after.st_ino == before.st_ino)
            except OSError:
                retained = False
            final = 'finalization failed' in cp.stderr
            complete = 'Done.' in cp.stderr
            record('character_device_finalization',
                   cp.returncode != 0 and final and retained and not complete,
                   cp, finalization_diagnostic=final, device_preserved=retained,
                   reported_completion=complete)
        else:
            rows.append(dict(name='character_device_finalization',
                             status='unrun', reason='/dev/full character device unavailable'))

        # Ordinary EOF, intentional trim, and unrelated PCM conversions must
        # continue to exit 0 with readable files and complete sample counts.
        native = d / 'native.wav'
        cp = invoke(sox, [small, native, 'dsdpcm', '88200'])
        try:
            with wave.open(str(native), 'rb') as wav:
                length = wav.getnframes()
                payload = wav.readframes(length)
            valid = length == 128 and len(payload) >= 128 * 2
        except (OSError, EOFError, wave.Error):
            valid = False
            length = -1
        record('ordinary_dsd_eof', cp.returncode == 0 and valid, cp,
               decoded_frames=length)

        trimmed = d / 'trimmed.wav'
        cp = invoke(sox, [small, trimmed, 'dsdpcm', '88200', 'trim', '0', '0.001'])
        try:
            with wave.open(str(trimmed), 'rb') as wav:
                trimmed_frames = wav.getnframes()
            valid = 0 < trimmed_frames < 128
        except (OSError, EOFError, wave.Error):
            valid = False
            trimmed_frames = -1
        record('intentional_trim_eof', cp.returncode == 0 and valid, cp,
               output_frames=trimmed_frames)

        pcm_in, pcm_out = d / 'pcm-in.wav', d / 'pcm-out.wav'
        samples = b''.join(struct.pack('<h', (i * 109) % 65536 - 32768)
                           for i in range(1024))
        with wave.open(str(pcm_in), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(samples)
        cp = invoke(sox, [pcm_in, pcm_out])
        try:
            with wave.open(str(pcm_out), 'rb') as wav:
                valid = (wav.getnframes() == 1024 and
                         wav.getnchannels() == 1 and wav.readframes(1024) == samples)
        except (OSError, EOFError, wave.Error):
            valid = False
        record('unrelated_pcm_copy', cp.returncode == 0 and valid, cp,
               pcm_bytes_identical=valid)

    failed = [r['name'] for r in rows if r['status'] == 'fail']
    unrun = [r['name'] for r in rows if r['status'] == 'unrun']
    summary = dict(schema='sox.dsd.p07.output-failures.v1', cases=len(rows),
                   pass_count=sum(r['status'] == 'pass' for r in rows),
                   fail_count=len(failed), unrun_count=len(unrun),
                   failures=failed, unrun=unrun, results=rows)
    opts.results.mkdir(parents=True, exist_ok=True)
    dst = opts.results / 'output-failures.json'
    tmp = dst.with_suffix('.tmp')
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    tmp.replace(dst)
    print('P07 output failures:', summary['pass_count'], 'pass,',
          summary['fail_count'], 'fail,', summary['unrun_count'], 'unrun')
    return 1 if failed else 2 if any(r['name'] == 'rlimit_failure_controls'
                                  for r in rows if r['status'] == 'unrun') else 0


if __name__ == '__main__':
    raise SystemExit(main())
