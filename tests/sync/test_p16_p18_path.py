#!/usr/bin/env python3
"""Exercise actual P16/P17/P18 native executables with isolated source/build.

Uses the real build binaries, but runs the runner with a source tree that has
no test executables. A stale source-relative executable path is a hard fail.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    args = parser.parse_args()
    source=args.source.resolve(); build=args.build.resolve()
    exe='.exe' if sys.platform=='win32' else ''
    with tempfile.TemporaryDirectory(prefix='sox-dsd-p16-18-outtree-') as temp:
        root=Path(temp)
        for name, is_dir in [('tests/dsd/run.py',False),
                             ('tests/dsd/reference',True),
                             ('tests/dsd/fixtures/manifest.json',False),
                             ('src/dsdiff.c',False),
                             ('docs/dsd/DSD_DESIGN.md',False)]:
            dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True)
            if is_dir: shutil.copytree(source/name,dst)
            else: shutil.copy2(source/name,dst)
        for phase,unit,test_name in [
            ('P16','p16','P16_native_packed_reader_contract'),
            ('P17','p17','P17_highrate_registry_delay_and_capabilities'),
            ('P18','p18','P18_registry_closed_gate')]:
            binary=build/'test'/('dsd_test_'+unit+exe)
            if not binary.is_file(): raise AssertionError(f'missing native binary {binary}')
            command=[sys.executable,str(root/'tests/dsd/run.py'),
                     '--phase',phase,'--mode','unit','--only',test_name,
                     '--results',str(root/('result-'+phase)),
                     '--sox',str(build/'src'/('sox'+exe)),
                     '--probe',str(build/'test'/('dsd_test_io'+exe)),
                     '--'+unit+'-unit',str(binary)]
            got=subprocess.run(command,cwd=root,capture_output=True,
                               text=True,timeout=200)
            receipt=json.loads((root/('result-'+phase)/'run.json').read_text())
            if (got.returncode or receipt.get('verdict')!='pass' or
                    len(receipt['tests'])!=1 or
                    receipt['tests'][0]['name']!=test_name or
                    receipt['tests'][0]['status']!='pass'):
                raise AssertionError(f'{phase} external unit failed: {got.stderr[-1000:]}')
            # A nonexistent path must fail; never fall back to ROOT/test.
            missing=root/('missing-'+phase)
            command[command.index(str(binary))]=str(missing)
            failed=subprocess.run(command,cwd=root,capture_output=True,
                                  text=True,timeout=200)
            failed_receipt=json.loads((root/('result-'+phase)/'run.json').read_text())
            if not failed.returncode or failed_receipt['verdict']!='fail':
                raise AssertionError(f'{phase} missing executable passed silently')
            print(json.dumps({'phase':phase,'test':test_name,'actual':'PASS',
                              'absent_executable':'FAIL_CLOSED'},sort_keys=True))


if __name__=='__main__':
    main()
