#!/usr/bin/env python3
"""Exercise P10 nominal receipt creation using the real encoder, not fake DSP.

The default one-second tests check receipt identity and retention; they cannot
qualify a 30-minute soak. --full-dsd64 exercises the identical writer/inspector
for one full release-duration DSD64 sequence. Rate enumeration is narrowed in
this test only; the source rate and every DSP setting are unchanged.
"""
from __future__ import annotations
import argparse
import contextlib
import io
import json
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import soak_p10


def execute(unit, results, seconds):
    args = SimpleNamespace(unit=unit, results=results, fixture='nominal-v2',
        seconds=seconds, segment_seconds=60 if seconds==1800 else seconds,
        timeout=14400, replay=False)
    with patch.object(soak_p10, 'RATES', (2822400,)):
        code = soak_p10.run(args)
    return code, json.loads((results/'soak.json').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', type=Path, default=soak_p10.ROOT/'test/dsd_test_p10')
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--full-dsd64', action='store_true')
    args = parser.parse_args()
    args.unit=args.unit.resolve();args.results.mkdir(parents=True, exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='p10-soak-receipts-') as tmp:
        work=Path(tmp)
        # A distinct executable path/hash catches an inspector that ignores
        # --unit and consults the default binary instead.
        wrapper=work/'selected-unit-executable'
        wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(args.unit))+' "$@"\n')
        wrapper.chmod(0o755)
        for unit, label in ((args.unit,'default-unit'),(wrapper,'selected-unit')):
            folder=work/label
            with contextlib.redirect_stdout(io.StringIO()):
                code, report=execute(unit,folder,1)
            row=report['profiles'][0]
            assert row['execution']['fixture']=='nominal-v2'
            assert row['execution']['binary_sha256']==soak_p10.sha(unit)
            assert row['execution']['exit_code']==0 and row['raw']['status']==3
            assert row['admission_checks']['reproducible_binary'] is True
            assert all(v for k,v in row['admission_checks'].items() if k!='release_sequence')
            assert code==1 and report['status']=='FAIL' and not report['qualified']
            cases.append(label+': correct fixture/binary receipt; short run not release-qualified')
            before={p.name:soak_p10.sha(p) for p in folder.iterdir() if p.name!='soak.json'}
            with contextlib.redirect_stdout(io.StringIO()):
                _, repeated=execute(unit,folder,1)
            after={p.name:soak_p10.sha(p) for p in folder.iterdir() if p.name!='soak.json'}
            assert before==after and repeated==report
            cases.append(label+': retained result is idempotent')
    full=None
    if args.full_dsd64:
        code, report=execute(args.unit,args.results/'nominal-dsd64',1800)
        row=report['profiles'][0]
        assert code==0 and report['status']=='PASS' and row['status']=='PASS'
        assert row['raw']['committed_native_frames']==5080320000
        assert all(row['admission_checks'].values()) and not report['qualified']
        full=dict(native_hz=2822400,seconds=1800,status='PASS',
            committed_native_frames=row['raw']['committed_native_frames'],
            snapshot_count=len(row['snapshots']),qualified=False,
            evidence='nominal-dsd64/soak.json')
        cases.append('full DSD64 nominal runner roundtrip: 1800 seconds with pinned receipt')
    out=dict(schema='P10/revalidated-soak-receipts/1',status='PASS',cases=len(cases),
        tests=cases,full_duration=full,scope='receipt generation and replay; no release promotion')
    soak_p10.atomic(args.results/'receipt-tests.json',out)
    print(json.dumps(out,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
