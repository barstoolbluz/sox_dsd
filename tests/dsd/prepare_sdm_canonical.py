#!/usr/bin/env python3
"""Link the same benchmark against two canonical Autotools builds and audit ISA.

The builds must already exist. No production source or build configuration is
changed. Compiler/options come from each actual generated src/Makefile. The
normal project ISA audits run on the actual canonical object layout; executable
section and relocation comparisons protect the independent scalar/legacy code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

from check_sdm_register_isa import exec_sections


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_value(text,name):
    match=re.search(r'^'+re.escape(name)+r'[ \t]*=[ \t]*([^\n]*)',text,re.M)
    if not match:
        raise ValueError('missing configured Makefile variable: '+name)
    value=match[1].strip()
    if '$' in value or value.endswith('\\'):
        raise ValueError('non-literal Makefile variable requires make expansion: '+name)
    return shlex.split(value)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline-build',type=Path,required=True)
    ap.add_argument('--candidate-build',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args()
    script=Path(__file__).resolve().parent
    benchmark=script/'bench_sdm_register.c'
    a.results.mkdir(parents=True,exist_ok=True)
    report={'schema':'sdm-register/canonical-benchmark-preparation/1',
            'benchmark_source_sha256':sha(benchmark),'builds':{},'checks':{},'errors':[]}
    snapshots={}
    try:
        for label,build in (('baseline',a.baseline_build.resolve()),
                            ('candidate',a.candidate_build.resolve())):
            identity=json.loads((build/'build-report.json').read_text())
            if identity['status']!='PASS' or identity['schema']!='sdm-register/canonical-build/1':
                raise ValueError(label+': canonical build did not pass')
            snapshot=Path(identity['snapshot'])
            snapshots[label]=snapshot
            makefile=build/'src/Makefile'
            text=makefile.read_text()
            settings={name:make_value(text,name) for name in ('CC','CFLAGS','CPPFLAGS','LDFLAGS','LIBS')}
            archive=build/'src/.libs/libsox_ng.a'
            target=build/'test/bench_sdm_register'
            argv=[*settings['CC'],*settings['CPPFLAGS'],'-DHAVE_CONFIG_H',
                  '-I'+str(build/'src'),'-I'+str(snapshot/'src'),*settings['CFLAGS'],
                  str(benchmark),str(archive),*settings['LDFLAGS'],*settings['LIBS'],
                  '-o',str(target)]
            p=subprocess.run(argv,capture_output=True,text=True)
            item={'build':str(build),'snapshot':str(snapshot),'settings':settings,
                  'compile_argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
                  'source_build_manifest_sha256':sha(build/'build-report.json'),
                  'makefile_sha256':sha(makefile),'make_log_sha256':sha(build/'make.log'),
                  'config_sha256':sha(build/'src/soxconfig.h'),
                  'library_sha256':sha(archive),'sox_sha256':sha(build/'src/sox')}
            report['builds'][label]=item
            if p.returncode:
                raise ValueError(label+': benchmark link failed: '+p.stderr)
            item['benchmark_sha256']=sha(target)
            item['benchmark_path']=str(target)
        check=report['checks']
        check['identical_compiler_options']=report['builds']['baseline']['settings']==report['builds']['candidate']['settings']
        check['identical_configuration']=report['builds']['baseline']['config_sha256']==report['builds']['candidate']['config_sha256']
        check['strict_floating_point_flags']=all(flag in report['builds']['candidate']['settings']['CFLAGS']
            for flag in ('-fno-fast-math','-ffp-contract=off','-frounding-math','-fno-lto'))
        for phase in ('p11','p12','p13'):
            log=a.results/(phase+'-isa.log')
            p=subprocess.run([sys.executable,str(script/f'check_{phase}_isa.py'),
                              '--build-root',str(a.candidate_build.resolve()),
                              '--results',str(a.results/('isa-'+phase))],capture_output=True,text=True)
            log.write_text(p.stdout+p.stderr)
            check[phase+'_actual_canonical_objects_isa_audit']=p.returncode==0
        report['unchanged_code']={}
        for name in ('sdm','dsd_kernels_scalar','dsd_dispatch'):
            relative=Path('src')/('libsox_ng_la-'+name+'.o')
            before=exec_sections(a.baseline_build.resolve()/relative)
            after=exec_sections(a.candidate_build.resolve()/relative)
            check[name+'_executable_sections_and_relocations_identical']=before==after
            check[name+'_source_unchanged']=sha(snapshots['baseline']/'src'/(name+'.c'))==sha(snapshots['candidate']/'src'/(name+'.c'))
            report['unchanged_code'][name]={'baseline':before,'candidate':after}
    except (KeyError,OSError,ValueError,subprocess.CalledProcessError) as exc:
        report['errors'].append(str(exc))
    report['status']='PASS' if report['checks'] and all(report['checks'].values()) and not report['errors'] else 'FAIL'
    (a.results/'benchmark-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    for key,value in report['checks'].items():
        print('PASS' if value else 'FAIL',key)
    for error in report['errors']:
        print('FAIL',error)
    print(report['status'],'canonical benchmark preparation')
    return report['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
