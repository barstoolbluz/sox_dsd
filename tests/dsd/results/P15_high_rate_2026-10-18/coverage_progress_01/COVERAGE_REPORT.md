# P15 high-rate coverage report

**Snapshot status: IN_PROGRESS. P15 remains BLOCKED.**

The explicitly selected current runs contain **215 distinct canonical local passes**. Of these, **208** were OPEN in the original 60-second campaign. The exact union of the original 6,835 passes and these current passes is **7043 / 11,516**.

Including the historical 600-second sample and four third-pass final local receipts produces **7074 / 11,516** explicitly covered intervals. This is a separate evidence union: **201** current passes are beyond those prior receipts. Historical receipts retain their original status.

## Difficult cells

| Cell | Canonical pass + stop | Original OPEN | Candidate PASS | Candidate OPEN | Unmeasured | Complete candidate cover |
|---|---:|---:|---:|---:|---:|---|
| dsd64.mastering.pcm384000 | 20 + 192 | 212 | 7 | 4 | 201 | no |
| dsd64.wideband.pcm384000 | 36 + 192 | 228 | 6 | 4 | 218 | no |
| dsd128.mastering.pcm384000 | 30 + 192 | 220 | 12 | 0 | 210 | no |
| dsd128.wideband.pcm384000 | 71 + 192 | 263 | 11 | 0 | 252 | no |
| dsd256.mastering.pcm192000 | 40 + 96 | 136 | 8 | 4 | 124 | no |
| dsd256.mastering.pcm384000 | 40 + 192 | 232 | 152 | 0 | 80 | no |
| dsd256.wideband.pcm192000 | 92 + 96 | 188 | 2 | 0 | 186 | no |
| dsd256.wideband.pcm384000 | 142 + 192 | 282 | 2 | 0 | 332 | no |
| dsd64.mastering_v2.pcm384000 | 25 + 192 | 217 | 1 | 1 | 215 | no |
| dsd128.mastering_v2.pcm384000 | 48 + 192 | 240 | 2 | 0 | 238 | no |
| dsd256.mastering_v2.pcm192000 | 66 + 96 | 162 | 0 | 0 | 162 | no |
| dsd256.mastering_v2.pcm384000 | 66 + 192 | 257 | 2 | 0 | 256 | no |

Candidate OPEN means at least one candidate attempt exists and none of the included candidate versions/budgets supplied a PASS. Unmeasured intervals have no candidate attempt in this snapshot. Neither classification establishes a spectral violation.

## Complete-cell evidence

No complete candidate cell is claimed in this snapshot. Remaining canonical intervals remain explicitly unproved or unmeasured.

## Matched complete-prover performance

### baseline_matched:candidate_matched

24 matched observations: baseline 22 PASS, candidate 22 PASS. Inputs, operator hashes, harness, budgets, CPU affinity, Python, and numerical-library versions are checked for each pair.

Across 22 PASS/PASS pairs, the geometric mean complete-prover speedup is **1.370×**, ranging from 0.910× to 1.841×. Ratios below 1 are measured regressions. Timeout results are censored and excluded from this ratio.

| Cell / band / interval (Hz) | Baseline s | Candidate s | Ratio | Outcome |
|---|---:|---:|---:|---|
| dsd64.mastering.pcm44100 / pass / 0–1000 | 0.979 | 0.893 | 1.096× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd64.mastering.pcm384000 / pass / 19000–20000 | 60.007 | 60.008 | censored | OPEN → OPEN |
| dsd64.mastering.pcm384000 / stop / 191000–192000 | 16.496 | 16.470 | 1.002× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd64.wideband.pcm384000 / pass / 35000–35280 | 41.968 | 34.515 | 1.216× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd64.wideband.pcm384000 / stop / 191000–192000 | 17.018 | 16.074 | 1.059× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.mastering.pcm384000 / pass / 29000–30000 | 16.599 | 10.965 | 1.514× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.mastering.pcm384000 / stop / 191000–192000 | 18.439 | 10.619 | 1.736× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.wideband.pcm384000 / pass / 70000–70560 | 17.318 | 9.406 | 1.841× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.wideband.pcm384000 / stop / 191000–192000 | 15.695 | 11.530 | 1.361× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering.pcm44100 / pass / 0–1000 | 11.187 | 12.299 | 0.910× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / pass / 0–1000 | 15.354 | 9.805 | 1.566× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / pass / 39000–40000 | 16.499 | 9.954 | 1.657× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / stop / 80000–81000 | 16.204 | 10.064 | 1.610× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering.pcm384000 / stop / 191000–192000 | 16.177 | 11.100 | 1.457× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.wideband.pcm192000 / pass / 91000–91200 | 9.766 | 7.561 | 1.292× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.wideband.pcm192000 / stop / 95000–96000 | 9.000 | 8.348 | 1.078× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.wideband.pcm384000 / pass / 141000–141120 | 9.379 | 6.234 | 1.504× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.wideband.pcm384000 / stop / 191000–192000 | 8.680 | 6.818 | 1.273× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd64.mastering_v2.pcm384000 / pass / 24000–25000 | 60.009 | 60.006 | censored | OPEN → OPEN |
| dsd64.mastering_v2.pcm384000 / stop / 191000–192000 | 16.859 | 17.211 | 0.979× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.mastering_v2.pcm384000 / pass / 47000–48000 | 20.314 | 11.188 | 1.816× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.mastering_v2.pcm384000 / stop / 191000–192000 | 19.655 | 11.523 | 1.706× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering_v2.pcm384000 / pass / 65000–66000 | 18.124 | 12.032 | 1.506× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering_v2.pcm384000 / stop / 191000–192000 | 19.335 | 11.919 | 1.622× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |

## What prevents remaining certification

The observed classification matrix contains 22 intervals certified by the third-pass baseline within the explicitly recorded budgets, and 1 intervals with a 60-second candidate OPEN followed by a larger-budget PASS.

For intervals still candidate-OPEN, recorded attempt reasons are: `{"interval_wall_clock_budget_exhausted": 13}`. These counts describe attempts; repeated budgets can contribute more than one reason to an interval.

The structural census separates path population from routing density. DSD256 mastering at 384 kHz has 9,408 complete paths and routing transitions every 600 Hz. DSD64 at 384 kHz has 4,704 paths, three SRC stages, and transitions every 300 Hz. DSD256 wideband at 192 kHz has 9,408 paths for 4,704 source families; multiplicity is retained.

FIR evaluation counts, finite-difference uses, alias-frontier operations, proof nodes, subdivisions, wall time, CPU time, and memory are retained in raw receipts and matched results. Missing baseline instrumentation is reported as null. The structural effort estimate is a work proxy, not a runtime prediction.

Remaining timeouts do not by themselves distinguish repeated numerical work, a conservative bound, path expansion, or a true envelope violation. No included receipt is a source-bound violation witness. Exact stop-membership crossings are also distinct from routing crossings; their presence alone does not prove that splitting them would resolve an OPEN.

## Reproduction and interpretation

Every current receipt is checked against an explicitly named complete frozen proof-code snapshot. Flat snapshots must be overlaid onto an extracted source repository for numerical replay; importing them as standalone repositories would change source-root resolution. Existing canonical receipts are never overwritten.

The accounting code verifies coverage and provenance. It does not recompute the interval arithmetic. Independent numerical replays and correctness tests are separate evidence. P15 remains BLOCKED until its independent production-arithmetic and release obligations are discharged.
