#!/usr/bin/env python3
"""Independent-reader and audio-reference gate for high-rate DSD decode.

P17 declared this gate and never implemented it: its collector returned the
literal string 'UNRUN' and an all-False profile map. P21 then opened the
high-rate read rows anyway, on the operator's declaration. This closes the
gap it can actually close.

What the gate establishes: that a second, independently written DSD reader
recovers the same audio from the same licensed file. Agreement in the audio
band validates container parsing, block and channel interleave, bit order,
sample alignment and gross gain -- the things a reader can get wrong and
still produce plausible output.

What it does NOT establish: filter equivalence. The reference implements its
own DSD-to-PCM reconstruction, so out-of-band behaviour differs by design and
bit-exactness is impossible. Nor does it establish device interoperability.

Licensed media never appears in receipts except as a SHA-256. No PCM is
retained. Requires numpy and scipy; see docs for the interpreter.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Thresholds. Each sits orders of magnitude from measured agreement and has a
# demonstrated failure mode that trips it; see REFERENCE_SEPARATION below.
MIN_PEARSON        = 0.999   # measured 0.9999+; a channel swap on real stereo
                             # material measured 0.81, a different track 0.01
MAX_LEVEL_DELTA_DB = 0.1     # measured 0.0002
MIN_CHANNEL_MARGIN = 0.01    # same-channel r must exceed cross-channel r
MAX_CONTROL_PEARSON = 0.5    # a different track must NOT pass
ANALYSIS_BAND_HZ   = (0, 20000)

# (cli flag or None for the default path, profile id, output Hz by native clock)
PROFILES = (
    ('mastering', 'decode.mastering.v1', {22579200: 176400,  45158400: 176400}),
    ('wideband',  'decode.wideband.v1',  {22579200: 705600,  45158400: 1411200}),
    (None,        'decode.mastering.v2', {22579200: 176400,  45158400: 176400}),
)
SELF_RATES = (22579200, 45158400)
SELF_CONTAINERS = ('dsf', 'dff')

def make_sources(sox, scratch, seconds, count=2, from_tracks=None,
                 start=0.0, timeout=1800):
    """Make media at every clock and container, then hand it back for reading.

    Self-encoded media cannot validate our encoder; that would be circular. It
    validates the READER: a second implementation parsing a file we wrote has
    to recover the same audio, so a reader fault, a writer fault, or both would
    have to be wrong in the same direction to pass. It cannot cover real-world
    header variation, unusual chunk order, or DST-compressed DFF, because these
    files only exercise the shapes our own writer emits.

    The stimulus is real program material where licensed tracks are available.
    Synthetic tone-plus-noise was tried first and measured the wrong thing:
    agreement tracked content frequency and oversampling ratio -- 0.9974 at
    DSD512 for an 11 kHz tone against 0.9998 at DSD1024 -- while channel
    identity, level and the negative control stayed perfect. That is
    reconstruction-filter divergence, which this gate explicitly does not test.
    Commercially mastered content gives 0.99997, so deriving from it keeps one
    threshold across provenance rather than a looser one here.

    Derived PCM is scratch only. It never reaches evidence, and the licensed
    source appears solely as a SHA-256.
    """
    import numpy as np
    srcs, fs = [], 176400
    for k in range(count):
        raw = scratch / f'src{k}.f64'
        origin = None
        if from_tracks and k < len(from_tracks):
            cmd = [str(sox), '--dsd-layout-loss', 'warn', '-D',
                   str(from_tracks[k]), '-t', 'f64', '-r', str(fs), '-c', '2',
                   str(raw), 'trim', str(start), str(seconds)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and raw.is_file() and raw.stat().st_size > 0:
                origin = 'derived-from-licensed-pcm'
        if origin is None:
            # Fallback only. Distinct content per source so the negative
            # control means something, and decorrelated channels so the
            # channel-identity check can discriminate: duplicating one signal
            # into both makes a swap undetectable in principle.
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
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode != 0 or not dest.is_file():
                    raise RuntimeError(f'could not encode self media {dest.name}: '
                                       + r.stderr[-400:])
                srcs.append((dest, rate, container, k, origin))
    return srcs

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def atomic(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(row, sort_keys=True, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)

def decode_ours(sox, src, profile, out_hz, dest, start, seconds, timeout):
    cmd = [str(sox), '--dsd-layout-loss', 'warn']
    if profile is not None:
        cmd += ['--dsd-decode', profile]
    cmd += ['-D', str(src), '-t', 'f64', '-r', str(out_hz), '-c', '2', str(dest),
            'trim', str(start), str(seconds)]
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stderr[-800:]

def decode_reference(ref, src, out_hz, dest, start, seconds, timeout):
    cmd = [str(ref), '-hide_banner', '-v', 'error', '-ss', str(start),
           '-i', str(src), '-t', str(seconds), '-ar', str(out_hz), '-ac', '2',
           '-c:a', 'pcm_f64le', '-f', 'f64le', str(dest), '-y']
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stderr[-800:]

def compare(ours_path, ref_path, control_path, out_hz):
    import numpy as np
    from scipy import signal
    def load(p):
        a = np.fromfile(p, dtype='<f8')
        return a[:len(a) // 2 * 2].reshape(-1, 2)
    ours, ref = load(ours_path), load(ref_path)
    n = min(len(ours), len(ref))
    if n < out_hz // 2:
        return None, 'too few frames recovered for a meaningful comparison'
    ours, ref = ours[:n], ref[:n]
    hi = min(ANALYSIS_BAND_HZ[1], out_hz // 2 - 1)
    sos = signal.butter(8, hi, fs=out_hz, output='sos')
    band = lambda x: signal.sosfiltfilt(sos, x)
    metrics = {'frames_compared': int(n), 'analysis_band_hz': [ANALYSIS_BAND_HZ[0], hi],
               'channels': []}
    for c in (0, 1):
        a, b = band(ours[:, c]), band(ref[:, c])
        x = band(ref[:, 1 - c])
        sa, sb = float(np.std(a)), float(np.std(b))
        metrics['channels'].append({
            'channel': c,
            'pearson_r': float(np.corrcoef(a, b)[0, 1]),
            'cross_channel_pearson_r': float(np.corrcoef(a, x)[0, 1]),
            'level_delta_db': float(20 * np.log10(sa / sb)) if sb > 0 else None,
        })
    if control_path is not None and Path(control_path).is_file():
        ctl = load(control_path)
        m = min(n, len(ctl))
        metrics['control_pearson_r'] = [
            float(np.corrcoef(band(ours[:m, c]), band(ctl[:m, c]))[0, 1]) for c in (0, 1)]
    return metrics, None

def judge(metrics):
    """Return (passed, reasons). Every threshold is a hard gate."""
    reasons = []
    if metrics is None:
        return False, ['no metrics']
    for ch in metrics['channels']:
        if not ch['pearson_r'] >= MIN_PEARSON:
            reasons.append(f"ch{ch['channel']} pearson {ch['pearson_r']:.6f} < {MIN_PEARSON}")
        d = ch['level_delta_db']
        if d is None or abs(d) > MAX_LEVEL_DELTA_DB:
            reasons.append(f"ch{ch['channel']} level delta {d} outside +/-{MAX_LEVEL_DELTA_DB} dB")
        if ch['pearson_r'] - ch['cross_channel_pearson_r'] < MIN_CHANNEL_MARGIN:
            reasons.append(f"ch{ch['channel']} channel identity unproven: "
                           f"same {ch['pearson_r']:.6f} vs cross {ch['cross_channel_pearson_r']:.6f}")
    ctl = metrics.get('control_pearson_r')
    if ctl is not None and max(abs(v) for v in ctl) > MAX_CONTROL_PEARSON:
        reasons.append(f"negative control correlates {ctl}; the comparison cannot fail")
    return (not reasons), reasons

def main():
    a = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--media-root', type=Path, default=None,
        help='private licensed DSF directory; never copied into evidence')
    a.add_argument('--self-encoded', action='store_true',
        help='additionally generate media at every clock and container and '
             'cross-read it; covers rows for which no licensed media exists')
    a.add_argument('--self-sources', type=int, default=2,
        help='distinct self-encoded sources; at least 2 for a negative control')
    a.add_argument('--sox', type=Path, default=ROOT / 'src/sox')
    a.add_argument('--reference', type=Path, default=Path('/usr/bin/ffmpeg'),
        help='independently written DSD reader used as the second opinion')
    a.add_argument('--results', type=Path, required=True,
        help='output directory; must not be an existing committed evidence tree')
    a.add_argument('--scratch', type=Path, default=None,
        help='where PCM is written and deleted; defaults to a temp dir')
    a.add_argument('--start-seconds', type=float, default=5.0)
    a.add_argument('--seconds', type=float, default=10.0)
    a.add_argument('--timeout', type=int, default=1800)
    a.add_argument('--require-media', action='store_true')
    args = a.parse_args()
    for p in ('sox', 'reference'):
        if not getattr(args, p).is_file():
            a.error(f'{p} not found: {getattr(args, p)}')
    if args.seconds <= 0 or args.start_seconds < 0:
        a.error('start-seconds must be >= 0 and seconds > 0')
    if args.media_root is None and not args.self_encoded:
        a.error('supply --media-root, --self-encoded, or both')
    if args.self_encoded and args.self_sources < 2:
        a.error('--self-sources must be at least 2 so a negative control exists')
    tracks = []
    if args.media_root is not None:
        root = args.media_root.resolve()
        if not root.is_dir():
            a.error('media directory missing')
        tracks = sorted(p for p in root.rglob('*')
                        if p.is_file() and p.suffix.lower() == '.dsf')
        if not tracks and args.require_media:
            a.error('no .dsf media found')

    import tempfile
    scratch_ctx = (tempfile.TemporaryDirectory(prefix='p21-reader-')
                   if args.scratch is None else None)
    scratch = Path(scratch_ctx.name) if scratch_ctx else args.scratch
    scratch.mkdir(parents=True, exist_ok=True)

    ref_version = subprocess.run([str(args.reference), '-version'],
        capture_output=True, text=True).stdout.splitlines()[:1]
    runner_sha, sox_sha = sha(Path(__file__)), sha(args.sox)

    # Unified work list. Commercial media is DSD512 DSF only, so the
    # self-encoded entries are what reach DFF at either clock and DSD1024 at
    # all. Provenance travels with every case and is never averaged away.
    work = []
    for i, track in enumerate(tracks):
        control = tracks[(i + 1) % len(tracks)] if len(tracks) > 1 else None
        work.append(dict(path=track, rate=None, container='dsf',
                         provenance='commercial', control=control, group=f'c{i}'))
    if args.self_encoded:
        made = make_sources(args.sox, scratch, args.seconds, args.self_sources,
                            from_tracks=tracks, start=args.start_seconds,
                            timeout=args.timeout)
        for path, rate, container, k, origin in made:
            peer = next((q for q, r2, c2, k2, _o in made
                         if r2 == rate and c2 == container and k2 != k), None)
            work.append(dict(path=path, rate=rate, container=container,
                             provenance='self-encoded', control=peer,
                             stimulus_origin=origin,
                             group=f's{k}-{rate}-{container}'))

    cases, qualified = [], {}
    for item in work:
        track = item['path']
        tsha = sha(track); token = tsha[:20]
        control_track = item['control']
        for flag, pid, out_map in PROFILES:
            native = item['rate']
            if native is None:  # commercial: ask the file what clock it is
                probe = subprocess.run([str(args.sox), '--i', '-r', str(track)],
                                       capture_output=True, text=True)
                try:
                    native = int(float(probe.stdout.strip()))
                except ValueError:
                    native = 22579200
            out_hz = out_map.get(native)
            if out_hz is None:
                continue
            tag = f'{token}-{item["container"]}-{pid}'
            ours = scratch / f'{tag}-ours.f64'
            refp = scratch / f'{tag}-ref.f64'
            ctlp = scratch / f'{tag}-ctl.f64' if control_track else None
            started = time.monotonic()
            # self-encoded clips are only `seconds` long, so start at zero
            start = args.start_seconds if item['provenance'] == 'commercial' else 0.0
            span = args.seconds if item['provenance'] == 'commercial' else args.seconds / 2
            rc_o, err_o = decode_ours(args.sox, track, flag, out_hz, ours,
                                      start, span, args.timeout)
            rc_r, err_r = decode_reference(args.reference, track, out_hz, refp,
                                           start, span, args.timeout)
            if ctlp is not None:
                decode_reference(args.reference, control_track, out_hz, ctlp,
                                 start, span, args.timeout)
            metrics, why = (None, 'decode failed') if (rc_o or rc_r) else \
                compare(ours, refp, ctlp, out_hz)
            passed, reasons = judge(metrics)
            if why:
                reasons = [why] + reasons
                passed = False
            row = dict(schema='P21/independent-reader-case/1',
                status='PASS' if passed else 'FAIL',
                source_sha256=tsha, source_id=token, source_bytes=track.stat().st_size,
                media_provenance=item['provenance'], container=item['container'],
                stimulus_origin=item.get('stimulus_origin', 'licensed-original'),
                native_hz=native, capability_row=f'{item["container"]}-read-{native}',
                profile_id=pid, cli_decode_flag=flag or '(default)',
                output_hz=out_hz, start_seconds=args.start_seconds,
                seconds=args.seconds,
                sox_sha256=sox_sha, runner_sha256=runner_sha,
                reference=ref_version, reference_exit=rc_r, sox_exit=rc_o,
                sox_stderr_tail=err_o, reference_stderr_tail=err_r,
                thresholds=dict(min_pearson=MIN_PEARSON,
                    max_level_delta_db=MAX_LEVEL_DELTA_DB,
                    min_channel_margin=MIN_CHANNEL_MARGIN,
                    max_control_pearson=MAX_CONTROL_PEARSON),
                metrics=metrics, failure_reasons=reasons,
                elapsed_seconds=time.monotonic() - started,
                establishes='container parse, interleave, bit order, alignment, gross gain',
                does_not_establish='filter equivalence, device interoperability')
            atomic(args.results / 'cases' / f'{tag}.json', row)
            cases.append(row)
            qualified.setdefault((item['provenance'], native, item['container'], pid),
                                 []).append(passed)
            print(row['status'], item['provenance'][:4], native, item['container'],
                  pid, flush=True)
            for p in (ours, refp, ctlp):
                if p is not None and p.is_file():
                    p.unlink()
    if scratch_ctx:
        scratch_ctx.cleanup()

    # Per capability row, and never blended across provenance. A row backed
    # only by media we wrote ourselves is a weaker claim than one backed by
    # commercially mastered files, and the evidence has to say which it is.
    rows_qualified, rows_by_provenance = {}, {}
    for (prov, native, container, pid), results in qualified.items():
        row = f'{container}-read-{native}'
        rows_qualified.setdefault(row, []).extend(results)
        rows_by_provenance.setdefault(row, set()).add(prov)
    rows_qualified = {r: all(v) and bool(v) for r, v in rows_qualified.items()}
    rows_by_provenance = {r: sorted(s) for r, s in rows_by_provenance.items()}

    any_fail = any(c['status'] == 'FAIL' for c in cases)
    gate = 'PASS' if (cases and not any_fail) else ('FAIL' if any_fail else 'UNRUN')
    report = dict(schema='P21/independent-reader-evidence/1',
        independent_reader_and_audio_reference_gate=gate,
        tracks=len({c['source_sha256'] for c in cases}), case_count=len(cases),
        profiles_qualified={pid: (bool(v) and all(v)) for pid, v in
            {k[3]: [x for kk, vv in qualified.items() if kk[3] == k[3] for x in vv]
             for k in qualified}.items()},
        rows_qualified=rows_qualified,
        rows_by_provenance=rows_by_provenance,
        media_sha256=sorted({c['source_sha256'] for c in cases}),
        case_receipts={f'cases/{c["source_id"]}-{c["profile_id"]}.json': c['status']
                       for c in cases},
        reference=ref_version, sox_sha256=sox_sha, runner_sha256=runner_sha,
        host=dict(node=platform.node(), os=platform.platform(), machine=platform.machine()),
        thresholds=dict(min_pearson=MIN_PEARSON, max_level_delta_db=MAX_LEVEL_DELTA_DB,
            min_channel_margin=MIN_CHANNEL_MARGIN, max_control_pearson=MAX_CONTROL_PEARSON),
        establishes='A second independently written reader recovers the same audio '
                    'from the same file: container parse, interleave, bit order, '
                    'alignment and gross gain.',
        does_not_establish='Filter equivalence; the reference reconstructs differently '
                    'by design. Device interoperability. For rows backed only by '
                    'self-encoded media: real-world header variation, unusual chunk '
                    'order, and DST-compressed DFF, since such files exercise only '
                    'the shapes our own writer emits.',
        provenance_note='A row listed under self-encoded alone rests on a '
                    'weaker claim than one under commercial, in two ways. It '
                    'shows our reader agrees with an independent one on '
                    'well-formed files at that clock, not that it handles files '
                    'in the wild. And it is an easier test: the stimulus was '
                    'decoded through our own filter before being re-encoded, so '
                    'it carries only content that filter passes. Measured '
                    'agreement is accordingly better on self-encoded cases than '
                    'on commercial ones, which is a property of the stimulus '
                    'rather than evidence of a better-behaved reader.',
        device_claims=[])
    atomic(args.results / 'independent-reader-evidence.json', report)
    print('INDEPENDENT_READER', gate, report['tracks'], 'tracks', len(cases), 'cases')
    return 0 if gate == 'PASS' or not args.require_media else 1

if __name__ == '__main__':
    raise SystemExit(main())
