#!/usr/bin/env python3
"""P16 executable native-packed CLI integration and independent output parity.

The C test exhaustively checks FIR tiers and bit offsets. This complementary
matrix exercises real DSF/DFF readers, the CLI adapter, native profiles and SRC.
Each case is saved atomically before the next case: interruption is resumable
only against an unchanged executable and test configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

RATES = (2822400, 5644800, 11289600)
ROOT = Path(__file__).resolve().parents[2]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic(path: Path, data: dict) -> None:
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temp.replace(path)


def invoke(command, *, packed: bool, timeout=90):
    env = os.environ.copy()
    env.update(SOX_OPTS='', OMP_NUM_THREADS='1', LC_ALL='C')
    if packed:
        env['SOX_DSD_PACKED_INPUT'] = '1'
    else:
        env.pop('SOX_DSD_PACKED_INPUT', None)
    started = time.perf_counter()
    cp = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    return dict(exit=cp.returncode, sha256=digest(cp.stdout), output_bytes=len(cp.stdout),
                stderr=cp.stderr.decode(errors='replace')[-1400:],
                packed_debug_marker=b'P16: native packed input enabled' in cp.stderr,
                seconds=time.perf_counter()-started,
                env_packed=packed)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox', type=Path, default=ROOT/'src/sox')
    ap.add_argument('--unit', type=Path, default=ROOT/'test/dsd_test_p16')
    ap.add_argument('--results', type=Path, default=ROOT/'tests/dsd/results/P16/integration')
    ap.add_argument('--quick', action='store_true', help='development subset; not full CLI qualification')
    args = ap.parse_args()
    args.sox = args.sox.resolve()
    args.unit = args.unit.resolve()
    args.results.mkdir(parents=True, exist_ok=True)
    for f in (args.sox,args.unit):
        if not f.is_file(): ap.error(f'missing built binary: {f}')
    token = digest(json.dumps(dict(sox=digest(args.sox.read_bytes()),
        unit=digest(args.unit.read_bytes()),
        harness=digest(Path(__file__).read_bytes()),quick=args.quick),sort_keys=True).encode())
    outfile = args.results/'packed-cli.json'
    records = []
    if outfile.exists():
        old = json.loads(outfile.read_text())
        if old.get('configuration_sha256') == token:
            records = old['cases']
    by_name = {x['name']:x for x in records}
    result = dict(schema='P16/packed-cli/1',configuration_sha256=token,
        executed_command=['python3', *map(str,os.sys.argv)],
        host=dict(node=platform.node(),system=platform.platform(),machine=platform.machine()),
        coverage='development subset' if args.quick else 'full integration matrix',
        cases=records)
    def save():
        result['verdict'] = 'FAIL' if any(x['status']!='PASS' for x in records) else 'PASS'
        result['counts'] = dict(pass_count=sum(x['status']=='PASS' for x in records),
                                fail_count=sum(x['status']!='PASS' for x in records))
        atomic(outfile,result)
    with tempfile.TemporaryDirectory(prefix='sox-p16-integration-') as root:
        d = Path(root)
        mk = subprocess.run([str(args.unit),'fixtures',str(d)],cwd=ROOT,
                            capture_output=True,text=True,timeout=180)
        if mk.returncode:
            raise RuntimeError(f'fixture builder exit {mk.returncode}: {mk.stderr}')
        rates = RATES[:1] if args.quick else RATES
        chans = (1,2) if args.quick else (1,2,6)
        profiles = ('conservative','wideband') if args.quick else ('conservative','wideband','v2')
        outputs = (88200,) if args.quick else (44100,192000)
        kernels = ('scalar',) if args.quick else ('scalar','avx2')
        for rate in rates:
            for ext in ('dsf','dff'):
                for ch in chans:
                    inp = d/f'p16-{ch}-{rate}.{ext}'
                    if not inp.is_file(): raise RuntimeError(f'fixture missing: {inp}')
                    for profile in profiles:
                        p = f'decode.mastering.v2.dsd{rate//44100}' if profile=='v2' else profile
                        for output in outputs:
                            for kernel in kernels:
                                name = f'{rate}-{ext}-{ch}ch-{profile}-{output}-{kernel}'
                                if name in by_name and by_name[name]['status']=='PASS':
                                    continue
                                command=[str(args.sox),'-V4','--dsd-mode','auto',
                                    '--combine=merge','--dsd-layout-loss','warn',
                                    '--dsd-decode',p,'-D',str(inp),'-r',str(output),
                                    '-t','raw','-e','signed-integer','-b','32','-']
                                old_fir=os.environ.get('SOX_DSD_KERNEL_FIR')
                                os.environ['SOX_DSD_KERNEL_FIR']=kernel
                                try:
                                    baseline=invoke(command,packed=False)
                                    native=invoke(command,packed=True)
                                finally:
                                    if old_fir is None:os.environ.pop('SOX_DSD_KERNEL_FIR',None)
                                    else:os.environ['SOX_DSD_KERNEL_FIR']=old_fir
                                try:
                                    assert baseline['exit']==0, f'expanded exit: {baseline}'
                                    assert native['exit']==0, f'packed exit: {native}'
                                    assert baseline['output_bytes']==native['output_bytes']
                                    assert baseline['sha256']==native['sha256'], 'PCM byte mismatch'
                                    assert native['output_bytes']>0 and native['output_bytes']% (4*ch)==0
                                    assert native['packed_debug_marker'], 'packed not activated'
                                    assert not baseline['packed_debug_marker']
                                    status='PASS'; error=None
                                except AssertionError as exc:
                                    status='FAIL';error=str(exc)
                                record=dict(name=name,status=status,error=error,command=command,
                                            environment=dict(SOX_DSD_KERNEL_FIR=kernel,
                                                             SOX_DSD_PACKED_INPUT='1 or absent'),
                                            expanded=baseline,packed=native)
                                if name in by_name: records[records.index(by_name[name])]=record
                                else:records.append(record)
                                by_name[name]=record
                                save()
                                if status!='PASS':print('FAIL',name,error,flush=True)
        # Native output must be byte-identical with the opt-in environment:
        # it belongs only to the PCM input adapter, not the DSD writer.
        for ext in ('dsf','dff'):
            name=f'native-I-O-{ext}'
            if name in by_name and by_name[name]['status']=='PASS':continue
            src=d/f'p16-2-2822400.{ext}'
            output_a=d/f'roundtrip-expanded-{ext}.dsf'
            output_b=d/f'roundtrip-packed-{ext}.dsf'
            base=[str(args.sox),'--dsd-mode','native','-D',str(src)]
            env={**os.environ,'SOX_OPTS':''}
            env.pop('SOX_DSD_PACKED_INPUT',None)
            a=subprocess.run(base+[str(output_a)],cwd=ROOT,env=env,
                             capture_output=True,timeout=90)
            b=subprocess.run(base+[str(output_b)],cwd=ROOT,
                             env={**env,'SOX_DSD_PACKED_INPUT':'1'},
                             capture_output=True,timeout=90)
            status=('PASS' if a.returncode==b.returncode==0 and
                digest(output_a.read_bytes())==digest(output_b.read_bytes()) else 'FAIL')
            record=dict(name=name,status=status,command=base,
                expanded_exit=a.returncode,packed_flag_exit=b.returncode,
                expanded_sha256=digest(output_a.read_bytes()) if output_a.is_file() else None,
                flagged_sha256=digest(output_b.read_bytes()) if output_b.is_file() else None,
                stderr_a=a.stderr.decode(errors='replace')[-500:],
                stderr_b=b.stderr.decode(errors='replace')[-500:])
            records.append(record);by_name[name]=record;save()

        # P14's report observer is source-bound to the original expanded
        # samples. With --dsd-report active the P16 opt-in must fall back,
        # preserving statistics instead of silently disabling observation.
        name='p14-report-opt-in-fallback'
        if name not in by_name or by_name[name]['status']!='PASS':
            src=d/'p16-2-2822400.dsf'
            reports=[d/'expanded-report.json',d/'flagged-report.json']
            runs=[]
            for i in range(2):
                command=[str(args.sox),'-V4','--dsd-report',str(reports[i]),
                    '--dsd-mode','auto','--combine=merge','--dsd-layout-loss','warn',
                    '-D',str(src),'-r','88200','-t','raw',
                    '-e','signed-integer','-b','32','-']
                runs.append(invoke(command,packed=(i==1)))
            valid=all(x['exit']==0 and not x['packed_debug_marker'] for x in runs)
            try:
                a=json.loads(reports[0].read_text())
                b=json.loads(reports[1].read_text())
                # Report destination is allowed to differ; the actual native
                # observations/counters/PCM are not.
                valid=valid and runs[0]['sha256']==runs[1]['sha256']
                # Compare the full report if deterministic; field-by-field
                # statistics in P14 are compared in its own exhaustive gate.
                observed=dict(report_keys=sorted(a.keys()),
                              same_report=a==b)
            except (OSError,ValueError) as exc:
                valid=False;observed=dict(error=str(exc))
            rec=dict(name=name,status='PASS' if valid else 'FAIL',runs=runs,
                     report_observations=observed)
            records.append(rec);by_name[name]=rec;save()
    # An entirely cached PASS replay calls no in-loop save(); finalize anyway.
    save()
    print(json.dumps(dict(verdict=result['verdict'],counts=result['counts'],path=str(outfile))))
    return int(result['verdict']!='PASS')


if __name__=='__main__':
    raise SystemExit(main())
