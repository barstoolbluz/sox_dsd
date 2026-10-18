# Final high-rate aggregation: configuration 02

Configuration 02 fixes the complete reporting input population at **12 measurement labels, 1,450 receipt instances, and 1,148 distinct canonical jobs**. These are input counts; certification dispositions come from the immutable receipts and their exact normative readjudication. No numerical proof runs during aggregation.

The original configuration, recipe, input manifest, and configuration 02 preparation drafts remain unchanged. The new input manifest binds both published configurations, the preserved draft lineage, the frozen reporting implementation, all required plan files, and the four proof snapshot identities.

## Selected input populations

| Measurement label | Required receipts | Proof implementation | Numerical budget |
|---|---:|---|---:|
| `candidate_v1_campaign_60s` | 383 | First high-rate candidate | 60 s |
| `baseline_matched_v1_60s` | 24 | Third-pass baseline | 60 s |
| `candidate_v1_matched_60s` | 24 | First high-rate candidate | 60 s |
| `candidate_v1_diagnostic_180s` | 1 | First high-rate candidate | 180 s |
| `candidate_v2b_diagnostic_60s` | 1 | Second high-rate candidate | 60 s |
| `baseline_matched_v2b_60s` | 26 | Third-pass baseline | 60 s |
| `candidate_v2b_matched_60s` | 26 | Second high-rate candidate | 60 s |
| `candidate_final_campaign_60s` | 927 | Final corrected candidate | 60 s |
| `baseline_matched_final_60s` | 8 | Third-pass baseline | 60 s |
| `candidate_final_matched_60s` | 8 | Final corrected candidate | 60 s |
| `candidate_final_wide256_192000_6000_7000_180s` | 1 | Final corrected candidate | 180 s |
| `candidate_final_retry_180s` | 21 | Final corrected candidate | 180 s |

Every measurement uses 128 maximum proof nodes and 20,000 maximum paths, without profiling. Proof implementation versions are independent of the decode profile named `mastering_v2`. The final corrected implementation serializes the full directed threshold intervals exactly: PASS uses inward endpoints, and generic FAIL uses outward endpoints.

The 22 final retries preserve the original 60-second OPEN receipts. Canonical job 6673 has its dedicated diagnostic directory and one-job plan. The remaining 21 jobs use `campaign_final_retry_180s` and the exact union in `execution/FINAL_RETRY_180S_PLAN.json`; that union lists five preserved, disjoint slice plans. All 22 jobs were already in the 927-job main plan, so retries increase receipt instances without enlarging the canonical job set. Their numerical signal budget is 180 seconds, and external supervision uses a separately recorded 205-second process termination limit.

A PASS from a larger-budget replay is feasibility evidence under that recorded attempt. It does not establish that more than 60 seconds was necessary. In particular, the successful dedicated job 6673 replay finished in 53.463893 seconds despite its earlier 60-second OPEN. Retry outcomes are not mixed into the matched timing comparisons.

## Readiness and independent admission

Run from the extracted repository root with the recorded Python dependencies available. The commands assume `mpmath` and the other repository dependencies are installed; this execution environment additionally used `/workspace/scratch/47ef0cb747fa/deps` in `PYTHONPATH`.

```sh
sha256sum -c tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_INPUTS_02.sha256
```

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --check-only
```

The check rejects changed pinned files, mixed proof snapshots, mismatched resource budgets, duplicate or unexpected canonical jobs, and incomplete configured plans. It returns `WAITING_FOR_CONFIGURED_RECEIPTS` until every configured receipt is present. Once the input populations are complete, it requires the refreshed independent exact-normative readjudication to admit every contributing current PASS by exact path and SHA. Publication also checks all contributing original and prior PASS receipts. A stale or absent readjudication cannot authorize final publication.

The readjudication checks the retained scalar enclosures against the exact normative inequalities; it is separate from numerical proof replay. The immutable proof receipts, complete imported-module snapshots, and source/operator identities remain the basis for replaying the interval calculations. The original 6,835 PASS count, the historical 600-second sample, and four third-pass local receipts remain distinct prior evidence populations.

## Publish fresh final outputs

Only after readiness returns `READY` and the independent readjudication inventory has frozen, run:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --census-output tests/dsd/results/P15_high_rate_2026-10-18/census_final_01 \
  --report-output tests/dsd/results/P15_high_rate_2026-10-18/coverage_final_01
```

These names are new output directories. Preserve them after publication. Changed inputs require fresh versioned output directories and an appropriately refreshed readjudication inventory.

The report distinguishes candidate PASS unions across recognized proof versions, newly certified originally OPEN jobs, progress beyond all explicitly included prior evidence, observed candidate OPEN without any later PASS, and jobs with no candidate measurement. Complete cells require exhaustive canonical interval witnesses, including exact interval endpoints, receipt hashes, and source/operator bindings. Sampled throughput does not establish complete-cell frequency coverage.

## Select the same configuration for packaging

Add the following argument to the final `execution/package_final.py` invocation, retaining its required `--root`, `--original`, and `--output` arguments:

```sh
--aggregation-config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json
```

This explicit selection is necessary: the default remains configuration 01. Packaging passes the selected file to its aggregation preflight and uses it again to check the completed report's measurement identities. Its validation receipt records the selected configuration's actual SHA.

No frozen proof, harness, census, reporting, or aggregation implementation changes are needed to select configuration 02. P15 remains BLOCKED pending its independent release obligations.
