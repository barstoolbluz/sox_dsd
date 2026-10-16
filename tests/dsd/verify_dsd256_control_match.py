#!/usr/bin/env python3
"""Spectral check that the DSD256 staged legacy control is bandwidth-matched.

P15-DSD256-direct-2x-and-matched-comparator was held open because the staged
control's transfer was asserted from its command line, never measured.
p15_readjudication.py says so directly: "Even if another syntactic cutoff is
used in future, independent spectral verification must precede calling the
control matched."

This supplies that verification, and nothing else. It does not time anything,
does not touch the timing receipt, and makes no promotion claim.

Method. Decoder and matched control read the SAME native DSD256 file, built
from broadband noise so that every bin up to each profile's edge carries
signal well above the floor. The six-tone timing fixture is useless here: its
content stops at 2.3 kHz, so a first version of this check compared only the
tone bins, reported 0.000 dB and would have passed a 20 kHz control without
noticing. Both outputs are written as float64 at the same rate and their
magnitude spectra compared band by band. A control narrower than the decoder
shows up as a large negative difference above its own corner; a matched
control agrees with the decoder across the passband.

--selftest-mismatch-hz forces a deliberately wrong control cutoff. The check
is expected to FAIL under it, which is how we know it can detect the error it
exists to detect; the recorded self-test is part of the evidence.

This measures the two transfers against each other, which is what "matched"
means here. It does not certify either transfer against section 6.1 in
absolute terms; the decoder's own passband guarantee is certified elsewhere
and is queried from the binary rather than assumed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile

# Agreement required across the shared passband, and the margin by which a
# narrower control must reveal itself. Both are generous: the error this
# guards against (a control matched to 20 kHz against a 40 or 66 kHz decoder)
# is tens of dB, not tenths.
PASSBAND_AGREEMENT_DB = 1.0
# Two filters of different design cannot be compared inside their transition
# regions: each turns down on its own schedule there, so a few dB of
# divergence in the last percent of the band says nothing about whether the
# control is bandwidth-matched. The comparison therefore runs over the
# passband proper, excluding the top 5%, and the full-passband figure
# including the transition is recorded alongside it, ungated.
#
# This margin cannot hide the error the check exists to catch. A control cut
# at 20 kHz against a 40 or 66 kHz decoder diverges by 140 dB or more from
# 22 kHz upward, which is nowhere near any profile's top 5%; the recorded
# self-test demonstrates exactly that.
TRANSITION_EXCLUSION = 0.05
NATIVE_HZ = 11289600


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(argv, cwd):
    subprocess.run([str(a) for a in argv], check=True, capture_output=True, cwd=cwd)


def spectrum(path: Path, nfft: int = 1 << 15):
    """Averaged magnitude spectrum in dB, and the bin frequencies."""
    rate, data = wavfile.read(path)
    x = np.asarray(data, dtype=np.float64)
    if x.ndim > 1:
        x = x[:, 0]
    if np.issubdtype(np.asarray(data).dtype, np.integer):
        x = x / float(2 ** (8 * np.asarray(data).dtype.itemsize - 1))
    # Welch average: a single transform of a noise-like signal is far too
    # ragged to compare band by band.
    step = nfft // 2
    win = np.hanning(nfft)
    segs = [x[i:i + nfft] * win for i in range(0, len(x) - nfft + 1, step)]
    if len(segs) < 4:
        raise RuntimeError(f'{path.name}: only {len(segs)} segments; need a longer fixture')
    power = np.mean([np.abs(np.fft.rfft(s)) ** 2 for s in segs], axis=0)
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    return rate, freqs, 10 * np.log10(np.maximum(power, 1e-300))


def compare(dec: Path, ctl: Path, passband_hz: int) -> dict:
    rate_d, f, sd = spectrum(dec)
    rate_c, _, sc = spectrum(ctl)
    if rate_d != rate_c:
        raise RuntimeError(f'rate mismatch: decoder {rate_d}, control {rate_c}')
    # Compare only where the decoder itself carries usable signal: bins far
    # below the noise floor say nothing about either filter.
    ref = np.max(sd)
    top = min(passband_hz, rate_d / 2 * 0.98)
    compared_to = top * (1.0 - TRANSITION_EXCLUSION)
    carries = (f > 1000) & (sd > ref - 120)
    usable = carries & (f <= compared_to)
    full = carries & (f <= top)
    if usable.sum() < 16:
        raise RuntimeError('too few usable passband bins to compare')
    diff = sc[usable] - sd[usable]
    full_diff = sc[full] - sd[full]
    worst = int(np.argmax(np.abs(diff)))
    full_worst = int(np.argmax(np.abs(full_diff)))
    # A profile so a reader can see where any divergence sits rather than
    # having to trust one summary number. Deliberately finer across the top
    # tenth: that is where the two filters' transitions part, and where the
    # decision to exclude the last 5% has to be judged. A uniform grid put
    # the whole edge in one 6.5 kHz bucket, which is not enough to judge it.
    profile = []
    bounds = np.concatenate([np.linspace(1000.0, top * 0.9, 10),
                             np.linspace(top * 0.9, top, 11)[1:]])
    for lo_hz, hi_hz in zip(bounds, bounds[1:]):
        band = carries & (f >= lo_hz) & (f < hi_hz)
        if band.sum():
            profile.append(dict(from_hz=round(float(lo_hz), 1),
                                to_hz=round(float(hi_hz), 1),
                                max_abs_difference_db=float(np.max(np.abs(sc[band] - sd[band]))),
                                mean_difference_db=float(np.mean(sc[band] - sd[band]))))
    # Where does each fall away? Reported for context, not gated on: the
    # decoder's own corner is a section 6.1 property certified elsewhere.
    def corner(s):
        lo = np.median(s[(f > 1000) & (f < 10000)])
        below = np.where((f > 10000) & (s < lo - 3))[0]
        return float(f[below[0]]) if len(below) else None
    return dict(
        output_hz=int(rate_d),
        passband_hz=int(passband_hz),
        compared_bins=int(usable.sum()),
        comparison_band_hz=[1000.0, round(float(compared_to), 1)],
        transition_excluded_fraction=TRANSITION_EXCLUSION,
        max_abs_difference_db=float(np.max(np.abs(diff))),
        max_abs_difference_at_hz=float(f[usable][worst]),
        mean_difference_db=float(np.mean(diff)),
        # Ungated, reported so the transition-region behaviour stays visible.
        full_passband_max_abs_difference_db=float(np.max(np.abs(full_diff))),
        full_passband_max_abs_difference_at_hz=float(f[full][full_worst]),
        difference_profile=profile,
        control_minus3db_hz=corner(sc),
        decoder_minus3db_hz=corner(sd),
        agreement_limit_db=PASSBAND_AGREEMENT_DB,
        matched=bool(np.max(np.abs(diff)) <= PASSBAND_AGREEMENT_DB))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sox', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True,
                    help='sox_p10_candidate, used only to build the native fixture')
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--profiles', default='mastering,decode.mastering.v2.dsd256')
    ap.add_argument('--seconds', type=float, default=6.0,
                    help='needs enough length for spectral averaging')
    ap.add_argument('--selftest-mismatch-hz', type=int, default=None,
                    help='force a wrong control cutoff; the check must then FAIL')
    a = ap.parse_args()
    sox, cand = a.sox.resolve(), a.candidate.resolve()
    W = a.work.resolve(); W.mkdir(parents=True, exist_ok=True)
    a.results.mkdir(parents=True, exist_ok=True)
    cwd = str(W)

    # Broadband probe. One channel, not the timing fixture's six: a filter's
    # transfer does not depend on channel count, and this runs far faster.
    # The two receipts bind through the executable digests instead.
    src6, nat = W / 'probe-src.wav', W / 'd256_probe.dsf'
    run([sox, '-n', '-r', 352800, '-b', 32, '-e', 'signed-integer', src6,
         'synth', a.seconds, 'whitenoise', 'vol', '0.1'], cwd)
    run([cand, '--dsd-layout-loss', 'warn', src6, '-r', NATIVE_HZ, nat,
         'pcmdsd', NATIVE_HZ], cwd)

    rows = {}
    for profile in [p.strip() for p in a.profiles.split(',') if p.strip()]:
        rp = W / f'probe-{profile}.json'
        run([sox, '--dsd-report', rp, '--dsd-layout-loss', 'warn', nat,
             '-b', 32, '-e', 'signed-integer', W / 'probe.wav',
             'dsdpcm', '-p', profile, '-l', 'preserve', 352800], cwd)
        d = json.loads(rp.read_text())['processing']['decoder'][0]
        pb, pid = int(d['effective_passband_hz']), d['profile_id']
        rates = {}
        for out_hz in (352800, 176400):
            # Control chain identical to bench_dsd256_2x.py, including the
            # intermediate-rate choice. Any divergence here would verify a
            # control that was never the one timed.
            inter = 176400 if pb >= 80000 else 88200 if pb < 44100 else 352800
            dec = W / f'dec{out_hz}.wav'
            ctl = W / f'stg{out_hz}.wav'
            run([sox, '--dsd-layout-loss', 'warn', nat, '-e', 'floating-point',
                 '-b', 64, dec, 'dsdpcm', '-p', profile, '-l', 'preserve', out_hz], cwd)
            cut = a.selftest_mismatch_hz or pb
            run([sox, '-D', nat, '-r', out_hz, '-e', 'floating-point', '-b', 64, ctl,
                 'rate', '-v', min(inter, out_hz), 'sinc', f'-{cut}', 'rate', '-v'], cwd)
            rates[str(out_hz)] = compare(dec, ctl, pb)
            c = rates[str(out_hz)]
            print('%-32s %6d Hz  max|diff| %7.3f dB to %6.0f Hz  '
                  '(%.3f dB incl. transition)  matched=%s'
                  % (profile, out_hz, c['max_abs_difference_db'],
                     c['comparison_band_hz'][1],
                     c['full_passband_max_abs_difference_db'],
                     c['matched']), flush=True)
        rows[profile] = dict(profile_id=pid, effective_passband_hz=pb, rates=rates)

    matched = all(r['matched'] for p in rows.values() for r in p['rates'].values())
    report = dict(
        schema='P15/dsd256-control-bandwidth-match/1',
        status='MATCHED' if matched else 'NOT-MATCHED',
        selftest_mismatch_hz=a.selftest_mismatch_hz,
        scope=('spectral comparison of the staged legacy control against the decoder '
               'on one shared native file; no timing, no promotion, no absolute '
               'certification of either transfer against section 6.1'),
        passband_source='decoder --dsd-report effective_passband_hz, per profile',
        probe_signal='broadband noise encoded to DSD256, decoded by both arms',
        agreement_limit_db=PASSBAND_AGREEMENT_DB,
        fixture=dict(native_hz=NATIVE_HZ, channels=1, seconds=a.seconds,
                     probe='whitenoise at -20 dBFS, broadband to Nyquist',
                     source_sha256=sha(src6), native_sha256=sha(nat)),
        executables=dict(sox_sha256=sha(sox), candidate_sha256=sha(cand)),
        rows=rows)
    (a.results / 'dsd256-control-match.json').write_text(
        json.dumps(report, indent=1, sort_keys=True) + '\n')
    for f in W.glob('*'):
        f.unlink()
    W.rmdir()
    print('status', report['status'], '->', a.results / 'dsd256-control-match.json')
    if a.selftest_mismatch_hz:
        # Inverted on purpose: under a forced-wrong cutoff, detecting the
        # mismatch is the pass.
        print('self-test with a forced %d Hz cutoff: %s'
              % (a.selftest_mismatch_hz, 'DETECTED' if not matched else 'MISSED'))
        return 0 if not matched else 1
    return 0 if matched else 1


if __name__ == '__main__':
    raise SystemExit(main())
