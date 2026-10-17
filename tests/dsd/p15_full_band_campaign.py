#!/usr/bin/env python3
"""Fail-closed, source-bound P15 continuous-frequency coverage worklist.

This is a bounded, resumable CAMPAIGN DRIVER for the independent stagewise
interval proof, not an acceptance shortcut.  It partitions each of the 72
SRC-active cells' ENTIRE effective passband and ENTIRE output Nyquist for
native >=S stop-source folding; every cell/mode/interval and both endpoints
must be accounted for.  Partial coverage is OPEN; a full computed coverage
is only a mathematical *candidate* for independent re-verification, never an
automatic P15 release PASS.  The 1kHz chunk size is a scheduling decision,
not a spectral acceptance relaxation.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from p15_src_complete_aliases import all_active_cells
from p15_src_capture_matrix import verify_pair
from p15_src_stagewise_continuum import certificate, PROFILE_BANDS
from p15_src_bound_operator import source_identity,sha_file

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOTS=ROOT/'tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16'
DESIGN=ROOT/'docs/dsd/DSD_DESIGN.md'
SCHEMA='P15/full-frequency-cover-campaign/1'
PRIOR_LOCAL=ROOT/'tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/local-continuum'

class Unproved(RuntimeError):pass

def rational(x):
    try:q=Fraction(str(x))
    except Exception as e:raise Unproved('bad rational frequency') from e
    if q<0 or not math.isfinite(float(q)):
        raise Unproved('negative/nonfinite frequency')
    return q

def freqstr(q):
    return str(q.numerator) if q.denominator==1 else str(q)

def windows(lo,hi,step):
    if not 0<=lo<=hi or step<=0:
        raise Unproved('invalid frequency partition')
    current=lo
    while current<hi:
        end=min(current+step,hi)
        yield (current,end)
        current=end
    if lo==hi: yield(lo,hi)

def canonical_plan(chunk_hz=1000):
    """No user-supplied cells, narrowed edges, or inferred identity bypass."""
    step=rational(chunk_hz)
    if step<=0 or step>1000000:
        raise Unproved('unreasonable chunk size')
    cells=all_active_cells()
    if len(cells)!=72 or len({c['id'] for c in cells})!=72:
        raise Unproved('incomplete P15 matrix')
    work=[]
    for c in cells:
        name=c['profile'];r=c['intermediate_hz'];rate=c['output_hz']
        if name not in PROFILE_BANDS or r==rate:
            raise Unproved('profile or SRC-active worklist incompatible')
        declared_p,declared_s=PROFILE_BANDS[name]
        # §6.5: adapt intersects P with 0.475 * min(R, Fout).
        effective_p=min(Fraction(declared_p),Fraction(475,1000)*min(r,rate))
        for mode,end in (('pass',effective_p),('stop',Fraction(rate,2))):
            for lo,hi in windows(Fraction(0),end,step):
                work.append(dict(cell_id=c['id'],profile=name,intermediate_hz=r,
                    output_hz=rate,mode=mode,lo=freqstr(lo),hi=freqstr(hi),
                    effective_p=freqstr(effective_p),source_s=declared_s))
    return work

def digest(item):
    return sha256(json.dumps(item,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def bindings():
    return dict(source=source_identity(),design=sha_file(DESIGN))

def receipt_path(output,job):
    return output/(digest(job)+'.json')

def check_one(output,job,binding):
    file=receipt_path(output,job)
    if not file.exists():return None
    if file.is_symlink() or not file.is_file():raise Unproved('unsafe receipt path')
    doc=json.loads(file.read_text())
    if doc.get('schema')!=SCHEMA or doc.get('job')!=job or doc.get('binding')!=binding:
        raise Unproved('stale/invented source-bound receipt: '+str(file))
    if doc.get('qualified_release') is not False:
        raise Unproved('unapproved release upgrade')
    cert=doc.get('certificate')
    if not isinstance(cert,dict) or cert.get('status') not in (
      'OPEN','PASS-LOCAL-BAND','PASS-LOCAL-STOP-SOURCE'):
        raise Unproved('invalid interval disposition')
    if cert.get('status').startswith('PASS'):
        if (cert.get('certified_hz')!=[job['lo'],job['hi']] or
            cert.get('band_kind')!=job['mode'] or
            cert.get('input_hz')!=job['intermediate_hz'] or
            cert.get('output_hz')!=job['output_hz'] or
            cert.get('governing_passband_hz')!=PROFILE_BANDS[job['profile']][0]):
            raise Unproved('certified frequency/result mismatch')
    return doc

def source_operators(work):
    operators={}
    for job in work:
        key=(job['intermediate_hz'],job['output_hz'])
        if key not in operators:
            pair=SNAPSHOTS/('%s-%s'%key)
            _,operators[key]=verify_pair(pair,*key)
    if len(operators)!=24:raise Unproved('expected all 24 stage/clock realizations')
    return operators

def import_local_witnesses(output,*,chunk_hz='1000'):
    """Import only byte-pinned, exactly matching prior LOCAL proofs; no interpolation."""
    jobs=canonical_plan(chunk_hz)
    by_identity={(j['profile'],j['intermediate_hz'],j['output_hz'],
                  j['mode'],j['lo'],j['hi']):j for j in jobs}
    bind=bindings()
    if not output.is_dir() or output.is_symlink():
        raise Unproved('trusted output directory required')
    recognized=0
    for file in sorted(PRIOR_LOCAL.glob('*.json')):
        if file.is_symlink() or not file.is_file():raise Unproved('unsafe prior witness')
        proof=json.loads(file.read_text())
        key=(proof['profile'],proof['input_hz'],proof['output_hz'],
             proof['band_kind'],*proof['certified_hz'])
        job=by_identity.get(key)
        if job is None:continue
        if (proof.get('status') not in ('PASS-LOCAL-BAND','PASS-LOCAL-STOP-SOURCE')
             or proof.get('qualified_release') is not False
             or proof.get('source_sha256')!=bind['source']
             or proof.get('governing_dsd_design_sha256')!=bind['design']):
            raise Unproved('stale or invalid prior local certificate')
        pair=SNAPSHOTS/f"{job['intermediate_hz']}-{job['output_hz']}"
        verify_pair(pair,job['intermediate_hz'],job['output_hz'])
        if (proof.get('stage_snapshot_sha256')!=sha_file(pair/'stage-snapshot.json')
            or proof.get('verified_operator_binding_sha256')!=sha_file(pair/'operator-binding.json')):
            raise Unproved('prior certificate from a different SRC realization')
        doc=dict(schema=SCHEMA,job=job,binding=bind,certificate={
             k:v for k,v in proof.items() if k not in (
               'governing_dsd_design_sha256','source_sha256','stage_snapshot_sha256',
               'verified_operator_binding_sha256','schema')},
             prior_receipt_sha256=sha_file(file),
             imported_from=str(file.relative_to(ROOT)),
             qualified_release=False,mathematical_scope='local continuous interval')
        dest=receipt_path(output,job)
        data=json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n'
        if dest.exists():
            # Earlier locally recomputed proof may differ in proof metadata,
            # but MUST never be replaced by an imported counterpart.
            check_one(output,job,bind)
            continue
        fd,tmp=tempfile.mkstemp(prefix='.import-',dir=output)
        try:
            with os.fdopen(fd,'w') as f:
                f.write(data);f.flush();os.fsync(f.fileno())
            os.link(tmp,dest)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        recognized+=1
    return recognized

def run_campaign(output,*,chunk_hz='1000',start=0,limit=0,
                 max_nodes=128,max_paths=12000,only_cell=None,only_mode=None):
    jobs=canonical_plan(chunk_hz)
    bind=bindings()
    operators=source_operators(jobs)
    selected=[j for j in jobs if (only_cell is None or j['cell_id']==only_cell)
              and (only_mode is None or j['mode']==only_mode)]
    if not selected or start<0 or start>=len(selected):
        raise Unproved('invalid workload selection')
    if not output.is_dir() or output.is_symlink():
        raise Unproved('trusted output directory must exist')
    completed=0
    for job in selected[start:]:
        if limit and completed>=limit:break
        file=receipt_path(output,job)
        if check_one(output,job,bind) is None:
            key=(job['intermediate_hz'],job['output_hz'])
            result=certificate(job['profile'],operators[key],job['lo'],job['hi'],
                 mode=job['mode'],max_nodes=max_nodes,max_paths=max_paths)
            doc=dict(schema=SCHEMA,job=job,binding=bind,certificate=result,
                qualified_release=False,mathematical_scope='local continuous interval')
            data=json.dumps(doc,indent=2,sort_keys=True,allow_nan=False)+'\n'
            fd,tmp=tempfile.mkstemp(prefix='.band-',dir=output)
            try:
                with os.fdopen(fd,'w') as f:
                    f.write(data);f.flush();os.fsync(f.fileno())
                if file.exists():raise Unproved('concurrent receipt publication detected')
                # Avoid implicit overwrite on restart: hard-link temp file to
                # final destination atomically; same-device exclusive create.
                os.link(tmp,file)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        completed+=1
    return summarize(output,chunk_hz=chunk_hz, binding=bind)

def summarize(output,*,chunk_hz='1000',binding=None):
    jobs=canonical_plan(chunk_hz)
    bind=bindings() if binding is None else binding
    # Verify worklist completeness, unique immutable identity, per-job bounds,
    # and independent source/operator identity before aggregating anything.
    source_operators(jobs)
    passed=opened=missing=0
    counts={}
    for job in jobs:
        receipt=check_one(output,job,bind)
        status=('MISSING' if receipt is None else receipt['certificate']['status'])
        if status.startswith('PASS-LOCAL-'):passed+=1
        elif status=='OPEN':opened+=1
        else:missing+=1
        cell=job['cell_id'];mode=job['mode']
        ent=counts.setdefault(cell,{'pass':{'total':0,'proven':0},
                                    'stop':{'total':0,'proven':0}})[mode]
        ent['total']+=1;ent['proven']+=int(status.startswith('PASS-LOCAL-'))
    # Never write PASS to release. A coverage candidate requires independent
    # replay and auditing, including whole-chain FP error separately.
    return dict(schema=SCHEMA,status='COMPLETE_COVERAGE_CANDIDATE_UNADJUDICATED'
        if missing==opened==0 else 'OPEN',qualified_release=False,
        cells=len(counts),jobs=len(jobs),local_intervals_proven=passed,
        mathematical_intervals_open=opened,missing_receipts=missing,
        cell_counts=counts,design_sha256=bind['design'],
        source_identity_sha256=digest(bind['source']),
        acceptance_limits=dict(passband_db='0.0001',native_stop_alias_db='-160'),
        method='exact rational disjoint-interior, shared-endpoint interval cover',
        remaining='Independent recomputation, arithmetic FFT4G, and physical comparator gate')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--chunk-hz',default='1000')
    ap.add_argument('--cell')
    ap.add_argument('--mode',choices=('pass','stop'))
    ap.add_argument('--start',type=int,default=0)
    ap.add_argument('--limit',type=int,default=1)
    ap.add_argument('--max-nodes',type=int,default=128)
    ap.add_argument('--max-paths',type=int,default=12000)
    ap.add_argument('--summary-only',action='store_true')
    ap.add_argument('--import-existing',action='store_true')
    a=ap.parse_args()
    if a.limit<0 or a.max_nodes<1 or a.max_paths<1:raise Unproved('invalid resource bound')
    path=a.output.resolve()
    if a.import_existing:print('Verified prior local receipts imported:',import_local_witnesses(path,chunk_hz=a.chunk_hz))
    result=(summarize(path,chunk_hz=a.chunk_hz) if a.summary_only or a.import_existing else
        run_campaign(path,chunk_hz=a.chunk_hz,start=a.start,limit=a.limit,
            max_nodes=a.max_nodes,max_paths=a.max_paths,
            only_cell=a.cell,only_mode=a.mode))
    print(json.dumps({k:v for k,v in result.items() if k!='cell_counts'},indent=2,sort_keys=True))
    return 0 if result['status'].startswith('COMPLETE_COVERAGE_') else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except (Unproved,OSError,ValueError,KeyError) as e:
        print('OPEN: '+str(e),file=sys.stderr)
        raise SystemExit(2)
