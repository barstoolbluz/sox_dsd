#!/usr/bin/env python3
"""Acquire/verify *all* P15 v1/v2 private SRC stage and alias identities.

Worklist completeness and native bank validity are hard preconditions. This
is a SOURCE BINDING / ALIAS ENUMERATION instrument, not a spectral PASS.
Historical coefficient manifests, scalar receipts and production DSP remain
unchanged; source-changing replays are refused rather than silently replaced.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile

from p15_src_bound_operator import (capture,load_snapshot,sha_file,
                                    source_identity,UnboundOperator)
from p15_src_complete_aliases import (all_active_cells,alias_families,native_profile)
from p15_src_full_chain import full_period

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16'


def verify_pair(path:Path, input_hz:int,output_hz:int) -> tuple[dict,object]:
    raw=path/'stage-snapshot.json'
    receipt=json.loads((path/'operator-binding.json').read_text())
    op=load_snapshot(raw)
    if not (receipt.get('schema')=='P15/stage-source-binding/1' and
        receipt.get('status')=='SOURCE_BOUND_UNCERTIFIED' and
        receipt.get('qualified') is False and
        receipt.get('source_sha256')==source_identity() and
        receipt.get('snapshot_sha256')==sha_file(raw) and
        (receipt.get('input_hz'),receipt.get('output_hz'))==(input_hz,output_hz) and
        (receipt.get('U'),receipt.get('V'))==(op.U,op.V) and
        receipt.get('period_multiple')==op.stage_period_multiple):
        raise UnboundOperator('invalid source/current snapshot receipt')
    if (op.input_hz,op.output_hz)!=(input_hz,output_hz):
        raise UnboundOperator('stage snapshot rate substitution')
    # Detect incorrect boundary/phase reflection in the composed operator:
    # identity holds *exactly* at the all-stage period on the ideal cascade.
    for n in (0,1,2):
        if op.shift_residual(n)!=0.0:
            raise UnboundOperator('stage-dependent clock-period identity failed')
    return receipt,op


def verify_matrix(directory:Path,exporter:Path | None=None) -> dict:
    cells=all_active_cells()
    pairs=sorted({(c['intermediate_hz'],c['output_hz']) for c in cells})
    if exporter is not None and not exporter.is_file():
        raise UnboundOperator('missing test-only stage exporter binary')
    captures={}
    for R,F in pairs:
        path=directory/f'{R}-{F}'
        if exporter is not None:
            capture(exporter,R,F,path)
        receipt,op=verify_pair(path,R,F)
        captures[(R,F)]=(receipt,op)
    recorded=[]
    total=0
    for c in cells:
        R,F=c['intermediate_hz'],c['output_hz']
        receipt,op=captures[(R,F)]
        native, r, _, _=native_profile(c['profile'])
        if r!=R:raise UnboundOperator('worklist profile/native bank mismatch')
        native_V,native_U=full_period(c['profile'],op)
        # Enumerate every family rather than inferring a count from the ratio.
        families=alias_families(native,op,1000)
        if len(families)!=native_V or native_U!=op.U:
            raise UnboundOperator('native and SRC phase lattice incomplete')
        if len({f.s for f in families})!=native_V:
            raise UnboundOperator('duplicate source family')
        if len({f.src_residue for f in families})!=op.V:
            raise UnboundOperator('missing source-phase residue classes')
        total+=len(families)
        recorded.append(dict(matrix=c['matrix'],id=c['id'],profile=c['profile'],
                    input_hz=R,output_hz=F,native_hz=native,
                    full_native_period=native_V,full_output_period=native_U,
                    alias_family_count=len(families),
                    sampled_frequency_hz='1000',
                    first_s=families[0].s,last_s=families[-1].s,
                    stage_snapshot_sha256=receipt['snapshot_sha256']))
    return dict(schema='P15/complete-source-alias-identity/1',
        status='SOURCE_BOUND_UNCERTIFIED',qualified=False,
        release='BLOCKED',tested_matrix_cells=len(cells),
        distinct_private_src_realizations=len(pairs),
        total_individually_enumerated_families_at_1khz=total,
        source_sha256=source_identity(),
        stages=[dict(input_hz=R,output_hz=F,U=op.U,V=op.V,
                     period_multiplier=op.stage_period_multiple,
                     rate_stage_types=[s.kind for s in op.stages],
                     stage_hash=receipt['snapshot_sha256'])
                for (R,F),(receipt,op) in sorted(captures.items())],
        cells=recorded,
        proofs_and_limitations=dict(
          established=('Stage coefficients and fixed-point clocks from source-inlined rate.c; '
            'verified FFT packed-bin correspondence; independent stage indexing; '
            'full stage-dependent phase period; exact native FIR bank SHA pins; '
            'finite centered FIR phase mapping; exhaustive signed native alias families.'),
          not_yet_established=('FFT4G arithmetic propagation/N_ops/B_coeff/B_other; '
            'independent Kaiser-generation proof; continuously bounded composite '
            'passband, stopband and coherent alias extrema; source-locked raw samples '
            'for normative full-chain same-transfer acceptance.'),
          forbidden_upgrade='Sampled tests and signedless hash receipts never justify a spectral/release PASS'))


def publish(summary:dict,path:Path) -> None:
    data=(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes()!=data:
            raise UnboundOperator('existing matrix summary changed/incomplete: refuse overwrite')
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.stage-summary-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if path.exists():raise UnboundOperator('matrix summary appeared during publication')
        os.replace(name,path)
        dfd=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT)
    p.add_argument('--exporter',type=Path,
                   help='test-only compiled test/dsd_test_p15_src_stage_export; omit to verify')
    args=p.parse_args()
    result=verify_matrix(args.output,args.exporter)
    publish(result,args.output/'SUMMARY.json')
    print(json.dumps({k:result[k] for k in ('status','release',
           'tested_matrix_cells','distinct_private_src_realizations',
           'total_individually_enumerated_families_at_1khz')},sort_keys=True))

if __name__=='__main__':main()
