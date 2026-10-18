# P15 second-pass persistent continuation and independent replay

**Checkpoint:** 2026-10-18. **P15 release:** BLOCKED.

## Current source base

The full bundle includes the complete source-bound SoX-NG test tree and the immutable original P15 campaign. Parent source is `sox_ng_P15_prover_optimized_FULL_SOURCE_2026-10-18.tar.gz`, SHA in `RESULTS_SUMMARY.json`. This pass modifies only four non-pinned numerical/campaign Python modules:

- `tests/dsd/p15_src_fixed_interval.py` -- cached exact derivative weights.
- `tests/dsd/p15_src_stagewise_continuum.py` -- complete primitive lattice coverage with duplicate reverse paths; maximum path budget 20,000; exclusive local-receipt publication.
- `tests/dsd/p15_src_stagewise_alias_proof.py` -- independent point diagnostic does not reject duplicate reverse paths.
- `tests/dsd/p15_full_band_campaign.py` -- max-path 20,000 and repeated soft deadline after expiry.

New tests and benchmark scripts: `test_p15_prover_second_pass.py`, `p15_second_pass_benchmark.py`, `p15_second_pass_fir_benchmark.py`. The original exact bound reference remains intact. All 35 pinned source paths are unchanged, so existing source-bound operator receipts remain valid.

## Unfinished goals and exact dispositions

1. **Done:** complete exact rational stage path enumeration for the three previously structurally refused factorized source-bound examples, with all native-frequency families covered. Counts: 9,408 paths / 4,704 unique native families (DSD64 -> 48k, DSD128 -> 96k); 18,816 paths / 9,408 unique (DSD256 -> 96k). Precisely one marked direct path in each.
2. **Done:** ideal-coefficient continuous-local PASS on all three 0-1 Hz passband intervals, each with bound receipt in `new_certificates/`; these are neither whole band nor release PASS.
3. **Done:** exact derivative weight caching, 6-size warm FIR performance replay (1.50x-1.73x), plus a full matched 40-second-budget baseline/revised case (36.37 vs 25.16 s, 835 evaluations and PASS each). A separate early DSD256 3-second run was OPEN and a later 20-second run PASS; both raw receipts retained.
4. **Done:** 65 test executions across eight test modules, 62 passed and 3 prior expected skips; a byte-for-byte audit of 16,711 original pinned source/historical campaign/budget sample files.
5. **Not done:** the second-pass 11,516-interval whole campaign; full closure of prior OPEN intervals; arbitrary-input FFT4G execution-roundoff proof; independent DSD256 P/S-matched physical comparison; final release approval. No production DSP or coefficients changed.
6. **Known limitation:** periodic SIGALRM is not a hard kill for a native call that never returns control to Python. Run the CLI through an external process supervisor for physical wall enforcement; an interrupted job can be retried in its exclusive receipt directory. A successful, completed OPEN receipt is immutable and requires a new output directory to re-prove with new limits.

## Reproduce independent tests and numerical outcomes

From full-source `sox_ng/` root (with Python, mpmath and NumPy from the first pass):

```sh
export PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1
python -m unittest test_p15_prover_second_pass -q
python -m unittest test_p15_prover_fixed_interval -q
python -m unittest test_p15_campaign_corrective_synthetic -q
python -m unittest test_p15_src_complete_aliases -q
python -m unittest test_p15_campaign_dispatch_corrective -q
python -m unittest test_p15_src_bound_operator -q
python -m unittest test_p15_src_continuum_bounds -q
python -m unittest test_p15_remaining_math -q
python tests/dsd/p15_second_pass_fir_benchmark.py --variant first_pass
python tests/dsd/p15_second_pass_fir_benchmark.py --variant second_pass
```

The following repeat existing *immutable* benchmark identities and skip if an identical result is present. To take fresh timings with the same code and a new runtime key, change the seconds/max-nodes options; do NOT delete historical benchmark evidence.

```sh
python tests/dsd/p15_second_pass_benchmark.py --variant first_pass --profile master128 --input-hz 176400 --output-hz 384000 --lo 0 --hi 1000 --seconds 40
python tests/dsd/p15_second_pass_benchmark.py --variant second_pass --profile master128 --input-hz 176400 --output-hz 384000 --lo 0 --hi 1000 --seconds 40
python tests/dsd/p15_second_pass_benchmark.py --variant second_pass --profile master256 --input-hz 176400 --output-hz 96000 --lo 0 --hi 1 --seconds 20
```

To reproduce one bound local result into a FRESH directory, run:

```sh
mkdir -p tests/dsd/results/P15_prover_second_pass_2026-10-18/replay_local
python tests/dsd/p15_src_stagewise_continuum.py --profile master64 --snapshot tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/88200-48000/stage-snapshot.json --lo 0 --hi 1 --max-nodes 128 --output tests/dsd/results/P15_prover_second_pass_2026-10-18/replay_local/master64-88200-48000-pass-0-1.json
```

For the 11,516 canonical campaign, create an entirely **new** directory and use the existing bounded dispatcher; do not overwrite or import OPEN receipts that you intend to retry. A zero `--start` shard with `--limit 206` and repeated shards at offsets 206, 412, ... 11330 covers the source-bound worklist; the same shard is resumable, files are published exclusively.

```sh
mkdir -p tests/dsd/results/P15_prover_second_pass_2026-10-18/next_full_60s_receipts
python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_prover_second_pass_2026-10-18/next_full_60s_receipts --start 0 --limit 206 --max-paths 20000 --interval-seconds 60
python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_prover_second_pass_2026-10-18/next_full_60s_receipts --summary-only
```

Dispatcher returns code 2 for aggregate OPEN even when the selected shard was executed and receipts were written. Periodic signal re-delivery is not a process-kill guarantee; externally supervise the command on machines requiring a strict kill policy. Keep any resumable campaign receipts separate from archived receipts and from new 0-1 Hz local evidence.

## Integrity and handoff

- The source patch is `SOURCE_CHANGES.patch` in this evidence directory and separately delivered outside the full archive.
- Raw first-pass numerical code copies, protected by `FIRST_PASS_CODE_SHA256SUMS`, are in `first_pass_code/`.
- `RESULTS_SUMMARY.json`, `FIR_WARM_*.json` and `benchmarks/*.json` are measured evidence, not extrapolated estimates.
- `SOURCE_INTEGRITY_REVERIFIED.json` records the renewed 16,711-file audit against the original supplied source tarball.
- `SHA256SUMS` lists changed source, new numerical scripts, local certificates, benchmarks and handoff docs; `DELIVERY_SHA256SUMS` lists top-level artifacts.

**No release authorization:** all full-campaign, execution-roundoff, matched comparator and independent release obligations remain open. Preserve the stronger completed source and evidence while continuing only the missing proof work.
