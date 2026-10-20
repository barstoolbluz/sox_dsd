#!/usr/bin/env python3
"""Measure external PCM_AUDIO releases through the P10 candidate CLI graph.

Inventory: tests/dsd/results/P10_pcm_arm_material_2026-10-10/pcm-candidate-inventory.json
Sources JSON: [{"release": "<exact inventory release>", "path": "/host/first-track.flac",
                "track": "optional public track name"}, ...]

One remote read per source. All checking, partial lossless decode, transcoding,
retry and window analysis use temporary LOCAL copies, never the sshfs original.
No external recordings, absolute paths, or temporary path names enter results.
Prior results are atomic checkpoints; --resume explicitly reuses completed
source/rate rows when file metadata remains unchanged. The original commercial
recordings are not bundled with this software.

This is a measurement driver, not permission to promote unqualified profiles.
The full gate requires >=60 seconds and >=2 distinct admitted recordings per
native rate, two genres, and both PCM source clock families.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import dsd_windows

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / 'tests/dsd/results/P10_pcm_arm_material_2026-10-10/pcm-candidate-inventory.json'
RATES = (2822400, 5644800, 11289600)
WORKING = {2822400: 88200, 5644800: 176400, 11289600: 176400}
SCHEMA = 'P10/PCM_AUDIO-external-corpus/1'
PEAK_TOLERANCE_DB = .5
RMS_TOLERANCE_DB = .25
MIN_SECONDS = 60
RECORD_NAME = 'pcm-corpus.json'


class CorpusError(Exception):
    """Expected failure of a measurement or its source precondition."""


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as src:
        for chunk in iter(lambda: src.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def atomic_json(path: Path, data) -> None:
    # An interrupted run must not replace the last complete receipt.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=path.parent,
                                     prefix='.pcm-receipt-', delete=False) as out:
        temp = Path(out.name)
        try:
            json.dump(data, out, sort_keys=True, indent=2, allow_nan=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


def read_streaminfo(flac: Path) -> dict:
    """Read the FLAC STREAMINFO directly; never trust a declared sample rate."""
    with open(flac, 'rb') as f:
        if f.read(4) != b'fLaC':
            raise CorpusError('not a native FLAC bitstream')
        while True:
            tag = f.read(4)
            if len(tag) != 4:
                raise CorpusError('missing FLAC STREAMINFO')
            length = int.from_bytes(tag[1:], 'big')
            if (tag[0] & 127) == 0:
                if length != 34:
                    raise CorpusError('invalid FLAC STREAMINFO length')
                block = f.read(length)
                if len(block) != 34:
                    raise CorpusError('truncated FLAC STREAMINFO')
                fields = int.from_bytes(block[10:18], 'big')
                return dict(sample_rate_hz=(fields >> 44) & ((1 << 20) - 1),
                            channels=((fields >> 41) & 7) + 1,
                            bits_per_sample=((fields >> 36) & 31) + 1,
                            total_samples=fields & ((1 << 36) - 1),
                            streaminfo_md5=block[18:34].hex())
            # Avoid an unbounded read for large ID3-like metadata blocks.
            f.seek(length, os.SEEK_CUR)
            if tag[0] & 128:
                raise CorpusError('missing FLAC STREAMINFO')


def copy_remote_once(source: Path, target: Path) -> str:
    digest = hashlib.sha256()
    with open(source, 'rb') as inp, open(target, 'xb') as out:
        for block in iter(lambda: inp.read(4 << 20), b''):
            digest.update(block)
            out.write(block)
    return digest.hexdigest()


def check_inventory(source_info: dict, actual: dict) -> None:
    for name in ('sample_rate_hz', 'channels', 'bits_per_sample'):
        if source_info[name] != actual[name]:
            raise CorpusError('STREAMINFO mismatch in '+name)
    if source_info['first_track_streaminfo_md5'].lower() != actual['streaminfo_md5']:
        raise CorpusError('STREAMINFO MD5 mismatch with inventory')
    hz = source_info['sample_rate_hz']
    expected_family = '44100-family' if hz % 44100 == 0 else '48000-family'
    if hz not in (44100, 48000, 88200, 96000, 176400, 192000) or \
            source_info['clock_family'] != expected_family:
        raise CorpusError('invalid PCM sample rate or clock family in inventory')
    if actual['total_samples'] < 1:
        raise CorpusError('FLAC with missing sample count cannot support exact excerpt selection')


def commands(*argv, redact=(), timeout=None) -> subprocess.CompletedProcess:
    cp = subprocess.run([str(a) for a in argv], capture_output=True,
                        text=True, errors='replace', timeout=timeout)
    cp.stdout = sanitize(cp.stdout, redact)
    cp.stderr = sanitize(cp.stderr, redact)
    return cp


def sanitize(message: str, paths) -> str:
    for p in sorted((str(p) for p in paths if p), key=len, reverse=True):
        message = message.replace(p, '<local-file>')
    return message[-1000:]


def check_wav_excerpt(path: Path, rate: int, frames: int) -> dict:
    # Hash actual PCM bytes, not just the WAVE header/container.
    digest = hashlib.sha256()
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) != \
                (2, 3, rate, frames):
            raise CorpusError('FLAC excerpt is not exact 24-bit stereo PCM at declared rate/duration')
        remaining = frames
        while remaining:
            n = min(1 << 16, remaining)
            chunk = wav.readframes(n)
            if len(chunk) != n * 2 * 3:
                raise CorpusError('short WAVE excerpt read')
            digest.update(chunk)
            remaining -= n
        if wav.readframes(1):
            raise CorpusError('extra WAVE frames beyond declared count')
    return dict(excerpt_pcm_sha256=digest.hexdigest(), excerpt_wav_sha256=sha_file(path),
                excerpt_frames=frames, excerpt_bytes=path.stat().st_size)


def stats(sox: Path, pcm: Path, *, gain: float | None = None,
          dsd: bool = False, working: int = 0) -> dict:
    argv = [sox, '-D', '--dsd-layout-loss', 'warn', pcm, '-n']
    if dsd:
        argv += ['dsdpcm', '-l', 'sacd', str(working)]
    if gain is not None and gain != 0:
        argv += ['gain', str(gain)]
    argv += ['stats']
    cp = commands(*argv, redact=(pcm, sox))
    if cp.returncode:
        raise CorpusError('level measurement failed: ' + cp.stderr)
    result = {}
    for line in cp.stderr.splitlines():
        pieces = line.split()
        if line.startswith('Pk lev dB') and len(pieces) >= 4:
            result['peak_db'] = float(pieces[3])
        if line.startswith('RMS lev dB') and len(pieces) >= 4:
            result['rms_db'] = float(pieces[3])
    if set(result) != {'peak_db', 'rms_db'} or not all(math.isfinite(v) for v in result.values()):
        raise CorpusError('missing or non-finite source/output level')
    return result


def gains(text: str | None) -> list[float]:
    values = [0.]
    if text:
        try:
            values += [float(x) for x in text.split(',')]
        except ValueError as e:
            raise CorpusError('gain ladder must contain numeric dB values') from e
    if (not all(math.isfinite(x) and x <= 0 for x in values) or
            any(values[i] >= values[i-1] for i in range(1, len(values)))):
        raise CorpusError('gain ladder must be strictly decreasing negative dB, after unity')
    return values


def run_encode(candidate: Path, pcm: Path, dst: Path, native: int, gain: float) -> dict:
    dst.unlink(missing_ok=True)
    args = [candidate, '--dsd-mode', 'auto', '--dsd-layout-loss', 'warn', '-D',
            pcm, '-r', str(native), dst]
    if gain:
        args += ['gain', str(gain)]
    args += ['pcmdsd', str(native)]
    cp = commands(*args, redact=(candidate, pcm, dst))
    admitted = cp.returncode == 0 and dst.is_file()
    failed_as_overload = cp.returncode != 0 and 'interpolation overload' in cp.stderr
    attempt = dict(gain_db=gain, exit_code=cp.returncode, admitted=admitted,
                   overload_rejected=failed_as_overload,
                   output_left_on_failure=not admitted and dst.exists(),
                   diagnostic_tail=cp.stderr[-600:])
    if cp.returncode == 0 and not admitted:
        attempt['measurement_error'] = 'encoder exited successfully without an output container'
    if cp.returncode != 0 and not failed_as_overload:
        attempt['measurement_error'] = 'encoder failed for a reason other than interpolation overload'
    return attempt


def measure_native(sox: Path, candidate: Path, pcm: Path, native: int,
                   seconds: int, ladder: list[float], *, chunk_blocks: int) -> dict:
    dst = pcm.parent / 'candidate.dsf'
    attempts = []
    row = dict(native_hz=native, working_hz=WORKING[native],
               reconstructed_reference='sacd', source_domain='PCM_AUDIO',
               expected_frames=seconds * native)
    for gain in ladder:
        attempt = run_encode(candidate, pcm, dst, native, gain)
        attempts.append(attempt)
        if attempt['admitted'] or attempt.get('measurement_error') or attempt['output_left_on_failure']:
            break
    row['attempts'] = attempts
    row['admitted'] = attempts[-1]['admitted']
    row['explicit_gain_db'] = attempts[-1]['gain_db'] if row['admitted'] else None
    row['rejected_at_unity'] = len(attempts) > 0 and attempts[0]['overload_rejected']
    row['status'] = 'rejected' if not row['admitted'] else 'evaluating'
    if not row['admitted']:
        if attempts[-1].get('measurement_error') or attempts[-1]['output_left_on_failure']:
            row['status'] = 'measurement-error'
        dst.unlink(missing_ok=True)
        return row
    try:
        decoded = dsd_windows.dsf_window_statistics(dst, chunk_blocks=chunk_blocks)
        row.update(output_dsf_sha256=sha_file(dst), output_bytes=dst.stat().st_size,
                   output_rate_hz=decoded['rate'], output_channels=decoded['channels'],
                   output_frames_per_channel=decoded['frames'],
                   frames_exact=(decoded['frames'] == seconds * native and
                                 decoded['rate'] == native and decoded['channels'] == 2),
                   windows_per_channel=decoded['windows_per_channel'],
                   per_channel=decoded['per_channel'])
        row['window_count_exact'] = all(
            s['windows'] == max(0, decoded['frames'] - dsd_windows.WINDOW + 1)
            for s in decoded['per_channel'])
        if native == RATES[0]:
            row['dsd64_population_4_24'] = all(
                s['min_ones'] is not None and s['min_ones'] >= 4 and s['max_ones'] <= 24
                for s in decoded['per_channel'])
        source_level = stats(sox, pcm, gain=attempts[-1]['gain_db'])
        output_level = stats(sox, dst, dsd=True, working=WORKING[native])
        row['source_level'] = source_level
        row['output_level'] = output_level
        row['rms_delta_db'] = round(output_level['rms_db']-source_level['rms_db'], 4)
        row['peak_delta_db'] = round(output_level['peak_db']-source_level['peak_db'], 4)
        row['levels_within_tolerance'] = (
            abs(row['rms_delta_db']) <= RMS_TOLERANCE_DB and
            abs(row['peak_delta_db']) <= PEAK_TOLERANCE_DB)
        row['status'] = ('pass' if row['frames_exact'] and row['window_count_exact'] and
                         row['levels_within_tolerance'] and
                         (native != RATES[0] or row['dsd64_population_4_24'])
                         else 'out-of-spec')
    except (ValueError, OSError, CorpusError) as error:
        row['status'] = 'measurement-error'
        row['error'] = sanitize(str(error), (sox, candidate, pcm, dst))
    finally:
        dst.unlink(missing_ok=True)
    return row


def evaluate(rows: list[dict], seconds: int, rates: tuple[int, ...]) -> dict:
    valid = [r for r in rows if r.get('source_domain') == 'PCM_AUDIO'
             and r.get('origin') == 'commercial-external']
    passing = [(r, t) for r in valid for t in r.get('targets', [])
               if t.get('status') == 'pass']
    by_native = {}
    for native in RATES:
        accepted = [r for r, t in passing if t['native_hz'] == native]
        by_native[str(native)] = dict(
            independent_recordings=len({r['excerpt_pcm_sha256'] for r in accepted}),
            releases=len({r['release'] for r in accepted}),
            genres=sorted({r['genre'] for r in accepted}),
            source_clock_families=sorted({r['clock_family'] for r in accepted}))
    genres = sorted({r['genre'] for r, _ in passing})
    families = sorted({r['clock_family'] for r, _ in passing})
    issues = []
    if seconds < MIN_SECONDS:
        issues.append('excerpts shorter than mandatory 60 seconds')
    if set(rates) != set(RATES):
        issues.append('not all three native targets were requested')
    if len(genres) < 2:
        issues.append('fewer than two genres in admitted PCM corpus')
    if families != ['44100-family', '48000-family']:
        issues.append('both PCM clock families are not present in admitted PCM corpus')
    for native in RATES:
        coverage = by_native[str(native)]
        if min(coverage['releases'], coverage['independent_recordings']) < 2:
            issues.append(f'{native}: fewer than two independent admitted commercial recordings')
    if any(t['status'] in ('measurement-error', 'out-of-spec', 'rejected') for r in rows
           for t in r.get('targets', [])) or any('error' in r for r in rows):
        issues.append('one or more measured items failed validation or exhausted the optional gain ladder')
    if len(valid) < len(rows):
        issues.append('source identity or external provenance incomplete')
    return dict(schema='P10/PCM_AUDIO-coverage/1', source_domain='PCM_AUDIO',
                genres=genres, pcm_clock_families=families,
                by_native=by_native, approved_for_profile_promotion=False,
                completed=not issues, gate_status='PASS' if not issues else 'INCOMPLETE',
                issues=issues, note='This covers only the PCM_AUDIO domain; DSD_NATIVE and other P10 gates remain separate.')


def ratification_rows(rows: list[dict]):
    """Export the *existing* P10 adjudicator schema; no threshold changes.

    Unity is always the first (0 dB) attempt, even when a later explicit retry
    was admitted. That preserves the evidence of initial overload instead of
    silently rewriting it as a unity success.
    """
    originals, unity_rows, ladder_rows = [], [], []
    for src in rows:
        for target in src['targets']:
            native = target['native_hz']
            # Source IDs are audio-derived and unique even when distinct
            # releases both call their first track '01.flac'.
            identity = dict(source='pcm-' + src['excerpt_pcm_sha256'][:24] + '.wav',
                            excerpt_sha256=src['excerpt_wav_sha256'],
                            native_hz=native,
                            excerpt_seconds=src['excerpt_seconds'],
                            release=src['release'], genre=src['genre'],
                            source_domain='PCM_AUDIO',
                            source_rate_hz=src['source_rate_hz'],
                            origin=src['source_origin'],
                            original_bytes=src['source_file_bytes'])
            originals.append(identity)
            attempts = target['attempts']
            first = attempts[0]
            common = dict(identity, working_hz=target['working_hz'],
                          reconstruction_reference='sacd',
                          expected_frames=target['expected_frames'])
            unity = dict(common, admitted=first['admitted'],
                         encode_exit=first['exit_code'],
                         encode_stderr_tail=first['diagnostic_tail'],
                         explicit_gain_db=0.)
            if first['admitted']:
                unity.update(ratification_metrics(target))
            unity_rows.append(unity)
            if not first['admitted']:
                ladder = dict(common, admitted=target['admitted'],
                              encode_exit=attempts[-1]['exit_code'],
                              encode_stderr_tail=attempts[-1]['diagnostic_tail'],
                              explicit_gain_db=attempts[-1]['gain_db'],
                              admitting_gain_db=(attempts[-1]['gain_db'] if target['admitted'] else None),
                              ladder_attempts=[dict(gain_db=x['gain_db'],
                                                    admitted=x['admitted'],
                                                    stderr_tail=x['diagnostic_tail']) for x in attempts],
                              ladder_exhausted=not target['admitted'])
                if target['admitted']:
                    ladder.update(ratification_metrics(target))
                ladder_rows.append(ladder)
    return originals, unity_rows, ladder_rows


def ratification_metrics(row: dict) -> dict:
    channels = row.get('per_channel', [])
    return dict(output_frames=row.get('output_frames_per_channel'),
                frames_exact=row.get('frames_exact'), output_rate=row.get('output_rate_hz'),
                output_channels=row.get('output_channels'), output_bytes=row.get('output_bytes'),
                per_channel=channels,
                windows28=sum(c['windows'] for c in channels),
                min_ones28=min((c['min_ones'] for c in channels), default=None),
                max_ones28=max((c['max_ones'] for c in channels), default=None),
                population_within_4_24=row.get('dsd64_population_4_24'),
                source_excerpt_level=row.get('source_level'),
                remodulated_level=row.get('output_level'),
                peak_delta_db=row.get('peak_delta_db'),
                rms_delta_db=row.get('rms_delta_db'))


def write_ratification_receipts(results: Path, rows: list[dict]) -> None:
    originals, unity, ladder = ratification_rows(rows)
    # Only create derived evidence at the END of a completed input pass.
    # In-progress source/rate attempts remain solely in the atomic checkpoint.
    for filename, data in (('pcm-sources.json', originals),
                           ('pcm-unity.json', unity),
                           ('pcm-ladder.json', ladder)):
        atomic_json(results / filename, data)


def preflight(inventory: list[dict], sources: list[dict]) -> list[tuple[dict, dict]]:
    catalog = {r['release']: r for r in inventory}
    if len(catalog) != len(inventory):
        raise CorpusError('duplicate releases in inventory')
    if not sources:
        raise CorpusError('sources JSON must contain at least one release-to-FLAC mapping')
    seen = set()
    jobs = []
    for entry in sources:
        if not isinstance(entry, dict) or not isinstance(entry.get('release'), str) \
                or not isinstance(entry.get('path'), str) or not entry['path']:
            raise CorpusError('each source requires release and path strings')
        release = entry['release']
        if release not in catalog or release in seen:
            raise CorpusError('unknown or duplicate release in source mapping')
        seen.add(release)
        item = catalog[release]
        if item['container'] != 'flac' or item['bits_per_sample'] != 24 or item['channels'] != 2:
            raise CorpusError('inventory contains unsupported source layout')
        # A receipt stores this optional label verbatim. Never allow it to be
        # used as a covert means of persisting a local path in evidence.
        track = entry.get('track', '')
        if not isinstance(track, str) or '/' in track or '\\' in track or \
                any(ord(c) < 32 for c in track):
            raise CorpusError('track must be a single human-readable label, not a path')
        jobs.append((entry, item))
    return jobs


def args_parse(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sox', type=Path, default=ROOT / 'src/sox')
    parser.add_argument('--candidate', type=Path, default=ROOT / 'test/sox_p10_candidate')
    parser.add_argument('--flac', type=Path, default=Path('flac'))
    parser.add_argument('--inventory', type=Path, default=INVENTORY)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, default=None,
                        help='LOCAL temporary filesystem; defaults to system tmp')
    parser.add_argument('--native-hz', type=int, action='append', choices=RATES,
                        help='limit target rates for a diagnostic run (full gate needs all)')
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--offset', type=int, default=30)
    parser.add_argument('--gain-ladder', type=str, default=None,
                        help='optional comma-separated decreasing negative dB retries, e.g. --gain-ladder=-0.1,-0.5,-1,-3')
    parser.add_argument('--resume', action='store_true', help='reuse completed results after checking source size/mtime')
    parser.add_argument('--chunk-blocks', type=int, default=128)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    a = args_parse(argv)
    if a.seconds <= 0 or a.offset < 0:
        raise CorpusError('seconds must be positive and offset nonnegative')
    if not 1 <= a.chunk_blocks <= 4096:
        raise CorpusError('invalid chunk-blocks')
    ladder = gains(a.gain_ladder)
    rates = tuple(sorted(set(a.native_hz or RATES)))
    inventory = json.loads(a.inventory.read_text())
    sources = json.loads(a.sources.read_text())
    jobs = preflight(inventory, sources)
    a.results.mkdir(parents=True, exist_ok=True)
    receipt = a.results / RECORD_NAME
    if not receipt.exists() and any((a.results / name).exists() for name in
            ('pcm-sources.json', 'pcm-unity.json', 'pcm-ladder.json')):
        raise CorpusError('derived PCM receipts exist without a source checkpoint; '
                          'refusing to overwrite historical data')
    config = dict(schema=SCHEMA, inventory_sha256=sha_file(a.inventory),
                  source_mapping_sha256=canonical_hash([{'release': s['release'],
                        'track': s.get('track', ''),
                        # Include the private source path in the one-way run
                        # identity, never in persisted receipt text.
                        'path_hash': hashlib.sha256(os.fsencode(
                            Path(s['path']).expanduser().absolute())).hexdigest()}
                        for s, _ in jobs]),
                  native_rates=rates, excerpt_seconds=a.seconds, preferred_offset_seconds=a.offset,
                  gain_ladder_db=ladder, sox_sha256=sha_file(a.sox),
                  candidate_sha256=sha_file(a.candidate),
                  flac_version=subprocess.check_output([str(a.flac), '--version'], text=True).strip(),
                  architecture=platform.machine(),
                  analysis_reference='sacd',
                  calibration_rms_tolerance_db=RMS_TOLERANCE_DB,
                  calibration_peak_tolerance_db=PEAK_TOLERANCE_DB)
    key = canonical_hash(config)
    if receipt.exists():
        if not a.resume:
            raise CorpusError('result already exists; use --resume or a new result directory')
        result = json.loads(receipt.read_text())
        if result.get('run_sha256') != key:
            raise CorpusError('existing receipt configuration differs; start a new result directory')
    else:
        result = dict(schema=SCHEMA, run_sha256=key, configuration=config,
                      source_domain='PCM_AUDIO', entries=[], coverage=None)
    previous = {r['release']: r for r in result['entries']}
    if len(previous) != len(result['entries']):
        raise CorpusError('duplicate source entry in receipt')
    for mapping, item in jobs:
        src = Path(mapping['path'])
        identity = src.stat()
        old = previous.get(item['release'])
        if old is not None:
            if (old.get('source_file_bytes'), old.get('source_file_mtime_ns')) != \
                    (identity.st_size, identity.st_mtime_ns):
                raise CorpusError('source metadata changed since checkpoint; use new result directory')
            print('reused completed', item['release'][:64], flush=True)
            continue
        # A fresh local work directory per release. ALL files are deleted even
        # if a decode, encoder, measurement or interruption fails.
        with tempfile.TemporaryDirectory(prefix='p10-pcm-', dir=a.scratch) as temp:
            work = Path(temp)
            staged, excerpt = work / 'source.flac', work / 'excerpt.wav'
            file_sha = copy_remote_once(src, staged)
            after_copy = src.stat()
            if (identity.st_size, identity.st_mtime_ns) != \
                    (after_copy.st_size, after_copy.st_mtime_ns) or \
                    staged.stat().st_size != identity.st_size:
                raise CorpusError('source metadata/length changed during remote staging')
            streaminfo = read_streaminfo(staged)
            check_inventory(item, streaminfo)
            checked = commands(a.flac, '-t', '-s', staged, redact=(a.flac, staged, src))
            if checked.returncode:
                raise CorpusError('FLAC CRC/STREAMINFO integrity check failed: ' + checked.stderr)
            source_frames = streaminfo['total_samples']
            n = a.seconds * item['sample_rate_hz']
            if n > source_frames:
                raise CorpusError('track too short for selected excerpt')
            offset = min(a.offset * item['sample_rate_hz'], source_frames - n)
            decoded = commands(a.flac, '-d', '-s', f'--skip={offset}',
                               f'--until={offset+n}', '-o', excerpt, staged,
                               redact=(a.flac, staged, excerpt, src))
            if decoded.returncode:
                raise CorpusError('lossless excerpt extraction failed: ' + decoded.stderr)
            digest = check_wav_excerpt(excerpt, item['sample_rate_hz'], n)
            row = dict(origin='commercial-external', source_domain='PCM_AUDIO',
                       release=item['release'], track=mapping.get('track', src.name),
                       genre=item['genre'], source_rate_hz=item['sample_rate_hz'],
                       clock_family=item['clock_family'],
                       source_origin=item.get('origin', 'unspecified-commercial-master'),
                       source_file_bytes=identity.st_size,
                       source_file_mtime_ns=identity.st_mtime_ns,
                       source_flac_sha256=file_sha,
                       source_streaminfo_md5=streaminfo['streaminfo_md5'],
                       streaminfo_md5_present=streaminfo['streaminfo_md5'] != '0'*32,
                       flac_crc_test_passed=True,
                       excerpt_offset_frames=offset,
                       excerpt_seconds=a.seconds, **digest,
                       targets=[])
            for native in rates:
                target = measure_native(a.sox, a.candidate, excerpt, native,
                                        a.seconds, ladder, chunk_blocks=a.chunk_blocks)
                row['targets'].append(target)
                print(item['release'][:45], native, target['status'], flush=True)
            result['entries'].append(row)
            result['coverage'] = evaluate(result['entries'], a.seconds, rates)
            atomic_json(receipt, result)
    result['coverage'] = evaluate(result['entries'], a.seconds, rates)
    atomic_json(receipt, result)
    # The ratification checker expects this existing wire format. Exporting it
    # requires that every declared source and every target was attempted.
    if len(result['entries']) == len(jobs) and all(
            len(row.get('targets', [])) == len(rates) for row in result['entries']):
        write_ratification_receipts(a.results, result['entries'])
    print('PCM_AUDIO coverage:', result['coverage']['gate_status'],
          '; cases:', len(result['entries']), '; output:', receipt.name)
    return 0 if all(t['status'] not in ('measurement-error', 'out-of-spec')
                    for r in result['entries'] for t in r['targets']) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (CorpusError, OSError, ValueError, subprocess.SubprocessError) as exc:
        # No local paths printed in archived evidence; the interactive CLI may
        # report the exception class, but no raw source path is needed.
        print('PCM_AUDIO measurement failed:', type(exc).__name__, file=sys.stderr)
        sys.exit(1)
