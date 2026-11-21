#!/usr/bin/env python3
"""D12: numerical parity with exact audited harness source, not an analogy."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor_audited_v2'))
import dsdqual.analysis as adopted
import audited_spectrum as candidate

# Pinned SHA256 of files extracted without modification from owner supplied
# Switched_Resonator_Qualification_Harness_AuditFixed_v2_Full.tar.gz.
ORIGINS={
    '__init__.py':'97d9f5aae9bbf82561944a439f50db2ef213e8395d928e778bbec22c8246cfda',
    'analysis.py':'ffe49f0e097baf810848c3b688670669069a819b1aafbab31261effe19256a23',
    'dsf.py':'93b8412c98d082f312e055f3b0a4797d5b7537ed12b99cfb1aaa7c2b3c9fa876',
    'common.py':'384d274ce4e0ac0aac3b216a58d698f0d428a167d8001606c9411b9d7aaffff0',
}


def check(test, message):
    if not test:raise AssertionError(message)


def run():
    for filename, expected in ORIGINS.items():
        actual=hashlib.sha256((HERE/'vendor_audited_v2/dsdqual'/filename).read_bytes()).hexdigest()
        check(actual==expected,f'audited harness source changed: {filename}')
    data=[]
    rng=np.random.default_rng(0x8082026)
    for fs in (2822400, 5644800):
        for N in (2048, 8192, 32768):
            x=rng.normal(.11,.23,N).astype(np.float64)
            # Multiple resolved in-band and out-of-band tones, plus nonzero DC.
            x+=(.07*np.sin(2*np.pi*101*np.arange(N,dtype=np.float64)/N))
            for beta in (30.,34.):
                weighted,bands=candidate.analyze(x,fs,beta)
                expected=adopted.bandpower(x,fs,beta)
                check(set(bands)==set(expected),'band names are not identical')
                windows=np.kaiser(N,beta)
                dc=float(np.dot(x,windows**2)/np.dot(windows,windows))
                check(math.isclose(weighted,dc,rel_tol=1e-13,abs_tol=1e-14),
                      'weighted DC differs')
                max_rel=0.
                for name,item in bands.items():
                    old=expected[name]['power'];new=item['power']
                    delta=abs(old-new)/max(old,new,1e-200)
                    check(delta <= 2e-13,f'{fs}/{N}/{beta}/{name}: spectral mismatch {delta}')
                    max_rel=max(max_rel,delta)
                    check(math.isclose(item['dbfs'],10*math.log10(max(old/.125,1e-300)),
                                       rel_tol=0,abs_tol=1e-10),f'{name}: dbfs mismatch')
                    check(item['bins'][1]>item['bins'][0],f'{name}: empty band')
                data.append({'sample_rate':fs,'frames':N,'beta':beta,'max_relative_power_delta':max_rel})
    return {'schema':'phase08-audited-metrology-parity/1','status':'PASS_FINITE_PARITY',
            'audit_source_hashes':ORIGINS,'cases':data,'case_count':len(data),
            'analysis_v1_primary_encoder_quality_gate':'SEPARATE',
            'universal_metrology_qualification':'OPEN'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True,type=Path)
    a=p.parse_args()
    try: result=run()
    except Exception as e: result={'status':'FAIL','error':str(e)}
    a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'metrology-parity.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f"{result['status']}: D12 {result.get('case_count',0)} parity cases")
    if result['status']=='FAIL':print(result['error'],file=sys.stderr)
    return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
