#!/usr/bin/env python3
"""Opt-in long-form regression for the P10 loud-input state guard.

Uses the original 2026-11-04 synthetic recipes. The source and the tested
encoder are the same executable; the user-provided reproduction verified
that the 0dd7ad224 and 1.0.4 generators produce matching input files.

This is deliberately separate from fast check-dsd-loud-encode: sustained
SDM exposure is required to detect the original delayed failures.
"""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


RECIPES = {
    'sq100+3': ('square', '100', 'norm', '-0.1', 'gain', '3'),
    'sq1k+3': ('square', '1000', 'norm', '-0.1', 'gain', '3'),
    'saw60+6': ('sawtooth', '60', 'norm', '-0.1', 'gain', '6'),
    'tri100+6': ('triangle', '100', 'norm', '-0.1', 'gain', '6'),
    'brown+3': ('brownnoise', 'norm', '-0.1', 'gain', '3'),
    'brown+9': ('brownnoise', 'norm', '-0.1', 'gain', '9'),
    'sq100-3': ('square', '100', 'norm', '-3'),
}
RATES = (2822400, 5644800, 11289600)
CLIP_CEILING = dict.fromkeys(RATES, 0.45)
FIELDS = ('signal', 'rate', 'duration_s', 'mode', 'exit', 'clipped', 'seconds')


def run(sox, *args, limit=180):
    return subprocess.run([str(sox), *map(str, args)], capture_output=True,
                          text=True, timeout=limit,
                          env={**os.environ, 'OMP_NUM_THREADS': '1'})


def require_ok(p, label):
    assert p.returncode == 0, (
        f'{label}: exit={p.returncode}: {p.stderr[-1400:]}')
    return p


def make_fixture(sox, path, seconds, recipe):
    require_ok(run(sox, '-R', '-r', 44100, '-c', 2, '-n',
                   '-e', 'floating-point', '-b', 32, path,
                   'synth', seconds, *recipe, limit=180), str(path))


def clipped_count(stderr):
    return sum(int(n) for n in re.findall(
        r'clipped (\d+) interpolated samples', stderr))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', required=True, type=Path)
    ap.add_argument('--quick', action='store_true',
                    help='Only the earliest DSD256 guard witness and policy checks')
    ap.add_argument('--stress-seconds', type=int, default=0,
                    help='Optional extra square-wave DSD256 run, e.g. 120 or 600')
    ap.add_argument('--results', type=Path,
                    help='Optional results TSV outside the source tree')
    args = ap.parse_args()
    assert args.stress_seconds >= 0
    sox = args.sox.resolve()
    rows = []

    with tempfile.TemporaryDirectory(prefix='sox-dsd-guard-') as temp:
        root = Path(temp)
        fixtures = {}
        for name, recipe in RECIPES.items():
            if args.quick and name not in ('sq1k+3', 'sq100+3'):
                continue
            path = root / f'{name}.wav'
            make_fixture(sox, path, 20, recipe)
            fixtures[name] = path

        def encode(signal, rate, source, options=(), duration=20):
            output = root / 'output.dsf'
            output.unlink(missing_ok=True)
            start = time.monotonic()
            p = run(sox, *options, source, '-r', rate, output,
                    limit=max(180, int(duration * 3)))
            seconds = time.monotonic() - start
            rows.append(dict(signal=signal, rate=rate, duration_s=duration,
                             mode=' '.join(options) or 'default',
                             exit=p.returncode, clipped=clipped_count(p.stderr),
                             seconds=round(seconds, 3)))
            return p, output

        if not args.quick:
            for rate in RATES:
                for signal, src in fixtures.items():
                    p, out = encode(signal, rate, src)
                    require_ok(p, f'{signal} to {rate}')
                    if signal != 'sq100-3':
                        assert clipped_count(p.stderr) > 0, (
                            f'{signal} to {rate}: missing clip warning')
                    if signal == 'sq100-3' and rate == 2822400:
                        assert clipped_count(p.stderr) == 0
                    assert out.is_file(), f'no DSF after {signal} to {rate}'
                    out.unlink()
                print(f'PASS 20s 7-signal matrix at {rate}', flush=True)

        # Reproduce the earliest observed failure without lengthy processing.
        short = root / 'sq1k-0.5s.wav'
        require_ok(run(sox, fixtures['sq1k+3'], short, 'trim', '0', '0.5'),
                   'short fixture')
        p, out = encode('sq1k+3', 11289600, short, duration=0.5)
        require_ok(p, 'early guard witness')
        default_digest = digest(out)
        p, out = encode('sq1k+3', 11289600, short,
                        options=('--headroom', '0'), duration=0.5)
        require_ok(p, 'zero headroom')
        assert digest(out) != default_digest, (
            'explicit --headroom 0 must override the default constant gain')

        report = root / 'auto-report.json'
        p, out = encode('sq1k+3', 11289600, short,
                        options=('--auto-headroom', '--dsd-clip', 'error',
                                 '--report', str(report)), duration=0.5)
        require_ok(p, 'strict measured headroom')
        data = json.loads(report.read_text())
        encoders = data['processing']['encoder']
        assert len(encoders) == 2
        assert int(data['clipping']['encoder_interpolation']) == 0
        assert all(int(e['clipped_interpolated_samples']) == 0 for e in encoders)
        assert all(e['clip_ceiling_applied'] is None for e in encoders)
        assert all(e['peak_modulator_input'] <= CLIP_CEILING[11289600] + 1e-10
                   for e in encoders)
        headrooms = [e['headroom_applied_db'] for e in encoders]
        assert headrooms[0] > 0 and abs(headrooms[0] - headrooms[1]) < 1e-10
        assert clipped_count(p.stderr) == 0

        p, out = encode('sq1k+3', 11289600, short,
                        options=('--dsd-clip', 'error'), duration=0.5)
        assert p.returncode != 0, 'strict input overload unexpectedly accepted'
        assert not out.exists(), 'strict failure published output'
        print('PASS 0.5s guard witness, zero headroom, strict and auto policy',
              flush=True)

        if args.stress_seconds:
            long_source = root / 'long-square.wav'
            make_fixture(sox, long_source, args.stress_seconds,
                         RECIPES['sq100+3'])
            p, out = encode('sq100+3', 11289600, long_source,
                            duration=args.stress_seconds)
            require_ok(p, f'{args.stress_seconds}s DSD256 stress')
            assert clipped_count(p.stderr) > 0
            assert out.is_file()
            print(f'PASS {args.stress_seconds}s DSD256 stress', flush=True)

    if args.results:
        args.results.parent.mkdir(parents=True, exist_ok=True)
        with args.results.open('w', newline='') as file:
            writer = csv.DictWriter(file, delimiter='\t', fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    print(f'PASS loud guard acceptance ({len(rows)} runs)', flush=True)


if __name__ == '__main__':
    main()
