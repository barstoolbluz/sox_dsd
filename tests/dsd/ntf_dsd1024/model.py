#!/usr/bin/env python3
"""Source-bound, nonproduction CLANS/SDM NTF designs at the DSD1024 clock.

No polynomial/Lee criterion is treated as proof of nonlinear one-bit safety.
All coefficients are carried as exact IEEE-754 binary64 hexadecimal words.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src/sdm.c'
DESIGNS512 = ROOT / 'tests/dsd/ntf_study/designs-new-native.json'
P19 = ROOT / 'src/sdm_p19_candidates.h'
RATE = 45158400
WORKING = 176400
FAMILY_NAMES = {f'{family}-{i}' for family in ('clans', 'sdm') for i in range(4, 9)}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + '\n'


def positive_coefficients(a: list[str], g: list[str], order: int) -> None:
    if not 4 <= order <= 8 or len(a) != order or len(g) != order:
        raise ValueError('Invalid order/length')
    if not all(isinstance(v, str) and re.fullmatch(r'0x[0-9a-f.]+p[+-]\d+', v) for v in a + g):
        raise ValueError('Nonhex coefficient')
    aa = [float.fromhex(v) for v in a]
    gg = [float.fromhex(v) for v in g]
    if any(not math.isfinite(v) for v in aa + gg) or min(aa) <= 0 or min(gg) < 0:
        raise ValueError('Invalid coefficient sign/value')
    if any(float.fromhex(word).hex() != word for word in a + g):
        raise ValueError('Coefficient words must be canonical binary64')
    # The C recurrence uses g[i] for coupling i->i+1; g[-1] unused and zero.
    if gg[-1] != 0:
        raise ValueError('Nonzero unused resonator coefficient')


def load_legacy() -> dict[str, dict]:
    text = SOURCE.read_text()
    if text.count('static const sdm_filter_t sdm_filters[] = {') != 1:
        raise ValueError('Expected exactly one frozen sdm filter array')
    src = text.split('static const sdm_filter_t sdm_filters[] = {', 1)[1].split('\n};', 1)[0]
    # This parser recognizes the frozen 256x44100-Hz literal table only;
    # fail closed on unexpected format rather than substituting guesses.
    pat = (r'\{\s*\{([\d\s.,+eE-]+)\},\s*'
           r'\{([\d\s.,+eE-]+)\},\s*(\d+),\s*'
           r'(\d+)\s*\*\s*44100,\s*"([^"]+)",\s*0,\s*0,\s*0\s*\}')
    out = {}
    for atxt, gtxt, ntext, hztext, name in re.findall(pat, src):
        if int(hztext) != 256 or name not in FAMILY_NAMES:
            continue
        n = int(ntext)
        a = [float(v).hex() for v in atxt.split(',') if v.strip()]
        g = [float(v).hex() for v in gtxt.split(',') if v.strip()]
        g += [0.0.hex()] * (n - len(g))
        positive_coefficients(a, g, n)
        if name in out:
            raise ValueError('Duplicate historic family: ' + name)
        out[name] = dict(order=n, a=a, g=g, kind='original-256x44100-rebound',
                         source='src/sdm.c', family=name)
    if set(out) != FAMILY_NAMES:
        raise ValueError('Expected all ten frozen historical production families; got: ' + repr(sorted(out)))
    # The frozen P19 v2 identity MUST be the historical CLANS-7, bit for bit.
    p19 = P19.read_text()
    a, g = out['clans-7']['a'], out['clans-7']['g']
    for word in a + g:
        if word not in p19 and word != 0.0.hex():
            raise ValueError('P19 v2 incumbent disagrees with CLANS-7')
    return out


def linear_metrics(a_words: list[str], g_words: list[str]) -> dict:
    a = np.array([float.fromhex(s) for s in a_words], dtype='float64')
    g = np.array([float.fromhex(s) for s in g_words], dtype='float64')
    n = len(a)
    m = np.eye(n)
    for i in range(1, n):
        m[i, i - 1] = 1.0
    for i in range(n-1):
        m[i, i + 1] = -g[i]
    b = np.zeros(n)
    b[0] = 1.0
    closed_poles = np.linalg.eigvals(m - np.outer(b, a))
    ntf_zeros = np.linalg.eigvals(m)
    # Dense low-frequency grid and sampled *full* Nyquist check.
    grid = np.r_[np.linspace(0, 300000, 601), np.geomspace(300001, RATE/2, 1200)]
    z = np.exp(2j * np.pi * grid / RATE)
    h = np.prod(z[:, None] - ntf_zeros, axis=1) / np.prod(z[:, None] - closed_poles, axis=1)
    if not np.isfinite(h).all():
        raise ValueError('Nonfinite linearized NTF')
    power = abs(h) ** 2
    def band(lo, hi):
        sel = (grid >= lo) & (grid <= hi)
        return float(10 * np.log10(max(float(power[sel].mean()), 1e-300)))
    return dict(pole_max_radius=float(np.max(abs(closed_poles))),
                sampled_peak_gain=float(np.max(abs(h))),
                ntf_0_40k_db=band(0, 40000), ntf_40_100k_db=band(40000, 100000),
                ntf_100_150k_db=band(100000, 150000),
                ntf_150_300k_db=band(150000, 300000),
                note='Linearized additive-noise screening ONLY, not a nonlinear stability certificate')


def make_designs() -> dict:
    originals = load_legacy()
    historic = json.loads(DESIGNS512.read_text())
    if set(historic['designs']) < {'o7-r8-a20', 'o7-r5-a20', 'order7-pareto-g3p0'}:
        raise ValueError('Missing DSD512 redesigned seed(s)')
    originals['d512-r8-a20'] = {**{k: historic['designs']['o7-r8-a20'][k] for k in ('order', 'a', 'g')},
                                'kind':'DSD512-redesign-rebound', 'source':'designs-new-native.json:o7-r8-a20', 'family':'dsd512-r8'}
    originals['d512-r5-a20'] = {**{k: historic['designs']['o7-r5-a20'][k] for k in ('order', 'a', 'g')},
                                'kind':'DSD512-redesign-rebound', 'source':'designs-new-native.json:o7-r5-a20', 'family':'dsd512-r5'}
    originals['d512-sdm7-g3'] = {**{k: historic['designs']['order7-pareto-g3p0'][k] for k in ('order', 'a', 'g')},
                                'kind':'DSD512-balance-rebound', 'source':'designs-new-native.json:order7-pareto-g3p0', 'family':'dsd512-balance'}
    result = {}
    for name, seed in sorted(originals.items()):
        positive_coefficients(seed['a'], seed['g'], seed['order'])
        multipliers = (1., .25, .5, 2.) if name in FAMILY_NAMES else (.25, .5, 1., 2., 4.)
        for multiplier in multipliers:
            key = name if multiplier == 1 else name + '-g' + str(multiplier).replace('.', 'p')
            # For original CLANS-7, the full-rate incumbent is directly rendered.
            a = seed['a'].copy()
            g = [float(float.fromhex(w) * multiplier).hex() for w in seed['g']]
            positive_coefficients(a, g, seed['order'])
            result[key] = dict(order=seed['order'], a=a, g=g, family=seed['family'],
                               kind=seed['kind'], source=seed['source'],
                               g_multiplier=multiplier, producer='exact binary64 multiply',
                               qualified=False, promoted=False,
                               linearized_ntf=linear_metrics(a, g))
    return dict(schema='DSD1024-NTF-nonproduction-designs/1',
                source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (SOURCE, P19, DESIGNS512)},
                working_hz=WORKING, native_hz=RATE,
                caveats=['Ten production families from DSD256 are rebinding seeds, not qualified at DSD1024.',
                         'The DSD512 redesigns are transported with exact binary64 coefficient words.',
                         'g scaling is bounded topology-preserving resonator exploration, not global optimum.',
                         'Sampled peak gain and pole radius are NEVER the nonlinear stability gate.',
                         'The 176400-Hz input pipeline cannot transmit material above 88200 Hz.'],
                incumbent_key='clans-7', designs=result)


if __name__ == '__main__':
    path = Path(__file__).with_name('designs.json')
    if path.exists():
        if path.read_text() != canonical(make_designs()):
            raise SystemExit('Existing designs differ; refusing overwrite')
    else:
        path.write_text(canonical(make_designs()))
    print(len(make_designs()['designs']), 'binary64 designs, exact SHA-256:', sha(path))
