#!/usr/bin/env python3
"""Replay and seal ALL currently available R7 candidate certificates.

A complete canonical cell is PASS only if every planned interval has a
source-bound proof which independently reproduces the exact inequalities.
Uncovered jobs and incomplete cells remain OPEN. No historical PASS assertion
or checkpoint can increase the count. Original release gates remain distinct.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import platform

from p15_full_band_campaign import canonical_plan,digest
from p15_r6_witness import RECEIPTS,ROOT,_atomic
from p15_r7_witness import R7_FILES,HERE,verify,SCHEMA
from p15_src_bound_operator import source_identity,sha_file
from p15_r6_exact_composite import ExactRefusal

EXPECTED_ARCHIVE='d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210'
DEFAULT=HERE/'results/P15_R7_REQUALIFIED_2026-10-19'


def _recheck_one(proof_file:Path):
    proof=json.loads(proof_file.read_text())
    return proof['job'],verify(proof)


def make_evidence(folder:Path,source_archive:Path|None=None,*,workers:int=1):
    if source_archive is not None and sha_file(source_archive)!=EXPECTED_ARCHIVE:
        raise ExactRefusal('source archive identity mismatch')
    plan=canonical_plan(1000)
    byid={digest(j):j for j in plan}
    if len(plan)!=11516 or len(byid)!=11516:
        raise ExactRefusal('canonical inventory not unique/complete')
    if len(list(RECEIPTS.glob('*.json')))!=11516:
        raise ExactRefusal('original immutable inventory unexpectedly incomplete')
    if {f.stem for f in RECEIPTS.glob('*.json')}!=set(byid):
        raise ExactRefusal('original immutable receipt namespace changed')
    all_files=sorted(folder.glob('*.r7.json'))
    if not all_files:raise ExactRefusal('no certificate candidates')
    if len(all_files)>len(plan):raise ExactRefusal('more proofs than canonical jobs')
    if not 1<=workers<=8:
        raise ExactRefusal('invalid mathematical verification worker count')
    outcomes=[];seen=set();qualified_by_cell=Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
      replayed=pool.map(_recheck_one,all_files,chunksize=1)
      for n,(f,(replayed_job,check)) in enumerate(zip(all_files,replayed),1):
        # No alternate name, alias, or noncanonical re-identification accepted.
        ident=f.name.removesuffix('.r7.json')
        if f.name!=ident+'.r7.json' or ident not in byid or ident in seen:
            raise ExactRefusal('unrecognized or duplicate proof file')
        if f.is_symlink():raise ExactRefusal('refusing proof symlink')
        proof=json.loads(f.read_text())
        if proof.get('schema')!=SCHEMA or proof.get('job')!=byid[ident]:
            raise ExactRefusal('certificate job does not match canonical slot')
        if replayed_job!=byid[ident]:
            raise ExactRefusal('independent worker replay bound to wrong canonical job')
        if n%10==0 or n==len(all_files):
            print(f'VERIFIED {n}/{len(all_files)}',flush=True)
        if check['status']!='PASS-LOCAL-R7-INDEPENDENT':
            raise ExactRefusal('mathematical proof was not independently replayed')
        qualified_by_cell[byid[ident]['cell_id']]+=1
        seen.add(ident)
        outcomes.append(dict(canonical_job_digest=ident,job=byid[ident],
             certificate_sha256=sha_file(f),check=check))
    total_by_cell=Counter(j['cell_id'] for j in plan)
    completed=sorted(k for k,v in qualified_by_cell.items()
                     if v==total_by_cell[k])
    return dict(schema='P15/R7/replayed-exact-arithmetic-spectral-evidence/1',
        date='2026-10-19',source_snapshot='cc399928',
        expected_source_archive_sha256=EXPECTED_ARCHIVE,
        directly_verified_source_archive=source_archive is not None,
        production_source_identity=source_identity(),
        method_code_sha256={name:sha_file(HERE/name) for name in R7_FILES},
        source_bound_r6_method_sha256={name:sha_file(HERE/name) for name in (
            'p15_r6_exact_composite.py','p15_r6_exact_policy.py',
            'p15_r5_exact_trig.py','p15_r5_integer_spectral.py')},
        exact_arithmetic_backend='Python integers/Fraction; certified Machin pi + dyadic Taylor trig; no libm/mpmath in PASS computation',
        python_runtime=dict(version=platform.python_version(),implementation=platform.python_implementation()),
        canonical_namespace=dict(total=11516,cells=72,
            hash_of_sorted_receipt_id_list=sha256(('\n'.join(sorted(byid))+'\n').encode()).hexdigest()),
        independent_qualification=dict(verified=len(outcomes),
            not_yet_qualified=len(plan)-len(outcomes),
            complete_cells=len(completed),complete_cell_names=completed,
            verified_by_cell=dict(sorted(qualified_by_cell.items())),
            canonical_by_cell=dict(sorted(total_by_cell.items()))),
        verified_complete_interval_witnesses=outcomes,
        release_gate_dispositions=dict(continuous_frequency_inventory='PASS',
            independent_ideal_operator_spectral_mathematics=('PASS' if len(outcomes)==11516 else 'CONDITIONAL'),
            source_and_execution_provenance='CONDITIONAL',
            arbitrary_input_FFT4G_execution_roundoff='CONDITIONAL',
            end_to_end_same_operator_numerical_acceptance='CONDITIONAL',
            physical_DSD256_2x_final_release='CONDITIONAL',
            overall_P15='OPEN'),
        caveats=('Historical receipt names are inventory, not mathematical proof. '
             'A newly computed source manifest is not historical execution attestation; '
             'FFT4G compiled execution and release ELF qualification are separate.'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proofs',type=Path,default=DEFAULT)
    ap.add_argument('--source-archive',type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args()
    e=make_evidence(args.proofs,args.source_archive,workers=args.workers)
    _atomic(args.out,e)
    summary=e['independent_qualification']
    print(json.dumps(dict(status=e['release_gate_dispositions']['independent_ideal_operator_spectral_mathematics'],
        independently_qualified=summary['verified'],missing=summary['not_yet_qualified'],
        fully_qualified_cells=summary['complete_cells'],name=summary['complete_cell_names'],
        evidence_sha256=sha_file(args.out)),sort_keys=True))

if __name__=='__main__':main()
