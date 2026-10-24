# SoX DSD — 14.8.1 corrective R3 (October 23, 2026)

**Purpose:** Narrow repair of two confirmed R2 handoff defects and the
mode-sensitive R2 patch-replay inconsistency. This is an **R2 -> R3**
corrective, not another upstream merge or DSP qualification project.

**Inputs:** R2 source archive
`sox_dsd_14_8_1_CORRECTIVE_R2_FULL_SOURCE_2026-10-23.tar.zst`
(SHA-256 `287584ab00cb5348f39c2f62771ec1b8bd892ecda11bc3bdffa9a663d3db15ae`).
The R2 bundle was used for the previous review patches and installer.

## Contents

- `source/sox_dsd_14_8_1_CORRECTIVE_R3_FULL_SOURCE_2026-10-23.tar.zst`:
  complete **available 4,126-file corrected source working set** (SHA-256
  `0c272e982ffc3a21083b873f119e89cf1ac470c7ba09ac09756c3b1f8364254e`).
- `review/06-extraction-and-readonly-corrective.patch`: self-contained
  **R2 -> R3 source patch**, changes `test/Makefile.am`, adds
  `test/run_check_staged.py`, and corrects P04 fixture staging in
  `tests/dsd/test_layout.py`. Clean `git apply` and byte-for-byte rehash
  against all 4,126 source files have been performed.
- `review/06-installer-r2-r3.diff`: separate difference to the overlay
  installer (which intentionally lives at bundle root, not in production
  source). `review/01` through `review/05` are retained unchanged for
  historical handoff; apply only to their original source stages.
- `BASE_SOURCE_MANIFEST.json`: R2 file bytes/size and recorded modes for
  all 4,125 source members. `CURRENT_SOURCE_MANIFEST.json`: R3 equivalents
  for all 4,126. `overlay/` contains the three R3 transition paths.
- `apply_overlay.py`, `tools/test_overlay_identity.py`, `evidence/`,
  `SOURCE_FILE_SHA256SUMS`, `SHA256SUMS`, and `CHECKPOINT.md`.

## What was fixed

### Installer — extraction modes are not source corruption

The previous installer rejected a correct R2 source extracted with a typical
`umask 022` (e.g. `AUTHORS` changes from `0664` to `0644`), or an R3 ZIP
extracted with Python's `zipfile.extractall()` (it commonly drops the UNIX
external executable/permission mode on payloads). A `git apply` that changed
non-executable permission bits also caused false refusal.

R3 authenticates the **SHA-256 and byte size of every one of the 4,125 R2
source members**, checks the **complete source file set**, and rejects unknown
files, directories used as files, symlinks, multiply linked files, and
special permission bits. It authenticates all overlay payload bytes before
writing. It deliberately ignores *read/write* mode variations caused by
archive extraction, while restoring the **expected executable bits** where an
extractor has removed or added them. It does not impose group-writable modes
on a user's source tree. Mode corrections and replacements are rechecked
against the source bytes immediately before mutation; post-install content,
member count and executable bits are checked again.

`--check` performs no writes. Interrupted states may contain any permitted
mix of R2 and R3 transition bytes and are resumable. Authentic but modified
source content outside the three permitted transition paths still fails closed.
The tool expects an exclusively owned, unchanged **extracted source snapshot**;
it is not intended for a source checkout with `.git`, generated build files,
or concurrent edits. It does not provide multi-process locking or a
multi-file transaction: an interrupted invocation is resumed by rerunning it.

### Test harness — immutable source trees

The R2 `test/Makefile.am` ran `test/check.sh` directly from `$(abs_srcdir)`,
where the regression scripts created output files and failed on read-only
sources. R3 stages **all 81 available inherited regression cases** and their
required fixture/helper files into a unique temporary directory under the
build-side `test/` directory, then runs the unchanged original `check.sh`.
Case directories are writable copies. It verifies every staged case was
actually reported, refuses an empty selection, and removes the scratch tree
on success or failure. The relative `../../src/monkey.wav` and `../samples`
references remain valid. No source fixture is modified.

The P04 DSD layout oracle also generated its own test fixtures under the
source tree, causing the full P18 gate to fail with immutable sources.
Generated P04 DFF/WAV/WSD fixtures and its manifest now live under the
caller-supplied results directory. All 14 independently generated audio
fixture bytes were compared against the committed originals and were
identical; only the generated manifest's paths change to describe their
real build-side locations. The 46 P04 cases pass with read-only sources.

## Installation and verification

The source tarball is standalone; it already contains R3. For an extracted R2
source tree, first extract **this ZIP** with `unzip` **or** Python's
`zipfile.extractall()`. The following commands work from the extracted R3
bundle directory (change the R2 path to suit your system):

```
sha256sum -c SHA256SUMS
python3 apply_overlay.py --source /path/to/R2/sox_dsd --check
python3 apply_overlay.py --source /path/to/R2/sox_dsd
python3 apply_overlay.py --source /path/to/R2/sox_dsd --check
```

To verify the **standalone** source archive:

```
mkdir -p /tmp/sox-dsd-r3-check
cd /tmp/sox-dsd-r3-check
tar --zstd -xf /path/to/R3/source/sox_dsd_14_8_1_CORRECTIVE_R3_FULL_SOURCE_2026-10-23.tar.zst
sha256sum -c /path/to/R3/SOURCE_FILE_SHA256SUMS
```

To apply the code patch manually from an R2 source tree, run `git apply
--check /path/to/R3/review/06-extraction-and-readonly-corrective.patch` then
`git apply` the same file. The patch produces all R3 file **bytes** exactly;
`git apply` does not promise to preserve group-write permission bits.

Build in an external build directory after running `autoreconf -fi` in a
writable source preparation step. Once configured, immutable-source execution
was independently exercised with the build owned by an unprivileged user:
`make check`, `make check-sync`, and `make check-rename`.
The standalone P04 oracle passed **46/46** cases, and the full external
`make check-dsd DSD_PHASE=P18` gate also **passed** with the source
read-only (phase runner **46/46**, packed CLI **219/219**).

## Scope and evidence

Exactly **two existing test-harness files** changed and **one regression
runner was added**. No DSD encoder, decoder, numerical coefficient, high-rate guard,
P00 index, historical P15 evidence, or DSD512/1024 authority file differs
from R2. The original reduced working-set omissions remain omissions; R3
does not manufacture historical `.npz` files or certificates.

See `evidence/qualification_R3.json` and `CHECKPOINT.md` for executed checks
and limits. This is not proof of Windows/MSVC, a full CMake 4 build, or
`make distcheck`. The inherited historical review patch 03 still contains
four binary fixture deltas that cannot be replayed from its text patch;
the integrated R3 archive contains the source-tree fixture bytes.
