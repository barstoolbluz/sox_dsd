#!/usr/bin/env python3
"""P12 object-level ISA boundary audit; never an executable proof on its own."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
from check_p11_isa import ROOT,OBJECTS,inspect_objdump


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    report={'schema':'P12/ISA-audit/1','checks':{},'objects':{},'errors':[],
        'limits':'Static disassembly alone does not establish executable ISA compatibility or throughput'}
    objects=dict(OBJECTS,avx2='src/libdsd_kernels_avx2_la-dsd_kernels_avx2.o')
    for name,path in objects.items():
        full=ROOT/path
        if not full.is_file():
            report['errors'].append('missing object: '+path)
            continue
        cp=subprocess.run(['objdump','-drwC',str(full)],capture_output=True,text=True)
        if cp.returncode:
            report['errors'].append('objdump failed: '+path)
            continue
        report['objects'][name]={'path':path,**inspect_objdump(full)}
        if name=='avx2':
            a.results.mkdir(parents=True,exist_ok=True)
            (a.results/'avx2-disassembly.txt').write_text(cp.stdout)
    if len(report['objects'])==len(objects):
        v=report['objects']
        check=report['checks']
        for name in ('baseline_dispatch','baseline_scalar','sse2'):
            check[name+'_no_avx']=not v[name]['avx_mnemonics']
        check['avx1_ymm']=v['avx1']['ymm_instructions']>0
        check['avx1_no_avx2']=not v['avx1']['possible_avx2_mnemonics']
        check['avx2_ymm']=v['avx2']['ymm_instructions']>0
        check['avx2_full_width_permute']=v['avx2']['avx_mnemonics'].get('vpermpd',0)>=2
        for name in objects:
            check[name+'_no_fma']=not v[name]['fma_mnemonics']
        config=(ROOT/'src/Makefile').read_text()
        check['avx2_isolated_flags']=bool(re.search(
            r'DSD_AVX2_CFLAGS\s*=.*-mavx2\s+-mno-fma\s+-ffp-contract=off\s+-fno-lto',config))
        check['avx1_non_avx2_flags']=bool(re.search(
            r'DSD_AVX1_CFLAGS\s*=.*-mavx\s+-mno-avx2\s+-mno-fma\s+-ffp-contract=off\s+-fno-lto',config))
        check['no_global_avx2']=not bool(re.search(r'^CFLAGS\s*=[^\n]*-mavx2',config,re.M))
    report['status']='PASS' if report['checks'] and all(report['checks'].values()) and not report['errors'] else 'FAIL'
    a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'isa-isolation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    for k,v in report['checks'].items():print(('PASS' if v else 'FAIL'),k)
    for err in report['errors']:print('FAIL',err)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
