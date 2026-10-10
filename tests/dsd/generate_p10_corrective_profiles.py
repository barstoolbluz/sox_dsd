#!/usr/bin/env python3
"""Versioned, unpromoted P10 corrective profile evidence; no promotion side effects.

The original P10 negative certificate remains immutable. This manifest records
new admitted-soak results alongside missing independent release requirements.
Use --check after the source tree and evidence have been archived.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from qualify_p10_corrective import ROOT,verify,sha

REF=ROOT/'tests/dsd/reference'
BASE=ROOT/'tests/dsd/results/P10_corrective'
TARGET=REF/'p10_profiles_corrective.json'


def build():
    status=verify(BASE)
    prior=json.loads((REF/'p10_profiles.json').read_text())
    soaks=json.loads((BASE/'nominal-v2/soak/soak.json').read_text())
    per_rate={p['configuration']['native_hz']:p for p in soaks['profiles']}
    rows=[]
    for p in prior['profiles']:
        native=p['native_hz'];s=per_rate[native]
        checks=['stage_unity_scaling_and_distribution',
            'original_expected_overload_replay','inherited_numeric_183_bit_identical',
            'inherited_analysis_v1','regressions_and_candidate_cli','nominal_30min_all_rates',
            'inherited_prepared_host_read_repack',
            'representative_hardware_1hour_per_profile_isa',
            'independent_realworld_corpus']
        gates={k:status['gates'][k]['status'] for k in checks}
        rows.append(dict(id=p['id'], native_hz=native,bank=p['bank'],
            original_profile_sha256=sha(REF/'p10_profiles.json'),
            guard_manifest_sha256=sha(REF/'p10_guards.json'),
            exact_rate_and_prefilter_identity='inherited unchanged from original P10 negative certificate',
            stage_reference_scale=.5,
            nominal_fixture_version='p10-soak-nominal-v2',
            nominal_fixture_sha256=sha(REF/'p10_soak_nominal_v2.json'),
            nominal_soak_status=s['status'],
            nominal_soak_seconds=s['completed_audio_seconds'],
            committed_native_frames=s['raw']['committed_native_frames'],
            nominal_max_post_scale_peak=s['raw']['peak'],
            original_overload_regression='PASS (original-v1 unchanged, exact failure replay)',
            gate_statuses=gates,qualified=False,
            status='INCOMPLETE' if all(v in ('PASS','UNRUN') for v in gates.values()) else 'FAILED',
            deployment='BLOCKED: no release/production/default promotion'))
    return dict(schema='P10/corrective-negative-profile-certificates/1',
        reviewer_determination='SUPPORTED: 0.7 noise overload is the required behavior after verified unity-stage and once-only scaling',
        original_negative_certificate_sha256=sha(REF/'p10_profiles.json'),
        original_soak_evidence_sha256=sha(ROOT/'tests/dsd/results/P10/soak/soak.json'),
        source_generator_sha256=sha(ROOT/'tests/dsd/test_p10.c'),
        frozen_analysis_sha256=sha(REF/'analysis-v1/SHA256SUMS.txt'),
        corrective_qualification_evidence_sha256=sha(BASE/'qualification.json'),
        nominal_fixture_sha256=sha(REF/'p10_soak_nominal_v2.json'),
        status=status['status'],qualified=False,default_promotion=False,
        profiles=rows,remaining_release_gates=status['remaining_release_gates'],
        warning='Nominal 30-minute synthetic soak is not an independent real-world-corpus or one-hour hardware qualification. No positive certificate has been issued.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    expected=build()
    if args.check:
        if not TARGET.exists() or json.loads(TARGET.read_text())!=expected:
            raise RuntimeError('corrective profile evidence mismatch; regenerate with current receipts')
        print('corrective negative profiles verified:',len(expected['profiles']))
        return 0
    if TARGET.exists() and json.loads(TARGET.read_text())!=expected:
        raise RuntimeError('refusing to overwrite a versioned corrective certificate with different evidence')
    TARGET.write_text(json.dumps(expected,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print('corrective release certificate:',expected['status'],'promoted:',expected['qualified'])
    return 0

if __name__=='__main__':raise SystemExit(main())
