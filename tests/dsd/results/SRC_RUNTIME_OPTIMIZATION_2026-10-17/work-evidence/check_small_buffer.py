#!/usr/bin/env python3
"""Record the inherited small-buffer truncation without relaxing validation."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sox_ng/tests/dsd'))
from bench_src_optimization import invocation, measure, sha256

dest = ROOT / 'work-evidence/small-buffer-diagnosis'
dest.mkdir(exist_ok=False)
fixture = ROOT / 'work-evidence/final-controls/pcm_buffer32_48000_44100/input.s32'
os.sched_setaffinity(0, {0})
case = dict(kind='pcm', input_hz=48000, output_hz=44100, channels=2,
            frames=480000, seconds=10.0, quality='-v', fir_kernel='auto')
overrides = dict(SOX_OPTS='', LC_ALL='C', OMP_NUM_THREADS='1', SOX_DSD_KERNEL_FIR='auto')
result = dict(schema='src-optimization/small-buffer-diagnosis/1',
    purpose='Check frozen and candidate output length after the strict control preflight failed; no performance claim.',
    fixture_sha256=sha256(fixture), fixture_bytes=fixture.stat().st_size,
    expected_output_frames=441000, expected_output_bytes=3528000, rows=[])
for buffer in (32, 64, 128, 256):
    case['buffer'] = buffer
    for name in ('baseline', 'candidate'):
        exe = ROOT / ('build-' + name) / 'sox_ng'
        label = f'buffer{buffer}-{name}'
        output = dest / (label + '.s32')
        command = invocation(exe, case, fixture, output)
        row = dict(buffer_bytes=buffer, variant=name, command=command,
                   executable_sha256=sha256(exe), env_overrides=overrides)
        row.update(measure(command, dest, overrides, 180,
                           dest/(label+'.stdout.txt'), dest/(label+'.stderr.txt')))
        row.update(output_bytes=output.stat().st_size,
                   output_sha256=sha256(output),
                   stderr=(dest/(label+'.stderr.txt')).read_text())
        row['correct_length'] = row['output_bytes'] == result['expected_output_bytes']
        result['rows'].append(row)
        print(json.dumps({k:row[k] for k in ('buffer_bytes','variant','exit','output_bytes','output_sha256','correct_length')}), flush=True)
result['same_output_by_buffer'] = {str(buffer):
    len({r['output_sha256'] for r in result['rows'] if r['buffer_bytes']==buffer})==1
    for buffer in (32,64,128,256)}
result['scope'] = 'Both builds preserve the observed behavior; a correct length is still required for any accepted throughput case.'
(dest/'diagnosis.json').write_text(json.dumps(result, indent=2)+'\n')
