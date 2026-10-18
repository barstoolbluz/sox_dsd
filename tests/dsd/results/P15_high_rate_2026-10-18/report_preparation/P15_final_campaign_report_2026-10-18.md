# Final high-rate campaign and retry report

**2026-10-18.** The completed final candidate3 campaign returns **905 PASS and 22 OPEN in 927 attempts**. The exact 22 previously OPEN jobs have separate successful same-proof retries, giving **927 distinct certified jobs after 949 total attempts**. The original OPEN receipts remain unchanged. This report records campaign resource yield; baseline-versus-candidate speed comparisons remain in the separately frozen [matched benchmark report](../P15_high_rate_benchmarks_2026-10-18.md).

**Provenance correction.** This report corrects the statement in the preserved [earlier addendum](P15_final_campaign_addendum_2026-10-18.md) that every retry ran on CPU 7. The final nine retries used eight workers on CPUs 0–7, as detailed below. The numerical tables, accounting JSON, receipts, prior validation record and original manifest remain unchanged. The [correction record](FINAL_CAMPAIGN_REPORT_CORRECTION_2026-10-18.json) pins the old and corrected report hashes and independently checks all 949 executions against supervisor requests, commands, receipt resources and measured affinities. This correction concerns the prose description of execution topology, not the measured results.

## Exact scope and identities

This accounting uses these labels from [FINAL_AGGREGATION_CONFIG_02.json](../execution/FINAL_AGGREGATION_CONFIG_02.json) and its [reproduction recipe](../execution/FINAL_AGGREGATION_RECIPE_02.md):

| Configuration label | Recorded attempts | Role here |
|---|---:|---|
| `candidate_final_campaign_60s` | 927 | Complete final main plan, 60-second signal / 85-second external limits |
| `candidate_final_wide256_192000_6000_7000_180s` | 1 | Dedicated retry of canonical index 6673 |
| `candidate_final_retry_180s` | 21 | Exact union of five explicitly preserved retry slice plans |

The retries use 180-second signal / 205-second external limits. All jobs retain maximum 128 proof nodes and 20,000 paths. The main campaign uses seven workers on CPUs 0–6. The dedicated retry and retry slices 01–04 use one worker pinned to CPU 7: respectively 1, 1, 4, 5 and 2 jobs, totaling 13 retries. Retry slice 05 uses eight workers on CPUs 0–7 for the remaining nine jobs. In that final slice, CPU 0 executes indices 6743 and 6755; CPUs 1–7 execute indices 5195, 10363, 6744, 6746, 6749, 6750 and 6752 respectively. Every job runs in a fresh process. The accounting verifies each plan's exact job set and every supervision record. All **949 executions finish without an external kill or execution failure**.

Every receipt matches the same final 15-module proof map and harness SHA-256 `1dbaf498e8127facf0bab4a72916a1bba5f7d3785f8d1babb028e071a68bcd57`. Source bindings agree across all 949 receipts, including all 35 pinned source/evidence files and the normative design digest. The current source, proof and harness files were checked against those hashes. The final [proof snapshot](../reference_high_rate_final_code/IDENTITY.json) includes the halfband subtree majorant, terminal saturation, exact-word cache, and corrected full directed policy intervals. Complete maps, operator identities, per-receipt hashes, counters and supervision hashes are retained in [the accounting JSON](FINAL_CAMPAIGN_ADDENDUM_2026-10-18.json).

The main plan contains 673 intervals at 384 kHz output, 212 at 192 kHz, 15 at 96 kHz and 27 at 44.1 kHz. Its source populations are 858 DSD256, 37 DSD128 and 32 DSD64 jobs. It produces 347 passband and 558 native-source-stop passes on the first attempt; the remaining 22 passband obligations pass on retry. These 927 jobs are one configured subset of the wider evidence union, not the entire 11,516-interval canonical campaign.

## Measured time, memory and useful throughput

| Metric | Main 927 attempts | All 22 retries | Combined 949 attempts |
|---|---:|---:|---:|
| Successful distinct jobs added | 905 | 22 | 927 |
| Recorded OPEN attempts | 22 | 0 | 22 retained historical attempts |
| Prover wall-time sum, seconds | 15,555.036 | 1,393.814 | 16,948.851 |
| Prover CPU-time sum, seconds | 15,253.421 | 1,366.397 | 16,619.818 |
| Harness process-time sum, seconds | 17,141.246 | 1,431.757 | 18,573.003 |
| Supervised process wall-time sum, seconds | 17,315.541 | 1,435.872 | 18,751.413 |
| Maximum single-process RSS, KiB | 209,544 | 142,724 | 209,544 |
| Certificates per prover CPU-hour | 213.59 | 57.96 | **200.80** |
| Certificates per supervised process-wall hour | 188.15 | 55.16 | **177.97** |

Combined throughput includes the cost of all 22 unsuccessful first attempts. It counts each final successful job once: retries are exactly the initial OPEN set and therefore duplicate no earlier PASS. Closing the most expensive residual jobs lowers average throughput while completing the requested plan; both effects are shown. The sum of per-process wall times is not the seven-worker campaign's elapsed makespan. Peak RSS is a single-process maximum, not simultaneous aggregate memory. These are actual resource yields for this selected corpus; no ratio here estimates acceleration over an unmeasured baseline campaign.

## Remaining difficult cases resolved by retry

Twenty retries are DSD256 wideband → 192 kHz passband intervals, retaining 9,408 complete paths. Two are DSD256 → 96 kHz passband intervals with **18,816 complete paths**. All first attempts ended specifically with `interval_wall_clock_budget_exhausted`; no structural precondition or spectral violation was reported.

| Canonical index | Profile / PCM rate | Passband interval, kHz | Successful retry wall time, seconds |
|---:|---|---:|---:|
| 5195 | mastering / 96 kHz | 39–40 | 103.818 |
| 6673 | wideband / 192 kHz | 6–7 | 53.464 |
| 6678 | wideband / 192 kHz | 11–12 | 52.477 |
| 6704 | wideband / 192 kHz | 37–38 | 64.685 |
| 6707 | wideband / 192 kHz | 40–41 | 68.032 |
| 6710 | wideband / 192 kHz | 43–44 | 65.619 |
| 6719 | wideband / 192 kHz | 52–53 | 68.393 |
| 6722 | wideband / 192 kHz | 55–56 | 61.359 |
| 6725 | wideband / 192 kHz | 58–59 | 64.456 |
| 6728 | wideband / 192 kHz | 61–62 | 61.150 |
| 6731 | wideband / 192 kHz | 64–65 | 61.811 |
| 6734 | wideband / 192 kHz | 67–68 | 69.020 |
| 6737 | wideband / 192 kHz | 70–71 | 62.593 |
| 6740 | wideband / 192 kHz | 73–74 | 62.865 |
| 6743 | wideband / 192 kHz | 76–77 | 59.139 |
| 6744 | wideband / 192 kHz | 77–78 | 52.021 |
| 6746 | wideband / 192 kHz | 79–80 | 59.835 |
| 6749 | wideband / 192 kHz | 82–83 | 60.108 |
| 6750 | wideband / 192 kHz | 83–84 | 52.540 |
| 6752 | wideband / 192 kHz | 85–86 | 60.049 |
| 6755 | wideband / 192 kHz | 88–89 | 54.242 |
| 10363 | mastering_v2 / 96 kHz | 23–24 | 76.138 |

The two 96 kHz retries consume 103.312 and 75.726 prover CPU seconds, with peak RSS 142,708 and 142,724 KiB respectively. They use 4,539 and 3,531 FIR evaluations, 15 and 11 proof nodes, and eight and six proved child intervals. Complete alias populations and multiplicity remain accounted for throughout.

Seven retries finish below 60 seconds and fifteen above it. The observed completion times of the 96 kHz cases exceed the original allowance in these runs, but a 180-second allowance is not an established minimum requirement. The [two-pair retry audit](WIDE256_192_RETRY_AUDIT_2026-10-18.md) checks exact source/proof identity and deterministic traversal ordering for indices 6673 and 6678. Original deadline receipts omit partial work counters, and CPU affinity changed; no particular hardware, hash-seed or scheduling cause is established for their timing difference. These retries are separate feasibility observations, not matched speed measurements.

## Recorded numerical work

The 927 successful certificates record:

| Counter | Total |
|---|---:|
| Stage-FIR interval evaluations | 637,671 |
| Successful inexpensive finite-difference majorants | 274,475 |
| Proof nodes examined | 3,941 |
| Proved child intervals | 2,434 |
| Exact branch splits | 892 |
| Ordinary interval subdivisions | 615 |
| Exact complete-path enumerations | 2,711 |
| Trie nodes created | 39,428,206 |
| Frontier expansions | 770,968 |
| Frontier insertions | 1,314,138 |
| Complete-subtree cap uses | 1,299,786 |
| Terminal-saturation returns | 612 |

These counters cover successful calculations only. They omit the unknown interrupted work inside the 22 deadline attempts, whose time and memory costs are nevertheless included above. Stage-FIR counters also exclude the separately proved cached global halfband cover. Counter savings cannot be inferred against the original third pass without matched measurements.

## Relation to final coverage and reproduction

The independently generated [final coverage report](../coverage_final_01/COVERAGE_REPORT.md) combines this campaign with the other explicit config02 labels and applicable earlier receipts. It reports 1,148 distinct current candidate passes, including 1,082 originally OPEN intervals and 1,063 passes beyond the explicitly included earlier evidence. Its four complete cells contain 1,012 canonical intervals, including all three DSD256 → 384 kHz profiles. The larger count includes work outside the 927-job campaign analyzed here. Frequency coverage and exact normative readjudication are established by those independent artifacts, not inferred from resource measurements.

Reproduce this accounting from the repository root without running numerical proofs:

```sh
python3 tests/dsd/results/P15_high_rate_2026-10-18/report_preparation/summarize_final_campaign.py \
  --root . \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --output /tmp/P15_final_campaign_accounting.json
```

Compare that output byte-for-byte with the retained JSON. The utility rejects missing/unexpected jobs, mixed proof identities, source or harness changes, supervision failures, and any retry set that differs from the exact initial OPEN set. P15 remains **BLOCKED**; ideal-coefficient spectral coverage does not discharge FFT4G execution-roundoff or independent release obligations.
