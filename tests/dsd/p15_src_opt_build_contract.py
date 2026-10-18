#!/usr/bin/env python3
"""Fail-closed build-flag qualification for the optional ordered SRC C kernel.

This validates the build configuration text, not compiler honesty or machine
code. A separate source-bound exporter receipt and exact-output tests are
required. It deliberately does not touch any historical P15 receipts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shlex

class BuildContractError(ValueError):
    pass

UNSAFE_FLAGS={'-ffast-math','-fassociative-math','-funsafe-math-optimizations',
              '-ffinite-math-only','-freciprocal-math','-fexcess-precision=fast',
              '-fno-signed-zeros','-fno-trapping-math','-frounding-math-off',
              '-mfpmath=387'}


def check_flags(flags: str) -> dict:
    """Reject unsafe or unasserted opt-in configurations; conservative by design."""
    tokens=shlex.split(flags)
    if any(t in UNSAFE_FLAGS or t.startswith('-Ofast') for t in tokens):
        raise BuildContractError('unsupported floating-point reassociation/fast-math flag')
    contracts=[t.split('=',1)[1] for t in tokens if t.startswith('-ffp-contract=')]
    if not contracts or contracts[-1]!='off':
        raise BuildContractError('opt-in requires last effective -ffp-contract=off')
    for macro in ('LSX_RATE_ORDERED_OPT','LSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF'):
        assignments=[t for t in tokens if t in ('-D'+macro, '-D'+macro+'=1', '-D'+macro+'=0',
                                                  '-U'+macro) or t.startswith('-D'+macro+'=')]
        if not assignments or assignments[-1]!='-D'+macro+'=1':
            raise BuildContractError('missing explicit active '+macro+'=1')
    return dict(qualified_opt_in_cflags=True,flags=flags,
                scope='build-command screening only; not a compiler or spectral proof')


def makefile_flags(path: Path) -> str:
    if not path.is_file(): raise BuildContractError('missing configured Makefile')
    pairs=dict(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*)$',path.read_text(),re.M))
    # Configuration-level CFLAGS and CPPFLAGS should be literal values in the
    # generated Autotools Makefile. Refuse unevaluated make references.
    value=pairs.get('CPPFLAGS','')+' '+pairs.get('CFLAGS','')
    if '$' in value or not value.strip(): raise BuildContractError('unexpanded compiler flags')
    return value.strip()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--makefile',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(check_flags(makefile_flags(a.makefile)),sort_keys=True))


if __name__=='__main__':
    try:main()
    except (BuildContractError,ValueError) as e:
        raise SystemExit('REFUSED: '+str(e))
