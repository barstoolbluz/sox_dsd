#!/usr/bin/env python3
"""Isolated DSD512 NTF candidate training, frozen guard, holdout and soak.

Run only in a disposable instrumented source checkout. This tool neither
promotes a production profile nor reuses the CLANS-7 guard. A soak report
is not a qualification certificate.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests/dsd'))
import p10_corpus
import p17_qualify_guards as p17

NATIVE = 22579200
WORKING = 176400
KEY = os.environ.get('NTF_NEW_CANDIDATE', 'o7-z5-opt')
if not KEY.startswith(('o4-','o5-','o6-','o7-')) or not KEY.replace('-','').isalnum():
    raise SystemExit('Invalid experimental candidate identity')
PROFILE = f'encode.experimental.ntf.{KEY}.dsd512'
TAG = KEY.replace('-', '_')
GUARD = ROOT/f'tests/dsd/reference/ntf_new_{TAG}_guard.json'
RESULTS = ROOT/f'tests/dsd/results/NTF_NEW_{TAG.upper()}_QUALIFICATION'
DESIGNS = ROOT/'tests/dsd/ntf_study/designs-new-native.json'
HEADER = ROOT/'src/ntf_experiment_candidates.h'
SDM = ROOT/'src/sdm.c'
P10 = ROOT/'tests/dsd/test_p10.c'
CORPUS = ROOT/'tests/dsd/p10_corpus.py'
SPLIT = ROOT/'tests/dsd/p17_qualify_guards.py'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical(x):
    return json.dumps(x, sort_keys=True, indent=2, allow_nan=False) + '\n'


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def write_once(path, obj):
    """Create once atomically; reruns may read only byte-for-byte identical data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = canonical(obj)
    if path.exists():
        if path.read_text() != body:
            raise RuntimeError('existing immutable evidence differs: ' + str(path))
        return
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix=path.name+'.tmp-',
                                      delete=False) as f:
        temp = Path(f.name)
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    try:
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_text() != body:
                raise RuntimeError('conflicting concurrent freeze: ' + str(path))
    finally:
        temp.unlink(missing_ok=True)


def definitions():
    d = json.loads(DESIGNS.read_text())['designs'][KEY]
    if d['order'] not in range(4,8) or len(d['a']) != d['order'] or len(d['g']) != d['order']:
        raise RuntimeError('invalid candidate order/coefficients')
    if any(float.fromhex(x).hex() != x for x in d['a']+d['g']):
        raise RuntimeError('not canonical binary64 coefficient words')
    if not HEADER.is_file() or not SDM.is_file():
        raise RuntimeError('instrumented source missing: run instrument_candidates.py')
    if PROFILE not in SDM.read_text() or f'"ntf-{KEY}"' not in HEADER.read_text():
        raise RuntimeError('candidate not present in instrumented source')
    return d


def source_hashes():
    return {str(p.relative_to(ROOT)): sha(p) for p in (DESIGNS, HEADER, SDM, P10,
                                                         CORPUS, SPLIT, Path(__file__))}


def cases(split):
    return [c for c in p17.configs(split) if c['native_hz'] == NATIVE]


def receipt_path(split, index, c):
    return RESULTS/split/f'{index:02d}-{c["name"]}.json'


def verified_guard():
    definitions()
    if not GUARD.is_file():
        raise RuntimeError('candidate training guard not frozen')
    g = json.loads(GUARD.read_text())
    if (g.get('schema') != 'NTF/new-P10-frozen-guards/1' or
        g.get('profile') != PROFILE or g.get('rate_hz') != NATIVE or
        g.get('qualified') is not False or g.get('holdout_used_to_set_bounds') is not False or
        g.get('candidate_definition') != {'a': definitions()['a'], 'g': definitions()['g']} or
        g.get('source_sha256') != source_hashes() or
        g.get('training_case_count') != len(cases('training'))):
        raise RuntimeError('guard/profile/source provenance mismatch')
    bounds = g.get('bounds')
    if not isinstance(bounds, list) or len(bounds) != 8 or any(
        not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 or
        v != float.fromhex(float(v).hex()) for v in bounds):
        raise RuntimeError('invalid frozen bounds')
    for name, checksum in g['training_receipts_sha256'].items():
        p = ROOT/name
        if not p.is_file() or sha(p) != checksum:
            raise RuntimeError('frozen training receipt absent or edited: '+name)
    return g


def render_case(args, split, index, c):
    receipt = receipt_path(split, index, c)
    unit_sha = sha(args.unit)
    original_id = dict(schema='NTF/new-P10-case/1',candidate_key=KEY, split=split,
         index=index, config=c, config_sha256=digest(c),
         source_sha256=source_hashes(), profile=PROFILE,
         executable_sha256=unit_sha, frozen_guard_sha256=sha(GUARD) if split=='holdout' else None)
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if not all(old.get(k) == v for k, v in original_id.items()) or old.get('complete') is not True:
            raise RuntimeError('incompatible immutable case receipt: ' + str(receipt))
        return receipt, old
    with tempfile.TemporaryDirectory(prefix='new-ntf-p10-') as folder:
        work=Path(folder)
        raw, stimulus = p10_corpus.stimulus(c)
        (work/'input.f64le').write_bytes(raw)
        mode = 'training' if split=='training' else 'guarded'
        if split == 'training':
            cmd=[str(args.unit),'--render',str(c['source_hz']),str(NATIVE),PROFILE,
                 '.5',mode,str(work/'input.f64le'),str(work/'output.bits'),str(work/'report.json')]
        else:
            g=verified_guard()
            cmd=[str(args.unit),'--render-candidate',str(c['source_hz']),str(NATIVE),PROFILE,
                 '.5',mode,str(work/'input.f64le'),str(work/'output.bits'),str(work/'report.json')]
            cmd += [float(x).hex() for x in g['bounds']]
        start=time.monotonic()
        try:
            p=subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                             timeout=args.timeout, env={**os.environ,'LSX_DSD_SDM_KERNEL':args.kernel})
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('case timed out, no evidence freeze: '+str(receipt)) from exc
        report=work/'report.json'
        if not report.is_file():
            raise RuntimeError('missing render report for '+str(receipt)+': '+p.stderr.decode(errors='replace')[-1000:])
        row={**original_id,'complete':True,'stimulus':stimulus,
            'exit_code':p.returncode,'stderr_tail':p.stderr.decode(errors='replace')[-1500:],
            'wall_seconds':time.monotonic()-start,
            'output_bytes':(work/'output.bits').stat().st_size,
            'output_sha256':sha(work/'output.bits'),
            'render':json.loads(report.read_text())}
        write_once(receipt,row)
        return receipt,row


def run_split(args, split):
    tasks=list(enumerate(cases(split)))
    if args.indices:
        chosen={int(n) for n in args.indices.split(',')}
        tasks=[(i,c) for i,c in tasks if i in chosen]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures={pool.submit(render_case,args,split,i,c):(i,c) for i,c in tasks}
        for fut in concurrent.futures.as_completed(futures):
            i,c=futures[fut]
            _,r=fut.result()
            print(split.upper(),i,c['name'],'rc',r['exit_code'],
                  'failure',r['render']['failure'],'frames',r['render']['processed_native_frames'],flush=True)


def rows(split):
    result=[]
    for i,c in enumerate(cases(split)):
        p=receipt_path(split,i,c)
        if not p.is_file():
            raise RuntimeError('missing '+split+' case: '+str(p))
        r=json.loads(p.read_text())
        if (r.get('candidate_key')!=KEY or r.get('config')!=c or r.get('config_sha256')!=digest(c) or
            r.get('source_sha256')!=source_hashes() or r.get('profile')!=PROFILE or
            r.get('complete') is not True or r['stimulus']['configuration_sha256']!=p10_corpus.identity(c)):
            raise RuntimeError('case content mismatch: '+str(p))
        result.append((p,r))
    if len({r['executable_sha256'] for _,r in result})!=1:
        raise RuntimeError('mixed test executables in '+split)
    return result


def freeze(args):
    definitions()
    tr=rows('training')
    for path,r in tr:
        rep=r['render']
        n=r['stimulus']['frames']
        total=(n*NATIVE+r['config']['source_hz']//2)//r['config']['source_hz']
        if not (r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                rep['nonfinite_states']==0 and rep['input_frames']==n and
                rep['processed_native_frames']==total and rep['committed_native_frames']==total and
                rep['windows28']==max(0,total-27) and rep['excursions28']==0 and
                rep['monitor_overloads_nominal_half']==0 and
                len(rep['max_abs_state'])==8 and all(math.isfinite(x) and x>=0 for x in rep['max_abs_state'])):
            raise RuntimeError('unadmitted training case: '+str(path))
    high=[max(float(r['render']['max_abs_state'][j]) for _,r in tr) for j in range(8)]
    bounds=[math.ldexp(1.,math.ceil(math.log2(16*max(1.,m)))) for m in high]
    frozen=dict(schema='NTF/new-P10-frozen-guards/1',profile=PROFILE,
        rate_hz=NATIVE,working_hz=WORKING,qualified=False,
        derivation='2**ceil(log2(16*max(1, per-coordinate maximum over admitted training)))',
        split='P10/P17 unguarded training, independent guarded P17 holdout',
        training_case_count=len(tr),rejected_case_count=0,
        training_max_abs_state=high,bounds=bounds,
        training_receipts_sha256={str(p.relative_to(ROOT)):sha(p) for p,_ in tr},
        source_sha256=source_hashes(),
        training_executable_sha256=tr[0][1]['executable_sha256'],
        candidate_definition={'a':definitions()['a'],'g':definitions()['g']},
        p20_clans7_guard_sha256=sha(ROOT/'tests/dsd/reference/p20_dsd512_v2_guard.json'),
        holdout_used_to_set_bounds=False)
    write_once(GUARD,frozen)
    verified_guard()
    print('FROZEN',str(GUARD.relative_to(ROOT)),sha(GUARD),'bounds',bounds,flush=True)


def holdout_assess():
    g=verified_guard();holdouts=rows('holdout');assess=[]
    for p,r in holdouts:
        c=r['config'];rep=r['render'];n=r['stimulus']['frames']
        total=(n*NATIVE+c['source_hz']//2)//c['source_hz']
        state=rep['max_abs_state'];finite=(len(state)==8 and all(isinstance(x,(int,float)) and
                  math.isfinite(x) and 0<=x<b for x,b in zip(state,g['bounds'])))
        length=(rep['input_frames']==n and rep['committed_native_frames']==total and
                rep['processed_native_frames']==total and rep['windows28']==max(0,total-27))
        if c.get('expected_overload'):
            good=(r['exit_code']!=0 and rep['failure']==2 and rep['nonfinite_states']==0)
            outcome='PASS_EXPECTED_INTERPOLATION_OVERLOAD' if good else 'FAIL'
        else:
            good=(r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                  rep['nonfinite_states']==0 and finite and length and rep['excursions28']==0 and
                  (c.get('separately_handled_fullscale') or rep['monitor_overloads_nominal_half']==0))
            outcome=('OBSERVED_FULLSCALE_NOT_NOMINAL' if c.get('separately_handled_fullscale')
                     else 'PASS') if good else 'FAIL'
        assess.append(dict(name=c['name'],status=outcome,
                           failure=rep['failure'],first_bad_frame=rep['first_bad_frame'],
                           min_ones28=rep['min_ones28'],max_ones28=rep['max_ones28'],
                           longest_run=rep['longest_run'],
                           max_guard_utilization=max((x/b for x,b in zip(state,g['bounds'])),default=None)))
    out=dict(schema='NTF/new-P10-holdout-adjudication/1',qualified=False,
         profile=PROFILE,guard_sha256=sha(GUARD),
         receipts_sha256={str(p.relative_to(ROOT)):sha(p) for p,_ in holdouts},
         case_count=len(holdouts),cases=assess,
         result='PASS' if all(r['status']!='FAIL' for r in assess) else 'FAIL')
    write_once(RESULTS/'holdout-summary.json',out)
    print('HOLDOUT',out['result'],'cases',len(assess),
          'failed',[r['name'] for r in assess if r['status']=='FAIL'],flush=True)
    return 0 if out['result']=='PASS' else 1


def host_snapshot():
    d=dict(machine=platform.machine(),os=platform.platform(),node=platform.node())
    try:d['affinity_cpu_ids']=sorted(os.sched_getaffinity(0))
    except (AttributeError,OSError):d['affinity_cpu_ids']=None
    try:d['load_average']=list(os.getloadavg())
    except (AttributeError,OSError):d['load_average']=None
    f=Path('/proc/cpuinfo')
    if f.exists():
        data={x.split(':',1)[0].strip():x.split(':',1)[1].strip()
              for x in f.read_text(errors='replace').splitlines()[:42] if ':' in x}
        d['cpu_model']=data.get('model name','')
        d['cpu_features']=data.get('flags','').split()
    return d


def audit(prefix,seconds,segment,variant,unit):
    g=verified_guard()
    rep_path=Path(str(prefix)+'-result.json');ex_path=Path(str(prefix)+'-execution.json')
    if not rep_path.exists() or not ex_path.exists():
        raise RuntimeError('raw report or execution receipt absent')
    rep=json.loads(rep_path.read_text());execution=json.loads(ex_path.read_text())
    mode='soak-candidate-nominal' if variant=='nominal' else 'soak-candidate'
    expected=[str(unit),'--soak-candidate-nominal' if variant=='nominal' else '--soak-candidate',
              str(NATIVE),str(seconds),str(segment),str(prefix),PROFILE]+[float(x).hex() for x in g['bounds']]
    checks=(execution.get('schema')=='NTF/new-prepared-host-soak/1' and
            execution.get('command')==expected and execution.get('profile')==PROFILE and
            execution.get('executable_sha256')==sha(unit) and
            execution.get('source_sha256')==source_hashes() and
            execution.get('frozen_guard_sha256')==sha(GUARD) and
            execution.get('runner_sha256')==sha(Path(__file__)) and
            execution.get('raw_report_sha256')==sha(rep_path) and
            execution.get('exit_code')==0 and execution.get('variant')==variant and
            execution.get('seconds')==seconds and execution.get('segment_seconds')==segment)
    target=seconds*NATIVE
    states=rep.get('max_abs_state') or []
    checks=checks and (rep.get('profile')==PROFILE and rep.get('mode')==mode and
        rep.get('source_hz')==WORKING and rep.get('native_hz')==NATIVE and
        rep.get('status')==3 and rep.get('failure')==0 and
        rep.get('input_frames')==seconds*WORKING and
        rep.get('committed_native_frames')==target and
        rep.get('processed_native_frames')==target and
        rep.get('first_bad_frame') is None and rep.get('nonfinite_states')==0 and
        rep.get('monitor_overloads_nominal_half')==0 and
        rep.get('excursions28')==0 and rep.get('windows28')==max(0,target-27) and
        len(states)==8 and all(math.isfinite(x) and x<bound for x,bound in zip(states,g['bounds'])) and
        7<=rep.get('min_ones28',-1)<=rep.get('max_ones28',99)<=22)
    snapshots=sorted(prefix.parent.glob(prefix.name+'-*.state'))
    final=Path(str(prefix)+'-final.state')
    checks=checks and (final.is_file() and not Path(str(prefix)+'-failure.state').exists() and
         len(snapshots)==seconds//segment+1 and execution.get('final_snapshot_sha256')==sha(final) and
         execution.get('state_snapshot_sha256')=={x.name:sha(x) for x in snapshots})
    summary=dict(schema='NTF/new-candidate-soak-assessment/1',qualified=False,
         status=('PASS_SUSTAINED_INPUT_GATE' if checks and seconds>=3600 else
                 'PASS_SHORT_SMOKE_ONLY' if checks else 'FAIL_OR_UNVERIFIED'),
         profile=PROFILE,seconds=seconds,variant=variant,
         frozen_guard_sha256=sha(GUARD),execution_receipt_sha256=sha(ex_path),
         raw_report_sha256=sha(rep_path),snapshots_sha256={x.name:sha(x) for x in snapshots},
         min_ones28=rep.get('min_ones28'),max_ones28=rep.get('max_ones28'),
         excursions28=rep.get('excursions28'),nonfinite_states=rep.get('nonfinite_states'),
         longest_constant_bit_run=rep.get('longest_run'),
         max_guard_utilization=max((x/b for x,b in zip(states,g['bounds'])),default=None),
         gates_verified=checks, limitations='One deterministic input and ISA, not production qualification')
    write_once(Path(str(prefix)+'-assessment.json'),summary)
    print(summary['status'],'longest_run',summary['longest_constant_bit_run'],
          'min28',summary['min_ones28'],'max28',summary['max_ones28'],flush=True)
    return 0 if checks else 1


def soak(args):
    g=verified_guard();prefix=args.prefix.resolve();unit=args.unit
    if args.seconds<1 or args.seconds>86400 or args.segment_seconds<1 or args.segment_seconds>args.seconds:
        raise RuntimeError('invalid soak duration')
    if args.timeout<=0 or not prefix.name:
        raise RuntimeError('invalid timeout or prefix')
    prefix.parent.mkdir(parents=True,exist_ok=True)
    report=Path(str(prefix)+'-result.json');receipt=Path(str(prefix)+'-execution.json')
    if receipt.exists():
        if audit(prefix,args.seconds,args.segment_seconds,args.variant,unit)==0:
            print('REUSED_MATCHING_COMPLETED_RUN',receipt,flush=True);return 0
        raise RuntimeError('existing run cannot be reused; use a fresh prefix')
    if any(prefix.parent.glob(prefix.name+'-*')):
        raise RuntimeError('preexisting prefix artifacts; use a fresh prefix')
    cmd=([str(unit),'--soak-candidate-nominal' if args.variant=='nominal' else '--soak-candidate',
          str(NATIVE),str(args.seconds),str(args.segment_seconds),str(prefix),PROFILE] +
         [float(x).hex() for x in g['bounds']])
    out=Path(str(prefix)+'-stdout.log');err=Path(str(prefix)+'-stderr.log')
    begin=host_snapshot();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    tick=time.monotonic()
    try:
        proc=subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,timeout=args.timeout,
            env={**os.environ,'LSX_DSD_SDM_KERNEL':args.kernel})
        rc=proc.returncode;stdout=proc.stdout;stderr=proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc=124;stdout=exc.stdout or b'';stderr=(exc.stderr or b'')+b'\nNTF_SOAK_TIMEOUT'
    wall=time.monotonic()-tick
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    out.write_bytes(stdout);err.write_bytes(stderr)
    final=Path(str(prefix)+'-final.state')
    states=sorted(prefix.parent.glob(prefix.name+'-*.state'))
    record=dict(schema='NTF/new-prepared-host-soak/1',qualified=False,profile=PROFILE,
         variant=args.variant,seconds=args.seconds,segment_seconds=args.segment_seconds,
         rate_hz=NATIVE,working_hz=WORKING,command=cmd,
         executable_sha256=sha(unit),source_sha256=source_hashes(),
         frozen_guard_sha256=sha(GUARD),candidate_sha256=sha(HEADER),
         runner_sha256=sha(Path(__file__)),exit_code=rc,
         elapsed_wall_seconds=wall,
         child_user_cpu_seconds=after.ru_utime-before.ru_utime,
         child_system_cpu_seconds=after.ru_stime-before.ru_stime,
         child_rss_kb_platform_reported=after.ru_maxrss,
         host_before=begin,host_after=host_snapshot(),kernel=args.kernel,
         raw_report_sha256=sha(report) if report.exists() else None,
         final_snapshot_sha256=sha(final) if final.exists() else None,
         state_snapshot_sha256={x.name:sha(x) for x in states},
         stdout_sha256=sha(out),stderr_sha256=sha(err))
    write_once(receipt,record)
    print('SOAK',('EXECUTED' if rc==0 else 'FAILED'),receipt,'exit',rc,flush=True)
    return audit(prefix,args.seconds,args.segment_seconds,args.variant,unit) if rc==0 else 1


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=('training','freeze','verify','holdout','adjudicate','soak','audit'))
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--jobs',type=int,default=2)
    ap.add_argument('--timeout',type=int,default=10800)
    ap.add_argument('--indices',help='partial case list, not eligible for guard freeze')
    ap.add_argument('--kernel',choices=('scalar','sse2','avx1','avx2','avx512'),default='scalar')
    ap.add_argument('--prefix',type=Path)
    ap.add_argument('--seconds',type=int,default=3600)
    ap.add_argument('--segment-seconds',type=int,default=60)
    ap.add_argument('--variant',choices=('original','nominal'),default='nominal')
    a=ap.parse_args()
    a.unit=a.unit.resolve()
    if not a.unit.is_file() or not os.access(a.unit,os.X_OK):ap.error('built P10 test binary missing')
    if not 1<=a.jobs<=5 or a.timeout<=0:ap.error('invalid worker count or timeout')
    if a.operation in ('soak','audit') and not a.prefix:ap.error('--prefix required')
    try:
        if a.operation=='training':return run_split(a,'training') or 0
        if a.operation=='freeze':freeze(a);return 0
        if a.operation=='verify':verified_guard();print('FROZEN_GUARD_VERIFIED');return 0
        if a.operation=='holdout':return run_split(a,'holdout') or 0
        if a.operation=='adjudicate':return holdout_assess()
        if a.operation=='soak':return soak(a)
        return audit(a.prefix.resolve(),a.seconds,a.segment_seconds,a.variant,a.unit)
    except (RuntimeError,ValueError,OSError,KeyError,TypeError) as exc:
        print('NTF_NEW_'+type(exc).__name__+': '+str(exc),file=sys.stderr,flush=True)
        return 2

if __name__=='__main__':raise SystemExit(main())
