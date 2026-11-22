#!/usr/bin/env python3
"""Phase 08 D6: enforce CORE-MATH at each independently routed dB site.

These five syntactically different sites all need the same private exp10.
Verify the exact, function-specific expression (not just a filename-wide
reference), and demonstrate that replacing any single site is rejected.
The executable numeric/special-value oracle is coremath_gain_reference.py.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
CALL = 'dsd_coremath_gain_from_db'
PATTERNS = {
    'gain_effect': ('src/gain.c', r'p->fixed_gain\s*=\s*dsd_coremath_gain_from_db\(p->fixed_gain\)\s*;'),
    'dsd_effect_encode': ('src/pcmdsd.c', r'p->applied_gain\s*=\s*p->options.headroom==LSX_DSD_HEADROOM_FIXED\s*\?\s*dsd_coremath_gain_from_db\(-p->options.headroom_db\)\s*:'),
    'precision64_encode': ('src/sox_ng.c', r'headroom\s*=\s*dsd_coremath_gain_from_db\(-dsd_policy.headroom_db\)\s*;'),
    'precision64_transcode': ('src/sox_ng.c', r'headroom\s*=\s*dsd_coremath_gain_from_db\(-dsd_policy.headroom_db\)\s*;'),
    'plan': ('src/dsd_plan.c', r'fprintf\(fp,"%\.17g",dsd_coremath_gain_from_db\(-spec->policy.headroom_db\)\)\s*;'),
}


def verify(sources):
    helper = sources['src/dsd_coremath_gain.h']
    if not re.search(r'return\s+cr_exp10\(db\s*/\s*20\.0\)\s*;', helper):
        raise AssertionError('D6 helper is not routed to correctly rounded cr_exp10')
    if not re.search(r'if\s*\(db\s*==\s*0\.0\)\s*return\s+1\.0\s*;', helper):
        raise AssertionError('D6 exact zero/unity short circuit absent')
    result = {}
    for name, (filename, pattern) in PATTERNS.items():
        matches = list(re.finditer(pattern, sources[filename], flags=re.S))
        expected = 2 if filename == 'src/sox_ng.c' else 1
        if len(matches) != expected:
            raise AssertionError(f'D6 {name}: expected {expected} CORE-MATH route(s), got {len(matches)}')
        result[name] = {'file': filename, 'matches': len(matches)}
    # Both precision64 uses have identical expressions; ensure they are in
    # distinct production path functions rather than duplicating one site.
    sox = sources['src/sox_ng.c']
    positions = [m.start() for m in re.finditer(PATTERNS['precision64_encode'][1], sox, re.S)]
    if not (len(positions) == 2 and 'native PCM-to-DSD' in sox[max(0,positions[0]-1800):positions[0]]
            and 'native DSD transcode' in sox[max(0,positions[1]-1800):positions[1]]):
        raise AssertionError('D6 precision64 routes cannot be independently located')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', type=Path, required=True)
    a = p.parse_args()
    names = sorted({file for file, _ in PATTERNS.values()} | {'src/dsd_coremath_gain.h'})
    sources = {name: (ROOT / name).read_text() for name in names}
    passing = verify(sources)
    rejected = []
    for name, (filename, pattern) in PATTERNS.items():
        original = sources[filename]
        matches = list(re.finditer(pattern, original, re.S))
        # In sox_ng.c, select the actual site by route order.
        m = matches[1] if name == 'precision64_transcode' else matches[0]
        changed = dict(sources)
        changed[filename] = original[:m.start()] + original[m.start():m.end()].replace(
            CALL, 'pow', 1) + original[m.end():]
        try:
            verify(changed)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError(f'D6 negative control missed replacement of {name}')
    mutant = dict(sources)
    mutant['src/dsd_coremath_gain.h'] = mutant['src/dsd_coremath_gain.h'].replace(
        'return cr_exp10(db / 20.0);', 'return pow(10.0, db / 20.0);')
    try:
        verify(mutant)
    except AssertionError:
        rejected.append('shared_coremath_implementation')
    else:
        raise AssertionError('D6 negative control missed helper replacement')
    record = {'schema': 'sox-dsd/d6-route-binding/1', 'status': 'PASS',
              'operator': 'private CORE-MATH cr_exp10',
              'sites': passing, 'negative_controls_rejected': rejected}
    a.results.mkdir(parents=True, exist_ok=True)
    (a.results / 'd6-route-bindings.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print('D6 route bindings: 5/5 paths and 6/6 mutation controls PASS')


if __name__ == '__main__':
    main()
