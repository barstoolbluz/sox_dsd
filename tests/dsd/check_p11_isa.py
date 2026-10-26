#!/usr/bin/env python3
"""P11 instruction isolation audit of executable built object code.

A disassembly audit complements, but never substitutes for, executable tests
on physical AVX1 hardware with AVX2 disabled and actual no-AVX hosts.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OBJECTS={
    'baseline_dispatch':'src/libsox_ng_la-dsd_dispatch.o',
    'baseline_scalar':'src/libsox_ng_la-dsd_kernels_scalar.o',
    'sse2':'src/libdsd_kernels_sse2_la-dsd_kernels_sse2.o',
    'avx1':'src/libdsd_kernels_avx1_la-dsd_kernels_avx1.o',
}


def inspect_objdump(path):
    p=subprocess.run(['objdump','-d',str(path)],capture_output=True,text=True,cwd=ROOT)
    if p.returncode:raise RuntimeError(f'objdump failure on {path}: {p.stderr[-500:]}')
    names=[];ymm=0
    for line in p.stdout.splitlines():
        parts=line.split('\t')
        if len(parts)<3 or not parts[0].strip().endswith(':'):continue
        asm=parts[2].strip()
        match=re.match(r'([A-Za-z][A-Za-z0-9.]*)\b',asm)
        if match:
            names.append(match.group(1).lower())
            if '%ymm' in asm:ymm+=1
    counts=collections.Counter(names)
    # AVX1 legally uses vperm2f128 and vpermilpd. VEX-encoded 128-bit
    # integer instructions may also be AVX1, so classify any suspicious
    # 256-bit integer operation by its YMM operand, not the "vp" prefix.
    # VPTEST is also legal with YMM operands in AVX1. Its 256-bit intrinsic
    # is declared in the AVX (not AVX2) header:
    # https://clang.llvm.org/doxygen/avxintrin_8h.html
    avx2_only=('vpermq','vpermpd','vperm2i128','vgather',
               'vextracti128','vinserti128','vbroadcasti128','vpbroadcast',
               'vpsrlv','vpsrav','vpsllv','vpblendd')
    forbidden_avx2=sorted(m for m in counts if m.startswith(avx2_only))
    for line in p.stdout.splitlines():
        parts=line.split('\t')
        if len(parts)<3:continue
        asm=parts[2].strip()
        if '%ymm' in asm and re.match(r'vp(?!erm(?:2f128|ilpd)\b|test\b)[A-Za-z0-9]+',asm):
            forbidden_avx2.append(asm.split()[0])
    forbidden_avx2=sorted(set(forbidden_avx2))
    forbidden_fma=[m for m in counts if m.startswith(('vfmadd','vfmsub','vfnmadd','vfnmsub'))]
    return dict(total_instructions=len(names),ymm_instructions=ymm,
       avx_mnemonics={k:v for k,v in sorted(counts.items()) if k.startswith('v')},
       possible_avx2_mnemonics=forbidden_avx2,fma_mnemonics=forbidden_fma)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--build-root',type=Path,default=ROOT,
                        help='configured build tree containing the compiled objects')
    a=parser.parse_args()
    build=a.build_root.resolve()
    report=dict(schema='P11/ISA-audit/1',objects={},checks={},errors=[],
       note='Static audit of built objects only; execution tests and AVX1-only hardware are independent gates')
    for tier,source in OBJECTS.items():
        obj=build/source
        if not obj.is_file():
            report['errors'].append(f'missing built object {source}')
            continue
        try:
            report['objects'][tier]=dict(path=source,**inspect_objdump(obj))
        except (OSError,RuntimeError) as exc:report['errors'].append(str(exc))
    d=report['objects']
    if len(d)==len(OBJECTS):
        for name in ('baseline_dispatch','baseline_scalar','sse2'):
            report['checks'][name+'_no_avx']=not bool(d[name]['avx_mnemonics'])
        report['checks']['avx1_ymm_executable']=d['avx1']['ymm_instructions']>0
        report['checks']['avx1_no_avx2']=not bool(d['avx1']['possible_avx2_mnemonics'])
        report['checks']['avx1_no_fma']=not bool(d['avx1']['fma_mnemonics'])
        report['checks']['sse2_no_fma']=not bool(d['sse2']['fma_mnemonics'])
        m=build/'src/Makefile'
        flags=m.read_text() if m.is_file() else ''
        report['checks']['explicit_avx1_flags']=bool(re.search(
            r'DSD_AVX1_CFLAGS\s*=.*-mavx\s+-mno-avx2\s+-mno-fma\b.*-fno-lto',flags))
        report['checks']['explicit_sse2_flags']=bool(re.search(
            r'DSD_SSE2_CFLAGS\s*=.*-msse2\s+-mno-avx\b.*-fno-lto',flags))
    report['status']='PASS' if report['checks'] and all(report['checks'].values()) and not report['errors'] else 'FAIL'
    a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'isa-isolation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    for key,val in report['checks'].items():print(('PASS' if val else 'FAIL'),key)
    for msg in report['errors']:print('FAIL',msg,file=sys.stderr)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
