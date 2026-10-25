# High-rate v2 decode certificate, 2026-10-24

P21 added `decode.mastering.v2.dsd512` and `.dsd1024` by reusing the DSD256
v2 final bank behind a longer half-band cascade. The justification at the
time was an analogy: v1 reuses `master64_256` across DSD256, 512 and 1024,
and the 66k/80k edges cannot usefully move while the intermediate clock
stays at 176400 with a Nyquist of 88200. The rows were committed on that
reasoning plus a behavioural comparison against the qualified DSD256 row,
matching to two decimals per band.

That is an argument and a comparison, not a certificate. This measures the
cascade with the same independently authored P06-derivative certifier that
certifies the low-rate v2 rows, and re-derives the published delay from the
cascade identity rather than trusting it.

## Result: PASS

| row | pass ripple (dB) | stopband (dB) | coherent alias (dB) | delay |
|---|---|---|---|---|
| v2.dsd256 (control, already certified) | 5.842e-09 | -188.5853517876 | -182.839 | — |
| v2.dsd512 | 5.877e-09 | -188.5853517876 | -182.775 | 12132 |
| v2.dsd1024 | 5.886e-09 | -188.5853517876 | -182.759 | 24292 |

The DSD256 row was measured in the same run, at the same grid, as the
control the reuse argument rests on. Comparing against figures recorded on
another day would not have been like for like.

## What the numbers say

The stopband is identical across all three to ten significant figures. That
is the reuse being correct rather than coincidental: the stopband peak is
set by the final bank, which is the same bank, so prepending half-bands
leaves it untouched. A wrong reuse would show here first.

Degradation across the two added stages totals 0.08 dB, all of it in the
coherent image sum, which is expected because the number of images summed
grows with the decimation factor as it goes 64, 128, 256. Passband ripple
moves in the eleventh decimal place.

Both published delays were re-derived independently:
`G = sum((len(bank)-1)//2 << j)` over the cascade returned 12132 and 24292,
matching `src/dsd.c`. A wrong delay would have failed before any filter
response was measured.

## Scope

Establishes that the reused final bank behind 6 and 7 half-bands meets the
same passband, stopband and image bounds the certified DSD256 v2 row meets.

Does not establish device behaviour, and does not close the composite
fractional SRC gate, which remains separate and open.

Read from the production C99 headers, not from any coefficient generator.
Bank identity is checked against the frozen `p15_r3_coefficients.json`
hashes before anything is measured.

## Reproducing

    python3 tests/dsd/certify_p21_highrate_decode.py --results <dir> --grid 4096

Requires numpy and mpmath.
