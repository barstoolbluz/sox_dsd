"""P01 writer vectors and native-bit acceptance; truth never comes from SoX."""
from __future__ import annotations

import json
import hashlib
import pathlib
import tempfile

from . import fixtures, verify


def timeline(words, frames):
    # The three hand-selected bytes repeat; this does not use the writer's
    # packing algorithm or the fixture constructor's completion routine.
    return tuple(bytes(int(format(word[i // 8 % len(word)], '08b')[i % 8])
                       for i in range(frames)) for word in words)


def expected_audio(words, frames):
    complete, residual = divmod(frames, 8)
    packed = bytearray(word[i % len(word)] for i in range(complete) for word in words)
    if residual:
        keep = (0xff << (8 - residual)) & 0xff
        packed.extend((word[complete % len(word)] & keep) | (0x69 & (keep ^ 0xff))
                      for word in words)
    return bytes(packed)


def check_output(raw, words, frames):
    nch = len(words)
    decoded = verify.decode_dff(raw)  # Independent, strict enclosing-span walker.
    top, sub = decoded['top'], decoded['prop']
    expected = expected_audio(words, frames)
    verify.check([c['tag'] for c in top] == ['FVER', 'PROP', 'DSD '], 'top-level order')
    verify.check([c['tag'] for c in sub] == ['FS  ', 'CHNL', 'CMPR'], 'property order')
    verify.check(top[0]['payload_size'] == 4 and raw[28:32] == bytes.fromhex('01050000'), 'FVER')
    verify.check(top[1]['payload_size'] == 66 + 4 * nch, 'PROP physical spans')
    verify.check(sub[-1]['payload_size'] == 19 and sub[-1]['pad'] == 1, 'CMPR external pad')
    audio = decoded['audio']
    verify.check(audio['payload_start'] == 122 + 4 * nch, 'hand-derived audio offset')
    verify.check(audio['payload_size'] == len(expected), 'completed cluster count')
    verify.check(audio['pad'] == len(expected) % 2, 'audio pad count')
    verify.check(raw[audio['payload_start']:audio['payload_end']] == expected, 'program/completion bytes')
    verify.check(len(raw) == 122 + 4 * nch + len(expected) + len(expected) % 2, 'physical file length')
    verify.check(decoded['frames'] == (frames + 7) // 8 * 8, 'completed frame count')
    verify.check(decoded['channels'] == nch and decoded['rate'] == fixtures.DSD64, 'signal')
    source = timeline(words, frames)
    verify.check(all(ch[:frames] == source[i] for i, ch in enumerate(decoded['timeline'])),
                 'source bits through the logical endpoint')
    return decoded


def hand_checks(catalog):
    for bit, field in ((0, 'zero_source_tail_hex_for_residual_1_to_7'),
                       (1, 'one_source_tail_hex_for_residual_1_to_7')):
        words = [bytes([255 * bit])]
        verify.check([expected_audio(words, r).hex() for r in range(1, 8)] == catalog[field],
                     'hand-derived residual constants')
    words = [bytes.fromhex(catalog['source_words_msb'][0])]
    verify.check(''.join(map(str, timeline(words, 9)[0])) == catalog['mono_nine_frame_source_bits'],
                 'hand-derived nine-frame source')
    verify.check(expected_audio(words, 9).hex() == catalog['mono_nine_frame_expected_audio_hex'],
                 'hand-derived nine-frame completion')


def run_vectors(runner):
    catalog = json.loads((pathlib.Path(__file__).resolve().parents[1] /
                          'fixtures/p01_writer_vectors.json').read_text())
    hand_checks(catalog)
    words = [bytes.fromhex(s) for s in catalog['source_words_msb']]
    observations = []
    with tempfile.TemporaryDirectory(prefix='dsd-p01-vectors-') as td:
        work = pathlib.Path(td)
        for nch in range(1, 7):
            for frames in catalog['frames']:
                source = timeline(words[:nch], frames)
                input_file = work / 'bits.bin'
                input_file.write_bytes(bytes(v for frame in zip(*source) for v in frame))
                for cap in catalog['call_frames']:
                    for perturb in catalog['allocator_perturbations']:
                        output = work / 'out.dff'
                        p = runner.invoke([runner.args.probe, 'write-bits', output, input_file, nch, cap],
                                          env={'MALLOC_PERTURB_': str(perturb)})
                        verify.check(p['exit'] == 0 and json.loads(p['stdout'])['write_ok'], 'writer command')
                        raw = output.read_bytes()
                        decoded = check_output(raw, words[:nch], frames)
                        observations.append(dict(channels=nch, source_frames=frames, call_frames=cap,
                            malloc_perturb=perturb, output_frames=decoded['frames'],
                            audio_bytes=decoded['audio']['payload_size'], output_sha256=runner_sha(raw)))
        # Hand-pinned zero/one tails complement the mixed and distinct-channel
        # vectors, including completion of one byte for EACH channel.
        for bit in (0, 1):
            for nch in (1, 6):
                for frames in range(1, 8):
                    input_file = work / 'bits.bin'
                    input_file.write_bytes(bytes([bit]) * (frames * nch))
                    output = work / 'out.dff'
                    p = runner.invoke([runner.args.probe, 'write-bits', output, input_file, nch, 1],
                                      env={'MALLOC_PERTURB_': '85'})
                    verify.check(p['exit'] == 0, 'constant-bit writer command')
                    decoded = check_output(output.read_bytes(), [bytes([255 * bit])] * nch, frames)
                    observations.append(dict(channels=nch, source_frames=frames, constant_bit=bit,
                                             output_frames=decoded['frames'], status='pass'))
    return dict(status='pass', vector_cases=len(observations), residuals=list(range(1, 8)),
                channels=list(range(1, 7)), checks=observations,
                oracle='hand-selected bytes, hand-pinned tails and independent strict chunk walker')


def runner_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def cross_format(runner):
    catalog = json.loads((pathlib.Path(__file__).resolve().parents[1] /
                          'fixtures/p01_writer_vectors.json').read_text())
    words = [bytes.fromhex(s) for s in catalog['source_words_msb']]
    checks = []
    with tempfile.TemporaryDirectory(prefix='dsd-p01-chronology-') as td:
        work = pathlib.Path(td)
        # >=64 frames avoids the separately named P02 reader minimum defect.
        for nch in (1, 2, 6):
            for frames in (65, 72, 73):
                source_bits = timeline(words[:nch], frames)
                source = work / 'source.dsf'
                source.write_bytes(fixtures.make_dsf(source_bits))
                dff, back = work / 'out.dff', work / 'back.dsf'
                p = runner.invoke([runner.args.sox, '-D', source, dff], env={'MALLOC_PERTURB_': '85'})
                verify.check(p['exit'] == 0, 'DSF to DFF native command')
                written = check_output(dff.read_bytes(), words[:nch], frames)
                args = [runner.args.sox, '-D', dff]
                if nch == 6 and int(runner.args.phase[1:]) >= 4:
                    # P04 rejects a false DFF surround-angle claim.  Retain
                    # the P01 numerical bit oracle, but make the previously
                    # implicit side/back assignment explicit at the bridge.
                    refused = runner.invoke([runner.args.sox, '-D', dff, back])
                    verify.check(refused['exit'] != 0, 'unassigned DFF surrounds must not become DSF backs')
                    args += ['--dsd-layout', 'FL,FR,FC,LFE,BL,BR']
                p = runner.invoke([*args, back])
                verify.check(p['exit'] == 0, 'DFF to DSF native command')
                returned = verify.decode_dsf(back.read_bytes())
                verify.check(returned['timeline'] == written['timeline'], 'completed round-trip chronology')
                checks.append(dict(channels=nch, source_frames=frames, completed_frames=written['frames'],
                    source_bits_unchanged=True, roundtrip_bits_unchanged=True,
                    source_chronology_sha256=verify.chronology_sha256(source_bits),
                    completed_chronology_sha256=written['chronological_bits_sha256']))
    return dict(status='pass', cases=len(checks), checks=checks,
                logical_endpoint_rule='round up to eight frames only for a partial cluster')
