#!/usr/bin/env python3
"""Audit the actual supplemental native build's instructions and compiler argv.

Reuses P11's object disassembly classifier and P12/P13 instruction checks.
Reads build.json produced by build_sdm_native.py instead of expecting an
Autotools Makefile or fabricating its object layout. Static ISA checks are
supporting evidence, not physical no-AVX/AVX1-only host qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from check_p11_isa import inspect_objdump

NAMES = {'legacy_sdm':'sdm.c', 'baseline_dispatch':'dsd_dispatch.c',
         'baseline_scalar':'dsd_kernels_scalar.c', 'sse2':'dsd_kernels_sse2.c',
         'avx1':'dsd_kernels_avx1.c', 'avx2':'dsd_kernels_avx2.c',
         'avx512':'dsd_kernels_avx512.c'}
STRICT = ['-fno-fast-math', '-ffp-contract=off', '-frounding-math', '-fno-lto']
ISA = {'sse2':['-msse2','-mno-avx'],
       'avx1':['-mavx','-mno-avx2','-mno-fma'],
       'avx2':['-mavx2','-mno-fma'],
       'avx512':['-mavx512f','-mno-avx512dq','-mno-avx512bw','-mno-avx512vl','-mno-fma']}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exec_sections(path):
    listing=subprocess.check_output(['objdump','-h',str(path)],text=True)
    sections=[]
    previous=None
    for line in listing.splitlines():
        match=re.match(r'\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s',line)
        if match:
            previous=(match[1],int(match[2],16))
        elif previous and 'CODE' in line and 'CONTENTS' in line:
            sections.append(previous)
            previous=None
    result={}
    with tempfile.TemporaryDirectory(prefix='sdm-text-check-') as directory:
        for i,(section,size) in enumerate(sections):
            out=Path(directory)/str(i)
            subprocess.run(['objcopy','--dump-section',f'{section}={out}',str(path)],
                           check=True,capture_output=True)
            if out.stat().st_size!=size:
                raise ValueError(f'{path}/{section}: section length differs')
            reloc=subprocess.check_output(['objdump','-r','-j',section,str(path)],text=True)
            relocs=[line.split() for line in reloc.splitlines()
                    if re.match(r'^\s*[0-9a-fA-F]+\s+R_',line)]
            result[section]={'bytes':size,'sha256':sha(out),'relocations':relocs}
    if not result:
        raise ValueError(f'no executable sections in {path}')
    return result


def load_objects(build, source_override, report, label):
    manifest=json.loads((build/'build.json').read_text())
    if manifest.get('schema')!='sdm-register/native-build/1' or manifest['status']!='PASS':
        raise ValueError(f'{label}: not a successful supported native build manifest')
    source=source_override or Path(manifest['source'])
    dependencies=manifest.get('dependency_sha256',{})
    report['checks'][label+'_records_dependency_hashes']=bool(dependencies)
    for relative,digest in dependencies.items():
        if not (source/relative).is_file() or sha(source/relative)!=digest:
            raise ValueError(f'{label}: dependency changed after build: {relative}')
    report['checks'][label+'_dependencies_match_build']=bool(dependencies)
    report['checks'][label+'_config_matches_build']=sha(build/'soxconfig.h')==manifest['config_sha256']
    result={}
    for name,filename in NAMES.items():
        matches=[c for c in manifest['commands'] if c['key']==filename]
        if len(matches)!=1 or matches[0]['returncode']:
            raise ValueError(f'{label}: missing/duplicate/failed command for {filename}')
        command=matches[0]['argv']
        original=Path(command[command.index('-o')+1])
        relative=original.relative_to(Path(manifest['build']))
        obj=build/relative
        if not obj.is_file():
            raise ValueError(f'{label}: missing object {obj}')
        assembly=subprocess.check_output(['objdump','-drwC',str(obj)],text=True)
        result[name]={'path':str(relative),'sha256':sha(obj),'compile_argv':command,
                      'assembly':assembly,**inspect_objdump(obj)}
        if name in ('legacy_sdm','baseline_scalar'):
            result[name]['executable_sections']=exec_sections(obj)
        source_hash=manifest['source_sha256']['src/'+filename]
        report['checks'][f'{label}_{name}_source_matches_build']=sha(source/'src'/filename)==source_hash
    report['manifests'][label]={'sha256':sha(build/'build.json'),
                              'compiler':manifest['compiler'],
                              'dependency_count':len(dependencies),
                              'config_sha256':manifest['config_sha256']}
    return result,source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-build',type=Path,required=True)
    parser.add_argument('--candidate-build',type=Path,required=True)
    parser.add_argument('--baseline-source',type=Path)
    parser.add_argument('--candidate-source',type=Path)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    report={'schema':'sdm-register/native-isa-audit/1','manifests':{},'objects':{},
            'checks':{},'errors':[],'limitations':__doc__}
    check=report['checks']
    try:
        baseline,baseline_source=load_objects(args.baseline_build.resolve(),args.baseline_source,report,'baseline')
        candidate,candidate_source=load_objects(args.candidate_build.resolve(),args.candidate_source,report,'candidate')
        check['same_compiler']=report['manifests']['baseline']['compiler']==report['manifests']['candidate']['compiler']
        check['same_configuration']=report['manifests']['baseline']['config_sha256']==report['manifests']['candidate']['config_sha256']
        for name,obj in candidate.items():
            argv=obj['compile_argv']
            base_argv=baseline[name]['compile_argv']
            # Include paths, input/output paths vary by tree; actual options must not.
            options=lambda v:[x for x in v[1:] if x.startswith('-') and not x.startswith('-I')]
            check[name+'_same_compile_options']=options(argv)==options(base_argv)
            check[name+'_strict_fp_flags']=all(x in argv for x in STRICT) and not any(
                x in argv for x in ('-ffast-math','-Ofast','-ffp-contract=fast','-ffp-contract=on'))
            check[name+'_no_fma']=not obj['fma_mnemonics']
            asm=obj['assembly']
            if name in ('legacy_sdm','baseline_dispatch','baseline_scalar','sse2'):
                check[name+'_no_avx']=not obj['avx_mnemonics']
            if name!='avx512':
                check[name+'_no_avx512_operands']=not bool(re.search(r'%zmm\d+|%k[1-7]\b',asm))
            if name in ISA:
                check[name+'_isolated_isa_flags']=all(x in argv for x in ISA[name])
            else:
                check[name+'_no_global_isa_flags']=not any(x.startswith(('-mavx','-march=')) for x in argv)
            if name in ('legacy_sdm','baseline_scalar'):
                check[name+'_all_executable_sections_identical']=obj['executable_sections']==baseline[name]['executable_sections']
                check[name+'_source_unchanged']=sha(candidate_source/'src'/NAMES[name])==sha(baseline_source/'src'/NAMES[name])
            if name in ('avx1','avx2'):
                check[name+'_ymm_executable']=obj['ymm_instructions']>0
            if name=='avx1':
                check[name+'_no_avx2']=not obj['possible_avx2_mnemonics']
            if name=='avx2':
                check['avx2_full_width_permute']=obj['avx_mnemonics'].get('vpermpd',0)>=2
            if name=='avx512':
                check['avx512_zmm_executable']=bool(re.search(r'%zmm\d+',asm))
                check['avx512_full_width_permutations']=len(re.findall(r'\bvperm(?:t2|i2)?pd\b',asm))>=2
                check['avx512_masked_tail_load']=bool(re.search(r'\bvmovupd\b.*%k[1-7]',asm))
                forbidden=r'\b(?:vpmovb2m|vpmovw2m|vpmovm2b|vpmovm2w|vpmullq|vpbroadcastb|vpbroadcastw)\b'
                check['avx512_no_known_DQ_BW_mnemonics']=not bool(re.search(forbidden,asm))
                # AVX-512F may have scalar EVEX instructions. A masked XMM/YMM
                # packed operation would require VL, disabled explicitly above.
                check['avx512_no_masked_XMM_YMM_packed']=not bool(re.search(
                    r'^.*\bv\w+(?:pd|ps|dq|qq|bw)\b[^\n]*%(?:xmm|ymm)\d+[^\n]*\{%k[1-7]\}',asm,re.M))
                declaration=(candidate_source/'src/dsd_kernels_avx512.c').read_text()
                check['avx512_declares_implicit_avx2']=bool(re.search(
                    r'"avx512",\s*LSX_DSD_CPU_SSE2\|LSX_DSD_CPU_AVX1\|LSX_DSD_CPU_AVX2\|LSX_DSD_CPU_AVX512F',declaration))
            (args.results/(name+'-disassembly.txt')).write_text(asm)
            # Full assembly lives beside JSON; no duplicate massive text payload.
            report['objects'][name]={k:v for k,v in obj.items() if k!='assembly'}
        report['baseline_text']={name:baseline[name]['executable_sections']
                                 for name in ('legacy_sdm','baseline_scalar')}
    except (KeyError,OSError,ValueError,subprocess.CalledProcessError) as exc:
        report['errors'].append(str(exc))
    report['status']='PASS' if check and all(check.values()) and not report['errors'] else 'FAIL'
    (args.results/'isa-isolation.json').write_text(json.dumps(report,indent=2)+'\n')
    for key,value in check.items():
        print('PASS' if value else 'FAIL',key)
    for error in report['errors']:
        print('FAIL',error)
    return report['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
