# P10–P15 corpus and FIR dispatch adjudication

**Date:** October 13, 2026. **Disposition:** The observed scalar/SSE2 FIR roundoff is allowed by the governing numerical contract. The recorded population extrema remain acceptable. **No production DSP modification, P10 certificate rewrite, or new release hold is justified by this evidence.** P15 remains unqualified for default promotion for its separately documented outstanding gates.

This assessment is an evidence review, **not** a new mastering-profile certificate, a private-corpus rerender, or proof of universal bitstream identity.

## Source custody

All three supplied `git archive` input hashes were verified against the brief. Their names and SHA-256 values appear in `tests/dsd/results/P15_corpus_fir_adjudication_2026-10-13/source-archives.json`. This deliverable is a pristine P15 source tree with **only additive** Python tests, a C probe, these notes, and new evidence files. It does not include build products, audio recordings, or changed production C files. Its original P15 production sources and historical certificates are preserved. In accordance with the P15 continuation checkpoint, the sole updated original file is the self-excluding P00 global SHA-256 inventory, regenerated **after** the additive evidence files are finalized.

## Findings against the four questions

1. **Expected and acceptable numerical difference:** Section 8.6 of `docs/dsd/DSD_DESIGN.md` explicitly permits scalar/SIMD FIR binary64 differences within an accumulated-roundoff envelope. Output count, phase, endpoint behavior and graph sample tolerance remain mandatory. The 28-bit extrema difference is not evidence of incorrect encoder arithmetic; all the reported per-channel minima/maxima remain in 4–24. The P11 kernel suite tests oracle comparisons and reproducible within-kernel SDM output.

2. **Cross-ISA claim:** FIR is numerically equivalent, not required to be bit-identical. Section 8.6 and §10.6 likewise do **not** assert cross-ISA modulated DSD byte equality; §10.6 requires per-kernel stability, reconstructed signal, spectral and state quality. One should not conflate identical post-graph decode files with identical internal decoder doubles. Both 32-bit-int and 64-bit-float CLI decode files pass through SoX's int32 graph. In the supplied P15 source, `src/dsd_decode.c` dispatches scalar versus SSE2 reconstruction; P15 SSE2 uses `lsx_dsd_fir_sse2_direct` for its non-halfband FIR, scalar uses `lsx_dsd_fir_scalar`. On the other hand, `src/pcmdsd.c:feed_fir()` calls `lsx_dsd_fir_scalar` unconditionally for the composite's *centered encoder prefilter*. Thus the brief's hypothesized site of dispatch is ruled out. The decoder's pre-graph binary64 values **do** differ in the deterministic direct probe: six profile/rate runs observe maximum absolute deltas of 1.39e-16 to 5.55e-16, below their computed bounds (1.12e-11 to 1.99e-11), and below 1.2e-6 int32-graph LSB in magnitude. This does not prove every resulting int32 sample is the same near a quantization boundary, nor does it localize a difference in the unavailable commercial recording. It does establish a real, allowed numerical path consistent with the correlation observed in the brief. The scalar versus SSE2 modulation discrepancy is **not proven to arise solely from that path**; that causal identification requires the private input or an instrumented reproduction.

3. **P10 certification:** P10's original revision-pinned checker passes on its original P10 tree (10/10 gates, corpus/profile and prepared-host receipts PASS). The same unchanged checker deliberately fails on current P15 source (`src/dsd_plan.c` changed). The P15 release ledger already records the four later changes among the P10-pinned source files `src/dsd_plan.c`, `src/pcmdsd.c`, `src/pcmdsd.h`, `src/sdm.c` (31/35 unchanged). An authorized numerical difference after P11 does not retroactively invalidate the **historical P10 source certificate**. Equally, the historical P10 positive result does not certify revised P15 sources. Do not rewrite source hashes, force the verifier green on P15, or promote any uncertified default. A current-version profile qualification remains distinct from this corpus review.

4. **Release decision:** The observed extrema themselves are **non-blocking** for the stated 4–24 population criterion. There is no admission, excerpt identity, output-size, output-frame count, aggregate max, level-metric, or P15-attempted ladder-admitting-gain regression in the 40 recorded comparisons. This does **not** make P15 generally release-ready: `docs/dsd/handoffs/P15_CHECKPOINT.md`, `docs/dsd/QUALIFICATION.md`, and `tests/dsd/results/P15/release/release-manifest.json` retain the external/hardware/performance/numerical qualification blockers.

## Correction: more than one recorded corpus statistic changed

Comparing the **stored manifest fields** in `tests/dsd/results/P10_realworld_corpus_2026-10-10/` and `tests/dsd/results/P15_corpus_independent_material_2026-10-13/dsd/` yielded **40 arms × source records (18 unity, 18 attenuated, 4 ladder); 18 source/rate identities; 6 extrema fields across 4 arm/source/rate pairs and 3 sources**:

| Arm | Source | Channel | Statistic | P10 | P15 |
|---|---|---|---:|---:|---:|
| unity | `Pink_Floyd~Meddle~side1.dsf` (DSD128) | 1 | maximum ones / 28 | 20 | 19 |
| attenuated, −0.1 dB | `01 - Cantata BWV 110_ 1. Chorus.dsf` (DSD64) | aggregate | minimum ones / 28 | 8 | 7 |
| attenuated, −0.1 dB | same Cantata | 1 | minimum ones / 28 | 8 | 7 |
| attenuated, −0.1 dB | `Pink_Floyd~Meddle~side1.dsf` (DSD128) | 1 | minimum ones / 28 | 8 | 7 |
| attenuated, −0.1 dB | same Meddle | 1 | maximum ones / 28 | 20 | 19 |
| ladder | `01 - Bone Machine.dsf` (DSD64) | 0 | minimum ones / 28 | 6 | 7 |

The Meddle and Bone Machine **aggregate** extrema are unchanged because another channel determines them. Consequently, the assertion “every other recorded field across eighteen sources matches” is incorrect even though the operational acceptance posture remains unchanged. The original P15 independent-material note and the question brief omitted these per-channel facts; they are retained as historical writings and corrected in this addendum rather than silently edited.

The four P15 ladder records attempted **fewer gains** than their P10 counterparts; all *overlapping* trial verdicts and the terminal admitting gain match. The audit discloses all four missing-trial sets instead of claiming the entire P10 ladder was rerun. The privately held audio itself is not included, so the source excerpt SHA fields can be compared but an independent new render of those recordings **cannot** be executed here.

## Additional checks and their limits

- Fresh P10/P15 Autotools static builds **PASS** (working trees only, not bundled). Original P10 certification exits **0**; P15's original P10 checker exits **1 as designed**.
- P15 compiled P11 and P12 kernel unit executables **PASS**, including tested scalar/SSE2/AVX oracle, state and buffering checks. The package changes no DSP implementation files.
- The included `tests/dsd/probe_p15_fir_roundoff.c` exercises scalar/SSE2 pre-graph doubles at DSD64/128/256, mastering and wideband profiles. All six PASS the bound and graph-magnitude checks. Its deterministic xorshift input is a synthetic stress case, not representative music; the recorded numeric output is in `pregraph-fir-roundoff.jsonl`. The bound does not imply quantized graph byte identity.
- A synthetic two-channel DSD64 `.dsf` fixture, processed by `trim 0 0.1`, `gain -0.1`, and `pcmdsd 2822400`, produces equal **73820-byte output files** with SHA-256 `94a4efc88b07907b8feb99045aaa82596034faaea5067f811228b32398a6e416` for P10, P15 scalar and P15 SSE2. This is one controlled example, **not** evidence of cross-ISA byte identity for arbitrary material.
- Manifest audit `tests/dsd/adjudicate_p10_p15_corpus.py` reports `PASS-BOUNDED-DRIFT`. Its **12 standard-library regression/mutation tests** confirm that source digest, admission, output size, frame count, 4–24 bounds, suspicious >1-step extrema shifts, level metrics, trial decisions, channel metrics and missing files fail as intended. The script reports only currently recorded evidence, never a fresh corpus-run certification.

## Minimal disposition and follow-up

No numerical correction to `pcmdsd`, no forced-scalar default, no certificate mutation and no special-case exemption for the Cantata file are warranted. Preserve the existing P15 release holds and existing per-ISA profiling tests. If a future requirement demands **raw cross-ISA encoded-byte identity**, that would change the documented product contract and require a deliberate performance/compatibility tradeoff; it cannot be inferred from the 4–24 criterion. The only unresolved causal detail relevant to this observation is which particular pre-graph rounding threshold(s), if any, cause the supplied private recording's shifted extrema. Rerun that commercial source with intermediate graph samples and SDM kernel choice held fixed only if that causal answer is needed to resolve a new acceptance failure; do not make that optional investigation a new P15 release gate.

All commands and files needed to resume are in `CORPUS_FIR_ADJUDICATION_RESUME.md`; all old evidence content and its source hashes are unchanged **except** the P00 global file inventory, which is regenerated last to cover the new paths.
