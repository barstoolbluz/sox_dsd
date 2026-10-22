#!/usr/bin/env python3
"""Prepared-host P17 P10-method soak executor, fail-closed provenance receipt.

Private test binary only; does not enable production encoder capabilities.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def save(path,record):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(temp,path)

def host_snapshot():
    """Best-effort host facts; opaque missing fields are never evidence of a tier."""
    host=dict(machine=platform.machine(),os=platform.platform(),node=platform.node(),
              cpu_reported=platform.processor())
    try:host['affinity_cpu_ids']=sorted(os.sched_getaffinity(0))
    except (AttributeError,OSError):host['affinity_cpu_ids']=None
    try:host['load_average']=list(os.getloadavg())
    except (AttributeError,OSError):host['load_average']=None
    info=Path('/proc/cpuinfo')
    if info.is_file():
        rows=[r.strip() for r in info.read_text(errors='replace').splitlines() if ':' in r]
        first=dict(r.split(':',1) for r in rows[:48])
        host['cpu_model']=first.get('model name',first.get('Processor','')).strip()
        host['cpu_vendor']=first.get('vendor_id','').strip()
        host['cpu_stepping']=first.get('stepping','').strip()
        host['cpu_microcode']=first.get('microcode','').strip()
        host['cpu_features']=first.get('flags',first.get('Features','')).strip().split()
    governors=set()
    for item in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_governor'):
        try:governors.add(item.read_text().strip())
        except OSError:pass
    host['scaling_governors']=sorted(governors)
    return host

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rate',type=int,required=True,choices=(22579200,45158400))
    ap.add_argument('--seconds',type=int,default=3600)
    ap.add_argument('--segment-seconds',type=int,default=60)
    ap.add_argument('--mode',choices=('original-v1','nominal-v2'),required=True)
    ap.add_argument('--prefix',type=Path,required=True)
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--timeout-seconds',type=int,default=86400)
    a=ap.parse_args()
    if not 1<=a.seconds<=86400 or not 1<=a.segment_seconds<=a.seconds:
        ap.error('invalid duration or segment')
    if a.timeout_seconds<=0:ap.error('invalid timeout')
    unit=a.unit.resolve();prefix=a.prefix.resolve()
    if not unit.is_file():ap.error('private P10 test executable missing')
    prefix.parent.mkdir(parents=True,exist_ok=True)
    receipt=Path(str(prefix)+'-execution.json')
    cmd=[str(unit),'--soak' if a.mode=='original-v1' else '--soak-nominal-v2',
        str(a.rate),str(a.seconds),str(a.segment_seconds),str(prefix)]
    report=Path(str(prefix)+'-result.json');binary_sha=sha(unit)
    if receipt.exists():
        old=json.loads(receipt.read_text())
        if (old.get('command')==cmd and old.get('executable_sha256')==binary_sha
            and old.get('exit_code')==0 and report.is_file()
            and old.get('raw_report_sha256')==sha(report)):
            print('P17 SOAK REUSE',receipt);return 0
        ap.error('mismatched or failed existing run receipt; choose fresh prefix')
    out_path=Path(str(prefix)+'-stdout.log');err_path=Path(str(prefix)+'-stderr.log')
    if out_path.exists() or err_path.exists():
        ap.error('preexisting log files; choose fresh prefix')
    machine_start=host_snapshot()
    resources_start=resource.getrusage(resource.RUSAGE_CHILDREN)
    start=time.monotonic()
    try:
        proc=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,
            text=True,timeout=a.timeout_seconds)
        exit_code=proc.returncode;stdout=proc.stdout;stderr=proc.stderr
    except subprocess.TimeoutExpired as ex:
        exit_code=124
        stdout=(ex.stdout or b'').decode(errors='replace') if isinstance(ex.stdout,bytes) else (ex.stdout or '')
        stderr=(ex.stderr or b'').decode(errors='replace') if isinstance(ex.stderr,bytes) else (ex.stderr or '')
        stderr+='\nP17_SOAK_TIMEOUT'
    elapsed=time.monotonic()-start
    resources_end=resource.getrusage(resource.RUSAGE_CHILDREN)
    machine_end=host_snapshot()
    out_path.write_text(stdout);err_path.write_text(stderr)
    final=Path(str(prefix)+'-final.state')
    record=dict(schema='P17/prepared-host-soak-execution/1',command=cmd,
        mode=a.mode,rate_hz=a.rate,seconds=a.seconds,
        segment_seconds=a.segment_seconds,executable_sha256=binary_sha,
        source_sha256=sha(ROOT/'tests/dsd/test_p10.c'),
        runner_sha256=sha(Path(__file__)),exit_code=exit_code,
        elapsed_wall_seconds=elapsed,
        child_user_cpu_seconds=resources_end.ru_utime-resources_start.ru_utime,
        child_system_cpu_seconds=resources_end.ru_stime-resources_start.ru_stime,
        child_rss_kb_platform_reported=resources_end.ru_maxrss,
        machine=platform.machine(),os=platform.platform(),cpu=platform.processor(),
        host_before=machine_start,host_after=machine_end,
        raw_report_sha256=sha(report) if report.exists() else None,
        final_snapshot_sha256=sha(final) if final.exists() else None,
        stdout_sha256=sha(out_path),stderr_sha256=sha(err_path),
        qualification=False,
        note='Operator must additionally record microarchitecture, ISA, flags, CPU governor, affinity, frequency, temperatures and interfering loads')
    save(receipt,record)
    print('P17 SOAK','PASS_EXECUTED' if exit_code==0 else 'FAIL',receipt)
    return 0 if exit_code==0 else 1
if __name__=='__main__':raise SystemExit(main())
