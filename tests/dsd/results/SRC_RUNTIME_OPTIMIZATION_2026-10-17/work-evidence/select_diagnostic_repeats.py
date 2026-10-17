#!/usr/bin/env python3
"""Select all sustained negative CPU intervals under the retained repeat policy."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--measurements', type=Path, nargs='+', required=True)
parser.add_argument('--policy', type=Path, required=True)
parser.add_argument('--output-directory', type=Path, required=True)
args = parser.parse_args()
dest = args.output_directory
dest.mkdir(parents=True, exist_ok=True)
outputs = [dest/'repeat-cases.json', dest/'repeat-selection.json']
if any(p.exists() for p in outputs):
    parser.error('refusing to overwrite selection evidence')
selected, inputs, seen, examined = [], [], set(), []
for path in args.measurements:
    raw = path.read_bytes()
    d = json.loads(raw)
    if d['status'] != 'PASS' or d['mode'] != 'PAIRED':
        raise ValueError('only completed paired receipts may select repeats')
    inputs.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest()))
    for case in d['cases']:
        if case['id'] in seen:
            raise ValueError('duplicate case ID')
        seen.add(case['id'])
        stat = d['comparisons'][case['id']+'/candidate']['cpu_seconds']
        chosen = case['seconds'] >= 1 and stat['median_ci95'][1] < 1
        examined.append(dict(id=case['id'], seconds=case['seconds'],
                             cpu_speedup=stat['paired_ratios']['median'],
                             cpu_ci95=stat['median_ci95'], selected=chosen))
        if chosen:
            repeat = dict(case, repeat_of=case['id'], id='repeat_'+case['id'])
            selected.append(repeat)
outputs[0].write_text(json.dumps(selected, indent=2)+'\n')
outputs[1].write_text(json.dumps(dict(
    schema='src-optimization/diagnostic-repeat-selection/1',
    policy=json.loads(args.policy.read_text()),
    policy_sha256=hashlib.sha256(args.policy.read_bytes()).hexdigest(),
    inputs=inputs, examined=examined, selected_count=len(selected),
    repetitions=30, warmups=2,
    interpretation='Diagnostic repeats remain additional observations; original results are retained.'
), indent=2)+'\n')
print(json.dumps(dict(examined=len(examined), selected=[c['repeat_of'] for c in selected])))
