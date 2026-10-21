#!/usr/bin/env python3
"""Shared DSD phase test runner: independent oracles, explicit defect lifetimes.

P00 xfails describe ONE observed baseline fingerprint each. An unexpected pass
or a different failure is a failing test, never a silent xfail. Later phases
keep this file and extend the registry; after each defect's phase, the case
must pass. All subprocess invocations and exits are written to raw JSON.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import pathlib
import platform
import re
import struct
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass

from reference import fixtures, verify, writer

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT/'tests/dsd/fixtures'


class CaseMismatch(AssertionError):
    pass


def require(condition, reason):
    if not condition:
        raise CaseMismatch(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def baseline_reader_bits(observed: dict, *, start: int = 0, stop: int | None = None,
                         trailer: str = '') -> bool:
    """Pin the full returned bits against the independent fixture chronology.

    All P00 regression fixtures are shorter than the observer's 8192-bit head
    capture; a missing/truncated oracle must never admit an xfail.
    """
    oracle = observed.get('expected_head_bits')
    actual = observed.get('head_bits')
    return (isinstance(oracle, str) and len(oracle) == observed.get('expected_samples')
            and isinstance(actual, str) and actual == oracle[start:stop] + trailer
            and len(actual) == observed.get('remaining_returned'))


def stable_writer_audio_tail(observed: dict, *, uninitialized_bytes: int, tail: bytes) -> bool:
    """Compare only bytes beyond the independently known uninitialized DFF cluster.

    The first cluster cannot be a stable oracle until its P01 writer fix;
    later bytes are deterministic for the C probe's constant input.
    """
    audio = observed.get('audio_hex')
    return (isinstance(audio, str) and len(audio) == 2 * (uninitialized_bytes + len(tail))
            and audio[uninitialized_bytes * 2:] == tail.hex())


def metadata(phase='P00'):
    cpu = ''
    p = pathlib.Path('/proc/cpuinfo')
    if p.is_file():
        cpu = p.read_text(errors='replace')
        matches = re.search(r'^model name\s*:\s*(.*)$', cpu, re.M)
        model = matches.group(1).strip() if matches else None
        flags = re.search(r'^flags\s*:\s*(.*)$', cpu, re.M)
        features = flags.group(1).split() if flags else []
        microcode = re.search(r'^microcode\s*:\s*(.*)$', cpu, re.M)
    else:
        model, features, microcode = platform.processor(), [], None
    return dict(architecture=platform.machine(), os=platform.platform(),
                hostname=platform.node(), cpu_model=model, cpu_microcode=microcode.group(1) if microcode else None,
                cpu_features=features, affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                python=platform.python_version(), seed=fixtures.SEED,
                build_configuration='configure --disable-shared --without-libltdl CFLAGS=-O2 -g',
                input_archive_sha256=(ROOT/f'tests/dsd/results/{phase}/build/input_archive.sha256').read_text().split()[0]
                    if (ROOT/f'tests/dsd/results/{phase}/build/input_archive.sha256').exists() else None,
                dsdiff_source_sha256=sha((ROOT/'src/dsdiff.c').read_bytes()),
                design_sha256=sha((ROOT/'docs/dsd/DSD_DESIGN.md').read_bytes()),
                prebuild_source_hash_manifest_sha256=sha((ROOT/'tests/dsd/results/P00/build/source_prebuild.sha256').read_bytes())
                    if (ROOT/'tests/dsd/results/P00/build/source_prebuild.sha256').exists() else None,
                source_baseline_claim='16aa7e17531dd3612f29247da98c8ea570cd905a',
                repository_git_metadata='not present in supplied tar; source C/H hashes retained')


@dataclass
class TestCase:
    name: str
    mode: str
    fn: object
    defect: str | None = None
    fixed_in: str | None = None
    fingerprint: object | None = None


def awaiting_fix(phase: int, case: TestCase) -> bool:
    """Only unresolved defects require their original baseline fingerprint."""
    return case.defect is not None and phase < int(case.fixed_in[1:])


def classify(phase: int, case: TestCase, observed: dict) -> tuple[str, str]:
    """A known defect is an xfail only for its approved observed fingerprint."""
    correct = observed.get('correct', True)
    must_pass = not awaiting_fix(phase, case)
    if correct:
        return ('pass' if must_pass else 'xpass',
                '' if must_pass else 'known failure disappeared before its planned resolution phase')
    if must_pass:
        return 'fail', 'observable behavior disagrees with independent oracle'
    if case.fingerprint(observed):
        return 'xfail', 'only the named baseline fingerprint matches'
    return 'fail', 'unrecognized failure, does not match approved baseline fingerprint'


class Runner:
    def __init__(self, args):
        self.args = args
        self.phase = int(args.phase[1:])
        self.cases: list[TestCase] = []
        self.records: list[dict] = []
        self.commands: list[dict] = []
        self.fixtures = json.loads((SRC/'manifest.json').read_text())['fixtures']
        args.results.mkdir(parents=True, exist_ok=True)

    def add(self, name, mode, fn, defect=None, fixed_in=None, fingerprint=None):
        if defect:
            require(fixed_in and fingerprint, f'{name}: every expected failure needs a defect, fix phase and fingerprint')
        self.cases.append(TestCase(name, mode, fn, defect, fixed_in, fingerprint))

    def invoke(self, argv, *, env=None, timeout=45):
        actual_env = os.environ.copy()
        actual_env.update(env or {})
        start = time.perf_counter()
        try:
            r = subprocess.run([str(x) for x in argv], capture_output=True, text=True,
                               env=actual_env, timeout=timeout, cwd=ROOT)
            result = dict(command=[str(x) for x in argv], cwd=str(ROOT),
                          env_overrides=env or {}, exit=r.returncode,
                          stdout=r.stdout, stderr=r.stderr,
                          wall_seconds=time.perf_counter()-start)
        except subprocess.TimeoutExpired as exc:
            result = dict(command=[str(x) for x in argv], cwd=str(ROOT),
                          env_overrides=env or {}, exit=None,
                          timeout_seconds=timeout, stderr=str(exc), stdout='',
                          wall_seconds=time.perf_counter()-start)
        self.commands.append(result)
        require(result['exit'] is not None, 'command timed out')
        return result

    def probe(self, filename, cap=4096, initial=0, offset=None, core_fix=False):
        cmd = [self.args.probe, 'read', SRC/filename, str(cap), str(initial),
               '-' if offset is None else str(offset), '1' if core_fix else '0']
        result = self.invoke(cmd)
        require(result['exit'] == 0, f'API probe exit: {result["exit"]}; {result["stderr"]}')
        try:
            observed = json.loads(result['stdout'])
        except ValueError as exc:
            raise CaseMismatch(f'non-JSON API result: {exc}') from exc
        return observed

    def expected_bits(self, filename, start_frame=0):
        blob = (SRC/filename).read_bytes()
        if filename.endswith('.dsf'):
            decoded = verify.decode_dsf(blob)
        elif filename.endswith('.dff'):
            decoded = verify.decode_dff(blob)
        else:
            raise ValueError('no independent decoder for ' + filename)
        frame_count = self.fixtures[filename]['logical_frames']
        timeline = decoded['timeline']
        return ''.join(str(ch[frame]) for frame in range(start_frame, frame_count)
                       for ch in timeline)

    def read_case(self, filename, cap=4096, initial=0, offset=None, fix=False,
                  expected_start=None):
        actual = self.probe(filename, cap, initial, offset, fix)
        source = self.fixtures[filename]
        expected_start = (offset // source['channels'] if offset is not None else
                          initial // source['channels']) if expected_start is None else expected_start
        expected = self.expected_bits(filename, expected_start)
        actual['expected_samples'] = len(expected)
        actual['expected_head_bits'] = expected[:8192]
        actual['oracle_filenames'] = [filename, 'fixtures/manifest.json']
        actual['correct'] = (actual.get('open') is True and
                             actual['remaining_returned'] == len(expected) and
                             actual['head_bits'] == expected[:8192] and
                             (offset is None or actual['seek_rc'] == 0))
        return actual

    def register_units(self):
        # Overflow is checked explicitly rather than passed through C wraparound.
        def counts():
            require(fixtures.sample_count(8, 6) == 48, 'interleaved count')
            require(fixtures.complete_frames(49, 6) == (8,1), 'partial frame')
            require(fixtures.sample_count(0, 2) == 0, 'empty frames')
            for fn, a, b in ((fixtures.sample_count, 1<<63,2),
                             (fixtures.sample_count, 1,0),
                             (fixtures.sample_count, -1,1)):
                try:
                    fn(a,b)
                except ValueError:
                    continue
                raise CaseMismatch('unchecked u64 or invalid channels')
            return {'samples_per_8_frames_at_6ch':48, 'partial_frames_for_49_samples_at_6ch':[8,1]}
        self.add('unit_exact_integer_counts', 'unit', counts)

        def classification():
            known = TestCase('synthetic', 'unit', None, 'DEFECT-EXAMPLE','P03',
                             lambda a: a.get('observed')=='original')
            require(classify(0,known,{'correct':False,'observed':'original'})[0]=='xfail', 'named fingerprint')
            require(classify(0,known,{'correct':True})[0]=='xpass', 'xfail unexpectedly fixed must fail')
            require(classify(0,known,{'correct':False,'observed':'different'})[0]=='fail', 'unknown failure must fail')
            require(classify(3,known,{'correct':False,'observed':'original'})[0]=='fail', 'after P03 old bug must fail')
            require(classify(3,known,{'correct':True})[0]=='pass', 'after P03 fix must pass')
            return {'xfail':'named baseline only', 'xpass':'error', 'new failure':'error',
                    'phase fix gate':'hard pass required'}
        self.add('unit_explicit_xfail_classifier', 'unit', classification)

        def p01_mutation_transition():
            by_name = {case.name: case for case in self.cases}
            writer = by_name['dff_writer_frm8_parent_size']
            reader = by_name['dff_trailing_manf_generic_counter']
            type5 = by_name['dsf_type5_channel_identity_loss']
            require(awaiting_fix(0, writer) and not awaiting_fix(1, writer),
                    'P01 writer must leave the live baseline-mutation gate')
            require(awaiting_fix(1, reader) and awaiting_fix(1, type5),
                    'P03 reader and P04 Type 5 baseline checks must remain active')
            corrected = {'correct': True}
            require(classify(0, writer, corrected)[0] == 'xpass',
                    'premature writer repair must still fail P00')
            require(classify(1, writer, corrected)[0] == 'pass',
                    'P01 corrected writer must pass without its old fingerprint')
            require(classify(1, writer, {'correct': False})[0] == 'fail',
                    'P01 must reject an unfixed writer')
            return {'P01_writer': 'hard pass, no baseline mutation check',
                    'P03_reader': 'baseline mutation check remains',
                    'P04_type5': 'baseline mutation check remains'}
        self.add('unit_P01_xfail_mutation_transition', 'unit', p01_mutation_transition)

        def spans():
            require([fixtures.span(v) for v in (0,1,2,3,19)] == [12,14,14,16,32], 'chunk span')
            for invalid in (-1, fixtures.UINT64_MAX):
                try: fixtures.span(invalid)
                except ValueError: continue
                raise CaseMismatch('chunk span overflow not rejected')
            result = {'physical_spans_0_1_2_3_19': [12,14,14,16,32]}
            if self.phase >= 1:
                unit = self.invoke([self.args.writer_unit])
                require(unit['exit'] == 0, 'production DFF arithmetic/tail/error unit test: ' + unit['stderr'])
                result['production_writer_units'] = json.loads(unit['stdout'])
            return result
        self.add('unit_dff_chunk_spans', 'unit', spans)

        def hand_bits():
            seq = bytes([0,1,1,0,1,0,0,1])
            require(fixtures.pack_byte(seq,0,True) == 0x69, 'MSB 0x69 timeline')
            require(fixtures.pack_byte(seq,0,False) == 0x96, 'LSB 0x96 timeline')
            x = fixtures.make_dsf((seq,), bps=1)
            y = fixtures.make_dsf((seq,), bps=8)
            require(x[92] == 0x96 and y[92] == 0x69, 'DSF physical byte')
            require(verify.decode_dsf(x)['timeline'] == verify.decode_dsf(y)['timeline'] == [seq], 'independent chronology')
            dff = fixtures.make_dff((seq,))
            require(verify.decode_dff(dff)['timeline'] == [seq], 'DFF chronology')
            require(fixtures.dop_words((seq+seq,)) == [[0x056969]], 'DoP hand word 0x056969')
            require(verify.decode_dop(bytes.fromhex('696905'),1,16)['timeline'] == [seq+seq], 'DoP hand bytes')
            return {'dsf_lsb_byte':'96', 'dsf_msb_byte':'69', 'dff_byte':'69', 'dop_pcm24le':'696905'}
        self.add('unit_hand_derived_bit_order_dsd_dop', 'unit', hand_bits)

        def generator():
            with tempfile.TemporaryDirectory(prefix='dsd-fixture-repro-') as td:
                m = fixtures.generate(pathlib.Path(td))
                require(self.fixtures == m['fixtures'], 'fixture manifest drift')
                for name, record in self.fixtures.items():
                    require((pathlib.Path(td)/name).read_bytes() == (SRC/name).read_bytes(), 'nondeterministic '+name)
                    require(sha((SRC/name).read_bytes()) == record['sha256'], 'file digest changed '+name)
                return {'byte_identical_regenerated_fixtures':len(self.fixtures), 'seed':fixtures.SEED}
        self.add('unit_reproducible_fixture_generator', 'unit', generator)

        def independent_decoding():
            verified = []
            for name, record in self.fixtures.items():
                raw = (SRC/name).read_bytes()
                if record['kind']=='dsf':
                    result = verify.decode_dsf(raw)
                elif record['kind']=='dff':
                    result = verify.decode_dff(raw)
                elif record['kind']=='dop-pcm24le':
                    result = verify.decode_dop(raw, record['channels'], record['logical_frames'])
                else:
                    continue
                reference = fixtures.bits(record['logical_frames'],record['channels'],
                                '69' if name.startswith(('mono_32_dop', 'dop_')) else 'distinct')
                require(len(result['timeline']) == record['channels'], f'{name}: channels')
                require(all(bytes(seq[:record['logical_frames']]) == reference[i]
                            for i,seq in enumerate(result['timeline'])), f'{name}: independent per-channel chronology')
                if record['kind']=='dff':
                    require(result['frames'] == (record['logical_frames']+7)//8*8, f'{name}: completed frames')
                    require(result['audio']['payload_size'] == record['channels']*((record['logical_frames']+7)//8),
                            f'{name}: physical audio length')
                    require(result['top'][-1]['tag'] == ('MANF' if record.get('trailing_manf') else 'DSD '),
                            f'{name}: trailing chunk')
                else:
                    require(result['chronological_bits_sha256'] == record['chronological_bits_sha256'],
                            f'{name}: bits digest')
                verified.append(name)
            # The independent walker must reject structural corruption.
            good = bytearray((SRC/'mono_9.dff').read_bytes())
            good[4:12] = struct.pack('>Q', len(good))
            try: verify.decode_dff(bytes(good))
            except verify.StructureError: pass
            else: raise CaseMismatch('walker accepted FRM8 size mismatch')
            return {'independent_fixture_decodes':len(verified), 'examples':verified}
        self.add('unit_independent_chunk_and_bit_oracles', 'unit', independent_decoding)

    def register_integrations(self):
        def reader(name, filename, cap, *, start=0, seek=None, initial=0, fix=False,
                   fingerprint=None, defect=None, fixed_in=None):
            self.add(name, 'integration',
                     lambda f=filename,c=cap,s=seek,i=initial,fx=fix: self.read_case(f,c,i,s,fx),
                     defect=defect, fixed_in=fixed_in, fingerprint=fingerprint)

        reader('dsf_normal_mono_96', 'mono_96.dsf', 4096)
        reader('dsf_normal_stereo_96', 'stereo_96.dsf', 4096)
        reader('dsf_fourchannel_type4_audio', 'type4_quad_96.dsf', 4096)
        reader('dsf_sixchannel_audio', 'six_96.dsf', 4096)
        reader('dff_normal_stereo_128', 'stereo_128.dff', 4096)
        reader('dff_manf_core_corrected_control', 'mono_128_manf.dff',128,
               seek=8, fix=True)
        reader('dsf_rewind_core_corrected_control', 'mono_96.dsf',96,
               initial=8,seek=0,fix=True)
        reader('dsf_small_capacity_one_frame', 'mono_96.dsf',1,
               defect='C3-DSF-SMALL-READ',fixed_in='P02',
               fingerprint=lambda a: a.get('open') is True and a.get('remaining_returned') == 0
                                     and a.get('head_bits') == '')
        reader('dff_small_capacity_one_frame', 'mono_128_manf.dff',1,
               defect='C3-DFF-SMALL-READ',fixed_in='P02',
               fingerprint=lambda a: a.get('open') is True and a.get('remaining_returned') == 0
                                     and a.get('head_bits') == '')
        # Independent tiny valid input reaches a distinct initialization error.
        reader('dsf_one_frame_first_bit', 'one.dsf',16,
               defect='C3-DSF-TINY',fixed_in='P02',
               fingerprint=lambda a: a.get('open') and a.get('remaining_returned') == 1 and a.get('head_bits') == '0')
        reader('dsf_empty_file', 'empty.dsf',16,
               defect='C3-DSF-EMPTY',fixed_in='P02',
               fingerprint=lambda a: a.get('open') is False)
        reader('dff_single_byte_cluster', 'one_cluster.dff',4096,
               defect='C3-DFF-MINIMUM',fixed_in='P02',
               fingerprint=lambda a: a.get('open') is False)
        reader('dsf_msb_first_8bit_storage', 'msb_stereo_96.dsf',4096,
               defect='C4-DSF-MSB',fixed_in='P02',
               fingerprint=lambda a: a.get('open') is False)
        reader('dsf_rewind_generic_core_position', 'mono_96.dsf',96,
               initial=8,seek=0,
               defect='C2-CORE-OLENGTH',fixed_in='P03',
               fingerprint=lambda a: a.get('open') is True and a.get('seek_rc') == 0
                                     and a.get('first_read') == 8
                                     and a.get('remaining_returned') == 88
                                     and a.get('olength_after_seek') == 8
                                     and baseline_reader_bits(a, stop=88))
        reader('dsf_multichannel_public_seek_offset16', 'stereo_96.dsf',4096,
               seek=16,fix=True,
               defect='C2-DSF-SEEK-UNITS',fixed_in='P03',
               # Baseline interprets offset 16 interleaved samples as 16 frames;
               # the independently expected slice begins 8 frames (16 samples) too early.
               fingerprint=lambda a: a.get('open') is True and a.get('seek_rc') == 0
                                     and a.get('remaining_returned') == 160
                                     and a.get('olength_after_seek') == 0
                                     and baseline_reader_bits(a, start=16))
        reader('dff_multichannel_public_seek_offset16', 'stereo_128.dff',4096,
               seek=16,fix=True,
               defect='C2-DFF-SEEK-UNITS',fixed_in='P03',
               fingerprint=lambda a: a.get('open') is True and a.get('seek_rc') == 0
                                     and a.get('remaining_returned') == 224
                                     and a.get('olength_after_seek') == 0
                                     and baseline_reader_bits(a, start=16))
        reader('dff_trailing_manf_generic_counter', 'mono_128_manf.dff',128,
               seek=8,
               defect='C2-DFF-MANF-CORE-OLENGTH',fixed_in='P03',
               # The stale counter reads one additional byte from the MANF tag:
               # ASCII 'M' == 0x4d == chronological bits 01001101 (MSB first).
               fingerprint=lambda a: a.get('open') is True and a.get('seek_rc') == 0
                                     and a.get('remaining_returned') == 128
                                     and a.get('olength_after_seek') == 0
                                     and baseline_reader_bits(a, trailer='01001101'))

        def wsd_case(cap):
            result = self.probe('mono_16.wsd',cap)
            result['expected_samples']=16
            result['expected_head_bits']='1100110110011011'
            result['correct']=(result.get('open') and result.get('remaining_returned') == 16 and
                               result.get('head_bits') == '1100110110011011')
            return result
        self.add('wsd_normal_mono_16', 'integration', lambda: wsd_case(4096))
        self.add('wsd_small_capacity_one_frame', 'integration', lambda: wsd_case(1),
                 defect='C3-WSD-SMALL-READ',fixed_in='P02',
                 fingerprint=lambda a: a.get('open') is True and a.get('remaining_returned') == 0
                                       and a.get('head_bits') == '')

        def wav_rewind():
            # Independently construct 441 PCM frames; do not rely on the SoX WAV writer.
            with tempfile.TemporaryDirectory(prefix='dsd-wav-seek-') as td:
                wav_path = pathlib.Path(td)/'mono.wav'
                with wave.open(str(wav_path),'wb') as w:
                    w.setnchannels(1); w.setsampwidth(4); w.setframerate(44100)
                    w.writeframes(struct.pack('<441i', *([0]*441)))
                argv = [self.args.probe, 'read', wav_path, '8192', '8', '0', '1']
                proc = self.invoke(argv)
                require(proc['exit']==0, 'WAV probe exited nonzero')
                val = json.loads(proc['stdout']); val['expected_samples']=441
                val['correct']=(val.get('open') and val.get('first_read')==8 and
                                val.get('remaining_returned')==441 and val.get('head_bits') == '0'*441)
                return val
        self.add('wav_rewind_after_manual_core_position_correction', 'integration', wav_rewind,
                 defect='D2-WAV-PRIVATE-REMAINING', fixed_in='P03',
                 fingerprint=lambda a: a.get('open') is True and a.get('seek_rc') == 0
                                       and a.get('first_read') == 8
                                       and a.get('remaining_returned') == 433
                                       and a.get('olength_after_seek') == 8
                                       and a.get('head_bits') == '0' * 433)

        def writer_run(frames, nch=1, perturb=False):
            with tempfile.TemporaryDirectory(prefix='dsd-writer-probe-') as td:
                target = pathlib.Path(td)/'output.dff'
                env = {'MALLOC_PERTURB_':'85'} if perturb else None
                p = self.invoke([self.args.probe,'write',target,nch,frames],env=env)
                require(p['exit']==0 and json.loads(p['stdout'])['write_ok'], f'DFF writer refused legitimate input: {p}')
                raw = target.read_bytes()
            cmpr = raw.find(b'CMPR')
            require(cmpr >= 0, 'missing CMPR')
            cmpr_bytes = struct.unpack_from('>Q',raw,cmpr+4)[0]
            audio = cmpr + 12 + cmpr_bytes + (cmpr_bytes & 1)
            require(raw[audio:audio+4] == b'DSD ', 'missing audio after CMPR chunk')
            n = (frames+7)//8 * nch
            return dict(channels=nch, logical_frames=frames, physical_bytes=len(raw),
                        frm8_declared=struct.unpack_from('>Q',raw,4)[0],
                        cmpr_declared=struct.unpack_from('>Q',raw,cmpr+4)[0],
                        cmpr_name_count=raw[cmpr+16],
                        dsd_declared=struct.unpack_from('>Q',raw,audio+4)[0],
                        dsd_observed_bytes=len(raw)-(audio+12),
                        expected_audio_bytes=n,
                        audio_hex=raw[audio+12:].hex(),
                        audio_start=audio+12,
                        expected_complete_file_bytes=audio+12+n+(n&1),
                        correct_cmpr=(struct.unpack_from('>Q',raw,cmpr+4)[0]==19 and raw[cmpr+16]==14),
                        correct_frm8=(struct.unpack_from('>Q',raw,4)[0]==len(raw)-12),
                        correct_audio_count=struct.unpack_from('>Q',raw,audio+4)[0]==n,
                        correct_odd_padding=len(raw)>=audio+12+n+(n&1))

        def cmpr_case():
            r = writer_run(16)
            r['correct'] = r['correct_cmpr']
            if self.phase >= 1:
                r['writer_vectors'] = writer.run_vectors(self)
            return r
        self.add('dff_writer_cmpr_name_length', 'integration', cmpr_case,
                 defect='C1-DFF-CMPR-SIZE', fixed_in='P01',
                 fingerprint=lambda a: a['cmpr_declared']==20 and a['cmpr_name_count']==15
                                       and stable_writer_audio_tail(a, uninitialized_bytes=1, tail=b'\x00'))
        self.add('dff_writer_frm8_parent_size', 'integration',
                 lambda: {'correct': (r:=writer_run(16))['correct_frm8'], **r},
                 defect='C1-DFF-FRM8-DOUBLECOUNT',fixed_in='P01',
                 fingerprint=lambda a: a['frm8_declared']==a['physical_bytes']-12+2
                                       and stable_writer_audio_tail(a, uninitialized_bytes=1, tail=b'\x00'))
        self.add('dff_writer_completed_tail_audio_count', 'integration',
                 lambda: {'correct': (r:=writer_run(9))['correct_audio_count'], **r},
                 defect='C1-DFF-TAIL-COUNT',fixed_in='P01',
                 fingerprint=lambda a: a['dsd_declared']==1 and a['dsd_observed_bytes']==2
                                       and stable_writer_audio_tail(a, uninitialized_bytes=1, tail=b'\x69'))
        self.add('dff_writer_odd_payload_external_pad', 'integration',
                 lambda: {'correct': (r:=writer_run(8))['correct_odd_padding'], **r},
                 defect='C1-DFF-ODD-PADDING',fixed_in='P01',
                 fingerprint=lambda a: a['dsd_declared']==1 and
                                       a['physical_bytes']==a['expected_complete_file_bytes']-1)
        for nch in (1,4):
            def first_cluster(nch=nch):
                r = writer_run(16,nch,True)
                b = bytes.fromhex(r['audio_hex'])
                r['expected_first_cluster_hex']=(bytes(nch)).hex()
                r['observed_first_cluster_hex']=b[:nch].hex()
                r['correct']=b[:nch] == bytes(nch)
                return r
            self.add(f'dff_writer_uninitialized_first_cluster_{nch}ch', 'integration',first_cluster,
                     defect='D1-DFF-FIRST-CLUSTER',fixed_in='P01',
                     fingerprint=lambda a: a['observed_first_cluster_hex']=='aa'*a['channels']
                                           and stable_writer_audio_tail(a, uninitialized_bytes=a['channels'],
                                                                        tail=bytes(a['channels'])))

        def type5():
            with tempfile.TemporaryDirectory(prefix='dsd-type5-') as td:
                p = pathlib.Path(td)/'out.dsf'
                rr = self.invoke([self.args.sox,'-D', SRC/'type5_quad_96.dsf',p])
                require(rr['exit']==0, 'DSF native roundtrip failed')
                raw = p.read_bytes()
                val = struct.unpack_from('<I',raw,48)[0]
                source_bits = verify.decode_dsf((SRC/'type5_quad_96.dsf').read_bytes())['timeline']
                output_bits = verify.decode_dsf(raw)['timeline']
                audio_matches = output_bits == source_bits
                return dict(observed_type=val,expected_type=5,
                            audio_matches_oracle=audio_matches,
                            correct=val==5 and audio_matches,
                            command=rr['command'], output_sha256=sha(raw))
        self.add('dsf_type5_channel_identity_loss', 'integration',type5,
                 defect='C5-DSF-TYPE5-LOSS',fixed_in='P04',
                 fingerprint=lambda a: a['observed_type']==4 and a.get('audio_matches_oracle') is True)

        def dop():
            with tempfile.TemporaryDirectory(prefix='dsd-dop-cli-') as td:
                dest = pathlib.Path(td)/'transport.wav'
                r = self.invoke([self.args.sox,'-D',SRC/'mono_32_dop.dsf','-r','176400',
                                 '-b','24','-e','signed-integer',dest,'dop'])
                require(r['exit']==0, 'DoP CLI command failed')
                with wave.open(str(dest),'rb') as w:
                    require(w.getnchannels()==1 and w.getsampwidth()==3 and w.getframerate()==176400,
                            'DoP WAV shape invalid')
                    raw=w.readframes(w.getnframes())
                reference=fixtures.dop_words(fixtures.bits(32,1,'69'))
                expected=bytes(byte for words in reference for word in words for byte in
                               (word&255,word>>8&255,word>>16&255))
                result=verify.decode_dop(raw,1,32)
                return dict(correct=(raw==expected and result['chronological_bits_sha256']==
                                      self.fixtures['mono_32_dop.dsf']['chronological_bits_sha256']),
                            output_hex=raw.hex(),expected_hex=expected.hex(),
                            marker_count=len(raw)//3)
        self.add('dop_cli_hand_vector_transport_markers', 'integration',dop)

        def fingerprint_mutations():
            # Real baseline observations, not synthetic counters: changing audio
            # alone must never be hidden by an otherwise matching defect count.
            by_name = {case.name: case for case in self.cases}
            reader_cases = (
                'dsf_rewind_generic_core_position',
                'dsf_multichannel_public_seek_offset16',
                'dff_multichannel_public_seek_offset16',
                'dff_trailing_manf_generic_counter',
                'wav_rewind_after_manual_core_position_correction',
            )
            writer_cases = (
                'dff_writer_cmpr_name_length',
                'dff_writer_frm8_parent_size',
                'dff_writer_completed_tail_audio_count',
            )
            tested = []
            for name in (*reader_cases, *writer_cases):
                case = by_name[name]
                if not awaiting_fix(self.phase, case):
                    continue
                observed = case.fn()
                require(observed.get('correct') is False and classify(self.phase, case, observed)[0] == 'xfail',
                        f'{name}: baseline no longer reproduces the approved fingerprint')
                field = 'head_bits' if name in reader_cases else 'audio_hex'
                baseline_bits = observed[field]
                require(len(baseline_bits) > 0, f'{name}: mutation input is empty')
                # For the writer only change a deterministic byte past its
                # uninitialized first cluster; do not pin allocator garbage.
                for at in ((0, len(baseline_bits)-1) if field == 'head_bits'
                           else (len(baseline_bits)-1,)):
                    altered = dict(observed)
                    altered[field] = (baseline_bits[:at] +
                                      ('1' if baseline_bits[at] == '0' else '0') +
                                      baseline_bits[at+1:])
                    require(altered['remaining_returned'] == observed['remaining_returned']
                            if field == 'head_bits' else altered['dsd_declared'] == observed['dsd_declared'],
                            f'{name}: count signature changed during mutation')
                    require(classify(self.phase, case, altered)[0] == 'fail',
                            f'{name}: changed audio concealed by baseline xfail')
                corrected = dict(observed, correct=True)
                require(classify(self.phase, case, corrected)[0] == 'xpass',
                        f'{name}: premature correction must report XPASS')
                require(classify(int(case.fixed_in[1:]), case, corrected)[0] == 'pass',
                        f'{name}: correction must pass at approved phase')
                require(classify(int(case.fixed_in[1:]), case, observed)[0] == 'fail',
                        f'{name}: baseline defect must fail after approved phase')
                # A missing fixture oracle must not count as a matching slice.
                if name in reader_cases and name != 'wav_rewind_after_manual_core_position_correction':
                    absent_oracle = dict(observed)
                    absent_oracle.pop('expected_head_bits')
                    require(classify(self.phase, case, absent_oracle)[0] == 'fail',
                            f'{name}: missing independent bits permitted an xfail')
                tested.append(name)
            # Type 5's defect is channel metadata loss, not an audio change.
            type5_case = by_name['dsf_type5_channel_identity_loss']
            if awaiting_fix(self.phase, type5_case):
                type5_observed = type5_case.fn()
                require(classify(self.phase, type5_case, type5_observed)[0] == 'xfail',
                        'Type 5 baseline no longer reproduces independently checked audio')
                type5_altered = dict(type5_observed, audio_matches_oracle=False)
                require(classify(self.phase, type5_case, type5_altered)[0] == 'fail',
                        'Type 5 audio mutation hidden behind channel metadata xfail')
                tested.append(type5_case.name)
            return dict(real_baseline_fingerprints_checked=tested,
                        mutations='first and last reader bits; deterministic writer tail',
                        unchanged_baseline='xfail', changed_audio='fail',
                        early_correction='xpass', phase_correction='pass')
        self.add('integration_xfail_audio_mutation_rejection', 'integration', fingerprint_mutations)

    def run(self):
        modes = ('unit','integration') if self.args.mode == 'all' else (self.args.mode,)
        names = set()
        for case in self.cases:
            if case.name in names:
                raise ValueError('duplicate test '+case.name)
            names.add(case.name)
            if case.mode not in modes or not fnmatch.fnmatch(case.name,self.args.only):
                continue
            t0 = time.perf_counter()
            entry = dict(name=case.name, mode=case.mode, defect_id=case.defect,
                         expected_resolution_phase=case.fixed_in)
            try:
                observed = case.fn()
                correct = observed.get('correct',True)
                entry['observed'] = observed
                entry['status'], entry['message'] = classify(self.phase,case,observed)
            except Exception as exc:
                entry['status']='fail'
                entry['message']=f'{type(exc).__name__}: {exc}'
            entry['wall_seconds'] = time.perf_counter()-t0
            self.records.append(entry)
            print(f'{entry["status"].upper():5} {case.name}',flush=True)
        counts={k:sum(x['status']==k for x in self.records) for k in ('pass','xfail','xpass','fail','skip')}
        report=dict(schema='dsd-tests/1',phase=self.args.phase,executed_command=sys.argv,utc_timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    fixture_manifest_sha256=sha((SRC/'manifest.json').read_bytes()),
                    metadata=metadata(self.args.phase), tests=self.records, counts=counts,
                    selected_count=len(self.records),commands=self.commands,
                    verdict='pass' if not counts['fail'] and not counts['xpass'] and self.records else 'fail')
        report_path=self.args.results/'run.json'
        if report_path.exists():
            old=report_path.read_bytes()
            try:
                prior=json.loads(old)
                if prior.get('verdict')=='fail':
                    backup=report_path.with_name('run-failed-'+hashlib.sha256(old).hexdigest()[:16]+'.json')
                    if not backup.exists():backup.write_bytes(old)
            except ValueError:
                pass
        temp=report_path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        temp.replace(report_path)
        print(json.dumps(dict(verdict=report['verdict'],counts=counts,
                              result_path=str(self.args.results/'run.json'))))
        return 0 if report['verdict']=='pass' else 1


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase',default='P00',choices=[f'P{i:02}' for i in range(19)])
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P00')
    ap.add_argument('--sox',type=pathlib.Path,default=ROOT/'src/sox')
    ap.add_argument('--probe',type=pathlib.Path,default=ROOT/'test/dsd_test_io')
    ap.add_argument('--writer-unit',type=pathlib.Path,default=ROOT/'test/dsd_test_dff_writer')
    ap.add_argument('--mode',choices=('unit','integration','all'),default='all')
    ap.add_argument('--only',default='*',help='glob-select named tests, no automatic skip')
    args=ap.parse_args()
    runner=Runner(args);runner.register_units();runner.register_integrations()
    if args.phase == 'P16':
        def p16_executable(suffix, timeout):
            def gate():
                command = [str(ROOT/'test/dsd_test_p16'), *suffix]
                result = runner.invoke(command, timeout=timeout)
                require(result['exit'] == 0,
                        f'P16 executable exit {result["exit"]}: {result["stderr"][-1500:]}')
                require(result['stdout'].startswith('P16 '),
                        'P16 executable returned no pass summary')
                return dict(correct=True, command=command,
                            summary=result['stdout'].strip())
            return gate
        runner.add('P16_native_packed_reader_contract', 'unit',p16_executable([],180))
        runner.add('P16_binary64_packed_versus_expanded_FIR_ISA_matrix',
                   'unit',p16_executable(['matrix'],180))

    if not args.sox.is_file() or not args.probe.is_file():
        ap.error('missing built sox and test/dsd_test_io; build with make and make -C test dsd_test_io')
    floor=runner.run()
    if args.phase=='P14' and not floor and args.only=='*' and args.mode=='all':
        # P00's inherited floor is still reported separately; the P14 gate
        # is an executable report/bit/stream contract, not a relabeled floor.
        command=[sys.executable,str(ROOT/'tests/dsd/test_p14.py'),
            '--sox',str(args.sox),
            '--unit',str(args.probe.parent/'dsd_test_p14'),
            '--results',str(args.results/'report')]
        try:
            cp=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=300)
            record=dict(name='P14_report_native_statistics',status='PASS' if cp.returncode==0 else 'FAIL',
                exit_code=cp.returncode,
                command=[str(x).replace(str(ROOT),'<tree>') for x in command],
                stdout=cp.stdout,stderr=cp.stderr)
        except (OSError,subprocess.TimeoutExpired) as error:
            record=dict(name='P14_report_native_statistics',status='FAIL',error=str(error))
        print(record['name'],record['status'],flush=True)
        (args.results/'implementation.json').write_text(json.dumps(dict(
            schema='P14/implementation-tests/1',records=[record],
            result='PASS' if record['status']=='PASS' else 'FAIL',
            physical_performance_qualification='OPEN'),indent=2,sort_keys=True)+'\n')
        return int(record['status']!='PASS')
    if floor or args.phase!='P10' or args.only!='*' or args.mode!='all':
        return floor
    # Keep the inherited 36-case floor visible, and execute real P10 contracts
    # in a separate report rather than relabeling that floor as qualification.
    tasks=[('P10_core',[str(ROOT/'test/dsd_test_p10'),'--unit']),
        ('P10_CLI',[sys.executable,str(ROOT/'tests/dsd/test_p10.py'),
            '--sox',str(args.sox),'--results',str(args.results/'cli')]),
        ('P10_continuation_replay',[sys.executable,str(ROOT/'tests/dsd/soak_p10.py'),
            '--test-replay','--results',str(args.results/'soak')]),
        ('P10_prefilter_reproduction',[sys.executable,str(ROOT/'tests/dsd/generate_p10_coeffs.py'),'--check']),
        ('P10_qualification_accounting',[sys.executable,str(ROOT/'tests/dsd/test_p10_qualification.py')]),
        ('P10_negative_certificates',[sys.executable,str(ROOT/'tests/dsd/generate_p10_profiles.py'),'--check'])]
    records=[]
    for name,command in tasks:
        try:
            cp=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=300)
            record=dict(name=name,status='PASS' if cp.returncode==0 else 'FAIL',
                exit_code=cp.returncode,command=[str(x).replace(str(ROOT),'<tree>') for x in command],
                stdout=cp.stdout,stderr=cp.stderr)
        except (OSError,subprocess.TimeoutExpired) as error:
            record=dict(name=name,status='FAIL',error=str(error))
        records.append(record)
        print(name,record['status'],flush=True)
        from soak_p10 import atomic
        atomic(args.results/'implementation.json',dict(schema='P10/implementation-tests/1',
            rows=records,qualified=False,status='FAIL' if any(r['status']=='FAIL' for r in records) else
            'PASS' if len(records)==len(tasks) else 'INCOMPLETE',
            distinction='Implementation tests do not qualify a mastering profile. See numeric/qualification.json.'))
    return int(any(r['status']!='PASS' for r in records))


if __name__=='__main__':
    raise SystemExit(main())
