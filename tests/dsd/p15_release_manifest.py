#!/usr/bin/env python3
"""P15 release gate ledger: keep evidence integrity distinct from release permission.

Machine-readable release status is fail-closed. Inherited receipts are not
promoted into a new hardware test merely because their JSON parses. This tool
never rewrites frozen P10 certification or any pre-P15 result files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CERT=Path('tests/dsd/results/P10_certification_2026-10-11/certification.json')
BINDING=Path('tests/dsd/results/DECODE_OPTIMIZATION_2026-10-12/validation/p10-certificate-binding.json')
CHANGED={'src/dsd_plan.c','src/pcmdsd.c','src/pcmdsd.h','src/sdm.c'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def stored(root,relative):return read(root/relative)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P15/release')
    ap.add_argument('--require-qualified',action='store_true',
                    help='exit 2 unless all mandatory release gates have passing evidence')
    args=ap.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    cert=stored(ROOT,CERT)
    assert cert['decision']=='CERTIFIED' and cert['p10_phase']=='CLOSED', 'unexpected P10 reviewer decision'
    binding=stored(ROOT,BINDING)
    mismatches={r['path']:r for r in binding['mismatches']}
    assert set(mismatches)==CHANGED,'P10 lineage expectations changed; investigate'
    matches=[];changed=[];problems=[]
    for path,expected in cert['input_sha256'].items():
        obj=ROOT/path
        actual=sha(obj) if obj.is_file() else None
        row={'path':path,'p10_certificate_sha256':expected,'current_sha256':actual}
        if actual==expected:matches.append(row)
        elif path in CHANGED:
            base=mismatches[path]['supplied_baseline_sha256']
            row['p15_input_sha256']=base
            row['p15_has_additional_change']=(actual!=base)
            if mismatches[path]['certificate_sha256']!=expected:
                problems.append('certificate binding mismatch for '+path)
            changed.append(row)
        else:problems.append('unexpected changed/missing P10 pinned input '+path)
    if len(matches)!=31 or len(changed)!=4:
        problems.append(f'expected 31 historical pinned inputs and 4 later changed, got {len(matches)}, {len(changed)}')
    # The P10 verifier deliberately rejects current source. These 31 intact
    # references plus accepted P11-P14 handoffs and current-revision regression
    # are the scoped lineage, not a fabricated new P10 certificate.
    tests={}
    for key,filename,read_status in (
        ('p15_cli','cli-qualification.json',assess_cli),
        ('p15_release_regression','../run/run.json',assess_run),
        ('p15_numeric','../numeric/measure.json',assess_numeric),
        ('p15_bench_development','../bench/bench.json',assess_bench),
        ('p15_evidence_preservation','../preservation.json',assess_preservation)):
        path=args.results/filename
        if not path.is_file():tests[key]=dict(status='UNRUN',path=filename)
        else:
            payload=read(path)
            tests[key]=dict(status=read_status(payload),sha256=sha(path),path=filename)
    # Production defaults deliberately held. The P10 positive certificate is
    # real; it does not certify future vector automatic selection, unavailable
    # hardware, or the entire current-revision P15 release workload.
    requirements=[
        dict(id='P10-positive-scalar-mastering-certificate',status='PASS-INHERITED',
             evidence=str(CERT),scope='original P10 scalar kernels and admitted corpus only'),
        dict(id='P10-current-source-lineage',status='RECONCILED' if not problems else 'FAIL',
             evidence='p10_source_lineage',scope='31 original SHA matches; four later edited paths documented below; current tests separately required'),
        dict(id='P15-current-source-regressions',status='PASS' if
             tests['p15_cli']['status']=='PASS' and
             tests['p15_release_regression']['status']=='PASS' and
             tests['p15_numeric']['status']=='PASS-SUBSET' and not problems
             else 'UNRUN-OR-FAIL',
             evidence=tests['p15_cli']['path']),
        dict(id='P15-full-3x9x2-numerical-release-matrix',status='UNRUN',
             evidence='P07 rendered PCM plus P15 54-cell versioned audio parity is not a complete independent spectral release matrix'),
        dict(id='P15-physical-Intel-AVX512-performance',status='UNRUN',
             evidence='Inherited Intel cross-vendor/virtual-machine receipts do not establish pinned physical throughput'),
        dict(id='P15-physical-older-AVX-performance',status='UNRUN',
             evidence='P11 AVX1-only QEMU confirms instruction compatibility, not physical throughput'),
        dict(id='P15-AMD-AVX512-preference',status='REJECTED',
             evidence='tests/dsd/results/P13_amd_physical_avx512_2026-10-12/README.md',
             scope='physical AMD measurement favors existing non-AVX512 defaults'),
        dict(id='P15-2x-six-channel-DSD256-controlled-reference-target',status='UNVERIFIED',
             evidence='No current-baseline physical reference-host 2x matched control certificate'),
        dict(id='P15-current-full-release-soaks-every-profile-ISA',status='UNRUN',
             evidence='Historical P10/P11 scalar/ISA soak receipts are not full P15 physical qualification'),
        dict(id='P15-current-independent-codec-and-hardware-corpus',status='UNRUN',
             evidence='Historical external excerpts not present for independent rerender'),
    ]
    requirements.extend(dict(id='P15-available-host-'+key,
          status=x['status'] if status_is_pass(x['status']) else 'UNRUN-OR-FAIL',
          evidence=x['path']) for key,x in tests.items())
    required=['P10-current-source-lineage','P15-current-source-regressions',
              'P15-available-host-p15_evidence_preservation',
              'P15-full-3x9x2-numerical-release-matrix',
              'P15-physical-Intel-AVX512-performance','P15-physical-older-AVX-performance',
              'P15-2x-six-channel-DSD256-controlled-reference-target',
              'P15-current-full-release-soaks-every-profile-ISA',
              'P15-current-independent-codec-and-hardware-corpus']
    gate_by_id={r['id']:r for r in requirements}
    not_closed=[g for g in required if gate_by_id[g]['status'] not in ('PASS','RECONCILED')]
    manifest=dict(schema='P15/release-result-manifest/1',
        base_archive_sha256='73454c06c4e071f9c1c3078846d325fdb6214a65eda3a9e4f49b38b192a42229',
        source_baseline='f13dda14',p10_certificate_sha256=sha(ROOT/CERT),
        original_certificate_source_count=len(cert['input_sha256']),
        p10_source_lineage=dict(unchanged=matches,later_changes=changed,
            errors=problems,status='RECONCILED-FOR-SCOPED-REVIEW' if not problems else 'FAIL',
            note='The unchanged P10 verifier intentionally fails on later source bytes; not a P15 code defect.'),
        tests=tests, gates=requirements, mandatory_unclosed=not_closed,
        default_promotion_authorized=not not_closed, status='READY' if not not_closed else 'BLOCKED',
        preserved_policy='legacy CLI mode, scalar SDM and scalar/SSE2 FIR auto dispatch; no new automatic AVX512')
    out=args.results/'release-manifest.json'
    tmp=out.with_suffix('.tmp')
    tmp.write_text(json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+'\n')
    tmp.replace(out)
    print(json.dumps(dict(status=manifest['status'],mandatory_unclosed=not_closed,
                          lineage_errors=problems,report='release-manifest.json'),sort_keys=True))
    if problems:return 1
    return 2 if args.require_qualified and not_closed else 0


def assess_cli(x):
    rows=x.get('cases',[])
    audio=[row for row in rows if row.get('name','').startswith('versioned_decode_audio_')]
    plan=[row for row in rows if row.get('name','').startswith('versioned_decode_plan_')]
    expected=3*9*2
    counts=x.get('summary',{})
    if (x.get('status')=='PASS' and len(audio)==len(plan)==expected and
        len({r['name'] for r in audio})==expected and
        len({r['name'] for r in plan})==expected and
        counts.get('failed')==0 and counts.get('passed')==len(rows) and
        all(r.get('status')=='PASS' for r in rows)):
        return 'PASS'
    return 'FAIL-OR-INCOMPLETE'


def assess_run(x):
    counts=x.get('counts',{})
    if (x.get('verdict')=='pass' and counts.get('fail')==0 and
        counts.get('skip')==0 and counts.get('xpass')==0 and
        counts.get('pass',0)>0):
        return 'PASS'
    return 'FAIL-OR-INCOMPLETE'


def assess_numeric(x):
    counts=x.get('summary',{})
    if counts.get('failed')==0 and counts.get('passed',0)>0:
        return 'PASS-SUBSET' if counts.get('unrun_gates') else 'PASS'
    return 'FAIL-OR-INCOMPLETE'


def assess_bench(x):
    summary=x.get('summary',{})
    planned=x.get('planned_cases',[])
    complete=x.get('completed_cases',[])
    p13=x.get('p13_avx512_vs_avx2',{})
    p14=x.get('p14_observer_overhead',{})
    if (summary.get('status')=='pass-development-only' and
        planned and len(planned)==len(complete) and
        summary.get('failed_or_incomplete')==[] and
        p13.get('exit')==0 and p14.get('exit')==0 and
        x.get('config',{}).get('profile')=='full' and
        x.get('config',{}).get('repetitions',0)>=15):
        return 'PASS-DEVELOPMENT-ONLY'
    return 'FAIL-OR-INCOMPLETE'


def assess_preservation(x):
    if (x.get('assessment')=='PASS' and x.get('protected_file_violations')==[] and
        x.get('old_files_deleted')==[] and
        x.get('source_archive_sha256')=='73454c06c4e071f9c1c3078846d325fdb6214a65eda3a9e4f49b38b192a42229' and
        x.get('old_result_file_count_unchanged')==x.get('old_result_file_count') and
        x.get('old_handoff_file_count_unchanged')==x.get('old_handoff_file_count')):
        return 'PASS'
    return 'FAIL-OR-INCOMPLETE'


def status_is_pass(x):
    return x in ('PASS','PASS-SUBSET','PASS-DEVELOPMENT-ONLY')

if __name__=='__main__':raise SystemExit(main())
