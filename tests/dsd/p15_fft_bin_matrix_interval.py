#!/usr/bin/env python3
"""Independent source-bound interval verification of all 24 captured SRC FFT bins.

This verifies DFT coefficients only, not execution-roundoff. Source snapshots
and source identities are verified before publication, every receipt is
immutable and byte-reproducible, and scope is explicitly recorded.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from p15_fft_coefficient_interval import certificate, DEFAULT

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/fft-bins'


def publish(path:Path, payload:dict):
    data=(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=data:
            raise ValueError('refusing receipt overwrite/replay drift: '+str(path))
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.stem+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        if path.exists():raise ValueError('receipt appeared during publication')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return True


def run(snapshot_root:Path=DEFAULT,output:Path=OUTPUT):
    snapshots=sorted(snapshot_root.glob('*/stage-snapshot.json'))
    if len(snapshots)!=24:
        raise ValueError('incomplete matrix stage snapshot inventory')
    entries=[]
    for i,path in enumerate(snapshots):
        result=certificate(path)
        p=output/(path.parent.name+'.json')
        publish(p,result)
        entries.append(dict(pair=path.parent.name,sha256=sha256(p.read_bytes()).hexdigest(),
            stages=len(result['fft_stages']),
            maximum_complex_bin_delta=max(x['max_complex_bin_deviation'] for x in result['fft_stages']),
            maximal_single_impulse_delta_bound=max(x['worst_single_impulse_bin_realization_bound'] for x in result['fft_stages'])))
        print('%d/%d FFT bin source-bound: %s'%(i+1,len(snapshots),path.parent.name),flush=True)
    summary=dict(schema='P15/24-FFT-bin-directed-interval/1',status='ALL_CAPTURED_FFT_BINS_BOUNDED',
        qualified_release=False,release='BLOCKED',distinct_source_bound_pairs=len(entries),
        all_pairs=entries,limitation='Coefficient-bin realization only; execution-roundoff and SRC Kaiser design bounds unresolved')
    publish(output/'SUMMARY.json',summary)
    return summary

if __name__=='__main__':
    print(json.dumps({k:v for k,v in run().items() if k!='all_pairs'},indent=2))
