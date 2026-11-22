#!/usr/bin/env python3
"""Fail closed on scoped Phase 08 test failures without misclosing owner gates."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
SOURCES={
    'reference-lock':('immutable-reference.json','PASS_LOCKED_PREDECESSOR'),
    'unified-decoder':('unified-reference.json','PASS_FINITE_WITNESSES_ONLY'),
    'float-boundary':('float-boundary.json','PASS'),
    'p2-encoder-frontend':('independent-primitive-cascade.json','PASS'),
    'p3-final-src':('final-src-reference.json','PASS_FINITE_WITNESSES_ONLY'),
    'd6-libm':('gain-libm-reference.json','PASS_FINITE_WITNESSES_ONLY'),
    'd6-coremath':('coremath-gain-reference.json','PASS_FINITE_WITNESSES_OWNER_OPEN'),
    'd11-accounting':('d11-bound-accounting.json','PASS_CONDITIONAL_ACCOUNTING_OWNER_OPEN'),
    'audited-metrology':('metrology-parity.json','PASS_FINITE_PARITY'),
    'v3-analysis-v1':('v3-analysis-v1.json','PASS_MEASUREMENT_ONLY'),
}


def command(*argv):
    return subprocess.check_output(argv,text=True,stderr=subprocess.STDOUT).strip()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True,type=Path)
    ap.add_argument('--sox',required=True,type=Path)
    args=ap.parse_args()
    results=args.results.resolve();sox=args.sox.resolve()
    checks={};failed=[]
    for tag,(name,want) in SOURCES.items():
        path=results/tag/name
        try:
            data=json.loads(path.read_text())
            observed=data.get('status')
            if observed!=want:raise ValueError(f'wrong or failed status: {observed!r}')
            if tag=='reference-lock':
                assert data['accepted_v2_fixtures']==19 and data['mutation_rejection']=='PASS'
                assert data['unified_decoder_reference_approval']=='OPEN'
            if tag=='unified-decoder':
                assert data['case_count']==64 and data['d16_reference_approval']=='OPEN'
            if tag=='audited-metrology': assert data['case_count']==12
            if tag=='float-boundary':
                assert data['case_count']>=8 and data['injected_adapter_check_count']>=26
                assert data['physical_level_check_count']>=4
            if tag=='p2-encoder-frontend':
                assert data['native_src_witness_count']==8
                assert len(data['primitive_and_composed_cases'])==8
                assert len(data['negative_controls'])==4
            if tag=='p3-final-src':
                assert data['case_count']==32 and len(data['wrong_tail_mutants'])==2
                assert data['d11_universal_p3_bound']=='OPEN'
            if tag=='d6-libm':
                assert data['sample_count']>=41
                assert data['d6_pow_universal_error_premise']=='OPEN'
            if tag=='d6-coremath':
                assert data['finite_normal_cases_verified']>=1000
                assert data['factor_correctly_rounded_at_x_in_sample'] is True
                assert data['zero_and_20_db_exact'] is True
                assert data['identity_graph']['plain_gain_words_identical'] is True
                assert data['d11_fft4g_all_input_error']=='OPEN'
                assert data['release_authorized'] is False
            if tag=='d11-accounting':
                assert data['fft4g_worst_case_error_bound']=='OPEN'
                assert data['glibc_pow_exp_maximum_error_bound']=='OPEN'
                assert data['owner_adoption_of_D11']=='OPEN'
                assert data['screen_multiplier_512_is_a_theorem'] is False
                assert len(data['routes'])==6
                assert data['finite_witness_count']['composed_rows_checked']>=200
                assert data['finite_witness_count']['C_strtod_and_linked_libm_rechecked']>=41
                assert data['release_authorized'] is False
            if tag=='v3-analysis-v1':
                assert {x['rate_hz'] for x in data['cases']}=={2822400,5644800}
                assert {x['case'] for x in data['cases']}=={'low_level','silence'}
                assert all(x['spur_target_disposition']=='REPORT_ONLY' for x in data['cases'])
            checks[tag]={'status':observed,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'data_path':str(path.relative_to(results))}
        except Exception as ex:
            checks[tag]={'status':'FAIL','detail':str(ex)}
            failed.append(tag)
    try:
        version=command('git','-C',str(ROOT),'rev-parse','HEAD')
        base=command('git','-C',str(ROOT),'rev-parse','595d401')
        changed=command('git','-C',str(ROOT),'status','--porcelain')
    except Exception as ex:
        version='UNKNOWN';base='UNKNOWN';changed=str(ex);failed.append('provenance')
    record={
        'schema':'phase08-owner-gate-ledger/1',
        'status':('FAIL_SCOPED_VALIDATION' if failed else
                  'PASS_SCOPED_VALIDATION_WITH_OPEN_OWNER_GATES'),
        'release_authorized_by_this_report':False,
        'timestamp_utc':command('date','-u','+%Y-%m-%dT%H:%M:%SZ'),
        'git_commit':version,'git_baseline':base,
        'git_worktree_clean':not bool(changed),
        'binary_sha256':hashlib.sha256(sox.read_bytes()).hexdigest() if sox.exists() else None,
        'platform':{'system':platform.platform(),'machine':platform.machine(),
                    'python':platform.python_version()},
        'checks':checks,'failed':failed,
        'open_owner_gates':{
            'D11_P2_encoder_frontend_all_inputs':'OPEN',
            'D11_P3_decoder_all_inputs_and_final_SRC':'OPEN',
            'D6_numeric_pow_error_limit':'OPEN',
            'D16_new_owner_accepted_unified_decoder_references':'OPEN',
            'D4_spur_target_qualification':'REPORT_ONLY_OWNER_REVIEW',
            'D4_cross_ISA_full_qualification':'OPEN',
            'D8_release_2_0_0_authorization':'NOT_REQUESTED',
            'D8_automatic_native_routing':'NOT_AUTHORIZED',
        },
        'non_applicable_frozen_v2_comparator':'2^-48 permits only its 19 historical v2 fixtures',
    }
    results.mkdir(parents=True,exist_ok=True)
    (results/'phase08-gates.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(record['status'],f'{len(checks)-len(failed)}/{len(checks)} finite checks;',
          'universal P2/P3 and D16 approvals remain OPEN')
    return int(bool(failed))

if __name__=='__main__':raise SystemExit(main())
