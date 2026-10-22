#!/usr/bin/env python3
"""P17 exact-clock P10-method state bound training and isolated holdout.

All 34 training cases use the unmodified P10 stimulus definitions with exact
512/1024 native clocks. Training records per-case binary/source digests.
Freeze is write-once. Holdout can neither mutate nor calibrate the bounds.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
import p10_corpus
RATES=(22579200,45158400)
GUARDS=ROOT/'tests/dsd/reference/p17_guards.json'
HEADER=ROOT/'src/pcmdsd_guards.h'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()

def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    t=path.with_name(path.name+'.tmp')
    t.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(t,path)

def configs(split):
    definition=(p10_corpus.training_cases(11289600) if split=='training'
                else p10_corpus.holdout_cases(11289600))
    result=[]
    for rate in RATES:
        for case in definition:
            c=dict(case);c['native_hz']=rate;c['split']='P17-'+split
            c['seed']+=170000 if split=='training' else 370000
            c['skip_analysis']=True
            result.append(c)
    if split=='holdout':
        for rate in RATES:
            for src in p10_corpus.SOURCES:
                result.append(dict(name=f'matrix-{src}',kind='tone',native_hz=rate,
                    source_hz=src,seconds=1.6,frequency=997.,dbfs=-6.,
                    taper_seconds=.1,seed=671009,split='P17-rate-matrix',skip_analysis=True))
    return result

def case_run(args,config,split,index):
    rate=config['native_hz'];id=f'encode.mastering.v1.dsd{rate//44100}'
    folder=args.results/split/str(rate)
    name=f'{index:02d}-{config["name"]}';receipt=folder/(name+'.json')
    config_sha=digest(config);binary_sha=sha(args.unit)
    corpus_sha=sha(ROOT/'tests/dsd/p10_corpus.py')
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if not (previous.get('state')=='COMPLETED' and
            previous.get('config_sha256')==config_sha and
            previous.get('binary_sha256')==binary_sha and
            previous.get('stimulus_generator_sha256')==corpus_sha):
            raise RuntimeError('incompatible checkpoint; refusing replacement: '+str(receipt))
        return previous
    folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p17-guard-') as directory:
        t=Path(directory);raw,stimulus=p10_corpus.stimulus(config)
        inp=t/'input.f64le';out=t/'bits.out';report=t/'monitor.json'
        inp.write_bytes(raw)
        command=[str(args.unit),'--render',str(config['source_hz']),str(rate),id,
            '.5','training' if split=='training' else 'guarded',str(inp),str(out),str(report)]
        started=time.monotonic()
        proc=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,
            text=True,timeout=args.timeout)
        result=dict(schema='P17/guard-case/1',state='COMPLETED',split=split,
            name=name,config=config,config_sha256=config_sha,stimulus=stimulus,
            unit_path='test/dsd_test_p10',binary_sha256=binary_sha,
            stimulus_generator_sha256=corpus_sha,
            command=['test/dsd_test_p10','--render',str(config['source_hz']),
                str(rate),id,'.5',command[6],'<private-f64le>',
                '<temporary-packed-bits>','<temporary-render-report>'],
            exit_code=proc.returncode,stderr_tail=proc.stderr[-2000:],
            elapsed_seconds=time.monotonic()-started,
            output_sha256=sha(out) if out.exists() else None,
            output_bytes=out.stat().st_size if out.exists() else None,
            render=json.loads(report.read_text()) if report.exists() else None)
        if not result['render']:raise RuntimeError('missing monitor report: '+name)
        atomic(receipt,result)
        return result

def read_rows(args,split):
    rows=[]
    for rate in RATES:
        cases=[c for c in configs(split) if c['native_hz']==rate]
        for idx,c in enumerate(cases):
            p=args.results/split/str(rate)/f'{idx:02d}-{c["name"]}.json'
            if not p.is_file():return None
            r=json.loads(p.read_text())
            if not (r.get('state')=='COMPLETED' and
                r.get('config_sha256')==digest(c) and r.get('config')==c and
                r.get('stimulus_generator_sha256')==sha(ROOT/'tests/dsd/p10_corpus.py')):
                raise RuntimeError('case integrity mismatch '+str(p))
            if split=='holdout' and r['binary_sha256']!=sha(args.unit):
                raise RuntimeError('mixed executable versions in holdout '+str(p))
            rows.append((p,r))
    if split=='training' and len({r['binary_sha256'] for p,r in rows})!=1:
        raise RuntimeError('mixed executable versions in training')
    return rows

def expected_header(guards):
    old=HEADER.read_text()
    known='#define LSX_PCMDSD_CERTIFICATE_SHA256 "df25a2a11855e8a380cd756cf38769701103338faf36b46271aa3df22bc5157e"'
    if known not in old:raise RuntimeError('P10 certificate modified')
    m=re.search(r'static const double lsx_pcmdsd_guards\[3\]\[8\] = \{\n((?:  \{[^\n]+\},\n){3})\};',old)
    if m is None:
        m=re.search(r'static const double lsx_pcmdsd_guards\[5\]\[8\] = \{\n((?:  \{[^\n]+\},\n){3})(?:  \{[^\n]+\},\n){2}\};',old)
    if m is None:raise RuntimeError('unknown P10/P17 guard header format')
    preserved=m.group(1)
    new=''.join('  {'+', '.join(float(x).hex() for x in guards[str(rate)]['bounds'])+'},\n'
                for rate in RATES)
    return old.split('static const double lsx_pcmdsd_guards[')[0]+\
        'static const double lsx_pcmdsd_guards[5][8] = {\n'+preserved+new+\
        '};\n'+old[old.index(known):]

def train(args):
    if GUARDS.exists():raise RuntimeError('guards already frozen; run verify, never retrain')
    for rate in RATES:
        for idx,c in enumerate(x for x in configs('training') if x['native_hz']==rate):
            r=case_run(args,c,'training',idx)
            print('TRAIN',rate,idx,c['name'],r['exit_code'],flush=True)
    rows=read_rows(args,'training')
    if rows is None or len(rows)!=34:raise RuntimeError('incomplete training')
    profiles={}
    for rate in RATES:
        subset=[r for p,r in rows if r['config']['native_hz']==rate]
        accepted=[r for r in subset if r['exit_code']==0 and r['render']['status']==3]
        if not accepted:raise RuntimeError('no accepted training input')
        maxima=[max(float(r['render']['max_abs_state'][j]) for r in accepted) for j in range(8)]
        if any(not math.isfinite(x) or x<0 for x in maxima):raise RuntimeError('invalid state maxima')
        bounds=[math.ldexp(1.,math.ceil(math.log2(16*max(1.,x)))) for x in maxima]
        profiles[str(rate)]=dict(bounds=bounds,max_abs_state=maxima,
            admitted_case_count=len(accepted),rejected_case_count=len(subset)-len(accepted),
            admitted=[r['config_sha256'] for r in accepted],
            rejected=[r['config_sha256'] for r in subset if r not in accepted])
    frozen=dict(schema='P17/operational-guards/1',qualified=False,
        derivation='2**ceil(log2(16*max(1, per-coordinate maximum over admitted training)))',
        P10_training_method='tests/dsd/qualify_p10.py train',
        frozen_low_rate_guard_rows_preserved=True,holdout_used_to_set_bounds=False,
        training_corpus_sha256=digest(configs('training')),
        training_case_count=len(rows),
        case_receipt_sha256={str(p.relative_to(ROOT)):sha(p) for p,r in rows},
        executable_sha256=sha(args.unit),
        p10_source_corpus_sha256=sha(ROOT/'tests/dsd/p10_corpus.py'),
        profiles=profiles,highrate_qualified=False)
    atomic(GUARDS,frozen)
    header=expected_header(profiles)
    temp=HEADER.with_name(HEADER.name+'.tmp');temp.write_text(header);os.replace(temp,HEADER)
    print('FROZEN',GUARDS,sha(GUARDS),flush=True)
    return 0

def holdout(args):
    if not GUARDS.is_file():raise RuntimeError('no frozen training before holdout')
    frozen=json.loads(GUARDS.read_text())
    if frozen['training_case_count']!=34 or frozen['holdout_used_to_set_bounds']:
        raise RuntimeError('invalid frozen guard evidence')
    for rate in RATES:
        for idx,c in enumerate(x for x in configs('holdout') if x['native_hz']==rate):
            r=case_run(args,c,'holdout',idx)
            print('HOLDOUT',rate,idx,c['name'],r['exit_code'],flush=True)
    rows=read_rows(args,'holdout')
    if rows is None:raise RuntimeError('incomplete holdout')
    verdict=[]
    for p,r in rows:
        c=r['config'];rep=r['render']
        bounds=frozen['profiles'][str(c['native_hz'])]['bounds']
        expect_fail=bool(c.get('expected_overload'))
        separate_fullscale=bool(c.get('separately_handled_fullscale'))
        frames=r['stimulus']['frames']
        expected_native=(frames*c['native_hz']+c['source_hz']//2)//c['source_hz']
        correct_length=(rep['input_frames']==frames and
            rep['committed_native_frames']==expected_native and
            rep['processed_native_frames']==expected_native and
            rep['windows28']==max(0,expected_native-27))
        finiteness=(rep['nonfinite_states']==0 and len(rep['max_abs_state'])==8 and
            all(math.isfinite(x) and 0<=x<=b
                for x,b in zip(rep['max_abs_state'],bounds)))
        if separate_fullscale:
            # P10's baseline explicitly excludes 0 dBFS tones from ordinary
            # nominal-overload and 28-bit population acceptance. Preserve the
            # raw excursions instead of disguising them as nominal successes.
            passed=(r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                rep['first_bad_frame'] is None and correct_length and finiteness)
            state='OBSERVED_SPECIAL_FULLSCALE' if passed else 'FAIL'
        elif expect_fail:
            # The intentional excessive-envelope source must trip the expected
            # interpolation-envelope gate, not merely some unrelated guard.
            passed=(r['exit_code']!=0 and rep['failure']==2 and
                    rep['nonfinite_states']==0)
            state='PASS' if passed else 'FAIL'
        else:
            passed=(r['exit_code']==0 and rep['status']==3 and rep['failure']==0 and
                rep['first_bad_frame'] is None and correct_length and finiteness and
                rep['monitor_overloads_nominal_half']==0)
            state='PASS' if passed else 'FAIL'
        verdict.append(dict(case_path=str(p.relative_to(ROOT)),status=state,
            deliberate_overload=expect_fail,separately_handled_fullscale=separate_fullscale,
            exit_code=r['exit_code'],failure=rep['failure'],
            monitor_overloads_nominal_half=rep['monitor_overloads_nominal_half'],
            excursions28=rep['excursions28'],min_ones28=rep['min_ones28'],
            max_ones28=rep['max_ones28'],correct_length=correct_length,
            max_abs_state=rep['max_abs_state'],
            guard_utilization=[x/b for x,b in zip(rep['max_abs_state'],bounds)]))
    per_rate={str(rate):dict(result='PASS' if all(
            v['status']!='FAIL' for v in verdict if f'/{rate}/' in v['case_path'])
            else 'FAIL',case_count=sum(f'/{rate}/' in v['case_path'] for v in verdict),
            failures=[v['case_path'] for v in verdict if
                f'/{rate}/' in v['case_path'] and v['status']=='FAIL'],
            separately_handled_fullscale=sum(f'/{rate}/' in v['case_path'] and
                v['status']=='OBSERVED_SPECIAL_FULLSCALE' for v in verdict)) for rate in RATES}
    out=dict(schema='P17/frozen-guard-holdout/2',qualified=False,
        result='PASS' if all(v['result']=='PASS' for v in per_rate.values()) else 'FAIL',
        derivation_sha256=sha(GUARDS),case_count=len(verdict),rate_results=per_rate,
        case_receipt_sha256={str(p.relative_to(ROOT)):sha(p) for p,r in rows},cases=verdict)
    atomic(args.results/'holdout-summary.json',out)
    print('HOLDOUT',out['result'],len(verdict),per_rate,flush=True)
    return 0 if out['result']=='PASS' else 1

def verify(args):
    rows=read_rows(args,'training')
    if rows is None or not GUARDS.exists():raise RuntimeError('incomplete source training')
    guard=json.loads(GUARDS.read_text())
    original_unit=args.results.parent/'guard-tools/dsd_test_p10_training'
    if not original_unit.is_file() or sha(original_unit)!=guard['executable_sha256']:
        raise RuntimeError('archived exact training executable absent or modified')
    if guard['training_case_count']!=34 or any(guard['case_receipt_sha256'].get(str(p.relative_to(ROOT)))!=sha(p) for p,r in rows):
        raise RuntimeError('training receipt hash mismatch')
    if HEADER.read_text()!=expected_header(guard['profiles']):
        raise RuntimeError('guard header differs from frozen derivation')
    low=json.loads((ROOT/'tests/dsd/reference/p10_guards.json').read_text())
    block=HEADER.read_text().split('lsx_pcmdsd_guards[5][8] = {\n')[1]
    for i,rate in enumerate((2822400,5644800,11289600)):
        values=[float.fromhex(x.strip()) for x in block.splitlines()[i].strip().strip(',{}').split(',')]
        if values!=low['profiles'][str(rate)]['bounds']:
            raise RuntimeError('inherited P10 guard row modified')
    for rate in RATES:
        accepted=[r for p,r in rows if r['config']['native_hz']==rate and
                  r['exit_code']==0 and r['render']['status']==3]
        values=[math.ldexp(1.,math.ceil(math.log2(16*max(1.,max(
            float(r['render']['max_abs_state'][i]) for r in accepted))))) for i in range(8)]
        if not accepted or values!=guard['profiles'][str(rate)]['bounds']:
            raise RuntimeError('guard derivation mismatch')
    print('P17 guard verification PASS: 34 cases, unchanged P10 rows, immutable high-rate bounds')
    return 0

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('operation',choices=('train','holdout','verify'))
    a.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17_qualification_2026-10-21/guards')
    a.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p10')
    a.add_argument('--timeout',type=int,default=1800)
    args=a.parse_args();args.results=args.results.resolve();args.unit=args.unit.resolve()
    if not args.unit.is_file():a.error('unit binary absent; build test/dsd_test_p10 first')
    try:return {'train':train,'holdout':holdout,'verify':verify}[args.operation](args)
    except (RuntimeError,KeyError,ValueError,OSError) as exc:
        print('P17 guard '+type(exc).__name__+': '+str(exc),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
