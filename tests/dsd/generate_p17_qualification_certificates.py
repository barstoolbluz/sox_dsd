#!/usr/bin/env python3
"""Six SHA-256-bound *unqualified* P17 candidate evidence records.

Never change qualification flags, public capabilities or P10 certificate.
The generated hashes remain external to production C profile pointers until
later release authority: this also avoids a binary/receipt SHA hash cycle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tests/dsd/reference/p17_qualification_certificates.json'
HEADER=ROOT/'src/dsd_p17_certificates.h'
RESULTS=ROOT/'tests/dsd/results/P17_qualification_2026-10-21'
NUMERIC=ROOT/'tests/dsd/results/P17/numeric-p17'
PROFILE=ROOT/'tests/dsd/reference/p17_profiles.json'

def sha(blob):return hashlib.sha256(blob).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def read(path):
    return json.loads(Path(path).read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
def digest(value):return sha((json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())

def generate():
    guards=ROOT/'tests/dsd/reference/p17_guards.json'
    if not guards.is_file():raise RuntimeError('no frozen clock-specific P17 guards')
    frozen=read(guards)
    if (set(frozen['profiles'])!={'22579200','45158400'} or
        frozen.get('training_case_count')!=34 or
        frozen.get('holdout_used_to_set_bounds') is not False):
        raise RuntimeError('bad/incomplete P10-method guard freeze')
    spectral=read(NUMERIC/'filter-development-evidence.json')
    finite=read(NUMERIC/'finite-reference-evidence.json')
    sdm=read(NUMERIC/'sdm-candidate-diagnostics.json')
    definition=read(PROFILE)
    if any(x['status']!='PASS' for x in (spectral,finite,sdm)):
        raise RuntimeError('preexisting sampled P17 numerical evidence incomplete')
    fixtures=RESULTS/'fixtures/probe-fixtures.json'
    fixture=read(fixtures)['result'] if fixtures.exists() else 'UNRUN'
    longstream=RESULTS/'fixtures/fullstream-fixtures.json'
    longstream_result=read(longstream)['result'] if longstream.exists() else 'UNRUN'
    media=RESULTS/'media/commercial-decode-evidence.json'
    media_receipt=read(media) if media.exists() else None
    holdout=RESULTS/'guards/holdout-summary.json'
    holdout_receipt=read(holdout) if holdout.exists() else None
    filenames=[
        'src/dsd.c','src/dsd_decode.c','src/dsd_decode.h','src/dsd_packed.c',
        'src/dsd_packed.h','src/sox_dsd.h','src/pcmdsd.c','src/pcmdsd.h',
        'src/pcmdsd_guards.h','src/pcmdsd_coeffs.h','src/sdm.c','src/sdm.h',
        'src/sdm_p17_candidates.h','src/dsd_kernels_scalar.c','src/dsd_kernels_avx2.c',
        'tests/dsd/p17_dsf_probe.c','tests/dsd/test_p17_dsf_probe.py',
        'tests/dsd/test_p17_long_dsf_stream.py',
        'tests/dsd/p17_media_qualification.py','tests/dsd/p17_qualify_guards.py',
        'tests/dsd/p17_soak_run.py','tests/dsd/p17_soak_assess.py',
        'tests/dsd/generate_p17_qualification_certificates.py',
        'tests/dsd/test_p17_qualification_registry.py']
    lineage={name:file_sha(ROOT/name) for name in filenames}
    sources=(NUMERIC/'filter-development-evidence.json',
        NUMERIC/'finite-reference-evidence.json',
        NUMERIC/'sdm-candidate-diagnostics.json',PROFILE,guards,
        ROOT/'docs/dsd/amendments/CONTINUUM_EXTREMA_WAIVER_2026-10-21.md')
    evidence={str(p.relative_to(ROOT)):file_sha(p) for p in sources}
    for p in (fixtures,longstream,media,holdout):
        if p.is_file():evidence[str(p.relative_to(ROOT))]=file_sha(p)
    records={}
    for rate in (22579200,45158400):
        suffix=str(rate//44100)
        for kind in ('mastering','wideband'):
            id=f'decode.{kind}.v1.dsd{suffix}'
            spectral_row=next(x for x in spectral['cases'] if x['profile']==id)
            finite_rows=[x for x in finite['cases'] if x['profile']==id]
            if spectral_row['status']!='PASS' or not finite_rows or any(x['status']!='PASS' for x in finite_rows):
                raise RuntimeError('failed source P17 numerical oracle '+id)
            complete=(media_receipt is not None and
                media_receipt['full_file_functional_gate']=='PASS' and rate==22579200)
            records[id]=dict(schema='P17/reconstruction-certificate/1',version=1,id=id,
                native_hz=rate,qualified=False,production_capability_enabled=False,
                decision='CANDIDATE_PENDING_INDEPENDENT_MEDIA_AND_AUDIO_ADJUDICATION',
                decoder_definition=definition['reconstruction'][id],
                source_sha256={k:v for k,v in lineage.items() if
                    k.startswith('src/dsd') or k.startswith('tests/dsd/p17_') or
                    k.endswith('generate_p17_qualification_certificates.py')},
                evidence_sha256={k:v for k,v in evidence.items() if any(k.endswith(x) for x in
                    ('filter-development-evidence.json','finite-reference-evidence.json',
                     'p17_profiles.json','probe-fixtures.json','fullstream-fixtures.json',
                     'commercial-decode-evidence.json',
                     'CONTINUUM_EXTREMA_WAIVER_2026-10-21.md'))},
                gates=dict(sampled_spectral='PASS_WAIVER_GOVERNED',
                    independent_finite_oracle='PASS',
                    private_dsf_synthetic_fixture=fixture,
                    private_dsf_longstream_fixture=longstream_result,
                    licensed_full_file_private_reader='PASS' if complete else 'UNRUN',
                    independent_reference_decoder_audio_comparison='UNRUN',
                    independent_rate_1024_media='UNRUN' if rate==45158400 else 'NOT_APPLICABLE',
                    physical_device_io='NOT_CLAIMED'),
                no_continuum_interval_obligation=True)
        id=f'encode.mastering.v1.dsd{suffix}'
        reported=next(x for x in sdm['cases'] if x['native_hz']==rate)
        training_files=sorted((RESULTS/'guards/training'/str(rate)).glob('*.json'))
        if len(training_files)!=17:
            raise RuntimeError('not all training receipts available for '+str(rate))
        training_rows=[read(p) for p in training_files]
        if any(frozen['case_receipt_sha256'].get(str(p.relative_to(ROOT)))!=file_sha(p)
               for p in training_files):
            raise RuntimeError('source training receipt hash mismatch for '+str(rate))
        rejected=[dict(name=r['config']['name'],failure=r['render']['failure'],
            nonfinite=r['render']['nonfinite_states']) for r in training_rows
            if r['exit_code']!=0 or r['render']['status']!=3]
        if len(rejected)!=frozen['profiles'][str(rate)]['rejected_case_count']:
            raise RuntimeError('training failure count mismatch '+str(rate))
        bad_finite=any(r['nonfinite'] for r in rejected)
        training_gate=('FAIL_NONFINITE_STATE' if bad_finite else
            'FAIL_REJECTED_CASES' if rejected else 'PASS')
        rate_holdout=(holdout_receipt.get('rate_results',{}).get(str(rate),{}).get('result','UNRUN')
            if holdout_receipt else 'UNRUN')
        records[id]=dict(schema='P17/encoder-certificate/1',version=1,id=id,
            native_hz=rate,qualified=False,production_capability_enabled=False,
            decision=('BLOCKED_TRAINING_NONFINITE_AND_HOLDOUT' if bad_finite else
                'CANDIDATE_GUARDS_FROZEN_SUSTAINED_SOAK_UNRUN'),
            training_case_count=len(training_rows),training_rejected=rejected,
            encoder_definition=definition['sdm_candidates'][str(rate)],
            guard_bounds=frozen['profiles'][str(rate)]['bounds'],
            guard_derivation=frozen['derivation'],
            source_sha256={k:v for k,v in lineage.items() if
                k.startswith('src/pcmdsd') or k.startswith('src/sdm') or
                any(k.endswith(x) for x in ('p17_qualify_guards.py',
                    'p17_soak_run.py','p17_soak_assess.py',
                    'generate_p17_qualification_certificates.py'))},
            evidence_sha256={k:v for k,v in evidence.items() if any(k.endswith(x) for x in
                ('p17_guards.json','p17_profiles.json','sdm-candidate-diagnostics.json',
                 'holdout-summary.json','CONTINUUM_EXTREMA_WAIVER_2026-10-21.md'))},
            gates=dict(clock_specific_guard_derivation='PASS_ADMITTED_CASES_ONLY',
                complete_training_input_acceptance=training_gate,
                guard_holdout=rate_holdout,
                P17_short_sdm_diagnostics='PASS_DIAGNOSTIC_ONLY',
                complete_input_envelope_matrix='UNRUN',
                sustained_clock_specific_multi_isa_soak='UNRUN',
                independent_highrate_reconstruction_quality='UNRUN',
                file_writer_interoperability='NOT_CLAIMED'),
            no_continuum_interval_obligation=True)
    order=[f'decode.{p}.v1.dsd{rate}' for rate in (512,1024)
        for p in ('mastering','wideband')]+[
        f'encode.mastering.v1.dsd{rate}' for rate in (512,1024)]
    if set(order)!=set(records):raise RuntimeError('missing certificate profiles')
    values={id:digest(records[id]) for id in order}
    data=dict(schema='P17/rate-specific-certificate-registry/1',
        input_claimed_revision='sox_dsd/main 2bda0491; supplied working-set metadata only',
        release_qualified=False,release_capabilities_enabled=False,
        independent_media_shared_in_bundle=False,device_claims=[],
        historical_p10_certificate_sha256='df25a2a11855e8a380cd756cf38769701103338faf36b46271aa3df22bc5157e',
        certificate_sha256=values,profiles=records,
        note='SHA-256 identifies an UNQUALIFIED source-bound evidence record; no promotion or device claim')
    registry=json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n'
    lines=['/* P17 candidate evidence SHA-256 records. NOT production certificates. */',
        '#ifndef LSX_DSD_P17_CERTIFICATES_H','#define LSX_DSD_P17_CERTIFICATES_H']
    for id in order:
        macro='LSX_DSD_P17_'+id.replace('.','_').upper()+'_CERTIFICATE_SHA256'
        lines.append(f'#define {macro} "{values[id]}"')
    lines+=['#endif','']
    return registry,'\n'.join(lines)

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--check',action='store_true')
    args=a.parse_args()
    try:registry,header=generate()
    except (RuntimeError,KeyError,ValueError,FileNotFoundError) as ex:
        print('P17 certificate '+str(ex),file=sys.stderr);return 2
    if args.check:
        if not OUT.is_file() or OUT.read_text()!=registry or not HEADER.is_file() or HEADER.read_text()!=header:
            print('P17 certificate mismatch',file=sys.stderr);return 1
    else:
        OUT.write_text(registry);HEADER.write_text(header)
    print('P17 certificate binding', 'PASS_CHECK' if args.check else 'GENERATED',
        'six unqualified records')
    return 0
if __name__=='__main__':raise SystemExit(main())
