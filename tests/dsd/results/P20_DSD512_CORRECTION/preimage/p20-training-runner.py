#!/usr/bin/env python3
"""DSD512 SDM v2 candidate: source-bound, write-once training and guarded holdout.

No P17 receipts, low-rate guards or production capabilities are modified.
All test cases use frozen P10 stimulus definitions and independently numbered
P17 train/holdout splits. Holdout never contributes to the guard row.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
import p10_corpus
import p17_qualify_guards as p17
RATE=22579200
ID='encode.mastering.v2.dsd512'
RESULTS=ROOT/'tests/dsd/results/P20_DSD512_CORRECTION'
FROZEN=ROOT/'tests/dsd/reference/p20_dsd512_v2_guard.json'
HEADER=ROOT/'src/pcmdsd_p20_guards.h'
TRAINING_RUNNER=RESULTS/'preimage/p20-training-runner.py'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()

def digest(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def write_once(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if path.exists():
        if path.read_text()!=body:raise RuntimeError('incompatible existing evidence: '+str(path))
        return
    tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    with tmp.open('x') as f:f.write(body)
    try:
        # Existing file cannot be silently replaced by a concurrent run.
        os.link(tmp,path)
    except FileExistsError:
        if path.read_text()!=body:raise RuntimeError('concurrent conflicting evidence: '+str(path))
    finally:tmp.unlink(missing_ok=True)

def cases(split):
    return [c for c in p17.configs(split) if c['native_hz']==RATE]

def path_for(split,i,c):
    return RESULTS/split/f'{i:02d}-{c["name"]}.json'

def run_case(arg):
    a,split,i,c=arg
    receipt=path_for(split,i,c)
    code_sha={n:sha(ROOT/n) for n in
        ('src/sdm_p20_candidates.h','tests/dsd/p10_corpus.py',
         'tests/dsd/p17_qualify_guards.py','tests/dsd/p20_qualify_dsd512.py')}
    identity=dict(schema='P20/v2-DSD512-case/1',split=split,
        config=c,config_sha256=digest(c),code_sha256=code_sha,
        executable_sha256=sha(a.unit),profile=ID,
        source_hz=c['source_hz'],native_hz=RATE)
    if receipt.exists():
        old=json.loads(receipt.read_text())
        matches=all(old.get(k)==v for k,v in identity.items())
        if not matches and split=='training' and TRAINING_RUNNER.is_file():
            # The originally used runner is archived byte-for-byte. The later
            # verifier-only fix may not invalidate or rewrite frozen training.
            archived=sha(TRAINING_RUNNER)
            original=old.get('code_sha256',{})
            a_code=dict(identity['code_sha256'])
            a_code['tests/dsd/p20_qualify_dsd512.py']=archived
            matches=(all(old.get(k)==v for k,v in identity.items() if k!='code_sha256')
                     and original==a_code and
                     old.get('complete') is True)
        if not matches or old.get('complete') is not True:
            raise RuntimeError('incompatible checkpoint: '+str(receipt))
        return receipt,old
    with tempfile.TemporaryDirectory(prefix='p20-qual-') as td:
        t=Path(td);raw,stimulus=p10_corpus.stimulus(c)
        (t/'input.f64le').write_bytes(raw)
        cmd=[str(a.unit),'--render',str(c['source_hz']),str(RATE),ID,'.5',
             'training' if split=='training' else 'guarded',
             str(t/'input.f64le'),str(t/'output.dsd'),str(t/'result.json')]
        started=time.monotonic()
        try:
            done=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,
                timeout=a.timeout,env={**os.environ,'LSX_DSD_SDM_KERNEL':a.kernel})
            returncode=done.returncode
            stderr=done.stderr.decode('utf-8',errors='replace')[-1000:]
        except subprocess.TimeoutExpired as ex:
            raise RuntimeError('TIMEOUT '+str(receipt)) from ex
        if not (t/'result.json').is_file():raise RuntimeError('missing report '+str(receipt)+' '+stderr)
        report=json.loads((t/'result.json').read_text())
        result={**identity,'complete':True,'stimulus':stimulus,
            'exit_code':returncode,'stderr_tail':stderr,
            'wall_seconds':time.monotonic()-started,
            'output_bytes':(t/'output.dsd').stat().st_size,
            'output_sha256':sha(t/'output.dsd'),'render':report}
        write_once(receipt,result)
    return receipt,result

def run_split(a,split):
    tasks=[(a,split,i,c) for i,c in enumerate(cases(split))]
    if a.indices:
        idx={int(x) for x in a.indices.split(',')}
        tasks=[t for t in tasks if t[2] in idx]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futures={ex.submit(run_case,t):t for t in tasks}
        for future in concurrent.futures.as_completed(futures):
            t=futures[future]
            path,res=future.result()
            print(split.upper(),t[2],t[3]['name'],'exit',res['exit_code'],
                'fail',res['render']['failure'],'frames',res['render']['processed_native_frames'],
                'wall',round(res['wall_seconds'],2),flush=True)
    return 0

def full_split(split):
    rows=[]
    for i,c in enumerate(cases(split)):
        p=path_for(split,i,c)
        if not p.is_file():raise RuntimeError('incomplete '+split+' receipt '+str(p))
        r=json.loads(p.read_text())
        if r['config']!=c or r['config_sha256']!=digest(c) or r['profile']!=ID:
            raise RuntimeError('invalid case '+str(p))
        if r['code_sha256']['src/sdm_p20_candidates.h']!=sha(ROOT/'src/sdm_p20_candidates.h'):
            raise RuntimeError('candidate changed after test '+str(p))
        rows.append((p,r))
    if len({r['executable_sha256'] for p,r in rows})!=1:
        raise RuntimeError('mixed executables in '+split)
    return rows

def header(bounds):
    return ('/* Frozen P20 DSD512 v2 clock-specific training bounds. NOT qualification.\n'
            ' * Distinct from immutable P10/P17 guard rows. Holdout cannot retune them. */\n'
            '#ifndef LSX_PCMDSD_V2_GUARDS_H\n#define LSX_PCMDSD_V2_GUARDS_H\n'
            'static const double lsx_pcmdsd_p20_guards[8] = {\n  '+
            ', '.join(float(x).hex() for x in bounds)+'\n};\n#endif\n')

def training(a,freeze=False):
    rows=full_split('training')
    for p,r in rows:
        rep=r['render'];frames=r['stimulus']['frames']
        total=(frames*RATE+r['source_hz']//2)//r['source_hz']
        if not (r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                rep['nonfinite_states']==0 and rep['processed_native_frames']==total and
                rep['committed_native_frames']==total and rep['input_frames']==frames and
                rep['monitor_overloads_nominal_half']==0 and rep['excursions28']==0 and
                7<=rep['min_ones28']<=rep['max_ones28']<=22 and
                all(math.isfinite(x) for x in rep['max_abs_state'])):
            raise RuntimeError('training case not admissible '+str(p))
    extrema=[max(float(r['render']['max_abs_state'][j]) for p,r in rows) for j in range(8)]
    bounds=[float(2**math.ceil(math.log2(16*max(1.,x)))) for x in extrema]
    proof=dict(schema='P20/DSD512-v2-frozen-guards/1',rate_hz=RATE,profile=ID,
        qualified=False,training_case_count=len(rows),rejected_case_count=0,
        executable_sha256=rows[0][1]['executable_sha256'],
        coefficients_sha256=sha(ROOT/'src/sdm_p20_candidates.h'),
        training_receipts_sha256={str(p.relative_to(ROOT)):sha(p) for p,r in rows},
        training_max_abs_state=extrema,bounds=bounds,
        derivation='2**ceil(log2(16*max(1,coordinate_max)))',
        split='frozen P10/P17 training; independent holdout excluded',
        old_p17_v1_guards_sha256=sha(ROOT/'tests/dsd/reference/p17_guards.json'),
        lowrate_guard_header_rows_unchanged=True,
        holdout_used_to_set_bounds=False)
    print('TRAINING_OK',len(rows),'bounds',bounds,flush=True)
    if freeze:
        # The placeholder is never a state certificate and cannot be reused after freeze.
        if FROZEN.exists():
            if FROZEN.read_text()!=json.dumps(proof,sort_keys=True,indent=2,allow_nan=False)+'\n':
                raise RuntimeError('frozen guard exists with different evidence')
        else:
            expected='P20 DSD512 v2 pre-training placeholder.'
            if expected not in HEADER.read_text():
                raise RuntimeError('unexpected guard header: not initial placeholder')
            write_once(FROZEN,proof)
            HEADER.write_text(header(bounds))
        print('FROZEN',sha(FROZEN),flush=True)
    return proof

def verify(a):
    proof=training(a,False)
    if not FROZEN.is_file() or json.loads(FROZEN.read_text())!=proof:
        raise RuntimeError('frozen proof missing or changed')
    if HEADER.read_text()!=header(proof['bounds']):raise RuntimeError('candidate bounds changed')
    original=(ROOT/'src/pcmdsd_guards.h').read_text()
    historical=(ROOT/'tests/dsd/reference/p17_guards.json')
    if proof['old_p17_v1_guards_sha256']!=sha(historical):
        raise RuntimeError('P17 v1 historical bounds changed')
    if 'lsx_pcmdsd_guards[5][8]' not in original or original.count('  {')!=5:
        raise RuntimeError('P10/P17 guards edited')
    print('VERIFY PASS',len(proof['training_receipts_sha256']),flush=True)

def adjudicate(a):
    verify(a)
    frozen=json.loads(FROZEN.read_text());bounds=frozen['bounds']
    rows=full_split('holdout');cases_out=[]
    for p,r in rows:
        rep=r['render'];conf=r['config'];frames=r['stimulus']['frames']
        total=(frames*RATE+conf['source_hz']//2)//conf['source_hz']
        correct_length=(rep['input_frames']==frames and
            rep['committed_native_frames']==total and
            rep['processed_native_frames']==total and
            rep['windows28']==max(0,total-27))
        finiteness=rep['nonfinite_states']==0 and all(math.isfinite(x) and 0<=x<=b
            for x,b in zip(rep['max_abs_state'],bounds))
        if conf.get('expected_overload'):
            passed=(r['exit_code']!=0 and rep['failure']==2 and
                rep['nonfinite_states']==0)
            status='PASS_EXPECTED_INTERPOLATION_OVERLOAD' if passed else 'FAIL'
        elif conf.get('separately_handled_fullscale'):
            passed=(r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                correct_length and finiteness)
            status='OBSERVED_FULLSCALE_NOT_NOMINAL' if passed else 'FAIL'
        else:
            passed=(r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                correct_length and finiteness and rep['monitor_overloads_nominal_half']==0 and
                rep['excursions28']==0 and
                7<=rep['min_ones28']<=rep['max_ones28']<=22)
            status='PASS' if passed else 'FAIL'
        cases_out.append(dict(case=str(p.relative_to(ROOT)),status=status,
            frames=rep['processed_native_frames'],failure=rep['failure'],
            coordinate=rep['coordinate'],nonfinite_states=rep['nonfinite_states'],
            peak=rep['peak'],excursions28=rep['excursions28'],
            min_ones28=rep['min_ones28'],max_ones28=rep['max_ones28'],
            guard_utilization=[x/b for x,b in zip(rep['max_abs_state'],bounds)]))
    out=dict(schema='P20/DSD512-v2-guarded-holdout/1',profile=ID,qualified=False,
        cases=cases_out,case_count=len(rows),frozen_guard_sha256=sha(FROZEN),
        executable_sha256=rows[0][1]['executable_sha256'],
        case_receipts_sha256={str(p.relative_to(ROOT)):sha(p) for p,r in rows},
        result='PASS' if all(c['status']!='FAIL' for c in cases_out) else 'FAIL')
    write_once(RESULTS/'holdout-summary.json',out)
    print('HOLDOUT',out['result'],'cases',len(rows),
        'failures',[x['case'] for x in cases_out if x['status']=='FAIL'],flush=True)
    return 0 if out['result']=='PASS' else 1

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=('run-training','freeze','run-holdout','verify','adjudicate'))
    ap.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--jobs',type=int,default=3)
    ap.add_argument('--timeout',type=int,default=1800)
    ap.add_argument('--indices',help='comma separated indices for partial smoke, no proof')
    ap.add_argument('--kernel',choices=('scalar','sse2','avx1','avx2','avx512'),default='scalar')
    a=ap.parse_args();a.unit=a.unit.resolve()
    if a.jobs<1 or a.jobs>6 or a.timeout<1:ap.error('invalid jobs or timeout')
    if not a.unit.is_file():ap.error('missing test binary')
    try:
        if a.operation=='run-training':return run_split(a,'training')
        if a.operation=='freeze':training(a,True);return 0
        if a.operation=='run-holdout':return run_split(a,'holdout')
        if a.operation=='verify':verify(a);return 0
        return adjudicate(a)
    except (RuntimeError,OSError,KeyError,AssertionError,ValueError) as ex:
        print('P20 '+type(ex).__name__+': '+str(ex),file=sys.stderr,flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())
