# P15 high-rate continuation — checkpoint 03

Captured 2026-10-18T20:37:51.258905+00:00.

## Verified result

DSD256 mastering → 384000 Hz is completely certified across all232 canonical obligations:40 passband intervals cover[0,40000]Hz and192 native-source-stop obligations cover the output-coordinate range[0,192000]Hz. The independent verifier reconstructs the entire canonical work set, checks source/operator/proof identities, checks the recorded outward bounds against exact rational normative limits, and proves closed coverage. It does not numerically replay the original interval calculation. The immutable verification is `complete_cell/master256_384000_v1_complete/verification.json` (SHA256 fbf18769ee4944fff5ac29e194b67645e9b33d230a8512e97ff3bb2ff76d4424).

The first high-rate campaign finished383 jobs:357PASS and26OPEN. The final combined candidate2 matched26-case run finished with26PASS; the untouched third-pass baseline had22PASS and4OPEN. Fresh candidate3 comparisons are in progress.

## Best corrected implementation

The working proof is now frozen candidate3: exact complementary-halfband complete-subtree upper bounds, terminal-upper saturation preserving every remaining alias contribution, exact binary64-word cache identity, and a correctness fix for inherited policy threshold representation. No production audio source, coefficient, normative band, or release policy changed.

The inherited `db_band` helper widened its binary64 acceptance limits by tiny slivers. Candidate3 serializes the full directed multiprecision intervals exactly; PASS uses inward guards and FAIL retains outward guards. All7,316 existing PASS summaries in the first exact-normative readjudication inventory passed independently; this includes6,835 original canonicalPASS,36 historical600-secondPASS,4third-pass locals and441 current receipt instances. It is scalar-bound readjudication, not numerical replay. The completed232-interval cell also passes these exact limits.

The final regression ran137 tests:134PASS and3 expected source-only skips,59.020533 wall seconds,272520KiB peak childRSS,zero source drift. Focused independent tests include full continuous halfband reference cover, multiplicity, rational boundaries, cancellation, cache words, import/binding drift, complete-coverage aggregation and six exact policy-rounding tests. Logs preserve prior failed implementation/test attempts and their corrections.

## Snapshot counts

These are receipt-instance counts at capture and can include repeated canonical work in separate matched runs. They are not a global coverage union.

```json
{
  "campaign_candidate_60s": {
    "OPEN": 26,
    "PASS-LOCAL-BAND": 85,
    "PASS-LOCAL-STOP-SOURCE": 272
  },
  "campaign_final_strict_60s": {
    "PASS-LOCAL-BAND": 14
  },
  "matched_final_combined": {
    "OPEN": 4,
    "PASS-LOCAL-BAND": 26,
    "PASS-LOCAL-STOP-SOURCE": 22
  },
  "matched_final_round1": {
    "OPEN": 4,
    "PASS-LOCAL-BAND": 22,
    "PASS-LOCAL-STOP-SOURCE": 22
  },
  "matched_final_strict": {
    "PASS-LOCAL-BAND": 4
  }
}
```

## Resume without overwriting evidence

1. Verify the submitted archive SHA256 `d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4`. Extract it and overlay this checkpoint's `sox_ng/` contents. This checkpoint is an incremental overlay, not the complete source bundle.
2. Use Python3.12, NumPy2.3.5 and mpmath1.3.0. Put dependencies on PYTHONPATH and set OPENBLAS_NUM_THREADS=1. The exact current fifteen-module proof map is `reference_high_rate_final_code/IDENTITY.json`. Earlier full maps are `reference_third_pass_code/`, `reference_high_rate_v1_code/`, and `reference_high_rate_v2_code/`; version2a diagnostic source copies are also retained.
3. Continue `execution/CAMPAIGN_FINAL_STRICT_PLAN.json` with `execution/run_experiments.py --source-root <candidate3-root> --output <evidence>/campaign_final_strict_60s --workers7 --cpu-start0`. The actual syntax uses spaces after options (for example `--workers 7 --cpu-start 0`). Keep the same canonical plan, code,60-second signal budget,85-second process kill limit and CPU assignment for idempotent resume. Different resources or code require a new output directory.927jobs are planned, targeting complete DSD256wideband384, mastering_v2 384, wideband192 and the diverse extension.
4. Continue `execution/MATCHED_FINAL_STRICT_PLAN.json` paired with the separately extracted untouched baseline, `--workers 1 --cpu-start 7`, using `matched_final_strict/`. The baseline source must remain separate; the harness validates actual imports and hashes. All final supervisor commands are retained in supervision request receipts.
5. Final reporting must use the updated census and coverage report, a newly refreshed exact-normative readjudication inventory admitting every used PASS SHA, and new output directories. Do not alter previous PASS or OPEN receipts. Source-stop interval coordinates are output frequency; the obligation concerns native-source families at or above S.
6. Finish exhaustive aggregation of each target cell, final performance report, continuation, source/receipt manifests, compact integration patch, and complete source archive. If any target interval remainsOPEN, retry under a bounded larger budget in a fresh directory or explicitly retain the gap.

## Remaining independent obligations

P15 remains BLOCKED. All33,487 inventoried inherited files, including16,711 priorpins, were byte-identical at the retained integrity check. The October16 P/S-matched physical measurements exist: all8lower confidence ratios exceed2, but results remain unadjudicated and replay payloads are incomplete; stale closeout binding is a separate issue. FFT4G arbitrary-input execution roundoff remainsOPEN. The old v2 metrology handoff understates existing scalar coverage; missing raw payloads and authorization remain separate. No v2 default promotion or P16 authorization.

The official persistence upload failed with `library_storage_limit_exceeded`. Local download artifacts are available; durable upload has not succeeded.
