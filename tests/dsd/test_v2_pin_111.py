#!/usr/bin/env python3
"""Release-1.1.1 high-rate v2 pin acceptance, using executable conversions.

A separate pre-0001 baseline comparison is required to prove 1.1.0 binary
compatibility; this gate tests current v1/v2 identity, strict/warn gain,
exact native-rate binding, explicit effect precedence, and replay behavior.
No external audio, scientific packages, or private fixtures are needed.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

NATIVE = (22579200, 45158400)
GAIN_V1 = -20 * math.log10(.9)


def require(ok, msg, p=None):
    if not ok:
        raise AssertionError(msg + (f'\n{p.stderr[-1800:]}' if p else ''))


def filehash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pcm(path):
    rate, count = 176400, int(.07 * 176400)
    b = bytearray()
    for i in range(count):
        env = min(1., i/(rate*.008), (count-1-i)/(rate*.008))
        for f in (997, 1571):
            x = .18 * env * math.sin(2 * math.pi * f * i / rate)
            b += struct.pack('<i', int(x * (2**31 - 1)))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(4)
        w.setframerate(rate)
        w.writeframes(b)


def run(exe, *opts):
    return subprocess.run([str(exe), *map(str, opts)],
                          stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=150,
                          env={**os.environ, 'SOX_OPTS': '', 'OMP_NUM_THREADS': '1'})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', required=True, type=Path)
    ap.add_argument('--results', type=Path)
    args = ap.parse_args()
    exe = args.sox.resolve()
    require(exe.is_file(), 'missing executable')
    cases = []
    with tempfile.TemporaryDirectory(prefix='sox-111-v2-') as t:
        root = Path(t)
        src = root/'independent-stereo.wav'
        pcm(src)
        input_sha256 = filehash(src)
        for native in NATIVE:
            mult = native // 44100
            v1, v2 = (f'encode.mastering.v{v}.dsd{mult}' for v in (1, 2))
            for mode in ('warn', 'error'):
                expected_v1_hash = None
                for label, prefix, ident in (
                        ('default', [], v1),
                        ('alias', ['--encode', 'mastering'], v1),
                        ('v1', ['--encode', v1], v1),
                        ('v2', ['--encode', v2], v2)):
                    profile_gain = 1. if mode == 'error' and label == 'v2' else .9
                    prefix = ['--dsd-clip', mode, *prefix]
                    dst = root/f'{mult}-{mode}-{label}.dsf'
                    report = root/f'{mult}-{mode}-{label}.json'
                    cmd = [*prefix, '--report', report, src, '-r', native, dst]
                    p = run(exe, *cmd)
                    require(p.returncode == 0 and dst.is_file() and report.is_file(),
                            f'{label} DSD{mult} {mode} executable path rejected', p)
                    rows = json.loads(report.read_text())['processing']['encoder']
                    require(len(rows) == 2, f'{label} DSD{mult} wrong channel-row count')
                    for ch in rows:
                        require(ch['profile_id'] == ident, f'{label} DSD{mult}: wrong executed ID')
                        applied = float(ch['headroom_applied_db'])
                        expected_db = -20 * math.log10(profile_gain)
                        require(abs(applied - expected_db) < 1e-9,
                                f'{label} DSD{mult} {mode}: wrong executed gain {applied}')
                        require(int(ch['clipped_interpolated_samples']) == 0,
                                f'{label} DSD{mult}: quiet stimulus clipped')
                    digest = filehash(dst)
                    if label == 'default':
                        expected_v1_hash = digest
                    if label in ('alias', 'v1'):
                        require(digest == expected_v1_hash,
                                f'DSD{mult} {mode}: default, alias, exact v1 not identical')
                    if label == 'v2':
                        require(digest != expected_v1_hash,
                                f'DSD{mult} {mode}: v2 selected v1 modulator audio')
                    plan = run(exe, '--plan', *prefix, src, '-r', native,
                               root/'plan-output.dsf')
                    require(plan.returncode == 0, f'{label} DSD{mult} --plan failed', plan)
                    planned = json.loads(plan.stdout)
                    require(planned['encoder']['id'] == ident and planned['executable'],
                            f'DSD{mult} {mode}: plan identity or executable status differs')
                    require(planned['policy']['encode'] == (ident if label == 'v2' else 'mastering'),
                            f'DSD{mult} {mode}: policy.encode conceals selected encoder pin')
                    require(abs(planned['encoder']['planned_linear_gain'] - profile_gain) < 1e-14,
                            f'DSD{mult} {mode}: plan gain differs from execution')
                    cases.append(dict(case=f'{mult}_{mode}_{label}',
                                      profile_id=ident, planned_gain=profile_gain,
                                      runtime_gain_db=rows[0]['headroom_applied_db'],
                                      output_sha256=digest, status='PASS'))

            # Exact effect-local v2 and global v2 with an explicit unpinned
            # pcmdsd must give the same bits as a global implicit route.
            for label, options, effect in (
                    ('global', ['--encode', v2], []),
                    ('local', [], ['pcmdsd', '-p', v2, str(native)]),
                    ('inherited', ['--encode', v2], ['pcmdsd', str(native)])):
                dst = root/f'{mult}-strict-explicit-{label}.dsf'
                report = root/f'{mult}-strict-explicit-{label}.json'
                p = run(exe, '--dsd-clip', 'error', *options, '--report', report,
                        src, '-r', native, dst, *effect)
                require(p.returncode == 0, f'DSD{mult} {label} explicit path fails', p)
                rows = json.loads(report.read_text())['processing']['encoder']
                require(len(rows) == 2 and all(ch['profile_id'] == v2 and
                        abs(float(ch['headroom_applied_db'])) < 1e-9 for ch in rows),
                        f'DSD{mult} {label}: runtime v2 identity/gain lost')
                expected = root/f'{mult}-error-v2.dsf'
                require(dst.read_bytes() == expected.read_bytes(),
                        f'DSD{mult} {label}: wrong actual v2 processing bits')
                cases.append(dict(case=f'{mult}_strict_explicit_{label}',
                                  profile_id=v2, status='PASS', output_sha256=filehash(dst)))

            # Auto scan/replay must retain v2 instead of recreating default v1.
            for label, pin in (('v1', v1), ('v2', v2)):
                dst = root/f'{mult}-replay-{label}.dsf'
                report = root/f'{mult}-replay-{label}.json'
                p = run(exe, '--auto-headroom', '--dsd-clip', 'error', '--encode', pin,
                        '--report', report, src, '-r', native, dst)
                require(p.returncode == 0, f'DSD{mult} {label}: replay failed', p)
                rows = json.loads(report.read_text())['processing']['encoder']
                require(len(rows) == 2 and all(row['profile_id'] == pin and
                        abs(float(row['headroom_applied_db'])) < 1e-9 for row in rows),
                        f'DSD{mult} {label}: replay lost encoder selection or gain')
                # At safe levels measured replay uses gain 1; compare with
                # explicit gain 1, not with the (different) implicit default.
                fixed = root/f'{mult}-fixed-{label}.dsf'
                p = run(exe, '--headroom', '0', '--dsd-clip', 'error', '--encode', pin,
                        src, '-r', native, fixed)
                require(p.returncode == 0 and dst.read_bytes() == fixed.read_bytes(),
                        f'DSD{mult} {label}: replay not equal to unity-gain output', p)
                cases.append(dict(case=f'{mult}_auto_replay_{label}',
                                  profile_id=pin, status='PASS',
                                  output_sha256=filehash(dst)))

            for label, flags, effect in (
                    ('wrong_rate_pin', ['--encode', v2], []),
                    ('wrong_rate_local', [], ['pcmdsd', '-p', v2, str(native)]),
                    ('conflict', ['--encode', v2], ['pcmdsd', '-p', v1, str(native)]),
                    ('unknown', ['--encode', f'encode.mastering.v2.dsd256'], [])):
                dst = root/f'{mult}-reject-{label}.dsf'
                rate = 45158400 if native == 22579200 else 22579200
                if label not in ('wrong_rate_pin', 'wrong_rate_local'):
                    rate = native
                p = run(exe, *flags, src, '-r', rate, dst, *effect)
                require(p.returncode != 0 and not dst.exists(),
                        f'DSD{mult} {label}: invalid pin accepted or partial output', p)
                cases.append(dict(case=f'{mult}_reject_{label}', status='PASS',
                                  exit_code=p.returncode, stderr_tail=p.stderr[-500:]))

        require(filehash(src) == input_sha256, 'input was modified')
        receipt = dict(schema='sox-dsd-111-v2-pin-regression/1',
                       sox_sha256=filehash(exe), input_sha256=input_sha256,
                       cases=cases, passed=len(cases))
        if args.results:
            args.results.parent.mkdir(parents=True, exist_ok=True)
            args.results.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(result='PASS', cases=len(cases), native_rates=NATIVE)))


if __name__ == '__main__':
    main()
