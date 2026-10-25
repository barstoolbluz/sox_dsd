#!/usr/bin/env python3
"""Independent audio-reference gate for high-rate DSF and DSDIFF reading.

Agreement with an independent decoder tests audio-band reader behavior, not
filter equivalence, device interoperability, or real-world DSDIFF header
variation when only self-encoded files are available. Commercial provenance
is declared by the operator supplying --media-root; it is not authenticated.

Uses numpy and scipy. PCM is transient and is deleted on every exit path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import struct
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_SCHEMA = 'P21/independent-reader-case/2'
REPORT_SCHEMA = 'P21/independent-reader-evidence/2'
MIN_PEARSON = 0.999
MAX_LEVEL_DELTA_DB = 0.1
MIN_CHANNEL_MARGIN = 0.01
MAX_CONTROL_PEARSON = 0.5
# An occasional dropped DSD block can be inaudible to a ten-second average.
# Bound 100 ms in-band residual energy without demanding filter equivalence.
MAX_WINDOW_RMS_RESIDUAL = 0.15
WINDOW_SECONDS = 0.1
ANALYSIS_BAND_HZ = (0, 20000)
PROFILES = (
    ('mastering', 'decode.mastering.v1', {22579200: 176400, 45158400: 176400}),
    ('wideband', 'decode.wideband.v1', {22579200: 705600, 45158400: 1411200}),
    (None, 'decode.mastering.v2', {22579200: 176400, 45158400: 176400}),
)
SELF_RATES = (22579200, 45158400)
SELF_CONTAINERS = ('dsf', 'dff')
EXPECTED_ROWS = {f'{ext}-read-{rate}' for ext in SELF_CONTAINERS for rate in SELF_RATES}
PROFILE_IDS = {pid for _, pid, _ in PROFILES}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        tmp.write_text(json.dumps(row, sort_keys=True, indent=2, allow_nan=False) + '\n')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def sanitized(stderr, src):
    # Error messages from decoders may quote licensed file paths.
    path = Path(src)
    for value in sorted({str(path), str(path.resolve()), path.name},
                        key=len, reverse=True):
        if value:
            stderr = stderr.replace(value, '<source-media>')
    return stderr[-800:]


def thresholds():
    return dict(min_pearson=MIN_PEARSON,
                max_level_delta_db=MAX_LEVEL_DELTA_DB,
                min_channel_margin=MIN_CHANNEL_MARGIN,
                max_control_pearson=MAX_CONTROL_PEARSON,
                max_window_rms_residual=MAX_WINDOW_RMS_RESIDUAL,
                window_seconds=WINDOW_SECONDS)


def native_dsd_rate(path, container):
    """Read the stored DSD bit clock from the file's container header.

    Do not use the writer's requested rate or its own decoder as an oracle.
    DSDIFF's PROP/SND/FS chunk may follow other chunks, including metadata.
    """
    path = Path(path)
    with path.open('rb') as f:
        size = path.stat().st_size
        if container == 'dsf':
            header = f.read(80)
            if (len(header) != 80 or header[:4] != b'DSD ' or
                struct.unpack_from('<Q', header, 4)[0] != 28 or
                header[28:32] != b'fmt ' or
                struct.unpack_from('<Q', header, 32)[0] < 52 or
                struct.unpack_from('<II', header, 40) != (1, 0)):
                raise ValueError('invalid DSF format header')
            return struct.unpack_from('<I', header, 56)[0]
        if container != 'dff':
            raise ValueError(f'unsupported DSD container: {container}')
        header = f.read(16)
        if len(header) != 16 or header[:4] != b'FRM8' or header[12:] != b'DSD ':
            raise ValueError('invalid DSDIFF form header')
        end = 12 + struct.unpack_from('>Q', header, 4)[0]
        if end > size or end < 16:
            raise ValueError('invalid DSDIFF form length')

        def chunks(limit):
            while f.tell() < limit:
                if limit - f.tell() < 12:
                    raise ValueError('truncated DSDIFF chunk header')
                chunk = f.read(12)
                name, length = chunk[:4], struct.unpack_from('>Q', chunk, 4)[0]
                start = f.tell()
                if length > limit - start or length % 2 and start + length + 1 > limit:
                    raise ValueError('invalid DSDIFF chunk length')
                yield name, start, length
                f.seek(start + length + (length & 1))

        sample_rates = []
        for name, start, length in chunks(end):
            if name != b'PROP':
                continue
            if length < 4:
                raise ValueError('invalid DSDIFF property chunk')
            f.seek(start)
            if f.read(4) != b'SND ':
                continue
            for subname, substart, sublength in chunks(start + length):
                if subname == b'FS  ':
                    if sublength != 4:
                        raise ValueError('invalid DSDIFF sample-rate field')
                    f.seek(substart)
                    sample_rates.append(struct.unpack('>I', f.read(4))[0])
        if len(sample_rates) != 1:
            raise ValueError('missing or ambiguous DSDIFF sample-rate field')
        return sample_rates[0]


def make_sources(sox, scratch, seconds, count=2, from_tracks=None,
                 start=0.0, timeout=1800):
    """Prepare independent-reader inputs from the writer's native file shapes.

    The self-encoded files do not independently qualify the writer or container
    variation. Licensed source extraction must succeed for a qualifying run;
    synthetic stimuli are available only for diagnostics without media inputs.
    """
    import numpy as np
    srcs, fs = [], 176400
    for k in range(count):
        raw = scratch / f'src{k}.f64'
        origin = None
        if from_tracks is not None:
            cmd = [str(sox), '--dsd-layout-loss', 'warn', '-D',
                   str(from_tracks[k]), '-t', 'f64', '-r', str(fs), '-c', '2',
                   str(raw), 'trim', str(start), str(seconds)]
            p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=timeout)
            if p.returncode == 0 and raw.is_file() and raw.stat().st_size > 0:
                origin = 'derived-from-licensed-pcm'
            else:
                raw.unlink(missing_ok=True)
                raise RuntimeError(f'licensed PCM extraction failed for source {k}: '
                                   f'{sanitized(p.stderr, from_tracks[k])}')
        if origin is None:
            n = int(fs * seconds)
            tt = np.arange(n, dtype=np.float64) / fs
            rng = np.random.default_rng(0x50D0 + k)
            chans = []
            for c in (0, 1):
                tone = sum(np.sin(2 * np.pi * f * tt + 0.7 * c)
                           for f in (131 * (k + 1) + 37 * c, 997 + 11 * c,
                                     5501 * (k + 1) + 97 * c))
                chans.append(np.clip(0.10 * tone + 0.05 * rng.uniform(-1., 1., n),
                                     -0.9, 0.9))
            np.stack(chans, axis=1).astype('<f8').tofile(raw)
            origin = 'synthetic'
        for rate in SELF_RATES:
            for container in SELF_CONTAINERS:
                dest = scratch / f'self{k}-{rate}-{container}.{container}'
                cmd = [str(sox), '-t', 'f64', '-r', str(fs), '-c', '2', str(raw),
                       '-t', container, '-r', str(rate), str(dest)]
                p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                                   text=True, timeout=timeout)
                if p.returncode != 0 or not dest.is_file() or not dest.stat().st_size:
                    raise RuntimeError(f'could not encode {dest.name}: {p.stderr[-400:]}')
                try:
                    actual_rate = native_dsd_rate(dest, container)
                except ValueError as exc:
                    raise RuntimeError(f'cannot verify native DSD clock in {dest.name}: '
                                       f'{exc}') from exc
                if actual_rate != rate:
                    raise RuntimeError(f'wrong native DSD clock in {dest.name}: '
                                       f'{actual_rate}, requested {rate}')
                srcs.append((dest, rate, container, k, origin))
        raw.unlink(missing_ok=True)
    return srcs


def decode_ours(sox, src, profile, out_hz, dest, start, seconds, timeout):
    cmd = [str(sox), '--dsd-layout-loss', 'warn']
    if profile is not None:
        cmd += ['--dsd-decode', profile]
    cmd += ['-D', str(src), '-t', 'f64', '-r', str(out_hz), '-c', '2', str(dest),
            'trim', str(start), str(seconds)]
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, sanitized(p.stderr, src)


def decode_reference(ref, src, out_hz, dest, start, seconds, timeout):
    cmd = [str(ref), '-hide_banner', '-v', 'error', '-ss', str(start),
           '-i', str(src), '-t', str(seconds), '-ar', str(out_hz), '-ac', '2',
           '-c:a', 'pcm_f64le', '-f', 'f64le', str(dest), '-y']
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, sanitized(p.stderr, src)


def compare(ours_path, ref_path, control_path, out_hz, seconds):
    """Compare complete stereo intervals; fail on missing/truncated control."""
    import numpy as np
    from scipy import signal

    expected = int(round(seconds * out_hz))
    if expected < int(out_hz * 0.5):
        return None, 'comparison interval shorter than 0.5 seconds'
    paths = (ours_path, ref_path, control_path)
    if any(p is None or not Path(p).is_file() for p in paths):
        return None, 'missing decode or independent negative control'
    lengths = []
    for p in paths:
        size = Path(p).stat().st_size
        if size % 16 != 0:
            return None, f'non-stereo or partial f64 frame: {Path(p).name}'
        frames = size // 16
        if abs(frames - expected) > 2:
            return None, (f'incomplete or extended decode: {Path(p).name} '
                          f'{frames} frames, expected {expected}')
        lengths.append(frames)
    n = min(lengths)
    ours, ref, ctl = (np.fromfile(p, dtype='<f8').reshape(-1, 2)[:n]
                      for p in paths)
    if not all(np.isfinite(v).all() for v in (ours, ref, ctl)):
        return None, 'non-finite PCM samples'
    hi = min(ANALYSIS_BAND_HZ[1], out_hz // 2 - 1)
    sos = signal.butter(8, hi, fs=out_hz, output='sos')
    a = signal.sosfiltfilt(sos, ours, axis=0)
    b = signal.sosfiltfilt(sos, ref, axis=0)
    t = signal.sosfiltfilt(sos, ctl, axis=0)
    metrics = dict(frames_compared=int(n), expected_frames=int(expected),
                   analysis_band_hz=[ANALYSIS_BAND_HZ[0], hi], channels=[],
                   control_pearson_r=[])
    window = max(32, int(round(WINDOW_SECONDS * out_hz)))
    starts = list(range(0, n - window + 1, window))
    if not starts or starts[-1] + window < n:
        starts.append(max(0, n - window))
    for c in (0, 1):
        x, y, z = a[:, c], b[:, c], t[:, c]
        sa, sb = float(np.std(x)), float(np.std(y))
        if sb <= 0 or sa <= 0:
            return None, f'ch{c} zero-energy audio'
        global_rms = float(np.sqrt(np.mean(y * y)))
        if global_rms <= 0:
            return None, f'ch{c} zero-energy reference'
        residual = x - y
        local_max = 0.0
        for start in starts:
            end = min(n, start + window)
            local_rms = float(np.sqrt(np.mean(y[start:end] ** 2)))
            err_rms = float(np.sqrt(np.mean(residual[start:end] ** 2)))
            local_max = max(local_max, err_rms /
                            max(local_rms, 0.1 * global_rms))
        metrics['channels'].append(dict(
            channel=c, pearson_r=float(np.corrcoef(x, y)[0, 1]),
            cross_channel_pearson_r=float(np.corrcoef(x, b[:, 1 - c])[0, 1]),
            level_delta_db=float(20 * np.log10(sa / sb)),
            max_window_rms_residual=float(local_max)))
        metrics['control_pearson_r'].append(float(np.corrcoef(x, z)[0, 1]))
    return metrics, None


def judge(metrics):
    """Fail unless all metrics are present, finite and inside their bounds."""
    if not isinstance(metrics, dict):
        return False, ['no metrics']
    reasons = []
    channels = metrics.get('channels')
    control = metrics.get('control_pearson_r')
    if not isinstance(channels, list) or len(channels) != 2 or not isinstance(control, list) or len(control) != 2:
        return False, ['incomplete channel metrics or negative control']
    for idx, ch in enumerate(channels):
        if not isinstance(ch, dict) or ch.get('channel') != idx:
            reasons.append(f'ch{idx} metrics missing')
            continue
        keys = ('pearson_r', 'cross_channel_pearson_r', 'level_delta_db',
                'max_window_rms_residual')
        if any(not isinstance(ch.get(key), (int, float)) or
               not math.isfinite(ch[key]) for key in keys):
            reasons.append(f'ch{idx} non-finite or missing metrics')
            continue
        r = ch['pearson_r']
        if r < MIN_PEARSON:
            reasons.append(f'ch{idx} pearson {r:.6f} < {MIN_PEARSON}')
        if abs(ch['level_delta_db']) > MAX_LEVEL_DELTA_DB:
            reasons.append(f'ch{idx} level delta {ch["level_delta_db"]} outside +/-{MAX_LEVEL_DELTA_DB} dB')
        if r - ch['cross_channel_pearson_r'] < MIN_CHANNEL_MARGIN:
            reasons.append(f'ch{idx} channel identity unproven: same {r:.6f} vs cross {ch["cross_channel_pearson_r"]:.6f}')
        if ch['max_window_rms_residual'] > MAX_WINDOW_RMS_RESIDUAL:
            reasons.append(f'ch{idx} local residual {ch["max_window_rms_residual"]:.6f} > {MAX_WINDOW_RMS_RESIDUAL}')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in control):
        reasons.append('negative control missing or non-finite')
    elif max(abs(v) for v in control) > MAX_CONTROL_PEARSON:
        reasons.append(f'negative control correlates {control}')
    return not reasons, reasons


def summarize_cases(cases):
    """Require the three CLI paths on each source, not just some passing path."""
    grouped = {}
    by_row = {}
    by_provenance = {}
    for c in cases:
        key = (c['media_provenance'], c['capability_row'], c['source_sha256'])
        grouped.setdefault(key, []).append(c)
        row = c['capability_row']
        by_row.setdefault(row, []).append(c)
        by_provenance.setdefault(row, set()).add(c['media_provenance'])
    complete = {}
    for (prov, row, src), entries in grouped.items():
        ids = {c['profile_id'] for c in entries}
        complete[(prov, row, src)] = (len(entries) == len(PROFILES)
                                       and ids == PROFILE_IDS
                                       and all(c['status'] == 'PASS' for c in entries))
    rows = {}
    rows_commercial = {}
    row_profiles = {}
    for row, entries in by_row.items():
        sources = {c['source_sha256'] for c in entries}
        rows[row] = (len(sources) >= 2 and
                     all(complete[(c['media_provenance'], row, c['source_sha256'])]
                         for c in entries))
        commercial = {c['source_sha256'] for c in entries
                      if c['media_provenance'] == 'commercial'}
        rows_commercial[row] = (rows[row] and len(commercial) >= 2 and
                                all(complete[('commercial', row, source)]
                                    for source in commercial))
        row_profiles[row] = {pid: rows[row] and
                             all(c['status'] == 'PASS' for c in entries
                                 if c['profile_id'] == pid) and
                             any(c['profile_id'] == pid for c in entries)
                             for pid in PROFILE_IDS}
    return (rows, rows_commercial, row_profiles,
            {r: sorted(provs) for r, provs in by_provenance.items()})


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--media-root', type=Path, default=None)
    a.add_argument('--self-encoded', action='store_true')
    a.add_argument('--self-sources', type=int, default=2)
    a.add_argument('--sox', type=Path, default=ROOT / 'src/sox')
    a.add_argument('--reference', type=Path, default=Path('/usr/bin/ffmpeg'))
    a.add_argument('--results', type=Path, required=True)
    a.add_argument('--scratch', type=Path, default=None)
    a.add_argument('--start-seconds', type=float, default=5.0)
    a.add_argument('--seconds', type=float, default=10.0)
    a.add_argument('--timeout', type=int, default=1800)
    a.add_argument('--require-media', action='store_true')
    args = a.parse_args()
    for name in ('sox', 'reference'):
        if not getattr(args, name).is_file():
            a.error(f'{name} not found: {getattr(args, name)}')
    if (not math.isfinite(args.seconds) or not math.isfinite(args.start_seconds)
            or args.seconds < 0.5 or args.start_seconds < 0):
        a.error('seconds must be >= 0.5 and start-seconds must be >= 0')
    if args.timeout < 1:
        a.error('timeout must be positive')
    if args.media_root is None and not args.self_encoded:
        a.error('supply --media-root, --self-encoded, or both')
    if args.self_encoded and args.self_sources < 2:
        a.error('--self-sources must be >= 2 for an independent negative control')
    if args.self_encoded and args.seconds < 1.0:
        a.error('self-encoded comparison needs at least one second of source')
    tracks = []
    if args.media_root is not None:
        root = args.media_root.resolve()
        if not root.is_dir():
            a.error('media directory missing')
        tracks = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.dsf')
    if args.require_media and len(tracks) < 2:
        a.error('at least two independent commercial DSF inputs required')
    if args.self_encoded and tracks and len(tracks) < args.self_sources:
        a.error('self-encoded run needs at least --self-sources licensed tracks')
    # Never overwrite a prior verdict or merge old case receipts into a new run.
    try:
        args.results.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        a.error(f'results directory already exists; use a new run directory: {args.results}')
    if args.scratch is not None:
        args.scratch.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([str(args.reference), '-version'], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=args.timeout)
    if version.returncode:
        a.error('reference version probe failed')
    ref_version = version.stdout.splitlines()[:1]
    runner_sha, sox_sha, ref_sha = sha(Path(__file__)), sha(args.sox), sha(args.reference)
    cases = []
    with tempfile.TemporaryDirectory(prefix='p21-reader-', dir=args.scratch) as scratch_name:
        scratch = Path(scratch_name)
        work = []
        for i, track in enumerate(tracks):
            work.append(dict(path=track, rate=None, container='dsf',
                             provenance='commercial',
                             control=tracks[(i + 1) % len(tracks)] if len(tracks) > 1 else None))
        if args.self_encoded:
            made = make_sources(args.sox, scratch, args.seconds, args.self_sources,
                                from_tracks=tracks if tracks else None,
                                start=args.start_seconds,
                                timeout=args.timeout)
            for path, rate, container, k, origin in made:
                peer = next((p for p, r, ct, j, _ in made
                             if r == rate and ct == container and j != k), None)
                work.append(dict(path=path, rate=rate, container=container,
                                 provenance='self-encoded', control=peer,
                                 stimulus_origin=origin))
        for item in work:
            track = item['path']
            source_hash = sha(track)
            token = source_hash[:20]
            control_track = item['control']
            control_hash = sha(control_track) if control_track is not None else None
            native = item['rate']
            if native is None:
                probe = subprocess.run([str(args.sox), '--i', '-r', str(track)],
                                       stdin=subprocess.DEVNULL, capture_output=True,
                                       text=True, timeout=args.timeout)
                if probe.returncode:
                    raise RuntimeError(f'could not identify rate of input {token}')
                try:
                    parsed = float(probe.stdout.strip())
                    native = int(parsed)
                except ValueError as e:
                    raise RuntimeError(f'invalid rate for input {token}') from e
                if not math.isfinite(parsed) or parsed != native:
                    raise RuntimeError(f'nonintegral or nonfinite rate for input {token}')
            if native not in SELF_RATES:
                raise RuntimeError(f'unsupported input rate for {token}: {native}')
            for flag, pid, out_map in PROFILES:
                out_hz = out_map[native]
                tag = f'{token}-{item["container"]}-{pid}'
                case_path = args.results / 'cases' / f'{tag}.json'
                if case_path.exists():
                    raise RuntimeError(f'duplicate reader case receipt: {tag}')
                ours, refp, ctlp = (scratch / f'{tag}-{suffix}.f64'
                                    for suffix in ('ours', 'ref', 'ctl'))
                started = time.monotonic()
                start = args.start_seconds if item['provenance'] == 'commercial' else 0.0
                span = args.seconds if item['provenance'] == 'commercial' else args.seconds / 2
                rc_o, err_o = decode_ours(args.sox, track, flag, out_hz, ours,
                                          start, span, args.timeout)
                rc_r, err_r = decode_reference(args.reference, track, out_hz, refp,
                                               start, span, args.timeout)
                rc_ctl, err_ctl = (None, 'negative control unavailable')
                if control_track is not None and control_hash != source_hash:
                    rc_ctl, err_ctl = decode_reference(args.reference, control_track,
                                                       out_hz, ctlp, start, span, args.timeout)
                if rc_o or rc_r or rc_ctl != 0:
                    metrics, why = None, (f'decode exit: sox={rc_o}, reference={rc_r}, '
                                          f'negative_control={rc_ctl}: {err_ctl[-200:]}')
                else:
                    metrics, why = compare(ours, refp, ctlp, out_hz, span)
                passed, reasons = judge(metrics)
                if why:
                    reasons.insert(0, why)
                    passed = False
                row = dict(schema=CASE_SCHEMA, status='PASS' if passed else 'FAIL',
                           source_sha256=source_hash, source_id=token,
                           source_bytes=track.stat().st_size,
                           media_provenance=item['provenance'], container=item['container'],
                           stimulus_origin=item.get('stimulus_origin', 'licensed-original'),
                           control_sha256=control_hash, native_hz=native,
                           capability_row=f'{item["container"]}-read-{native}',
                           profile_id=pid, cli_decode_flag=flag or '(default)',
                           output_hz=out_hz, start_seconds=start, seconds=span,
                           sox_sha256=sox_sha, runner_sha256=runner_sha,
                           reference_sha256=ref_sha, reference=ref_version,
                           sox_exit=rc_o, reference_exit=rc_r,
                           control_exit=rc_ctl, sox_stderr_tail=err_o,
                           reference_stderr_tail=err_r,
                           control_stderr_tail=err_ctl,
                           thresholds=thresholds(), metrics=metrics,
                           failure_reasons=reasons,
                           elapsed_seconds=time.monotonic() - started)
                atomic(case_path, row)
                cases.append(row)
                print(row['status'], item['provenance'], native, item['container'], pid,
                      flush=True)
                for p in (ours, refp, ctlp):
                    p.unlink(missing_ok=True)
    rows, rows_commercial, row_profiles, provenance = summarize_cases(cases)
    any_fail = any(c['status'] != 'PASS' for c in cases)
    # Four rows require coverage; DSF512 additionally requires commercial files.
    licensed_stimuli = all(c['stimulus_origin'] == 'derived-from-licensed-pcm'
                           for c in cases if c['media_provenance'] == 'self-encoded')
    complete = (not any_fail and licensed_stimuli and EXPECTED_ROWS <= rows.keys()
                and all(rows[r] for r in EXPECTED_ROWS)
                and rows_commercial.get('dsf-read-22579200') is True)
    gate = 'FAIL' if any_fail else ('PASS' if complete else 'INCOMPLETE')
    commercial_sources = sorted({c['source_sha256'] for c in cases
                                 if c['media_provenance'] == 'commercial'})
    self_sources = sorted({c['source_sha256'] for c in cases
                           if c['media_provenance'] == 'self-encoded'})
    receipt_index = {f'cases/{c["source_id"]}-{c["container"]}-{c["profile_id"]}.json': c['status']
                     for c in cases}
    if len(receipt_index) != len(cases):
        raise RuntimeError('duplicate reader case index entries')
    report = dict(schema=REPORT_SCHEMA,
                  independent_reader_and_audio_reference_gate=gate,
                  tracks=len({c['source_sha256'] for c in cases}),
                  case_count=len(cases),
                  profiles_qualified={pid: (gate == 'PASS' and all(
                      row_profiles[row].get(pid) is True for row in EXPECTED_ROWS))
                      for pid in PROFILE_IDS},
                  rows_qualified=rows, rows_qualified_commercial=rows_commercial,
                  row_profiles_qualified=row_profiles, rows_by_provenance=provenance,
                  commercial_media_sha256=commercial_sources,
                  self_encoded_media_sha256=self_sources,
                  media_sha256=sorted(set(commercial_sources + self_sources)),
                  case_receipts=receipt_index,
                  reference=ref_version, reference_sha256=ref_sha,
                  sox_sha256=sox_sha, runner_sha256=runner_sha,
                  host=dict(node=platform.node(), os=platform.platform(),
                            machine=platform.machine()),
                  thresholds=thresholds(),
                  establishes='Independent reader audio-band agreement on complete intervals, '
                              'with channel identity, negative controls, and local residual bounds.',
                  does_not_establish='Filter equivalence, higher-frequency wideband reconstruction, '
                                     'device interoperability, independently qualified writer behavior, '
                                     'or real-world DSDIFF header/DST variation for self-encoded media.',
                  provenance_note='Commercial denotes operator-supplied files under --media-root; '
                                  'authenticity is not independently verified. Self-encoded files '
                                  'exercise the writer\'s file shapes and often contain program '
                                  'material reconstructed by this same SoX decoder.',
                  device_claims=[])
    atomic(args.results / 'independent-reader-evidence.json', report)
    print('INDEPENDENT_READER', gate, report['tracks'], 'tracks', len(cases), 'cases')
    return 0 if gate == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
