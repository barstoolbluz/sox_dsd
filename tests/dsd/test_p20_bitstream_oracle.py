#!/usr/bin/env python3
"""Independent packed-bit oracle for P20: checks the actual overlapping 28-bit
population (7..22) and constant-run gates, not the SDM's monitor counters.
This is a short guarded exercise, NOT a replacement for sustained qualification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/dsd'))
import p10_corpus
import p17_qualify_guards as p17


def independently_assess(bits: np.ndarray, frames: int) -> dict:
    if bits.size < frames:
        raise AssertionError('Truncated native packed output')
    bits = bits[:frames]
    minimum, maximum, windows, longest = 29, -1, 0, 0
    prior = np.empty(0, dtype=np.uint8)
    last_bit, last_run = None, 0
    for start in range(0, frames, 4000000):
        block = bits[start:start+4000000]
        joined = np.concatenate((prior, block))
        if joined.size >= 28:
            cumulative = np.cumsum(joined, dtype=np.int32)
            populations = cumulative[27:].copy()
            populations[1:] -= cumulative[:-28]
            minimum = min(minimum, int(populations.min()))
            maximum = max(maximum, int(populations.max()))
            windows += populations.size
        prior = joined[-27:].copy()
        changes = np.flatnonzero(block[1:] != block[:-1]) + 1
        parts = np.diff(np.r_[0, changes, block.size])
        if last_bit == int(block[0]):
            parts[0] += last_run
        longest = max(longest, int(parts.max()))
        last_run = int(parts[-1])
        last_bit = int(block[-1])
    return dict(min_ones28=minimum, max_ones28=maximum,
                windows28=windows, longest_run=longest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit', type=Path, default=ROOT/'test/dsd_test_p10')
    ap.add_argument('--results', type=Path, required=True)
    a = ap.parse_args()
    cases = [c for c in p17.configs('holdout') if c['native_hz'] == 22579200]
    rows = []
    for index in (1, 16, 17, 21):
        c = cases[index]
        data, stamp = p10_corpus.stimulus(c)
        with tempfile.TemporaryDirectory(prefix='p20-oracle-') as td:
            directory = Path(td)
            src = directory/'source.f64le'
            packed = directory/'output.dsd'
            report = directory/'report.json'
            src.write_bytes(data)
            cmd = [str(a.unit.resolve()), '--render', str(c['source_hz']),
                   '22579200', 'encode.mastering.v2.dsd512', '.5', 'guarded',
                   str(src), str(packed), str(report)]
            proc = subprocess.run(cmd, capture_output=True,
                                  env={**os.environ, 'LSX_DSD_SDM_KERNEL': 'scalar'},
                                  timeout=180)
            if proc.returncode != 0:
                raise RuntimeError(f'{c["name"]} rendering failed: {proc.stderr!r}')
            claimed = json.loads(report.read_text())
            native = int(claimed['committed_native_frames'])
            # MSB first, as emitted by the P10 private encoder renderer.
            emitted = np.unpackbits(np.frombuffer(packed.read_bytes(), dtype='u1'),
                                    bitorder='big')
            independent = independently_assess(emitted, native)
            assert all(independent[k] == claimed[k] for k in independent), (c['name'], independent, claimed)
            # Inherited holdout gate is 4..24; 7..22 applies to the nominal sustained soak.
            assert 4 <= independent['min_ones28'] <= independent['max_ones28'] <= 24
            expected = (stamp['frames'] * 22579200 + c['source_hz']//2)//c['source_hz']
            assert native == expected
            rows.append(dict(case=c['name'], native_frames=native,
                             verified_monitor=independent,
                             sustained_nominal_population_gate=(7 <= independent['min_ones28']
                                 <= independent['max_ones28'] <= 22)))
            print('ORACLE PASS', c['name'], independent, flush=True)
    body = dict(schema='P20/independent-packed-bit-oracle/1',
                profile='encode.mastering.v2.dsd512', qualified=False, cases=rows)
    a.results.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, sort_keys=True, indent=2)+'\n'
    if a.results.exists() and a.results.read_text()!=text:
        raise RuntimeError('Refusing to replace conflicting oracle receipt')
    a.results.write_text(text)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
