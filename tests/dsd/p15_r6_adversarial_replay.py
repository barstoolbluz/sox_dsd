#!/usr/bin/env python3
"""Deliberate on-copy P15 R6 proof corruption. Never alters original evidence.

All corruptions are expected to REFUSE; a successful acceptance aborts the audit.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import time

from p15_r6_witness import check_proof

ROOT=Path(__file__).resolve().parent
PROOF=ROOT/'results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_STOP_0000_1000.json'


def audit():
    p=json.loads(PROOF.read_text()); tested=[]
    def one(name, mutate, expected_fragment):
        candidate=copy.deepcopy(p);mutate(candidate)
        start=time.monotonic()
        try:
            check_proof(candidate)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            reason=str(exc)
            if expected_fragment not in reason:
                raise AssertionError(f'{name}: unexpected refusal: {reason}') from exc
            tested.append(dict(name=name,result='REFUSED',reason=reason,elapsed_seconds=round(time.monotonic()-start,3)))
            return
        raise AssertionError(f'{name}: corrupted proof incorrectly ACCEPTED')
    one('original_source_identity_corruption',
        lambda c:c['binding'].update(source={'FAKE_SOURCE':'0'*64}),
        'identity mutated')
    one('math_method_digest_corruption',
        lambda c:c['binding']['exact_method_sources'].update({'p15_r6_exact_composite.py':'0'*64}),
        'identity mutated')
    one('missing_interval_end',
        lambda c:c['leaves'][0].update(hi='999'),
        'final endpoint')
    one('fabricated_stop_transfer_zero',
        lambda c:c['leaves'][0]['bounds'].update(source_stop_upper='0'),
        'reported bound differs')
    one('fabricated_summary_zero',
        lambda c:c['independent_check'].update(max_composite_unwanted_exact='0'),
        'summary differs')
    return dict(schema='P15/R6/adversarial-corruption/1',source_proof=PROOF.name,
                date='2026-10-19',tests=len(tested),refused=len(tested),
                false_acceptances=0,results=tested)


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,sort_keys=True))
