# P15 independent 3x9x2 metrology: executed

The adjudication of 2026-10-13 specified this gate; the R2 bundle supplied the
instrument. This directory is our execution of it. **No cell is qualified and
no gate is closed by this run**: the instrument reports
`MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW`, `qualified` false and
`release_gate_closed` false on every row, by its own design.

## What ran

| run | result |
|---|---|
| scalar full matrix, with SRC and graph raw capture | 54 of 54 cells measured, 0 failed |
| forced-tier grid, five tiers x 54 cells | 270 of 270 measured, 0 failed |
| required local observations | present for all 54 |
| real graph rows | 54 |
| sampled SRC spectral rows | 54 |

Reference split as the contract requires: 30 integer-ratio cells against
independent high-precision finite decimated convolution, 24 fractional cells
against the independently constructed rational SRC.

## The production FIR agrees with the independent oracle to machine epsilon

Across all 54 cells the isolated native FIR cascade differs from the 75-digit
independent convolution reference by **1.949e-16 to 2.576e-16**. That is the
strongest statement in this run: the certified coefficient banks and the
production cascade reproduce an independently composed high-precision
convolution to the last representable bit.

## Where the full chain diverges, and why

| group | cells | behaviour |
|---|---|---|
| pure factor-2 cascade, no final SRC | 4 | bit-exact end to end, max_abs 1.99e-16 to 2.58e-16 |
| edge-dominated | 28 | interior 1e-11 to 1e-8, maximum at the finite-file boundary, 1e-05 to 1e-03 |
| interior divergence | 22 | 1e-05 to 1e-04 throughout |

So every end-to-end divergence traces to an SRC stage, and in 28 of 54 cells it
is concentrated at file boundaries rather than present in the interior. The
bit-exact four are `dsd64.*.pcm88200`, `dsd128.mastering.pcm176400`,
`dsd256.mastering.pcm176400` and `dsd256.wideband.pcm352800`.

This is the condition the instrument's authors predicted: a deliberately
independently designed SRC does not produce the same samples as production, and
its finite-file boundary differences can dominate floating-point roundoff. They
explicitly declined to let §8.6's FIR accumulated-roundoff limit serve as an
end-to-end SRC acceptance envelope, and we are not proposing one. **The 24
fractional cells and the 28 edge-dominated maxima require a predeclared,
independently justified numerical envelope before any of this becomes an
acceptance result.** Without it these are measurements, not verdicts.

## Cross-ISA

All five tiers produce **one** binary64 output hash per cell across all 54
cells: 54 of 54 in agreement, 0 differing. Consistent with the forced-tier
output equality already recorded on AMD Zen 4, Intel Sapphire Rapids and the
Xeon E5-1680 v2, and measured here at full binary64 precision rather than after
int32 quantisation, which is where our earlier reasoning went wrong.

## Curation

The scalar run produced 922 MB. Committed here are the cell records, SRC
spectral records, worklist, session binding and summaries: 715 files, 9.3 MB.
Excluded: `src-raw` 825 MB, `arrays` 53 MB, `graph-raw` 43 MB. Those are raw
binary64 tone dumps, numerical NPZ vectors and graph audio whose SHA-256
digests are retained inside the committed cell records, so a reviewer can see
what was measured and demand the originals. They remain reproducible from the
session binding, which pins the worklist hash, both probe binaries, the bank and
reference hashes and the Python/NumPy/SciPy/mpmath versions.

## What this does not do

It does not close the gate. The instrument says so itself, and the obligations
it names as outstanding are full spectral extrema and coherent-alias
certification, a justified combined-stage SRC numerical envelope, real
graph-thread and clipping evidence, and independent review. Our reading is that
the first and last are not ours to supply.

Figures are from one host and are not a property of the code alone.
