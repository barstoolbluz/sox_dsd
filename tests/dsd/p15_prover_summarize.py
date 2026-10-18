#!/usr/bin/env python3
"""Mechanical, provenance-preserving paired local P15 benchmark summary."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'tests/dsd/results/P15_prover_optimization_2026-10-18'


def read(file):
    return [json.loads(line) for line in (E/file).read_text().splitlines()]


def result_counts(rows):
    return dict(Counter(x['result']['status'] for x in rows))


def main():
    corpus=json.loads((E/'CORPUS.json').read_text())['cases']
    assert len(corpus)==104 and sum('historical_43' in r['groups'] for r in corpus)==43
    assert sum(any(g.startswith('600s_sample_') for g in r['groups']) for r in corpus)==48
    before4=read('BASELINE_4S.jsonl'); after4=read('OPTIMIZED_4S.jsonl')
    before2=read('BASELINE_2S.jsonl'); after2=read('OPTIMIZED_2S.jsonl')
    before60=read('BASELINE_60S.jsonl'); after60=read('OPTIMIZED_60S.jsonl')
    for rows,expected in ((before4,43),(after4,43),(before2,25),(after2,25),
                          (before60,1),(after60,7)):
        assert len(rows)==expected, (len(rows),expected)
        assert len({x['index'] for x in rows})==expected
        assert all(x['job']==next(c['job'] for c in corpus if c['index']==x['index']) for x in rows)
    assert {x['index'] for x in before4}=={x['index'] for x in after4}
    assert {x['index'] for x in before2}=={x['index'] for x in after2}
    join4={x['index']:x for x in before4}
    fir_ratios=[]
    for x in after4:
        original=join4[x['index']]
        f1=original['profile_calls'].get('fir',0)
        f2=x['profile_calls'].get('fir',0)
        if f1 and f2:
            fir_ratios.append(f2/f1)
    measured=[]
    for row in sorted(after60,key=lambda r:r['index']):
        candidate=dict(index=row['index'],cell=row['cell_id'],mode=row['job']['mode'],
             band_hz=[row['job']['lo'],row['job']['hi']],
             archived_60s_status=row['original_receipt_status'],
             archived_60s_reason=row['original_receipt_reason'],
             result=row['result']['status'],
             unresolved_reason=row['result'].get('reason'),
             elapsed_s=row['elapsed_s'],
             process_high_water_kib=row['process_high_water_kib'],
             fir_interval_evaluations=row['result'].get('fir_interval_evaluations'),
             certified_max_alias_upper=row['result'].get('max_coherent_alias_upper'),
             certified_total_upper=row['result'].get('max_total_transfer_upper'))
        matching=[b for b in before60 if b['index']==row['index']]
        if matching:
            candidate['same_host_baseline_60s']=dict(status=matching[0]['result']['status'],
                       elapsed_s=matching[0]['elapsed_s'],
                       process_high_water_kib=matching[0]['process_high_water_kib'])
        measured.append(candidate)
    micro=json.loads((E/'FIR_MICROBENCH.json').read_text())
    audit=json.loads((E/'STAGE_PARITY_AUDIT.json').read_text())
    integrity=json.loads((E/'SOURCE_INTEGRITY.json').read_text())
    dispatch=list((E/'optimized_dispatch_receipts').glob('*.json'))
    assert len(dispatch)==1
    verified=json.loads(dispatch[0].read_text())
    assert verified['certificate']['status']=='PASS-LOCAL-BAND'
    assert verified['job']['cell_id']=='dsd128.mastering.pcm384000'
    report=dict(schema='P15/prover-optimized-quantified-outcomes/1',
        original_campaign=dict(total_intervals=11516,passes=6835,open=4681,
              open_time_budget=3907,open_structural_precondition=774),
        optimized_full_campaign_reexecuted=False,
        corpus=dict(size=len(corpus),historical_43=43,
            source_bound_historical_extended_budget_sample=48),
        short_historical_benchmark=dict(seconds_per_job=4,case_count=43,
             baseline=result_counts(before4),optimized=result_counts(after4),
             source_fir_interval_evaluations_baseline=sum(x['profile_calls'].get('fir',0) for x in before4),
             source_fir_interval_evaluations_optimized=sum(x['profile_calls'].get('fir',0) for x in after4),
             per_case_fir_evaluation_median_ratio=statistics.median(fir_ratios)),
        short_representative_benchmark=dict(seconds_per_job=2,case_count=25,
             baseline=result_counts(before2),optimized=result_counts(after2)),
        actual_sixty_second_selected=dict(cases=measured,optimized_counts=result_counts(after60),
             baseline_same_host_counts=result_counts(before60),
             nonrepresentative_selection=True),
        warm_fir_microbenchmark=dict(taps_to_speedup={str(x['taps']):x['speedup']
             for x in micro['results']},process_peak_rss_kib=micro['process_peak_rss_kib']),
        exact_binary64_symmetry_audit=audit['counts'],
        historical_evidence_byte_integrity=dict(status=integrity['status'],
             verified_files=integrity['verified_files'],
             inventory_sha256=integrity['original_evidence_inventory_sha256']),
        new_dispatch_receipt=dict(file=str(dispatch[0].relative_to(ROOT)),
             status=verified['certificate']['status'],
             proof_interval=verified['certificate']['certified_hz'],
             alias_upper=verified['certificate']['max_coherent_alias_upper'],
             source_bindings_count=len(verified['binding']['source'])),
        release_disposition='BLOCKED; no full-campaign or FFT4G roundoff closure',
        caution='OPEN is not FAIL. Alias routing schedules and spectral inequality proofs are distinct.')
    (E/'RESULTS_SUMMARY.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('actual_sixty_second_selected',)},indent=2))


if __name__=='__main__':main()
