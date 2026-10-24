#!/usr/bin/env python3
"""Run the inherited BUG/CVE scripts from private, writable build-side copies.

The historical scripts use relative fixture paths and write their outputs to
CWD.  Executing them directly in $(srcdir) is not valid for VPATH builds with
read-only sources.  This runner stages only the regression cases and their
one shared src/monkey.wav input, never altering the source fixture tree.
"""
import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


def run_tests(source_test: Path, source_monkey: Path, build_test: Path,
              sox: Path, samples: Path, wav_size_state_test: Path) -> int:
    source_test = source_test.resolve(strict=True)
    source_monkey = source_monkey.resolve(strict=True)
    build_test = build_test.resolve(strict=True)
    sox = sox.resolve(strict=True)
    samples = samples.resolve(strict=True)
    wav_size_state_test = wav_size_state_test.resolve(strict=True)
    if not (source_test / 'check.sh').is_file():
        raise ValueError('regression suite check.sh missing from source')
    if not source_monkey.is_file():
        raise ValueError('shared monkey.wav regression fixture missing')
    if not build_test.is_dir():
        raise ValueError('build test directory missing')
    # Match check.sh exactly: every test/ subdirectory with a 'run' file,
    # including PATCH-*, format, DSP, and security regressions.
    cases = sorted(path for path in source_test.iterdir()
                   if path.is_dir() and (path / 'run').is_file())
    if not cases:
        raise ValueError('no regression cases found; refusing an empty test pass')

    # A new, unique build-side work directory per run avoids collisions from
    # concurrent invocations, and cleanup works even when a test fails.
    with tempfile.TemporaryDirectory(prefix='.regression-', dir=build_test) as tmp:
        root = Path(tmp)
        work_test = root / 'test'
        work_test.mkdir()
        work_src = root / 'src'
        work_src.mkdir()
        shutil.copy2(source_monkey, work_src / 'monkey.wav')
        shutil.copy2(source_test / 'check.sh', work_test / 'check.sh')
        # bit-depth/run resolves ../samples relative to its case directory.
        shutil.copy2(samples, work_test / 'samples')
        for case in cases:
            destination = work_test / case.name
            shutil.copytree(case, destination, symlinks=False)
            # Fixtures may be extracted with read-only directory modes.
            # All writes must occur within these disposable copies.
            destination.chmod(stat.S_IMODE(destination.stat().st_mode) | 0o700)

        env = dict(os.environ)
        env['sox'] = str(sox)
        env['wav_size_state_test'] = str(wav_size_state_test)
        print('staged %d regression cases in a build-side scratch directory' % len(cases),
              flush=True)
        process = subprocess.run(['/bin/sh', './check.sh', '-n'], cwd=work_test,
                                 env=env, capture_output=True, text=True)
        sys.stdout.write(process.stdout)
        sys.stdout.flush()
        if process.stderr:
            sys.stderr.write(process.stderr)
        # check.sh normally returns 0 even if no cases were selected.  Check
        # that it actually reported every staged test, rather than silently
        # giving a green result after a harness path regression.
        observed = set()
        for line in process.stdout.splitlines():
            name, sep, _result = line.partition(': ')
            if sep:
                observed.add(name)
        missing = set(case.name for case in cases) - observed
        if missing:
            print('ERROR: regression cases not executed: ' +
                  ', '.join(sorted(missing)[:8]), file=sys.stderr)
            return 2
        return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-test', required=True, type=Path)
    parser.add_argument('--source-monkey', required=True, type=Path)
    parser.add_argument('--build-test', required=True, type=Path)
    parser.add_argument('--sox', required=True, type=Path)
    parser.add_argument('--wav-size-state-test', required=True, type=Path)
    parser.add_argument('--samples', required=True, type=Path)
    args = parser.parse_args()
    try:
        return run_tests(args.source_test, args.source_monkey,
                         args.build_test, args.sox, args.samples,
                         args.wav_size_state_test)
    except (OSError, ValueError, shutil.Error) as exc:
        print('ERROR: regression setup failed: %s' % exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
