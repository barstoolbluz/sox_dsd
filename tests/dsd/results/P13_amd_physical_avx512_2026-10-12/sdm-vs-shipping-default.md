# Corroboration pass 2: against the shipping default, the vector SDM wins

Second independent pass, fresh source, 9 reps, CPU 8, same prepared host.
Passes 1 and 2 agree on decode; pass 2 adds a comparison never previously run.

## What pass 2 reproduced

Decode by forced FIR tier spans 1.2% across all five tiers (pass 1: 1.6%), with
AVX-512F slowest in both. Read-only is 3.8% of decode wall time in both passes.
Decode is insensitive to the FIR tier at 44100 too, where the SRC is active.

## What pass 2 added, and it reframes the earlier conclusion

Every comparison before this measured AVX-512F against AVX2. Neither is
selected by default. Measuring each against `scalar`, which `dsd_dispatch.c`
actually selects for the mastering SDM:

| forced SDM tier | encode 176400 to 2822400 | vs scalar |
|---|---|---|
| scalar | 0.8156s | 1.000x |
| sse2 | 0.7333s | 1.112x |
| avx1 | 0.7625s | 1.070x |
| avx2 | 0.7314s | 1.115x |
| avx512 | 0.7675s | 1.063x |

All four vector tiers beat the shipping default by 6.3% to 11.5%. AVX2 is best.
AVX-512F is 4.9% slower than AVX2 and still 6.3% faster than scalar, an ordering
consistent with the kernel benchmark's `sdm` figure of 0.920x AVX-512F over AVX2.

## The correction this forces

The parent README concluded "do not promote AVX-512F" and that stands: AVX-512F
is the wrong vector tier, beaten by AVX2 on every end-to-end encode case.

But the README's wider implication, that vectorisation is not worth promoting,
is not supported. It rested on comparing two unselected tiers with each other.
Against the tier in force, vectorising the mastering SDM appears to be worth
about 11% on encode.

`dsd_dispatch.c` gives the reason scalar is selected, and it is explicitly not
a performance judgement: *"P10's scalar SDM is the frozen mastering reference.
A wider tier is not a silent new certification; explicit forcing allows
qualification."* On our reading the gap is therefore an open certification
question, not a missed optimisation. We are not placed to decide whether that
certification should be reopened and we have not changed any default.

## Standing uncertainty

We still do not know where decode spends its 96%. Two explanations we offered
were withdrawn within a day, `perf` is not installed here, and we have no
attribution. The question is referred out rather than answered again.

Figures are from one host and are not a property of the code alone.
