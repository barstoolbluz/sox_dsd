#!/usr/bin/env python3
"""Supplemental Linux/x86-64 native build when Autotools is unavailable.

Compiles the unchanged unconditional libsox source lists from src/Makefile.am.
Optional codec/device libraries and OpenMP are disabled. This is not a substitute
for qualification of the project's Autotools/CMake build systems. All compile and
link commands, source identities, host probes and compiler version are retained.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import tempfile

BASE_FLAGS = ['-O3', '-g', '-fno-fast-math', '-ffp-contract=off',
              '-frounding-math', '-fno-lto', '-fno-strict-aliasing']
ISA_FLAGS = {
    'sse2': ['-msse2', '-mno-avx'],
    'avx1': ['-mavx', '-mno-avx2', '-mno-fma'],
    'avx2': ['-mavx2', '-mno-fma'],
    'avx512': ['-mavx512f', '-mno-avx512dq', '-mno-avx512bw',
               '-mno-avx512vl', '-mno-fma'],
}
HEADERS = ('byteswap.h fcntl.h fenv.h glob.h inttypes.h malloc.h stdlib.h stdint.h string.h '
           'strings.h sys/ioctl.h sys/select.h sys/stat.h sys/timeb.h '
           'sys/time.h sys/types.h sys/utsname.h sys/wait.h termios.h unistd.h').split()
FUNCTIONS = {
    'aligned_alloc': 'stdlib.h', 'execvp': 'unistd.h', 'fmemopen': 'stdio.h',
    'fork': 'unistd.h', 'fseeko': 'stdio.h', 'getenv': 'stdlib.h',
    'gettimeofday': 'sys/time.h', 'lrint': 'math.h', 'mkstemp': 'stdlib.h',
    'pipe': 'unistd.h', 'popen': 'stdio.h', 'posix_fadvise': 'fcntl.h',
    'posix_memalign': 'stdlib.h', 'setenv': 'stdlib.h', 'sigaction': 'signal.h',
    'strcasecmp': 'strings.h', 'strdup': 'string.h', 'vsnprintf': 'stdio.h',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_archive(run, archive, objects):
    # ar rcs updates existing members but does not remove omitted members.
    # A fresh archive also leaves the previous usable result intact on failure.
    with tempfile.TemporaryDirectory(prefix='sdm-archive-', dir=archive.parent) as directory:
        temporary = Path(directory) / archive.name
        result = run(['ar', 'rcs', temporary, *objects], 'archive')
        if result['returncode'] == 0:
            temporary.replace(archive)
        return result


def library_sources(source):
    text = (source / 'src/Makefile.am').read_text().replace('\\\n', ' ')
    depth = 0
    result = []
    for line in text.splitlines():
        if re.match(r'^if\s', line):
            depth += 1
        elif re.match(r'^endif\b', line):
            depth -= 1
        elif depth == 0:
            match = re.match(r'^libsox_ng_la_SOURCES\s*\+?=\s*(.*)', line)
            if match:
                result += [x for x in match.group(1).split() if x.endswith('.c')]
    if not {'sdm.c', 'pcmdsd.c', 'dsf.c', 'wav.c'} <= set(result):
        raise ValueError('unconditional Makefile.am source lists missing required modules')
    if len(result) != len(set(result)):
        raise ValueError('duplicate native source')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--extra-cflags', default='')
    parser.add_argument('--only', choices=['all', 'kernels'], default='all')
    parser.add_argument('--test', action='append', default=[])
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('this supplemental build is explicitly scoped to Linux/x86-64')
    source, build = args.source.resolve(), args.build.resolve()
    build.mkdir(parents=True, exist_ok=True)
    obj = build / 'obj'
    obj.mkdir(exist_ok=True)
    report = {'schema': 'sdm-register/native-build/1', 'source': str(source),
              'build': str(build), 'scope': __doc__, 'platform': platform.platform(),
              'compiler': subprocess.check_output([args.cc, '--version'], text=True),
              'commands': [], 'probes': {}, 'source_sha256': {},
              'dependency_sha256': {}, 'test_source_sha256': {}, 'errors': []}
    for directory in ('src', 'libgsm'):
        for dependency in sorted((source/directory).glob('*.h')):
            report['dependency_sha256'][str(dependency.relative_to(source))] = sha(dependency)
        makefile = source/directory/'Makefile.am'
        report['dependency_sha256'][str(makefile.relative_to(source))] = sha(makefile)
    flags = BASE_FLAGS + shlex.split(args.extra_cflags)

    def run(argv, key):
        proc = subprocess.run(list(map(str, argv)), text=True, capture_output=True)
        return {'key': key, 'argv': list(map(str, argv)), 'returncode': proc.returncode,
                'stdout': proc.stdout, 'stderr': proc.stderr}

    header = ['/* Linux native qualification configuration, generated by build_native.py. */',
              '#ifndef SOXCONFIG_H', '#define SOXCONFIG_H',
              '#define PACKAGE_VERSION "1.0.2"', '#define VERSION "1.0.2"',
              '#define SOX_DSD_UPSTREAM_BASE "14.8.1"', '#define _FILE_OFFSET_BITS 64']
    for name in HEADERS:
        probe = build / 'probe.c'
        probe.write_text(f'#include <{name}>\nint main(void) {{ return 0; }}\n')
        result = run([args.cc, '-Werror', probe, '-o', build/'probe'], name)
        report['probes'][name] = result
        if result['returncode'] == 0:
            header.append('#define HAVE_' + re.sub('[^A-Za-z0-9]', '_', name).upper() + ' 1')
    for name, include in FUNCTIONS.items():
        probe = build / 'probe.c'
        probe.write_text(f'#define _GNU_SOURCE\n#include <{include}>\n'
                         f'int main(void) {{ return &{name} == 0; }}\n')
        result = run([args.cc, '-Werror', probe, '-o', build/'probe', '-lm'], name)
        report['probes'][name] = result
        if result['returncode'] == 0:
            header.append('#define HAVE_' + name.upper() + ' 1')
    for name, isa in ISA_FLAGS.items():
        probe = build/'probe.c'
        probe.write_text('#include <immintrin.h>\nint main(void){return 0;}\n')
        result = run([args.cc, *flags, *isa, '-Werror', probe, '-o', build/'probe'], name)
        report['probes'][name] = result
        if result['returncode']:
            raise RuntimeError(f'compiler cannot isolate {name}: {result}')
        header.append('#define HAVE_DSD_' + name.upper() + ' 1')
    header += ['#define HAVE_STRUCT_STAT_ST_BLOCKS 1', '#endif', '']
    (build/'soxconfig.h').write_text('\n'.join(header))
    (build/'src').mkdir(exist_ok=True)
    (build/'src/soxconfig.h').write_text('\n'.join(header))
    report['config_sha256'] = sha(build/'soxconfig.h')
    sources = library_sources(source) if args.only == 'all' else [
        'sdm.c', 'dsd_dispatch.c', 'dsd_kernels_scalar.c']
    sources += ['dsd_kernels_' + name + '.c' for name in ISA_FLAGS]
    common = [args.cc, *flags, '-I'+str(build), '-I'+str(obj),
              '-I'+str(source/'src'), '-DHAVE_CONFIG_H']
    commands = []
    objects = []
    for name in sources:
        tier = name.removeprefix('dsd_kernels_').removesuffix('.c')
        report['source_sha256']['src/'+name] = sha(source/'src'/name)
        commands.append(([*common, *ISA_FLAGS.get(tier, []), '-c', source/'src'/name,
                          '-o', obj/(Path(name).stem+'.o')], name))
        objects.append(obj/(Path(name).stem+'.o'))
    if args.only == 'all':
        gsm_make = (source/'libgsm/Makefile.am').read_text().replace('\\\n', ' ')
        gsm_sources = re.search(r'^libgsm_la_SOURCES\s*=\s*(.*)', gsm_make, re.M).group(1).split()
        for name in gsm_sources:
            if not name.endswith('.c'):
                continue
            report['source_sha256']['libgsm/'+name] = sha(source/'libgsm'/name)
            target = obj/('gsm_'+Path(name).stem+'.o')
            objects.append(target)
            commands.append(([*common, '-DSASR', '-DFAST', '-DWAV49', '-c',
                              source/'libgsm'/name, '-o', target], 'libgsm/'+name))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(lambda command: run(*command), commands):
            report['commands'].append(result)
            if result['returncode']:
                report['errors'].append(result['key'])
                print(result['key'] + ': ' + result['stderr'], file=sys.stderr)
    archive = build/'libsox_native.a'
    if not report['errors']:
        result = build_archive(run, archive, objects)
        report['commands'].append(result)
        if result['returncode']:
            report['errors'].append('archive')
    if not report['errors'] and args.only == 'all':
        result = run([*common, source/'src/sox_ng.c', archive, '-lm', '-ldl', '-o', build/'sox'], 'sox')
        report['commands'].append(result)
        if result['returncode']:
            report['errors'].append('sox')
            print(result['stderr'], file=sys.stderr)
    if not report['errors']:
        for test in args.test:
            unit = Path(test)
            if not unit.is_absolute():
                unit = source/'tests/dsd'/unit
            report['test_source_sha256'][str(unit)] = sha(unit)
            result = run([*common, unit, archive, '-lm', '-ldl', '-o', build/unit.stem], unit.stem)
            report['commands'].append(result)
            if result['returncode']:
                report['errors'].append(unit.stem)
                print(result['stderr'], file=sys.stderr)
    # A header edited while parallel compiler jobs are running could produce a
    # mixed library. Refuse to certify such a build even if linking succeeds.
    for name, digest in {**report['source_sha256'], **report['dependency_sha256']}.items():
        if sha(source/name) != digest:
            report['errors'].append('source changed during build: '+name)
    for name, digest in report['test_source_sha256'].items():
        if sha(Path(name)) != digest:
            report['errors'].append('test source changed during build: '+name)
    report['status'] = 'FAIL' if report['errors'] else 'PASS'
    (build/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['errors']:
        print('PASS native build:', build)
    return bool(report['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
