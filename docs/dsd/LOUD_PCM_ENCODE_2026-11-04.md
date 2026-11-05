# Loud PCM-to-DSD encoding: implementation record (2026-11-04)

Source baseline: commit `179b434ad`.
See [Using SoX DSD](USING_SOX_DSD.md) for the user interface.

**Update (2026-11-05):** The original 0.5 clip ceiling and auto-headroom
formula recorded below are historical. The DSD128/256 warning ceilings
were changed to 0.45 after sustained state-guard failures. The follow-on
fidelity correction also applies a default constant 0.9 gain at DSD128/256;
explicit headroom and strict mode do not inherit that gain. See
[the loud guard corrective](LOUD_GUARD_CORRECTIVE_2026-11-05.md) and
[the D-01 fidelity corrective](LOUD_GUARD_D01_FIDELITY_CORRECTIVE_2026-11-05.md).
A later change the same day extended the 0.45 ceiling and the 0.9 default gain
to every DSD rate (see the D-01 record).

## Decision and scope

* The normal composite encoder accepts finite inter-sample PCM overshoots,
  clamps only samples above the qualified mastering SDM input envelope of
  magnitude 0.5, and warns once per affected channel with a saturated count.
* `--dsd-clip error` retains fail-closed behavior for any interpolation
  overload. Numeric, nonfinite, and SDM state/bound checks remain fatal for
  **all** settings; an infinity or NaN cannot be converted into a valid sample
  by the clipping path.
* `--headroom DB` (0..120) applies a fixed post-interpolation attenuation,
  identically across channels. `--auto-headroom` applies the smallest necessary
  common attenuation, without amplification. Both require a qualified
  composite PCM-to-DSD path, and neither changes source files.
* The core qualification and candidate-create APIs stay strict by default;
  only the explicit CLI effect policy enables clip-and-warn. No FIR, SRC,
  coefficients, profile ID, SDM kernel, or bounds were altered.

## Measured headroom implementation

The first pass uses the **same** source-rate converter, certified prefilter,
second interpolator, reference scaling, and finite EOF handling as the
actual encoder, but skips the SDM recurrence. It measures the maximum absolute
native-rate floating-point value for each channel. SoX stores the
encoder-input-rate signed 32-bit PCM samples in one seekable temporary file
per channel, with fixed-size streaming buffers. This works with pipes and
avoids holding whole programmes or native-rate samples in RAM.

At upstream EOF, effect-flow 0 finishes **all** channel scans, computes the
largest channel peak `P`, and chooses `gain=1` when `P<=0.5`, otherwise
`gain=(0.5*(1-1e-12))/P`. This 1e-12 relative guard is below 1e-10 dB and
absorbs finite-precision multiplication differences between passes. The
normal qualified encoder then starts anew with the chosen common gain and
replays the PCM-rate temporary files. It does not preserve simulated SDM
state from the scan, and it cannot publish native output before measurement
has completed. A scan error or replay error aborts processing.

`--plan` discloses headroom mode/request. `--report` records the applied dB
and the clipped native sample count per encoder channel, a saturated
`clipping.encoder_interpolation` aggregate, and a report warning on clipping.
The scale convention and applied attenuation are separate fields.

## Reproduction and validation

From a checkout containing this change:

```sh
autoreconf -fi
./configure
make -j4
make check
make check-dsd-cli
make check-dsd-loud-encode
make check-sdm-guard-policy
make check-dsd-optimization
```

The loud-master acceptance script generates its own 24-bit stereo source
with <0 dBFS *sample* peaks but >0 dBFS *interpolated* peaks. It tests
DSD64/128/256 clip-and-warn, strict refusal and partial-output cleanup,
fixed headroom, minimum measured cut with shared stereo gain, report/plan
consistency, unchanged bitstreams for safe programmes, explicit/automatic
encoder agreement, stdin pipes, short/empty source tails, qualified
DSD512/1024 execution, multithreaded determinism, and invalid/inapplicable
controls. All fixtures are deterministic and require no copyrighted audio.

The historical P05 `norm_native_overload_reject` test now requests
`--dsd-clip error`. This keeps its strict numeric rejection check meaningful
without assuming the old default policy. Historical qualification receipts
and coefficient manifests were not changed.

For the broader P18 gate on some uninstalled libtool builds, use
`LD_LIBRARY_PATH="$PWD/src/.libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" make check-dsd DSD_PHASE=P18`.
Without this path, Python subprocesses which execute `.libs/dsd_test_io`
directly may fail dynamic loading even when the source and binary are valid.

The unrelated P15-R3 coefficient regeneration check can report a manifest
mismatch when the local mpmath version differs from the archived 1.3.0.
The source package already documents the baseline mismatch, and the
coefficient headers remain byte-identical; do not silently rewrite numerical
qualification manifests to conceal an environment-dependent receipt.
