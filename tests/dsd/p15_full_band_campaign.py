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
from contextlib import contextmanager
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
import re
import signal
import threading
import time
from pathlib import Path
import sys
import tempfile

from p15_src_complete_aliases import all_active_cells
from p15_src_capture_matrix import verify_pair,DEFAULT as ACTIVE_STAGE_ROOT
from p15_src_stagewise_continuum import certificate, PROFILE_BANDS
from p15_src_bound_operator import source_identity,sha_file

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOTS=ACTIVE_STAGE_ROOT
DESIGN=ROOT/'docs/dsd/DSD_DESIGN.md'
SCHEMA='P15/full-frequency-cover-campaign/1'
PRIOR_LOCAL=ROOT/'tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/local-continuum'
ARCHIVED_PARTIAL=ROOT/'tests/dsd/results/P15_full_band_campaign_partial_2026-10-17'
# Independently pinned by the historical 43-stall routing replay.
ARCHIVED_PARTIAL_SHA256='043e5475cb9c8d054759daa20005efd675ae58b98bfd0b6d221709b1585e3045'
# Hash of the sorted (receipt filename, SHA-256-of-file) archive inventory.
ARCHIVED_RECEIPTS_SHA256='7bbd0c5c2d889ad7bb46fbc27e8ba350b2c86f877b0f5f1e7c50c04a3b80347f'

class Unproved(RuntimeError):pass


class IntervalBudgetExpired(TimeoutError):
    """Per-job wall-clock bound expired; the only disposition is OPEN."""


@contextmanager
def interval_deadline(seconds):
    """Bound synchronous interval work using SIGALRM, restoring signal state.

    Fail closed on unsupported platforms/threads. Python delivers the signal
    when interpreter control returns from an uninterruptible native call; a
    hard kill of such a call is not promised by this interface.
    """
    try:
        budget=float(seconds)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('invalid interval wall-clock budget') from exc
    if not math.isfinite(budget) or budget<=0:
        raise ValueError('invalid interval wall-clock budget')
    if (not hasattr(signal,'SIGALRM') or not hasattr(signal,'ITIMER_REAL') or
        threading.current_thread() is not threading.main_thread()):
        raise Unproved('per-interval SIGALRM deadline not supported in this context')
    previous_handler=signal.getsignal(signal.SIGALRM)
    previous_timer=signal.getitimer(signal.ITIMER_REAL)
    started=time.monotonic()
    def expired(_signal,_frame):
        raise IntervalBudgetExpired('interval wall-clock budget exhausted')
    signal.signal(signal.SIGALRM,expired)
    try:
        signal.setitimer(signal.ITIMER_REAL,budget)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous_handler)
        if previous_timer[0]>0:
            remaining=max(1e-6,previous_timer[0]-(time.monotonic()-started))
            signal.setitimer(signal.ITIMER_REAL,remaining,previous_timer[1])

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
    status=cert['status']
    # A stopband proof cannot discharge a passband job, or vice versa.
    if status!='OPEN' and status!=(
        'PASS-LOCAL-BAND' if job['mode']=='pass' else 'PASS-LOCAL-STOP-SOURCE'):
        raise Unproved('interval certificate status incompatible with job mode')
    if cert.get('qualified_release',False) is not False:
        raise Unproved('unapproved inner-certificate release upgrade')
    if status.startswith('PASS'):
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

def archived_receipt_inventory(archive_receipts):
    """Bind every historical receipt, not only the aggregate summary."""
    state=sha256()
    entries=sorted(archive_receipts.iterdir(),key=lambda p:p.name)
    for file in entries:
        if (file.is_symlink() or not file.is_file() or
            re.fullmatch(r'[0-9a-f]{64}\.json',file.name) is None):
            raise Unproved('unrecognized or linked archived receipt')
        state.update(file.name.encode('ascii')+b'\0'+sha_file(file).encode('ascii')+b'\n')
    return len(entries),state.hexdigest()


def import_archived_partial(output,*,chunk_hz='1000'):
    """Import source-matching historical receipts into an independent folder.

    Do not alter immutable historical evidence or promote an archived OPEN.
    The source SHA, job identity, certificate scope and byte-pinned historical
    summary are checked before copying; pre-existing results are unchanged.
    """
    output=Path(output)
    archive=ARCHIVED_PARTIAL.resolve()
    destination=output.resolve()
    if destination==archive or archive in destination.parents:
        raise Unproved('archived campaign requires an independent output')
    if not output.is_dir() or output.is_symlink():
        raise Unproved('trusted independent output directory required')
    summary=ARCHIVED_PARTIAL/'SUMMARY.json'
    if (not summary.is_file() or summary.is_symlink() or
        sha_file(summary)!=ARCHIVED_PARTIAL_SHA256):
        raise Unproved('archived campaign summary SHA drift or unavailable')
    historical=json.loads(summary.read_text())
    jobs=canonical_plan(chunk_hz)
    if (historical.get('intervals_nonterminating')!=43 or
        len(historical.get('nonterminating_intervals',[]))!=43 or len(jobs)!=11516):
        raise Unproved('historical campaign shape changed')
    archive_receipts=ARCHIVED_PARTIAL/'receipts'
    if not archive_receipts.is_dir() or archive_receipts.is_symlink():
        raise Unproved('archived campaign receipts missing or linked')
    receipt_count,receipt_digest=archived_receipt_inventory(archive_receipts)
    if (receipt_count!=historical.get('receipts') or
        receipt_digest!=ARCHIVED_RECEIPTS_SHA256):
        raise Unproved('archived receipt inventory missing, added or SHA drift')
    binding=bindings()
    imported=0
    for job in jobs:
        source=receipt_path(archive_receipts,job)
        proof=check_one(archive_receipts,job,binding)
        if proof is None:continue
        target=receipt_path(output,job)
        if target.exists() or target.is_symlink():
            check_one(output,job,binding)
            continue
        data=source.read_bytes()
        if json.loads(data)!=proof:
            raise Unproved('archived campaign receipt changed during import')
        fd,temp=tempfile.mkstemp(prefix='.historic-',dir=output)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.link(temp,target)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        imported+=1
    return imported


def run_campaign(output,*,chunk_hz='1000',start=0,limit=0,
                 max_nodes=128,max_paths=12000,only_cell=None,only_mode=None,
                 interval_seconds=60.0):
    try:
        budget=float(interval_seconds)
    except (TypeError,ValueError,OverflowError) as exc:
        raise Unproved('invalid per-interval wall-clock budget') from exc
    if not math.isfinite(budget) or budget<=0:
        raise Unproved('invalid per-interval wall-clock budget')
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
            try:
                with interval_deadline(budget):
                    result=certificate(job['profile'],operators[key],job['lo'],job['hi'],
                         mode=job['mode'],max_nodes=max_nodes,max_paths=max_paths)
            except IntervalBudgetExpired:
                result=dict(status='OPEN',reason='interval_wall_clock_budget_exhausted',
                    qualified_release=False,certified_hz=[job['lo'],job['hi']],
                    band_kind=job['mode'],input_hz=job['intermediate_hz'],
                    output_hz=job['output_hz'])
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
    ap.add_argument('--interval-seconds',type=float,default=60.0)
    ap.add_argument('--summary-only',action='store_true')
    ap.add_argument('--import-existing',action='store_true')
    ap.add_argument('--import-archived-partial',action='store_true')
    a=ap.parse_args()
    if a.limit<0 or a.max_nodes<1 or a.max_paths<1:raise Unproved('invalid resource bound')
    path=a.output.resolve()
    if a.import_existing:print('Verified prior local receipts imported:',import_local_witnesses(path,chunk_hz=a.chunk_hz))
    if a.import_archived_partial:print('Verified archived receipts imported:',import_archived_partial(path,chunk_hz=a.chunk_hz))
    result=(summarize(path,chunk_hz=a.chunk_hz) if a.summary_only or a.import_existing or a.import_archived_partial else
        run_campaign(path,chunk_hz=a.chunk_hz,start=a.start,limit=a.limit,
            max_nodes=a.max_nodes,max_paths=a.max_paths,
            only_cell=a.cell,only_mode=a.mode,interval_seconds=a.interval_seconds))
    print(json.dumps({k:v for k,v in result.items() if k!='cell_counts'},indent=2,sort_keys=True))
    return 0 if result['status'].startswith('COMPLETE_COVERAGE_') else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except (Unproved,OSError,ValueError,KeyError) as e:
        print('OPEN: '+str(e),file=sys.stderr)
        raise SystemExit(2)
