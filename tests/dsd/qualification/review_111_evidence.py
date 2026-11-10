#!/usr/bin/env python3
"""Independently summarize the supplied 1.1.1 high-rate, real-track receipts.

Uses JSONL metadata only; input PCM and emitted DSD were not supplied.
Reports source-stage `balancing clipped` warnings separately from pcmdsd's
modulator clipping. Does not treat an exit code of zero as audio fidelity proof.
"""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = HERE / 'results' / 'V1_HIGH_RATE_ENCODE_2026-11-07'
# A distribution tarball ships only the path-redacted copy of the receipt;
# it keeps every field this summary reads.
REDACTED = HERE / 'release_evidence' / 'v1_high_rate_real_tracks_redacted.jsonl'
INPUT_WARNING = re.compile(r'\bbalancing clipped ([0-9,]+) samples?\b')


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, help='save summary as JSON')
    parser.add_argument('--check-expected', action='store_true',
                        help='assert original 800-run cohort count and warning totals')
    args = parser.parse_args()
    root = args.results_root
    source = root / 'real-tracks' / 'results.jsonl'
    if not source.is_file() and root == DEFAULT_ROOT:
        source = REDACTED
        launcher = HERE / 'release_evidence' / 'v1_high_rate_soak_launcher.log'
    else:
        launcher = root / 'gates' / 'soak' / 'launcher.log'
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('no historical run records')
    grouped = {}
    for row in rows:
        if any(key not in row for key in ('id', 'level', 'rate', 'exit', 'stderr', 'fail')):
            raise ValueError('malformed run record')
        if not isinstance(row['stderr'], str):
            raise ValueError('malformed stderr field')
        key = (row['level'], row['rate'])
        grouped.setdefault(key, []).append(row)
    cohorts = []
    for (level, rate), entries in sorted(grouped.items()):
        clipped = []
        for row in entries:
            counts = [int(m.replace(',', '')) for m in INPUT_WARNING.findall(row['stderr'])]
            if counts:
                clipped.append((row['id'], counts))
        cohorts.append(dict(level=level, rate=rate, runs=len(entries),
                            unique_track_ids=len({r['id'] for r in entries}),
                            successes=sum(r['exit'] == 0 for r in entries),
                            nonempty_failure_arrays=sum(bool(r['fail']) for r in entries),
                            input_stage_clipping_runs=len(clipped),
                            input_stage_clipping_tracks=len({x[0] for x in clipped}),
                            maximum_input_stage_clipped_samples=max(
                                (n for _, counts in clipped for n in counts), default=0),
                            sum_input_stage_clipped_samples=sum(
                                n for _, counts in clipped for n in counts),
                            modulator_clip_warning_runs=sum('WARN pcmdsd: clipped' in r['stderr']
                                                            for r in entries)))
    peak = [row for row in cohorts if row['level'] == 'peak0']
    warn_count = sum(x['input_stage_clipping_runs'] for x in peak)
    max_clipped = max((x['maximum_input_stage_clipped_samples'] for x in peak), default=0)
    response = dict(schema='sox-dsd-1.1.1-observations-recheck/1',
                    source_sha256=checksum(source), total_runs=len(rows),
                    zero_exit_runs=sum(r['exit'] == 0 for r in rows),
                    peak0_runs=sum(r['level'] == 'peak0' for r in rows),
                    peak0_input_stage_warning_runs=warn_count,
                    peak0_input_stage_clipped_max_samples=max_clipped,
                    soak_launcher_bytes=launcher.stat().st_size,
                    cohorts=cohorts,
                    limits=['Input audio unavailable; cannot verify original PCM.',
                            'DSD outputs discarded to /dev/null; cannot verify output bytes.',
                            'A successful exit does not establish signal integrity.',
                            'A zero-byte launcher log does not establish a missing run.'])
    if args.check_expected:
        assert (response['total_runs'], response['zero_exit_runs'],
                response['peak0_runs'], warn_count, max_clipped,
                response['soak_launcher_bytes']) == (800, 800, 400, 194, 3936, 0), response
    encoded = json.dumps(response, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
