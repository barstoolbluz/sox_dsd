#!/usr/bin/env python3
"""AM4 accepted SoX precision/dither behavior at correctly rounded gains."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import wave


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sox', type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    a = p.parse_args()
    sox = a.sox.resolve()
    with tempfile.TemporaryDirectory(prefix='p08-am4-gain-') as td:
        root = Path(td)
        src = root/'input.wav'
        samples = [i*113 % 301 - 150 for i in range(32000)]
        with wave.open(str(src),'wb') as w:
            w.setnchannels(1)
            w.setframerate(44100)
            w.setsampwidth(2)
            w.writeframes(struct.pack('<%dh' % len(samples), *samples))
        def render(name, db, *, automatic=True, explicit=False):
            out = root/(name+'.raw')
            argv = [str(sox),'-R', *([] if automatic else ['-D']),
                    str(src),'-t','raw','-e','signed-integer','-b','16',str(out),
                    'gain',str(db),*(['dither','-p','15'] if explicit else [])]
            result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            if result.returncode or not out.is_file() or out.stat().st_size != len(samples)*2:
                raise AssertionError(f'{name}: gain/dither CLI failed: {result.stderr[-550:]}')
            return out.read_bytes()
        observed = []
        for db in (20,40):
            enabled = render(f'integer-{db}-automatic',db)
            disabled = render(f'integer-{db}-noautomatic',db,automatic=False)
            if enabled != disabled:
                raise AssertionError(f'AM4: +{db} dB unexpectedly triggers automatic dither')
            observed.append({'gain_db':db, 'factor':10**(db//20),
                             'automatic_equals_disabled':True,
                             'sha256':hashlib.sha256(enabled).hexdigest()})
        auto = render('noninteger-automatic',-2.5)
        noauto = render('noninteger-disabled',-2.5,automatic=False)
        if auto == noauto:
            raise AssertionError('AM4: noninteger gain did not trigger automatic dither')
        explicit = render('integer-explicit-p15',20,automatic=False,explicit=True)
        base = render('integer-no-dither',20,automatic=False)
        if explicit == base:
            raise AssertionError('AM4: explicit dither -p 15 was bypassed')
        record = {'schema':'phase08-am4-gain-dither/1','status':'PASS',
                  'integer_factors':observed,
                  'noninteger_gain_db':-2.5,
                  'noninteger_automatic_differs_from_disabled':True,
                  'explicit_dither_precision_bits':15,
                  'explicit_dither_differs_from_disabled':True,
                  'samples':len(samples), 'random_seed_mode':'SoX -R',
                  'note':'No change to gain precision tracking or SoX dither policy'}
        a.results.mkdir(parents=True, exist_ok=True)
        (a.results/'gain-dither-policy.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print('AM4 gain/dither: +20, +40, -2.5 dB and explicit -p 15 PASS')


if __name__=='__main__':
    main()
