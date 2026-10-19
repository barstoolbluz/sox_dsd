#!/usr/bin/env python3
"""Independent, fail-closed re-adjudication of the historical P15 physical receipt.

Never reconstructs deleted payloads or authenticates the reported physical CPU.
It proves receipt-internal arithmetic/shape consistency and current SOURCE binding,
not retained binary or execution custody. Does not change any acceptance gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
HISTORIC = ROOT / 'tests/dsd/results/P15_ps_matched_physical_2026-10-16'
SCHEMA = 'P15/R5.2/physical-benchmark-independent-review/1'
PROFILES = (('mastering', 40000, 80000), ('decode.mastering.v2.dsd256', 66000, 80000))
RATES = (176400, 352800)
ARMS = ('decoder', 'legacy_direct', 'legacy_ps_matched')
SOURCES = ('src/rate.c', 'src/fft4g.c', 'src/sinc.c', 'src/effects_i_dsp.c',
           'src/dsd_decode.c', 'src/dsd_coeffs.h', 'src/dsd_coeffs_v2.h',
           'tests/dsd/verify_dsd256_control_match.py')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')

class Refusal(ValueError):
    pass

def require(ok, why):
    if not ok:
        raise Refusal(why)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text())

def independent_bootstrap(legacy, decoder):
    """Re-derive the existing unpaired bootstrap, without importing its code."""
    def valid(seq):
        return (type(seq) is list and len(seq)==15 and
                all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in seq))
    require(valid(legacy) and valid(decoder), 'timing repetition count/value malformed')
    rng=random.Random(20261016)
    ratios=[]
    for _ in range(10000):
        a=sorted(legacy[rng.randrange(15)] for __ in range(15))[7]
        b=sorted(decoder[rng.randrange(15)] for __ in range(15))[7]
        ratios.append(a/b)
    ratios.sort()
    return {'point':statistics.median(legacy)/statistics.median(decoder),
            'ci95':[ratios[250],ratios[9750]],
            'exceeds_two_at_lower_bound':ratios[250]>2}

def check_manifest(path, file_hashes, *, allow_missing):
    missing=[];verified=0
    for name,expected in sorted(file_hashes.items()):
        require(Path(name).name==name and name not in ('.','..'), 'unsafe inventory path')
        require(type(expected) is str and SHA_RE.fullmatch(expected), 'invalid audio digest')
        f=path/name
        if not f.is_file():
            missing.append(name)
        else:
            require(not f.is_symlink() and sha(f)==expected, 'audio payload corrupted: '+name)
            verified+=1
    require(allow_missing or not missing, 'required audio payloads are missing')
    return {'present_verified':verified,'total_recorded':len(file_hashes),
            'missing':missing,'full_payload_integrity':not missing}

def check_sha_list(path, expected):
    """A later checksum list is a claimed digest inventory, not recovered bytes."""
    require(path.is_file() and not path.is_symlink(), 'missing claimed audio hash inventory')
    lines=[ln.split('  ',1) for ln in path.read_text().splitlines()]
    require(all(len(p)==2 for p in lines),'invalid checksum inventory syntax')
    got={name:hashstr for hashstr,name in lines}
    require(len(got)==len(lines) and got==expected, 'checksum inventory conflicts with receipt')

def command_cell(profile, rate, p, s, sox):
    name=profile.replace('.','_')
    prefix=[sox,'-D','<fixture>','-r',str(rate),'-e','floating-point','-b','64']
    return {
      'decoder':[sox,'-D','--dsd-layout-loss','warn','<fixture>',
           '-r',str(rate),'-e','floating-point','-b','64',
           f'<output>/decoder-{name}-{rate}.wav','dsdpcm','-p',profile,
           '-l','preserve',str(rate)],
      'legacy_direct':prefix+[f'<output>/direct-{name}-{rate}.wav','rate','-v'],
      'legacy_ps_matched':prefix+[f'<output>/psmatched-{name}-{rate}.wav',
          'rate','-v','352800','sinc','-a','180','-t',str(s-p),
          '-'+str((p+s)//2),'rate','-v'],
    }

def audit(root=ROOT, historic=HISTORIC, current_sox=None, current_candidate=None):
    root=Path(root).resolve();historic=Path(historic).resolve()
    bench_dir=historic/'bench';spec_dir=historic/'comparator'
    b_path=bench_dir/'RECEIPT.json';s_path=spec_dir/'RECEIPT.json'
    b=read_json(b_path);s=read_json(s_path)
    require(b.get('schema')=='P15/physical-ps-matched-six-channel-benchmark/1', 'benchmark schema drift')
    require(s.get('schema')=='P15/new-dsd256-ps-matched-control/1', 'comparator schema drift')
    require(b.get('qualified_release') is False and s.get('qualified_release') is False,
            'historical release-promotion claim')
    require(b.get('status')=='MEASURED_PHYSICAL_UNADJUDICATED', 'historical benchmark status drift')
    require(s.get('status')=='SPECTRALLY_MATCHED_DIAGNOSTIC' and
            s.get('spectrally_matched_on_fixture') is True and
            s.get('selftest_wrong_cutoff') is False,
            'spectral status drift/not positively matched')
    require(b.get('spectral_receipt_sha256')==sha(s_path), 'spectral receipt identity mismatch')
    require(b.get('executable_sha256')==s.get('executable_sha256'), 'different measured executables')
    for k in ('sox','candidate'):
        require(type(b['executable_sha256'].get(k)) is str and
                SHA_RE.fullmatch(b['executable_sha256'][k]), 'invalid binary digest')
    recorded=b.get('source_sha256')
    require(type(recorded) is dict and set(recorded)==set(SOURCES) and
            recorded==s.get('source_sha256'), 'source inventory mismatch')
    for name in SOURCES:
        require(sha(root/name)==recorded[name], 'source drift: '+name)
    require(b.get('target')==2.0 and b.get('repetitions')==15 and
            b.get('warmups',0)>=1 and b.get('bootstrap')=={'iterations':10000,'seed':20261016},
            'benchmark protocol mismatch')
    require(b.get('fixture_seconds',0)>=1 and b.get('fixture_seconds',0)<=30 and
            s.get('fixture_seconds',0)>=1.5, 'fixture duration outside contract')
    host=b.get('host',{})
    require(host.get('system')=='Linux' and host.get('machine') in ('x86_64','aarch64') and
            host.get('hypervisor') is False and b.get('physical_host_admissible') is True and
            type(b.get('pinned_cpu')) is int and b['pinned_cpu'] in host.get('allowed_cpus',[]) and
            type(host.get('cpu')) is str and bool(host['cpu']) and
            type(host.get('microcode')) is str and bool(host['microcode']),
            'reported host fails original physical screening')
    require(host.get('governor')=='performance','physical receipt did not record performance governor')
    # Hash-only retained inventory cannot authenticate the original audio.
    native_hash=b.get('six_channel_native_sha256'); pcm_hash=b.get('six_channel_pcm_sha256')
    require(type(native_hash) is str and SHA_RE.fullmatch(native_hash) and
            type(pcm_hash) is str and SHA_RE.fullmatch(pcm_hash), 'invalid six-channel fixture hash')
    bp=check_manifest(bench_dir,{'input-6ch.dsf':native_hash,'input-6ch.wav':pcm_hash},allow_missing=True)
    sp=check_manifest(spec_dir,s.get('file_sha256',{}),allow_missing=True)
    require('noise-dsd256.dsf' in s['file_sha256'] and
            s['file_sha256']['noise-dsd256.dsf']==s.get('native_sha256'),
            'spectral fixture identity mismatch')
    if (bench_dir/'AUDIO_SHA256.txt').exists():
        check_sha_list(bench_dir/'AUDIO_SHA256.txt',{'input-6ch.dsf':native_hash,'input-6ch.wav':pcm_hash})
    else:
        require(bp['full_payload_integrity'],'benchmark lacks both payload and checksum inventory')
    if (spec_dir/'AUDIO_SHA256.txt').exists():
        check_sha_list(spec_dir/'AUDIO_SHA256.txt',{k:v for k,v in s['file_sha256'].items() if k.endswith(('.wav','.dsf'))})
    else:
        require(sp['full_payload_integrity'],'comparator lacks both payload and checksum inventory')
    expected={(p,r) for p,_,_ in PROFILES for r in RATES}
    require(set(b.get('rows',{}))=={f'{p}@{r}' for p,r in expected},'benchmark cells not exact')
    require(type(s.get('rows')) is list and len(s['rows'])==4 and
            {(x.get('profile'),x.get('rate')) for x in s['rows']}==expected,
            'spectral comparator cell inventory not exact')
    spect={(x['profile'],x['rate']):x for x in s['rows']}
    rows={}
    sox_command=None
    for profile,p,stop in PROFILES:
        for rate in RATES:
            key=f'{profile}@{rate}';cell=b['rows'][key]
            cm=cell.get('commands',{})
            require(type(cm) is dict and set(cm)==set(ARMS), 'command arms missing: '+key)
            cmd=cm['decoder']
            require(type(cmd) is list and len(cmd)>0 and type(cmd[0]) is str, 'command binary missing')
            this_sox=cmd[0]
            require(Path(this_sox).is_absolute(),'benchmark command lacks absolute executable')
            if sox_command is None: sox_command=this_sox
            require(this_sox==sox_command and
                    cm==command_cell(profile,rate,p,stop,this_sox), 'benchmark command/control drift: '+key)
            require((cell.get('pass_hz'),cell.get('stop_hz'),cell.get('rate')) ==
                    (p,stop,rate),'benchmark P/S or output rate mismatch')
            samples=cell.get('seconds')
            require(type(samples) is dict and set(samples)==set(ARMS),'timing arms missing')
            comparator=spect[(profile,rate)]
            label=('v2' if 'v2' in profile else 'v1')+'-'+str(rate)
            verifier=comparator.get('verification',{})
            require((comparator.get('pass_hz'),comparator.get('stop_hz'),
                     comparator.get('initial_intermediate_hz'),comparator.get('label'))==
                    (p,stop,352800,label),'spectral matched band or rate changed')
            require(comparator.get('proposed_control')==
                    f'sinc -a 180 -t {stop-p} -{(p+stop)//2}', 'spectral comparator cutoff changed')
            require(verifier.get('matched') is True and
                    verifier.get('comparison_band_hz',[None,None])[1]==p and
                    verifier.get('transition_excluded_fraction')==0 and
                    0<=verifier.get('max_abs_difference_db',float('inf'))<=1.0,
                    'full guaranteed passband not matched: '+key)
            require(s['file_sha256'].get('decoder-'+label+'.wav')==
                    comparator.get('decoder_wav_sha256') and
                    s['file_sha256'].get('control-'+label+'.wav')==
                    comparator.get('control_wav_sha256'),'spectral audio digest inconsistent')
            if sp['full_payload_integrity']:
                # Replay full-band audio checks on fresh prospective receipts.
                # Historical 2026-10-16 payloads were deleted, so never claim
                # their acoustic verification has been reproduced.
                from verify_dsd256_control_match import compare
                recomputed=compare(spec_dir/('decoder-'+label+'.wav'),
                                   spec_dir/('control-'+label+'.wav'),p)
                require(recomputed==verifier, 'retained spectral waveform does not reproduce result: '+key)
            expected_comparisons=cell.get('comparisons',{})
            require(type(expected_comparisons) is dict and
                    set(expected_comparisons)==set(ARMS[1:]),'missing CIs')
            details={}
            for arm in ARMS[1:]:
                observed=independent_bootstrap(samples[arm],samples['decoder'])
                saved=expected_comparisons[arm]
                require(type(saved) is dict and set(saved)==set(observed) and
                        saved['exceeds_two_at_lower_bound'] is observed['exceeds_two_at_lower_bound'] and
                        all(math.isclose(a,b,rel_tol=0,abs_tol=1e-12)
                            for a,b in zip([saved['point']]+saved['ci95'],
                                           [observed['point']]+observed['ci95'])),
                        'bootstrap receipt cannot be independently recomputed: '+key+' '+arm)
                details[arm]=observed
            rows[key]={'pass_hz':p,'stop_hz':stop,'rate':rate,
                       'spectral_max_abs_difference_db':verifier['max_abs_difference_db'],
                       'median_decoder_s':statistics.median(samples['decoder']),
                       'comparisons':details}
    release_binaries={}
    for k,v in (('sox',current_sox),('candidate',current_candidate)):
        if v is not None:
            actual=sha(v);release_binaries[k]={'path':str(Path(v).resolve()),'sha256':actual,
                'matches_historical':actual==b['executable_sha256'][k]}
    return {
        'schema':SCHEMA,'status':'HISTORICAL_SOURCE_MATCHED_RECEIPT_ARITHMETIC_VERIFIED',
        'overall_gate':'OPEN','physical_2x_gate':'OPEN',
        'source_sha256':recorded,
        'historical_evidence':{
            'benchmark_receipt_sha256':sha(b_path),'spectral_receipt_sha256':sha(s_path),
            'bench_audio':bp,'spectral_audio':sp,
            'captured_eight_source_files_match_current':True,
            'complete_release_source_dependency_closure':False,
            'recorded_host_is_physical':True,
            'contains_changed_after_2026_10_16_header_unpinned_by_historical_receipt':
                ('src/rate_poly_fir0.h' not in SOURCES),
            'historical_benchmark_and_comparator_script_hashes_unrecorded':True,
            'externally_verified_physical_host':False,
            'release_binaries_available_for_original_measurement':False,
            'historical_binaries_sha256':b['executable_sha256'],
            'current_binaries':release_binaries,
            'method':'15 raw timings/arm/cell, 10000 seeded unpaired bootstrap iterations',
            'cells':4,'comparisons_recomputed':8,'lower_95_percent_over_2x':sum(
                sum(x['exceeds_two_at_lower_bound'] for x in row['comparisons'].values())
                for row in rows.values())},
        'rows':rows,
        'scope':('Historical recorded physical benchmark, exact bound production SOURCE; '
               'no independent prior host attestation, original executables or raw audio custody.'),
        'release_refusal':('Receipt arithmetic alone cannot authenticate the original physical host, full build dependency closure, or runtime binary identity. Historical audio payloads are absent unless the payload counts above say otherwise; final release requires a prospective physical measurement on the finalized production binaries or independent signoff of a matching verified execution identity.')
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--historic',type=Path,default=HISTORIC)
    ap.add_argument('--current-sox',type=Path)
    ap.add_argument('--current-candidate',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--require-release',action='store_true',help='return status 2: cannot promote historical evidence')
    a=ap.parse_args()
    try:
        report=audit(a.root,a.historic,a.current_sox,a.current_candidate)
        result=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n'
        a.output.parent.mkdir(parents=True,exist_ok=True)
        if a.output.exists():
            require(a.output.read_text()==result, 'existing report differs; refuse to overwrite')
        else:
            temp=a.output.with_name('.'+a.output.name+'.'+str(os.getpid())+'.tmp')
            try:
                temp.write_text(result)
                os.link(temp,a.output)  # atomic no-replace, never clobber prior evidence
            finally:
                temp.unlink(missing_ok=True)
        print(json.dumps({k:report['historical_evidence'][k] for k in
              ('cells','comparisons_recomputed','lower_95_percent_over_2x')},sort_keys=True))
        if a.require_release:
            print('OPEN: historical receipt is not a final physical release qualification',file=sys.stderr)
            return 2
        return 0
    except (OSError,KeyError,TypeError,ValueError,IndexError) as e:
        print('REFUSED: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
