#!/usr/bin/env python3
"""D9/D10 observable native DSD float-boundary and failed-block checks.

The file creator is independent of SoX. Native DSD bits are never floats, so
nonfinite reconstruction is tested only through the existing arithmetic-guard
suite, not falsely claimed as a produced fixture here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
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
        volume=None, bits=64, pipe=False, gain=None):
    target = '-' if pipe else str(work / ('out-' + str(len(list(work.iterdir()))) + '.wav'))
    receipt = work / ('report-' + str(len(list(work.iterdir()))) + '.json')
    cmd = [str(sox), '--precision', '64', '--dsd-clip', mode,
           '--dsd-level', level]
    if volume is not None:
        cmd += ['-v', str(volume)]
    if report:
        cmd += ['--report', str(receipt)]
    cmd += [str(source), '-b', str(bits), '-e', 'floating-point',
            '-r', '88200', *(['-t', 'wav'] if pipe else []), target]
    if gain is not None:
        cmd += ['gain', str(gain)]
    cp = subprocess.run(cmd, capture_output=True, timeout=45)
    rr = json.loads(receipt.read_text()) if report and receipt.exists() else None
    payload = (cp.stdout if pipe else Path(target).read_bytes()
               if Path(target).exists() else b'')
    return {'rc': cp.returncode, 'stderr': cp.stderr.decode(errors='replace'),
            'payload': payload, 'report': rr, 'target': target, 'argv': cmd}


def main(sox, results):
    results.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='phase08-float-') as t:
        work = Path(t)
        source = work / 'constant-one.dsf'
        source.write_bytes(fixtures.make_dsf((bytes([1]) * 65536,), fixtures.DSD64))
        measured = []
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
        return {'schema':'phase08-d9-d10/1','status':'PASS',
                'scope':'actual native binary64 DSD64 CLI, signed owner outcomes D9/D10',
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
