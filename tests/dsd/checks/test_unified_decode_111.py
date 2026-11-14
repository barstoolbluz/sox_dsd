#!/usr/bin/env python3
"""Executable 1.1.1 one-decoder contract, using locally generated PCM/DSF.

Test both global and effect-local selection, actual profile receipts and PCM
bytes, planner identity, retired selector refusal and native clock pins. This
is a regression suite, not listening tests or commercial-media qualification.
"""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

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

RATES = (2822400, 5644800, 11289600, 22579200, 45158400)


def check(condition, label, command=None):
    if not condition:
        suffix = (f"\n{command.stderr[-1200:]}" if command else '')
        raise AssertionError(label + suffix)


def invoke(sox, *args):
    return subprocess.run([str(sox), '--dsd-layout-loss', 'warn',
                           *map(str, args)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          timeout=120, env={**os.environ, 'SOX_OPTS': '',
                                            'OMP_NUM_THREADS': '1'})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pcm(path):
    hz = 176400
    n = round(.030 * hz)
    data = bytearray()
    for i in range(n):
        taper = min(1.0, i / (hz*.003), (n-1-i) / (hz*.003))
        sample = taper * .2 * (math.sin(2*math.pi*997*i/hz) +
                               .33*math.sin(2*math.pi*19001*i/hz))
        data.extend(struct.pack('<i', round(sample * (2**31-1))))
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setframerate(hz)
        f.setsampwidth(4)
        f.writeframes(data)


def test(sox, root):
    source = root / 'original.wav'
    pcm(source)
    original_hash = sha(source)
    rows = []
    for native in RATES:
        suffix = native // 44100
        dsd = root / f'fixture-{suffix}.dsf'
        enc = invoke(sox, '-D', source, '-r', native, dsd)
        check(enc.returncode == 0 and dsd.exists(), f'fixture DSD{suffix} failed', enc)
        out_hz = 88200 if suffix == 64 else 176400
        default_id = f'decode.mastering.dsd{suffix}'
        canonical = None
        for label, selectors, expected in (
                ('default', (), default_id),
                ('mastering', ('--decode', 'mastering'), default_id),
                ('pinned', ('--decode', default_id), default_id),
                ('wideband', ('--decode', 'wideband'),
                 f'decode.wideband.dsd{suffix}')):
            dest = root / f'{suffix}-{label}.f64'
            report = root / f'{suffix}-{label}.json'
            args = (*selectors, '--report', report, '-D', dsd,
                    '-t', 'f64', '-r', out_hz, dest)
            run = invoke(sox, *args)
            check(run.returncode == 0 and dest.is_file() and report.is_file(),
                  f'DSD{suffix} {label}: missing executable conversion', run)
            data = json.loads(report.read_text())
            observed = data['processing']['decoder']
            check(len(observed) == 1 and observed[0]['profile_id'] == expected,
                  f'DSD{suffix} {label}: wrong actual decoder identity: {observed}')
            digest = sha(dest)
            if label == 'default':
                canonical = digest
            elif label != 'wideband':
                check(digest == canonical,
                      f'DSD{suffix} {label} did not preserve default PCM bits')
            else:
                check(digest != canonical,
                      f'DSD{suffix} wideband unexpectedly used the standard bank')
            planned = invoke(sox, '--plan', *selectors, '-D', dsd,
                             '-t', 'f64', '-r', out_hz,
                             root / f'{suffix}-not-created.f64')
            check(planned.returncode == 0, f'DSD{suffix} {label}: plan failed', planned)
            plan = json.loads(planned.stdout)
            check(plan['decoder']['id'] == expected and plan['executable'],
                  f'DSD{suffix} {label}: plan disagrees with actual decoder')
            check(plan['policy']['decode'] == ('wideband' if label=='wideband' else 'mastering'),
                  f'DSD{suffix} {label}: policy.decode misrepresented selection')
            rows.append(dict(rate=native, kind=label, selected=expected,
                             output_sha256=digest, result='PASS'))

        # An explicit effect-local mastering request must inherit global
        # defaults and execute the same bank, never silently substitute a retired decoder.
        for label, selectors, effects in (
                ('effect-local', (), ('dsdpcm', '-p', 'mastering', str(out_hz))),
                ('effect-inherited', ('--decode', 'mastering'),
                 ('dsdpcm', str(out_hz)))):
            dest = root / f'{suffix}-{label}.f64'
            report = root / f'{suffix}-{label}.json'
            run = invoke(sox, *selectors, '--report', report, '-D', dsd,
                         '-t', 'f64', '-r', out_hz, dest, *effects)
            check(run.returncode == 0 and report.exists(),
                  f'DSD{suffix} {label}: explicit effect failed', run)
            decoder = json.loads(report.read_text())['processing']['decoder']
            check(len(decoder) == 1 and decoder[0]['profile_id'] == default_id,
                  f'DSD{suffix} {label}: wrong executed effect bank')
            check(sha(dest) == canonical,
                  f'DSD{suffix} {label}: decoded PCM differs from default')
            rows.append(dict(rate=native, kind=label, selected=default_id,
                             output_sha256=sha(dest), result='PASS'))

        for removed in ('conservative', 'legacy',
                        f'decode.mastering.v2.dsd{suffix}'):
            for label, opt, effects in (
                    ('global', ('--decode', removed), ()),
                    ('effect', (), ('dsdpcm', '-p', removed, str(out_hz)))):
                dest = root / f'{suffix}-reject-{label}-{removed}.f64'
                p = invoke(sox, *opt, '-D', dsd, '-t', 'f64',
                           '-r', out_hz, dest, *effects)
                check(p.returncode != 0 and not dest.exists(),
                      f'DSD{suffix} {label}: retired decoder spelling accepted', p)
                rows.append(dict(rate=native, kind=f'reject-{label}',
                                 selected=removed, exit_code=p.returncode, result='PASS'))
        wrong = 128 if suffix == 64 else 64
        dest = root / f'{suffix}-reject-wrong-clock.f64'
        p = invoke(sox, '--decode', f'decode.mastering.dsd{wrong}',
                   '-D', dsd, '-t', 'f64', '-r', out_hz, dest)
        check(p.returncode != 0 and not dest.exists(),
              f'DSD{suffix}: mismatched native decoder pin accepted', p)
        rows.append(dict(rate=native, kind='reject-wrong-clock',
                         exit_code=p.returncode, result='PASS'))

    check(sha(source) == original_hash, 'source mutated')
    return dict(schema='sox-dsd-unified-decode-111/1',
                sox_sha256=sha(sox), pcm_input_sha256=original_hash,
                cases=rows, passed=len(rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sox', required=True, type=Path)
    parser.add_argument('--results', type=Path)
    a=parser.parse_args()
    sox=a.sox.resolve()
    check(sox.is_file(), 'SoX executable missing')
    with tempfile.TemporaryDirectory(prefix='sox-unified-decoder-111-') as temp:
        result = test(sox, Path(temp))
    if a.results:
        a.results.parent.mkdir(parents=True,exist_ok=True)
        a.results.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(result='PASS', cases=result['passed'],
                          native_rates=RATES)))

if __name__=='__main__':
    main()
