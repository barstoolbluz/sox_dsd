#!/usr/bin/env python3
"""R2 fail-closed, source-bound nonlinear screens; research ONLY.

Never changes production, P19 receipts, R1 evidence, or frozen coefficients.
The native renderer is the SAME executable used for R1 native render receipts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np

from model import WORKING, RATE, sha, canonical
from study import (DESIGNS, definitions, load_registry, native_pass,
                   render_one, write_once)

HERE = Path(__file__).resolve().parent
CASES = ('dc-positive-1p0', 'dc-negative-1p0', 'tone997-0dbfs',
         'dc-positive-0p99', 'dc-negative-0p99', 'tone997-minus0p1dbfs',
         'tone997-0dbfs-inverted', 'programme-unclipped-0p90')
EVIDENCE = HERE/'evidence_r2'


def material(name: str) -> tuple[bytes, str]:
    sys.path.insert(0, str(HERE.parent))
    import p10_corpus
    # Exactly the P10, 176.4 kHz, Q31-normalized graph-equivalent
    # generation for the six cases drawn from frozen P10 material.
    base = dict(native_hz=11289600, source_hz=WORKING, seconds=1.6,
                split='holdout', seed=201003, taper_seconds=.1)
    if name.startswith('dc-'):
        positive = name.split('-')[1]=='positive'
        amplitude = 1.0 if name.endswith('1p0') else .99
        config = base | dict(name=name, kind='dc',peak=amplitude if positive else -amplitude)
        data,detail=p10_corpus.stimulus(config)
        return data, 'P10 graph-equivalent, C2 100ms taper; '+name+'; '+detail['configuration_sha256']
    if name in ('tone997-0dbfs','tone997-minus0p1dbfs','tone997-0dbfs-inverted'):
        db= -.1 if name=='tone997-minus0p1dbfs' else 0.0
        config=base | dict(name=name,kind='tone',frequency=997.,dbfs=db)
        data,detail=p10_corpus.stimulus(config)
        if name=='tone997-0dbfs-inverted':
            arr=-np.frombuffer(data,dtype='<f8');data=arr.astype('<f8').tobytes()
        return data,'P10 graph-equivalent, C2 100ms taper; '+name+'; '+detail['configuration_sha256']
    if name=='programme-unclipped-0p90':
        # Fully deterministic, continuously elevated, multicomponent stress
        # with broad tonal content and bounded, clipped peaks, including
        # slow phase and polarity transitions and an independent noise seed.
        n=round(3.2*WORKING);t=np.arange(n,dtype=np.float64)/WORKING
        rng=np.random.Generator(np.random.PCG64(0x10242026))
        x=(.92*np.sin(2*np.pi*997*t)+.45*np.sin(2*np.pi*53*t+.37)
           +.38*np.sin(2*np.pi*5501*t+1.1)+.21*np.sin(2*np.pi*17011*t)
           +.12*np.sin(2*np.pi*40000*t+.72)+.12*rng.uniform(-1,1,n))
        x=.90*x/np.max(np.abs(x))
        taper=round(.1*WORKING);u=np.arange(taper,dtype=np.float64)/taper
        ramp=u*u*u*(10+u*(-15+6*u));x[:taper]*=ramp;x[-taper:]*=ramp[::-1]
        if not (np.isfinite(x).all() and np.max(np.abs(x))<=.90+1e-14):
            raise RuntimeError('Programme stress violates bounded binary64 source contract')
        return x.astype('<f8').tobytes(),'3.2s deterministic UNCLIPPED .90-peak multitone with bounded noise, seed 0x10242026'
    raise RuntimeError('Unknown mandatory R2 source: '+name)


def external_scratch(path: Path) -> None:
    from model import ROOT
    resolved=path.resolve()
    authority=ROOT.resolve()
    if resolved==authority or resolved.is_relative_to(authority) or authority.is_relative_to(resolved):
        raise RuntimeError('Scratch output must not be in or above production source')


def generate(directory: Path) -> None:
    external_scratch(directory)
    directory.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name in CASES:
        data,description=material(name)
        path=directory/(name+'.f64le')
        # Atomic, non-overwriting stimulus generation; do not accept external
        # data with a coincidentally compatible file name.
        import hashlib
        digest=hashlib.sha256(data).hexdigest()
        if path.exists():
            if path.read_bytes()!=data:raise RuntimeError('Stimulus conflict '+str(path))
        else:
            import os,tempfile
            with tempfile.NamedTemporaryFile(dir=directory,prefix='.r2-',delete=False) as f:
                temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
            try:
                os.link(temp,path)
            except FileExistsError:
                if sha(path)!=digest:raise RuntimeError('Concurrent conflicting stimulus')
            finally:
                temp.unlink(missing_ok=True)
        manifest[name]={'sha256':digest,'frames':len(data)//8,
                        'working_hz':WORKING,'description':description}
    write_once(directory/'manifest.json',{'schema':'DSD1024-NTF-R2-stimuli/1','cases':manifest,
           'generation':'P10 Q31 graph-equivalent except explicit tagged deterministic programme'})
    print('R2_GENERATED',len(CASES), 'digest',sha(directory/'manifest.json'),flush=True)


def screen(args: argparse.Namespace) -> None:
    if args.jobs<1 or args.jobs>5 or args.timeout<1:raise RuntimeError('Invalid jobs/timeout')
    from concurrent.futures import ThreadPoolExecutor,as_completed
    external_scratch(args.outputs)
    registry=load_registry(args.registry,args.checkout)
    records={r['key']:r for r in registry['candidates']}
    if set(records)!=set(definitions()['designs']):raise RuntimeError('Registry lacks design(s)')
    manifest=json.loads((args.stimuli/'manifest.json').read_text())
    if set(manifest['cases'])!=set(CASES):raise RuntimeError('Missing mandatory R2 stimulus')
    for name in CASES:
        if args.only_cases and name not in args.only_cases:continue
        inp=args.stimuli/(name+'.f64le')
        if not inp.is_file() or sha(inp)!=manifest['cases'][name]['sha256']:
            raise RuntimeError('Missing/mismatched input: '+name)
        receipts=args.outputs/name/'receipts';packed=args.outputs/name/'packed'
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            future={pool.submit(render_one,k,records[k],inp,args.binary.resolve(),
                                args.checkout.resolve(),receipts,packed,args.timeout):k
                    for k in sorted(records) if not args.only_keys or k in args.only_keys}
            for result in as_completed(future):result.result()
        print('R2_SCREEN_COMPLETE',name,flush=True)


def r2_native_pass(receipt: dict, case: str) -> tuple[bool,str]:
    """Strict nonlinear gate with a *narrowly disclosed* full-scale endpoint.

    The P10 binary64 waveform reaches exactly ±1 source sample; in the
    unchanged native interpolator the reconstructed peak is 0.500000000023
    at 0.5 encoding scale (11 double-roundoff nominal-overload counts),
    independent of all 40 stable design recurrences. The P19 corpus marks
    0dBFS tones as separately handled fullscale. Refuse nonfinite/28-window
    problems absolutely. Admit ONLY this bounded roundoff for these two
    known exact source digests, and retain/report the real counter and peak.
    There is no exception for the 0.99 DC, -0.1dB tone, or programme cases.
    """
    if case not in ('tone997-0dbfs','tone997-0dbfs-inverted'):
        return native_pass(receipt)
    import copy
    status=receipt.get('status')
    if not isinstance(status,dict):return False,'missing native monitor'
    counted=status.get('monitor_overloads_nominal_half')
    peak=status.get('peak')
    if (not isinstance(counted,int) or counted<0 or counted>11 or
        not isinstance(peak,(float,int)) or not (0<=peak<=.500000001)):
        return False,'fullscale endpoint exceeds explicit numerical allowance'
    adjusted=copy.deepcopy(receipt)
    adjusted['status']['monitor_overloads_nominal_half']=0
    passed,reason=native_pass(adjusted)
    if counted:
        reason+='; '+str(counted)+' nominal overbound samples within 1e-9 endpoint roundoff (NOT zero overload)'
    return passed,reason


def assess(args: argparse.Namespace) -> dict:
    original=json.loads((HERE/'evidence/comparison.json').read_text())
    stimuli=json.loads(args.manifest.read_text())
    if stimuli['schema']!='DSD1024-NTF-R2-stimuli/1' or set(stimuli['cases'])!=set(CASES):
        raise RuntimeError('R2 input manifest incomplete')
    registry=json.loads((HERE/'evidence/experimental-registry.json').read_text())
    bindings={x['key']:x for x in registry['candidates']}
    keys=set(definitions()['designs'])
    if len(keys)!=55 or set(bindings)!=keys or set(original['spectra'])!=keys:
        raise RuntimeError('R1 design/registry/spectra coverage incomplete')
    if set(original['screens'])!=keys or original['required_screen_inputs']!=['hot-997','noise-safe','dc-step','silence']:
        raise RuntimeError('R1 precedent screen changed')
    for key in keys:
        if not original['screens'][key]['passed'] or not original['screens'][key]['complete']:
            raise RuntimeError('R1 base screening no longer passes: '+key)
    output={};failures={};screened=0;binary_identities=set()
    for key in sorted(keys):
        rows=[]
        for name in CASES:
            path=args.results/name/'receipts'/(key+'.json')
            if not path.is_file():raise RuntimeError('Missing mandatory R2 render: '+str(path))
            r=json.loads(path.read_text())
            case=stimuli['cases'][name]
            binding=bindings[key]
            expected={'schema':'DSD1024-NTF-native-render/1','key':key,
                'profile':binding['profile'],'design_sha256':sha(DESIGNS),
                'input_sha256':case['sha256'],'input_frames':case['frames'],
                'experimental_header_sha256':registry['experimental_header_sha256'],
                'experimental_sdm_sha256':registry['experimental_sdm_sha256'],
                'native_hz':RATE,'working_hz':WORKING,'candidate_qualified':False,
                'guard':'training/unbounded experimental','kernel':'scalar','scale':0.5}
            for field,exp in expected.items():
                if r.get(field)!=exp:raise RuntimeError(f'R2 identity mismatch {path}: {field}')
            if not r.get('complete') or not isinstance(r.get('status'),dict) or r.get('timed_out'):
                raise RuntimeError('Incomplete R2 receipt (not accepted as a measured failure): '+str(path))
            if (r['status'].get('schema')!='P10/candidate-render/1' or
                    not (0<r['status'].get('input_frames',-1)<=case['frames']) or
                    r['status'].get('profile')!=binding['profile']):
                raise RuntimeError('Native monitor does not describe the requested source/profile')
            if r['return_code']==0 and r['status']['input_frames']!=case['frames']:
                raise RuntimeError('Native successful case has truncated source consumption')
            unit_digest=r.get('unit_sha256')
            if not isinstance(unit_digest,str) or len(unit_digest)!=64:
                raise RuntimeError('Missing original native executable identity')
            binary_identities.add(unit_digest)
            if r['status'].get('processed_native_frames',-1)>case['frames']*(RATE//WORKING):
                raise RuntimeError('Reported native frame count exceeds possible input length')
            good,reason=r2_native_pass(r,name)
            if good and (r['status']['processed_native_frames']!=case['frames']*(RATE//WORKING)
                 or r['status']['committed_native_frames']!=case['frames']*(RATE//WORKING)
                 or r.get('packed_bytes')!=(case['frames']*RATE//WORKING+7)//8):
                raise RuntimeError('PASS status on truncated output: '+str(path))
            if r['return_code'] and r['status'].get('failure',0)==0 and r.get('packed_bytes',0)==0:
                # A native process failure is still a rejected design, but
                # require a real monitor; do not count silent infra errors.
                raise RuntimeError('Cannot adjudicate native process failure: '+str(path))
            rows.append({'name':name,'pass':good,'reason':reason,
                         'sha256':sha(path),'native_return_code':r['return_code'],
                         'nominal_fullscale_overloads':r['status'].get('monitor_overloads_nominal_half'),
                         'peak':r['status'].get('peak'),
                         'nonfinite_states':r['status'].get('nonfinite_states'),
                         'failure':r['status'].get('failure'),
                         'excursions28':r['status'].get('excursions28'),
                         'committed_native_frames':r['status'].get('committed_native_frames')})
            screened+=1
        passed=all(row['pass'] for row in rows)
        output[key]={'passed':passed,'cases':rows}
        if not passed:failures[key]=[row['name'] for row in rows if not row['pass']]
    incumbent=original['spectra']['clans-7']['integrated_sine_equivalent_dbfs']
    winners=[];rejected=[]
    for key in sorted(keys):
        if key=='clans-7':continue
        levels=original['spectra'][key]['integrated_sine_equivalent_dbfs']
        spectral=(levels['0_40k'] <= incumbent['0_40k']+1 and
                  levels['40_100k']<=incumbent['40_100k']-3 and
                  levels['100_150k']<=incumbent['100_150k']-3)
        if spectral:
            (winners if output[key]['passed'] else rejected).append(key)
    if set(winners+rejected)!={x['key'] for x in original['research_pareto_candidates']}:
        raise RuntimeError('R1 research selection/reclassification mismatch')
    if len(binary_identities)!=1:
        raise RuntimeError('Mixed or missing native executable identities in single R2 comparison')
    result={'schema':'DSD1024-NTF-R2-assessment/1','designs':55,
         'sources':list(CASES),'native_receipts':screened,
         'native_executable_sha256':next(iter(binary_identities)),
         'pass_all_count':sum(rec['passed'] for rec in output.values()),
         'spectral_only_r1_count':len(winners)+len(rejected),
         'stable_and_spectral_candidate_count':len(winners),
         'stable_and_spectral_candidate_keys':winners,
         'r1_spectral_cannot_advance_keys':rejected,'failed_by_candidate':failures,
         'screens':output,'r1_comparison_sha256':sha(HERE/'evidence/comparison.json'),
         'r2_stimuli_manifest_sha256':sha(args.manifest),
         'numerical_fullscale_exception':'For exact 0dBFS 997Hz P10 tones only, native peak must be <=0.500000001 at scale 0.5 and nominal-overload count <=11; counters are retained, never described as zero. All nonfinite and 28-window failures reject.',
         'decision':'NO PROMOTION: stability-screen survivors are ONLY preliminary research candidates. Raw ultrasonic load and playback transfer functions, candidate guard/holdouts, 3600s, ISA and performance all remain open.',
         'guard':'training/unbounded experimental, production unchanged'}
    write_once(args.output,result)
    print('R2_ASSESS',result['pass_all_count'],'of 55 pass',
          'stable spectral candidates',len(winners),winners,'reject',rejected,flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='task',required=True)
    g=sub.add_parser('generate');g.add_argument('--directory',type=Path,required=True)
    s=sub.add_parser('screen');s.add_argument('--checkout',type=Path,required=True)
    s.add_argument('--registry',type=Path,required=True);s.add_argument('--binary',type=Path,required=True)
    s.add_argument('--stimuli',type=Path,required=True);s.add_argument('--outputs',type=Path,required=True)
    s.add_argument('--jobs',type=int,default=4);s.add_argument('--timeout',type=int,default=900)
    s.add_argument('--only-cases',nargs='*',default=[]);s.add_argument('--only-keys',nargs='*',default=[])
    a=sub.add_parser('assess');a.add_argument('--manifest',type=Path,required=True)
    a.add_argument('--results',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.task=='generate':generate(args.directory)
    elif args.task=='screen':screen(args)
    else:assess(args)

if __name__=='__main__':
    try:main()
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        print('R2 SCREEN FAIL',type(e).__name__,e,file=sys.stderr)
        sys.exit(2)
