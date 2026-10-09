#!/usr/bin/env python3
"""Fail if this DFF-reader hotfix changes output from its P02/P05 input tree.

The P02 timing harness excludes a case when a P01 and P02 repack disagree.
That is legitimate for repaired P02 small-capacity behavior, but it cannot
establish whether a later optimization preserved the P02 output. Compare
against an independently built, unmodified copy of the hotfix input instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from bench_read_p02 import dff_bytes, dsf_bytes


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-sox', type=Path, required=True,
                        help='compiled, unmodified input tree')
    parser.add_argument('--after-sox', type=Path, required=True,
                        help='compiled hotfix candidate')
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--large-frames', type=int, default=1048576)
    parser.add_argument('--small-frames', type=int, default=131072)
    args = parser.parse_args()
    before, after = args.before_sox.resolve(), args.after_sox.resolve()
    for n in (args.large_frames, args.small_frames):
        if n <= 0 or n % (4096 * 8):
            parser.error('frame counts must be positive multiples of 32768')
    records = []
    with tempfile.TemporaryDirectory(prefix='sox-ng-hotfix-eq-') as directory:
        temp = Path(directory)
        for fmt in ('dff', 'dsf'):
            for channels in (2, 6):
                for size, frames, capacity in (('small', args.small_frames, 32),
                                               ('large', args.large_frames, 65536)):
                    source = temp / f'{fmt}-{channels}-{size}.{fmt}'
                    source.write_bytes(dff_bytes(channels, frames) if fmt == 'dff'
                                       else dsf_bytes(channels, frames)[0])
                    digests = {}
                    exits = {}
                    for arm, binary in (('before', before), ('after', after)):
                        output = temp / f'{fmt}-{channels}-{size}-{arm}.dff'
                        run = subprocess.run([str(binary), '--buffer', str(capacity),
                                              str(source), str(output)],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, timeout=120)
                        exits[arm] = run.returncode
                        if run.returncode == 0 and output.is_file():
                            digests[arm] = dict(sha256=sha256(output),
                                                bytes=output.stat().st_size)
                        else:
                            digests[arm] = {'error': run.stderr.decode(errors='replace')[-500:]}
                    identical = (exits == {'before': 0, 'after': 0} and
                                 digests['before'] == digests['after'])
                    record = {'case': f'{fmt}-{channels}ch-repack-{size}',
                              'source_sha256': sha256(source),
                              'before': digests['before'], 'after': digests['after'],
                              'identical': identical}
                    records.append(record)
                    print(f"{'PASS' if identical else 'FAIL'} {record['case']}", flush=True)
    result = {'purpose': 'supplied P05 input tree versus hotfix byte-equivalence',
              'before_binary_sha256': sha256(before),
              'after_binary_sha256': sha256(after),
              'passed': sum(row['identical'] for row in records),
              'total': len(records), 'cases': records}
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['passed'] == result['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
