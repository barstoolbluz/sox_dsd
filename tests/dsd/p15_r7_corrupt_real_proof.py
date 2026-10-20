#!/usr/bin/env python3
"""Falsification campaign against a REAL independently verified R7 proof."""
from __future__ import annotations
import argparse,copy,json
from pathlib import Path
from p15_r7_witness import verify
from p15_r6_exact_composite import ExactRefusal


def exercise(original:dict):
    assert verify(original)['status']=='PASS-LOCAL-R7-INDEPENDENT'
    variants={}
    p=copy.deepcopy(original);p['binding']['r7_method_sources']['p15_r7_fast_fir.py']='0'*64
    variants['forged_math_kernel']=p
    p=copy.deepcopy(original);p['binding']['r6_source_and_method']['capture_binding']='f'*64
    variants['forged_stage_operator']=p
    p=copy.deepcopy(original);p['leaves'][0]['bounds']['source_stop_upper']='0'
    variants['fabricated_stop_upper']=p
    p=copy.deepcopy(original);p['leaves'][0]['hi']='1/2'
    variants['missing_frequency_coverage']=p
    p=copy.deepcopy(original);p['independent_check']['max_composite_unwanted_exact']='0'
    variants['fabricated_summary']=p
    p=copy.deepcopy(original);p['leaves'][0]['lo']='-1/100'
    variants['out_of_domain_frequency']=p
    failures={}
    for label,corrupt in variants.items():
        try:verify(corrupt)
        except (ExactRefusal,ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
            failures[label]=str(exc)
        else:
            raise AssertionError('CORRUPTED PROOF ACCEPTED: '+label)
    return dict(schema='P15/R7/adversarial-real-proof-replay/1',
        positive_control='PASS-LOCAL-R7-INDEPENDENT',
        deliberate_corruptions_rejected=len(failures),
        deliberate_corruptions_total=len(variants),rejections=failures)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proof',type=Path,required=True)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    report=exercise(json.loads(args.proof.read_text()))
    if args.out:
        from p15_r6_witness import _atomic
        _atomic(args.out,report)
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=='__main__':main()
