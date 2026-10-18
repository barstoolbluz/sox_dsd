# Applying the P15 high-rate implementation to the third-pass baseline

This directory contains the independently applicable source patch, exact changed-file copies, preimage/postimage manifests, and an actual zero-fuzz application check. New evidence is a separate overlay. No production DSP source, filter coefficient, normative tolerance, or release-policy file is patched. P15 remains BLOCKED.

## Required starting point

Use an untouched extraction of:

```text
sox_ng_P15_prover_third_pass_FULL_SOURCE_2026-10-18.tar.gz
SHA-256 d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4
```

`CHANGED_FILES.json` identifies exactly four modified original files and twelve new Python files. `PREIMAGE_SHA256SUMS` pins the four old files; every newly added path must be absent from the baseline. `POSTIMAGE_SHA256SUMS` pins all sixteen final files. The final file copies are under `changed_files/tests/dsd/`.

The modified original files are the branch-population bounder, continuum policy-limit helper, stagewise prover instrumentation, and the existing second-pass regression test. Additions supply the certified halfband majorant, bounded experiment and diagnostic tools, census/report tools, and focused independent tests. The original campaign dispatcher is unchanged. Historical proof implementations and receipts remain in their original locations or explicitly named frozen snapshots.

## Dependencies

The recorded numerical environment uses **Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, and mpmath 1.3.0**. `requirements-proof.txt` pins the three external Python packages. The proof tests load SciPy through existing source/operator support; install it even when an individual new helper appears to use only mpmath. No third-party package is vendored by this patch.

For a separate environment with the matching Python interpreter:

```sh
python3.12 -m venv /path/to/p15-proof-venv
/path/to/p15-proof-venv/bin/python -m pip install -r /path/to/integration/requirements-proof.txt
```

These versions and the recorded platform identify the tested environment; they are not a proof of the numerical libraries. The methods document states the interval-arithmetic trust boundary. Use a matching Python 3.12.14 installation for exact environment reproduction.

## Apply the source patch and copy new evidence

In the commands below, `P15_INTEGRATION` names this directory in the compact bundle. Run the patch commands from the extracted baseline repository root. The source hashes, not timestamps, determine applicability.

```sh
P15_INTEGRATION=/absolute/path/to/integration
sha256sum -c "$P15_INTEGRATION/PREIMAGE_SHA256SUMS"
patch -p1 --fuzz=0 --batch --forward --input "$P15_INTEGRATION/P15_high_rate.patch"
sha256sum -c "$P15_INTEGRATION/POSTIMAGE_SHA256SUMS"
```

Before applying, confirm that the twelve `ADDED` paths in `CHANGED_FILES.json` do not already exist. The independent applicability validator below performs this check automatically. A preimage mismatch, an already present new file, a rejected hunk, or a postimage mismatch must be resolved by restoring an untouched baseline; do not relax fuzz or adapt the patch silently.

Copy the bundle's complete new `P15_high_rate_2026-10-18` evidence directory into a **new** `tests/dsd/results/P15_high_rate_2026-10-18/` directory in the patched repository. Preserve its relative structure. If that destination already exists, compare manifests and use a clean baseline extraction instead of overwriting evidence. The evidence includes immutable raw receipts, old and final proof snapshots, source/operator verification reports, scalar readjudication, benchmark metadata, mathematical methods, and continuation instructions. It is not applied as a modification to prior historical receipts.

## Actual applicability validation

The retained `applicability/RESULT.json` records a successful application with GNU patch 2.7.6, `-p1 --fuzz=0 --batch --forward`, to isolated copies of the exact third-pass preimages. All sixteen resulting file hashes equal the final best-source hashes. The original baseline was unchanged. The raw patch log and both hash manifests are preserved. This is an application/identity test; numerical validation is recorded separately in the evidence testing directories.

To repeat this check without modifying an extracted baseline:

```sh
python "$P15_INTEGRATION/validate_patch.py" \
  --baseline /absolute/path/to/untouched/sox_ng \
  --output /absolute/path/to/new-validation-directory
```

The isolated directory contains only the affected source paths. It is not a full source tree or an audio build. The validator refuses mismatched old files, unexpected existing additions, a changed patch, rejected application, extra postimage files, or a nonmatching result. Each validation uses a new output directory so its logs are preserved.

## Focused numerical tests

From the patched repository root, with the pinned environment active:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m unittest \
  test_p15_high_rate_independent \
  test_p15_high_rate_population \
  test_p15_high_rate_terminal_saturation \
  test_p15_normative_limit_rounding \
  test_p15_prover_second_pass \
  test_p15_prover_third_pass \
  test_p15_high_rate_census \
  test_p15_high_rate_coverage_report \
  test_p15_high_rate_experiment
```

The stored runs identify exact test-source hashes, outcomes, time, memory, and any expected executable-dependent skips. Repeating tests is not a substitute for regenerating source-bound continuous-frequency receipts. The independent aggregation and scalar-admission tests under `complete_cell/` are stdlib-only and can be run separately with `python -m unittest discover -s tests/dsd/results/P15_high_rate_2026-10-18/complete_cell -p 'test_*.py'`.

## Reconstruct proof versions for benchmark replay

The retained `reference_third_pass_code`, `reference_high_rate_v1_code`, `reference_high_rate_v2_code`, and `reference_high_rate_final_code` directories each contain a flat imported-module snapshot, an `IDENTITY.json` map, and a SHA-256 manifest. The first high-rate and v2 snapshots preserve the old policy-threshold helper; their receipts require the separate exact-normative summary readjudication. The final snapshot contains the corrected full directed threshold intervals. Historical snapshots are references, not a recommendation to install an older decision procedure for new qualification.

To replay a historical version, make a separate complete extraction of the verified baseline and copy only the `.py` files from that chosen snapshot into its `tests/dsd/`. Check the resulting imported-module hashes against the snapshot's `IDENTITY.json`. The source/operator inputs remain those of the untouched baseline. Use the new experiment harness from the patched tree with `--source-root` pointing to the separate reconstructed tree. For example:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python /absolute/path/to/patched/sox_ng/tests/dsd/p15_high_rate_experiment.py \
  --source-root /absolute/path/to/reconstructed/sox_ng \
  --job-index 5597 --label independent-replay \
  --seconds 60 --max-nodes 128 --max-paths 20000 \
  --output /absolute/path/to/new-receipts
```

Use each recorded experiment's exact job index, budget, node/path limits, profiling flag, CPU affinity, and numerical environment when comparing performance. The harness verifies actual imported module paths and hashes before and after the proof; it refuses mixed implementation trees and conflicting receipt identities. It preserves a full code/source/operator identity in every new result.

The internal signal deadline is not enforceable process termination. For strict execution limits use external process supervision, such as the bounded runner retained in `execution/`, with a separate startup allowance and kill deadline. A killed process is a resource outcome, not a spectral PASS or violation. Use a new output directory when changing proof code, budget, or source bindings; never overwrite a prior OPEN or PASS receipt.

Final certified coverage, remaining OPEN cases, and exact continuation commands belong to the completed coverage reports and persistent continuation checkpoint. This integration README makes no planned-campaign completion claim.
