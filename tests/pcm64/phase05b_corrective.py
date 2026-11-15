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


def ordinary_pipe_input_gate(sox, root):
    """Trimmed libc popen inputs must keep their ordinary SIGPIPE semantics.

    A finite producer should exit cleanly rather than complain of a broken
    pipe. A producer which loops despite write errors must not hold pclose
    after the requested trim has completed. Bound and reap the entire test
    process group if a regression returns.
    """
    if os.name != 'posix' or not hasattr(os, 'killpg'):
        return 'NOT_RUN: POSIX process-group signals unavailable'
    large = root / 'pipe-cat-source.wav'
    with wave.open(str(large), 'wb') as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(8000)
        sink.writeframes(b'\0\0' * 300000)

    def bounded(args):
        child = subprocess.Popen([str(sox), *args], cwd=root,
                                 stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        try:
            return child.communicate(timeout=6), child.returncode
        except subprocess.TimeoutExpired as exc:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            raise AssertionError(f'pipe input failed to stop after trim: {args!r}') from exc

    for explicit32 in (False, True):
        options = ['--precision', '32'] if explicit32 else []
        out = root / f'pipe-endless-{explicit32}.wav'
        (stdout, stderr), rc = bounded([
            *options, '-t', 'raw', '-r', '8000', '-e', 'signed',
            '-b', '16', '-c', '1',
            '|while :; do printf AAAAAAAA 2>/dev/null; done',
            str(out), 'trim', '0', '0.1'])
        demand(rc == 0 and not stdout and out.is_file(),
               f'endless pipe did not exit normally: {rc} {stderr[-250:]!r}')
        with wave.open(str(out), 'rb') as source:
            demand(source.getnframes() == 800,
                   'trimmed pipe produced an incorrect number of frames')

        target = root / f'pipe-finite-{explicit32}.wav'
        (stdout, stderr), rc = bounded([
            *options, '|cat pipe-cat-source.wav', str(target),
            'trim', '0', '0.01'])
        demand(rc == 0 and not stdout and target.is_file() and
               b'cat: write error' not in stderr and b'Broken pipe' not in stderr,
               f'pipe producer inherited ignored SIGPIPE: {rc} {stderr[-250:]!r}')
    return 'PASS'


def stdout_input_alias_gate(sox, root):
    """An input opened via fd 1 may not become a JSON report destination."""
    if os.name != 'posix':
        return 'NOT_RUN: POSIX descriptor aliases unavailable'
    aliases = [path for path in ('/dev/stdout', '/dev/fd/1')
               if Path(path).exists()]
    if not aliases:
        return 'NOT_RUN: no /dev/stdout or /dev/fd/1'
    source = root / 'stdout-input-keep.wav'
    with wave.open(str(source), 'wb') as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(48000)
        sink.writeframes(b'\x02\x01' * 400)
    original = source.read_bytes()
    for alias in aliases:
        for report in ('-', *aliases):
            for bad_options in ([], ['-r', 'abc'],
                                ['--comment-file', str(root / 'no-comment.txt')]):
                output = root / 'stdout-input-output.wav'
                output.unlink(missing_ok=True)
                with source.open('r+b') as sink:
                    result = subprocess.run([
                        str(sox), '--precision', '64', '--report', report,
                        '-t', 'wav', alias, *bad_options, str(output)],
                        stdin=subprocess.DEVNULL, stdout=sink,
                        stderr=subprocess.PIPE, timeout=7)
                demand(result.returncode != 0 and
                       source.read_bytes() == original and not output.exists(),
                       f'report damaged fd-1 audio input: {alias} {report} '
                       f'{bad_options} rc={result.returncode} '
                       f'{result.stderr[-200:]!r}')
    return 'PASS'


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



def return4_stdout_report_gate(sox, root):
    """No report may overwrite an input, effect sink or option file."""
    source = root / 'return4-source.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(b'\x02\x01' * 128)
    aliases = ('-', '/dev/stdout') if Path('/dev/stdout').exists() else ('-',)
    if os.name == 'posix':
        for target in aliases:
            for early in (False, True):
                original = source.read_bytes()
                output = root / 'return4-output.wav'
                output.unlink(missing_ok=True)
                with source.open('r+b') as shared:
                    result = subprocess.run([str(sox), '--precision', '64',
                        '--report', target, '-t', 'wav', '-',
                        *(['-r', 'abc'] if early else []), str(output)],
                        stdin=shared, stdout=shared, stderr=subprocess.PIPE,
                        timeout=7)
                demand(result.returncode != 0 and source.read_bytes() == original
                       and not output.exists(),
                       'stdin/stdout same inode leaked JSON or changed the audio input')
        # -p (SoX format over stdin) can also be the input operand, and
        # must not write a failure report back into that same file.
        sox_stream = call(sox, ['-R', '-n', '-p', 'synth', '0.01', 'sine', '440'])
        demand(sox_stream.returncode == 0 and sox_stream.stdout,
               'could not construct the SoX-pipe input fixture')
        pipe_source = root / 'return4-pipe-input.sox'
        pipe_source.write_bytes(sox_stream.stdout)
        for target in aliases:
            for option in ('-p', '--pipe'):
                original = pipe_source.read_bytes()
                with pipe_source.open('r+b') as shared:
                    result = subprocess.run([str(sox), '--precision', '64',
                        '--report', target, option, '-r', 'abc',
                        str(root / 'return4-pipe-dest.wav')],
                        stdin=shared, stdout=shared, stderr=subprocess.PIPE,
                        timeout=7)
                demand(result.returncode != 0 and
                       pipe_source.read_bytes() == original,
                       f'{option} input shared with stdout was overwritten')
        # Distinct stdin/stdout is legitimate: stdout may carry JSON, even
        # when the native runner subsequently refuses the stdin WAV reader.
        result = subprocess.run([str(sox), '--precision', '64', '--report', '-',
            '-t', 'wav', '-', str(root / 'return4-stdin-dest.wav')],
            input=source.read_bytes(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=7)
        demand(result.stdout.startswith(b'{') and
               json.loads(result.stdout)['status'] in ('complete','refused','failed'),
               'separate stdin incorrectly blocks the stdout report')

    # These paths are not audio endpoints. The effect or the file-valued
    # option owns stdout, so the reporting channel must remain unused.
    for target in aliases:
        result = call(sox, ['--precision', '64', '--report', target,
                            source, '-n', 'noiseprof', '-'])
        demand(result.returncode != 0 and b'sox.dsd.conversion' not in result.stdout,
               'noiseprof stdout was contaminated by JSON')
        if Path('/dev/stdout').exists():
            for option in (['--comment-file', '/dev/stdout'],
                           ['--comment-file=/dev/stdout']):
                comment = root / 'return4-comment.txt'
                comment.write_bytes(b'comment\n')
                original = comment.read_bytes()
                output = root / 'return4-comment-output.wav'
                output.unlink(missing_ok=True)
                with comment.open('r+b') as descriptor:
                    result = call(sox, ['--precision', '64', '--report', target,
                        *option, source, output], stdout=descriptor)
                demand(result.returncode != 0 and comment.read_bytes() == original
                       and not output.exists(),
                       'file-valued --comment-file consumed report JSON')

    for flag in ('--help', '--version', '--help-dsd'):
        result = call(sox, ['--precision', '64', '--report',
                            root / 'missing-dir' / 'report.json', flag])
        demand(result.returncode != 0 and b'--report publication failed' in result.stderr,
               f'{flag} reported success after report publication failed')
    return 'PASS'



def return4_option_discovery_gate(sox, root):
    """Accepted getopt prefixes and SOX_OPTS must get the same safe report."""
    source = root / 'return4-options-source.wav'
    with wave.open(str(source), 'wb') as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(48000)
        sink.writeframes(b'\x01\x00' * 400)
    original = source.read_bytes()
    output = root / 'return4-options-output.wav'
    missing = root / 'nonexistent-report-directory' / 'report.json'

    def execute(args, *, env_opts='', stdin=None, stdout=subprocess.PIPE):
        return subprocess.run([str(sox), *map(str, args)], stdin=stdin,
                              stdout=stdout, stderr=subprocess.PIPE,
                              env={**os.environ, 'SOX_OPTS': env_opts}, timeout=8)

    # Shared fd 0/fd 1: full spelling, accepted prefixes, and = syntax
    # must refuse both a complete command and an error before audio opens.
    for report_args in (['--report', '-'], ['--repo', '-'],
                        ['--repor', '-'], ['--repo=-']):
        for bad in ([], ['-r', 'abc']):
            source.write_bytes(original)
            output.unlink(missing_ok=True)
            with source.open('r+b') as stream:
                cp = execute(['--prec=64', *report_args, '-t', 'wav', '-',
                              *bad, output], stdin=stream, stdout=stream)
            demand(cp.returncode != 0 and source.read_bytes() == original
                   and not output.exists(),
                   f'accepted report spelling damaged shared input: '
                   f'{report_args} {bad} {cp.returncode} {cp.stderr[-150:]!r}')
    for bad in ([], ['-c', 'abc']):
        source.write_bytes(original)
        output.unlink(missing_ok=True)
        with source.open('r+b') as stream:
            cp = execute(['-t', 'wav', '-', *bad, output],
                         env_opts='--precision 64 --report -',
                         stdin=stream, stdout=stream)
        demand(cp.returncode != 0 and source.read_bytes() == original
               and not output.exists(),
               f'SOX_OPTS report damaged shared input: {bad} {cp.stderr[-150:]!r}')

    # Explicit fd 1 input aliases are unsafe even when the audio output is a
    # separate file. Test their early-error route as well as normal parsing.
    for alias in ('/dev/stdout', '/dev/fd/1'):
        if not Path(alias).exists():
            continue
        for bad in ([], ['-c', 'abc']):
            source.write_bytes(original)
            output.unlink(missing_ok=True)
            with source.open('r+b') as stream:
                cp = execute(['--prec', '64', '--repor', '-', '-t', 'wav',
                              alias, *bad, output], stdout=stream)
            demand(cp.returncode != 0 and source.read_bytes() == original
                   and not output.exists(),
                   f'fd1 input alias accepted: {alias} {bad}')

    if Path('/dev/stdout').exists():
        for option in ('--comment-file', '--effects-file'):
            for env_owned in (False, True):
                comment = root / 'return4-option-keep.txt'
                comment.write_bytes(b'original comment\n')
                output.unlink(missing_ok=True)
                env_opts = ('--prec 64 --repo=- ' + option + ' /dev/stdout'
                            if env_owned else '')
                args = ([source, output] if env_owned else
                        ['--prec=64', '--repo=-', option, '/dev/stdout',
                         source, output])
                with comment.open('r+b') as stream:
                    cp = execute(args, env_opts=env_opts, stdout=stream)
                demand(cp.returncode != 0 and
                       comment.read_bytes() == b'original comment\n' and
                       not output.exists(),
                       f'{option} via {"environment" if env_owned else "CLI"} '
                       f'accepted report collision: {cp.stderr[-150:]!r}')

    # noiseprof - owns stdout; options from SOX_OPTS must not publish into it.
    for env_owned in (False, True):
        args = ([source, '-n', 'noiseprof', '-'] if env_owned else
                ['--prec', '64', '--repo=-', source, '-n', 'noiseprof', '-'])
        cp = execute(args, env_opts='--prec 64 --repo=-' if env_owned else '')
        demand(cp.returncode != 0 and b'sox.dsd.conversion' not in cp.stdout,
               f'noiseprof stdout received report JSON: {env_owned}')

    # A refused stdout report must also make early success exits nonzero.
    if Path('/dev/stdout').exists():
        for early in ('--help', '--version'):
            owned = root / 'return4-early-stdout-owned.txt'
            owned.write_bytes(b'original comment\n')
            with owned.open('r+b') as stream:
                cp = execute(['--prec', '64', '--repo=-',
                              '--comment-file', '/dev/stdout', early],
                             stdout=stream)
            demand(cp.returncode != 0 and
                   b'sox.dsd.conversion' not in owned.read_bytes(),
                   f'{early} hid a refused stdout report')

    # Early success exits must propagate failed report publication from every
    # accepted spelling and from either source of option arguments.
    for prec in (['--precision', '64'], ['--prec', '64'], ['--prec=64']):
        for report in (['--report', missing], ['--repo', missing],
                       [f'--repor={missing}']):
            for early in ('--help', '--version'):
                cp = execute([*prec, *report, early])
                demand(cp.returncode != 0 and
                       b'--report publication failed' in cp.stderr,
                       f'early {early} lost publication failure: {prec} {report}')
    for early in ('--help', '--version'):
        for env_opts, args in (
                (f'--prec 64 --repo {missing}', [early]),
                ('--prec=64', ['--repo', missing, early]),
                (f'--report {missing}', ['--prec', '64', early])):
            cp = execute(args, env_opts=env_opts)
            demand(cp.returncode != 0 and
                   b'--report publication failed' in cp.stderr,
                   f'{early} ignored report in SOX_OPTS: {env_opts}')

    # Parser diagnostics survive when report discovery follows a bad value.
    for bad, reason in ((['-r', 'abc'], 'rate'),
                        (['-c', 'abc'], 'channels'),
                        (['--comment-file', root / 'missing-comment'], 'comment file')):
        for report_first in (False, True):
            report = ['--repo=-']
            args = (['--prec', '64', *report, source, *bad, output]
                    if report_first else
                    ['--prec', '64', source, *bad, *report, output])
            cp = execute(args)
            demand(cp.returncode != 0, f'bad option accepted: {bad}')
            receipt = json.loads(cp.stdout)
            demand(receipt['status'] == 'failed' and
                   reason in (receipt.get('failure_reason') or ''),
                   f'early error report lost: {bad} {report_first} {receipt}')

    # A separately connected stdout may still carry JSON, and command-line
    # options still override SOX_OPTS. The historical --rep is replay-gain.
    for env_opts in ('', '--prec=64 --repo=-'):
        output.unlink(missing_ok=True)
        cp = execute(['--prec', '64', '--repo=-', source, output], env_opts=env_opts)
        receipt = json.loads(cp.stdout)
        demand(receipt['status'] in ('complete', 'failed', 'refused') and
               source.read_bytes() == original,
               f'separate stdout incorrectly blocked: {env_opts}')
    older = root / 'return4-env-report.json'
    newer = root / 'return4-cli-report.json'
    cp = execute(['--prec=64', '--repo', newer, source, '-r', 'abc', output],
                 env_opts=f'--precision 32 --report {older}')
    demand(cp.returncode != 0 and not older.exists() and newer.exists() and
           json.loads(newer.read_text())['status'] == 'failed',
           'command line did not override SOX_OPTS precision/report')
    cp = execute(['--prec', '64', '--rep', 'track', '--version'])
    demand(cp.returncode == 0 and b'sox.dsd.conversion' not in cp.stdout,
           '--rep replay-gain alias was mistaken for --report')
    return 'PASS'


def return4_effect_path_alias_gate(sox, root):
    """An early parser failure must not overwrite an effect-owned pathname."""
    source = root / 'return4-effect-source.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b'\x01\x00' * 300)
    original = b'original noise profile - preserve these bytes\n'
    for case in ('same', 'hardlink', 'same-env', 'hardlink-env', 'separate'):
        profile = root / f'return4-effect-{case}-profile.txt'
        report = root / f'return4-effect-{case}-report.json'
        output = root / f'return4-effect-{case}-output.wav'
        profile.write_bytes(original)
        if case.startswith('hardlink'):
            os.link(profile, report)
        elif case.startswith('same'):
            report = profile
        env_report = case.endswith('-env')
        options = (['-r', 'abc', source, output, 'noiseprof', profile]
                   if env_report else
                   ['--precision', '64', '--report', report, '-r', 'abc',
                    source, output, 'noiseprof', profile])
        env = {**os.environ, 'SOX_OPTS':
               f'--precision 64 --report {report}' if env_report else ''}
        result = subprocess.run([str(sox), *map(str, options)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=8)
        demand(result.returncode != 0 and not output.exists(),
               f'effect alias {case} accepted invalid rate or created audio: '
               f'{result.returncode} {result.stderr[-200:]!r}')
        demand(profile.read_bytes() == original,
               f'effect alias {case} overwrote existing profile')
        if case == 'separate':
            demand(report.is_file(), 'safe early report was not published')
            receipt = json.loads(report.read_text())
            demand(receipt['status'] == 'failed' and
                   'rate' in (receipt.get('failure_reason') or ''),
                   f'nonconflicting early report malformed: {receipt}')
        elif report != profile:
            demand(report.read_bytes() == original,
                   f'effect alias {case} overwrote hard-linked report')
    return 'PASS'



def return5_report_carrier_gate(sox, root):
    """Report publication cannot borrow any option/effect/audio carrier.

    The same cases run with and without native arithmetic; they exercise
    admission and early errors, not the native PCM processing path.
    """
    source=root/'return5-source.wav'
    with wave.open(str(source),'wb') as sink:
        sink.setnchannels(1);sink.setsampwidth(2);sink.setframerate(48000)
        sink.writeframes(b'\x11\x00'*500)
    original=b'original file owned by an option or effect\n'

    def execute(args, *, env='', stdin=None, stdout=subprocess.PIPE):
        return subprocess.run([str(sox),*map(str,args)],stdin=stdin,stdout=stdout,
                              stderr=subprocess.PIPE,timeout=10,
                              env={**os.environ,'SOX_OPTS':env})

    # File-valued options and effects, direct aliases, hardlinks and symlinks.
    for family in ('comment', 'effects', 'noisered', 'noiseprof',
                   'spectrogram'):
        for alias in ('same', 'hardlink', 'symlink'):
            owned=root/f'return5-{family}-{alias}.txt'
            owned.write_bytes(original)
            report=owned
            if alias!='same':
                report=root/f'return5-report-{family}-{alias}.json'
                report.unlink(missing_ok=True)
                if alias=='hardlink':os.link(owned,report)
                else:report.symlink_to(owned.name)
            output=root/f'return5-{family}-{alias}-out.wav'
            output.unlink(missing_ok=True)
            if family=='comment':
                args=[source,'--comment-file',owned,output]
            elif family=='effects':
                args=['--effects-file',owned,source,output]
            elif family=='noisered':
                args=[source,output,'noisered',owned,'0.2']
            elif family=='noiseprof':
                args=[source,'-n','noiseprof',owned]
            else:
                args=[source,'-n','spectrogram','-o',owned]
            cp=execute(['--prec','64','--repo',report,*args])
            demand(cp.returncode!=0 and owned.read_bytes()==original and
                   not output.exists(),
                   f'{family}/{alias} damaged an owned file or opened audio: '
                   f'{cp.returncode} {cp.stderr[-180:]!r}')

    # Option precedence and file references carried through SOX_OPTS.
    for owner in ('comment','effects','noisered'):
        owned=root/f'return5-env-{owner}.txt';owned.write_bytes(original)
        output=root/f'return5-env-{owner}-out.wav';output.unlink(missing_ok=True)
        if owner=='comment':
            env=f'--precision 64 --report {owned} --comment-file {owned}'
            args=[source,output]
        elif owner=='effects':
            owned.write_text('noiseprof -\n')
            env='--precision 64 --report - --effects-file '+str(owned)
            args=[source,'-n']
        else:
            env='--precision 64 --report '+str(owned)
            args=['-r','abc',source,output,'noisered',owned,'0.2']
        cp=execute(args,env=env)
        demand(cp.returncode!=0 and not output.exists() and
               owned.read_bytes()==(b'noiseprof -\n' if owner=='effects' else original) and
               b'sox.dsd.conversion' not in cp.stdout,
               f'SOX_OPTS {owner} collision was not refused')

    # Failure before the effect starts must not write the report into it.
    for alias in ('same','hardlink','env'):
        owned=root/f'return5-early-{alias}.prof';owned.write_bytes(original)
        report=owned
        if alias=='hardlink':
            report=root/'return5-early-hardlink-report.json'
            report.unlink(missing_ok=True);os.link(owned,report)
        output=root/f'return5-early-{alias}-out.wav';output.unlink(missing_ok=True)
        env=f'--prec 64 --repo {report}' if alias=='env' else ''
        head=[] if alias=='env' else ['--prec','64','--repo',report]
        cp=execute([*head,'-r','abc',source,output,'noiseprof',owned],env=env)
        demand(cp.returncode!=0 and owned.read_bytes()==original and
               not output.exists(),f'early {alias} report overwrote effect file')

    # Nonconflicting early error is still reported, with its real reason.
    profile=root/'return5-nonconflicting-profile.prof';profile.write_bytes(original)
    report=root/'return5-safe-failure.json';report.unlink(missing_ok=True)
    output=root/'return5-safe-error-out.wav';output.unlink(missing_ok=True)
    cp=execute(['--prec','64','--repo',report,'-r','abc',source,output,
                'noiseprof',profile])
    demand(cp.returncode!=0 and not output.exists() and
           profile.read_bytes()==original and
           json.loads(report.read_text())['status']=='failed',
           'nonconflicting early report failed or altered profile')

    # Implicit stdout and effects-file stdout must not carry report JSON.
    effectfile=root/'return5-implicit-effects.txt'
    for content in ('noiseprof -\n','noiseprof\n','spectrogram -o -\n'):
        effectfile.write_text(content)
        for options in ([source,'-n','noiseprof'],
                        ['--effects-file',effectfile,source,'-n']):
            if options[-1]=='noiseprof' and content!='noiseprof -\n':continue
            cp=execute(['--prec','64','--repo=-',*options])
            demand(cp.returncode!=0 and not cp.stdout.startswith(b'{'),
                   f'implicit effect wrote report JSON to stdout: {options} {content}')

    # Explicit descriptor aliases are the same stdout carrier as report '-'.
    # They must not become an escape hatch for option/effect-owned output.
    for effect in (['noiseprof','/dev/stdout'],
                   ['noiseprof','/dev/fd/1'],
                   ['spectrogram','-o','/dev/stdout']):
        cp=execute(['--prec','64','--repo=-',source,'-n',*effect])
        demand(cp.returncode!=0 and not cp.stdout.startswith(b'{'),
               f'explicit stdout alias reached report carrier: {effect}')

    # A bare '-' is not necessarily stdout. remix interprets it as a channel
    # selector, and noisered/fir read stdin, not stdout.
    prof=root/'return5-valid-noise.prof'
    cp=execute([source,'-n','noiseprof',prof]);demand(cp.returncode==0,'noise profile fixture failed')
    for effect,stdin in ((['remix','-'],None),(['noisered','-','0.2'],prof.open('rb'))):
        try:
            output=root/'return5-safe-effect-out.wav';output.unlink(missing_ok=True)
            cp=execute(['--precision','64','--report','-',source,output,*effect],stdin=stdin)
            receipt=json.loads(cp.stdout)
            demand(b'--report conflicts' not in cp.stderr and
                   receipt['status'] in ('complete','refused','failed') and
                   (output.exists() if cp.returncode==0 else not output.exists()),
                   f'non-stdout effect operand was incorrectly rejected: {effect} {cp.stderr[-200:]!r}')
        finally:
            if stdin:stdin.close()

    # A file input borrowed by stdin (even through effect '-') must be
    # protected when stdout and stdin are the same underlying regular file.
    before=prof.read_bytes()
    with prof.open('r+b') as stream:
        cp=execute(['--prec','64','--repo=-',source,'-n','noisered','-','0.2'],
                   stdin=stream,stdout=stream)
    demand(cp.returncode!=0 and prof.read_bytes()==before,
           'effect stdin/stdout shared descriptor was overwritten')

    # SOX_OPTS --effects-file may be overridden; do not treat inactive effect
    # arguments as carriers. The report may use stdout independently.
    safe_effects=root/'return5-override-effective.txt'
    safe_effects.write_text('vol 0.5\n')
    risky_effects=root/'return5-override-inactive.txt'
    risky_effects.write_text('noiseprof -\n')
    cp=execute(['--prec','64','--repo=-','--effects-file',safe_effects,source,
                root/'return5-override-out.wav'],env=f'--effects-file {risky_effects}')
    demand(b'--report conflicts' not in cp.stderr and cp.stdout.startswith(b'{'),
           'overridden SOX_OPTS effects-file caused false stdout collision')

    # Ordinary --plan retains pre-Phase05B exit behavior; strict64 plan and
    # report retain the publication-failure obligation.
    for closed in (False,True):
        if closed:
            cp=subprocess.run([str(sox),'--plan',str(source),str(root/'return5-plan.wav')],
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                              preexec_fn=lambda:os.close(1),timeout=10,
                              env={**os.environ,'SOX_OPTS':''})
        else:
            with open('/dev/full','wb') as full:
                cp=execute(['--plan',source,root/'return5-plan.wav'],stdout=full)
        demand(cp.returncode==0,
               f'ordinary --plan changed its stdout error exit: {closed} {cp.returncode}')
    with open('/dev/full','wb') as full:
        cp=execute(['--precision','64','--plan',source,root/'return5-strict-plan.wav'],stdout=full)
    demand(cp.returncode!=0,'strict64 plan concealed a publication failure')
    return 'PASS'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    parser.add_argument('--oracle', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='p05b-corrective-') as tmp:
        root = Path(tmp)
        for gate in (ordinary_pipe_input_gate, stdout_input_alias_gate,
                     return4_stdout_report_gate, return4_option_discovery_gate,
                     return4_effect_path_alias_gate,
                     return5_report_carrier_gate):
            status = gate(args.sox.resolve(), root)
            demand(status in ('PASS',) or status.startswith('NOT_RUN:'),
                   f'{gate.__name__}: {status}')
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
