"""Source-bound qualification execution context without inferred properties.

The measured process FENV entry/exit comes from the test-only, same-process
wrapper. It does not purport to be a per-sample FENV record or cross-ISA bit
identity. The normal production executable does not contain the wrapper.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess


def read_fenv(path):
    p=Path(path)
    if not p.is_file():raise AssertionError('actual CLI FENV process witness missing')
    try: j=json.loads(p.read_text())
    except Exception as e:raise AssertionError('invalid actual-process FENV witness') from e
    if (j.get('schema')!='sox-p08-inprocess-fenv/1' or
        j.get('entry_round')!='FE_TONEAREST' or
        j.get('exit_round')!='FE_TONEAREST' or
        j.get('sox_exit')!=0 or
        not isinstance(j.get('entry_exceptions'),int) or
        not isinstance(j.get('exit_exceptions'),int)):
        raise AssertionError('non-nearest or incomplete FENV process witness')
    return {'path':str(p),
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'schema':j['schema'],'entry_round':j['entry_round'],
            'exit_round':j['exit_round'],
            'entry_exceptions':j['entry_exceptions'],
            'exit_exceptions':j['exit_exceptions'],
            'sox_exit':j['sox_exit'],
            'observation_scope':'main process entry/exit, not individual DSP samples'}


def build_context(source):
    source=Path(source).resolve()
    makefile=source/'Makefile'
    if not makefile.is_file():raise AssertionError('configured Makefile absent')
    values={}
    text=makefile.read_text()
    for k in ('CC','CFLAGS','CPPFLAGS','LDFLAGS','host','host_cpu'):
        m=re.search(r'^'+re.escape(k)+r' = (.*)$',text,flags=re.M)
        if not m:raise AssertionError('missing configured '+k)
        values[k]=m.group(1)
    ver=subprocess.run([values['CC'].split()[0],'--version'],capture_output=True,text=True,timeout=10)
    if ver.returncode!=0:raise AssertionError('compiler identity unavailable')
    flags=[]
    if platform.system()=='Linux':
        try:
            line=next((x for x in Path('/proc/cpuinfo').read_text().splitlines()
                       if x.startswith('flags')),None)
            if line:flags=[x for x in line.split(':',1)[1].strip().split()
                           if x in {'sse2','sse4_1','sse4_2','avx','avx2','avx512f',
                                    'avx512bw','avx512dq','avx512vl','fma','f16c'}]
        except OSError:pass
    return {'configured_build':values,
        'configured_compiler_version':ver.stdout.splitlines()[0],
        'config_log_sha256':hashlib.sha256((source/'config.log').read_bytes()).hexdigest(),
        'platform_machine':platform.machine(), 'platform_system':platform.system(),
        'cpu_vector_features_observed':flags,
        'native_library_block_capacity':{'source_frames':256,'native_frames':512},
        'qualification_driver_flags':
            ['SOX_P08_ADMISSION_TEST_BUILD','SOX_P08_CANCEL_TEST_BUILD'],
        'thread_configuration':{'openmp_env':os.environ.get('OMP_NUM_THREADS'),
            'openblas_env':os.environ.get('OPENBLAS_NUM_THREADS'),
            'sox_thread_count':'not instrumented',
            'test_process_launch':'sequential per physical case'},
        'fenv_evidence':'real diagnostic-CLI main-process entry/exit per physical command;'
                        ' separate foundation tests exercise rejected rounding modes;'
                        ' no per-sample or per-worker fenv identity claimed'}
