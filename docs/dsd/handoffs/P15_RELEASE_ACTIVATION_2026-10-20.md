# P15 release activation, 2026-10-20

Operator decision, taken after the design authority recorded its engineering
acceptance on 2026-10-19 and stated that completion of the outstanding
formal-proof obligation is no longer required for release.

Two changes, both activation rather than DSP.

## 1. v2 is the decode default

`src/dsd.c` and `src/dsd_public.c`. The effect parser is shared with the
encoder and both MASTERING enums are zero, so the decode default is
conditioned on `is_encode` and the encoder keeps the value it had.

| native | profile | effective passband |
|---|---|---|
| 2822400 | `decode.mastering.v2.dsd64` | 25000 Hz |
| 5644800 | `decode.mastering.v2.dsd128` | 48000 Hz |
| 11289600 | `decode.mastering.v2.dsd256` | 66000 Hz |

v1 remains on `-p mastering`, still 40000 Hz at DSD256. Coefficients
untouched.

## 2. The encoder is activated

`src/pcmdsd.c`: the three `encode.mastering.v1` profiles now carry
`qualified=1`. Until now the shipping binary refused every DSD encode with
"P10 mastering profile is unqualified; qualification evidence blocks
activation", and only the `sox_p10_candidate` test wrapper could encode.

Coefficients, guards and certificate digests are unchanged. The flag is the
only edit.

## Verified end to end with the stock binary

Encode at all three native rates, 1.4 / 2.8 / 5.7 MB outputs, then decode
back through the v2 default: `decode.mastering.v2.dsd256`, 66000 Hz,
5,644,880 bytes out, maximum amplitude 0.150 and RMS 0.106 on a 0.3-scaled
two-tone source. `make check-dsd` on the shipping build: 92 PASS, 0 FAIL.
Its exit 2 is the long-standing out-of-tree `soxconfig.h` path bug, not a
test failure.

## Consequence for the evidence tooling

Two of the three edited files, `src/dsd.c` and `src/dsd_public.c`, are in
the 35-entry pinned source set in `p15_src_bound_operator.py`.
`src/pcmdsd.c`, carrying the encoder activation flag, is not pinned.

Those two entries therefore no longer match the fingerprint stamped on the
stage-bound operator receipts, `source_operators` refuses with
`UnboundOperator`, and the binding suites fail. The certificates remain
valid for the source they were derived from, which is in git history and
immutable; what is lost is the ability to re-verify them mechanically
against the current checkout. Restoring that means re-deriving the stage
bindings against the new source, as was needed when the SRC optimization
changed `rate_poly_fir0.h`.

This concerns receipt provenance, not the audio path. Encode and decode work
with the stock binary and `make check-dsd` on the shipping build is 92 PASS,
0 FAIL.
