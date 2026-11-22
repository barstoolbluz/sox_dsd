#!/usr/bin/env python3
"""D6 finite MP high-precision witnesses of the PRODUCTION-compiled exp10 object.

Does not claim a universal theorem, substitute for D15 owner adoption, or
relabel the historical glibc pow/exp witnesses as CORE-MATH evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shlex
import struct
import subprocess
import tempfile
import wave

import mpmath as mp

SOURCE = Path(__file__).resolve().parents[3]


def bits(x: float) -> int:
    return struct.unpack('>Q', struct.pack('>d', x))[0]


def value(b: int) -> float:
    return struct.unpack('>d', struct.pack('>Q', b))[0]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv: list[str], **kw) -> subprocess.CompletedProcess:
    p = subprocess.run(argv, capture_output=True, text=True, **kw)
    if p.returncode:
        raise RuntimeError(f'{argv!r}: exit {p.returncode}: {p.stderr[-2500:]}')
    return p


def cli_identity(sox: Path, temp: Path) -> dict:
    inp = temp / 'gain-input.wav'
    raw = [-2147483648, -2147483647, -1073741824, -65537, -1, 0, 1,
           32767, 65535, 1073741823, 2147483646, 2147483647]
    samples = (raw * 8)[:96]
    with wave.open(str(inp), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(4)
        w.setframerate(88200)
        w.writeframes(struct.pack('<%di' % len(samples), *samples))
    norm_inp = temp / 'norm-input.wav'
    with wave.open(str(norm_inp), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(4)
        w.setframerate(88200)
        w.writeframes(struct.pack('<%di' % len(samples),
                                  *(x // 4 for x in samples)))
    results = {}
    for name, effects in (('control', []), ('gain-0', ['gain', '0']),
                          ('gain-negzero', ['gain', '-0']),
                          ('gain-pluszero', ['gain', '+0']),
                          ('normalize-control', []),
                          ('normalize-run', ['gain', '-n', '0']),
                          ('limiter', ['gain', '-l', '0']),
                          ('headroom-mode', ['gain', '-h', '0'])):
        out = temp / f'{name}.raw'
        argv = [str(sox), '-R', '-D', '-V0', str(norm_inp if name.startswith('normalize-') else inp), '-t', 'raw',
                '-e', 'signed-integer', '-b', '32', '-L', str(out), *effects]
        command(argv)
        results[name] = sha(out)
    for name in ('gain-0', 'gain-negzero', 'gain-pluszero'):
        if results[name] != results['control']:
            raise AssertionError(f'{name} changed raw sample words')
    if results['normalize-run'] == results['normalize-control']:
        raise AssertionError('gain -n 0 was incorrectly bypassed')
    return {'frames': len(samples) // 2, 'input_32bit_values': len(raw),
            'plain_gain_words_identical': True,
            'normalization_remains_distinct': True,
            'other_mode_runs': ['-l', '-h'], 'output_sha256': results}


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, default=SOURCE)
    ap.add_argument('--build', type=Path, default=SOURCE)
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = ap.parse_args()
    source = args.source.resolve()
    build = args.build.resolve()
    sox = args.sox.resolve()
    obj = build / 'src/coremath/.libs/libsox_ng_la-exp10.o'
    if not obj.exists():
        obj = build / 'src/coremath/libsox_ng_la-exp10.o'
    if not obj.is_file() or not sox.is_file():
        raise RuntimeError('production CORE-MATH object or sox executable missing')
    test_c = source / 'tests/pcm64/qualification/coremath_gain_probe.c'
    src_c = source / 'src/coremath/exp10.c'
    expected_blob = '94f9f21eec1ea74bbc169bd4937c6792e933f26a'
    actual_blob = command(['git', '-C', str(source), 'hash-object', str(src_c)]).stdout.strip()
    if actual_blob != expected_blob:
        raise AssertionError('CORE-MATH source blob identity mismatch')
    if not test_c.exists():
        raise RuntimeError('test probe source missing')
    values = [0.0, -0.0, 1.0, -1.0, .5, -.5, 3.0, -3.0, 6.0, -6.0,
              20.0, -20.0, 60.0, -60.0, 120.0, -120.0,
              240.0, -240.0, 320.0, -320.0, 1e-8, -1e-8,
              2.0 ** -1074, -(2.0 ** -1074)]
    cases = [v for y in values for v in (y, math.nextafter(y, -math.inf),
                                          math.nextafter(y, math.inf))]
    rng = random.Random(20261121)
    cases += [rng.uniform(-320.0, 320.0) for _ in range(600)]
    cases += [float(x) for x in ['0.915', '-0.915', '3.0103', '6.0206',
                                   '0.0001', '-0.0001']]
    cases = list(dict.fromkeys(bits(x) for x in cases))
    entries = [('g', v) for v in cases] + [('h', v) for v in cases]
    entries += [('g', bits(float('inf'))), ('g', bits(float('-inf'))),
                ('g', bits(float('nan'))), ('h', bits(float('inf'))),
                ('h', bits(float('-inf'))), ('h', bits(float('nan')))]
    # Direct calls into the production CORE-MATH object cover the LLP64
    # mask/shift boundary paths that ordinary admitted dB inputs do not reach.
    direct_values = [-350.0, -325.0, -324.0, -323.0, -310.0, -308.0,
                     -1.0, -0.0, 0.0, 1.0, 308.0, 310.0, 350.0,
                     float('-inf'), float('inf'), float('nan')]
    entries += [('x', bits(x)) for x in direct_values]
    payload = ''.join(f'{mode} {b:016x}\n' for mode, b in entries)
    with tempfile.TemporaryDirectory(prefix='coremath-d6-') as dirname:
        tmp = Path(dirname)
        probe = tmp / 'coremath_gain_probe'
        cc = shlex.split(args.cc)
        command([*cc, '-O2', '-std=c11', '-fno-fast-math', '-ffp-contract=off',
                 '-fexcess-precision=standard', '-frounding-math',
                 '-I', str(source / 'src'), str(test_c), str(obj), '-lm',
                 '-o', str(probe)])
        p = command([str(probe)], input=payload)
        results = p.stdout.splitlines()
        if len(results) != len(entries):
            raise AssertionError('probe output case count mismatch')
        with mp.workdps(140):
            ln10 = mp.log(10)
            max_ideal_rel = mp.mpf(0)
            max_form_rel = mp.mpf(0)
            max_exp10_ulp = mp.mpf(0)
            checks = []
            direct_checks = []
            for (mode, dbbits), line in zip(entries, results):
                a, source_bits, x_bits, y_bits = line.split()
                if a != mode or int(source_bits, 16) != dbbits:
                    raise AssertionError('probe input mismatch')
                db = value(dbbits)
                x, y = value(int(x_bits, 16)), value(int(y_bits, 16))
                if not math.isfinite(db):
                    if math.isnan(db):
                        if not math.isnan(y):
                            raise AssertionError('NaN propagation mismatch')
                    elif math.isinf(db):
                        target = float('inf') if (db > 0) != (mode == 'h') else 0.0
                        if y != target:
                            raise AssertionError('infinity handling mismatch')
                    continue
                if mode == 'x':
                    if bits(x) != bits(db):
                        raise AssertionError('direct CORE-MATH argument mismatch')
                    exact_direct = mp.power(10, mp.mpf(x))
                    expected_direct = float(exact_direct)
                    if bits(y) != bits(expected_direct):
                        raise AssertionError(f'direct CORE-MATH mismatch x={db.hex()} '
                                             f'observed={y.hex()} '
                                             f'expected={expected_direct.hex()}')
                    direct_checks.append({'input_hex': db.hex(), 'observed_hex': y.hex(),
                                          'reference_hex': expected_direct.hex(),
                                          'kind': ('overflow' if math.isinf(y) else
                                                   'underflow' if y == 0.0 else
                                                   'subnormal' if y < 2.0 ** -1022 else
                                                   'normal')})
                    continue
                d = -db if mode == 'h' else db
                expected_arg = d / 20.0
                if bits(x) != bits(expected_arg):
                    raise AssertionError('binary64 argument rounding mismatch')
                exact_at_x = mp.power(10, mp.mpf(x))
                expected_y = float(exact_at_x)
                if bits(y) != bits(expected_y):
                    raise AssertionError(f'CORE-MATH mismatch {mode} db={db.hex()} '
                                         f'x={x.hex()} observed={y.hex()} '
                                         f'expected={expected_y.hex()}')
                # Independently calculate the exactly parsed dB's ideal exponent.
                exact_t = mp.mpf(d) / 20
                exact_ideal = mp.power(10, exact_t)
                formation = mp.expm1(ln10 * abs(mp.mpf(x) - exact_t))
                final_rel = abs(mp.mpf(y) - exact_at_x) / exact_at_x
                ideal_rel = abs(mp.mpf(y) - exact_ideal) / exact_ideal
                # Valid for these normal finite results; all tested outputs
                # are in the normal range and no overflow route is admitted.
                half_ulp = mp.mpf(math.ulp(y)) / 2
                if not (abs(y) >= 2.0 ** -1022):
                    raise AssertionError('normal-only envelope used outside normal range')
                if abs(mp.mpf(y) - exact_at_x) > half_ulp:
                    raise AssertionError('sampled final rounding exceeds half an ULP')
                if ideal_rel > formation + final_rel * (1 + formation) + mp.mpf('1e-120'):
                    raise AssertionError('argument + output error composition failed')
                max_ideal_rel = max(max_ideal_rel, ideal_rel)
                max_form_rel = max(max_form_rel, formation)
                max_exp10_ulp = max(max_exp10_ulp,
                                    abs(mp.mpf(y) - exact_at_x) / mp.mpf(math.ulp(y)))
                if db in (0., 20., -20., 120., -120., 3., -3.):
                    checks.append({'mode': mode, 'db_hex': db.hex(),
                                   'argument_hex': x.hex(), 'factor_hex': y.hex(),
                                   'reference_at_rounded_argument_hex': expected_y.hex(),
                                   'ideal_relative_error': mp.nstr(ideal_rel, 18),
                                   'formation_bound': mp.nstr(formation, 18)})
            for mode, dbbits in [('g', bits(0.0)), ('g', bits(-0.0)),
                                  ('h', bits(0.0)), ('h', bits(-0.0))]:
                i = entries.index((mode, dbbits))
                if int(results[i].split()[3], 16) != bits(1.0):
                    raise AssertionError('signed-zero exact unity violated')
            plus20 = entries.index(('g', bits(20.0)))
            if int(results[plus20].split()[3], 16) != bits(10.0):
                raise AssertionError('exact +20dB -> 10 factor violated')
            identity = cli_identity(sox, tmp)
            record = {
                'schema': 'phase08-coremath-d6/1',
                'status': 'PASS_FINITE_WITNESSES_OWNER_OPEN',
                'git_commit': command(['git', '-C', str(source), 'rev-parse', 'HEAD']).stdout.strip(),
                'coremath_git_blob': actual_blob,
                'coremath_sha256': sha(src_c),
                'compiled_production_object': str(obj),
                'compiled_production_object_sha256': sha(obj),
                'shipped_sox_sha256': sha(sox),
                'shipped_library_sha256': (sha(build / 'src/.libs/libsox_ng.so')
                                           if (build / 'src/.libs/libsox_ng.so').exists()
                                           else None),
                'test_probe_source_sha256': sha(test_c),
                'compiler': command([*cc, '--version']).stdout.splitlines()[0],
                'architecture': platform.machine(),
                'fenv_premises': 'FE_TONEAREST, FLT_EVAL_METHOD=0, FMA, gradual underflow; verified by linked probe',
                'probe_uses_compiled_production_exp10_object': True,
                'finite_normal_cases_verified': len(entries) - 6 - len(direct_values),
                'direct_coremath_finite_cases_verified': len(direct_checks),
                'direct_coremath_nonfinite_cases_verified': 3,
                'direct_coremath_representative_results': direct_checks,
                'nonfinite_cases_verified': 6,
                'factor_correctly_rounded_at_x_in_sample': True,
                'max_exp10_output_error_ulp_sample': float(max_exp10_ulp),
                'max_argument_formation_relative_bound_sample': mp.nstr(max_form_rel, 18),
                'max_factor_relative_error_vs_exact_binary64_db_sample': mp.nstr(max_ideal_rel, 18),
                'zero_and_20_db_exact': True,
                'identity_graph': identity,
                'selected': checks,
                'd6_universal_correct_rounding_proof_for_compiled_binary': 'OPEN_CONDITIONAL_ON_PINNED_CORE_MATH_AND_BUILD_PREMISES',
                'd6_input_rounding_argument_formation_bound': 'conditional analytic bound; not universal empirical proof',
                'd11_fft4g_all_input_error': 'OPEN',
                'd16_accepted_decoder_words': 'OPEN',
                'd4_cross_isa': 'OPEN',
                'release_authorized': False,
            }
    args.results.mkdir(parents=True, exist_ok=True)
    target = args.results / 'coremath-gain-reference.json'
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(f'D6 CORE-MATH finite qualification PASS: {record["finite_normal_cases_verified"]} normal, '
          f'6 nonfinite, {record["direct_coremath_finite_cases_verified"]} direct exp10 '+
          f'finite boundary cases, 3 direct nonfinite, unity sample-word identity; universal gates OPEN')


if __name__ == '__main__':
    run()
