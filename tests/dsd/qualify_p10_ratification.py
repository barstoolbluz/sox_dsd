#!/usr/bin/env python3
"""P10 2026-10-10 release gate ratification, without rewriting earlier evidence.

This is the active post-corrective collector. The pre-ratification collector
and its negative certificate reproduce their historical UNRUN decisions;
current gate decisions come from the reviewer-pinned criterion manifest and
independent checks of the new committed evidence.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from qualify_p10_corrective import verify, ROOT, sha
from ratify_p10_gates import check_corpus, check_hardware, CRITERIA, HARDWARE, CORPUS

DEFAULT_OUTPUT = ROOT/'tests/dsd/results/P10_ratification_2026-10-10/qualification.json'


def assess(base=None, hardware=None, corpus=None, unit=None):
    if base is None:base=ROOT/'tests/dsd/results/P10_corrective'
    if hardware is None:hardware=HARDWARE
    if corpus is None:corpus=CORPUS
    base=Path(base)
    earlier=verify(base,unit)
    gates=dict(earlier['gates'])
    gates['representative_hardware_1hour_per_profile_isa']=check_hardware(hardware)
    gates['independent_realworld_corpus']=check_corpus(corpus)
    statuses=[g['status'] for g in gates.values()]
    result='FAIL' if 'FAIL' in statuses else 'INCOMPLETE' if any(
        s in ('UNRUN','PARTIAL','INCOMPLETE') for s in statuses) else 'PASS'
    # Fail closed for future unknown gate-state names.
    if any(s not in ('PASS','FAIL','PARTIAL','UNRUN','INCOMPLETE') for s in statuses):
        result='FAIL'
    return dict(schema='P10/reviewer-ratification/1',status=result,qualified=False,
        promotion='BLOCKED',profile_activation='UNQUALIFIED: requires explicit positive certification; P15 governs defaults',
        criteria='tests/dsd/reference/p10_ratification_criteria.json',
        criteria_sha256=sha(CRITERIA),
        supersedes_release_accounting='tests/dsd/results/P10_corrective/qualification.json',
        historical_corrective_receipt_sha256=sha(base/'qualification.json'),
        old_release_status=earlier['status'],
        inherited_gates_unchanged=all(gates[k]==v for k,v in earlier['gates'].items()
            if k not in ('representative_hardware_1hour_per_profile_isa','independent_realworld_corpus')),
        gates=gates,
        remaining_release_gates=[k for k,g in gates.items() if g['status']!='PASS'],
        limitation='Recorded hardware provenance and audio hashes are operator-supplied; '
            'external commercial sources are not distributed or re-rendered here. '
            'The 1-hour soak qualifies the scalar P10 recurrence, not legacy SIMD or future P11 runtime kernels.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P10_corrective')
    parser.add_argument('--hardware',type=Path,default=HARDWARE)
    parser.add_argument('--corpus',type=Path,default=CORPUS)
    parser.add_argument('--unit',type=Path)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data=assess(args.results,args.hardware,args.corpus,args.unit)
    if args.check:
        if not args.output.is_file() or read(args.output)!=data:
            raise SystemExit('ratification receipt absent or stale')
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.output.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n')
        tmp.replace(args.output)
    print(json.dumps(dict(status=data['status'],qualified=False,promotion='BLOCKED',
        remaining_release_gates=data['remaining_release_gates'],
        hardware=data['gates']['representative_hardware_1hour_per_profile_isa']['status'],
        corpus=data['gates']['independent_realworld_corpus']['status']),sort_keys=True))
    return {'PASS':0,'FAIL':1,'INCOMPLETE':2}[data['status']]


def read(path):
    return json.loads(Path(path).read_text())


if __name__=='__main__':raise SystemExit(main())
