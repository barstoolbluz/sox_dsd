# P15 high-rate coverage report

**Snapshot status: SELECTED_PLANS_RECORDED. P15 remains BLOCKED.**

The explicitly selected current runs contain **1148 distinct canonical local passes**. Of these, **1082** were OPEN in the original 60-second campaign. The exact union of the original 6,835 passes and these current passes is **7917 / 11,516**.

Including the historical 600-second sample and four third-pass final local receipts produces **7936 / 11,516** explicitly covered intervals. This is a separate evidence union: **1063** current passes are beyond those prior receipts. Historical receipts retain their original status.

## Inherited threshold defect and strict readjudication

Review found that the inherited conversion of dB decision limits to binary64 amplitudes could widen the acceptance envelope through binary64 rounding. A recorded PASS flag or a textual `limits` field is therefore insufficient by itself. The final corrected prover exactly serializes the full directed threshold intervals: PASS uses their inward endpoints, and a generic FAIL uses their outward endpoints. Stored proof bounds also preserve exact endpoints.

All **8266 contributing PASS receipts** in the unions above have independently passed exact normative comparisons of their preserved outward enclosure summaries. `STRICT_NORMATIVE_READJUDICATION.json` binds each exact receipt hash to `tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json` and its manifested verifier implementation. This checks the stored scalar bounds against the unchanged 0.0001-dB / 160-dB obligations; it does not rerun interval arithmetic, alias enumeration, phase identities, or internal proof-tree coverage. Historical receipts and dispositions remain unchanged.

## Proof implementation and decode-profile versions

The proof implementation identifiers describe numerical prover code. The cell component `mastering_v2` describes the captured decode profile and coefficients. These are independent version axes: running a newer proof implementation does not promote or change a decode profile.

| Measurement label | Role | Frozen proof snapshot | Snapshot description |
|---|---|---|---|
| baseline_matched_final_60s | third-pass baseline | `tests/dsd/results/P15_high_rate_2026-10-18/reference_third_pass_code` | Exact module map retained in IDENTITY.json |
| baseline_matched_v1_60s | third-pass baseline | `tests/dsd/results/P15_high_rate_2026-10-18/reference_third_pass_code` | Exact module map retained in IDENTITY.json |
| baseline_matched_v2b_60s | third-pass baseline | `tests/dsd/results/P15_high_rate_2026-10-18/reference_third_pass_code` | Exact module map retained in IDENTITY.json |
| candidate_final_campaign_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_final_code` | candidate3: halfband subtree bounds, terminal saturation, exact-word cache, full directed normative thresholds |
| candidate_final_matched_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_final_code` | candidate3: halfband subtree bounds, terminal saturation, exact-word cache, full directed normative thresholds |
| candidate_final_retry_180s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_final_code` | candidate3: halfband subtree bounds, terminal saturation, exact-word cache, full directed normative thresholds |
| candidate_final_wide256_192000_6000_7000_180s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_final_code` | candidate3: halfband subtree bounds, terminal saturation, exact-word cache, full directed normative thresholds |
| candidate_v1_campaign_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_v1_code` | Exact module map retained in IDENTITY.json |
| candidate_v1_diagnostic_180s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_v1_code` | Exact module map retained in IDENTITY.json |
| candidate_v1_matched_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_v1_code` | Exact module map retained in IDENTITY.json |
| candidate_v2b_diagnostic_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_v2_code` | candidate2 v2b: terminal saturation plus exact coefficient-word cache identity |
| candidate_v2b_matched_60s | candidate proof implementation | `tests/dsd/results/P15_high_rate_2026-10-18/reference_high_rate_v2_code` | candidate2 v2b: terminal saturation plus exact coefficient-word cache identity |

## Difficult cells

| Cell | Canonical pass + stop | Original OPEN | Candidate PASS | Candidate OPEN | Unmeasured | Complete candidate cover |
|---|---:|---:|---:|---:|---:|---|
| dsd64.mastering.pcm384000 | 20 + 192 | 212 | 11 | 0 | 201 | no |
| dsd64.wideband.pcm384000 | 36 + 192 | 228 | 10 | 0 | 218 | no |
| dsd128.mastering.pcm384000 | 30 + 192 | 220 | 12 | 0 | 210 | no |
| dsd128.wideband.pcm384000 | 71 + 192 | 263 | 12 | 0 | 251 | no |
| dsd256.mastering.pcm192000 | 40 + 96 | 136 | 12 | 0 | 124 | no |
| dsd256.mastering.pcm384000 | 40 + 192 | 232 | 232 | 0 | 0 | yes |
| dsd256.wideband.pcm192000 | 92 + 96 | 188 | 188 | 0 | 0 | yes |
| dsd256.wideband.pcm384000 | 142 + 192 | 282 | 334 | 0 | 0 | yes |
| dsd64.mastering_v2.pcm384000 | 25 + 192 | 217 | 11 | 0 | 206 | no |
| dsd128.mastering_v2.pcm384000 | 48 + 192 | 240 | 13 | 0 | 227 | no |
| dsd256.mastering_v2.pcm192000 | 66 + 96 | 162 | 12 | 0 | 150 | no |
| dsd256.mastering_v2.pcm384000 | 66 + 192 | 257 | 258 | 0 | 0 | yes |

Candidate OPEN means at least one candidate attempt exists and none of the included candidate versions/budgets supplied a PASS. Unmeasured intervals have no candidate attempt in this snapshot. Neither classification establishes a spectral violation.

## Complete-cell evidence

- **dsd256.mastering.pcm384000: 232 / 232 canonical intervals**, comprising 40 passband and 192 native-source-stop intervals.
- **dsd256.mastering_v2.pcm384000: 258 / 258 canonical intervals**, comprising 66 passband and 192 native-source-stop intervals.
- **dsd256.wideband.pcm192000: 188 / 188 canonical intervals**, comprising 92 passband and 96 native-source-stop intervals.
- **dsd256.wideband.pcm384000: 334 / 334 canonical intervals**, comprising 142 passband and 192 native-source-stop intervals.

`COMPLETE_CELL_WITNESSES.json` names every canonical interval and immutable receipt hash, verifies exact shared endpoints from DC to each required upper edge, and binds the unchanged source. Local proofs from different recognized proof snapshots may cover the same unchanged coefficient operator. This is ideal-coefficient spectral coverage; FFT4G arithmetic and release adjudication remain separate.

## Boundary and difficult-population coverage

`BOUNDARY_COVERAGE.json` separately audits the selected plans and the union of candidate PASS intervals. It records exact output-frequency event locations and coverage of the point, left neighborhood, and right neighborhood. Planned coverage is never counted as a numerical certificate.

| Cell with candidate PASS | Passband DC / upper edge | Stop-output DC / Nyquist | Pass routing events, both sides | Stop routing events, both sides | Complete paths |
|---|---|---|---:|---:|---:|
| dsd128.mastering.pcm384000 | yes / yes | yes / yes | 7 | 9 | 4704 |
| dsd128.mastering_v2.pcm384000 | yes / yes | yes / yes | 7 | 9 | 4704 |
| dsd128.wideband.pcm384000 | yes / yes | yes / yes | 7 | 8 | 4704 |
| dsd256.mastering.pcm192000 | yes / yes | yes / yes | 6 | 9 | 9408 |
| dsd256.mastering.pcm384000 | yes / yes | yes / yes | 66 | 319 | 9408 |
| dsd256.mastering.pcm96000 | yes / yes | yes / yes | 3 | 5 | 18816 |
| dsd256.mastering_v2.pcm192000 | yes / yes | yes / yes | 7 | 9 | 9408 |
| dsd256.mastering_v2.pcm384000 | yes / yes | yes / yes | 109 | 319 | 9408 |
| dsd256.mastering_v2.pcm96000 | yes / yes | yes / yes | 4 | 5 | 18816 |
| dsd256.wideband.pcm192000 | yes / yes | yes / yes | 75 | 79 | 9408 |
| dsd256.wideband.pcm384000 | yes / yes | yes / yes | 117 | 159 | 4704 |
| dsd64.mastering.pcm384000 | yes / yes | yes / yes | 15 | 18 | 4704 |
| dsd64.mastering_v2.pcm384000 | yes / yes | yes / yes | 15 | 18 | 4704 |
| dsd64.wideband.pcm384000 | yes / yes | yes / yes | 13 | 15 | 4704 |

Every PASS interval starting at zero covers DC and all frequencies arbitrarily close to zero within that interval. Source Nyquist is not an output-frequency endpoint: the complete native lattice uses the half-open interval [−Fnative/2, Fnative/2), and its Nyquist family relabels at output frequencies congruent to −Fnative/2 modulo the primitive spacing. Those exact events and both applicable limits are audited separately. At DC and the upper edge, only the neighborhood inside the normative output band is required.

Native-source-stop jobs range over the output-frequency domain and enclose every included native source alias at or above the declared source stop edge. The audit distinguishes source-stop membership crossings from routing crossings. It does not add a new acceptance band inside the source transition region. Independent tests cover rational one-sided limits, zero and near-zero amplitudes, cancellation, phase-retaining complex references, and repeated alias paths; selected canonical intervals are not advertised as an exhaustive search for maximum cancellation.

## Matched complete-prover performance

### baseline_matched_v1_60s:candidate_v1_matched_60s

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

### baseline_matched_v2b_60s:candidate_v2b_matched_60s

26 matched observations: baseline 22 PASS, candidate 26 PASS. Inputs, operator hashes, harness, budgets, CPU affinity, Python, and numerical-library versions are checked for each pair.

Across 22 PASS/PASS pairs, the geometric mean complete-prover speedup is **1.543×**, ranging from 1.006× to 3.763×. Ratios below 1 are measured regressions. Timeout results are censored and excluded from this ratio.

| Cell / band / interval (Hz) | Baseline s | Candidate s | Ratio | Outcome |
|---|---:|---:|---:|---|
| dsd64.mastering.pcm44100 / pass / 0–1000 | 0.858 | 0.853 | 1.006× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd64.mastering.pcm384000 / pass / 19000–20000 | 60.008 | 59.653 | censored | OPEN → PASS-LOCAL-BAND |
| dsd64.mastering.pcm384000 / stop / 191000–192000 | 16.741 | 15.126 | 1.107× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd64.wideband.pcm384000 / pass / 35000–35280 | 43.033 | 19.555 | 2.201× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd64.wideband.pcm384000 / stop / 191000–192000 | 16.982 | 16.148 | 1.052× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.mastering.pcm384000 / pass / 29000–30000 | 16.453 | 9.297 | 1.770× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.mastering.pcm384000 / stop / 191000–192000 | 16.539 | 10.028 | 1.649× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.wideband.pcm384000 / pass / 70000–70560 | 16.366 | 9.322 | 1.756× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.wideband.pcm384000 / stop / 191000–192000 | 14.932 | 10.206 | 1.463× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering.pcm44100 / pass / 0–1000 | 9.794 | 2.603 | 3.763× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm192000 / pass / 39000–40000 | 60.031 | 27.268 | censored | OPEN → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / pass / 0–1000 | 16.192 | 9.512 | 1.702× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / pass / 39000–40000 | 15.133 | 10.563 | 1.433× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / stop / 80000–81000 | 16.711 | 10.048 | 1.663× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering.pcm384000 / stop / 191000–192000 | 16.431 | 9.824 | 1.672× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.wideband.pcm192000 / pass / 91000–91200 | 9.503 | 7.587 | 1.253× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.wideband.pcm192000 / stop / 95000–96000 | 10.479 | 9.304 | 1.126× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.wideband.pcm384000 / pass / 141000–141120 | 7.982 | 6.191 | 1.289× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.wideband.pcm384000 / stop / 191000–192000 | 8.595 | 5.427 | 1.584× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd64.mastering_v2.pcm384000 / pass / 24000–25000 | 60.022 | 48.887 | censored | OPEN → PASS-LOCAL-BAND |
| dsd64.mastering_v2.pcm384000 / stop / 191000–192000 | 19.066 | 15.440 | 1.235× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd128.mastering_v2.pcm384000 / pass / 47000–48000 | 16.566 | 10.486 | 1.580× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd128.mastering_v2.pcm384000 / stop / 191000–192000 | 17.594 | 9.638 | 1.825× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd256.mastering_v2.pcm192000 / pass / 65000–66000 | 60.020 | 29.481 | censored | OPEN → PASS-LOCAL-BAND |
| dsd256.mastering_v2.pcm384000 / pass / 65000–66000 | 17.473 | 10.595 | 1.649× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering_v2.pcm384000 / stop / 191000–192000 | 18.819 | 11.333 | 1.661× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |

### baseline_matched_final_60s:candidate_final_matched_60s

8 matched observations: baseline 5 PASS, candidate 8 PASS. Inputs, operator hashes, harness, budgets, CPU affinity, Python, and numerical-library versions are checked for each pair.

Across 5 PASS/PASS pairs, the geometric mean complete-prover speedup is **1.816×**, ranging from 1.029× to 4.286×. Ratios below 1 are measured regressions. Timeout results are censored and excluded from this ratio.

| Cell / band / interval (Hz) | Baseline s | Candidate s | Ratio | Outcome |
|---|---:|---:|---:|---|
| dsd64.mastering.pcm44100 / pass / 0–1000 | 0.910 | 0.885 | 1.029× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd64.mastering.pcm384000 / pass / 19000–20000 | 60.009 | 59.087 | censored | OPEN → PASS-LOCAL-BAND |
| dsd256.mastering.pcm44100 / pass / 0–1000 | 11.172 | 2.606 | 4.286× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm192000 / pass / 39000–40000 | 60.031 | 31.360 | censored | OPEN → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / pass / 39000–40000 | 16.884 | 9.377 | 1.801× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |
| dsd256.mastering.pcm384000 / stop / 191000–192000 | 16.425 | 11.093 | 1.481× | PASS-LOCAL-STOP-SOURCE → PASS-LOCAL-STOP-SOURCE |
| dsd64.mastering_v2.pcm384000 / pass / 24000–25000 | 60.016 | 52.118 | censored | OPEN → PASS-LOCAL-BAND |
| dsd256.mastering_v2.pcm384000 / pass / 65000–66000 | 19.433 | 11.570 | 1.680× | PASS-LOCAL-BAND → PASS-LOCAL-BAND |

## What prevents remaining certification

The observed classification matrix contains 22 intervals certified by the third-pass baseline within the explicitly recorded budgets, 23 intervals with a 60-second candidate OPEN and a larger-budget PASS using the same proof implementation and numerical limits, and 203 intervals whose original operator-path precondition is now resolved by a candidate PASS. Larger-budget observations are feasibility evidence; their execution environments need not be matched timing pairs.

For intervals still candidate-OPEN, recorded attempt reasons are: `{}`. These counts describe attempts; repeated budgets can contribute more than one reason to an interval.

The structural census separates path population from routing density. DSD256 mastering at 384 kHz has 9,408 complete paths and routing transitions every 600 Hz. DSD64 at 384 kHz has 4,704 paths, three SRC stages, and transitions every 300 Hz. DSD256 wideband at 192 kHz has 9,408 paths for 4,704 source families; multiplicity is retained.

FIR evaluation counts, finite-difference uses, alias-frontier operations, proof nodes, subdivisions, wall time, CPU time, and memory are retained in raw receipts and matched results. Missing baseline instrumentation is reported as null. The structural effort estimate is a work proxy, not a runtime prediction.

Remaining timeouts do not by themselves distinguish repeated numerical work, a conservative bound, path expansion, or a true envelope violation. No included receipt is a source-bound violation witness. Exact stop-membership crossings are also distinct from routing crossings; their presence alone does not prove that splitting them would resolve an OPEN.

## Reproduction and interpretation

Every current receipt is checked against an explicitly named complete frozen proof-code snapshot. Flat snapshots must be overlaid onto an extracted source repository for numerical replay; importing them as standalone repositories would change source-root resolution. Existing canonical receipts are never overwritten.

The accounting code verifies coverage and provenance. It does not recompute the interval arithmetic. Independent numerical replays and correctness tests are separate evidence. P15 remains BLOCKED until its independent production-arithmetic and release obligations are discharged.
