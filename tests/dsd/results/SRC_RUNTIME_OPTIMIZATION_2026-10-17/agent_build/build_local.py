#!/usr/bin/env python3
"""Reproduce a static SoX DSP test build without autotools, on Linux x86_64.

Uses the repository's retained generated GNU/Linux configuration and source
lists. This is development build support, not a replacement for configure.
External codec libraries are absent; all bundled codecs and isolated DSD ISA
kernels are built. No source file is generated or changed inside the source tree.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_list(path, name, definitions):
    text = path.read_text().replace('\\\n', ' ')
    active = [True]
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('if '):
            active.append(active[-1] and line[3:].strip() in definitions)
        elif line == 'else':
            active[-1] = active[-2] and not active[-1]
        elif line == 'endif':
            active.pop()
        elif all(active):
            match = re.match(re.escape(name) + r'\s*(\+?=)\s*(.*)', line)
            if match:
                if match[1] == '=':
                    entries = []
                entries += [part for part in match[2].split() if part.endswith('.c')]
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--build', type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    ap.add_argument('--cflags', default='-O2 -g -ffp-contract=off')
    ap.add_argument('--extra-cflags', default='')
    ap.add_argument('--probes', default='p07,p07_reference,p11,p12_bounds,p13,p14,decode_optimization,p15_instrument,p15_src_stage_export,src_optimization,io,plan,decode,decode_faults,dop_capacity')
    args = ap.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        ap.error('This retained configuration is restricted to Linux x86_64.')
    source, build = args.source.resolve(), args.build.resolve()
    build.mkdir(parents=True, exist_ok=True)
    (build/'obj').mkdir(exist_ok=True)
    (build/'src').mkdir(exist_ok=True)
    (build/'test').mkdir(exist_ok=True)
    retained = source/'tests/dsd/results/P01/build/soxconfig.h'
    config = retained.read_text()
    isa_flags = {
        'sse2': '-msse2 -mno-avx -ffp-contract=off -fno-lto',
        'avx1': '-mavx -mno-avx2 -mno-fma -ffp-contract=off -fno-lto',
        'avx2': '-mavx2 -mno-fma -ffp-contract=off -fno-lto',
        'avx512': '-mavx512f -mno-avx512dq -mno-avx512bw -mno-avx512vl -mno-fma -ffp-contract=off -fno-lto',
    }
    config += '\n/* Isolated DSD kernels; flags copied from configure.ac. */\n'
    config += ''.join(f'#define HAVE_DSD_{isa.upper()} 1\n' for isa in isa_flags)
    config_path = build/'src/soxconfig.h'
    if not config_path.exists() or config_path.read_text() != config:
        config_path.write_text(config)
    definitions = set(re.findall(r'^#define (\w+) 1$', config, re.MULTILINE))
    definitions.add('STATIC_LIBSOX_ONLY')
    sources = [(source/'src'/name, []) for name in source_list(source/'src/Makefile.am', 'libsox_ng_la_SOURCES', definitions)]
    sources += [(source/'src'/name, []) for name in source_list(source/'src/optional-fmts.am', 'libsox_ng_la_SOURCES', definitions)]
    for dirname, libname in [('libgsm','libgsm'),('lpc10','liblpc10'),('libdolbyb','libdolbyb'),('libebur128','libebur128')]:
        flags = ['-DSASR', '-DFAST', '-DWAV49'] if dirname == 'libgsm' else []
        sources += [(source/dirname/name, flags) for name in source_list(source/dirname/'Makefile.am', libname+'_la_SOURCES', definitions)]
    sources += [(source/'src'/f'dsd_kernels_{isa}.c', shlex.split(flags)) for isa, flags in isa_flags.items()]
    tracked = {src for src,_ in sources}
    tracked.update(source/'tests/dsd'/f'test_{name}.c' for name in filter(None,args.probes.split(',')))
    tracked.update((source/'src/sox_ng.c',source/'src/sox_sample_test.c'))
    tracked.update(path for folder in ('src','libgsm','lpc10','libebur128','libdolbyb')
                   for path in (source/folder).glob('*.h'))
    references = sorted((source/'tests/dsd/reference/src_optimization').glob('*'))
    tracked.update(path for path in references if path.is_file())
    before = {str(path.relative_to(source)):digest(path) for path in sorted(tracked)}
    (build/'build-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
    flags = shlex.split(args.cflags) + shlex.split(args.extra_cflags)
    include = ['-I'+str(build/'src'), '-I'+str(source/'src')]
    commands = []
    def run(command):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            raise RuntimeError(shlex.join(command)+'\n'+result.stdout)
        return result.stdout
    def compile_one(item):
        src, special = item
        obj = build/'obj'/(str(src.relative_to(source)).replace('/', '__')+'.o')
        command = [args.cc, *flags, *include, *special, '-c', str(src), '-o', str(obj)]
        commands.append({'directory':str(build), 'file':str(src), 'arguments':command})
        log = run(command)
        return obj, log
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(compile_one, sources))
    objects = [str(obj) for obj, _ in results]
    (build/'build.log').write_text(''.join(log for _, log in results))
    library = build/'libsox_ng.a'
    if library.exists():
        library.unlink()
    run(['ar','rcs',str(library),*objects])
    def link(program, inputs, extra=()):
        run([args.cc,*flags,*include,*inputs,str(library),'-lm',*extra,'-o',str(program)])
    cli_object, cli_log = compile_one((source/'src/sox_ng.c', []))
    with (build/'build.log').open('a') as log:
        log.write(cli_log)
    link(build/'sox_ng',[str(cli_object)])
    # Same link-only sample profiling technique as test/Makefile.am.
    link(build/'sox_dsd_profile_linkonly',[str(cli_object)],['-pg'])
    link(build/'sox_sample_test',[str(source/'src/sox_sample_test.c')])
    for name in filter(None, args.probes.split(',')):
        extra = ['-DDSD_OPTIMIZATION=1'] if name == 'decode_optimization' else []
        link(build/'test'/f'dsd_test_{name}',[str(source/'tests/dsd'/f'test_{name}.c')],extra)
    changed = [name for name,expected in before.items() if digest(source/name)!=expected]
    if changed:
        raise RuntimeError('Sources changed during compilation; repeat the build: '+', '.join(changed))
    commands.sort(key=lambda entry: entry['file'])
    (build/'compile_commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    record = {
        'scope':'Development GNU/Linux x86_64 static build using retained generated configuration; no external codec dependencies; not configure qualification.',
        'source':str(source), 'build':str(build), 'compiler':run([args.cc,'--version']).splitlines()[0],
        'cflags':flags, 'isa_flags':isa_flags,
        'retained_config':str(retained.relative_to(source)), 'retained_config_sha256':digest(retained),
        'build_config_sha256':digest(config_path),
        'source_sha256':{str(src.relative_to(source)):digest(src) for src,_ in sources},
        'header_sha256':{str(path.relative_to(source)):digest(path) for folder in
            ('src','libgsm','lpc10','libebur128','libdolbyb') for path in sorted((source/folder).glob('*.h'))},
        'probe_source_sha256':{name:digest(source/'tests/dsd'/f'test_{name}.c') for name in filter(None,args.probes.split(','))},
        'probe_reference_sha256':{str(path.relative_to(source)):digest(path) for path in references if path.is_file()},
        'sox_sha256':digest(build/'sox_ng'), 'library_sha256':digest(library),
        'profile_executable':str(build/'sox_dsd_profile_linkonly'),
        'profile_sha256':digest(build/'sox_dsd_profile_linkonly'),
        'profile_mode':'-pg applied at link only; CLI and library objects not instrumented',
        'cli_source_sha256':digest(source/'src/sox_ng.c'),
        'probes':list(filter(None,args.probes.split(','))),
    }
    (build/'build-record.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'sox':str(build/'sox_ng'), 'library':str(library),'objects':len(objects),'build_record':str(build/'build-record.json')}))


if __name__ == '__main__':
    main()
