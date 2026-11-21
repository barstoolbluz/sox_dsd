#!/usr/bin/env python3
"""D9/D10 native DSD float-boundary, parity and failed-block checks.

Exact adapter values are injected at the public decoder return boundary by
an uninstalled qualification-only ELF interposer. The actual ordinary/native
adapters, conversion, clip predicates and writers remain unchanged. A DSF
file cannot physically encode an exact float or NaN sample.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests/dsd/reference'))
import fixtures


def demand(ok, why):
    if not ok:
        raise AssertionError(why)


def wav_data(raw):
    demand(raw[:4] == b'RIFF' and raw[8:12] == b'WAVE', 'invalid WAV output')
    marker = raw.find(b'data', 12)
    demand(marker > 0, 'WAV has no data payload')
    return raw[marker+8:]


def run(sox, work, source, mode, *, report=True, level='sacd',
        volume=None, bits=64, pipe=False, gain=None, precision=64,
        encoding='floating-point', inject=None, shim=None):
    target = '-' if pipe else str(work / ('out-' + str(len(list(work.iterdir()))) + '.wav'))
    receipt = work / ('report-' + str(len(list(work.iterdir()))) + '.json')
    cmd = [str(sox), '--precision', str(precision), '--dsd-clip', mode,
           '--dsd-level', level]
    if volume is not None:
        cmd += ['-v', str(volume)]
    if report:
        cmd += ['--report', str(receipt)]
    cmd += [str(source), '-b', str(bits), '-e', encoding,
            '-r', '88200', *(['-t', 'wav'] if pipe else []), target]
    if gain is not None:
        cmd += ['gain', str(gain)]
    env = os.environ.copy()
    if inject is not None:
        demand(shim is not None, 'adapter injection requires the real test interposer')
        env.update(LD_PRELOAD=str(shim), SOX_DSD_TEST_INJECT=inject,
                   SOX_DSD_PACKED_INPUT='0')
    cp = subprocess.run(cmd, capture_output=True, timeout=45, env=env)
    rr = json.loads(receipt.read_text()) if report and receipt.exists() else None
    payload = (cp.stdout if pipe else Path(target).read_bytes()
               if Path(target).exists() else b'')
    return {'rc': cp.returncode, 'stderr': cp.stderr.decode(errors='replace'),
            'payload': payload, 'report': rr, 'target': target, 'argv': cmd}


def build_injector(work):
    """No production files or APIs are changed to synthesize exact samples."""
    demand(platform.system() == 'Linux',
           'UNSUPPORTED: exact adapter injection requires Linux/ELF + LD_PRELOAD')
    source = ROOT / 'tests/pcm64/qualification/decoder_boundary_inject.c'
    shim = work / 'decoder-boundary-inject.so'
    cp = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                         '-fPIC', '-shared', '-I', str(ROOT / 'src'),
                         str(source), '-ldl', '-lm', '-o', str(shim)],
                        capture_output=True, timeout=45)
    demand(cp.returncode == 0,
           f'qualification interposer build failed: {cp.stderr.decode()[-900:]}')
    return shim, hashlib.sha256(source.read_bytes()).hexdigest()


def injected_adapter_matrix(sox, work, quiet):
    shim, source_digest = build_injector(work)
    rows = []

    # Exact integer endpoints, nextafter neighbours, and nonfinite values
    # travel through the *real* input-adapter checks, not an idealized Python
    # predicate. Both CLI routes must actually hit the test interposer.
    cases = [('positive_one', False, 'clip'),
             ('negative_one', True, None),
             ('positive_inside', True, None),
             ('positive_outside', False, 'clip'),
             ('negative_inside', True, None),
             ('negative_outside', False, 'clip'),
             ('nan', False, 'nonfinite'),
             ('positive_infinity', False, 'nonfinite')]
    for name, should_pass, reason in cases:
        for with_report in (False, True) if name in ('positive_one', 'negative_one', 'nan') else (False,):
            for bits, encoding in ((64, 'floating-point'), (32, 'floating-point'),
                                   (24, 'signed-integer')) if name in ('positive_one', 'negative_one', 'nan') else ((64, 'floating-point'),):
                outcomes = []
                for precision in (32, 64):
                    result = run(sox, work, quiet, 'error', level='preserve',
                                 report=with_report, bits=bits, encoding=encoding,
                                 precision=precision, inject=name, shim=shim)
                    ok = result['rc'] == 0
                    demand(result['stderr'].count(f'qualification hook: injected {name}') == 1,
                           f'{name}/{precision}: injected boundary never reached exactly once')
                    demand(ok == should_pass,
                           f'{name}/{bits}/{precision}: unexpected adapter outcome: '
                           f'{result["stderr"][-600:]}')
                    if reason == 'clip':
                        demand('--dsd-clip error' in result['stderr'],
                               f'{name}/{precision}: no clip error')
                    if reason == 'nonfinite':
                        demand('nonfinite' in result['stderr'],
                               f'{name}/{precision}: no nonfinite error')
                    if with_report:
                        demand(result['report'] is not None and
                               result['report']['status'] == ('complete' if ok else 'failed'),
                               f'{name}/{precision}: mismatched report status')
                    outcomes.append(ok)
                demand(outcomes[0] == outcomes[1],
                       f'{name}/{bits}: ordinary/native error parity failed')
                rows.append({'injection': name, 'bits': bits, 'encoding': encoding,
                             'with_report': with_report, 'ordinary_and_native_pass':
                             outcomes, 'expected': should_pass})

    # Check ordering of input -v relative to the adapter predicate, without
    # allowing the ordinary graph to rescue a sample after it has failed.
    for name, volume, should_pass in (('positive_one', .25, True),
                                      ('negative_inside', 2., False),
                                      ('positive_outside', .25, True)):
        outcomes = []
        for precision in (32, 64):
            result = run(sox, work, quiet, 'error', precision=precision,
                         volume=volume, inject=name, shim=shim, level='preserve',
                         report=False)
            demand(f'qualification hook: injected {name}' in result['stderr'],
                   'volume-parity injector did not execute')
            outcomes.append(result['rc'] == 0)
        demand(outcomes == [should_pass] * 2,
               f'{name}/volume {volume} ordinary/native mismatch: {outcomes}')
        rows.append({'injection':name,'volume':volume,'pass':outcomes,
                     'expected':should_pass,'operation':'input_volume_pre_adapter'})
    return rows, source_digest


def level_parity(sox, work):
    # An independent physical fixture: enough ones to exceed ±1 with SACD's
    # factor of two, but not with preserve. No synthetic decoder output here.
    physical = work / 'quarter-zero.dsf'
    physical.write_bytes(fixtures.make_dsf((bytes([1, 1, 1, 0]) * 8192,), fixtures.DSD64))
    rows = []
    for level, should_pass in (('preserve', True), ('sacd', False)):
        for with_report in (False, True):
            outcomes = []
            for precision in (32, 64):
                result = run(sox, work, physical, 'error', level=level,
                             report=with_report, precision=precision)
                ok = result['rc'] == 0
                demand(ok == should_pass, f'{level}/{precision}: unexpected level result')
                if with_report:
                    demand(result['report'] is not None and
                           result['report']['status'] == ('complete' if ok else 'failed'),
                           f'{level}/{precision}: unexpected report status')
                outcomes.append(ok)
            demand(outcomes[0] == outcomes[1], f'{level}: ordinary/native parity failed')
            rows.append({'physical_dsf_sha256':hashlib.sha256(physical.read_bytes()).hexdigest(),
                         'level':level,'with_report':with_report,
                         'ordinary_and_native_pass':outcomes})
    return rows


def main(sox, results):
    results.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='phase08-float-') as t:
        work = Path(t)
        source = work / 'constant-one.dsf'
        source.write_bytes(fixtures.make_dsf((bytes([1]) * 65536,), fixtures.DSD64))
        measured = []
        quiet = work / 'alternating.dsf'
        quiet.write_bytes(fixtures.make_dsf((bytes([0, 1]) * 32768,), fixtures.DSD64))
        injected_rows, injected_digest = injected_adapter_matrix(sox, work, quiet)
        level_rows = level_parity(sox, work)
        warned = run(sox, work, source, 'warn')
        no_report = run(sox, work, source, 'warn', report=False)
        demand(warned['rc'] == no_report['rc'] == 0, 'D9 warning case failed')
        demand('reconstructed PCM excursions' in warned['stderr'] and
               warned['stderr'].count('reconstructed PCM excursions') == 1 and
               no_report['stderr'].count('reconstructed PCM excursions') == 1,
               'D9 warns once even without --report')
        receipt = warned['report']
        demand(receipt and receipt['status'] == 'complete' and
               len([w for w in receipt['warnings'] if 'reconstructed PCM excursions' in w]) == 1,
               'D9 report lacks single warning')
        decoder = receipt['processing']['decoder'][0]
        clips = int(decoder['graph_clips'])
        demand(clips > 0 and decoder['max_graph_preclip_amplitude'] > 1,
               'D9 must count over-unity output and record peak')
        original = wav_data(warned['payload'])
        demand(original == wav_data(no_report['payload']),
               'D9 --report changed FLOAT64 reconstructed words')
        values = struct.unpack('<' + str(len(original)//8) + 'd', original)
        demand(max(values) > 1.5 and min(values) > -1.,
               'D9 finite >unity binary64 words were truncated')
        measured.append({'scenario':'warn_f64_report_and_no_report','graph_clips':clips,
                         'graph_peak':decoder['max_graph_preclip_amplitude'],
                         'output_data_sha256':hashlib.sha256(original).hexdigest()})
        f32 = run(sox, work, source, 'warn', bits=32)
        demand(f32['rc'] == 0 and f32['report']['status'] == 'complete',
               'D9 FLOAT32 warn case failed')
        samples = struct.unpack('<' + str(len(wav_data(f32['payload']))//4) + 'f',
                                wav_data(f32['payload']))
        demand(max(samples) > 1.5, 'D9 FLOAT32 endpoint clipped a finite >unity sample')
        measured.append({'scenario':'warn_f32','peak':max(samples)})
        for with_report in (False, True):
            for bits in (32, 64):
                rejected = run(sox, work, source, 'error', report=with_report, bits=bits)
                demand(rejected['rc'] != 0 and
                       'reconstructed PCM excursion' in rejected['stderr'] and
                       not Path(rejected['target']).exists(),
                       'D9 error-mode must refuse float output and remove partial file')
                if with_report:
                    demand(rejected['report']['status'] == 'failed' and
                           'reconstructed PCM excursion' in rejected['report']['failure_reason'],
                           'D9 failure report must name clip as cause')
                measured.append({'scenario':'float_error','report':with_report,'bits':bits,
                                 'exit_status':rejected['rc']})
        gentle = run(sox, work, source, 'error', volume=.25)
        demand(gentle['rc'] == 0 and gentle['report']['status'] == 'complete',
               'D9 -v must be applied before adapter clip check')
        boosted = run(sox, work, source, 'error', volume=1.)
        demand(boosted['rc'] != 0 and boosted['report']['status'] == 'failed',
               'D9 -v unity did not trigger the clip')
        # Effect gain is after the adapter boundary, not an accidental second
        # pre-adapter volume; the input -v safely reduces the adapter level.
        after = run(sox, work, source, 'error', volume=.25, gain=6.)
        demand(after['rc'] == 0, 'D9 clip boundary incorrectly follows gain effect')
        measured.append({'scenario':'volume_vs_effect_gain','status':'PASS'})
        # D10: split the physical stream into quiet alternating then loud ones.
        # Error is first seen after 4096 reconstructed PCM frames, when 4054
        # completed frames have already been published to a pipe. The whole
        # newly decoded block containing the excursion must be withheld.
        later = work / 'quiet-then-hot.dsf'
        n = 131072
        later.write_bytes(fixtures.make_dsf(
            (bytes(i & 1 for i in range(n)) + bytes([1])*n,),fixtures.DSD64))
        okay = run(sox, work, later, 'warn', pipe=True)
        refused = run(sox, work, later, 'error', pipe=True)
        demand(okay['rc'] == 0 and refused['rc'] != 0,
               'D10 pipe comparison did not reach the expected failure')
        demand(0 < len(refused['payload']) < len(okay['payload']) and
               okay['payload'].startswith(refused['payload']),
               'D10 failed block was published or previous good bytes changed')
        observed_written = int(refused['report']['output']['frames_written'])
        demand(observed_written > 0 and
               len(wav_data(refused['payload'])) == observed_written * 8 and
               refused['report']['status'] == 'failed',
               'D10 pipe/report completion accounting mismatch')
        regular = run(sox, work, later, 'error', pipe=False)
        demand(regular['rc'] != 0 and regular['report']['status'] == 'failed' and
               not Path(regular['target']).exists(),
               'D10 regular-file partial output cleanup not observed')
        measured.append({'scenario':'D10_late_failure_pipe_and_regular_file',
                         'pipe_frames_published_before_failure':observed_written,
                         'full_pipe_frames':len(wav_data(okay['payload']))//8,
                         'regular_failed_file':'absent'})
        return {'schema':'phase08-d9-d10/2','status':'PASS',
                'scope':'actual DSD64 ordinary/native CLI error-parity, plus D9/D10 native fixtures; Linux/ELF boundary injection is test-only',
                'injected_adapter_checks':injected_rows,
                'injected_adapter_check_count':len(injected_rows),
                'physical_level_checks':level_rows,
                'physical_level_check_count':len(level_rows),
                'injection_source_sha256':injected_digest,
                'cases':measured,'case_count':len(measured)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sox', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    try:
        row = main(args.sox.resolve(), args.results)
    except Exception as exc:
        row = {'status': 'FAIL', 'error': str(exc)}
    (args.results / 'float-boundary.json').write_text(json.dumps(row, indent=2) + '\n')
    print('D9/D10:', row['status'], row.get('case_count', 0), 'cases',row.get('error',''))
    raise SystemExit(0 if row['status'] == 'PASS' else 1)
