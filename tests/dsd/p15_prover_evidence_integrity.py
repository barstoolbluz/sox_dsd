#!/usr/bin/env python3
"""Byte-level comparison with the submitted tarball's immutable P15 evidence."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import tarfile
from p15_src_bound_operator import ROOT, SOURCES, source_identity, sha_file

OUT=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18/SOURCE_INTEGRITY.json'
PREFIXES=('tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/receipts/',
          'tests/dsd/results/P15_full_band_campaign_partial_2026-10-17/receipts/',
          'tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/budget-sample/')


def verify(tar_path):
    original=sha256(tar_path.read_bytes()).hexdigest()
    if original!='82c6e31d24b37b18ff5c60bb18f7c1dd266988da6cace9687005c2c6384365c2':
        raise ValueError('submitted source archive digest mismatch')
    counter={name:0 for name in PREFIXES}
    counter['pinned_sources']=0
    inventory=sha256()
    checked=set()
    with tarfile.open(tar_path,mode='r|gz') as tar:
        for member in tar:
            if not member.isfile() or not member.name.startswith('sox_ng/'):
                continue
            rel=member.name[len('sox_ng/'):]
            tag=(next((name for name in PREFIXES if rel.startswith(name)),None)
                 or ('pinned_sources' if rel in SOURCES else None))
            if not tag:continue
            with tar.extractfile(member) as stream:
                original_bytes=stream.read()
            now=ROOT/rel
            if now.is_symlink() or not now.is_file():
                raise ValueError('original evidence file removed or converted to symlink: '+rel)
            if len(original_bytes)!=now.stat().st_size or sha256(original_bytes).hexdigest()!=sha_file(now):
                raise ValueError('original historical evidence/source modified: '+rel)
            checked.add(rel)
            counter[tag]+=1
            inventory.update(rel.encode()+b'\0'+sha256(original_bytes).hexdigest().encode()+b'\n')
    expected={rel for name in PREFIXES for rel in (
        str(p.relative_to(ROOT)) for p in (ROOT/name).glob('*.json'))} | set(SOURCES)
    if expected!=checked:
        raise ValueError('archive/checkout evidence set inconsistent: '+str(len(expected^checked)))
    return dict(schema='P15/original-archive-immutability/1',
        archive_sha256=original,counts=counter,verified_files=len(checked),
        original_evidence_inventory_sha256=inventory.hexdigest(),
        current_pinned_source_identity=source_identity(),
        status='ALL_CHECKED_FILES_BYTE_IDENTICAL',
        scope='submitted archive pinned sources + original full, partial and budget receipts')


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--submitted',required=True,type=Path)
    args=a.parse_args()
    result=verify(args.submitted)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='current_pinned_source_identity'},indent=2))
