#!/usr/bin/env python3
"""Small production DSD attribution screen, reusing project fixture/profiler helpers.

No prepared-host gate, candidate comparison or inference of speedup. Use wait4
for each child's CPU/RSS because this environment has no GNU /usr/bin/time.
"""
from pathlib import Path
import collections
import json
import os
import subprocess
import sys
import threading
import time

WORK = Path('/workspace/scratch/4dd8292178b8')
ROOT = WORK / 'sox_ng'
BUILD = WORK / 'build-baseline'
sys.path.insert(0, str(ROOT / 'tests/dsd'))
from profile_decode import atomic_json, host, make_fixture, parse_flat_profile, sha256

DEST = WORK / 'agent_dsd' / 'profile-screens'
os.sched_setaffinity(0, {3})
if DEST.exists():
    raise SystemExit('Refusing existing attribution directory')
DEST.mkdir()
SECS = 4
CASES = [
    ('dsd64-v1-native', 2822400, 'mastering', 88200),
    ('dsd64-v2-native', 2822400, 'decode.mastering.v2.dsd64', 88200),
    ('dsd128-v1-native', 5644800, 'mastering', 176400),
    ('dsd128-v2-native', 5644800, 'decode.mastering.v2.dsd128', 176400),
    ('dsd256-v1-native', 11289600, 'mastering', 176400),
    ('dsd256-v2-native', 11289600, 'decode.mastering.v2.dsd256', 176400),
    ('dsd128-v2-192k', 5644800, 'decode.mastering.v2.dsd128', 192000),
    ('dsd256-v2-384k', 11289600, 'decode.mastering.v2.dsd256', 384000),
]
report = dict(schema='production-src-opt/dsd-attribution-screen/1', status='RUNNING',
    host=host(), audio_seconds=SECS, channels=2, cpu=3, threads=1,
    input_kind='Deterministic seeded canonical native DSD bits; performance stimulus',
    build_record=json.loads((BUILD / 'build-record.json').read_text()),
    executable_sha256={n:sha256(BUILD / n) for n in ['sox_ng', 'sox_dsd_profile']},
    source_sha256={str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'src').glob('dsd*.c'))},
    fixtures={}, cases=[], limitations=[
        'Exploratory single-host screen; host is not prepared or physically qualified.',
        'Other agents are running independent work on other CPU cores.',
        'Link-only gprof histograms are coarse, may attribute neighboring symbols, and omit shared-library/kernel time.',
        'No baseline/optimized speedup or confidence interval is inferred from these attribution samples.',
        'All wall times include process initialization, complete conversion and file I/O.'
    ])

def save():
    atomic_json(DEST/'screen.json', report)

def invoke(exe, args, directory, *, profile=False):
    directory.mkdir(parents=True)
    env=dict(os.environ, SOX_OPTS='', OMP_NUM_THREADS='1', LC_ALL='C',
             SOX_DSD_KERNEL_FIR='sse2')
    for name in ('GMON_OUT_PREFIX','SOX_DSD_KERNEL_SDM','LSX_DSD_FIR_KERNEL','LSX_DSD_SDM_KERNEL'):
        env.pop(name,None)
    command=[str(exe), *map(str,args)]
    start=time.perf_counter_ns()
    with (directory/'stdout.txt').open('wb') as out, (directory/'stderr.txt').open('wb') as err:
        process=subprocess.Popen(command,cwd=directory,env=env,stdout=out,stderr=err)
        expired=threading.Event()
        def terminate():
            expired.set()
            try:process.kill()
            except ProcessLookupError:pass
        timer=threading.Timer(90,terminate)
        timer.daemon=True
        timer.start()
        try:
            _,status,usage=os.wait4(process.pid,0)
            process.returncode=os.waitstatus_to_exitcode(status)
        finally:
            timer.cancel();timer.join()
    wall=(time.perf_counter_ns()-start)*1e-9
    row=dict(command=command, exit=process.returncode, timed_out=expired.is_set(),
        wall_seconds=wall,cpu_user_seconds=usage.ru_utime,
        cpu_system_seconds=usage.ru_stime,cpu_seconds=usage.ru_utime+usage.ru_stime,
        max_rss_kib=usage.ru_maxrss, directory=str(directory.relative_to(DEST)))
    if profile:
        result=subprocess.run(['gprof','-Q','-b',str(exe),str(directory/'gmon.out')],
                              capture_output=True,text=True,check=True)
        (directory/'gprof.txt').write_text(result.stdout)
        row['profile']=parse_flat_profile(result.stdout)
    if row['exit'] or row['timed_out']:
        raise RuntimeError(f'Conversion failed: {row}')
    return row

try:
    for rate in (2822400,5644800,11289600):
        fixture=DEST/f'seeded-dsd{rate//44100}.dsf'
        make_fixture(fixture,rate,2,rate*SECS)
        report['fixtures'][str(rate)]=dict(path=str(fixture),sha256=sha256(fixture),native_frames=rate*SECS)
    save()
    for ident,native,profile,output in CASES:
        case=dict(id=ident,native_hz=native,decode_profile=profile,output_hz=output,runs=[])
        report['cases'].append(case)
        directory=DEST/ident
        fixture=DEST/f'seeded-dsd{native//44100}.dsf'
        common=['--dsd-mode','auto','--dsd-decode',profile,'-D','--single-threaded','--buffer','8192']
        expected_hash=None
        for label,exe,prof in [('diagnostic','sox_ng',False),('normal','sox_ng',False),
                               ('profile-1','sox_dsd_profile',True),('profile-2','sox_dsd_profile',True)]:
            run_dir=directory/label
            target=run_dir/'out.wav'
            args=common+(['--dsd-report',run_dir/'conversion.json'] if label=='diagnostic' else [])
            args += [fixture,'-r',str(output),'-e','floating-point','-b','64',target]
            row=invoke(BUILD/exe,args,run_dir,profile=prof)
            row['output_sha256']=sha256(target)
            row['output_bytes']=target.stat().st_size
            row['audio_seconds_per_cpu_second']=SECS/row['cpu_seconds']
            if expected_hash is None:expected_hash=row['output_sha256']
            if row['output_sha256']!=expected_hash:raise AssertionError('Production/profile output hash mismatch')
            if label=='diagnostic':
                decoder=json.loads((run_dir/'conversion.json').read_text())['processing']['decoder']
                case['decoder']=decoder
                if any(d['fir_kernel_actual']!='sse2' for d in decoder):raise AssertionError('Wrong forced FIR tier')
            target.unlink()
            case['runs'].append(row)
            save()
        bins=collections.defaultdict(float)
        for row in case['runs']:
            if 'profile' in row:
                for binrow in row['profile']['functions']:
                    bins[binrow['symbol']]+=binrow['sampled_self_seconds']
        total=sum(bins.values())
        case['sampled_executable_cpu_seconds']=total
        case['aggregate_top_symbols']=[dict(symbol=name,seconds=t,percent=100*t/total)
            for name,t in sorted(bins.items(),key=lambda x:-x[1])[:20]]
        save()
        print(ident,case['aggregate_top_symbols'][:7],flush=True)
    report['status']='COMPLETE-SCREEN-ONLY'
except BaseException as exc:
    report['status']='INCOMPLETE'
    report['error']=f'{type(exc).__name__}: {exc}'
    raise
finally:
    save()
