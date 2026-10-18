#!/usr/bin/env python3
"""Source-bound exact binary64 stage parity audit for the P15 72-cell matrix."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
from p15_src_capture_matrix import verify_pair, DEFAULT
from p15_src_complete_aliases import all_active_cells
from p15_src_stagewise_alias_proof import make_native_stages,make_src_stages
from p15_src_continuum_bounds import TrigPoly
from p15_src_symmetric_interval import even_taps
from p15_src_bound_operator import source_identity

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18/STAGE_PARITY_AUDIT.json'


def audit():
    cells=all_active_cells()
    if len(cells)!=72:raise ValueError('not the P15 72-cell matrix')
    pairs={};counts=Counter();asymmetric=[]
    unique=set()
    for c in cells:
        clock=(c['intermediate_hz'],c['output_hz'])
        if clock not in pairs:
            _,pairs[clock]=verify_pair(DEFAULT/f'{clock[0]}-{clock[1]}',*clock)
        stages=make_native_stages(c['profile'])+make_src_stages(pairs[clock])
        for stage in stages:
            poly=TrigPoly(stage.taps,0)
            is_even=even_taps(poly) is not None
            counts['stage_occurrences']+=1
            counts['exact_even_stage_occurrences']+=int(is_even)
            key=(stage.kind,stage.input_hz,stage.output_hz,stage.L,stage.M,stage.taps)
            if key not in unique:
                unique.add(key)
                counts['unique_stage_witnesses']+=1
                counts['unique_even_stage_witnesses']+=int(is_even)
            if not is_even:
                asymmetric.append(dict(cell=c['id'],stage_kind=stage.kind,
                                        stage_taps=len(stage.taps)))
    return dict(schema='P15/source-stage-even-parity/1',cells=len(cells),
        verified_pairs=len(pairs),counts=dict(counts),non_even=asymmetric,
        source_identity=source_identity(),scope='exact coefficient symmetry only; not a spectral certificate')


if __name__=='__main__':
    result=audit()
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='source_identity'},indent=2))
