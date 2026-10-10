#!/usr/bin/env python3
"""P10 corrective, fail-closed stage gain and noise-envelope classification.

Uses the actual composite encoder's optional READ-ONLY observer; it never
bypasses or reinterprets overload. Probe cases use separately named result
files and preserve all historical P10 evidence. Reported original-noise
measurements are *prefix only*: overload aborts the pipeline deliberately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NATIVES = (2822400, 5644800, 11289600)
SOURCES = (48000, 705600)


def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ratio(row, a, b):
    return row['stages'][a]['steady_mean'] / row['stages'][b]['steady_mean']


def run(args):
    base = args.results
    base.mkdir(parents=True, exist_ok=True)
    records = []
    for native in NATIVES:
        R = 88200 if native == NATIVES[0] else 176400
        for hz,kind,seconds,expect in (
                *((rate, 'dc', 1.5, 0) for rate in (SOURCES[0], R, SOURCES[1])),
                (R, 'original-noise', 30., 4),
                (R, 'nominal-noise', 30., 0),
                (R, 'attenuated-original-noise', 30., 0)):
            name = f'{native}-{hz}-{kind}'
            dest = base / f'{name}.json'
            command = [str(args.unit), '--stage-probe', str(native), str(hz), kind, str(seconds)]
            receipt = base / f'{name}.receipt.json'
            invocation=dict(command=command[1:],binary_sha256=sha(args.unit),
                source_sha256=sha(ROOT/'tests/dsd/test_p10.c'))
            if receipt.exists():
                prev=json.loads(receipt.read_text())
                if prev['invocation']!=invocation or sha(dest)!=prev['sha256']:
                    raise RuntimeError(name+': saved result no longer matches this executable; use a new result directory')
                data=json.loads(dest.read_text());code=prev['exit_code'];stderr=prev['stderr']
            else:
                p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
                try:
                    data = json.loads(p.stdout)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f'{name}: invalid output {p.stderr!r} {p.stdout[:200]!r}') from e
                atomic(dest, data)
                code=p.returncode;stderr=p.stderr
                atomic(receipt,dict(invocation=invocation,exit_code=code,stderr=stderr,sha256=sha(dest)))
            records.append(dict(name=name, exit_code=code,
                expected_exit_code=expect, relative_result=dest.name,
                sha256=sha(dest), stderr=stderr))
            atomic(base/'execution.json',dict(status='INCOMPLETE',probes=records))
            print(name, 'exit', code, 'peak', data['stages']['scaled_modulator_input']['peak'], flush=True)
            if code != expect:
                atomic(base/'execution.json', dict(status='FAIL', probes=records))
                return 1
    atomic(base/'execution.json', dict(status='PASS', probes=records,
        executable_sha256=sha(args.unit), source_sha256=sha(ROOT/'tests/dsd/test_p10.c'),
        labels=['noise-prefix-overload', 'versioned admitted nominal noise',
            'explicit graph PCM attenuation', 'DC unity source SRC/pre-FIR/native SRC']))
    return verify(args)


def classify(base):
    """Recompute the verdict from raw probes without modifying evidence."""
    base = Path(base)
    execution = json.loads((base/'execution.json').read_text())
    conclusions = []
    failures = []
    if execution['status'] != 'PASS':
        failures.append('stage probe execution not all complete')
    expected = {}
    for native in NATIVES:
        R = 88200 if native == NATIVES[0] else 176400
        for hz in (*SOURCES, R):
            expected[f'{native}-{hz}-dc'] = 0
        for kind in ('original-noise', 'nominal-noise', 'attenuated-original-noise'):
            expected[f'{native}-{R}-{kind}'] = 4 if kind == 'original-noise' else 0
    names = [r['name'] for r in execution['probes']]
    if len(names) != len(expected) or set(names) != set(expected):
        failures.append('stage probe coverage must contain every expected case exactly once')
    if execution.get('source_sha256') != sha(ROOT/'tests/dsd/test_p10.c'):
        failures.append('stage probe source identity differs from this generator')
    for record in execution['probes']:
        data = json.loads((base/record['relative_result']).read_text())
        if sha(base/record['relative_result']) != record['sha256']:
            failures.append(record['name'] + ': evidence hash mismatches')
        if (record['exit_code'] != record['expected_exit_code'] or
                record['exit_code'] != expected.get(record['name'])):
            failures.append(record['name'] + ': unexpected exit')
        if record['relative_result'] != record['name'] + '.json':
            failures.append(record['name'] + ': result does not identify the expected probe')
        for stage in data['stages'].values():
            if (len(stage['abs_bins_0p01']) != 101 or
                    any(not isinstance(n, int) or n < 0 for n in stage['abs_bins_0p01']) or
                    sum(stage['abs_bins_0p01']) != stage['count']):
                failures.append(record['name'] + ': distribution count mismatch')
    for native in NATIVES:
        R = 88200 if native == NATIVES[0] else 176400
        for hz in (SOURCES[0], R, SOURCES[1]):
            data = json.loads((base/f'{native}-{hz}-dc.json').read_text())
            vals = [ratio(data, 'R_SRC','source'),
                    ratio(data, 'R_prefilter','R_SRC'),
                    ratio(data, 'native_SRC','R_prefilter'),
                    ratio(data, 'scaled_modulator_input','native_SRC')]
            if data['failure'] or any(abs(v-1)>1e-7 for v in vals[:3]) or vals[3]!=.5:
                failures.append(f'{native}/{hz}: non-unity transfer or non-half reference')
            conclusions.append(dict(kind='dc',source_hz=hz,native_hz=native,
                stage_gain=vals,status='PASS' if vals[3]==.5 and all(abs(v-1)<1e-7 for v in vals[:3]) else 'FAIL'))
        probes = {}
        for kind in ('original-noise','nominal-noise','attenuated-original-noise'):
            probes[kind] = json.loads((base/f'{native}-{R}-{kind}.json').read_text())
        original,nominal,attenuated = (probes[k] for k in ('original-noise','nominal-noise','attenuated-original-noise'))
        if original['failure']!=2 or original['status']!=7 or original['first_bad_frame'] is None:
            failures.append(f'{native}: original noise did not reject on overload')
        for label, data in (('nominal', nominal), ('attenuated',attenuated)):
            sc=data['stages']['scaled_modulator_input'];src=data['stages']['source'];
            if (data['failure']!=0 or data['status']!=3 or sc['over_envelope'] or sc['peak']>.5+1e-8 or src['peak']>.450001):
                failures.append(f'{native}: {label} PCM noise not admitted')
        for label,data in probes.items():
            st=data['stages'];
            # Inspect *actual stage samples*, not a crossing-time statistical model.
            if abs(st['scaled_modulator_input']['rms'] / st['native_SRC']['rms'] - .5)>1e-14:
                failures.append(f'{native}: {label} scaling not exactly half RMS')
            if st['R_prefilter']['rms']>=st['R_SRC']['rms']:
                failures.append(f'{native}: {label} unexplained net noise gain')
        os=original['stages'];ns=nominal['stages'];ats=attenuated['stages']
        conclusions.append(dict(kind='noise-classification',native_hz=native,
            original_exit=4,original_error=original['failure'],
            original_observed_prefix_native_frames=os['scaled_modulator_input']['count'],
            original_input_peak=os['source']['peak'],
            original_R_prefilter_peak=os['R_prefilter']['peak'],
            original_post_interpolation_peak=os['native_SRC']['peak'],
            original_post_interpolation_rms=os['native_SRC']['rms'],
            original_scaled_peak=os['scaled_modulator_input']['peak'],
            original_scaled_rms=os['scaled_modulator_input']['rms'],
            original_scaled_distribution_abs_bins_0p01=os['scaled_modulator_input']['abs_bins_0p01'],
            nominal_pcm_peak=ns['source']['peak'],
            nominal_scaled_peak=ns['scaled_modulator_input']['peak'],
            nominal_scaled_rms=ns['scaled_modulator_input']['rms'],
            nominal_scaled_distribution_abs_bins_0p01=ns['scaled_modulator_input']['abs_bins_0p01'],
            explicit_pcm_attenuation_db=20*math.log10(.45/.7),
            attenuated_original_pcm_peak=ats['source']['peak'],
            attenuated_original_scaled_peak=ats['scaled_modulator_input']['peak'],
            attenuated_original_scaled_rms=ats['scaled_modulator_input']['rms'],
            observed_nominal_headroom_db=20*math.log10(.5/ns['scaled_modulator_input']['peak']),
            note='original noise measure is stopped by real overload; no extrapolated full-run distribution'))
    verdict=dict(schema='P10/corrective-classification/1',
        status='PASS' if not failures else 'FAIL',
        guidance='supported: in-envelope fixture issue, not a measurable unity-gain or reference-scaling defect' if not failures else 'conditional',
        findings=conclusions, failures=failures, source_scope='original noise prefix plus admitted 30-second noise signals; long soaks reported separately')
    return verdict


def verify(args):
    verdict = classify(args.results)
    atomic(args.results/'classification.json', verdict)
    print('stage-classification', verdict['status'], 'failures', verdict['failures'])
    return int(bool(verdict['failures']))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--verify-only',action='store_true')
    args=ap.parse_args()
    return verify(args) if args.verify_only else run(args)

if __name__=='__main__':raise SystemExit(main())
