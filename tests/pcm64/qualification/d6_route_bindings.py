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


# Function-specific source checks deliberately operate on comment-free C.
# These checks are narrow admission controls, not claims of semantic C proof.
# Independent live numeric route oracles remain in coremath_gain_reference.py.
SCOPES = {
    'gain_effect': 'create_gain',
    'dsd_effect_encode': 'effect_start',
    'precision64_encode': 'dsd_run_native_encode',
    'precision64_transcode': 'dsd_run_native_transcode',
    'plan': 'lsx_dsd_plan_json',
}


def no_comments(raw: str) -> str:
    """Ignore actual C comments, preserving strings and line positions."""
    parts = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*', re.S)
    return parts.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group())
                     if m.group().startswith(('/*', '//')) else m.group(), raw)


def function_body(source: str, name: str) -> str:
    match = re.search(r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', source, re.S)
    if not match:
        raise AssertionError(f'D6 source function {name} missing')
    opened = match.end() - 1
    depth = 0
    for i in range(opened, len(source)):
        if source[i] == '{': depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0: return source[opened + 1:i]
    raise AssertionError(f'D6 source function {name} is unbalanced')


def verify(sources):
    cleaned = {k: no_comments(v) for k, v in sources.items()}
    helper = cleaned['src/dsd_coremath_gain.h']
    if not re.search(r'return\s+cr_exp10\(db\s*/\s*20\.0\)\s*;', helper):
        raise AssertionError('D6 helper does not call correctly rounded cr_exp10')
    if not re.search(r'if\s*\(db\s*==\s*0\.0\)\s*return\s+1\.0\s*;', helper):
        raise AssertionError('D6 zero/unity short circuit absent')
    if re.search(r'(?m)^\s*#\s*(?:define|undef)\s+(?:dsd_coremath_gain_from_db|cr_exp10)\b', helper):
        raise AssertionError('D6 helper operator preprocessor redefinition')
    result = {}
    for name, (filename, pattern) in PATTERNS.items():
        source = cleaned[filename]
        if re.search(r'(?m)^\s*#\s*(?:define|undef)\s+(?:dsd_coremath_gain_from_db|cr_exp10)\b', source):
            raise AssertionError(f'D6 {name}: preprocessor redefines private operator')
        body = function_body(source, SCOPES[name])
        matches = list(re.finditer(pattern, body, flags=re.S))
        if len(matches) != 1:
            raise AssertionError(f'D6 {name}: expected one executable CORE-MATH route, got {len(matches)}')
        # A matching call followed by an overwrite would fool a token-only
        # admission check. These exact D6 route functions use no libm pow.
        if re.search(r'\b(?:pow|powf|powl|exp|exp10)\s*\(', body):
            raise AssertionError(f'D6 {name}: alternate libm dB factor in production route')
        if name in ('precision64_encode', 'precision64_transcode'):
            assignments = re.findall(r'\bheadroom\s*=(?!=)\s*([^;]+);', body)
            if (len(assignments) != 3 or
                sum('dsd_coremath_gain_from_db' in x for x in assignments) != 1 or
                sum('lsx_pcmdsd_default_warn_gain' in x for x in assignments) != 1):
                raise AssertionError(f'D6 {name}: unexpected headroom overwrite')
        if name == 'gain_effect':
            if len(re.findall(r'p->fixed_gain\s*=(?!=)', body)) != 1:
                raise AssertionError('D6 gain effect: unexpected gain factor overwrite')
        result[name] = {'file': filename, 'function': SCOPES[name], 'matches': 1}
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
    # Reject the precise independent bypass classes observed on Return 1:
    # commented-out call, a second overwrite, and a preprocessor substitute.
    for name in ('precision64_encode', 'precision64_transcode'):
        c = dict(sources)
        expression = 'headroom=dsd_coremath_gain_from_db(-dsd_policy.headroom_db);'
        positions = [m.start() for m in re.finditer(re.escape(expression), c['src/sox_ng.c'])]
        if len(positions) != 2:
            raise AssertionError('D6 explicit bypass oracle cannot find both routes')
        pos = positions[0 if name == 'precision64_encode' else 1] + len(expression)
        c['src/sox_ng.c'] = (c['src/sox_ng.c'][:pos] +
            '\n  headroom=pow(10.,-dsd_policy.headroom_db/20.);' + c['src/sox_ng.c'][pos:])
        try: verify(c)
        except AssertionError: rejected.append(name + '_late_overwrite')
        else: raise AssertionError(f'D6 negative control missed {name} late overwrite')
    c = dict(sources)
    c['src/dsd_plan.c'] = '#define dsd_coremath_gain_from_db(x) pow(10.,(x)/20.)\n' + c['src/dsd_plan.c']
    try: verify(c)
    except AssertionError: rejected.append('plan_macro_override')
    else: raise AssertionError('D6 negative control missed plan macro')
    c = dict(sources)
    c['src/gain.c'] = c['src/gain.c'].replace(
        'p->fixed_gain = dsd_coremath_gain_from_db(p->fixed_gain);',
        '/* p->fixed_gain = dsd_coremath_gain_from_db(p->fixed_gain); */\n'
        'p->fixed_gain = pow(10.,p->fixed_gain/20.);', 1)
    try: verify(c)
    except AssertionError: rejected.append('gain_comment_decoy')
    else: raise AssertionError('D6 negative control missed commented call')
    record = {'schema': 'sox-dsd/d6-route-binding/1', 'status': 'PASS',
              'operator': 'private CORE-MATH cr_exp10',
              'sites': passing, 'negative_controls_rejected': rejected}
    a.results.mkdir(parents=True, exist_ok=True)
    (a.results / 'd6-route-bindings.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print(f'D6 route bindings: 5/5 paths and {len(rejected)}/{len(rejected)} mutation controls PASS')


if __name__ == '__main__':
    main()
