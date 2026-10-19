# DSD256 P/S-matched re-certification against current binaries (2026-10-18)

The 2026-10-16 physical measurements were taken before the opt-in SRC header
change. The delivery's addendum reads that gate as blocked on "adjudication,
executable scope, and replay material", not on missing measurements. This
re-run addresses the executable-scope half: the same two instruments, run
against binaries built from this tree at 8e9ddcdb, where
`src/rate_poly_fir0.h` is the post-rebind `bd86a881...`.

Prepared host: Threadripper 7970X, governor performance, boost 0, pinned
cpu 8, `physical_host_admissible: true`.

## Comparator, full guaranteed passband, no exclusion

| cell | control | band | max abs difference |
|---|---|---|---|
| v1 @ 176400 | `sinc -a 180 -t 40000 -60000` | to 40000 Hz | 0.00213 dB |
| v1 @ 352800 | same | to 40000 Hz | 0.00163 dB |
| v2 @ 176400 | `sinc -a 180 -t 14000 -73000` | to 66000 Hz | 0.00648 dB |
| v2 @ 352800 | same | to 66000 Hz | 0.00316 dB |

## Timings

| cell | vs direct | vs P/S-matched |
|---|---|---|
| mastering @ 176400 | 4.014 [3.975, 4.046] | 4.126 [4.083, 4.159] |
| mastering @ 352800 | 3.880 [3.857, 3.904] | 3.893 [3.872, 3.916] |
| v2 @ 176400 | 3.863 [3.850, 3.879] | 3.967 [3.955, 3.982] |
| v2 @ 352800 | 3.740 [3.726, 3.752] | 3.761 [3.748, 3.774] |

Eight of eight exceed 2x at the 95% CI lower bound; the lowest is 3.726.

Every point estimate and interval was recomputed here from the saved
per-repetition arrays rather than read from the receipt: zero disagreements.
Comparator and bench share both binaries, and the bench's
`spectral_receipt_sha256` equals the comparator receipt's actual digest.

## What this does not fix

The bench pins eight sources and `src/rate_poly_fir0.h` is not among them.
So the receipt still does not record the header identity that the rebind
changed. The binaries are current; the pin set is unchanged. If the
executable-scope objection is specifically about the header being outside
the recorded scope, this re-run does not close it and the instrument would
need to pin it.

Bulk audio dropped after recording digests in `AUDIO_SHA256.txt`.

## Scope

`MEASURED_PHYSICAL_UNADJUDICATED`, `qualified_release: false`. Throughput on
one prepared host with a spectrally verified comparator. Not an audio
quality result, not a v2 qualification, not a promotion. The gate stays OPEN
and the disposition is the authority's.
