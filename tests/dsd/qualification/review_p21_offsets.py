#!/usr/bin/env python3
"""Recount P21 FFmpeg/SoX alignment measurements from original JSON cases.

This is a *measurement review*, not a new audio decode or a proof about the
origin of the offset. It accepts external case directories to reproduce the
same calculation, and rejects duplicate, malformed, or failed source cases.
"""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

EXPECTED = -40.5  # native DSD frames, measured on supplied synthetic cases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases-root', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--check-observed', action='store_true',
                    help='check the supplied 36 synthetic-case corpus')
    args = ap.parse_args()
    records = sorted(args.cases_root.glob('*.json'))
    if not records:
        ap.error('no P21 case JSON files in supplied cases directory')
    by_profile = defaultdict(list)
    by_source = defaultdict(list)
    seen = set()
    hashes = {}
    for path in records:
        content = path.read_bytes()
        case = json.loads(content)
        if case.get('status') != 'PASS' or case.get('sox_exit') != 0 or case.get('reference_exit') != 0:
            raise ValueError(f'failed or unexecuted case: {path.name}')
        native = case['native_hz']
        if native not in (22579200, 45158400):
            raise ValueError(f'unknown native rate in {path.name}')
        profile = case['profile_id']
        if profile not in ('decode.mastering.v1', 'decode.mastering.v2',
                           'decode.wideband.v1'):
            raise ValueError(f'unknown decoder in {path.name}')
        key = (case['source_sha256'], case['container'], native, profile)
        if key in seen:
            raise ValueError(f'duplicate case identity {key}')
        seen.add(key)
        shift_us = case['metrics']['reference_shift_us']
        if not isinstance(shift_us, (int, float)) or not math.isfinite(shift_us):
            raise ValueError(f'invalid shift {path.name}')
        shift_native = shift_us * 1e-6 * native
        by_profile[(native, profile)].append(shift_native)
        by_source[key[:3]].append((profile, shift_native))
        hashes[path.name] = hashlib.sha256(content).hexdigest()
    if args.check_observed:
        if len(records) != 36:
            raise ValueError(f'expected supplied 36 cases, got {len(records)}')
        if len(by_profile) != 6 or any(len(xs) != 6 for xs in by_profile.values()):
            raise ValueError('incomplete 2 native rates x 3 profiles x 6 cases')
        if len(by_source) != 12 or any(len(vals) != 3 for vals in by_source.values()):
            raise ValueError('incomplete profile triples for the 12 sources')
    details = [dict(native_hz=native, profile_id=profile, count=len(shifts),
                    min_native_frames=min(shifts), max_native_frames=max(shifts),
                    max_abs_deviation_from_minus_40p5_native_frames=max(
                        abs(v - EXPECTED) for v in shifts))
               for (native, profile), shifts in sorted(by_profile.items())]
    common = [dict(source_sha256=key[0], container=key[1], native_hz=key[2],
                   interprofile_spread_native_frames=max(v for _, v in values) -
                   min(v for _, v in values))
              for key, values in sorted(by_source.items())]
    summary = dict(schema='sox-dsd-p21-reference-offset-review/1',
                   case_count=len(records), expected_native_frames=EXPECTED,
                   max_abs_deviation_native_frames=max(
                       row['max_abs_deviation_from_minus_40p5_native_frames']
                       for row in details),
                   max_interprofile_spread_native_frames=max(
                       row['interprofile_spread_native_frames'] for row in common),
                   by_profile=details, by_source=common, case_sha256=hashes,
                   limitation='Observational source data only; does not prove a filter-delay '
                              'mechanism, a general FFmpeg offset, or new decoder behavior.')
    if args.check_observed and summary['max_abs_deviation_native_frames'] > .01:
        raise AssertionError('supplied offset is not within 0.01 native DSD frame')
    encoded = json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
