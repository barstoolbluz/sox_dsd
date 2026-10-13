# P15 release soaks: five SDM families by three encode profiles

**Fifteen runs, 3600 audio seconds each, all fifteen clean against the design
10.5 criteria.** Run on the physical prepared host, five families concurrently
on dedicated cores, 9365 CPU seconds total.

This addresses `P15-current-full-release-soaks-every-profile-ISA`, whose
delivered evidence note read "Historical P10/P11 scalar/ISA soak receipts are
not full P15 physical qualification". These are current-revision runs on the
integrated P15 tree at the commit recorded below.

| family | native Hz | profile | exc28 | nonfinite | longest run | ones28 | worst bound use | CPU s |
|---|---|---|---|---|---|---|---|---|
| `scalar` | 2822400 | `encode.mastering.v1.dsd64` | 0 | 0 | 8 | 7-21 | 6.05% | 292 |
| `scalar` | 5644800 | `encode.mastering.v1.dsd128` | 0 | 0 | 9 | 6-22 | 6.37% | 590 |
| `scalar` | 11289600 | `encode.mastering.v1.dsd256` | 0 | 0 | 9 | 6-22 | 6.21% | 1133 |
| `sse2` | 2822400 | `encode.mastering.v1.dsd64` | 0 | 0 | 8 | 7-21 | 5.94% | 264 |
| `sse2` | 5644800 | `encode.mastering.v1.dsd128` | 0 | 0 | 9 | 6-22 | 6.64% | 532 |
| `sse2` | 11289600 | `encode.mastering.v1.dsd256` | 0 | 0 | 9 | 6-22 | 6.00% | 1016 |
| `avx1` | 2822400 | `encode.mastering.v1.dsd64` | 0 | 0 | 8 | 7-21 | 5.94% | 272 |
| `avx1` | 5644800 | `encode.mastering.v1.dsd128` | 0 | 0 | 9 | 6-22 | 6.64% | 551 |
| `avx1` | 11289600 | `encode.mastering.v1.dsd256` | 0 | 0 | 9 | 6-22 | 6.00% | 1043 |
| `avx2` | 2822400 | `encode.mastering.v1.dsd64` | 0 | 0 | 8 | 7-21 | 5.94% | 259 |
| `avx2` | 5644800 | `encode.mastering.v1.dsd128` | 0 | 0 | 9 | 6-22 | 6.64% | 524 |
| `avx2` | 11289600 | `encode.mastering.v1.dsd256` | 0 | 0 | 9 | 6-22 | 6.00% | 1005 |
| `avx512` | 2822400 | `encode.mastering.v1.dsd64` | 0 | 0 | 8 | 7-21 | 5.94% | 275 |
| `avx512` | 5644800 | `encode.mastering.v1.dsd128` | 0 | 0 | 9 | 6-22 | 6.64% | 552 |
| `avx512` | 11289600 | `encode.mastering.v1.dsd256` | 0 | 0 | 9 | 6-22 | 6.00% | 1058 |

Every run: zero 28-bit excursions, zero nonfinite states, zero monitor
overloads, `failure` 0, `first_bad_frame` null, exact frame accounting
(`committed_native_frames` equals `processed_native_frames`,
10160640000 at DSD64), worst integrator-state use of the frozen P10 guard bounds
under 6.7%, and DSD64 window population inside the required 4 to 24.

## Cross-phase reproduction

The nine runs shared with `P11_soak_per_family_2026-10-11` reproduce
**identically**, including every one of the eight per-order
`max_abs_state` maxima. The numerical behaviour of the modulator is therefore
unchanged from P11 through the P14 report work, the decode optimization and
P15. We did not expect otherwise, since none of those touched `sdm.c`, but it is
checked rather than assumed.

The two newly covered families, `avx2` and `avx512`, produce figures identical
to `sse2` and `avx1` at every rate, and all four vector families differ from
`scalar` in the same consistent way. That is the vector-versus-scalar split
already established for the SDM.

## On the harness label

Each record carries `qualification: UNQUALIFIED` and `status: 3`. P11's accepted
records carry exactly the same two values, and those nine were accepted as
satisfying the criteria. We read it as the harness declining to certify on its
own behalf rather than as a criterion failure, and the substantive fields are
what we assess above. If that reading is wrong the assessment changes, and it is
ours to be corrected on.

## What this covers, and what it does not

`soak_p10.py` is the **composite** soak: PCM to DSD, exercising the SDM kernel
families across the three encode mastering profiles. "Every profile-ISA" is
satisfied on that axis: three encode profiles by five SDM families is the
complete matrix of fifteen.

It does **not** cover the decode side. There is no equivalent long-duration
harness for the FIR tiers and the two decode profiles, so decode-side soak
coverage is absent rather than passing. We have not built one, because what a
decode soak should assert is a design question we are not placed to answer: the
SDM soak's criteria are modulator-state and population bounds, which have no
direct decode analogue.

Whether this closes the gate as worded therefore depends on whether
"every profile-ISA" was meant to include the decode axis. We state the coverage
and leave the determination.

No default changed, no profile promoted, and no gate status was altered in the
delivered release manifest.

Figures are from one host and are not a property of the code alone.
