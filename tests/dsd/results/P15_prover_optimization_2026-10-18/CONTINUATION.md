# P15 prover optimization — persistent handoff checkpoint (2026-10-18)

## Identity, immutable evidence and current disposition

**Submitted baseline:** `sox_ng-P15-prover-optimization-76282bdc.tar.gz`, SHA-256 `82c6e31d24b37b18ff5c60bb18f7c1dd266988da6cace9687005c2c6384365c2`, repository root `sox_ng/`.

**Delivered change:** retained the original finite, source-bound rational branch enumeration and the fail-closed operator identity checks. The only original files changed are `tests/dsd/p15_src_interval_recurrence.py`, `p15_src_stagewise_continuum.py` and `p15_src_stagewise_alias_proof.py`. Ten new numerical, test, profiling and evidence-support Python scripts reside in `tests/dsd/`, plus this new evidence directory. **No production SRC/DSD sources or pinned source dependencies were changed.** Existing rebound operator receipts therefore have the same source binding. `SOURCE_INTEGRITY.json` verifies **16,711** original source and historical evidence files byte-for-byte against the submitted source tarball, including 11,516 complete-campaign receipts, 5,112 partial receipts, 48 extended-budget samples and 35 pinned source files. Do not overwrite those.

**Proof engine:** `p15_src_fixed_interval.py` now uses 288-bit dyadic-directed integer arithmetic, exactly even source binary64 coefficient parity, signed cosine derivatives, and a global exact-coefficient moment/Taylor remainder, with 75-digit directed mpmath trig anchors. `p15_src_symmetric_interval.py` supplies an independently implemented real interval evaluator; the original general complex reference remains callable. Verified exact symmetry in all 499 captured FIR-stage occurrences (all 72 cells, 24 operator pairs). Added identity-aware immutable stage caching and safe reuse of exact-rational stationary-path schedules across dyadic subintervals (with fresh paths at branch transitions). `MATHEMATICAL_METHODS.md` explains all enclosure obligations and trusted dependencies, including what was not formally proved independently.

**Evidence:** `CORPUS.json` (104 reproducible cases), paired 43-case baseline/optimized 4s JSONL, paired 25-case baseline/optimized 2s JSONL, one same-host baseline 60s, seven optimized 60s (6 local PASS, 1 OPEN), warm 57/153/720/1005/1845/4160-tap microbenchmarks (~6–9x), cProfile data, independent correctness tests and independent SHA audit. See `RESULTS_SUMMARY.json`, `PERFORMANCE_AND_CERTIFICATION.md`. The canonical dispatcher separately published a new source-bound, locally proved, immutable `PASS-LOCAL-BAND` receipt for index **3001** (DSD128 mastering → 384k, 0–1000 Hz). Repetition skipped it and preserved its SHA. New dispatcher aggregate status is still OPEN; 11,515 receipts are missing from that **new** output directory. Optimized full 11,516 campaign has **not** run.

**Release and unproved obligations:** **P15 BLOCKED**. The original campaign contains 6,835 local PASS + 4,681 OPEN, comprising 3,907 timed-out and 774 structural alias/operator precondition failures. The unique primitive-native-family ambiguity (factorized `176400→192000→96000`) remains explicitly unproved, not a numerical timeout. No complete re-run, independent arbitrary-input FFT4G execution-roundoff proof or DSD256 P/S-matched comparator closure; no v2 default promotion, P16, or v2 authorization. Remaining `OPEN` is not `FAIL` without a rigorously established witness.

## Rebuild/replay from the delivered complete source root

The paths below assume a POSIX terminal and `cd sox_ng` first; a Python installation with the baseline project's supported `mpmath` and other existing test dependencies is required. On the numerical benchmark host, use `OPENBLAS_NUM_THREADS=1` to reduce thread noise.

```sh
export PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1
python -m unittest test_p15_src_continuum_bounds test_p15_src_complete_aliases test_p15_campaign_dispatch_corrective test_p15_prover_fixed_interval -q
python -m unittest test_p15_campaign_corrective_synthetic test_p15_src_bound_operator test_p15_remaining_math -q
python tests/dsd/p15_prover_stage_parity_audit.py
python tests/dsd/p15_prover_fir_microbenchmark.py
python tests/dsd/p15_prover_cost_profile.py
python tests/dsd/p15_prover_evidence_integrity.py --help  # check options before expensive tar rehash
python tests/dsd/p15_prover_summarize.py
python tests/dsd/results/P15_prover_optimization_2026-10-18/generate_source_patch.py
```

The recorded benchmark outputs are **append-only** and skip matching, completed canonical jobs; a deliberate new numerical comparison should use new filenames/output directories (instead of modifying evidentiary JSONL). Raw benchmark lines include source and stage-code digest, detailed dispositions, elapsed time and cumulative peak process RSS. The scripts `run_corpus_short.sh` and `run_60s_subset.sh` in this directory are executable replays which skip existing job lines. To remeasure rather than skip, copy scripts and change their outputs to new named files; do not erase retained results. Each call to `p15_prover_benchmark.py` has `--variant baseline|optimized --seconds N --first INDEX --limit COUNT --output FILE`.

**The bounded full-campaign path already exists in the baseline; do not replace it:**

```sh
# Create a NEW output folder. Do not copy historical OPEN receipts: the dispatcher
# deliberately preserves them and would not recompute under a new budget.
mkdir -p tests/dsd/results/P15_prover_optimization_2026-10-18/new_full_60s_receipts
export PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1
# Repeat this same command with --start 0, 206, 412, ... , 11330.
# Each 206-job shard is deterministic; 56 shards cover 11,516 jobs in total.
# A return code 2 means aggregate OPEN (expected before full closure), not lost receipts.
python tests/dsd/p15_full_band_campaign.py \
  --output tests/dsd/results/P15_prover_optimization_2026-10-18/new_full_60s_receipts \
  --start 0 --limit 206 --interval-seconds 60
# For a restart, rerun exactly the same shard: existing bound receipts are checked
# and skipped byte-for-byte. The dispatcher uses exclusive atomic publication.
# At any point: 
python tests/dsd/p15_full_band_campaign.py \
  --output tests/dsd/results/P15_prover_optimization_2026-10-18/new_full_60s_receipts \
  --summary-only
```

**Important:** A previously published OPEN in a new campaign directory remains immutable on resume. To retry OPEN at higher budget, start an entirely new receipt directory for those jobs; never overwrite old evidence. The proven 60-second local index 3001 may be independently replayed in a fresh new proof-output directory with `--start 3001 --limit 1 --interval-seconds 60`; `optimized_dispatch_receipts` already has that bound receipt and replays will skip it. Do not mark whole-source completion on its basis.

This handoff contains executable numerical implementation, unit tests, reproducible benchmark selection and cost measurement, source patch, math methods, before/after evidence, live continuation details and manifests; no further prompt is needed just to reproduce its proven results.
