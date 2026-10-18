#!/usr/bin/env python3
"""Reproducible same-host P15 proof benchmark; append-only resumable results.

Baseline numerical modules are exact bytes from the input archive, retained
in the evidence directory. Historical campaign receipts are never modified.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18'
SCHEMA='P15/paired-source-bound-prover-benchmark/1'


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',choices=('baseline','optimized'),required=True)
    p.add_argument('--seconds',type=float,default=5)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--first',type=int,default=0)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--max-nodes',type=int,default=128)
    a=p.parse_args()
    if not (0<a.seconds<=3600 and math.isfinite(a.seconds)):
        raise ValueError('invalid bounded benchmark duration')
    if a.variant=='baseline':sys.path.insert(0,str(EVIDENCE/'baseline_code'))
    sys.path.insert(1,str(ROOT/'tests/dsd'))
    import p15_src_stagewise_continuum as stagewise
    from p15_src_capture_matrix import verify_pair,DEFAULT
    from p15_src_bound_operator import source_identity,sha_file
    from p15_full_band_campaign import canonical_plan

    corpus=json.loads((EVIDENCE/'CORPUS.json').read_text())['cases']
    canonical=canonical_plan()
    source=source_identity()
    source_digest=__import__('hashlib').sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    code_digest=sha_file(Path(stagewise.__file__))
    assert all(c['job']==canonical[c['index']] for c in corpus), 'corpus not canonical'
    if a.first<0 or a.first>=len(corpus) or a.limit<0:
        raise ValueError('invalid benchmark index')
    args_id=dict(variant=a.variant,seconds=a.seconds,max_nodes=a.max_nodes,
                 source_digest=source_digest,code_digest=code_digest)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    existing={}
    if a.output.exists():
        if a.output.is_symlink():raise ValueError('unsafe benchmark output')
        for line in a.output.read_text().splitlines():
            doc=json.loads(line)
            if doc['run_parameters']!=args_id or doc['schema']!=SCHEMA:
                raise ValueError('benchmark output identity conflict')
            if doc['index'] in existing:raise ValueError('duplicate completed benchmark job')
            existing[doc['index']]=doc
    op_cache={}
    count=0
    for entry in corpus[a.first:]:
        if a.limit and count>=a.limit:break
        count+=1
        index=entry['index'];job=entry['job']
        if index in existing:
            print('SKIP',index,flush=True)
            continue
        key=(job['intermediate_hz'],job['output_hz'])
        if key not in op_cache:
            _,op_cache[key]=verify_pair(DEFAULT/f'{key[0]}-{key[1]}',*key)
        op=op_cache[key]
        clocks=defaultdict(float)
        calls=defaultdict(int)
        def timed(name,func):
            def wrapper(*args,**kwargs):
                started=time.perf_counter()
                try:
                    result=func(*args,**kwargs)
                    if name=='paths' and isinstance(result,stagewise.BranchBoundary):
                        calls['exact_boundaries']+=1
                    return result
                finally:
                    clocks[name]+=time.perf_counter()-started
                    calls[name]+=1
            return wrapper
        originals={n:getattr(stagewise,n) for n in ('complete_paths','bounds_single','bound_population')}
        for name,orig in originals.items():
            setattr(stagewise,name,timed({'complete_paths':'paths','bounds_single':'fir',
                'bound_population':'population'}[name],orig))
        def expire(s,f):raise TimeoutError('benchmark wall budget')
        old_handler=signal.getsignal(signal.SIGALRM)
        start=time.perf_counter()
        signal.signal(signal.SIGALRM,expire)
        try:
            signal.setitimer(signal.ITIMER_REAL,a.seconds)
            try:
                result=stagewise.certificate(job['profile'],op,job['lo'],job['hi'],
                                              mode=job['mode'],max_nodes=a.max_nodes)
            except TimeoutError:
                result=dict(status='OPEN',reason='benchmark_interval_seconds_exhausted',
                    qualified_release=False)
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.signal(signal.SIGALRM,old_handler)
            for name,orig in originals.items():setattr(stagewise,name,orig)
        elapsed=time.perf_counter()-start
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss=int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines()
                 if line.startswith('VmRSS:')))
        doc=dict(schema=SCHEMA,index=index,cell_id=job['cell_id'],
                 job=job,run_parameters=args_id,original_receipt_status=entry['prior_status'],
                 original_receipt_reason=entry['prior_reason'],groups=entry['groups'],
                 result=result,elapsed_s=elapsed,process_high_water_kib=peak,
                 process_rss_kib=rss,profile_s=dict(clocks),profile_calls=dict(calls),
                 machine=dict(python=sys.version.split()[0],cpu=os.uname().machine))
        # One complete JSON line written and fsynced for resumability; never
        # rewrite an existing record (even when OPEN).
        data=(json.dumps(doc,sort_keys=True,allow_nan=False)+'\n').encode()
        with a.output.open('ab') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        print(a.variant,index,job['cell_id'],job['mode'],result['status'],
              result.get('reason',''),f'{elapsed:.3f}s',flush=True)


if __name__=='__main__':run()
