#!/usr/bin/env python3
"""Reproducible, non-mutating audited-harness working-copy overlay for P08-D03.

The historical harness is extracted verbatim, has its SHA-256 inventory
verified and runs original historical tests/receipts. The *distinct* Phase08
native64 family is verified with its own runner and source/binary identities.
There is no transfer of historical calibration or results into native64.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HARNESS_SHA='7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414'
ROOT_NAME='Switched_Resonator_Qualification_Harness_AuditFixed_v2_Full'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''): h.update(data)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--immutable-archive',type=Path,required=True)
    parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--native-results',type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--sox',type=Path)
    parser.add_argument('--probe',type=Path)
    parser.add_argument('--oracle',type=Path)
    parser.add_argument('--historical-only',action='store_true')
    args=parser.parse_args()
    work=args.workdir.resolve();archive=args.immutable_archive.resolve()
    if work.exists() and tuple(work.iterdir()):
        parser.error('working copy must be new/empty; historical material is immutable')
    work.mkdir(parents=True,exist_ok=True)
    report={'schema':'p08-audited-harness-working-copy/1','status':'RUNNING',
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'immutable_archive_sha256':sha(archive),'historical':[],
            'current_native64':None}
    def run(name,command,cwd=None,env=None):
        cp=subprocess.run(list(map(str,command)),cwd=cwd,env=env,
                          capture_output=True,text=True,timeout=240)
        record={'name':name,'argv':list(map(str,command)),
                'cwd':str(cwd) if cwd else None,
                'exit_status':cp.returncode,
                'stdout_tail':cp.stdout[-4000:],
                'stderr_tail':cp.stderr[-4000:]}
        if name.startswith('historical'): report['historical'].append(record)
        (work/(name+'.stdout.log')).write_text(cp.stdout)
        (work/(name+'.stderr.log')).write_text(cp.stderr)
        if cp.returncode: raise AssertionError(f'{name}: exit {cp.returncode}: {cp.stderr[-800:]}')
        return record
    try:
        if report['immutable_archive_sha256'] != HARNESS_SHA:
            raise AssertionError('immutable audited-harness archive identity changed')
        run('historical-extract',['tar','-xf',archive,'-C',work])
        root=work/ROOT_NAME
        run('historical-inventory',['sha256sum','-c','SHA256SUMS'],root)
        harness=root/'harness'
        # The older result roots retain their own original dates, executable
        # identities and source calibration; do not copy or rewrite them.
        runtime=root/'runtime/runtime.json'
        if not runtime.is_file(): raise AssertionError('historical runtime JSON absent')
        report['historical_runtime_sha256']=sha(runtime)
        env={**os.environ,'DSDQUAL_RUNTIME':str(runtime)}
        run('historical-unittest',[sys.executable,'-m','unittest','discover','-s','tests','-v'],harness,env)
        run('historical-qualification',[sys.executable,'-m','dsdqual','verify',
            '--results',str(root/'qualification')],harness,env)
        run('historical-qualification-new',[sys.executable,'-m','dsdqual','verify',
            '--results',str(root/'qualification-new')],harness,env)
        if not args.historical_only:
            fields=('native_results','source','sox','probe','oracle')
            if any(getattr(args,f) is None for f in fields):
                raise AssertionError('current native64 qualification needs results, source and all three binaries')
            current=args.native_results.resolve();source=args.source.resolve()
            if (current==root/'qualification' or current==root/'qualification-new' or
                    current.is_relative_to(root)):
                raise AssertionError('current results must be separate from historical roots')
            receipt=json.loads((current/'qualification.json').read_text())
            git=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],
                capture_output=True,text=True,check=True).stdout.strip()
            if receipt.get('source_git_commit') != git or receipt.get('schema') != 'sox-native64-qualification/2':
                raise AssertionError('historical or stale receipt cannot qualify current native64')
            command=[sys.executable,source/'tests/pcm64/qualification/verify.py',
                 '--results',current,'--source',source,'--sox',args.sox,
                 '--probe',args.probe,'--oracle',args.oracle,'--negative-controls']
            report['current_native64']=run('current-native64',command)
            report['current_native64']['git_commit']=git
            report['current_native64']['result_root']=str(current)
            report['current_native64']['receipt_sha256']=sha(current/'qualification.json')
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc)
    (work/'WORKING_COPY_VERIFICATION.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('Audited working-copy verification:',report['status'])
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
