#!/usr/bin/env python3
"""Deterministic P15 R6 evidence audit; no historical receipts are modified."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys

from p15_src_bound_operator import sha_file,source_identity
from p15_src_complete_aliases import all_active_cells
from p15_full_band_campaign import canonical_plan,digest
from p15_r6_witness import check_proof,code_hashes,ROOT,RECEIPTS
from p15_r6_exact_policy import policy_data

EXPECTED='d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210'
BASE=ROOT/'tests/dsd'
PROOFS=BASE/'results/P15_R6_EXACT_COMPOSITE_2026-10-19'


def dependency_graph():
    """AST import dependency map for the complete locally available P15 graph."""
    roots=['p15_r6_witness','p15_r6_exact_composite','p15_r6_exact_policy',
           'p15_r5_integer_spectral','p15_r5_exact_trig',
           'p15_src_stagewise_continuum','p15_src_continuum_bounds',
           'p15_src_fixed_interval','p15_src_symmetric_interval',
           'p15_src_interval_recurrence','p15_src_difference_upper',
           'p15_src_branch_bound','p15_src_halfband_majorant',
           'p15_src_stagewise_alias_proof','p15_src_complete_aliases',
           'p15_src_capture_matrix','p15_full_band_campaign']
    seen=set();queue=roots[:];graph={}
    while queue:
        mod=queue.pop(0)
        if mod in seen:continue
        seen.add(mod);path=BASE/(mod+'.py')
        if not path.is_file():
            raise RuntimeError('dependency missing '+mod)
        tree=ast.parse(path.read_text())
        dependencies=set();outside=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): names=[x.name.split('.')[0] for x in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:
                names=[node.module.split('.')[0]]
            else:continue
            for name in names:
                if name.startswith('p15_') and (BASE/(name+'.py')).is_file():
                    dependencies.add(name);queue.append(name)
                elif name in ('mpmath','numpy','scipy','sympy','gmpy2','flint'):
                    outside.add(name)
        graph[mod]=dict(sha256=sha_file(path),local_imports=sorted(dependencies),
                        numerical_third_party_imports=sorted(outside))
    return dict(sorted(graph.items()))


def make_evidence(source_archive=None):
    if source_archive is not None and sha_file(source_archive)!=EXPECTED:
        raise RuntimeError('starting source archive SHA-256 mismatch')
    jobs=canonical_plan(1000)
    if len(jobs)!=11516 or len({digest(x) for x in jobs})!=11516:
        raise RuntimeError('canonical plan incomplete')
    rows=list(RECEIPTS.glob('*.json'))
    if len(rows)!=11516 or {x.stem for x in rows}!={digest(x) for x in jobs}:
        raise RuntimeError('receipt inventory incomplete or substituted')
    counts=Counter()
    for p in rows:
        raw=json.loads(p.read_text())
        if digest(raw.get('job'))!=p.stem:
            raise RuntimeError('historical receipt job/digest mismatch: '+p.name)
        counts[raw['certificate']['status']]+=1
    if counts!=Counter({'PASS-LOCAL-BAND':2850,'PASS-LOCAL-STOP-SOURCE':8666}):
        raise RuntimeError('historical local receipt inventory changed')
    payloads=[]
    for name in ('MASTER64_44100_PASS_0000_1000.json','MASTER64_44100_STOP_0000_1000.json'):
        p=PROOFS/name
        raw=json.loads(p.read_text())
        answer=check_proof(raw)
        payloads.append(dict(file=name,sha256=sha_file(p),reverification=answer,
                             job=raw['job'],checked_source_stage_sha256=raw['binding']['capture_stage']))
    cells=all_active_cells()
    stages={}
    for x in cells:
        key=f"{x['intermediate_hz']}-{x['output_hz']}"
        stages[key]=dict(stage=sha_file(BASE/'results/P15_SRC_STAGE_BOUND_OPT_2026-10-17'/key/'stage-snapshot.json'),
                         binding=sha_file(BASE/'results/P15_SRC_STAGE_BOUND_OPT_2026-10-17'/key/'operator-binding.json'))
    if len(stages)!=24:
        raise RuntimeError('stage pair population mismatch')
    return dict(schema='P15/R6/exact-integer-independent-certificate-evidence/1',
                date='2026-10-19',source_snapshot='cc399928',
                source_archive_sha256=EXPECTED,
                source_archive_verified_directly=source_archive is not None,
                runtime=dict(python=platform.python_version(),implementation=platform.python_implementation(),
                             proof_backend='exact Python integers/Fraction plus R5 pure-integer trigonometry'),
                artifact_code_sha256=code_hashes(),
                original_source_identity=source_identity(),
                design_sha256=sha_file(ROOT/'docs/dsd/DSD_DESIGN.md'),
                dependency_graph=dependency_graph(),
                original_coverage=dict(cells=len(cells),distinct_pairs=len(stages),
                                       canonical_jobs=len(jobs),historical_counts=dict(counts),
                                       original_mathematical_status='UNQUALIFIED_AGGREGATE_RECEIPTS'),
                stage_snapshots=stages,policy=policy_data(),
                independent_real_source_bound_proofs=payloads,
                independently_qualified_canonical_jobs=len(payloads),
                still_unqualified_canonical_jobs=len(jobs)-len(payloads),
                seven_gates=dict(continuous_frequency_inventory='PASS',
                                 independent_composite_spectral_mathematics='CONDITIONAL',
                                 source_and_execution_provenance='CONDITIONAL',
                                 arbitrary_input_FFT4G_roundoff='CONDITIONAL',
                                 end_to_end_same_operator_numerical_acceptance='CONDITIONAL',
                                 physical_DSD256_2x_release_gate='CONDITIONAL',
                                 P15_composite_SRC_overall='OPEN'),
                production_dsp_modified=False,
                qualification_comment=('Two independently rechecked 0..1000 Hz local canonical intervals '\
                       'demonstrate valid sound method; all other 11514 original jobs are not '\
                       'independently qualified, and the final ELF/FFT4G obligations remain.'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-archive',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    evidence=make_evidence(args.source_archive)
    data=(json.dumps(evidence,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists() and args.out.read_bytes()!=data:
        raise RuntimeError('evidence output conflict; will not overwrite')
    if not args.out.exists():
        import tempfile,os
        fd,p=tempfile.mkstemp(dir=args.out.parent,prefix='.r6-seal-')
        try:
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            try:os.link(p,args.out)
            except FileExistsError:
                if args.out.read_bytes()!=data:raise RuntimeError('concurrent evidence collision')
        finally:
            if os.path.exists(p):os.unlink(p)
    print(json.dumps(dict(status='CONDITIONAL',source_archive_verified=evidence['source_archive_verified_directly'],
                     independent_full_canonical_jobs=evidence['independently_qualified_canonical_jobs'],
                     original_coverage=evidence['original_coverage']['canonical_jobs'],
                     evidence_sha256=sha256(data).hexdigest()),sort_keys=True))

if __name__=='__main__':main()
