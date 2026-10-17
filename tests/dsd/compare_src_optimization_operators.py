#!/usr/bin/env python3
"""Compare the existing C source-operator export on both runtime builds.

This checks coefficient words, realized FFT bins, stage graph, and initial
clock/support metadata. It does not perform spectral or arithmetic certification.
"""
import argparse
import json
from pathlib import Path
import subprocess

from profile_decode import atomic_json, sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    a = ap.parse_args()
    probes = {'baseline': a.baseline.resolve(), 'candidate': a.candidate.resolve()}
    dest = a.results.resolve()
    if any(not p.is_file() for p in probes.values()):
        ap.error('both existing stage-export probes are required')
    if dest.exists() and any(dest.iterdir()):
        ap.error('refusing nonempty results directory')
    dest.mkdir(parents=True, exist_ok=True)
    report = dict(schema='sox/src-optimization-operator-identity/1', status='RUNNING',
                  scope='coefficient/graph/clock identity only; not P15 certification',
                  probes={n:dict(path=str(p), sha256=sha256(p)) for n,p in probes.items()},
                  cases=[], errors=[])
    save = lambda: atomic_json(dest/'identity.json', report)
    save()
    try:
        for ir in (88200, 176400, 352800):
            for rate in (44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000, 705600):
                if ir == rate:
                    continue
                row = dict(input_hz=ir, output_hz=rate, variants={})
                data = {}
                for name, probe in probes.items():
                    output = dest/f'{ir}-{rate}-{name}.json'
                    command = [str(probe), str(ir), str(rate), str(output)]
                    run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                    if run.returncode:
                        raise RuntimeError(f'{name} export {ir}->{rate}: {run.returncode}: {run.stderr.decode(errors="replace")}')
                    data[name] = output.read_bytes()
                    row['variants'][name] = dict(command=command, file=output.name, sha256=sha256(output))
                row['byte_identical'] = data['baseline'] == data['candidate']
                snapshot = json.loads(data['candidate'])
                row['stage_count'] = snapshot['stage_count']
                row['rational_stages'] = [s['index'] for s in snapshot['stages']
                                          if s['kind'] == 3 and s['order'] == 0]
                report['cases'].append(row)
                if not row['byte_identical']:
                    raise RuntimeError(f'operator export changed at {ir}->{rate}')
                save()
        report['status'] = 'PASS-IDENTITY'
        report['nonidentity_rate_pairs'] = len(report['cases'])
        report['pairs_with_rational_fir_stage'] = sum(bool(r['rational_stages']) for r in report['cases'])
    except Exception as exc:
        report['status'] = 'FAIL'
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    save()
    print(report['status'], len(report['cases']), 'rate pairs', flush=True)
    return int(report['status'] != 'PASS-IDENTITY')


if __name__ == '__main__':
    raise SystemExit(main())
