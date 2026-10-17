# P15 DSD256 P/S-matched comparator and 2x, physical host (2026-10-16)

The physical run the R2 obligations handoff left to us. **The gate status is
not changed here.** The handoff says "No automatic promotion occurs even if
all ratios satisfy 2x", and we were reversed earlier this day for setting a
DSD256 disposition ourselves. `p15_current_closeout.py` still derives that
gate from the superseded 2026-10-15 receipt and still reads OPEN.

Produced on tree b158ea5e by, in order:

    p15_dsd256_comparator_2026.py --sox <b>/src/sox_ng \
      --candidate <b>/test/sox_p10_candidate --output .../comparator
    bench_p15_dsd256_ps_matched.py --sox <b>/src/sox_ng \
      --candidate <b>/test/sox_p10_candidate \
      --spectral-receipt .../comparator --output .../bench \
      --cpu 8 --seconds 2 --warmups 2

Host: AMD Ryzen Threadripper 7970X, physical, `hypervisor False`, microcode
0xa10810c, governor performance, boost 0 via `benchprep.sh prepare --cpu 8`,
kernel 6.12.85. `physical_host_admissible: true`.

Bulk audio was deleted after its digests were recorded in `AUDIO_SHA256.txt`
in each directory; the receipts carry the same hashes.

## The comparator, which is the point of this round

Our 2026-10-15 control used `sinc -P`, which centres its transition on P and
therefore rolls off before reaching P. That produced 6.017 dB of divergence at
v2's 66 kHz edge, and we responded by excluding the top 5% of the passband.
That exclusion was rejected. The corrected comparator instead designs the
pre-decimation FIR with passband edge P, stopband S and centre (P+S)/2.

Over the **full** guaranteed passband, no exclusion:

| cell | control | band | max abs difference |
|---|---|---|---|
| v1 @ 176400 | `sinc -a 180 -t 40000 -60000` | 1k-40000 Hz | 0.00202 dB |
| v1 @ 352800 | `sinc -a 180 -t 40000 -60000` | 1k-40000 Hz | 0.00096 dB |
| v2 @ 176400 | `sinc -a 180 -t 14000 -73000` | 1k-66000 Hz | 0.00611 dB |
| v2 @ 352800 | `sinc -a 180 -t 14000 -73000` | 1k-66000 Hz | 0.00364 dB |

6.017 dB became 0.0061 dB, and the 5% crop is no longer needed. The diagnosis
was theirs and it was right.

## Timings

Six-channel DSD256 fixture, 15 repetitions per arm after 2 warmups, pinned to
cpu 8, 10000-iteration bootstrap, seed 20261016.

| cell | vs direct | vs P/S-matched |
|---|---|---|
| mastering @ 176400 | 3.913 [3.899, 3.923] | 4.021 [4.005, 4.031] |
| mastering @ 352800 | 3.784 [3.755, 3.807] | 3.800 [3.773, 3.823] |
| v2 @ 176400 | 3.779 [3.772, 3.784] | 3.887 [3.880, 3.893] |
| v2 @ 352800 | 3.673 [3.629, 3.684] | 3.689 [3.641, 3.698] |

Eight of eight exceed 2x at the 95% CI lower bound. The lowest lower bound is
3.629, so the margin is not marginal.

The decoder scores slightly *better* against the matched control than against
the direct one, because the matched control does the band-limiting the decoder
also does. That is the comparison the gate asked for.

## Independent recomputation

Every point estimate and interval was recomputed here from the saved
per-repetition arrays rather than read from the receipt: 8 of 8 point
estimates agree to 1e-9, all eight bootstrap lower bounds reproduce within
0.03, and all eight exceed 2. Zero disagreements.

Provenance checked: all eight pinned sources (`rate.c`, `fft4g.c`, `sinc.c`,
`effects_i_dsp.c`, `dsd_decode.c`, `dsd_coeffs.h`, `dsd_coeffs_v2.h`,
`verify_dsd256_control_match.py`) match this tree; the comparator and the
bench are bound to the same two binaries; and the bench's
`spectral_receipt_sha256` equals the actual SHA-256 of the comparator receipt.

## What this is not

`status: MEASURED_PHYSICAL_UNADJUDICATED`, `qualified_release: false`.
Throughput on one prepared host with a spectrally matched comparator. Not an
audio quality result, not a v2 qualification, and not a promotion. Release
remains BLOCKED and v2 remains off by default.

One limitation worth stating: the receipt records governor but not turbo
state. Boost was 0, set and verified through `benchprep.sh`, but that fact
lives in this README rather than in the receipt.
