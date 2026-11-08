#!/usr/bin/env python3
"""Release-1.1.1 strict-gain, fail-closed, and replacement-headroom gate.

Generates deterministic int32 PCM locally; no private audio, numpy, or
historical result archive is required. Tests actual CLI processing and
per-channel runtime reports, not only --plan metadata. Results may be
preserved as a JSON receipt using --results.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import wave

RATES = (11289600, 22579200, 45158400)
GAIN_DB = -20 * math.log10(0.9)
HINT = re.compile(r'minimum explicit --headroom attenuation ([0-9.eE+-]+) dB')
VALUE = re.compile(r'\bvalue ([0-9.eE+-]+), observed peak')


def pcm(path, kind):
    hz, length = 176400, 0.35
    count = round(hz * length)
    edge = round(hz * 0.02)
    signal = []
    for i in range(count):
        t = i / hz
        if kind == 'square':
            v = 1. if math.sin(2 * math.pi * 1000 * t + .1) >= 0 else -1.
        elif kind == 'limited997':
            v = max(-1., min(1., 2 * math.sin(2 * math.pi * 997 * t)))
        else:
            raise ValueError(kind)
        u = min(1., i / edge, (count - 1 - i) / edge)
        taper = u * u * (3. - 2 * u)
        signal.append(round(v * taper * (2**31 - 1)))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(4)
        w.setframerate(hz)
        w.writeframes(struct.pack('<' + 'i' * count, *signal))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(sox, *args):
    p = subprocess.run([str(sox), *map(str, args)], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=90,
                       env={**os.environ, 'SOX_OPTS': '', 'OMP_NUM_THREADS': '1'})
    return p


def require(ok, label, p=None):
    if not ok:
        extra = f'\n{p.stderr[-1200:]}' if p is not None else ''
        raise AssertionError(label + extra)


def run():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--results', type=Path)
    args = ap.parse_args()
    sox = args.sox.resolve()
    require(sox.is_file(), 'missing SoX binary')
    rows = []

    def record(label, p, **data):
        rows.append({'case': label, 'exit_code': p.returncode,
                     'command_args': data.pop('command_args', []),
                     'fail_line': next((x for x in p.stderr.splitlines()
                                        if 'FAIL pcmdsd' in x), None), **data})

    with tempfile.TemporaryDirectory(prefix='sox-dsd-111-') as temp:
        root = Path(temp)
        square = root / 'square.wav'
        limited = root / 'limited997.wav'
        inputs = {'square': pcm(square, 'square'),
                  'limited997': pcm(limited, 'limited997')}

        # The lower rate is intentionally different: strict mode there uses
        # unity gain, whereas high-rate v1 retains 0.9. Compare actual DSD
        # run reports, not the declarative plan alone.
        for rate in RATES:
            report = root / f'strict-{rate}.json'
            dst = root / f'strict-{rate}.dsf'
            opts = ('--dsd-clip', 'error', '--report', report,
                    limited, '-r', rate, dst)
            p = command(sox, *opts)
            if rate == 11289600:
                require(p.returncode != 0 and 'interpolation overload' in p.stderr,
                        f'DSD256 strict must reject the clipped 997-Hz sine', p)
                require(not dst.exists(), 'partial regular DSD256 file not removed')
                record(f'limited_strict_{rate}', p, expected='overload / unity gain')
            else:
                require(p.returncode == 0, f'DSD{rate // 44100} strict rejected test', p)
                data = json.loads(report.read_text())
                enc = data['processing']['encoder']
                require(len(enc) == 1, 'expected one runtime encoder channel')
                actual = enc[0]
                require(actual['profile_id'] == f'encode.mastering.v1.dsd{rate // 44100}',
                        f'wrong actual v1 profile at {rate}')
                require(abs(float(actual['headroom_applied_db']) - GAIN_DB) < 1e-9,
                        f'wrong actual strict gain at {rate}: {actual}')
                require(int(actual['clipped_interpolated_samples']) == 0,
                        'strict unexpectedly clipped interpolated samples')
                record(f'limited_strict_{rate}', p,
                       runtime_profile_id=actual['profile_id'],
                       runtime_headroom_db=float(actual['headroom_applied_db']),
                       clipped_interpolated_samples=actual['clipped_interpolated_samples'],
                       output_sha256=hashlib.sha256(dst.read_bytes()).hexdigest())

        # The first detected overshoot constrains absolute --headroom, not
        # how much EXTRA gain must be removed from the current mapping.
        for rate, cut in ((11289600, .5), (22579200, None),
                          (45158400, None), (22579200, 0.)):
            opt = (['--dsd-clip', 'error'] +
                   (['--headroom', str(cut)] if cut is not None else []))
            dst = root / f'fail-{rate}-{cut}.dsf'
            p = command(sox, *opt, square, '-r', rate, dst)
            require(p.returncode != 0 and 'interpolation overload' in p.stderr,
                    f'missing strict overload at {rate}, {cut}', p)
            require(not dst.exists(), 'failed regular DSF file was not removed')
            hint = HINT.search(p.stderr)
            bad = VALUE.search(p.stderr)
            require(bool(hint and bad), 'missing first-sample total-headroom hint', p)
            value = abs(float(bad.group(1)))
            suggested = float(hint.group(1))
            old_gain_db = GAIN_DB if cut is None and rate >= 22579200 else (cut or 0.)
            expected = old_gain_db + 20 * math.log10(value / .5)
            require(abs(suggested - expected) < 1e-7,
                    f'wrong replacement-headroom hint: {suggested} vs {expected}', p)
            require(suggested > old_gain_db,
                    'replacement-headroom lower bound did not include prior cut', p)
            record(f'strict_hint_{rate}_{cut}', p,
                   applied_headroom_db=old_gain_db,
                   first_rejected_value=float(bad.group(1)),
                   suggested_total_headroom_db=suggested,
                   expected_total_headroom_db=expected,
                   output_removed=True)

        # Rate bindings prevent accidentally claiming the internally
        # qualified v2 encoder can still be CLI-pinned at high rates.
        for rate in (22579200, 45158400):
            ident = f'encode.mastering.v2.dsd{rate // 44100}'
            dst = root / f'pin-{rate}.dsf'
            p = command(sox, '--encode', ident, limited, '-r', rate, dst)
            require(p.returncode != 0 and not dst.exists() and '--encode:' in p.stderr,
                    f'CLI unexpectedly accepted former v2 pin {ident}', p)
            record(f'old_v2_pin_unavailable_{rate}', p, profile_id=ident)

        receipt = dict(schema='sox-dsd-1.1.1-review-strict/1',
                       sox_sha256=hashlib.sha256(sox.read_bytes()).hexdigest(),
                       input_sha256=inputs, cases=rows, passed=len(rows))
        if args.results:
            args.results.parent.mkdir(parents=True, exist_ok=True)
            args.results.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(dict(result='PASS', cases=len(rows),
                              rates=list(RATES),
                              first_high_rate_hint_db=next(
                                  r['suggested_total_headroom_db'] for r in rows
                                  if r['case'] == 'strict_hint_22579200_None'))))


if __name__ == '__main__':
    run()
