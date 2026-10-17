#!/usr/bin/env python3
"""P15 prospective six-channel PHYSICAL DSD256 benchmark with corrected P/S control.

The old 20 kHz/66-kHz-edge sinc controls are not admissible. Both profiles
must be timed against the SAME full-passband-verified control definition used
by p15_dsd256_comparator_2026.py, never an after-the-fact narrowed control.

This instrument does not provide a physical measurement in a VM, and it never
unblocks release. No result is published until all arms complete. Verification
replays the bootstrap from the saved raw samples, source/bin identities and
spectral-comparability prerequisite; it does not trust the reported CI.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from p15_dsd256_comparator_2026 import (PROFILES,RATES,NATIVE,INTERMEDIATE,
                                         command as control_command,
                                         sources as comparator_sources,
                                         verify as verify_spectral)

ROOT=Path(__file__).resolve().parents[2]
SCHEMA='P15/physical-ps-matched-six-channel-benchmark/1'
ARMS=('decoder','legacy_direct','legacy_ps_matched')
BOOTSTRAP=10000
SEED=20261016
REPS=15

class BenchmarkError(ValueError):pass

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def platform_identity():
    cpu=Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').is_file() else ''
    try: aff=sorted(os.sched_getaffinity(0))
    except AttributeError: aff=[]
    def cpuval(prefix):
        return next((l.split(':',1)[1].strip() for l in cpu.splitlines()
            if l.lower().startswith(prefix)),None)
    return dict(machine=platform.machine(),system=platform.system(),
        kernel=platform.release(),cpu=cpuval('model name'),
        microcode=cpuval('microcode'),hypervisor=('hypervisor' in cpu.split()),
        allowed_cpus=aff,
        governor=(Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').read_text().strip()
            if Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').exists() else None))

def admissible_host(info,cpu):
    return (info['system']=='Linux' and info['machine'] in ('x86_64','aarch64')
            and not info['hypervisor'] and cpu in info['allowed_cpus']
            and bool(info['cpu']) and bool(info['microcode']))

def commands(sox,native,profile,rate,p,s,folder):
    """Same destination PCM representation and full effect order on all arms."""
    common=[str(sox),'-D',str(native),'-r',str(rate),
            '-e','floating-point','-b','64']
    dst=lambda arm:folder/f'{arm}-{profile.replace(".","_")}-{rate}.wav'
    return {
        'decoder':[str(sox),'-D','--dsd-layout-loss','warn',
                  str(native),'-r',str(rate),'-e','floating-point','-b','64',
                  str(dst('decoder')),'dsdpcm','-p',profile,'-l','preserve',str(rate)],
        'legacy_direct':common+[str(dst('direct')),'rate','-v'],
        'legacy_ps_matched':control_command(sox,native=native,output=dst('psmatched'),
                                             rate=rate,pass_hz=p,stop_hz=s),
    }

def bootstrap_ratio(legacy,decoded,iterations=BOOTSTRAP,seed=SEED):
    if len(legacy)!=REPS or len(decoded)!=REPS or any(
        not isinstance(x,(float,int)) or not math.isfinite(x) or x<=0
        for x in legacy+decoded):
        raise BenchmarkError('invalid repetitions')
    # Independent, seeded bootstrap of median ratio, identical on readback.
    rng=random.Random(seed)
    values=[]
    for i in range(iterations):
        a=statistics.median(legacy[rng.randrange(REPS)] for _ in range(REPS))
        b=statistics.median(decoded[rng.randrange(REPS)] for _ in range(REPS))
        values.append(a/b)
    values.sort()
    return dict(point=statistics.median(legacy)/statistics.median(decoded),
        ci95=[values[int(.025*iterations)],values[int(.975*iterations)]],
        exceeds_two_at_lower_bound=values[int(.025*iterations)]>2)

def run_cmd(argv,cpu,cwd):
    def pin():os.sched_setaffinity(0,{cpu})
    t=time.perf_counter_ns()
    p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,preexec_fn=pin)
    dt=(time.perf_counter_ns()-t)*1e-9
    if p.returncode:
        raise BenchmarkError(f'command failed {p.returncode} {argv[-8:]}: '
                 +p.stderr.decode(errors='replace')[-1200:])
    return dt

def fixture(work,sox,candidate,seconds):
    src=work/'input-6ch.wav'; dsf=work/'input-6ch.dsf'
    subprocess.run([str(sox),'-n','-r',str(INTERMEDIATE),'-b','32',
        '-e','signed-integer',str(src),'synth',str(seconds),
        'sine','997','sine','1193','sine','1511','sine','1777',
        'sine','2003','sine','2311','vol','0.25'],check=True,capture_output=True,cwd=ROOT)
    subprocess.run([str(candidate),'--dsd-layout-loss','warn',str(src),'-r',str(NATIVE),
                   str(dsf),'pcmdsd',str(NATIVE)],check=True,capture_output=True,cwd=ROOT)
    soxi=subprocess.run([str(sox),'--i','-c',str(dsf)],capture_output=True,text=True,cwd=ROOT)
    if soxi.returncode or soxi.stdout.strip()!='6':
        raise BenchmarkError('generated native fixture is not six-channel DSD')
    return src,dsf

def verify_report(directory,spectral_path,sox,candidate):
    """Independently recompute all statistics from retained raw durations."""
    directory=Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise BenchmarkError('benchmark receipt directory missing or linked')
    if {p.name for p in directory.iterdir()} != {'RECEIPT.json','input-6ch.dsf','input-6ch.wav'}:
        raise BenchmarkError('missing/unexpected benchmark payload')
    report=json.loads((directory/'RECEIPT.json').read_text())
    if report.get('schema')!=SCHEMA or report.get('qualified_release') is not False or \
       report.get('source_sha256')!=comparator_sources() or \
       report.get('executable_sha256')!=dict(sox=sha(sox),candidate=sha(candidate)):
        raise BenchmarkError('changed source, binary or receipt scope')
    if (sha(directory/'input-6ch.dsf')!=report.get('six_channel_native_sha256') or
        sha(directory/'input-6ch.wav')!=report.get('six_channel_pcm_sha256')):
        raise BenchmarkError('source input fixture modified or missing')
    proof=verify_spectral(spectral_path,sox,candidate)
    if not proof['spectrally_matched_on_fixture'] or \
       sha(spectral_path/'RECEIPT.json')!=report['spectral_receipt_sha256']:
        raise BenchmarkError('changed/invalid full-passband comparator receipt')
    if report.get('repetitions')!=REPS or report.get('warmups',0)<1 or \
       report.get('target')!=2.0 or report.get('bootstrap')!=dict(iterations=BOOTSTRAP,seed=SEED):
        raise BenchmarkError('benchmark method changed')
    host=report.get('host')
    if not host or not admissible_host(host,report.get('pinned_cpu')) or \
       report.get('physical_host_admissible') is not True:
        raise BenchmarkError('VM or unqualified host cannot be physical evidence')
    if report.get('status')!='MEASURED_PHYSICAL_UNADJUDICATED':
        raise BenchmarkError('result status invented')
    if set(report['rows'])!={p+'@'+str(rate) for p,_,_ in PROFILES for rate in RATES}:
        raise BenchmarkError('profile/rate grid incomplete')
    for profile,p,s in PROFILES:
        for rate in RATES:
            cell=report['rows'][profile+'@'+str(rate)]
            expected=commands(sox,Path('<fixture>'),profile,rate,p,s,Path('<output>'))
            if cell.get('commands')!=expected or \
               (cell.get('pass_hz'),cell.get('stop_hz'),cell.get('rate'))!=(p,s,rate):
                raise BenchmarkError('altered control or timing cell shape')
            if set(cell.get('seconds',{}))!=set(ARMS):
                raise BenchmarkError('missing raw timing arm')
            for arm in ARMS:
                r=cell['seconds'][arm]
                if (not isinstance(r,list) or len(r)!=REPS or any(
                    not isinstance(x,(float,int)) or not math.isfinite(x) or x<=0 for x in r)):
                    raise BenchmarkError('missing/invalid raw samples')
            for arm in ARMS[1:]:
                calculated=bootstrap_ratio(cell['seconds'][arm],cell['seconds']['decoder'])
                if calculated!=cell['comparisons'][arm]:
                    raise BenchmarkError('reported speedup/CI not reproducible')
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--spectral-receipt',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cpu',type=int,default=None)
    ap.add_argument('--seconds',type=int,default=2)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--verify-only',action='store_true')
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    sox=args.sox.resolve(strict=True);candidate=args.candidate.resolve(strict=True)
    spectral=args.spectral_receipt.resolve(strict=True)
    output=args.output.resolve()
    host=platform_identity()
    if args.verify_only:
        report=verify_report(output,spectral,sox,candidate)
        print(json.dumps(dict(status='VERIFIED_PHYSICAL_MEASUREMENT_RELEASE_BLOCKED',
            cells=len(report['rows']), qualified=False)))
        return 0
    proof=verify_spectral(spectral,sox,candidate)
    if not proof['spectrally_matched_on_fixture']:
        raise BenchmarkError('comparator fails full guaranteed passband')
    if args.cpu is None:
        raise BenchmarkError('explicit pinned CPU required')
    physical=admissible_host(host,args.cpu)
    if args.dry_run:
        print(json.dumps(dict(physical_host_admissible=physical,host=host,
            cells={p+'@'+str(rate): commands(sox,Path('<fixture>'),p,rate,P,S,Path('<output>'))
                  for p,P,S in PROFILES for rate in RATES},
            status='NO_TIMING_PERFORMED'),indent=2,default=str))
        return 0
    if not physical:
        raise BenchmarkError('physical prepared host required; VM results not admissible')
    if args.warmups<1 or args.seconds<1 or args.seconds>30:
        raise BenchmarkError('invalid timing duration/warmup')
    if output.exists():
        verify_report(output,spectral,sox,candidate)
        print('Verified existing receipt; no rerun/rewrite')
        return 0
    if not output.parent.exists() or output.parent.is_symlink():
        raise BenchmarkError('create trusted result directory before invoking')
    work=Path(tempfile.mkdtemp(prefix='.dsd256-ps-',dir=output.parent))
    try:
        src,native=fixture(work,sox,candidate,args.seconds)
        rows={}
        for profile,p,s in PROFILES:
            for rate in RATES:
                cmds=commands(sox,native,profile,rate,p,s,work)
                for _ in range(args.warmups):
                    for arm in ARMS:run_cmd(cmds[arm],args.cpu,ROOT)
                r={arm:[] for arm in ARMS}
                rng=random.Random(SEED+rate+p)
                for i in range(REPS):
                    order=list(ARMS);rng.shuffle(order)
                    for arm in order:r[arm].append(run_cmd(cmds[arm],args.cpu,ROOT))
                rows[profile+'@'+str(rate)]=dict(
                    pass_hz=p,stop_hz=s,rate=rate,
                    commands=commands(sox,Path('<fixture>'),profile,rate,p,s,Path('<output>')),
                    seconds=r,
                    comparisons={arm:bootstrap_ratio(r[arm],r['decoder']) for arm in ARMS[1:]})
        report=dict(schema=SCHEMA,qualified_release=False,target=2.,
            status='MEASURED_PHYSICAL_UNADJUDICATED',repetitions=REPS,
            warmups=args.warmups,fixture_seconds=args.seconds,host=host,
            physical_host_admissible=physical,pinned_cpu=args.cpu,
            source_sha256=comparator_sources(),
            executable_sha256=dict(sox=sha(sox),candidate=sha(candidate)),
            spectral_receipt_sha256=sha(spectral/'RECEIPT.json'),
            six_channel_native_sha256=sha(native),six_channel_pcm_sha256=sha(src),
            bootstrap=dict(iterations=BOOTSTRAP,seed=SEED),rows=rows,
            note='Independent adjudication required. Changed P/S control; historical 2x timings ineligible.')
        (work/'RECEIPT.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
        for pth in work.iterdir():
            if pth.name not in ('RECEIPT.json','input-6ch.dsf','input-6ch.wav'):
                pth.unlink()
        if output.exists():raise BenchmarkError('output appeared during acquisition')
        os.replace(work,output)
    finally:
        if work.exists():shutil.rmtree(work)
    verify_report(output,spectral,sox,candidate)
    print('Measured scoped physical evidence; release remains BLOCKED: '+str(output))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (BenchmarkError,OSError,ValueError,subprocess.CalledProcessError) as e:
        print('OPEN: '+str(e),file=sys.stderr);raise SystemExit(2)
