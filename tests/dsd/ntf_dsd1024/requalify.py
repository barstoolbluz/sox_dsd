#!/usr/bin/env python3
"""Reproduce P19 DSD1024 guards from a clean, private *pre-freeze* checkout.

Never edits or replaces delivered training receipts, official frozen guard,
production coefficient tables, P00, or historical qualification artifacts.
Removes only cloned copies of P19 training/holdout receipts in a disposable
scratch tree. Rebuilds before and after freeze and compares with authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from model import ROOT, canonical, sha

FROZEN = Path('tests/dsd/reference/p19_dsd1024_v2_guard.json')
HEADER = Path('src/pcmdsd_v2_guards.h')
P19_RESULTS = Path('tests/dsd/results/P19_DSD1024_CORRECTION')
SOURCE_C = Path('src/sdm_p19_candidates.h')
MARKER = '.DSD1024_REQUAL_DISPOSABLE_ONLY'


def placeholder() -> str:
    return ('/* Disposable P19 requalification pre-freeze placeholder.\n'
            ' * Replaced only by P19 freeze following complete unguarded training.\n'
            ' * NOT a production or historical guard. */\n'
            '#ifndef LSX_PCMDSD_V2_GUARDS_H\n#define LSX_PCMDSD_V2_GUARDS_H\n'
            'static const double lsx_pcmdsd_v2_guards[8] = {0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100};\n'
            '#endif\n')


def authority() -> dict:
    g = json.loads((ROOT/FROZEN).read_text())
    assert g['qualified'] is False and g['rate_hz']==45158400 and g['training_case_count']==17
    if g['coefficients_sha256'] != sha(ROOT/SOURCE_C):
        raise RuntimeError('Original coefficient SHA does not match frozen guard')
    for rel, digest in g['training_receipts_sha256'].items():
        f = ROOT/rel
        if not f.is_file() or sha(f)!=digest:
            raise RuntimeError('Historical training receipt absent/changed: '+rel)
    return g


def clone_scratch(dest: Path) -> None:
    authority()
    dest=dest.resolve()
    if dest.exists() or dest.is_relative_to(ROOT.resolve()) or ROOT.resolve().is_relative_to(dest):
        raise RuntimeError('Destination must be a NEW directory outside original source')
    original = {'original_frozen_sha256':sha(ROOT/FROZEN),
                'original_guard_header_sha256':sha(ROOT/HEADER),
                'original_coefficients_sha256':sha(ROOT/SOURCE_C),
                'original_sdm_sha256':sha(ROOT/'src/sdm.c'),
                'original_p19_runner_sha256':sha(ROOT/'tests/dsd/p19_qualify_dsd1024.py')}
    shutil.copytree(ROOT,dest,symlinks=False,ignore=shutil.ignore_patterns(
        '__pycache__','*.pyc','.git','.libs','.deps','autom4te.cache'))
    (dest/MARKER).write_text(canonical(original))
    (dest/'requal-authority-preimage.json').write_text(canonical(original))
    for p in (dest/P19_RESULTS/'training').glob('*.json'):
        p.unlink()
    for p in (dest/P19_RESULTS/'holdout').glob('*.json'):
        p.unlink()
    (dest/P19_RESULTS/'holdout-summary.json').unlink(missing_ok=True)
    (dest/FROZEN).unlink()
    (dest/HEADER).write_text(placeholder())
    if len(list((dest/P19_RESULTS/'training').glob('*.json'))) != 0:
        raise RuntimeError('P19 training receipts still present in scratch')
    print('PREPARED PRIVATE P19 PRE-FREEZE',dest,flush=True)


def check(dest: Path) -> None:
    dest=dest.resolve()
    if dest==ROOT.resolve() or dest.is_relative_to(ROOT.resolve()):
        raise RuntimeError('Refusing to requalify in authority tree')
    expected={'original_frozen_sha256':sha(ROOT/FROZEN),
              'original_guard_header_sha256':sha(ROOT/HEADER),
              'original_coefficients_sha256':sha(ROOT/SOURCE_C),
              'original_sdm_sha256':sha(ROOT/'src/sdm.c'),
              'original_p19_runner_sha256':sha(ROOT/'tests/dsd/p19_qualify_dsd1024.py')}
    if not (dest/MARKER).is_file() or json.loads((dest/MARKER).read_text()) != expected:
        raise RuntimeError('Scratch marker or frozen original changed')
    for path in (SOURCE_C,Path('src/sdm.c'),Path('tests/dsd/p19_qualify_dsd1024.py')):
        if sha(dest/path)!=sha(ROOT/path):
            raise RuntimeError('Scratch source differs from verified original: '+str(path))


def run_command(args: list[str], workdir: Path, log: Path, env: dict | None = None) -> None:
    started=time.monotonic()
    with log.open('ab') as f:
        f.write(('$ '+' '.join(args)+'\n').encode())
        f.flush()
        r=subprocess.run(args,cwd=workdir,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
    if r.returncode:
        raise RuntimeError(f'Command returned {r.returncode}; see {log}: {args}')
    print('PASS',args[0],args[1:4],round(time.monotonic()-started,2),'sec',flush=True)


def requalify(dest: Path,jobs: int, evidence_dir: Path, quick: bool) -> None:
    check(dest)
    original=authority()
    evidence_dir.mkdir(parents=True,exist_ok=True)
    # This operation is for a new, pre-freeze scratch tree; reruns are
    # refused. Idempotency belongs to each P19 case receipt after creation.
    frozen=(dest/FROZEN).is_file()
    if not frozen and (dest/HEADER).read_text()!=placeholder():
        raise RuntimeError('Guard header not the designated scratch placeholder')
    if frozen:
        current=json.loads((dest/FROZEN).read_text())
        expected=('static const double lsx_pcmdsd_v2_guards[8] = {\n  ' +
                  ', '.join(float(v).hex() for v in current['bounds']))
        if expected not in (dest/HEADER).read_text():
            raise RuntimeError('Frozen scratch guard header/proof mismatch')
    make_jobs='-j'+str(jobs)
    steps=[(['autoreconf','-fi'],'autoreconf.log'),
           (['./configure','--disable-shared'],'configure.log'),
           (['make',make_jobs],'make-before.log'),
           (['make','-C','test','dsd_test_p10'],'p10-build-before.log')]
    for argv,filename in steps:
        run_command(argv,dest,evidence_dir/filename)
    unit=str(dest/'test/dsd_test_p10')
    run_command([unit,'--unit'],dest,evidence_dir/'p10-unit.log')
    runner=['python3','tests/dsd/p19_qualify_dsd1024.py']
    options=['--unit',unit,'--jobs',str(jobs),'--timeout','1800','--kernel','scalar']
    if quick:
        run_command(runner+['run-training']+options+['--indices','0,1'],dest,evidence_dir/'training-smoke.log')
        print('SMOKE ONLY: no freeze/verify/adjudication and NO qualification claim',flush=True)
        return
    if not frozen:
        run_command(runner+['run-training']+options,dest,evidence_dir/'training.log')
        run_command(runner+['freeze']+options,dest,evidence_dir/'freeze.log')
    # The guard header changed; explicitly invalidate its compiling C unit
    # rather than `make -B` (which races recursive Autotools config.status).
    (dest/'src/pcmdsd.c').touch()
    run_command(['make',make_jobs],dest,evidence_dir/'make-after.log')
    run_command(['make','-C','test','dsd_test_p10'],dest,evidence_dir/'p10-build-after.log')
    if sha(dest/'test/dsd_test_p10') == json.loads((dest/FROZEN).read_text())['executable_sha256']:
        raise RuntimeError('Post-freeze guarded P10 binary did not change; stale link suspected')
    run_command([unit,'--unit'],dest,evidence_dir/'p10-unit-after.log')
    run_command(runner+['verify']+options,dest,evidence_dir/'verify.log')
    run_command(runner+['run-holdout']+options,dest,evidence_dir/'holdout.log')
    run_command(runner+['adjudicate']+options,dest,evidence_dir/'adjudicate.log')
    current=json.loads((dest/FROZEN).read_text())
    if current['bounds'] != original['bounds']:
        raise RuntimeError('Recreated frozen bounds differ from authority; do not promote')
    max_delta=[abs(float(a)-float(b)) for a,b in zip(current['training_max_abs_state'],original['training_max_abs_state'])]
    comparison={'schema':'DSD1024-P19-independent-host-replay/1',
        'original_frozen_sha256':sha(ROOT/FROZEN),'recreated_frozen_sha256':sha(dest/FROZEN),
        'coefficients_sha256':sha(ROOT/SOURCE_C),'training_max_abs_state_abs_differences':max_delta,
        'bounds_match':True,'maxima_exact_match':max_delta==[0]*8,
        'training_cases':len(current['training_receipts_sha256']),
        'holdout_summary_sha256':sha(dest/P19_RESULTS/'holdout-summary.json'),
        'holdout_result':json.loads((dest/P19_RESULTS/'holdout-summary.json').read_text())['result'],
        'status':'REPRODUCED_IN_ISOLATED_COPY; NO PRODUCTION PROMOTION'}
    (evidence_dir/'requalification-result.json').write_text(canonical(comparison))
    print('REQUALIFIED',comparison['training_cases'],'cases, bounds',comparison['bounds_match'],flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=('prepare','run'))
    ap.add_argument('--scratch',type=Path,required=True)
    ap.add_argument('--evidence-dir',type=Path)
    ap.add_argument('--jobs',type=int,default=3)
    ap.add_argument('--quick',action='store_true')
    args=ap.parse_args()
    if args.jobs<1 or args.jobs>6:ap.error('jobs must be in 1..6')
    if args.operation=='prepare':clone_scratch(args.scratch)
    else:
        if args.evidence_dir is None:ap.error('--evidence-dir required for run')
        requalify(args.scratch.resolve(),args.jobs,args.evidence_dir.resolve(),args.quick)


if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,KeyError,OSError) as exc:
        print('REQUALIFY FAILED:',type(exc).__name__,exc,file=sys.stderr)
        raise SystemExit(2)
