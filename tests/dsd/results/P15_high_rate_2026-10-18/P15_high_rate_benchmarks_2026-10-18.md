# P15 high-rate prover: measured performance and certification

**Date:** 2026-10-18. **Scope:** ideal-coefficient, source-bound continuous-frequency spectral certificates. These results do not discharge FFT4G execution-roundoff, physical-comparator adjudication, or other release obligations.

The final corrected candidate3 implementation improves **5 PASS / 3 OPEN to 8 PASS / 0 OPEN** in its fresh matched round, with a **1.824× wall-time ratio of sums on the five common passes**. The larger candidate2 v2b round improves **22 PASS / 4 OPEN to 26 PASS / 0 OPEN**, using the same 60-second interval budgets. On its 22 common passes, prover wall time falls from **342.244 to 219.087 seconds**, a **1.562× ratio of sums**. Including timeout cost, v2b certification throughput increases from **136.74 to 244.82 certificates per prover CPU-hour**. These are results for the stated corpora and proof versions, not an extrapolated full-campaign speedup.

## 1. Version and evidence boundaries

Four implementations have distinct proof-code identities:

| Version | Changes from the supplied third pass | Principal evidence |
|---|---|---|
| Third-pass baseline | Supplied implementation, including the existing finite-difference FIR majorant | Baseline halves of every matched pair |
| High-rate v1 | Certified complementary-halfband pair bound and complete-subtree cap | `matched_final_round1`, `profiles/final_v1` |
| Candidate2 v2b | V1 plus terminal-upper saturation and exact binary64-word halfband-cache keys | `matched_final_combined`, isolated terminal diagnostics |
| Candidate3 | V2b plus full directed policy-limit intervals with exact dyadic-to-decimal serialization | `matched_final_strict`; final strict campaign |

The original finite-difference kernel is unchanged in all four versions. V2b's cache correction affects admission and identity of synthetic signed-zero or equal-valued non-float inputs; the captured source taps do not depend on those exceptional inputs. Candidate3 corrects a real inherited threshold-conversion defect. The old implementation widened the mathematical passband by approximately 2.02×10⁻¹⁶ at the lower amplitude edge and 4.91×10⁻¹⁷ at the upper edge. The final implementation preserves both outward policy endpoints, so PASS comparisons use inner guards and generic FAIL comparisons use outer guards. It does not change the normative ±0.0001 dB tolerance.

Earlier versions' status columns reproduce their immutable receipt labels. Final admission requires direct comparison of their stored outward bounds with the exact normative limits or replay using candidate3; earlier labels alone are not the final adjudication. The [methods document](P15_high_rate_methods_2026-10-18.md) and [threshold validation](diagnostics/normative_limit_candidate3/THRESHOLD_CORRECTION_VALIDATION.json) explain the distinction.

The [matched data](performance/BENCHMARKS_V1_V2B.json) bind every raw receipt by SHA-256, record the complete per-receipt proof import map, and retain exact source/operator/work identities. The [auxiliary accounting](performance/V1_V2B_AUXILIARY.json) additionally checks uniform proof maps within each version. Complete snapshots are retained under [v1](reference_high_rate_v1_code/IDENTITY.json) and [v2b](reference_high_rate_v2_code/IDENTITY.json). Candidate3's changed continuum module is `2656e0fafac58a6d4cffd19002f6ff22d5a851f4e730afd9ab6e70c684f7f1b5`; its [source identities](diagnostics/normative_limit_candidate3/SOURCE_IDENTITIES.json) specify the change from v2b. Production source and operator identities are matched independently of proof-code identity.

## 2. Execution controls and measurement definitions

The recorded host is an AMD EPYC 9V74 system with Python 3.12.14, mpmath 1.3.0, NumPy 2.3.5, and Linux x86-64. The container exposes CPUs 0–8, an eight-CPU-equivalent cgroup quota, and 8 GiB of memory. The two larger matched rounds used two workers pinned to CPUs 0 and 1, with each pair on the same core. Candidate/baseline order alternates by job position. Every measurement runs in a fresh process; `OPENBLAS_NUM_THREADS=1`. See [ENVIRONMENT.json](execution/ENVIRONMENT.json).

Each job has a 60-second repeated Python signal deadline, maximum 128 proof nodes and 20,000 paths. The external supervisor separately enforces an 85-second process deadline with process-group termination. A signal deadline can be delayed by interpreter/native-code behavior; the external deadline is a distinct enforceable bound. All 100 processes in the completed 24- and 26-pair rounds finished with expected PASS or OPEN exit codes. There were **zero external kills and zero execution failures**. [Supervision records and hashes](performance/SUPERVISION_V1_V2B.json) establish those facts.

The harness resolves imports from the requested source root, records actual imported module paths and SHA-256 values, and checks proof files before and after execution. Paired summaries reject differing work, source bindings, stage snapshots, verified operator bindings, budgets, interpreter/library versions, CPU affinity, or profiling state. Profiled measurements are excluded from matched speed ratios.

“Prover wall” and “prover CPU” cover the certificate calculation. Harness process time additionally includes imports and source/operator binding checks but omits some interpreter startup and final publication work. Supervisor process wall includes the entire launched process. Sums of per-process wall times are resource-accounting measures, not the elapsed makespan of the two-worker dispatcher. Peak RSS is the maximum observed **single-process** resident set, not concurrent aggregate memory.

Other campaigns used other assigned cores. Shared caches, memory bandwidth, and cgroup scheduling can still affect timings. Each round has one observation per variant per interval; no statistical confidence interval or robust latency guarantee is inferred. OPEN times are censored: the report does not divide a timeout by a candidate runtime and call that a measured speedup.

## 3. Matched results by version

| Metric | Third pass, 24 pairs | High-rate v1, 24 pairs | Third pass, 26 pairs | Candidate2 v2b, 26 pairs |
|---|---:|---:|---:|---:|
| PASS / OPEN | 22 / 2 | 22 / 2 | 22 / 4 | 26 / 0 |
| Prover wall sum, seconds | 471.060 | 376.542 | 582.325 | 384.376 |
| Prover CPU sum, seconds | 465.940 | 374.104 | 579.222 | 382.328 |
| Harness process wall sum, seconds | 516.530 | 422.176 | 628.983 | 430.131 |
| Supervisor process wall sum, seconds | 520.969 | 426.464 | 633.707 | 434.631 |
| Maximum single-process RSS, KiB | 217,308 | 217,452 | 217,284 | 209,420 |
| PASS per prover CPU-hour, all jobs included | 169.98 | 211.71 | 136.74 | 244.82 |
| PASS per supervised process-wall hour | 152.02 | 185.71 | 124.98 | 215.36 |

The 24-pair corpus contains 20 intervals at 384 kHz, two at 192 kHz, and two at 44.1 kHz; it includes 7 DSD64, 6 DSD128, and 11 DSD256 intervals. V1 preserves all 22 baseline passes and improves their wall-time ratio of sums by **1.368×**, with a per-job median ratio of **1.481×**. Its two OPEN intervals remain DSD64 mastering 19–20 kHz and DSD64 mastering_v2 24–25 kHz, both targeting 384 kHz. Both versions exhaust their 60-second budgets there.

The 26-pair corpus adds DSD256 mastering 39–40 kHz and mastering_v2 65–66 kHz at 192 kHz output. V2b certifies both added cases and both difficult DSD64 cases. It retains all 22 baseline passes. On common passes, the median per-job wall ratio is **1.617×**; the ratio of wall sums is **1.562×**. Across all 26 jobs, including baseline timeout cost, the ratio of prover wall sums is **1.515×**, while actual certificate yield per prover CPU-hour rises **1.790×**. The different ratios answer different questions and are not interchangeable.

### Complete 26-pair measured corpus

Times are prover wall seconds, rounded only for display. `OPEN` means the raw receipt reports time-budget exhaustion. “PB” is the normative passband; “SS” is the native-source stopband obligation, displayed by its canonical output-frequency interval. Frequencies and PCM rates in this table are kHz. Full precision, bounds, counters, source/operator bindings and receipt hashes are in [BENCHMARKS_V1_V2B.json](performance/BENCHMARKS_V1_V2B.json).

| Canonical index | DSD / profile | PCM | Region, kHz | Third pass | V2b |
|---:|---|---:|---|---:|---:|
| 0 | 64 mastering | 44.1 | PB 0–1 | 0.858 PASS | 0.853 PASS |
| 596 | 64 mastering | 384 | PB 19–20 | 60.008 OPEN | 59.653 PASS |
| 788 | 64 mastering | 384 | SS 191–192 | 16.741 PASS | 15.126 PASS |
| 1842 | 64 wideband | 384 | PB 35–35.28 | 43.033 PASS | 19.555 PASS |
| 2034 | 64 wideband | 384 | SS 191–192 | 16.982 PASS | 16.148 PASS |
| 3030 | 128 mastering | 384 | PB 29–30 | 16.453 PASS | 9.297 PASS |
| 3222 | 128 mastering | 384 | SS 191–192 | 16.539 PASS | 10.028 PASS |
| 4363 | 128 wideband | 384 | PB 70–70.56 | 16.366 PASS | 9.322 PASS |
| 4555 | 128 wideband | 384 | SS 191–192 | 14.932 PASS | 10.206 PASS |
| 4980 | 256 mastering | 44.1 | PB 0–1 | 9.794 PASS | 2.603 PASS |
| 5283 | 256 mastering | 192 | PB 39–40 | 60.031 OPEN | 27.268 PASS |
| 5597 | 256 mastering | 384 | PB 0–1 | 16.192 PASS | 9.512 PASS |
| 5636 | 256 mastering | 384 | PB 39–40 | 15.133 PASS | 10.563 PASS |
| 5717 | 256 mastering | 384 | SS 80–81 | 16.711 PASS | 10.048 PASS |
| 5828 | 256 mastering | 384 | SS 191–192 | 16.431 PASS | 9.824 PASS |
| 6758 | 256 wideband | 192 | PB 91–91.2 | 9.503 PASS | 7.587 PASS |
| 6854 | 256 wideband | 192 | SS 95–96 | 10.479 PASS | 9.304 PASS |
| 6996 | 256 wideband | 384 | PB 141–141.12 | 7.982 PASS | 6.191 PASS |
| 7188 | 256 wideband | 384 | SS 191–192 | 8.595 PASS | 5.427 PASS |
| 8309 | 64 mastering_v2 | 384 | PB 24–25 | 60.022 OPEN | 48.887 PASS |
| 8501 | 64 mastering_v2 | 384 | SS 191–192 | 19.066 PASS | 15.440 PASS |
| 9568 | 128 mastering_v2 | 384 | PB 47–48 | 16.566 PASS | 10.486 PASS |
| 9760 | 128 mastering_v2 | 384 | SS 191–192 | 17.594 PASS | 9.638 PASS |
| 10499 | 256 mastering_v2 | 192 | PB 65–66 | 60.020 OPEN | 29.481 PASS |
| 10904 | 256 mastering_v2 | 384 | PB 65–66 | 17.473 PASS | 10.595 PASS |
| 11096 | 256 mastering_v2 | 384 | SS 191–192 | 18.819 PASS | 11.333 PASS |

V1 has two measured common-pass slowdowns: index 4980 rises from 11.187 to 12.299 seconds (**9.94% slower**) and index 8501 from 16.859 to 17.211 seconds (**2.09% slower**). These observations are retained. In the separate v2b round all common passes are faster, including 4980 at 9.794→2.603 seconds. This does not erase the earlier regression or prove every unmeasured cheap interval improves. The 0.858→0.853 second difference on index 0 is too small for a practical speed claim from one pair.

## 4. Fresh final-policy matched round

The independently identified eight-pair candidate3 round is complete. It uses [MATCHED_FINAL_STRICT_PLAN.json](execution/MATCHED_FINAL_STRICT_PLAN.json), the same 60/85-second limits, and CPU 7 while the final campaign runs on CPUs 0–6. All 16 processes finish without external termination or execution failure. The [paired summary](performance/BENCHMARKS_FINAL_STRICT.json) binds every measurement; [additional accounting](performance/FINAL_STRICT_AUXILIARY.json) verifies uniform proof-code identities and includes all supervisor logs and hashes.

| Canonical index | Interval from the preceding table | Third-pass wall seconds | Candidate3 wall seconds |
|---:|---|---:|---:|
| 0 | DSD64 mastering, 44.1 kHz PB 0–1 kHz | 0.910 PASS | 0.885 PASS |
| 596 | DSD64 mastering, 384 kHz PB 19–20 kHz | 60.009 OPEN | 59.087 PASS |
| 4980 | DSD256 mastering, 44.1 kHz PB 0–1 kHz | 11.172 PASS | 2.606 PASS |
| 5283 | DSD256 mastering, 192 kHz PB 39–40 kHz | 60.031 OPEN | 31.360 PASS |
| 5636 | DSD256 mastering, 384 kHz PB 39–40 kHz | 16.884 PASS | 9.377 PASS |
| 5828 | DSD256 mastering, 384 kHz SS 191–192 kHz | 16.425 PASS | 11.093 PASS |
| 8309 | DSD64 mastering_v2, 384 kHz PB 24–25 kHz | 60.016 OPEN | 52.118 PASS |
| 10904 | DSD256 mastering_v2, 384 kHz PB 65–66 kHz | 19.433 PASS | 11.570 PASS |

The baseline yields five passes and three deadline OPENs; final candidate3 yields eight passes. No common pass becomes slower or OPEN in this round. Common-pass wall sums are **64.825→35.532 seconds** (1.824×), with median per-job ratio 1.680×. Those five passes have the same 55 proof nodes, three exact branch splits and 11 exact path enumerations; stage-FIR evaluations decrease **12,618→2,048**, while successful finite-difference uses remain 574.

Including all eight jobs, prover wall sums are **244.882→178.097 seconds**; prover CPU sums are **234.366→171.848 seconds**. Maximum single-process RSS is **217,372→209,336 KiB**. Supervisor process-wall sums are **260.307→193.933 seconds**, with actual certificate yield **69.15→148.50 per supervised process-wall hour**. Including timeout costs, prover-CPU throughput is **76.80→167.59 certificates/hour**, a 2.182× ratio. This small corpus deliberately includes three previously expensive deadline cases, so that throughput ratio must not be compared with the larger corpus's 1.790× ratio as though the policy-serialization correction produced additional acceleration. This round directly establishes the final version's measured behavior.

## 5. Why the gains occur

### Complementary alias populations reduce FIR work

Across the 22 common passes, baseline FIR interval evaluations total **39,060**. V1 reduces them to **25,493** and v2b to **8,973**. In both comparisons the 22 common-pass results use **112 proof nodes, 22 exact branch splits and 66 exact path enumerations**. Candidate ordinary subdivisions total 23; the original baseline did not record this counter, so its value remains unknown rather than being reported as zero. Successful inexpensive finite-difference uses are 3,613 baseline versus 3,511 candidate. A lower use count can mean a stage no longer needed evaluation, rather than a worse majorant.

Across all 26 v2b certificates, the receipts record 992,035 trie nodes, 20,950 frontier expansions, 34,442 insertions, 33,864 subtree-cap uses and 28 terminal-saturation returns. These counters describe actual bound operations. The baseline did not record matching population counters, and deadline OPEN receipts omit their unfinished proof counters; aggregate baseline work on all 26 jobs therefore cannot be reconstructed exactly.

The global halfband proof is additional work, recorded separately from the stage-FIR counter. The actual 57-tap halfband, including 28 exact zero taps, needs a 55-node proof with 28 closed covering intervals. Its certified complementary-pair upper is **1.0000000077254763**, producing a five-stage complete-tail cap of **1.0000000386273817**, compared with the old path-count/L1 value **248.07333464780757**. An isolated cold bound calculation after source load took **0.06267 seconds**. This majorant improvement is not itself a full-prover speed ratio. See [HALFBAND_MAJORANT.json](mathematics/HALFBAND_MAJORANT.json).

### Profile of DSD256 mastering → 384 kHz, 39–40 kHz

The matched unprofiled v1 pair for canonical index 5636 takes **16.499→9.954 seconds**. Separate cProfile runs take 28.389→17.308 seconds and are excluded from speed ratios. Both certify the interval with the same three proof nodes and exact split. Stage-FIR evaluations fall **1,324→346**, while successful finite-difference uses stay at 192.

| Profile quantity | Third pass | V1 |
|---|---:|---:|
| Fixed symmetric Taylor calls | 1,132 | 209 |
| Fixed Taylor cumulative seconds | 24.174 | 12.853 |
| Integer `_mul` calls | 4,939,510 | 2,937,040 |
| Integer `_mul` self seconds | 7.748 | 4.132 |
| `complete_paths` calls | 3 | 3 |
| `complete_paths` cumulative seconds | 2.595 | 3.180 |
| `bound_population` cumulative seconds | 25.245 | 13.502 |

The 209 candidate Taylor calls comprise 154 stage evaluations plus the 55 nodes of the new global halfband proof. The remaining long FIR calculations still dominate arithmetic. Path enumeration retains the same call count; its higher observed profiled time is not evidence of additional algorithmic enumeration. After the FIR reduction it occupies a larger fraction of total time, which is a measured limit to further kernel-only gains. The [profile receipts](profiles/final_v1) retain full function data and proof identities. An earlier launch using unavailable `/usr/bin/time` failed before measurement; its error log is preserved and excluded.

### Terminal saturation addresses a different obstruction

DSD64 mastering → 384 kHz at 19–20 kHz still exhausted the v1 60-second budget. A bounded 180-second diagnostic certified it in **119.958 seconds**, with 39,576 stage-FIR evaluations. At the coarse 19–19.2 kHz segment, one finalized path upper alone was **2.5198099933317692×10⁻⁸**, already exceeding the 10⁻⁸ alias limit. Exhausting the other frontier work could not reduce that immutable upper; narrower 100 Hz children could pass. This is a loose interval bound requiring subdivision, not a witnessed spectral violation or a permanent finite-difference floor.

Terminal saturation returns the still-valid complete upper once the directed sum of finalized upper endpoints reaches the limit. The caller then subdivides. An isolated v2b replay passes in **54.872 seconds**, with only **2,624 stage-FIR evaluations** and four early returns. The v1 and v2b receipts have the same 15 nodes, four ordinary subdivisions, eight proved children, and final alias upper **9.998018426093185×10⁻⁹**. Their final direct/total passband amplitude bounds also agree. All pending aliases remain included; the criterion is never used to assert actual amplitude failure. The [comparison](diagnostics/terminal_saturation_candidate_v2b/JOB596_COMPARISON.json) preserves exact measurements and receipt hashes.

The 26-pair loaded run certifies this same interval in **59.653 seconds**, leaving only about 0.35 seconds before the nominal signal budget. The observed isolated 54.872-second pass and loaded 59.653-second pass demonstrate useful progress, but do not establish a robust 60-second service-level guarantee.

## 6. Reproduction and interpretation

From the repository root, regenerate the completed v1/v2b summary without running numerical jobs:

```sh
python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/summarize_benchmarks.py \
  --runs tests/dsd/results/P15_high_rate_2026-10-18/performance/BENCHMARK_RUNS_V1_V2B.json \
  --output /tmp/P15_BENCHMARKS_V1_V2B_reproduced.json
```

Compare the output byte-for-byte with the retained summary. The summary script refuses incomplete pairs, mismatched controls and profiled measurements. Each supervision `request.json` retains the exact run command and CPU/resource allocation. For a numerical replay, use a new output directory, the supplied baseline source root and the appropriate preserved proof snapshot; never overwrite the historical receipts. The final integrated repository is candidate3, so it must not be labeled v1 or v2b merely because it is replaying an older plan.

Regenerate the final eight-pair summary with the same command using `performance/BENCHMARK_RUNS_FINAL_STRICT.json` as its run specification and a separate temporary output; compare it with `performance/BENCHMARKS_FINAL_STRICT.json`. Both summaries contain the full imported proof maps and individual receipt hashes, rather than a single ambiguous version label.

No matched result is used to infer complete canonical frequency coverage. That question is answered by the independently checked coverage matrix and exhaustive cell verifier. A finite set of performance intervals can expose obstruction and measure throughput; it cannot stand in for the remaining continuous-frequency proof obligations. The arithmetic remains an ideal captured-coefficient operator proof with the interval-library assumptions described in the methods document. P15 release qualification remains a separate determination.
