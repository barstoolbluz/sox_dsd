#!/usr/bin/env python3
"""P05B-D01/D02/D03: small, reproducible preflight/layout/empty-input gate."""
import argparse
import json
import os
import select
import shutil
import signal
import time
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/dsd/reference'))
import fixtures
sys.path.insert(0, str(ROOT / 'tests/pcm64'))
from decode import decode_case, parse_wav


def demand(cond, reason):
    if not cond:
        raise AssertionError(reason)


def call(sox, args, *, env=None, stdout=subprocess.PIPE, timeout=45):
    return subprocess.run([str(sox), *map(str, args)], stdout=stdout,
                          stderr=subprocess.PIPE, env={**os.environ, **(env or {})},
                          timeout=timeout)


def output_args(src, dest):
    return [src, '-r', '96000', '-b', '64', '-e', 'floating-point',
            '-t', 'wav', dest]


def planned(sox, args, *, stdout=subprocess.PIPE):
    result = call(sox, ['--precision', '64', '--plan', *args], stdout=stdout)
    demand(result.returncode == 0, f'plan failed: {result.stderr[-500:]!r}')
    if stdout == subprocess.PIPE:
        return json.loads(result.stdout)


def route(plan):
    return plan['precision']['actual_route']


def put_source(root, kind, channels, n):
    path = root / f'{kind}-{channels}-{n}.{kind}'
    path.write_bytes(getattr(fixtures, 'make_' + kind)(
        fixtures.bits(n, channels, 'distinct'), fixtures.DSD64))
    return path


def stdout_gate(sox, root, src):
    args = output_args(src, '-')
    for mode, prefill, acceptable in [('wb', b'', True),
                                      ('ab', b'', False),
                                      ('ab', b'EXISTING', False),
                                      ('wb', b'EXISTING', False)]:
        # A nonempty non-append descriptor is a distinct refused case.
        if prefill and mode == 'wb':
            mode = 'r+b'
        dest = root / ('stdout-' + src.suffix[1:] + '-' + mode + '-' + str(len(prefill)))
        dest.write_bytes(prefill)
        with dest.open(mode) as fd:
            if prefill and mode == 'r+b':
                fd.seek(0, 2)
            result = call(sox, ['--precision', '64', '--plan', *args], stdout=fd)
        if acceptable:
            demand(result.returncode == 0 and route(json.loads(dest.read_text())) ==
                   'native-binary64-pcm', f'{src} stdout {mode}: plan mismatch')
        else:
            # A plan aimed at the audio descriptor is allowed to publish JSON
            # on the descriptor. Its native route must nevertheless refuse.
            if not prefill:
                plan = json.loads(dest.read_text())
                demand(route(plan) == 'refused-before-output' and
                       plan['precision']['runner_available'] is False,
                       f'{src} stdout {mode}: false acceptance')
            else:
                demand(result.returncode == 0 and
                       route(json.loads(dest.read_bytes()[len(prefill):])) == 'refused-before-output',
                       'nonempty append plan falsely accepts')
        dest.write_bytes(prefill)
        report = root / ('receipt-' + src.suffix[1:] + '-' + mode + '-' + str(len(prefill)) + '.json')
        with dest.open(mode) as fd:
            if prefill and mode == 'r+b':
                fd.seek(0, 2)
            result = call(sox, ['--precision', '64', '--report', report, *args], stdout=fd)
        if acceptable:
            demand(result.returncode == 0 and dest.stat().st_size > 44,
                   f'{src} stdout {mode}: valid run failed {result.stderr!r}')
            demand(json.loads(report.read_text())['status'] == 'complete',
                   'successful stdout run reported failure')
        else:
            demand(result.returncode != 0 and dest.read_bytes() == prefill,
                   'refused stdout committed audio bytes')
            receipt = json.loads(report.read_text())
            demand(receipt['status'] == 'refused' and receipt['executable'] is False and
                   receipt['failure_reason'], f'false stdout refusal receipt: {receipt}')
    pipe_plan = planned(sox, args)
    demand(route(pipe_plan) == 'native-binary64-pcm', 'known-length stdout pipe rejected')
    run = call(sox, ['--precision', '64', *args])
    demand(run.returncode == 0 and run.stdout.startswith(b'RIFF'),
           f'known-length stdout pipe failed: {run.stderr[-250:]!r}')
    # The stream must not contain both audio and JSON, even via /dev/stdout.
    for plan_only in (False, True):
        result = call(sox, ['--precision', '64', *(['--plan'] if plan_only else []),
                            '--report', '/dev/stdout', *args])
        demand(result.returncode != 0 and not result.stdout.startswith(b'RIFF'),
               'audio/report stdout alias accepted')
    separate = root / ('report-separate-' + src.suffix[1:] + '.wav')
    args = output_args(src, separate)
    result = call(sox, ['--precision', '64', '--report', '/dev/stdout', *args])
    demand(result.returncode == 0 and separate.exists() and
           json.loads(result.stdout)['status'] == 'complete',
           'report on stdout and audio in file should succeed')
    result = call(sox, ['--precision', '64', '--plan', '--report', '/dev/stdout', *args])
    demand(result.returncode == 0 and
           route(json.loads(result.stdout)) == 'native-binary64-pcm',
           'separate audio destination rejected while report goes to stdout')


def empty_pcm_stdout_gate(sox, root):
    """A zero-frame WAV has a known, not an unknown, native frame count."""
    for channels in (1, 2):
        for frames in (0, 4):
            source = root / f'pcm16-{channels}-{frames}.wav'
            with wave.open(str(source), 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)
                wav.setframerate(96000)
                wav.writeframes(b'\0' * (frames * channels * 2))
            args = output_args(source, '-')
            plan = planned(sox, args)
            demand(route(plan) == 'native-binary64-pcm' and
                   plan['precision']['runner_available'] is True,
                   f'known {frames}-frame PCM refused on stdout pipe ({channels}ch)')
            result = call(sox, ['--precision', '64', *args])
            expected_size = 94 + frames * channels * 8
            demand(result.returncode == 0 and
                   len(result.stdout) == expected_size and
                   result.stdout.startswith(b'RIFF'),
                   f'known PCM stdout failed ({channels}ch, {frames} frames): '
                   f'{result.stderr[-300:]!r}')
            # Existing append-mode restrictions still apply to empty inputs.
            if frames == 0:
                stdout_gate(sox, root, source)


def layout_gate(sox, root, oracle=None):
    for channels in (1, 2):
        src = put_source(root, 'wsd', channels, 4096)
        dst = root / f'wsd-{channels}-native.wav'
        legacy = root / f'wsd-{channels}-default.wav'
        args = output_args(src, dst)
        demand(route(planned(sox, args)) == 'native-binary64-pcm', 'WSD plan refused')
        p = call(sox, ['--precision', '64', *args])
        demand(p.returncode == 0, f'WSD strict64 failed: {p.stderr[-500:]!r}')
        p = call(sox, output_args(src, legacy))
        demand(p.returncode == 0, f'WSD default failed: {p.stderr[-500:]!r}')
        data, mask = parse_wav(dst, 139, channels, 96000)  # rounded 4096*96000/2822400
        demand(mask == 0 and len(data) == 139*channels*8,
               'WSD writer invented roles or altered channel count')
        if oracle:
            decode_case(sox, oracle, root, f'oracle-wsd-{channels}', src,
                        96000, 'mastering-v2', 'preserve',
                        report=False, speaker_mask=0)
    src = put_source(root, 'dff', 6, 4096)
    args = output_args(src, root / 'dff-loss.wav')
    result = call(sox, ['--precision', '64', *args])
    demand(result.returncode != 0 and not Path(args[-1]).exists(),
           'unpermitted named DFF layout was accepted')
    opts = ['--dsd-layout-loss', 'warn']
    demand(route(planned(sox, [*opts, *args])) == 'native-binary64-pcm',
           'permitted DFF layout plan rejected')
    result = call(sox, ['--precision', '64', *opts, *args])
    demand(result.returncode == 0, f'permitted DFF failed: {result.stderr[-500:]!r}')
    _, mask = parse_wav(Path(args[-1]), 139, 6, 96000)
    demand(mask == 0, 'permitted DFF layout should have unspecified WAV mask')
    if oracle:
        decode_case(sox, oracle, root, 'oracle-dff-loss-warn', src,
                    96000, 'mastering-v2', 'preserve', report=False,
                    other_options=tuple(opts), speaker_mask=0)
    for roles, expected in [('FL,FR', 0x3), ('FC,FL,FR,LFE,SL,SR', 0x60f)]:
        ch = roles.count(',') + 1
        source = put_source(root, 'dsf' if ch == 2 else 'dff', ch, 4096)
        dest = root / f'roles-{ch}.wav'
        result = call(sox, ['--precision', '64', '--dsd-layout', roles,
                            *output_args(source, dest)])
        demand(result.returncode == 0, f'named layout failed: {result.stderr[-500:]!r}')
        _, mask = parse_wav(dest, 139, ch, 96000)
        demand(mask == expected, f'named speaker mask {mask:#x} != {expected:#x}')


def packed_gate(sox, root):
    for kind, channels, count in [('dsf', 1, 0), ('dsf', 2, 1), ('dsf', 2, 7),
                                  ('dsf', 2, 9), ('dsf', 2, 256), ('dsf', 2, 4096),
                                  ('dsf', 2, 32769), ('dsf', 2, 100000),
                                  ('dff', 2, 4096)]:
        src = put_source(root, kind, channels, count)
        outputs = []
        for packed in (0, 1):
            dest = root / f'packed-{kind}-{channels}-{count}-{packed}.wav'
            cp = call(sox, ['--precision', '64', *output_args(src, dest)],
                      env={'SOX_DSD_PACKED_INPUT': str(packed)})
            demand(cp.returncode == 0, f'packed={packed} count={count}: {cp.stderr[-400:]!r}')
            outputs.append(dest.read_bytes())
        demand(outputs[0] == outputs[1], f'packed/expanded bytes differ: {kind} {count}')
        if count == 0:
            _, mask = parse_wav(root / f'packed-{kind}-{channels}-{count}-1.wav',
                                0, channels, 96000)
    # Reporting intentionally deactivates packed reader; do not confuse this
    # with the no-report packed-on comparison above.
    src = put_source(root, 'dsf', 1, 0)
    receipt = root / 'empty-with-report.json'
    cp = call(sox, ['--precision', '64', '--report', receipt,
                    *output_args(src, root / 'empty-with-report.wav')],
              env={'SOX_DSD_PACKED_INPUT': '1'})
    demand(cp.returncode == 0 and json.loads(receipt.read_text())['status'] == 'complete',
           'empty DSD reporting path failed')


def fifo_call_with_reader(sox, args, fifo):
    """Hold a real FIFO reader open while draining output as SoX runs."""
    fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    try:
        child = subprocess.Popen([str(sox), *map(str, args)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        received = bytearray()
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if select.select([fd], [], [], 0.02)[0]:
                    try:
                        chunk = os.read(fd, 65536)
                    except BlockingIOError:
                        chunk = b''
                    if chunk:
                        received.extend(chunk)
                if child.poll() is not None:
                    # The writer has closed: drain any final buffered JSON.
                    while True:
                        try:
                            chunk = os.read(fd, 65536)
                        except BlockingIOError:
                            break
                        if not chunk:
                            break
                        received.extend(chunk)
                    break
            else:
                raise AssertionError('SoX waited despite a connected FIFO reader')
            stdout, stderr = child.communicate(timeout=2)
            return child.returncode, stdout, stderr, bytes(received)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
    finally:
        os.close(fd)


def fifo_return_gate(sox, root):
    """P05B return: neither plan nor early option failures block on FIFO."""
    fifo = root / 'report.fifo'
    os.mkfifo(fifo)
    pcm = root / 'fifo-pcm.wav'
    with wave.open(str(pcm), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(96000)
        wav.writeframes(b'\0\0\0\0' * 128)
    dsf = put_source(root, 'dsf', 2, 511)
    bad_comment = root / 'missing-comment-file.txt'
    failures = [(['-r', 'abc'], 'rate'),
                (['-c', 'abc'], 'channels'),
                (['--comment-file', str(bad_comment)], 'comment file')]
    for src in (pcm, dsf):
        output = root / f'fifo-{src.suffix[1:]}-output.wav'
        planned_args = ['--precision', '64', '--plan', '--report', fifo,
                        *output_args(src, output)]
        run_args = ['--precision', '64', '--report', fifo,
                    *output_args(src, output)]
        for args, reason in [(planned_args, '--report'),
                             (run_args, '--report'),
                             *[(['--precision', '64', '--report', fifo,
                                 src, *bad_args, output], error)
                               for bad_args, error in failures]]:
            result = call(sox, args, timeout=4)
            demand(result.returncode != 0 and result.stdout == b'' and
                   reason.encode() in result.stderr and not output.exists(),
                   f'unread FIFO blocked, wrote audio or lost cause: '
                   f'{src} {args} {result.returncode} {result.stderr[-250:]!r}')
        # Planning never creates the audio output; JSON uses only the
        # retained FIFO descriptor and is emitted exactly once.
        rc, stdout, stderr, payload = fifo_call_with_reader(sox, planned_args, fifo)
        demand(rc == 0 and stdout == b'' and not output.exists() and
               route(json.loads(payload)) == 'native-binary64-pcm',
               f'connected FIFO plan failed: {src}, {stderr[-300:]!r}')
        for bad_args, reason in failures:
            rc, stdout, stderr, payload = fifo_call_with_reader(
                sox, ['--precision', '64', '--report', fifo,
                      src, *bad_args, output], fifo)
            doc = json.loads(payload)
            demand(rc != 0 and stdout == b'' and not output.exists() and
                   doc['status'] == 'failed' and
                   reason in (doc.get('failure_reason') or ''),
                   f'connected FIFO early error lacks truthful JSON: {src} {bad_args} {doc}')
        rc, stdout, stderr, payload = fifo_call_with_reader(sox, run_args, fifo)
        doc = json.loads(payload)
        demand(rc == 0 and stdout == b'' and output.exists() and
               doc['status'] == 'complete',
               f'connected FIFO normal report failed: {src} {stderr[-300:]!r} {doc}')
        output.unlink()


def cli_preflight_gate(sox, root):
    """Capability-independent CLI guards (also in --disable-native-f64 builds)."""
    pcm = root / 'cli-preflight-pcm.wav'
    with wave.open(str(pcm), 'wb') as sink:
        sink.setnchannels(2)
        sink.setsampwidth(2)
        sink.setframerate(48000)
        sink.writeframes(b'\0\0\0\0' * 96)
    # Report aliases all refer to the same stdout descriptor.  An explicit
    # stdin source does not make that descriptor an audio output when another
    # file operand follows it.
    report_stdout = ('-',) + tuple(
        alias for alias in ('/dev/stdout', '/dev/fd/1') if Path(alias).exists())
    pipe = root / 'cli-preflight-pcm.sox'
    generated = call(sox, [pcm, '-p'], timeout=5)
    demand(generated.returncode == 0 and generated.stdout.startswith(b'.SoX'),
           f'cannot prepare valid -p input: {generated.stderr[-200:]!r}')
    pipe.write_bytes(generated.stdout)
    absent_comment = root / 'missing-stdin-comment.txt'
    for stdin_name, stdin_file, input_args in (
            ('wav-stdin', pcm, ['-t', 'wav', '-']),
            ('sox-pipe', pipe, ['-p'])):
        for target in report_stdout:
            for bad_args, reason in (
                    (['-r', 'abc'], 'rate'),
                    (['-c', 'abc'], 'channels'),
                    (['--comment-file', str(absent_comment)], 'comment file')):
                output = root / ('stdin-report-' + stdin_name + '.wav')
                with stdin_file.open('rb') as fd:
                    cp = subprocess.run(
                        [str(sox), '--precision', '64', '--report', target,
                         *input_args, *bad_args, str(output)],
                        stdin=fd, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=5)
                demand(cp.returncode == 1 and not output.exists(),
                       f'{stdin_name} {target} {bad_args}: '
                       f'early failure did not exit 1: {cp.stderr[-200:]!r}')
                try:
                    receipt = json.loads(cp.stdout)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise AssertionError(
                        f'{stdin_name} {target} {bad_args}: '
                        f'missing failed JSON report ({cp.stdout[:100]!r})') from exc
                demand(receipt['status'] == 'failed' and
                       receipt['executable'] is False and
                       reason in (receipt.get('failure_reason') or ''),
                       f'{stdin_name} {target} {bad_args}: '
                       f'wrong early failure report: {receipt}')
    # A terminal -n is an output, not an indication that the earlier
    # stdin - or -p operand writes audio to the report's stdout descriptor.
    for stdin_name, stdin_file, input_args in (
            ('wav-stdin', pcm, ['-t', 'wav', '-']),
            ('sox-pipe', pipe, ['-p'])):
        for target in report_stdout:
            for bad_args, reason in (
                    (['-r', 'abc'], 'rate'),
                    (['-c', 'abc'], 'channels'),
                    (['--comment-file', str(absent_comment)], 'comment file')):
                with stdin_file.open('rb') as fd:
                    cp = subprocess.run(
                        [str(sox), '--precision', '64', '--report', target,
                         *input_args, *bad_args, '-n'],
                        stdin=fd, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=5)
                demand(cp.returncode == 1,
                       f'null-output stdin early error did not exit 1: '
                       f'{stdin_name} {target} {bad_args}: {cp.stderr[-150:]!r}')
                try:
                    receipt = json.loads(cp.stdout)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise AssertionError(
                        f'null-output stdin early report missing: '
                        f'{stdin_name} {target} {bad_args} '
                        f'{cp.stdout[:100]!r}') from exc
                demand(receipt['status'] == 'failed' and
                       receipt['executable'] is False and
                       reason in (receipt.get('failure_reason') or ''),
                       f'null-output stdin early report incorrect: {receipt}')
    # An explicit filename that resolves to stdout is unsafe even when a
    # subsequent regular-file output is identifiable.  Unlike bare - or -p,
    # its position must not make the early JSON observer writable.
    for audio_alias in ('/dev/stdout', '/dev/fd/1'):
        if not Path(audio_alias).exists():
            continue
        for target in report_stdout:
            for bad_args in (['-r', 'abc'], ['-c', 'abc'],
                             ['--comment-file', str(absent_comment)]):
                output = root / 'explicit-stdout-audio-never.wav'
                cp = call(sox, ['--precision', '64', '--report', target,
                                '-t', 'wav', audio_alias, *bad_args, output],
                          timeout=5)
                demand(cp.returncode == 1 and cp.stdout == b'' and
                       not output.exists(),
                       f'explicit stdout audio emitted JSON on early error: '
                       f'{audio_alias} {target} {bad_args} '
                       f'{cp.returncode} {cp.stdout[:90]!r}')
    for target in report_stdout:
        # Parsing -r/-c/-v can consume the input filename, leaving a single
        # '-' operand; that is still the intended audio sink, not a report.
        for opt, arg in (('-r', str(pcm)), ('-c', str(pcm)), ('-v', str(pcm))):
            cp = call(sox, ['--precision', '64', '--report', target,
                            opt, arg, '-t', 'wav', '-'], timeout=5)
            demand(cp.returncode == 1 and cp.stdout == b'',
                   f'early {opt} report reached audio stdout: {cp.returncode} '
                   f'{cp.stdout[:80]!r} {cp.stderr[-150:]!r}')
            cp = call(sox, ['--precision', '64', '--report', target,
                            opt, str(pcm), '-p'], timeout=5)
            demand(cp.returncode == 1 and cp.stdout == b'',
                   f'early {opt} JSON reached -p audio output: '
                   f'{cp.returncode} {cp.stdout[:80]!r}')
            # Positive control: report stdout is allowed when no operand
            # names that stream, even on an early option error.
            cp = call(sox, ['--precision', '64', '--report', target, pcm,
                            opt, 'abc', root / 'cli-early-never.wav'], timeout=5)
            receipt = json.loads(cp.stdout)
            demand(cp.returncode != 0 and receipt['status'] == 'failed',
                   f'separate early report not delivered: {opt} {cp.stderr!r}')
    if not hasattr(os, 'mkfifo'):
        return 'NOT_RUN: host has no named FIFO support'
    fifo = root / 'cli-preflight.fifo'
    os.mkfifo(fifo)
    dest = root / 'cli-preflight-out.wav'
    unread = [['--precision', '64', '--plan', '--report', fifo,
               *output_args(pcm, dest)]]
    failures = [('-r', 'abc', 'rate'), ('-c', 'abc', 'channels'),
                ('--comment-file', str(root / 'absent-comment.txt'), 'comment file')]
    for opt, value, reason in failures:
        unread.append(['--precision', '64', '--report', fifo,
                       pcm, opt, value, dest])
    for argv in unread:
        cp = call(sox, argv, timeout=4)
        demand(cp.returncode != 0 and cp.stdout == b'' and not dest.exists(),
               f'unread FIFO blocked or admitted: {argv} {cp.returncode}')
    for opt, value, reason in failures:
        rc, stdout, stderr, payload = fifo_call_with_reader(
            sox, ['--precision', '64', '--report', fifo,
                  pcm, opt, value, dest], fifo)
        receipt = json.loads(payload)
        demand(rc != 0 and stdout == b'' and receipt['status'] == 'failed' and
               reason in (receipt['failure_reason'] or '') and not dest.exists(),
               f'connected FIFO early {opt} lost failure receipt: {rc} {receipt}')
    # Pause exactly after SoX has admitted and fdopen'd the FIFO writer.
    # The reader closes while publication is still pending: a reverted
    # early SIGPIPE handler must now fail this test deterministically.
    if sys.platform.startswith('linux'):
        cc = shutil.which('cc')
        demand(cc is not None, 'Linux FIFO regression requires the build compiler')
        shim = root / 'fifo-report-stop.so'
        compiled = subprocess.run([cc, '-shared', '-fPIC', '-o', str(shim),
                                   str(ROOT / 'tests/pcm64/fifo_report_stop.c'), '-ldl'],
                                  capture_output=True, timeout=20)
        demand(compiled.returncode == 0,
               f'FIFO disconnect test shim failed to compile: {compiled.stderr!r}')
        reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        child = subprocess.Popen([str(sox), '--precision', '64',
                                  '--report', str(fifo), str(pcm),
                                  '-r', 'abc', str(dest)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env={**os.environ, 'LD_PRELOAD': str(shim),
                                      'SOX_PCM64_STOP_REPORT_FIFO': '1'})
        try:
            deadline = time.monotonic() + 5
            stopped = False
            while time.monotonic() < deadline:
                pid, state = os.waitpid(child.pid, os.WNOHANG | os.WUNTRACED)
                if pid and os.WIFSTOPPED(state):
                    stopped = True
                    break
                if pid and (os.WIFEXITED(state) or os.WIFSIGNALED(state)):
                    break
                time.sleep(0.002)
            demand(stopped, 'report writer never reached test disconnect point')
            os.close(reader)
            reader = -1
            os.kill(child.pid, signal.SIGCONT)
            stdout, stderr = child.communicate(timeout=5)
            demand(child.returncode == 1 and stdout == b'' and not dest.exists(),
                   f'disconnected early report terminated by signal or blocked: '
                   f'{child.returncode} {stderr[-200:]!r}')
        finally:
            if reader >= 0:
                os.close(reader)
            if child.poll() is None:
                child.kill()
                child.communicate()
    # If the FIFO reader disappears during early-error JSON publication,
    # the process must report ordinary failure, never die from SIGPIPE.
    for _ in range(20):
        reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        child = subprocess.Popen([str(sox), '--precision', '64',
                                  '--report', str(fifo), str(pcm),
                                  '-r', 'abc', str(dest)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if select.select([reader], [], [], 0.002)[0]:
                    try:
                        if os.read(reader, 1):
                            break
                    except BlockingIOError:
                        pass
                if child.poll() is not None:
                    break
            os.close(reader)
            reader = -1
            stdout, stderr = child.communicate(timeout=4)
            demand(child.returncode == 1 and not stdout and not dest.exists(),
                   f'early FIFO reader-disconnect killed process: {child.returncode} '
                   f'{stderr[-120:]!r}')
        finally:
            if reader >= 0:
                os.close(reader)
            if child.poll() is None:
                child.kill()
                child.communicate()
    return 'PASS'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    parser.add_argument('--oracle', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='p05b-corrective-') as tmp:
        root = Path(tmp)
        status = cli_preflight_gate(args.sox.resolve(), root)
        demand(status == 'PASS', status)
        if args.preflight_only:
            print('PASS: Phase05B CLI preflight and FIFO error gates (native F64 not required)')
            return
        dsf = put_source(root, 'dsf', 2, 511)
        stdout_gate(args.sox.resolve(), root, dsf)
        pcm = root / 'source-pcm.wav'
        # Standalone float64 WAV, not prepared through the binary64 path.
        data = struct.pack('<8d', *([0.125, -0.5] * 4))
        pcm.write_bytes(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVE' +
                        b'fmt ' + struct.pack('<IHHIIHH', 16, 3, 2, 96000,
                                               96000*16, 16, 64) +
                        b'data' + struct.pack('<I', len(data)) + data)
        stdout_gate(args.sox.resolve(), root, pcm)
        empty_pcm_stdout_gate(args.sox.resolve(), root)
        fifo_return_gate(args.sox.resolve(), root)
        layout_gate(args.sox.resolve(), root, args.oracle.resolve() if args.oracle else None)
        packed_gate(args.sox.resolve(), root)
    print('PASS: P05B-D01/D02/D03, zero-frame PCM stdout and FIFO return, CLI guards')


if __name__ == '__main__':
    main()
