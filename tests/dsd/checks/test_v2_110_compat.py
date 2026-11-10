#!/usr/bin/env python3
"""Compare the *actual* selected v2 output with the 1.1.0 implementation.

The caller must supply two independently built binaries: 1.1.0 before the
1.1.1 review patches and the candidate. This script never treats an
old receipt as proof of identity: it runs both encoders, checks the runtime
profile identity and gain, and compares byte-for-byte container outputs.
No licensed inputs are required. Builds/provenance are caller obligations.
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
from pathlib import Path
import struct
import tempfile
import wave

from test_v2_pin_111 import pcm, require, filehash, run


def hotter_pcm(path):
    rate, count = 176400, int(.07*176400)
    data = bytearray()
    for i in range(count):
        envelope = min(1., i/(rate*.009), (count - i - 1)/(rate*.009))
        for f in (1307, 2879):
            t = i/rate
            x = envelope * (.54*math.sin(2*math.pi*f*t) +
                            .10*math.sin(2*math.pi*7219*t))
            data.extend(struct.pack('<i', int(x*(2**31 - 1))))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(4)
        w.setframerate(rate)
        w.writeframes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--old-sox', required=True, type=Path)
    ap.add_argument('--new-sox', required=True, type=Path)
    ap.add_argument('--results', type=Path)
    a = ap.parse_args()
    old, new = a.old_sox.resolve(), a.new_sox.resolve()
    require(old.is_file() and new.is_file(), 'both built executable paths are required')
    rows = []
    with tempfile.TemporaryDirectory(prefix='sox-v2-110-compat-') as d:
        root = Path(d)
        normal, louder = root/'quiet.wav', root/'multi.wav'
        pcm(normal)
        hotter_pcm(louder)
        hashes = {f.name: filehash(f) for f in (normal, louder)}
        for native in (22579200, 45158400):
            pin = f'encode.mastering.v2.dsd{native//44100}'
            for src in (normal, louder):
                for ext in ('dsf', 'dff'):
                    for mode in ('warn', 'error'):
                        label = f'{native//44100}_{src.stem}_{ext}_{mode}'
                        digest = None
                        for version, exe in (('original-1.1.0', old), ('corrected', new)):
                            out = root/f'{label}-{version}.{ext}'
                            report = root/f'{label}-{version}.json'
                            cmd = ['--encode', pin, '--dsd-clip', mode,
                                   '--report', report, src, '-r', native, out]
                            p = run(exe, *cmd)
                            require(p.returncode == 0 and out.is_file() and report.is_file(),
                                    f'{label} {version}: run unsuccessful', p)
                            runtime = json.loads(report.read_text())['processing']['encoder']
                            expected_db = -20 * math.log10(.9) if mode == 'warn' else 0.
                            require(len(runtime) == 2 and all(
                                c['profile_id'] == pin and
                                abs(c['headroom_applied_db'] - expected_db) < 1e-9
                                for c in runtime),
                                f'{label} {version}: runtime profile or gain drift')
                            output_digest = filehash(out)
                            if digest is None:
                                digest = output_digest
                            else:
                                require(output_digest == digest,
                                        f'{label}: v2 container audio differs from 1.1.0')
                        rows.append(dict(case=label, profile_id=pin,
                                         output_sha256=digest, status='PASS'))

            # The measured replay must keep the old v2 modulation bits and
            # the same unity-gain input envelope at both native rates.
            for label, options in (
                ('auto-strict', ['--auto-headroom', '--dsd-clip', 'error']),
                ('fixed-strict', ['--headroom', '0', '--dsd-clip', 'error'])):
                digest = None
                for version, exe in (('original-1.1.0', old), ('corrected', new)):
                    out = root/f'{native//44100}-{label}-{version}.dsf'
                    report = root/f'{native//44100}-{label}-{version}.json'
                    p = run(exe, '--encode', pin, *options, '--report', report,
                            normal, '-r', native, out)
                    require(p.returncode == 0 and out.is_file(),
                            f'{native//44100} {label} {version}: failed', p)
                    runtime = json.loads(report.read_text())['processing']['encoder']
                    require(len(runtime) == 2 and all(
                        c['profile_id'] == pin and
                        abs(c['headroom_applied_db']) < 1e-9 for c in runtime),
                        f'{native//44100} {label} {version}: wrong v2 identity/gain')
                    value = filehash(out)
                    if digest is None: digest = value
                    else: require(value == digest, f'{native//44100} {label}: bytes differ')
                rows.append(dict(case=f'{native//44100}_{label}',
                                 profile_id=pin, status='PASS', output_sha256=digest))
        require(filehash(normal) == hashes[normal.name] and
                filehash(louder) == hashes[louder.name], 'input bytes mutated')
        receipt = dict(schema='sox-dsd-111-v2-110-compatibility/1',
                       old_sox_sha256=filehash(old), new_sox_sha256=filehash(new),
                       input_sha256=hashes, cases=rows, passed=len(rows))
        if a.results:
            a.results.parent.mkdir(parents=True, exist_ok=True)
            a.results.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(result='PASS', comparisons=len(rows),
                              rates=[512, 1024], formats=['dsf', 'dff'])))


if __name__ == '__main__':
    main()
