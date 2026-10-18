# P15 third pass — executable continuation checkpoint

**Checkpoint:** 2026-10-18. **Release:** BLOCKED. **Working source:** `sox_ng/` in full archive. **Parent:** complete second-pass full source archive of 2026-10-18. Work does not require any previous session state.

## Completed and retained

1. Kept the entire second-pass rigorous Taylor/collision-path implementation as the baseline. The first adaptive-order experiment proved little value and was excluded from delivered code.
2. Added `tests/dsd/p15_src_difference_upper.py`, an exact-binary64, zero-padded full-support finite-difference L1 bound valid over continuous source-frequency intervals.
3. Integrated that upper ONLY into the existing stagewise alias upper evaluation in `p15_src_stagewise_continuum.py`; the direct wanted lower and all historical acceptance policy remain unchanged. A stage with a weak difference bound uses the original Taylor evaluator.
4. Added adversarial independent correctness tests and a reproducible FIR arithmetic benchmark; repaired a flaky test of the existing repeated deadline (test only, no campaign executor code change).
5. Independently measured second-pass versus final third-pass local continuum proofs, produced four final source-bound receipts and code source hashes, and verified 16,711 unchanged original locked sources/receipts.
6. Verified one final source-bound receipt can be replayed byte-identically; final raw measurements and original statuses appear in `RESULTS_SUMMARY.json`.
7. Kept transient experiment results and one invalid baseline run separate, labeled and excluded from final results.

## Regenerate evidence and tests

All commands from the root of `sox_ng/`. Requires Python, mpmath and the NumPy operator dependencies already used by the second pass. `OPENBLAS_NUM_THREADS=1` gives comparable CPU measurements.

```sh
export PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1
python -m unittest test_p15_prover_third_pass -q
python -m unittest test_p15_prover_second_pass -q
python -m unittest test_p15_prover_fixed_interval -q
python -m unittest test_p15_campaign_corrective_synthetic -q
python -m unittest test_p15_src_complete_aliases -q
python -m unittest test_p15_campaign_dispatch_corrective -q
python -m unittest test_p15_src_bound_operator -q
python -m unittest test_p15_src_continuum_bounds -q
python -m unittest test_p15_remaining_math -q
python tests/dsd/p15_third_pass_fir_benchmark.py
```

The benchmark below uses each **frozen** prover implementation, independent fresh processes, immutable receipt filenames bound to code hashes, source hashes and arguments. The second-pass modules are included under `results/P15_prover_third_pass_2026-10-18/second_pass_code/`. Explicit module-path assertions prevent accidentally comparing the same code against itself.

```sh
python tests/dsd/p15_third_pass_benchmark.py --variant second_pass --profile master128 --input-hz 176400 --output-hz 384000 --lo 0 --hi 1000 --seconds 40
python tests/dsd/p15_third_pass_benchmark.py --variant third_pass  --profile master128 --input-hz 176400 --output-hz 384000 --lo 0 --hi 1000 --seconds 40
python tests/dsd/p15_third_pass_benchmark.py --variant second_pass --profile master128 --input-hz 176400 --output-hz 384000 --lo 150000 --hi 151000 --mode stop --seconds 20
python tests/dsd/p15_third_pass_benchmark.py --variant third_pass  --profile master128 --input-hz 176400 --output-hz 384000 --lo 150000 --hi 151000 --mode stop --seconds 20
```

Matching immutable receipts will print `SKIP`; use a new **fresh directory and explicit --directory argument** for new timings instead of deleting/overwriting recorded data.

## Resume canonical certification without overwriting history

The 11,516-interval canonical campaign is still incomplete under this optimized code. Create an entirely new independent receipt directory (never use the historical complete, partial, second-pass, or four final local certificate directories):

```sh
mkdir -p tests/dsd/results/P15_prover_third_pass_new_full_60s
python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_prover_third_pass_new_full_60s --start 0 --limit 206 --max-paths 20000 --max-nodes 128 --interval-seconds 60
python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_prover_third_pass_new_full_60s --summary-only
```

Repeat offsets 206, 412, 618, etc. through 11330. A driver exit status 2 with an aggregate `OPEN` is expected until every interval is proven; the per-job receipt is still published exclusively. Previously published `OPEN` receipts are immutable and will not be re-proved by increasing a budget in the same folder: create a separate fresh budget-specific directory. For strict external wall-clock process termination, supervise the CLI with an OS process limit; inherited Python SIGALRM cannot force an uninterruptible native call to stop.

## Remaining mathematical and engineering obligations

- Source-bound all 11,516 canonical intervals with exact rational alias stationary splits; independently reverify any coverage candidate. The 43 historical routing stalls are in the existing `CORPUS.json`; neither a selected fast PASS nor a finite routing split proves whole-band coverage.
- Investigate unresolved alias lower/upper tightness **only where empirical evidence shows proof looseness**. Do not invent phase cancellation; a phase-aware coherent bound would require exact verified relative stage phase origins and independent testing.
- Independently establish arbitrary-input FFT4G execution roundoff and all other release preconditions, including the matched DSD256 physical comparison.
- Do not change production SRC, source coefficient filters, source-locked modules, acceptance policy, v2 defaults or P16 authorization.

The original complete campaign remains **6,835 local PASS and 4,681 OPEN**. This third pass adds four verified individual local certificates but does not update that old campaign's aggregate. The old results remain historical artifacts, not silently relabeled.
