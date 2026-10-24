#!/usr/bin/env python3
"""Check P10 phase gate against a separate source/build path (stdlib only)."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--build', type=Path, required=True)
    args = ap.parse_args()
    src = args.source.resolve()
    build = args.build.resolve()
    exe = '.exe' if sys.platform == 'win32' else ''
    unit = build/'test'/('dsd_test_p10' + exe)
    probe = build/'test'/('dsd_test_io' + exe)
    sox = build/'src'/('sox' + exe)
    control = subprocess.run([str(unit), '--unit'], capture_output=True,
                             text=True, timeout=120)
    if control.returncode:
        raise AssertionError(f'P10 direct native suite failed: {control.stderr[-500:]}')
    with tempfile.TemporaryDirectory(prefix='sox-dsd-src-build-') as scratch:
        root = Path(scratch)
        for name, is_dir in [('tests/dsd/run.py',False),
                             ('tests/dsd/reference',True),
                             ('tests/dsd/fixtures/manifest.json',False),
                             ('src/dsdiff.c',False),
                             ('docs/dsd/DSD_DESIGN.md',False)]:
            dst = root/name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if is_dir: shutil.copytree(src/name,dst)
            else: shutil.copy2(src/name,dst)
        for phase in ('P10', 'P11', 'P18'):
            results = root/('results-'+phase)
            argv = [sys.executable, str(root/'tests/dsd/run.py'),
                    '--phase', phase, '--mode', 'unit',
                    '--only', 'P10_native_unit_contract', '--results', str(results),
                    '--sox', str(sox), '--probe', str(probe)]
            got = subprocess.run(argv, cwd=root, capture_output=True,
                                 text=True, timeout=150)
            receipt = json.loads((results/'run.json').read_text())
            if got.returncode != 0 or receipt['tests'][0]['status'] != 'pass':
                raise AssertionError(f'{phase} out-tree P10 failed: {got.stderr[-750:]}')
            print(json.dumps({'phase':phase, 'result':'PASS',
                              'command':receipt['tests'][0]['name']},sort_keys=True))


if __name__ == '__main__':
    main()
