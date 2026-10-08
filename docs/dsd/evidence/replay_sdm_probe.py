#!/usr/bin/env python3
"""Replay the captured short SDM matrix; not a mastering qualification test.

The original JSON printed amplitudes with eight significant digits. This runner
uses those captured values and explicitly records that limitation. Chaotic SDM
trajectories need not match the original output statistics bit for bit.
"""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--matrix', type=Path,
                        default=Path(__file__).with_name('sdm_short_stress.json'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    probe = args.probe.resolve()
    if not probe.is_file():
        parser.error('The compiled probe does not exist.')
    if args.out.resolve() == args.matrix.resolve():
        parser.error('Use a separate output path; do not overwrite baseline evidence.')
    matrix = json.loads(args.matrix.read_text())
    duration = matrix['seconds_per_case']
    results = []
    for case in matrix['cases']:
        cmd = [str(probe), case['filter'], str(case['rate']), case['stimulus'],
               repr(case['amplitude_dsd']), repr(duration)]
        completed = subprocess.run(cmd, text=True, capture_output=True)
        if completed.returncode:
            raise RuntimeError(f'Probe failed ({completed.returncode}): {cmd!r}\n'
                               f'{completed.stderr}')
        result = json.loads(completed.stdout)
        result['command'] = cmd
        result['exit_code'] = completed.returncode
        results.append(result)
    report = {
        'scope': matrix['scope'],
        'seconds_per_case': duration,
        'amplitude_provenance': ('Replayed from eight-significant-digit values in '
                                'the captured baseline JSON; not an exact argv archive.'),
        'cases': results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Wrote {len(results)} cases to {args.out}')


if __name__ == '__main__':
    main()
