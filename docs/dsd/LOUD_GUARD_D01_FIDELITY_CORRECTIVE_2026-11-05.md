# Loud guard D-01: prevent default clipping distortion (2026-11-05)

Base: `cli-legacy-route-corrective` at `580f930` (first loud-guard
corrective). This is a follow-on correction, not a modulator redesign.

## Confirmed defect

At DSD128/256, a 0.95-FS, 1 kHz PCM sine has reconstructed peak about 0.475
in reference-0.5 units. The previous default clipped every native sample
above 0.45 even though the original `3ed2434` could encode the signal
without clipping. The independent audit measured ~21% clipped native samples
and -33.8 dBc THD in the default DSD128/256 output, against ~-155 dBc
on `3ed2434`. This is a real audio-fidelity regression.

## Revised one-pass policy

- For the **implicit** DSD128/256 default (`--dsd-clip warn`, no headroom
  flag), multiply all interpolated samples by **0.9** (exact ratio 0.45/0.5)
  before the existing 0.45 clip-and-warn check. This is **constant linear
  attenuation**, -0.9151498112 dB, not waveform clipping, dynamic
  compression, or adaptive gain. The modulator, coefficients, and state
  guards are untouched. Residual reconstructed overs still clip and warn.
- Other native DSD rates (DSD64/512/1024) retain unity gain and their 0.5
  warning ceiling. Core qualification, test candidate, and strict paths
  remain unchanged. Explicit `--headroom DB` applies exactly DB dB of cut
  **instead of** the implicit 0.915 dB (including `--headroom 0`).
- `--auto-headroom` remains opt-in and measures the entire interpolated
  signal across all channels with bounded RAM/PCM-rate temporary files.
  It selects the minimum common gain needed for the warning ceiling, so
  quiet material remains at unity gain. `--dsd-clip error` selects strict,
  unattenuated fail-closed behavior unless an explicit headroom option is
  also requested.
- `--plan` exposes `encoder.planned_linear_gain`: 0.9 at the affected
  default, 1 at strict unity, the requested gain for fixed headroom, and
  null in auto mode until measurement completes. `--report` records the
  actual cut in each channel's existing `headroom_applied_db` field and
  the residual clip ceiling and counts.

**Important level consequence:** The fast default reduces quiet DSD128/256
programmes by 0.915 dB as well. This is a deliberate amplitude change,
not a claim of bit identity. A one-pass encoder cannot know the full
programme peak before encoding it. Avoiding both global attenuation and
local nonlinear limiting requires a full peak scan (available via
`--auto-headroom`) or separate qualification of another modulator. No
more complex limiter has been introduced to conceal that tradeoff.

**Stability limitation:** A 0.45 clipping ceiling is empirically supported
by finite tests, not a mathematical guarantee. The fail-closed state guard
remains active for any waveform that exceeds its qualified bounds.

## Regression and validation

The default 2-second IEEE float32 stereo 1 kHz/0.95-FS sine now reports
**zero** clipped samples at both rates. After DSD reconstruction to
88.2 kHz PCM, a coherent 1.5-second interval yields about **-164.7 dBc
THD** at DSD128 and DSD256 in the reference build; the measured
fundamental amplitude is about 0.4275 (0.95 * 0.5 * 0.9). This tests
actual encoded and decoded audio, not just an uncommitted input buffer.
The assertion is intentionally tolerant of normal compiler/ISA differences
(THD < -100 dBc); it detects the previous ~-34 dBc failure.

Run:

```sh
make check-dsd-loud-encode
python3 tests/dsd/test_loud_guard.py --sox src/sox --quick
make check-dsd-loud-guard
make check-dsd-cli
make check-sdm-guard-policy
LD_LIBRARY_PATH="$PWD/src/.libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" make check-dsd DSD_PHASE=P18
```

The original seven synthetic witnesses and longer stress tests must continue
to pass with the revised default. Real-track source recordings referenced
in the original report were not provided and cannot be retested here.
