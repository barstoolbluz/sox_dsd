# P15 R7 — seven-gate independent adjudication

**Date:** 2026-10-19. **Original source identity:** `cc399928`; archive SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Verdict

- Continuous-frequency spectral **inventory: PASS** (11,516 canonical jobs from the historical 72-cell campaign, not independent mathematics).
- Independent ideal-operator **spectral mathematics: CONDITIONAL**. **87/11,516** canonical intervals independently certified by sound exact-integer R7 checker, **two entire cells** independently closed. Remaining **11,429** intervals need equivalent qualification.
- **Source and execution provenance: CONDITIONAL**. Current cc399928 source archive, captured operators, R7 method hashes verified. Historical Oct 18 original generating-prover execution is not cryptographically attested; actual release binary closure still missing.
- Arbitrary-input actual **FFT4G execution roundoff: CONDITIONAL**, unchanged. Final ELF/FP/warm-cache/concurrency theorem is not provided by R7.
- End-to-end **same-operator numerical acceptance: CONDITIONAL**, unchanged, pending release FFT4G correspondence and total cascade error.
- **Physical DSD256 matched 2×: CONDITIONAL as final-release gate**, unchanged. Previous recorded physical comparison exceeded 2× on the measured host/binary identity; R7 does not bind this result to the eventual release ELF.
- **Overall P15-v1-and-v2-composite-SRC-acceptance: OPEN**. No v2-default or release decision is authorized by this proof companion.

## The two fully qualified mathematical cells

| Source/cell | Passband | Source-stop | Total |
|---|---:|---:|---:|
| `dsd64.mastering.pcm44100` | 20/20 | 23/23 | **43/43** |
| `dsd256.mastering_v2.pcm44100` | 21/21 | 23/23 | **44/44** |
| **Total independent R7 replay** | **41/41** | **46/46** | **87/87** |

These statements concern all continuous frequencies within the listed intervals, not just a finite grid. They do **not** imply other rates, 384 kHz, all SRC-active cells, original campaign provenance, or release FFT4G equivalence.

## Mathematical kernel and release boundaries

The R7 exact-dyadic ball/linear-phase/reflected-support FIR bounds are proven as ordinary mathematical lemmas over rational frequency intervals, building on the R5 exact trig and R6 composite recurrence. The R7 verifier replays every bound and exact leaf partition from source-bound taps, and rechecks original amplitude inequalities rather than trusting the legacy PASS metadata. The original native DSP, SRC source, and FFT4G code are **unchanged**.

**Unfinished smallest coherent next job:** increase qualified cell coverage through rigorous, budgeted, resumable verification of additional 11,429 canonical intervals, especially bottlenecked 192/384-kHz and DSD256 rates. The mathematical bottleneck is composite spectral refinement over 4,160-tap rational stages and up to 9,408 inverse alias paths. Do not misclassify a time/resource refusal as a spectral counterexample. Keep compiled-execution FFT4G and release binary obligations separate.
