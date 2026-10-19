# DSD256 P/S-matched prospective physical measurement (2026-10-19)

The run the R5.2 gate document asks for: a physical measurement bound to
final binaries, on the only physical host we have.

    OMP_NUM_THREADS=1 ./tests/dsd/p15_r52_run_physical_benchmark.sh \
      <build>/src/sox_ng <build>/test/sox_p10_candidate 8 <fresh dir>

Threadripper 7970X, governor performance, boost 0, cpu 8,
`physical_host_admissible: true`. Binaries built from this tree with
`-O2 -g -ffp-contract=off -fno-fast-math`, verified true ELF rather than
libtool wrappers, which the wrapper refuses.

## Results

Comparator, full guaranteed passband, no exclusion, fresh 6-second
broadband fixture, and re-checked by its own `--verify-only` pass:

| cell | band | max abs difference |
|---|---|---|
| v1 @ 176400 | to 40000 Hz | 0.00248 dB |
| v1 @ 352800 | to 40000 Hz | 0.00106 dB |
| v2 @ 176400 | to 66000 Hz | 0.00690 dB |
| v2 @ 352800 | to 66000 Hz | 0.00444 dB |

Timings, eight of eight above 2x at the 95% CI lower bound, lowest 3.534:

| cell | vs direct | vs P/S-matched |
|---|---|---|
| mastering @ 176400 | 3.888 [3.858, 3.908] | 3.995 [3.961, 4.014] |
| mastering @ 352800 | 3.689 [3.652, 3.730] | 3.702 [3.668, 3.743] |
| v2 @ 176400 | 3.727 [3.703, 3.767] | 3.837 [3.816, 3.881] |
| v2 @ 352800 | 3.606 [3.534, 3.613] | 3.624 [3.551, 3.632] |

`p15_r52_physical_benchmark_review.py` recomputed 8/8 over these receipts.
We also recomputed all eight independently from the saved per-repetition
arrays: zero disagreements.

## What this fixes relative to 2026-10-16

The earlier measurements were refused scope because the recorded inventory
omitted `src/rate_poly_fir0.h`, edited on 17 October. The R5.2 wrapper hashes
it in BEFORE and AFTER, here at `bd86a881...`. Thirteen paths are hashed and
BEFORE is byte-identical to AFTER, so neither source nor binary moved during
measurement.

Audio payloads are retained, 146 MB, because the runbook asks for it: the
reviewer recomputes spectral agreement from preserved WAV rather than from
recorded digests. October's run deleted them.

## The FFT4G locking precondition

The gate document asks for the R5.1 FFT4G reader/writer corrective or an
independently proven exclusive-use configuration. That corrective is not in
this tree. The OpenMP exposure is two `pragma omp parallel for` in
`src/effects.c` and nothing else, so we ran with `OMP_NUM_THREADS=1`, which
makes the race unreachable by construction rather than by argument. That is
the route taken; it is not the corrective.

## Host qualification, both readings

`benchprep.sh noise --cpu 8` reports 0.0% spread over 15 runs, verdict
usable against a 2.0% tolerance. `benchprep.sh status --cpu 8` separately
warns that the core's clock varies, 2188 to 3969 MHz, because its spin-up
probe catches the idle floor before the core ramps. We report both; the
repeatability measurement is the one bearing on the timings.

## Scope

`MEASURED_PHYSICAL_UNADJUDICATED`, `qualified_release: false`. Their
reviewer returns `physical_2x_gate: OPEN` and `overall_gate: OPEN`, refusing
on the grounds that receipt arithmetic cannot authenticate host identity or
full build-dependency closure. We agree and claim nothing further. The
disposition is the authority's.
