#!/usr/bin/env python3
"""Apply the compact patch to isolated, exact third-pass source preimages.

This checks patch applicability and postimage identity. It does not build the
DSP library, run a numerical proof, or modify the supplied baseline tree.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or unsafe regular file: ' + str(path))
    return sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new isolated validation directory')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    baseline = args.baseline.resolve(strict=True)
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('validation output must be a new directory')
    specification = json.loads((here/'CHANGED_FILES.json').read_bytes())
    patch = here/'P15_high_rate.patch'
    if digest(patch) != specification['patch_sha256']:
        raise ValueError('patch digest mismatch')
    before = {}
    for row in specification['files']:
        path = Path(row['path'])
        if path.is_absolute() or '..' in path.parts or str(path) != row['path']:
            raise ValueError('unsafe patch path')
        source = baseline/path
        expected = row['baseline_sha256']
        if expected is None:
            if source.exists() or source.is_symlink():
                raise ValueError('expected new source already exists: '+str(path))
        elif digest(source) != expected:
            raise ValueError('baseline preimage mismatch: '+str(path))
        before[str(path)] = expected
    output.mkdir(parents=True)
    isolated = output/'source_subset'
    isolated.mkdir()
    for row in specification['files']:
        if row['baseline_sha256'] is not None:
            destination = isolated/row['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(baseline/row['path'], destination)
    command = ['patch', '-p1', '--fuzz=0', '--batch', '--forward', '--input', str(patch)]
    started = time.monotonic()
    result = subprocess.run(command, cwd=isolated, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.monotonic()-started
    (output/'PATCH_APPLICATION.log').write_bytes(result.stdout)
    after = {}
    for row in specification['files']:
        target = isolated/row['path']
        after[row['path']] = digest(target) if target.exists() else None
    exact = all(after[row['path']] == row['candidate_sha256'] for row in specification['files'])
    actual = {str(p.relative_to(isolated)) for p in isolated.rglob('*') if p.is_file()}
    no_extra = actual == set(after)
    unchanged = all((digest(baseline/path) == value if value is not None
                     else not (baseline/path).exists() and not (baseline/path).is_symlink())
                    for path, value in before.items())
    report = dict(status='PASS' if result.returncode == 0 and exact and no_extra and unchanged else 'FAIL',
        scope='Exact-preimage patch application and all-postimage SHA-256 comparison; no numerical test run',
        baseline=str(baseline), isolated_source=str(isolated), command=command,
        returncode=result.returncode, elapsed_s=elapsed, baseline_unchanged=unchanged,
        exact_postimages=exact, no_extra_source_files=no_extra,
        files=len(after), modified=specification['modified_files'], added=specification['added_files'],
        baseline_archive_sha256=specification['baseline_archive_sha256'],
        patch_sha256=digest(patch), specification_sha256=digest(here/'CHANGED_FILES.json'),
        validator_sha256=digest(Path(__file__)), python=sys.version,
        patch_version=subprocess.run(['patch','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0],
        preimage_sha256=before, postimage_sha256=after,
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
        nice=os.getpriority(os.PRIO_PROCESS,0) if hasattr(os,'getpriority') else None)
    (output/'RESULT.json').write_bytes(encoded(report))
    (output/'PREIMAGE_SHA256SUMS').write_text(''.join(value+'  '+path+'\n' for path,value in sorted(before.items()) if value is not None))
    (output/'POSTIMAGE_SHA256SUMS').write_text(''.join(str(value)+'  '+path+'\n' for path,value in sorted(after.items())))
    print(json.dumps({key:report[key] for key in ('status','files','modified','added','exact_postimages','baseline_unchanged','patch_sha256')},sort_keys=True))
    return 0 if report['status']=='PASS' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'status':'FAIL','error':str(error)},sort_keys=True))
        raise SystemExit(2)
