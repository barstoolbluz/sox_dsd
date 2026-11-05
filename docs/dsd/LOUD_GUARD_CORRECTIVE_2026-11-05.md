# Loud PCM state-guard corrective (2026-11-05)

**Follow-on D-01 fidelity correction:** The 0.45-only warning policy in this
original delivery distorted valid, high-amplitude PCM. The current source
retains the 0.45 ceiling but additionally applies a constant 0.9 linear gain
in the *implicit* DSD128/256 default. Explicit fixed, measured, and strict
modes retain their original gain semantics. This document preserves the
original reproduction record; see
[the D-01 corrective](LOUD_GUARD_D01_FIDELITY_CORRECTIVE_2026-11-05.md)
for current default behavior and new test results. Bit identity claims below
refer to the first corrective, not the follow-on default-gain change.

Base: `0dd7ad224`. Source evidence:
`SoX_DSD_Loud_Guard_2026-11-04.tar.zst`, including
`observed/synth_guard.sh`, `observed/synth/results.tsv`, and the historical
1.0.4 comparison. This is a release-scoped 1.0.x corrective, not a new
modulator qualification or proof of unbounded input stability.

## Answer to the supplied Ask

The unqualified, bounded-recovery research encoder is **not the only possible
remedy** and is not appropriate to introduce as an automatic 1.0.x path.
The existing CLI clips reconstructed values exceeding the 0.5 reference
amplitude, but the DSD128/DSD256 mastering-v1 modulator can still accumulate
state until a certified guard is exceeded. The trigger depends on **level,
duration at that level, signal content, and native rate**. An exposure of
0.35 seconds is enough for one DSD256 square wave; another fails only after
18 seconds. Even a 0.48 ceiling that passes a 20-second case can fail after
36 seconds. The DSD64 synthetic cases did not fail; that is not a general
immunity claim.

The smallest release corrective lowers only the **default warning/clipping
ceiling** for the two affected native rates from 0.5 to **0.45**. This
is 0.91515 dB below the original input-reference ceiling. DSD64, DSD512,
and DSD1024 retain 0.5. The CLI clips and warns instead of aborting due to
interpolation overshoot; it does not suppress the modulator's state guard.
No unqualified recovery algorithm, SDM recurrence, FIR coefficient, guard,
certificate, runtime dispatcher, or strict/core qualification path changed.

This is an empirically tested operating bound **for the supplied witnesses**,
not a proven upper bound for arbitrary input or programme duration. The
state guard still fails closed when necessary. Neither a different modulator
nor any dynamically state-dependent processing is hidden in default mode.

## Independently reproduced observations

The supplied `observed/synth_guard.sh` was run against the original
`0dd7ad224` and the historical base (the SoX DSD 1.0.4 release
`ddc03469e`). All seven generated input WAV SHA-256 digests matched the
supplied receipts. The synthetic matrix comprised seven deterministic
stereo signals, three native rates, and four configurations, i.e. **84
runs**. The initial command started 84 conversions simultaneously and
the container OOM-killed ten baseline runs. Repeating those ten serially
produced **84/84 identical exit statuses, clip counts and failure
messages** relative to `observed/synth/results.tsv`. The seven default
`0dd7ad224` failures also occurred at the **same native frame indices**.
An exit 137 caused by host memory contention must not be classified as an
encoder failure.

The default failures at 20 seconds were:

| Rate | Failure witnesses |
| --- | --- |
| DSD64 (2,822,400 Hz) | 0 of 7 |
| DSD128 (5,644,800 Hz) | `brown+9`, `tri100+6` |
| DSD256 (11,289,600 Hz) | `brown+3`, `brown+9`, `saw60+6`, `sq100+3`, `sq1k+3` |

Additional pre-correction control runs showed that a 0.25 dB fixed cut
**delayed**, but did not eliminate, the earliest `sq1k+3` DSD256 guard
failure within 20 seconds. A 0.5 dB cut passed that 20-second case.
The exploratory **0.48 default clipping ceiling** still failed DSD256
`sq100+3` at native frame 408,680,964 (36.2 seconds), demonstrating why
20-second acceptance alone was inadequate.

On the **0.45 corrective**:

- All **21 default conversions** from the 20-second synthetic corpus passed,
  including all seven formerly failing conversions.
- DSD256 `sq100+3` passed 120 seconds and **600 seconds** continuously.
- DSD128 `brown+9` passed **300 seconds** continuously.
- Original fixed, strict and measured-headroom regression cases continue to
  pass. In this **earlier** corrective, `--headroom 0` was bit-identical
  to the default; it now explicitly overrides the implicit 0.9 gain.
  `--auto-headroom`
  with strict mode avoids clipping and applies the same attenuation to all
  channels.
- Ten deliberately non-clipping or strict/attenuated conversion cases were
  compared byte-for-byte to a **separate rebuild of `0dd7ad224`**: PCM-only,
  quiet PCM at all five DSD rates, loud DSD64, and attenuated/strict DSD128
  and DSD256. All ten complete output files had identical SHA-256 hashes.

The archive reports six state-guard failures among **1,200 real-track
conversions** on `0dd7ad224`. The corresponding recordings were not supplied,
so their corrected outputs could **not** be independently tested; the
supplied TSV receipts are historical observations only.

## Behavior and trade-offs

- Normal `sox in.wav -r dsd256 out.dsf` remains a one-pass streaming
  conversion. The ceiling is selected once per encoder context; the existing
  per-native-sample clipping comparison uses that value. No additional
  buffer, input reread, state scan or recovery loop is added to default mode.
- The lower ceiling can clip samples that were previously accepted, even
  for some nominally sub-0 dBFS recordings. This changes their native DSD
  bits. The CLI reports the number of clipped *interpolated* samples and
  identifies the actual clipping ceiling. It does not falsely promise
  identical output to 1.0.4 in affected material.
- `--auto-headroom` runs its existing bounded-memory, temporary-file scan
  and now scales the **maximum post-interpolation peak** to the corresponding
  0.45/0.5 ceiling. This additional I/O and scan remain opt-in. It avoids
  local hard clipping for properly measured finite inputs, while retaining
  the ordinary modulator guard and qualified signal path.
- `--dsd-clip error` retains the original 0.5 input-overload rejection
  threshold and state checks. The `--auto-headroom --dsd-clip error`
  combination targets the lower ceiling, without introducing clipping.
- `--plan` exposes `encoder.warning_clip_ceiling` (null in strict mode) and
  `--report` exposes each executed encoder channel's `clip_ceiling_applied`
  (null when clipping is disabled). Existing report fields and the warning
  text remain valid; these are additive diagnostic fields.
- Native DSD repacking, non-PCM paths, existing PCM effects, profile
  selection, and the qualified coefficients are unaffected.

**Residual risk:** The envelope is empirical. There is no general
closed-form proof that 0.45 prevents every state excursion indefinitely,
and the 1.0.x scope explicitly retains a follow-on certified-modulator
redesign. Users who need an unclipped audio output should use
`--auto-headroom`; production users can select `--dsd-clip error` to
reject overloads and receive fail-closed diagnostics.

## Build and tests

```sh
autoreconf -fi
./configure
make -j4
make check
make check-dsd-cli
make check-dsd-loud-encode
make check-dsd-loud-guard
python3 tests/dsd/test_loud_guard.py --sox src/sox --quick
python3 tests/dsd/test_loud_guard.py --sox src/sox --stress-seconds 120
make check-sdm-guard-policy
make check-dsd-optimization
```

`check-dsd-loud-guard` creates exactly the seven deterministic fixtures and
checks all 21 native-rate/default conversions. It also tests a short
state-guard witness, strict rejection and cleanup, explicit zero-headroom
override, and shared-channel measured headroom. The stress option is
**opt-in** because it creates long signals and DSF outputs. Its fixture
construction uses a fixed SoX random seed (`-R`), not external media.

For independent baseline replay, run the supplied shell script in the
original guard package with `BASE_SOX` and `NEW_SOX` pointing to the
corresponding builds. **Memory-limited hosts should serialize the
conversion cases** rather than launch all 84 in parallel.

The historical `check-dsd-p15-r3` coefficient regeneration check failed on
both unchanged original builds with an environment-dependent numerical
mismatch; that baseline issue does not justify regenerating, rewriting or
requalifying immutable coefficient evidence here.
