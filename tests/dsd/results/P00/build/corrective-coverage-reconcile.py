#!/usr/bin/env python3
"""Reconcile the executed P00 generic gate; evidence only, not a production test change."""
import json
import pathlib
import re
import shutil
import subprocess

root = pathlib.Path(__file__).resolve().parents[5]
build = root / 'tests/dsd/results/P00/build'
logfile = build / 'corrective-check.log'
log = logfile.read_text(errors='replace').splitlines()
observed = [(n, re.fullmatch(r'([^:]+): (OK|VOID|FAIL|ABRT|ASAN|SEGV|EXEC|FPE|ILL|LOOP|SUCC)', line))
            for n, line in enumerate(log, start=1)]
checks = [(line_no, m.group(1), m.group(2)) for line_no, m in observed if m]
skips = [(n, m) for n, line in enumerate(log, 1) if (m := re.fullmatch(r'Skipped: (.+?)\s*', line))]
assert len(skips) == 1, f'Expected one format-skip summary, found {skips}'
assert len([x for x in checks if x[2] == 'VOID']) == 8, 'Unexpected VOID count'
assert len([x for x in checks if x[2] == 'OK']) == 73, 'Unexpected OK count'
assert not [x for x in checks if x[2] not in ('OK', 'VOID')], 'Other legacy regression results present'
assert (build / 'corrective-check.exit').read_text().strip() == '0', 'generic exit changed'
format_order = skips[0][1].group(1).split()
assert len(format_order) == 7, 'Unexpected count of skipped format groups'
reason = {
    'BUG-305': ('AMR format absent from configured SoX', 'test/BUG-305/run'),
    'BUG-327': ('MP3 decoding format absent from configured SoX', 'test/BUG-327/run'),
    'BUG-334': ('FLAC writable format absent from configured SoX', 'test/BUG-334/run'),
    'BUG-libsndfile-float-level': ('w64 and caf read/write float formats unavailable', 'test/BUG-libsndfile-float-level/run'),
    'ebu-r-128': ('bc executable absent (EBUR128 effect itself is configured)', 'test/ebu-r-128/run'),
    'equiv-chorus-flanger': ('bc executable absent', 'test/equiv-chorus-flanger/run'),
    'ffmpeg-command-execution': ('Wine absent and required Windows SoX binary not built', 'test/ffmpeg-command-execution/run'),
    'playlist-with-pipe': ('Wine absent and required Windows SoX binary not built', 'test/playlist-with-pipe/run'),
}
assert {name for _, name, status in checks if status == 'VOID'} == set(reason)
formats = []
for name in format_order:
    command = ['src/sox_ng', '--help-format', name]
    p = subprocess.run([str(root/'src/sox_ng'), '--help-format', name], capture_output=True, text=True, cwd=root)
    first_line = (p.stdout + p.stderr).splitlines()[0]
    assert f'Cannot find a format called `{name}\'' in first_line, f'Unexpected {name} status: {first_line}'
    formats.append({'name':name, 'status':'unrun', 'log_line':skips[0][0],
                    'preflight':'format not available on configured executable',
                    'probe_command':command, 'probe_exit':p.returncode,
                    'probe_first_line':first_line})
result = {
    'schema': 'dsd-generic-coverage-reconciliation/1',
    'gate_command': 'make check',
    'gate_log': 'tests/dsd/results/P00/build/corrective-check.log',
    'gate_exit': 0,
    'assertion_coverage': 'incomplete',
    'qualification': 'nonzero skipped/unrun cases are not passing tests, notwithstanding exit code zero',
    'regression_cases': {'ok_executed':len([x for x in checks if x[2]=='OK']),
                         'void_not_executed':len(reason), 'unexpected':0},
    'skipped_format_groups':formats,
    'void_regressions': [{'name':name, 'status':'unrun', 'log_line':n,
                          'preflight_blocker':reason[name][0], 'preflight_source':reason[name][1]}
                         for n,name,status in checks if status=='VOID'],
    'optional_tools': {'bc':shutil.which('bc'), 'wine':shutil.which('wine')},
    'provenance_limit': 'Source commit is declared in supplied docs; the archive has no Git metadata to authenticate it.',
}
path = build / 'corrective-generic-coverage.json'
path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(f'Generic suite: exit={result["gate_exit"]}, assertions=INCOMPLETE, '
      f'OK={result["regression_cases"]["ok_executed"]}, '
      f'VOID={result["regression_cases"]["void_not_executed"]}, '
      f'format_groups_unrun={len(formats)}, output={path}')
