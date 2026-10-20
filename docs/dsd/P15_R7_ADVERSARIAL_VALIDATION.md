# P15 R7 — independent adversarial and integration validation

**Source archive:** SoX-NG cc399928. **Date:** 2026-10-19.

## Executed

- `PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r7_fast_fir test_p15_r7_fast_math test_p15_r6_exact_composite` — **40 tests PASS**. Coverage includes negative and asymmetric taps, cancellation, exact rational 0/Nyquist/quarter points, even and odd centered FIRs, source-unpaired fallback, strict refusal of approximate symmetry, interval-domain errors, nonfinite coefficients, integer-grid ball product/powers, agreement with independent R5 interval envelopes, and inherited R6 composite/oracle tests. The R5 comparisons corroborate; they are not the mathematical justification.
- Source-bound producer and *independent replay* of **87** canonical certificates: 20 pass + 23 source-stop for DSD64 mastering 44.1k; 21 pass + 23 source-stop for DSD256 mastering_v2 44.1k. Every original R7 candidate with an earlier method hash was **recomputed from source** against the final R7 method before publication; none was silently re-signed. Completed new canonical certificates have their own source and method fingerprints.
- `p15_r7_seal_evidence.py --workers 4 --source-archive ...` — rechecked **87/87** certificates in fresh worker processes, verified full canonical cell cover, source/operator fingerprint, and original source archive digest. Final machine-readable manifest SHA-256 is specified in the archive manifest and independently recomputable.
- `p15_r7_corrupt_real_proof.py --proof ...` — **6/6 deliberate corruptions REFUSED**, plus valid positive control PASSED. Rejected: changed kernel SHA, changed captured operator SHA, fabricated composite stop upper, missing exact interval endpoint, fabricated summary, and out-of-range frequency endpoint.
- Bounded high-rate `dsd256.mastering_v2.pcm384000` passband attempt for [0,1000] ended **OPEN** (not FAIL), with an exact-rational checkpoint; no spectral PASS asserted.

## Reproduce in installed cc399928 + R6/R7 addon

```bash
PYTHONPATH=tests/dsd python3 -m unittest -q \
  test_p15_r7_fast_fir test_p15_r7_fast_math test_p15_r6_exact_composite
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r7_corrupt_real_proof.py \
  --proof tests/dsd/results/P15_R7_REQUALIFIED_2026-10-19/9765832e7bce058bdf339ee713b1d023e22bf3c30325521755622a444723b321.r7.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r7_seal_evidence.py \
  --proofs tests/dsd/results/P15_R7_REQUALIFIED_2026-10-19 \
  --workers 4 --out /tmp/P15_R7_SEAL_REPLAY.json
```

The full 87-proof replay is computationally expensive (minutes on the present 4-vCPU environment), with exact method hashes and output deterministic except the explicit `directly_verified_source_archive` flag if the archive argument is omitted. Use resource/time budgets accordingly; no original historical mpmath campaign rerun is necessary. Avoid overwriting a differently signed evidence report (the writer refuses collisions).

## Unqualified work

Source-generated original campaign 11,516/11,516 remains historical coverage evidence, **not 11,516 independent new mathematical passes**. DSD256 at 384 kHz has a 4,160-tap rational FIR and up to 9,408 inverse alias histories and remains costly under leaf refinement. The bounded SIGALRM producer can be interrupted safely at leaf boundaries; accumulated OPEN leaves do not contribute to PASS. Final execution FFT4G/ELF, physical release, and other P15 gates remain unqualified by this work.
