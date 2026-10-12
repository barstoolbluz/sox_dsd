#!/usr/bin/env python3
"""P13 built-object AVX-512F instruction isolation audit.

Compile flags and disassembly are supporting evidence only. Capability
selection, correct OS state and actual execution have their own gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from check_p11_isa import ROOT, OBJECTS, inspect_objdump


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--results',type=Path,required=True)
    args=a.parse_args()
    objs={**OBJECTS,'avx2':'src/libdsd_kernels_avx2_la-dsd_kernels_avx2.o',
          'avx512':'src/libdsd_kernels_avx512_la-dsd_kernels_avx512.o'}
    report=dict(schema='P13/ISA-isolation/1',objects={},checks={},errors=[],
        limitations='Object ISA inspection; executable CPU/XCR0 and hardware tests are separate')
    for name,rel in objs.items():
        p=ROOT/rel
        if not p.is_file():
            report['errors'].append(f'missing {rel}')
            continue
        try:
            v=inspect_objdump(p)
            cp=subprocess.run(['objdump','-drwC',str(p)],capture_output=True,text=True)
            if cp.returncode: raise RuntimeError(f'objdump exit {cp.returncode}')
            if name=='avx512':
                args.results.mkdir(parents=True,exist_ok=True)
                (args.results/'avx512-disassembly.txt').write_text(cp.stdout)
            report['objects'][name]=dict(path=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                         **v)
        except Exception as exc:
            report['errors'].append(f'{name}: {exc}')
    if len(report['objects'])==len(objs):
        checks=report['checks']
        for name in ('baseline_dispatch','baseline_scalar','sse2','avx1','avx2'):
            cp=subprocess.run(['objdump','-d',str(ROOT/objs[name])],capture_output=True,text=True)
            checks[name+'_no_zmm']=not bool(re.search(r'%zmm\d+|%k[1-7]\b',cp.stdout))
        for name in objs:
            checks[name+'_no_fma']=not report['objects'][name]['fma_mnemonics']
        cp=subprocess.run(['objdump','-d',str(ROOT/objs['avx512'])],capture_output=True,text=True)
        asm=cp.stdout
        checks['avx512_zmm_execution']=bool(re.search(r'%zmm\d+',asm))
        checks['avx512_full_width_permutations']=len(re.findall(r'\bvperm(?:t2|i2)?pd\b',asm))>=2
        checks['avx512_masked_tail_load']=bool(re.search(r'\bvmovupd\b.*%k[1-7]',asm))
        # Known DQ/BW/VL-specific mnemonics. vextractf64x4 and
        # vinsertf64x4 are AVX-512F operations, not AVX-512DQ.
        # The compiler also explicitly
        # disables all these subsets, so no extended instruction should
        # appear unless the flags or toolchain are broken.
        forbidden=r'\b(?:vpmovb2m|vpmovw2m|vpmovm2b|vpmovm2w|vpermi2q|vpermt2q|vpmullq|vpbroadcastb|vpbroadcastw)\b'
        checks['avx512_no_known_non_F_subsets']=not bool(re.search(forbidden,asm))
        config=(ROOT/'src/Makefile').read_text()
        checks['isolated_compiler_flags']=bool(re.search(
            r'DSD_AVX512_CFLAGS\s*=.*-mavx512f\s+-mno-avx512dq\s+-mno-avx512bw\s+-mno-avx512vl\s+-mno-fma\s+-ffp-contract=off\s+-fno-lto',config))
        checks['no_global_avx512']=not bool(re.search(r'^CFLAGS\s*=[^\n]*-mavx512f',config,re.M))
        checks['baseline_dispatch_no_avx']=not report['objects']['baseline_dispatch']['avx_mnemonics']
        checks['avx1_no_avx2']=not report['objects']['avx1']['possible_avx2_mnemonics']
        # GCC enables AVX2 with -mavx512f; the P13 kernel descriptor must
        # require it instead of granting unsupported CPUID-only requests.
        declaration=(ROOT/'src/dsd_kernels_avx512.c').read_text()
        checks['avx512_declares_implicit_avx2']=bool(re.search(
            r'"avx512",\s*LSX_DSD_CPU_SSE2\|LSX_DSD_CPU_AVX1\|LSX_DSD_CPU_AVX2\|LSX_DSD_CPU_AVX512F',declaration))
    report['status']='PASS' if not report['errors'] and report['checks'] and all(report['checks'].values()) else 'FAIL'
    args.results.mkdir(parents=True,exist_ok=True)
    (args.results/'isa-isolation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    for name,ok in report['checks'].items():print('PASS' if ok else 'FAIL',name)
    for item in report['errors']:print('FAIL',item)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
