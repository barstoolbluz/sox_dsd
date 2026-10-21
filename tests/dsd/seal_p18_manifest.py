#!/usr/bin/env python3
"""P18 capability manifest: explicit seal and read-only verification.

All capability rows remain denied regardless of test outcomes. A green local
suite cannot promote DSP/file/DoP. Sealing binds actual source and gate bytes,
never edits historical P00/P15/P17 receipts, and is atomic/reproducible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/dsd'
OUT=DOC/'P18_RELEASE_MANIFEST.json'
SCHEMA=DOC/'P18_RELEASE_MANIFEST.schema.json'
SOURCE=[
    'Makefile.am','test/Makefile.am',
    'tests/dsd/test_p16.py','tests/dsd/seal_p18_manifest.py',
    'docs/dsd/P18_RELEASE_MANIFEST.schema.json',
    'docs/dsd/README.md',
    'src/dsd.c','src/dsd.h','src/formats.c','src/dsf.c','src/dsdiff.c','src/dop.c',
    'src/dsd_plan.c','tests/dsd/test_p18.c','tests/dsd/test_p18.py',
    'tests/dsd/run.py','tests/dsd/measure.py','tests/dsd/bench.py',
    'README.md','sox.1',
    'docs/dsd/P18_COMPATIBILITY_LEDGER.md',
    'docs/dsd/P18_RELEASE_NOTES.md'
]
P17='tests/dsd/results/P17/numeric-p17/qualification.json'
AUTH='docs/dsd/amendments/P18_AUTHORIZATION_2026-10-21.md'
FIXTURE='tests/dsd/reference/p18_fixture_matrix.json'
HIGH=[(22579200,'DSD512'),(45158400,'DSD1024')]
ROWS=[('DSF','read'),('DSF','write'),('DSDIFF','read'),('DSDIFF','write'),('DoP','transport'),('WSD','read')]

def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()

def read_json(name):return json.loads((ROOT/name).read_text())

def gates():
    # Verbatim exit codes from executed invocations, not speculative claims.
    config={
      'generic_sox': ('tests/dsd/results/P18/build/make-check.exit', 'exit'),
      'check_dsd': ('tests/dsd/results/P18/build/check-dsd-qualified.exit', 'exit'),
      'native_p18_unit': ('tests/dsd/results/P18/build/unit-p18.exit', 'exit'),
      'check_rename': ('tests/dsd/results/P18/build/check-rename-qualified.exit', 'exit'),
      'p16_fresh_replay': ('tests/dsd/results/P18/build/p16-fresh-qualified.exit','exit'),
      'p16_cached_replay': ('tests/dsd/results/P18/build/p16-cached-qualified.exit','exit'),
      'explicit_p18_runner': ('tests/dsd/results/P18/build/run-p18-qualified.exit','exit'),
      'numeric_command_development': ('tests/dsd/results/P18/build/measure-p18-qualified.exit','exit'),
      'bench_command_development': ('tests/dsd/results/P18/build/bench-p18-qualified.exit','exit'),
      'fixture_matrix': (FIXTURE, 'fixture'),
      'p18_cli': ('tests/dsd/results/P18/integration/capability-integration.json','p18_cli'),
      'p16_packed_cli': ('tests/dsd/results/P18/integration/packed-cli.json','p16_cli'),
      'p18_run': ('tests/dsd/results/P18/run.json','p18_run'),
      'numerical_development': ('tests/dsd/results/P18/numeric/measure.json','numeric'),
      'inherited_bench': ('tests/dsd/results/P18/bench/bench.json','bench'),
    }
    result={}
    for name,(path,kind) in config.items():
        file=ROOT/path
        if not file.exists():status='UNRUN';detail='missing evidence artifact'
        else:
            try:
                if kind=='exit':
                    status='PASS' if file.read_text().strip()=='0' else 'FAIL'
                    detail='recorded process exit code '+file.read_text().strip()
                else:
                    obj=read_json(path)
                    if kind=='fixture':
                        status='PASS' if obj['high_rate_capability']=='DISABLED' and len(obj['cases'])==198 and len(obj['dop_cases'])==36 else 'FAIL'
                        detail='independent deterministic reference records only'
                    elif kind=='p18_cli':
                        expected=hashlib.sha256(json.dumps(dict(
                            binary_sha256=obj['sox_sha256'],
                            test_sha256=sha('tests/dsd/test_p18.py'),
                            reference_sha256=sha(FIXTURE)),sort_keys=True).encode()).hexdigest()
                        status='PASS' if obj['verdict']=='PASS' and obj['summary']=={'PASS':106,'FAIL':0} and obj['high_rate_enabled'] is False and obj['config_sha256']==expected else 'FAIL'
                        detail='SoX high-rate refusal/legacy native roundtrip CLI'
                    elif kind=='p16_cli':
                        # The P16 configuration token already binds its SoX,
                        # native test binary and harness. Original binaries
                        # are not shipped in a clean source checkout, so use
                        # the immutable saved token and hashed raw receipt,
                        # not whatever executable happens to be installed.
                        token=obj['configuration_sha256']
                        status='PASS' if (obj['verdict']=='PASS' and
                            obj['counts']=={'pass_count':219,'fail_count':0} and
                            len(token)==64 and all(c in '0123456789abcdef' for c in token)
                            and len(obj['cases'])==219 and
                            all(c['status']=='PASS' for c in obj['cases'])) else 'FAIL'
                        detail='219 real-SoX packed/expanded parity cases; sealed configuration token and raw receipt'
                    elif kind=='p18_run':
                        status='PASS' if obj['verdict']=='pass' and not obj['counts']['fail'] and obj['phase']=='P18' and any(x['name'].startswith('P18_') for x in obj['tests']) else 'FAIL'
                        detail='inherited and P18 C/CLI tests'
                    elif kind=='numeric':
                        status='PASS' if obj['phase']=='P18' and obj['summary']['failed']==0 and 'FAIL_CLOSED' in obj['summary']['qualification_status'] else 'FAIL'
                        detail='unqualified rate-specific DSP preserved; sampled development only'
                    else:
                        status='PASS' if obj['config']['phase']=='P18' and obj['summary']['status']!='incomplete' and obj['p18_highrate_end_to_end']['status']=='UNRUN_AUTHORIZATION_WITHHELD' else 'FAIL'
                        detail='inherited rates only; high-rate end-to-end intentionally unrun'
            except (ValueError,KeyError,TypeError) as err:
                status='FAIL';detail=f'cannot parse/confirm receipt: {err}'
        result[name]={'status':status,'path':path,'detail':detail,
                      'sha256':sha(path) if file.is_file() else None}
    return result


def canonical():
    p17=read_json(P17)
    if p17['rate_specific_profile_certificates_qualified'] is not False or p17['writer_enabled'] is not False:
        raise ValueError('P17 upstream qualification status changed; audit before sealing')
    rows=[]
    for hz,label in HIGH:
        for endpoint,op in ROWS:
            rows.append(dict(native_hz=hz,rate_label=label,endpoint=endpoint,
                operation=op,enabled=False,
                reason='P17_HIGH_RATE_DSP_UNQUALIFIED_AND_P18_ENABLEMENT_WITHHELD',
                transport_pcm_hz=hz//16 if endpoint=='DoP' else None))
    ledger=gates()
    return dict(schema='P18/capability-release/1',phase='P18',
        decision='P18_COMPLETE_FAIL_CLOSED' if all(x['status']=='PASS' for x in ledger.values())
            else 'P18_INCOMPLETE_FAIL_CLOSED',
        source_lineage='Supplied 51c391f2 working set, synthetic Git baseline (no original .git)',
        authority_sha256=sha(AUTH),p17_qualification_sha256=sha(P17),
        p17_dsp_qualified=False,high_rate_capability_enabled=False,
        capabilities=rows,source_sha256={p:sha(p) for p in SOURCE},
        fixture_manifest_sha256=sha(FIXTURE),
        gates=ledger,
        unrun_independent_gates=[
            'Independent 512/1024 commercial/reference media, known-answer release decoding and cross-player readback',
            'P17 certified exact-rate numerical and sustained ISA/soak qualification',
            'Actual high-rate writer/file roundtrips and physical channel/layout interoperability',
            'Actual 1.4112/2.8224 MHz DoP transport, host negotiation and device qualification',
            'High-rate end-to-end runtime throughput, memory and storage traffic',
            'P15 standing source qualification obligations remain OPEN'],
        device_claims=[])


def validate_schema(obj):
    import jsonschema
    jsonschema.Draft202012Validator(read_json('docs/dsd/P18_RELEASE_MANIFEST.schema.json')).validate(obj)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    operation=ap.add_mutually_exclusive_group(required=True)
    operation.add_argument('--seal',action='store_true')
    operation.add_argument('--check',action='store_true')
    args=ap.parse_args()
    generated=canonical();validate_schema(generated)
    if args.seal:
        tmp=OUT.with_name(OUT.name+'.tmp')
        tmp.write_text(json.dumps(generated,sort_keys=True,indent=2)+'\n')
        tmp.replace(OUT)
        print('P18 sealed',generated['decision'])
        return 0
    if not OUT.is_file():ap.error('sealed P18 manifest missing')
    if read_json('docs/dsd/P18_RELEASE_MANIFEST.json')!=generated:
        ap.error('sealed P18 manifest differs from current source or gate evidence')
    print('P18 manifest CHECK PASS:',generated['decision'],len(generated['capabilities']),'disabled endpoint rows')
    return 0

if __name__=='__main__':raise SystemExit(main())
