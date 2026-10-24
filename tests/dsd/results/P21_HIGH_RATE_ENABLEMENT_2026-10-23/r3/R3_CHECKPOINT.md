# R3 corrective checkpoint — October 23, 2026 (America/New_York)

## Source of authority and objective

Fix the October 23 R2 handoff review: (1) authentic overlay ZIP/source
extraction fails on noncanonical rw permission bits; (2) `test/check.sh`
is run from read-only source directories and cannot create temporary files;
(3) `git apply` non-executable mode changes lead to installer refusal.
Do not alter numerical DSP, DSD512/1024 capability decisions, P00, P15
historical receipts, or the earlier F01 downloader and F04 WinMM corrections.

## Implemented corrections

- The R3 installer performs 4,125-to-4,126 **full-tree content identity**
  verification with exact SHA-256, file size, path set, regular-file type,
  symlink/hardlink/special-bits refusal. Read/write bits are not used for
  source authenticity. Executable bits are normalized from the manifest,
  without forcing extractor-dependent read/write modes.
- `test/Makefile.am` invokes `test/run_check_staged.py`, which copies the
  original `test/check.sh`, all 81 case directories, the `samples` helper,
  and `src/monkey.wav` into build-side scratch. P04 independent
  generated fixtures are also moved from the source tree into results. Reports every test and
  refuses empty/incomplete execution. Scratch removed at exit.
- The R2 -> R3 source patch changes two existing test-harness paths
  (`test/Makefile.am`, `tests/dsd/test_layout.py`) and adds one runner
  (`test/run_check_staged.py`). Git replay was checked against all 4,126
  source hashes; 4,123 existing paths retain identical bytes.

## Verified checkpoints

- R2 tar.zst SHA-256:
  `287584ab00cb5348f39c2f62771ec1b8bd892ecda11bc3bdffa9a663d3db15ae`
- R3 tar.zst SHA-256:
  `0c272e982ffc3a21083b873f119e89cf1ac470c7ba09ac09756c3b1f8364254e`
- Re-extracted R3 archive matches all 4,126 SHA-256 entries.
- `git apply --check` and `git apply` to the authenticated R2 source:
  all 4,126 resulting source hashes match R3. The R3 installer `--check`
  accepts the patched snapshot even if mode bits differ.
- Installer test rejects tampered unmanaged `src/dsf.c`, tampered payloads,
  unexpected files, symlinks; passes extracted `AUTHORS=0644`, missing
  executable bits, idempotent second application and partial resume.
- Linux out-of-tree Autotools `autoreconf -fi`, `configure
  --disable-shared --without-libltdl`, clean `make -j12`: PASS. Actual CLI:
  `SoX DSD v1.0.0 (based on sox_ng 14.8.1)`.
- Source recursively chmodded read-only/readable and external build directory
  owned by `nobody`: `runuser -u nobody -- make check` passed. All 81 cases
  reported: 73 OK, 8 VOID (optional capabilities). `BUG-363`, `bit-depth`,
  `chorus-glitch`, `wav-riff-size-overflow` reported OK.
- `runuser -u nobody -- make check-sync check-rename`: PASS.
- P04 layout oracle writes 14 generated audio fixtures and a generated
  manifest to the build-side results directory; audio fixture bytes match
  committed source fixtures. Source remains unwritable and 46/46 cases PASS.

## Persistent files and reproducibility

The R3 ZIP contains the standalone source tar.zst, the source patch,
installer patch, baseline/current full manifests, overlay, SHA256SUMS,
source hash manifest, installer adversarial regression, and build/test logs.
Rerun the commands in README.md. Execution logs preserve actual command
results; **do not** convert blocked platform checks into claims of PASS.

## Qualification boundaries

Native Windows/MSVC with real WinMM, full CMake 4 project build,
`make distcheck`, and historical omitted P15 numerical records are not
qualified by these R3 changes. The earlier R2 WinMM mock and downloader
regressions remain available as `make check-sync` and unchanged source tests.
- Entire `make check-dsd DSD_PHASE=P18`, out-of-tree as unprivileged
  `nobody` with immutable source: PASS, exit 0. `tests/dsd/run.py`
  recorded 46/46 PASS, all subsequent enabled stages completed successfully,
  including packed CLI 219/219 and P17 finite/spectral/SDM checks. Evidence
  in `evidence/R3/make_check_dsd_P18_readonly.log` and `P18_run.json`.

- A R3 ZIP extracted using Python `zipfile.extractall()` (payload
  `test/Makefile.am` mode 0644), paired with an R2 source extracted under
  `umask 022`, passed full-tree installer preflight, installation, and
  idempotent reapplication. The separately extracted payload passed the
  adversarial corrupted-unmanaged-source/payload/symlink tests.
- Overlay replacement preserves read/write bits of existing source files
  and restores only the expected executable mask. Newly added files use
  the invoking process's umask.
