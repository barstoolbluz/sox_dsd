#!/usr/bin/env python3
"""Produce and independently apply-check a minimal patch against the input tree."""
from __future__ import annotations
import difflib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[4]
E=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18'
ORIGINAL=E/'baseline_code'
MODIFIED=('p15_src_stagewise_continuum.py','p15_src_interval_recurrence.py',
          'p15_src_stagewise_alias_proof.py')
NEW=('p15_src_fixed_interval.py','p15_src_symmetric_interval.py',
     'test_p15_prover_fixed_interval.py','p15_prover_build_corpus.py',
     'p15_prover_benchmark.py','p15_prover_cost_profile.py',
     'p15_prover_evidence_integrity.py','p15_prover_fir_microbenchmark.py',
     'p15_prover_stage_parity_audit.py','p15_prover_summarize.py')


def generate():
    parts=[]
    for name in MODIFIED+NEW:
        rel=Path('tests/dsd')/name
        source=(ORIGINAL/name).read_text().splitlines(keepends=True) if name in MODIFIED else []
        candidate=(ROOT/rel).read_text().splitlines(keepends=True)
        parts.extend(difflib.unified_diff(source,candidate,
            fromfile='a/'+str(rel) if name in MODIFIED else '/dev/null',
            tofile='b/'+str(rel)))
    patch=''.join(parts)
    dest=E/'SOURCE_CHANGES.patch'
    dest.write_text(patch)
    with tempfile.TemporaryDirectory(prefix='p15-patch-replay-') as folder:
        sandbox=Path(folder)
        sub=sandbox/'tests/dsd'
        sub.mkdir(parents=True)
        for name in MODIFIED:shutil.copyfile(ORIGINAL/name,sub/name)
        subprocess.run(['patch','-s','-p1','-d',str(sandbox),'-i',str(dest)],check=True)
        for name in MODIFIED+NEW:
            if (sub/name).read_bytes()!=(ROOT/'tests/dsd'/name).read_bytes():
                raise ValueError('patch replay content mismatch: '+name)
    print('Patch replay PASS for',len(MODIFIED),'modified and',len(NEW),'new files;',len(patch),'bytes')


if __name__=='__main__':generate()
