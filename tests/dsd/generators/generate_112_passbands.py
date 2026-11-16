#!/usr/bin/env python3
"""Generate the DSD256/512/1024 replacement mastering FIRs.

95-digit Kaiser-windowed sinc -> exactly symmetric binary64 coefficients.
The 256 and 1024 profiles deliberately share a bank where normalized P/S
are identical. Existing P06 and P10 coefficient authority stays untouched.
This script is reproducible; numerical acceptance is a separate verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import mpmath as mp
import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_coeffs import design, hexdigest

mp.mp.dps = 95
A = mp.mpf(190)
BETA = mp.mpf('19.97926')
# Name, working-clock numerator, pass, stop, denominator relative to working.
# Every entry is a non-decimating encoder FIR at R, or a decoder FIR at 2R.
BANKS = {
    'encoder': [
        ('master256_1024', 352800, 60000, 100000),
        ('master512', 352800, 88200, 148200),
    ],
    'decoder': [
        ('master256_1024', 705600, 60000, 100000),
        ('master512', 705600, 88200, 148200),
    ],
}
PROFILES = {
    256: dict(native_hz=11289600, intermediate_hz=352800, pass_hz=60000, stop_hz=100000, bank='master256_1024'),
    512: dict(native_hz=22579200, intermediate_hz=352800, pass_hz=88200, stop_hz=148200, bank='master512'),
    1024: dict(native_hz=45158400, intermediate_hz=705600, pass_hz=120000, stop_hz=200000, bank='master256_1024'),
}


def freq_check(values, p, s):
    """Fast search for a sufficient bank; independently refine later."""
    h = np.asarray(values, dtype=np.float64)
    response = np.fft.rfft(h, 262144)
    # FFT is at 0..Nyquist; round outward so no unsafe boundary samples enter.
    ni = len(response)-1
    p_idx = math.ceil(p * 2 * ni)
    s_idx = math.floor(s * 2 * ni)
    small = np.abs(response)
    max_pass = float(np.max(np.abs(20*np.log10(small[:p_idx+2]))))
    max_stop = float(np.max(small[s_idx-1:]))
    return max_pass, -20*math.log10(max(max_stop, 1e-300))


def write_header(group, found):
    hdr = [f'/* SoX DSD 1.1.2 mastering {group} filters; generated, do not hand-edit. */',
           f'#ifndef LSX_DSD_112_{group.upper()}_H', f'#define LSX_DSD_112_{group.upper()}_H', '']
    for name, h in found.items():
        hdr += [f'static const double lsx_dsd112_{group}_{name}[{len(h)}] = {{']
        for j in range(0, len(h), 4):
            hdr.append('  '+', '.join(v.hex() for v in h[j:j+4])+(',' if j+4 < len(h) else ''))
        hdr += ['};', '']
    hdr += ['#endif', '']
    return '\n'.join(hdr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = {
        'schema': 'sox-dsd/1.1.2/mastering-fir/1',
        'generator': 'tests/dsd/generators/generate_112_passbands.py',
        'attenuation_design_db': 190,
        'beta': str(BETA),
        'arithmetic': 'mpmath 95 decimal digits, round symmetric pairs to IEEE-754 binary64',
        'hash_algorithm': 'SHA256 of newline-delimited float.hex words, final newline',
        'bank_contract': {'passband_max_abs_db': 0.0001, 'min_stop_rejection_db':185},
        'profiles': {}, 'banks': {},
    }
    for group, entries in BANKS.items():
        found = {}
        manifest['banks'][group] = {}
        for name, fs, pass_hz, stop_hz in entries:
            p, s = mp.mpf(pass_hz)/fs, mp.mpf(stop_hz)/fs
            taps = int(mp.ceil((A - 8)/(mp.mpf('2.285')*2*mp.pi*(s-p))))+1
            taps += (1-taps) % 4
            for _ in range(96):
                coeff = design(taps, p, s, False)
                ripple, rejection = freq_check(coeff, float(p),float(s))
                if ripple <= .00008 and rejection >= 187: break
                taps += 4
            else:
                raise RuntimeError(f'failed to design {group}/{name} within 96 tries')
            found[name] = coeff
            manifest['banks'][group][name] = {
                'taps': len(coeff), 'input_hz': fs, 'pass_hz': pass_hz,
                'stop_hz': stop_hz, 'pass_cycles':float(p), 'stop_cycles':float(s),
                'delay_input_frames':(taps-1)//2,
                'sha256_float_hex':hexdigest(coeff),
                'design_grid_pass_abs_db':ripple,
                'design_grid_worst_stop_rejection_db':rejection,
                'design_grid_points':262145,
            }
        path=ROOT/'src'/('pcmdsd_coeffs_112.h' if group=='encoder' else 'dsd_coeffs_112.h')
        content=write_header(group,found)
        if args.check:
            assert path.read_text()==content, path
        else:
            path.write_text(content)
    for d, info in PROFILES.items():
        item=dict(info)
        D=info['native_hz']//info['intermediate_hz']
        assert D.bit_count()==1
        stages=D.bit_length()-1
        last_taps=manifest['banks']['decoder'][info['bank']]['taps']
        G=sum(28*(1<<j) for j in range(stages-1)) + (last_taps//2)*(1<<(stages-1))
        item.update(factor=D,stages=stages,decoder_stage_taps=[57]*(stages-1)+[last_taps],
                    delay_native_frames=G,discard_frames=G//D, phase_native_frames=G%D,
                    encoder_taps=manifest['banks']['encoder'][info['bank']]['taps'])
        manifest['profiles'][f'dsd{d}']=item
    out=ROOT/'tests/dsd/reference/mastering_passband_112.json'
    raw=json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if args.check:
        assert out.read_text()==raw,out
    else:
        out.write_text(raw)
    print(json.dumps({group:{k:r['taps'] for k,r in rows.items()}
                      for group,rows in manifest['banks'].items()},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
