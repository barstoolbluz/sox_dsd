# P11 one-hour soak per SDM kernel family (2026-10-11)

**Nine runs, three SDM families by three native rates, 3600 audio seconds each.
All nine satisfy the design 10.5 criteria.** No nonfinite state, no 28-bit
excursion, no guard-bound crossing, exact frame accounting, and DSD64 population
inside 4 to 24 throughout.

This addresses the requirement the frozen P10 criterion carries into this phase,
"P11 requalifies every newly introduced runtime ISA/kernel family", for the SDM
families. It certifies nothing: P11's own disposition is INCOMPLETE and
certification is a separate judgement.

| Family | Native Hz | nonfinite | 28-bit exc | longest run | ones | worst bound use | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scalar` | 2822400 | 0 | 0 | 8 | 7-21 | 6.05% | 292 |
| `scalar` | 5644800 | 0 | 0 | 9 | 6-22 | 6.37% | 591 |
| `scalar` | 11289600 | 0 | 0 | 9 | 6-22 | 6.21% | 1133 |
| `sse2` | 2822400 | 0 | 0 | 8 | 7-21 | 5.94% | 263 |
| `sse2` | 5644800 | 0 | 0 | 9 | 6-22 | 6.64% | 529 |
| `sse2` | 11289600 | 0 | 0 | 9 | 6-22 | 6.00% | 1012 |
| `avx1` | 2822400 | 0 | 0 | 8 | 7-21 | 5.94% | 274 |
| `avx1` | 5644800 | 0 | 0 | 9 | 6-22 | 6.64% | 547 |
| `avx1` | 11289600 | 0 | 0 | 9 | 6-22 | 6.00% | 1042 |

## The scalar family reproduces P10 exactly

Every recorded field compared across the three rates - processed frames, window
counts, excursions, population range, longest run, nonfinite count and all eight
integrator state maxima - is identical to
`tests/dsd/results/P10_soak_1hour_sse2_2026-10-10/`: **true**. The P11
dispatcher refactor therefore leaves the recurrence P10 certified bit-unchanged
over an hour per rate, which is the strongest regression evidence available for
the certified path.

## The vector families agree with each other and not with scalar

Final continuation-state hashes: `sse2` and `avx1` are identical at every rate
(true), and both differ from `scalar` at every rate (true). Their
integrator state maxima are identical to each other and diverge from scalar by
up to 6.0% relative.

That is expected rather than alarming. Reordered floating-point arithmetic in a
feedback recurrence does not reproduce bit-for-bit, which is why the SOW requires
cross-ISA SDM validation to be spectral and state based rather than a raw DSD
hash comparison. The consequence that matters is that P10's scalar certification
does not transfer to these kernels on its own, and the dispatcher's default of
scalar for the SDM is the correct conservative choice.

What these runs establish for the vector families is long-duration stability:
over 3600 seconds per rate each stayed finite, crossed no guard bound, produced
no 28-bit excursion and held population inside the admitted range, with worst
bound utilisation 6.64%. Spectral equivalence is a separate matter
covered by the phase's own `tests/dsd/results/P11/numeric/`.

## SSE2 is faster than AVX1 here

Summed over the three rates: scalar 2017 s, sse2 1803 s, avx1 1864 s. So
AVX1 costs about 3.3% more than SSE2 on this part while both beat
scalar. The SOW's instruction to assume no preference from ISA width is borne
out: the wider tier is not the faster one here. These are soak timings on a
prepared host rather than the phase's own per-tier benchmarks, and no throughput
claim is made from them.

## Scope

Composite soaks exercise the SDM families only. `src/pcmdsd.c` contains no
`LSX_DSD_FIR` reference and a run's final state is unchanged under
`SOX_DSD_KERNEL_FIR`, so the FIR tiers are not requalified by anything here;
they are exercised by the decode path, in the phase's own integration suite and
in `tests/dsd/results/P11_avx1_no_avx2_2026-10-11/`.

Fixture `p10-soak-nominal-v2`, 60-second segments, one uninterrupted encoder per
family and rate, forced with `SOX_DSD_KERNEL_SDM`, pinned to CPU 8 on an AMD
Ryzen Threadripper 7970X with a 0.0% host noise probe beforehand. Figures are
from one host.
