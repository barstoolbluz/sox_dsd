# Configuration02 draft: final same-proof resource retries

**Draft only. Do not publish a final coverage matrix from this configuration yet.** The 927-job main campaign and the final set of retry directories must be settled first. The draft configuration deliberately uses an unsupported draft schema, so `aggregate_final.py` refuses it as an execution configuration.

The original `execution/FINAL_AGGREGATION_CONFIG.json`, `FINAL_AGGREGATION_RECIPE.md`, and `FINAL_AGGREGATION_INPUTS.sha256` remain unchanged.

## Known addition

`FINAL_AGGREGATION_CONFIG_02_DRAFT.json` retains the original ten measurement labels and adds:

| Field | Value |
|---|---|
| Label | `candidate_final_wide256_192000_6000_7000_180s` |
| Canonical job | 6673 |
| Cell / band | DSD256 wideband → 192 kHz / passband |
| Frequency interval | 6,000–7,000 Hz |
| Receipt directory | `diagnostics/wide256_192000_6000_7000_final_180s` |
| Plan | `execution/WIDE256_192000_6000_7000_RETRY_PLAN.json` |
| Proof snapshot | `reference_high_rate_final_code` |
| Numerical resources | 180-second signal budget, 128 nodes, 20,000 paths |
| External process supervision | 205-second termination limit, recorded by the separate runner |

With only this addition, the intended input population becomes **11 labels and 1,429 receipt instances**, still covering **1,148 distinct planned canonical jobs**. These are input counts, not certification dispositions. The original main-campaign 60-second OPEN remains in its original directory and remains included. The larger-budget attempt is a separate receipt and is not a matched timing comparison.

The draft pins the unchanged census, reporting, and aggregation code; the original configuration and its input manifest; the new retry plan; and the original proof snapshot identities. The separate draft manifest binds both the original configuration and the draft's exact bytes.

## Exact promotion steps after the retry set is frozen

1. Start from this draft. Retain every existing label and append one explicitly named measurement for every additional selected retry directory. Record the actual resource budget and exact frozen proof snapshot for each addition. Pin each new plan and any new snapshot identity file. Do not combine distinct directories under a repeated label.
2. Recompute `expected_current_receipt_instances` as the sum of the configured plan sizes and `planned_unique_canonical_jobs` as the union of their canonical indices. The known one-job addition changes only the first count.
3. Change `schema` to `P15/final-high-rate-aggregation/1`. Remove `draft_status` and `promote_schema_to`, and replace draft-specific scope wording with the actual finalized retry scope. Preserve `predecessor_config` and all its hash bindings.
4. Publish the result as the new immutable file `execution/FINAL_AGGREGATION_CONFIG_02.json`. Preserve this preparation draft. The finalized configuration has a new SHA; its hash is not the draft hash.
5. Publish `execution/FINAL_AGGREGATION_RECIPE_02.md` with the explicit commands below and the final exact label/receipt/job counts. Publish `execution/FINAL_AGGREGATION_INPUTS_02.sha256` from the finalized configuration's `pinned_files_sha256`, adding the actual SHA and repository-relative path of the finalized configuration and recipe. That manifest must bind both configurations, not substitute the draft SHA for the final configuration SHA.
6. Ask the independent readjudicator to publish `complete_cell/normative_readjudication_02/verification.json` after all selected retries have completed. This refreshed inventory must include every selected retry PASS by its actual receipt SHA.
7. Run readiness checking and final aggregation with `--config` pointing explicitly to configuration02. Do not alter the frozen report, aggregation, or proof implementation merely to select the new input set.

## Explicit aggregation selection

After promotion, run these from the repository root with the recorded numerical dependencies available:

```sh
sha256sum -c tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_INPUTS_02.sha256
```

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --check-only
```

Once this returns `READY`:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --census-output tests/dsd/results/P15_high_rate_2026-10-18/census_final_01 \
  --report-output tests/dsd/results/P15_high_rate_2026-10-18/coverage_final_01
```

Those output names remain appropriate because no final aggregation has yet been published. If a final output is published before the input set changes again, use a fresh output version rather than replacing it.

## Explicit packaging selection

Add this argument to the final `package_final.py` invocation, retaining its required `--root`, `--original`, and `--output` arguments:

```sh
--aggregation-config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json
```

The packaging implementation passes this exact file to its aggregation preflight and uses it again when checking completed-report measurement identities. Its default remains the original configuration, so the explicit argument is necessary for the retry receipt to be required by both checks. The packaging validation receipt records the selected configuration's actual SHA.

No code change is required in `aggregate_final.py` or the frozen reporting implementation. P15 remains BLOCKED; a larger resource budget changes neither the normative limits nor the independent release obligations.
