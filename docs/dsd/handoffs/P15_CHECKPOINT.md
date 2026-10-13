# P15 authoritative continuation checkpoint

**Date:** 2026-10-12 (local). **Status: IMPLEMENTATION AND AVAILABLE-HOST VERIFICATION DELIVERED; MANDATORY RELEASE GATES OPEN.** Do not promote automatic defaults or production mastering solely from this checkpoint. This is a resumable source-only continuation, not a full P15 release certificate.

## Input identity and custody

- Input `sox_ng-P15-dispatch-f13dda14-2026-10-12.tar.gz`, SHA-256 `73454c06c4e071f9c1c3078846d325fdb6214a65eda3a9e4f49b38b192a42229`, original tree `sox_ng/`, no `.git`.
- The initial early source checkpoint was captured before long-running work; its checkpoint tarball SHA-256 is `7b3724cc9f93cbbcd826d89c4ece5fffcfeda5ab7d7dd2708b0145b28d315a07`. That **early** archive is superseded by this complete P15 continuation; it is not nested in the delivered source.
- The final source tree includes P00-P14 accepted documentation and test receipts byte-identically. `tests/dsd/results/P15/preservation.json` checks the original archive: 3,623/3,623 older result files and 50/50 older handoffs unchanged, no original source files deleted. The P00 self-excluding SHA-256 index was deliberately rebuilt after source/result finalization.
- Use `docs/dsd/sows/P15.md` and `docs/dsd/DSD_DESIGN.md` as acceptance authority. `docs/dsd/handoffs/P15.md` is the detailed human delivery report. `docs/dsd/QUALIFICATION.md` is the release-gate interpretation. `tests/dsd/results/P15/release/release-manifest.json` is the machine-readable current evidence ledger.

## Current known-good implemented work

- Nine versioned profile IDs parse through the shared registry at both CLI and effect level; rate pins enforce the actual decode/encode selection; conflicting explicit pins are diagnosed before output creation.
- Production legacy default, selected FIR/SDM automatic preferences, mastering encoder qualification bits, coefficients, guard thresholds, and generic PCM graph are **unchanged**.
- Final P15 CLI regression includes **134 executable checks**, including 54 real PCM render and human/versioned alias comparison cells; separate source P15 functions, tests, docs and release-manifest writer are present.
- `autoreconf -fi`, configure, `make -j2`, `make check`, full inherited `make check-dsd`, P15 runner (36/36), numeric (10/10 available checks) and P15 full development benchmark (54/54 generic cases and 7/7 forced AVX2/AVX-512 suites) exited **0** on a virtualized Intel host. The full 134-cell integrated `make check-dsd` replay is documented separately in the final result tree.
- The unchanged P10 revision-pinned verifier exits **1 by design**, because four named source files changed after certification. The original P10 scalar certificate remains positive and unedited for the candidate revision. P15 binding: 31 original source receipts intact, four later-source deltas recorded, zero unanticipated deltas.
- Independent clean extraction of the source-only preliminary archive passed global SHA verification, Autotools regeneration, configure, compilation, generic `make check`, full P15 `make check-dsd` and direct 134-check P15 suite (all **exit 0**). Receipt: `tests/dsd/results/P15/packaged-recheck/validation.json` and corresponding raw logs. Executable code hashes match the delivered source.
- The P15 manifest's `status=BLOCKED` and `default_promotion_authorized=false` are expected, *not* failing execution. `--require-qualified` returns **2**, intentionally. The six outstanding mandatory gates are listed in both the handoff and manifest.

## Rebuild and test in any new session

```sh
# Work from the extracted sox_ng source directory. No generated build
# products are in the authoritative continuation archive.
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
make check
make check-dsd DSD_PHASE=P15
python3 tests/dsd/run.py --phase P15 --results tests/dsd/results/P15/resume-run \
  --sox "$PWD/src/sox_ng" --probe "$PWD/test/dsd_test_io" \
  --writer-unit "$PWD/test/dsd_test_dff_writer"
python3 tests/dsd/measure.py --phase P15 --results tests/dsd/results/P15/resume-numeric \
  --sox "$PWD/src/sox_ng"
python3 tests/dsd/bench.py --phase P15 --results tests/dsd/results/P15/resume-bench \
  --sox "$PWD/src/sox_ng" --profile full --repetitions 15 --warmups 1
python3 tests/dsd/p15_release_manifest.py --results tests/dsd/results/P15/release \
  --require-qualified
# The last command is expected to exit 2 until all independent gates close.
```

Create disposable build/results copies before replay rather than overwriting this delivered evidence. Do not run the full benchmark concurrently with CPU-intensive regression checks if interpreting timing results. Future physical benchmarks must record the *actual* host and controlled clock, affinity, microcode, compiler flags and `hypervisor` state. Do not infer physical throughput from this VM's performance ratios.

## Remaining work and next permitted phase

1. Full independent 3 native rates x 9 PCM rates x 2 profile **spectral and stability** release metrology; 54 waveform identity checks do not establish it.
2. Physical Intel AVX-512 and older AVX1-only CPU performance and default-preference suitability, independently controlled.
3. Controlled reference-host 2x six-channel DSD256 target with matching baseline and uncertainty.
4. Complete present-version per-profile/ISA long-duration hardware soak and event/state evidence.
5. Independent present-version DSD corpus/codec/device re-render and acceptance.

These five work packages correspond to six separately tracked release gates because the two physical CPU classes are distinct. Re-evaluate the positive P10 historical scalar mastering certificate in its original scope; never rewrite the immutable P10 receipt to obtain a zero exit from the revision-pinned verifier. Only after all mandatory gates close, change the *specific* default/qualification switches supported by receipts and rerun all inherited suites against the delivered bytes. **Continue P15 until that decision; do not claim P16 authorization.**

When producing a later archive, leave historical results byte-identical, place new receipts under new phase-scoped paths, regenerate the P00 global checksum inventory **last** (excluding itself), and verify `sha256sum -c` before packaging. Keep temporary host paths, compiled binaries and the uploaded covering note out of the source bundle.
