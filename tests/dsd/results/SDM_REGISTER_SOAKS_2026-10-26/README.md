# Register-resident SDM: one-hour soaks at 1.0.2

Nineteen one-hour soaks of the shaper at `56732a042` (SoX DSD 1.0.2), on the
AMD Ryzen Threadripper 7970X, each tier on its own core. Each run covers
3,600 audio seconds of the nominal-v2 fixture.

| set | harness | tiers | rates |
|---|---|---|---|
| `low-rate/` | `soak_p10.py` | scalar, sse2, avx1, avx2, avx512 | DSD64, DSD128, DSD256 |
| `high-rate/` | `p20_soak_run.py`, `p19_soak_run.py` | scalar, avx512 | DSD512, DSD1024 |

## Result

All nineteen are clean:

- zero 28-bit excursions
- zero nonfinite states
- zero overloads
- failure 0
- committed frames equal processed frames, which equal 3600 times the rate

Every vector tier's result is identical to scalar in every field except
`cpu_seconds`, including all eight `max_abs_state` maxima.

Scalar is identical to the committed scalar soaks:

- `P15_soaks_every_profile_isa_2026-10-13` at DSD64-256
- `P19_OPERATOR_QUALIFICATION_2026-10-22/soak/d1024-v2`
- `P20_OPERATOR_QUALIFICATION_2026-10-22/soak/p20-nominal`

So the default AVX2 and AVX-512 paths reproduce the soaks those profiles
were qualified on. The vector tiers no longer match their own P15 soaks.
That is expected: they now follow scalar's trajectory, not the inherited
x86 one.

CPU seconds per audio hour:

| rate | scalar | avx2 | avx512 |
|---|---|---|---|
| DSD64 | 236 | 162 | 164 |
| DSD128 | 476 | 328 | 333 |
| DSD256 | 911 | 618 | 627 |
| DSD512 | 1690 | — | 1152 |
| DSD1024 | 3334 | — | 2267 |

The harnesses label every record `qualification: UNQUALIFIED`, `status 3`,
as the accepted P11 and P15 records also are. Figures are from one host.
