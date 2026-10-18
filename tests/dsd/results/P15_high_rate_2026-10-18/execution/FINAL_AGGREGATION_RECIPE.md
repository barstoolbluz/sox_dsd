# Final high-rate coverage aggregation

This recipe specifies the final evidence inputs. It does not run a numerical campaign and it is not a final coverage report. Run it after the configured campaigns and strict scalar readjudication have completed.

## Exact input set

`FINAL_AGGREGATION_CONFIG.json` binds ten measurement directories, four complete frozen proof-code snapshots, all applicable job plans, and the census/report/aggregation implementations. The configuration declares **1,428 current receipt instances representing 1,148 distinct canonical jobs**. These are expected input populations, not PASS counts.

| Measurement label | Role | Receipts | Budget | Proof snapshot |
|---|---|---:|---:|---|
| `candidate_v1_campaign_60s` | First high-rate campaign | 383 | 60 s | `reference_high_rate_v1_code` |
| `baseline_matched_v1_60s` | Matched baseline | 24 | 60 s | `reference_third_pass_code` |
| `candidate_v1_matched_60s` | Matched first candidate | 24 | 60 s | `reference_high_rate_v1_code` |
| `candidate_v1_diagnostic_180s` | Larger-budget edge diagnostic | 1 | 180 s | `reference_high_rate_v1_code` |
| `candidate_v2b_diagnostic_60s` | Terminal-saturation edge diagnostic | 1 | 60 s | `reference_high_rate_v2_code` |
| `baseline_matched_v2b_60s` | Matched baseline | 26 | 60 s | `reference_third_pass_code` |
| `candidate_v2b_matched_60s` | Matched second candidate | 26 | 60 s | `reference_high_rate_v2_code` |
| `candidate_final_campaign_60s` | Final strict-threshold campaign | 927 | 60 s | `reference_high_rate_final_code` |
| `baseline_matched_final_60s` | Final matched baseline | 8 | 60 s | `reference_third_pass_code` |
| `candidate_final_matched_60s` | Final matched candidate | 8 | 60 s | `reference_high_rate_final_code` |

Each receipt has a 128-node and 20,000-path resource allocation. CPU assignment is retained in the receipt; paired performance checks require equal CPU affinity and execution environment. Profiling is disabled for every configured measurement. Archived exploratory and profiling results remain separate from these selected coverage and matched-performance inputs.

The proof version names are independent of the `mastering_v2` decode profile. The final candidate exactly serializes the **full directed threshold intervals**: PASS uses inward endpoints, and generic FAIL uses outward endpoints. Its stored bound endpoints remain exact. Production coefficients, normative bands, and release policy are unchanged.

## Required order

1. Complete `CAMPAIGN_FINAL_STRICT_PLAN.json` and `MATCHED_FINAL_STRICT_PLAN.json`, retaining every receipt and any OPEN result.
2. Have the independent readjudicator publish `complete_cell/normative_readjudication_02/verification.json` after those directories are frozen. Its inventory must include all original, prior, and configured current PASS receipts.
3. Run the readiness check below. It verifies expected job populations, resource limits, proof-code maps, configured file hashes, and strict readjudication of current PASS receipts before creating output directories.
4. Run aggregation into the fresh directories below. The report independently validates all original/prior/current PASS contributors, their exact receipt hashes, source/operator identities, canonical intervals, matched environments, and exact boundary neighborhoods.

The census automatically includes the immutable original campaign, the historical 600-second sample, and four final third-pass local receipts under separate labels. It never relabels their historical dispositions. Every PASS used in the final union must pass exact normative scalar readjudication; that readjudication is explicitly separate from numerical proof replay.

## Commands

Run from the extracted repository root with the recorded Python environment and its `mpmath` and `numpy` dependencies available. For this workspace, prepend `/workspace/scratch/47ef0cb747fa/deps` to `PYTHONPATH` if those dependencies are not installed in the selected interpreter.

Check all configured static inputs:

```sh
sha256sum -c tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_INPUTS.sha256
```

Check readiness without publishing a census or report:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --check-only
```

An incomplete configured plan returns exit status 2 and `WAITING_FOR_CONFIGURED_RECEIPTS`, including missing canonical indices. A changed configured input, mixed proof version, stale readjudication inventory, or conflicting identity fails closed. Neither condition publishes a coverage claim.

Generate the final census and report once the check returns `READY`:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --census-output tests/dsd/results/P15_high_rate_2026-10-18/census_final_01 \
  --report-output tests/dsd/results/P15_high_rate_2026-10-18/coverage_final_01
```

Publication is immutable and idempotent. An exact replay may reuse an output directory. Any changed input set, code, or readjudication snapshot requires a new configuration/output version; preserve the earlier evidence.

## Generated final artifacts

- `COVERAGE_REPORT.md`: all nine 384-kHz cells and the three DSD256→192-kHz profiles; historical/current/prior unions; exact complete-cell flags; performance regressions and limits.
- `CELL_COVERAGE.json` and `CLASSIFICATION.jsonl`: every canonical interval's measured or unmeasured state. Timeouts alone are never assigned a mathematical cause or treated as a violation.
- `COMPLETE_CELL_WITNESSES.json`: every required canonical job and its valid source-bound receipt hash for each claimed complete cell, with exact gap-free endpoints.
- `BOUNDARY_COVERAGE.json`: separate planned and actual-PASS coverage of DC, near-zero neighborhoods, normative upper edges, routing transitions, native-Nyquist alias relabelings, and native-stop membership crossings; point/left/right coverage is explicit.
- `MATCHED_BENCHMARKS.json`: baseline/candidate timings, memory, numerical counters, outcomes, exact identities, and PASS/PASS speedups. Censored timeouts are excluded from speedup ratios.
- `STRICT_NORMATIVE_READJUDICATION.json`: exact receipt hashes contributing to the unions and their manifested strict scalar verification source.
- `SUMMARY.json` and `SHA256SUMS`: accounting totals, source/proof identities, and immutable artifact hashes.

P15 remains **BLOCKED**. Exhaustive ideal-coefficient local spectral coverage does not discharge FFT4G execution-roundoff, physical qualification/adjudication, or other independent release obligations.
