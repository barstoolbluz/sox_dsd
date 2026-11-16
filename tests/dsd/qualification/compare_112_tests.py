#!/usr/bin/env python3
"""Compare preserved 1.1.1/1.1.2 P10 outcomes and P21 qualification.

This evidence comparison never changes old tests or their thresholds.
"""
import argparse
import hashlib
import json
from pathlib import Path


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    document = json.loads(path.read_text())
    out = {}
    for row in document['rows']:
        name = row['name']
        if name in out:
            raise AssertionError(f'duplicate P10 case {name}: {path}')
        out[name] = dict(status=row['status'], reason=row.get('reason'))
    assert document['summary']['fail'] == sum(x['status'] == 'fail' for x in out.values())
    assert document['summary']['pass'] == sum(x['status'] == 'pass' for x in out.values())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ('baseline', 'candidate', 'baseline-log', 'candidate-log',
                  'owner-summary', 'p21', 'output'):
        ap.add_argument('--' + field, type=Path, required=True)
    args = ap.parse_args()
    original, updated = rows(args.baseline), rows(args.candidate)
    assert original.keys() == updated.keys(), 'P10 case inventory changed'
    old_fail = {k: v['reason'] for k,v in original.items() if v['status'] == 'fail'}
    new_fail = {k: v['reason'] for k,v in updated.items() if v['status'] == 'fail'}
    added = {k: v for k,v in new_fail.items() if k not in old_fail}
    recovered = sorted(set(old_fail) - set(new_fail))
    reason_changes = {k:(old_fail[k],new_fail[k]) for k in old_fail.keys() & new_fail.keys()
                      if old_fail[k] != new_fail[k]}
    assert not added and not recovered and not reason_changes
    assert len(old_fail) == len(new_fail) == 8, (old_fail, new_fail)
    assert all(original[k]['status'] == updated[k]['status'] for k in original)
    # The supplied owner's original 1.1.1 check differs from both local runs.
    owner_lines = args.owner_summary.read_text().splitlines()
    owner_p10 = [line for line in owner_lines if line.startswith('check-dsd DSD_PHASE=P10 ')]
    assert owner_p10 == ['check-dsd DSD_PHASE=P10 0'], owner_p10
    p21 = json.loads(args.p21.read_text())
    assert p21['case_count'] == 24
    assert p21['independent_reader_and_audio_reference_gate'] == 'INCOMPLETE'
    assert p21['commercial_media_sha256'] == []
    assert not any(p21['rows_qualified_commercial'].values())
    files = {name:dict(sha256=fingerprint(getattr(args, field)), name=getattr(args, field).name)
             for field, name in (('baseline','baseline_p10_rows'),
                                 ('candidate','candidate_p10_rows'),
                                 ('baseline_log','baseline_p10_log'),
                                 ('candidate_log','candidate_p10_log'),
                                 ('owner_summary','owner_supplied_111_summary'),
                                 ('p21','p21_independent_reader_receipt'))}
    result = dict(schema='sox-dsd/1.1.2/release-test-comparison/1',
        status='PASS_EVIDENCE_COMPARISON',
        p10=dict(total=len(original), baseline_failures=len(old_fail),
                 candidate_failures=len(new_fail), inherited_failures=old_fail,
                 newly_failing=added, recovered=recovered, changed_failure_reasons=reason_changes,
                 interpretation='same eight failures on both local builds; cause not attributed to 1.1.2'),
        owner_p10_discrepancy=dict(owner_111_recorded='PASS',
                                   local_111='FAIL',local_112='FAIL',
                                   cause='not established; do not rewrite P10 to make the runs agree'),
        p21=dict(synthetic_audio_comparisons=24, synthetic_status='PASS',
                 commercial_media_cases=0, overall='INCOMPLETE'),
        evidence=files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending=args.output.with_suffix('.tmp')
    pending.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    pending.replace(args.output)
    print('P10 8/8 baseline-identical failures, no newly failing cases; P21 24/24 synthetic, INCOMPLETE overall')


if __name__ == '__main__':
    main()
