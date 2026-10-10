#!/usr/bin/env python3
"""Run an independent real-world recording corpus through the P10 composite.

Design 10.5 requires release qualification to include material that the project
did not generate. This driver takes commercial DSD releases, reduces each to a
fixed excerpt in the DSD domain, and pushes it through the real CLI effect
graph: native DSD input -> the planner's automatic reconstruction at the
profile working rate -> one composite `pcmdsd` at the native rate.

The composite is unqualified, so the graph must be exercised with the
uninstalled candidate executable; the release binary refuses it by design.

What is measured per source: whether the encoder admitted the material or
rejected it under the section 7.2 envelope; whether the output frame count is
exactly the requested duration; the 28-bit window population over the encoded
bitstream; and whether reconstructing the output reproduces the source excerpt's
level, which is the regression for the extra 6.0206 dB loss of risk R7a.

Bitstream statistics come from `dsd_windows.py`, which must pass its own
`--self-check` against `reference/verify.decode_dsf` first.

This driver measures. It does not decide whether a gate is discharged.

usage:
  corpus_realworld.py --sox SOX --candidate CAND --sources FILE --results DIR
                      [--seconds N] [--offset N] [--gain DB] [--stage-only]

`--sources` is a JSON list of {path, native, genre, release}. Paths are read
but never recorded; only the basename, release and genre are kept, so the
evidence carries no local filesystem layout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import dsd_windows

WORKING = {2822400: 88200, 5644800: 176400, 11289600: 176400}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


def levels(sox: Path, path: Path) -> dict:
    cp = subprocess.run([str(sox), str(path), '-n', 'stats'],
                        capture_output=True, text=True)
    out = {}
    for line in cp.stderr.splitlines():
        field = line.split()
        if line.startswith('Pk lev dB'):
            out['peak_db'] = float(field[3])
        elif line.startswith('RMS lev dB'):
            out['rms_db'] = float(field[3])
    return out


def stage(sox: Path, source: Path, dest: Path, native: int, offset: int, seconds: int):
    """Cut the excerpt in the DSD domain: no reconstruction, exact frames."""
    return subprocess.run([str(sox), '--dsd-layout-loss', 'warn', str(source),
                           '-r', str(native), str(dest),
                           'trim', str(offset), str(seconds)],
                          capture_output=True, text=True)


def run_one(args, item, work: Path) -> dict:
    source, native = Path(item['path']), int(item['native'])
    working = WORKING[native]
    excerpt = work / 'excerpt.dsf'
    encoded, src_pcm, out_pcm = work / 'encoded.dsf', work / 'source.wav', work / 'output.wav'
    for f in (excerpt, encoded, src_pcm, out_pcm):
        f.unlink(missing_ok=True)
    row = dict(source=source.name, release=item.get('release'), genre=item.get('genre'),
               native_hz=native, working_hz=working, source_bytes=source.stat().st_size,
               excerpt_offset_s=args.offset, excerpt_seconds=args.seconds,
               explicit_gain_db=float(args.gain) if args.gain else 0.0)
    started = time.time()
    cut = stage(args.sox, source, excerpt, native, args.offset, args.seconds)
    if cut.returncode != 0:
        row.update(staged=False, stage_stderr_tail=cut.stderr[-400:])
        return row
    row.update(staged=True, excerpt_sha256=sha256(excerpt),
               excerpt_bytes=excerpt.stat().st_size)

    # The explicit trim keeps the planner's reconstruction ahead of the
    # composite: pcmdsd directly after native DSD input is refused by the P05
    # preflight. It also pins the encoded length exactly.
    effects = ['trim', '0', str(args.seconds)]
    if args.gain:
        effects += ['gain', str(args.gain)]
    cp = subprocess.run([str(args.candidate), '--dsd-layout-loss', 'warn', str(excerpt),
                         '-r', str(native), str(encoded)] + effects + ['pcmdsd', str(native)],
                        capture_output=True, text=True)
    row.update(encode_exit=cp.returncode, encode_stderr_tail=cp.stderr[-500:],
               admitted=cp.returncode == 0 and encoded.exists())
    if not row['admitted']:
        row['seconds_elapsed'] = round(time.time() - started, 1)
        return row

    reconstruct = ['dsdpcm', '-l', 'preserve', str(working)]
    a = subprocess.run([str(args.sox), '--dsd-layout-loss', 'warn', str(excerpt),
                        '-b', '32', '-e', 'signed-integer', str(src_pcm)] + reconstruct
                       + (['gain', str(args.gain)] if args.gain else []),
                       capture_output=True, text=True)
    b = subprocess.run([str(args.sox), '--dsd-layout-loss', 'warn', str(encoded),
                        '-b', '32', '-e', 'signed-integer', str(out_pcm)] + reconstruct,
                       capture_output=True, text=True)
    if a.returncode == 0 and b.returncode == 0:
        before, after = levels(args.sox, src_pcm), levels(args.sox, out_pcm)
        row.update(source_excerpt_level=before, remodulated_level=after)
        if 'peak_db' in before and 'peak_db' in after:
            row['peak_delta_db'] = round(after['peak_db'] - before['peak_db'], 3)
            row['rms_delta_db'] = round(after['rms_db'] - before['rms_db'], 3)
    else:
        row['level_check_error'] = dict(source_exit=a.returncode, output_exit=b.returncode,
                                        stderr=(a.stderr or b.stderr)[-300:])

    decoded = dsd_windows.dsf_channel_bits(encoded.read_bytes())
    row.update(output_bytes=encoded.stat().st_size, output_channels=decoded['channels'],
               output_rate=decoded['rate'], output_frames=decoded['frames'],
               expected_frames=args.seconds * native,
               frames_exact=decoded['frames'] == args.seconds * native)
    per = []
    for channel, bits in enumerate(decoded['bits']):
        low, high, total = dsd_windows.window_ones(bits)
        per.append(dict(channel=channel, windows=total, min_ones=low, max_ones=high,
                        ones_fraction=round(float(bits.mean()), 6)))
    row.update(per_channel=per,
               min_ones28=min(c['min_ones'] for c in per),
               max_ones28=max(c['max_ones'] for c in per),
               windows28=sum(c['windows'] for c in per))
    row['population_within_4_24'] = row['min_ones28'] >= 4 and row['max_ones28'] <= 24
    row['seconds_elapsed'] = round(time.time() - started, 1)
    for f in (excerpt, encoded, src_pcm, out_pcm):
        f.unlink(missing_ok=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--sources', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--seconds', type=int, default=120)
    ap.add_argument('--offset', type=int, default=30)
    ap.add_argument('--gain', default=None,
                    help='explicit PCM attenuation in dB applied before the composite')
    ap.add_argument('--gain-ladder', default=None,
                    help='comma-separated attenuations in dB, tried in order until the '
                         'encoder admits the excerpt. The reported minimum attenuation is '
                         'only the value needed at the first overload, where the encoder '
                         'stops, so a single pass cannot establish what the whole excerpt '
                         'needs; the ladder measures that directly.')
    a = ap.parse_args()
    a.results.mkdir(parents=True, exist_ok=True)
    work = a.results / 'work'
    work.mkdir(exist_ok=True)
    rows = []
    ladder = [s.strip() for s in a.gain_ladder.split(',')] if a.gain_ladder else None
    for item in json.loads(a.sources.read_text()):
        if ladder:
            attempts = []
            for step in ladder:
                a.gain = None if float(step) == 0 else step
                row = run_one(a, item, work)
                attempts.append(dict(gain_db=float(step), admitted=bool(row.get('admitted')),
                                     stderr_tail=row.get('encode_stderr_tail')))
                if row.get('admitted'):
                    break
            row['ladder_attempts'] = attempts
            row['admitting_gain_db'] = (attempts[-1]['gain_db']
                                        if attempts[-1]['admitted'] else None)
            row['ladder_exhausted'] = not attempts[-1]['admitted']
        else:
            row = run_one(a, item, work)
        rows.append(row)
        print(row['source'][:48], row['native_hz'],
              'admitted' if row.get('admitted') else 'rejected',
              ('at %s dB' % row['admitting_gain_db']) if ladder and row.get('admitted') else '',
              flush=True)
    name = ('corpus-ladder.json' if ladder else
            'corpus-attenuated.json' if a.gain else 'corpus-unity.json')
    (a.results / name).write_text(json.dumps(rows, indent=1, sort_keys=True))
    for leftover in work.iterdir():
        leftover.unlink()
    work.rmdir()
    print('wrote', a.results / name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
