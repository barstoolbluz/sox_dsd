# P15 high-rate continuation — checkpoint 04

Captured 2026-10-18T20:49:21.824602+00:00. The archive is an incremental overlay for the verified third-pass source. Counts below are computed from the exact archived receipt bytes, not a live directory listing after capture.

## Completed and independently checked

Two difficult cells have exhaustive canonical coverage:

| Cell | Passband obligations | Native-source stop obligations | Total |
|---|---:|---:|---:|
| DSD256 mastering → 384 kHz | 40, covering 0–40 kHz | 192, output coordinates 0–192 kHz | 232 / 232 |
| DSD256 wideband → 384 kHz | 142, covering 0–141.12 kHz | 192, output coordinates 0–192 kHz | 334 / 334 |

The independent verifier reconstructs the canonical worklist, verifies source/operator and exact proof snapshots, checks each preserved outward summary against independent exact-rational normative limits, and proves closed interval coverage. This is independent aggregation and scalar readjudication; it does not rerun each numerical proof tree.

- Mastering verification: `complete_cell/master256_384000_v1_complete/verification.json`, SHA-256 `fbf18769ee4944fff5ac29e194b67645e9b33d230a8512e97ff3bb2ff76d4424`.
- Wideband verification: `complete_cell/wide256_384000_final_complete/verification.json`, SHA-256 `139784a69ee08ca6c2afe45fd821e5af09a7dfa4bf9b2a2344cc2d1f6a6f7942`.

The mastering cell uses frozen high-rate v1 receipts plus strict exact-normative readjudication. Every wideband receipt uses the final corrected candidate3 proof. No receipt was rewritten.

The final candidate3 matched run is complete: eight PASS versus five PASS and three deadline OPENs for the untouched third-pass baseline. Common-pass wall sums are 64.825 → 35.532 seconds. Full raw measurements, identities, censoring qualifications, prior-version regressions, and reproduction scripts are preserved in the completed benchmark report and `performance/`.

The difficult DSD128 mastering_v2 → 384 kHz native-source stop obligation over closed 59–60 kHz also passed in 33.431 seconds, with upper 9.998666836350442e-9. Its diagnostic remains separate from the matched performance corpus.

## Frozen implementation and tests

The best proof uses the complementary-halfband complete-subtree majorant, terminal upper saturation, exact binary64-word cache keys, and full directed policy thresholds serialized exactly. The inherited binary64 threshold conversion was permissive by tiny slivers; independent readjudication of all 7,316 PASS summaries in the first inventory succeeds. The final inventory must be refreshed after the remaining campaign.

The 137-test numerical run passed with three expected source-only skips. A subsequent eight-test independent population run explicitly verified exhaustive traversal against an exact rational sum of direct-complex upper endpoints; twelve final reporting tests also passed. Supplemental source snapshots and logs are retained. Production audio code, filter coefficients, normative tolerances, release policy, and the original bounded dispatcher remain unchanged.

The integration patch is frozen under `integration/`. It applies with GNU patch, `-p1 --fuzz=0 --batch --forward`, to four untouched baseline preimages and adds twelve files. All sixteen resulting hashes match the best source. Patch SHA-256: `0d0e5b7663b411ff3931f0af26bc820dff6f4e70edc6f872944077e4514007d7`.

## Exact receipt-instance counts in this checkpoint

These include repeated canonical work in separate experiments and are not a coverage union.

```json
{
  "campaign_candidate_60s": {
    "OPEN": 26,
    "PASS-LOCAL-BAND": 85,
    "PASS-LOCAL-STOP-SOURCE": 272
  },
  "campaign_final_strict_60s": {
    "PASS-LOCAL-BAND": 172,
    "PASS-LOCAL-STOP-SOURCE": 192
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
    "OPEN": 3,
    "PASS-LOCAL-BAND": 11,
    "PASS-LOCAL-STOP-SOURCE": 2
  }
}
```

## Remaining work and exact resume

The final 927-job campaign is still running. DSD256 mastering_v2 → 384 kHz and wideband → 192 kHz are complete-cell targets still awaiting exhaustive aggregation. The rest of the plan covers all nine 384 kHz cells, the other DSD256 192 kHz profiles, cross-family 44.1 kHz cases, and the largest 18,816-path populations at 96 kHz, including exact rational boundary neighborhoods.

1. Verify the supplied source archive SHA-256 `d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4`, extract it, and overlay this checkpoint's `sox_ng/` directory. Check `P15_CHECKPOINT_04_SHA256SUMS` from that repository root.
2. Use the recorded Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0 and mpmath 1.3.0 environment. `integration/README.md` describes isolated setup and source reconstruction. The final full proof map is `reference_high_rate_final_code/IDENTITY.json`.
3. Resume `execution/CAMPAIGN_FINAL_STRICT_PLAN.json` with `execution/run_experiments.py`, final proof source, output `campaign_final_strict_60s`, `--workers 7 --cpu-start 0 --seconds 60 --external-seconds 85`. Keep the recorded source/resource identity for idempotent resume; use a new output directory if any identity changes. The supervisor supplies external process termination in addition to the internal signal budget.
4. When all jobs are recorded, inspect any OPEN reasons. Retry necessary complete-cell gaps in a new bounded larger-budget directory if feasible. Do not call a timeout a spectral violation.
5. Publish the remaining independent complete-cell manifests. Refresh `complete_cell/normative_readjudication_02/verification.json`, admitting every final PASS actually used. `execution/FINAL_AGGREGATION_RECIPE.md` and `aggregate_final.py` check exact input populations and fail closed on incomplete plans or stale readjudication.
6. Generate `census_final_01` and `coverage_final_01`, preserving existing snapshots. Finalize the persistent continuation and source/receipt manifests. `execution/package_final.py` is a prepared delivery utility; it requires completed coverage and continuation before building and re-reading both archives. It has not yet produced final source archives in this checkpoint.

The applicable P15 release disposition remains **BLOCKED**. The October 16 physical comparator measurements exist and exceed the recorded ratio threshold but await adjudication; full historical payload replay is incomplete and older closeout inputs are stale. Arbitrary-input FFT4G execution roundoff remains unproved. Existing v2 observations are broader than the old handoff suggested, but their missing numeric payloads prevent full replay. No v2 default promotion or P16 authorization has changed.

Durable upload remains unavailable because the official service returned `library_storage_limit_exceeded`. The local checkpoint is downloadable.
