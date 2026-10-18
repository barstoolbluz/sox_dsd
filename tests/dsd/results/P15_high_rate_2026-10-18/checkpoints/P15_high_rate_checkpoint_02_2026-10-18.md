# P15 high-rate continuation — checkpoint 02

Captured 2026-10-18T20:21:26.342074+00:00.

Validated high-rate version 1 is frozen while its campaign runs. The improvement is the exact complementary-halfband complete-subtree magnitude majorant. Production source, filters, normative bands and historical receipts remain unchanged. The entire DSD256 mastering → 384 kHz guaranteed passband has 40 canonical PASS receipts; full native-source stop coverage is still running. This checkpoint contains 131 completed main-campaign receipts, of which 118 are PASS, plus the available matched measurements and diagnostic evidence. Counts are those captured in this archive, not a claim of final campaign completion.

An independent DSD64 mastering → 384 kHz 19–20 kHz interval passed at about 120 seconds under a 180-second budget. A separate candidate2 experiment is investigating early return when fixed evaluated-leaf upper endpoints already prevent the current interval bound from passing. That change is NOT integrated into the validated version 1 proof sources in this checkpoint.

## Resume

1. Verify the submitted third-pass archive SHA-256 d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4. Extract it, then overlay the sox_ng/ contents of this checkpoint. The checkpoint contains an incremental repository overlay; it is not a complete source archive.
2. Use Python 3.12, NumPy 2.3.5 and mpmath 1.3.0; set OPENBLAS_NUM_THREADS=1 and put mpmath on PYTHONPATH if needed. All proof imports are explicitly rooted by p15_high_rate_experiment.py.
3. Canonical source, plans, current evidence, fixed proof snapshots and authority findings are under tests/dsd/results/P15_high_rate_2026-10-18/. The original p15_full_band_campaign.py dispatcher is unchanged.
4. Continue execution/CAMPAIGN_PLAN.json with execution/run_experiments.py --source-root . --output tests/dsd/results/P15_high_rate_2026-10-18/campaign_candidate_60s --workers 5 --cpu-start 2. Keep the same job plan, CPU assignment and 60-second budget for exact idempotent resume. If resources or code change, use a fresh output directory. The external supervisor enforces 85 seconds per child independently of the 60-second Python signal deadline.
5. Continue matched comparisons only with the separately extracted baseline and the frozen version 1 proof sources. reference_third_pass_code/ and reference_high_rate_v1_code/ contain their exact imported proof-module maps. Never overwrite an existing receipt to change its identity.
6. Final coverage aggregation must use the corrected census validator and a new output directory. Do not relabel historical OPEN receipts.

## Verified work and open obligations

The numerical regression suite completed 104 passing tests and 3 expected source-only skips (107 total); corrected census overlay binding subsequently passed 19 focused tests. Test commands, hashes and logs are retained. Exact halfband continuous reference comparisons, alias multiplicity, cancellation, rational boundaries, and import/binding drift have independent tests.

The 33,487-file inherited integrity inventory, including the previously pinned 16,711 files, is retained under authority/. P15 remains BLOCKED. The October 16 physical comparator measurements exist and exceed the physical ratio threshold but remain unadjudicated; stale closeout inputs and incomplete replay payloads are separate limitations. The arbitrary-input FFT4G execution-roundoff proof remains open. No v2 default or P16 authorization has changed.

The final deliverables, exhaustive full-cell aggregate, completed matched performance report, final integration choice and source archives remain to be produced. Library upload was attempted through the official prepared-upload helper and failed with library_storage_limit_exceeded; this local checkpoint is downloadable, but durable persistence was not established.
