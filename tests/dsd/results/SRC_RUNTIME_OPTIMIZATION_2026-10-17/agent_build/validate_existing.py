#!/usr/bin/env python3
"""Run existing focused SoX DSD/SRC regressions against an external build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source',type=Path,required=True)
ap.add_argument('--build',type=Path,required=True)
ap.add_argument('--results',type=Path,required=True)
args=ap.parse_args()
if hasattr(os,'sched_setaffinity') and 4 in os.sched_getaffinity(0):
    os.sched_setaffinity(0,{4})
source=args.source.resolve(); build=args.build.resolve(); results=args.results.resolve()
results.mkdir(parents=True,exist_ok=True)
checks=[(name,[str(build/'test'/('dsd_test_'+name))]) for name in
        ('p07','p11','p12_bounds','p13','plan','decode_faults','dop_capacity')]
checks += [('decode_optimization_'+tier,[str(build/'test/dsd_test_decode_optimization'),tier])
           for tier in ('scalar','sse2','avx1','avx2','avx512')]
checks += [(name,[sys.executable,str(source/'tests/dsd'/('test_'+name+'.py')),
                  '--sox',str(build/'sox_ng'),'--results',str(results/name)])
           for name in ('p07','p15','p15_r3')]
checks += [('p14_numeric',[sys.executable,str(source/'tests/dsd/test_p14_numeric.py'),
                           '--sox',str(build/'sox_ng'),'--unit',str(build/'test/dsd_test_p14'),
                           '--results',str(results/'p14_numeric')])]
record={'schema':'sox/local-existing-validation/1','source':str(source),'build':str(build),
        'binary_sha256':hashlib.sha256((build/'sox_ng').read_bytes()).hexdigest(),
        'status':'RUNNING','checks':[]}
def save():
    temp=results/'summary.json.tmp'
    temp.write_text(json.dumps(record,indent=2)+'\n')
    temp.replace(results/'summary.json')
save()
for index,(name,command) in enumerate(checks):
    log=results/f'{index:02}_{name}.log'
    start=time.monotonic()
    with log.open('w') as stream:
        cp=subprocess.run(command,cwd=source,stdout=stream,stderr=subprocess.STDOUT,
                          env=dict(os.environ,SOX_OPTS='',OMP_NUM_THREADS='1',LC_ALL='C'),timeout=180)
    row={'name':name,'command':command,'exit':cp.returncode,'seconds':time.monotonic()-start,
         'log':str(log.relative_to(results))}
    record['checks'].append(row); save()
    print(f'{name}: exit={cp.returncode} {row["seconds"]:.3f}s',flush=True)
record['status']='PASS' if all(row['exit']==0 for row in record['checks']) else 'FAIL'
save()
sys.exit(record['status']!='PASS')
