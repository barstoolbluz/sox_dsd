# P15 re-adjudication reproducible checkpoint — 2026-10-14

## Custody

Input archive: `sox_ng-P15-readjudication-81d141b8.tar.gz` (snapshot of reported `81d141b8`, no `.git`). SHA-256: `03a798a2d3002278b8450c04406c34a319f1c0b4c8e882b17949bfb6311b594a`. Source authority: `docs/dsd/DSD_DESIGN.md`; previous closeout decision: `docs/dsd/handoffs/P15_CLOSEOUT_ADJUDICATION_2026-10-14.md`.

## Checkpoint 1 — independent reinspection

- Archive SHA-256 matches stated digest.
- Original 7,802-entry P00 SHA inventory: `sha256sum -c ...` exit 0.
- Five R2 matrix sessions: existing `p15_matrix_receipt_review.py --require-coverage` exit 0 (54 scalar cells, 216 forced non-scalar, 96 detailed, 54 graphs, 54 sampled SRC). NOT a release certificate: complete composite extrema and like-for-like SRC proof absent.
- Fifteen soak families/rates contain 915 `.state` files (61 per run), 15 execution JSON receipts, 15 result JSONs.
- DSD256 R2: each arm at both 176400/352800 Hz contains 15 repetitions; observed median ratio vs direct legacy >3.7. `-20000` low-pass in asserted matched control is not DSD256 mastering's 40,000-Hz passband. Matched-control claim cannot yet pass.
- Intel AVX-512 physical timing remains UNRUN; proposed narrowly scoped *policy/performance* exception is under review and cannot be treated as an executed test.

## Work still to persist

1. Formal narrowly scoped Intel AVX-512 amendment, if review warrants, with exact wording and no change to dispatch or production bits.
2. Source-bound, repeatable independent receipt checks; versioned new adjudication receipt; regression tests.
3. Four-gate disposition, complete release decision, no changed historical files other than self-excluding P00 inventory.
4. Verification and handoff, export source-only tar.gz with SHA-256 and command results.

**Operational rule:** no production qualification activation and no P16 until complete first-release gates close. This checkpoint is not an authority replacing the versioned final adjudication.

## Checkpoint 2 — design, checks and bounded refusal persisted

- Feature-scoped design amendment inserted immediately under the mandatory
  Intel benchmark clause in `docs/dsd/DSD_DESIGN.md` section 10.7; companion
  `docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md` explains the
  decision. The physical test remains UNRUN, with no default/qualified edit.
- R2 source-bound reviewer `tests/dsd/p15_readjudication.py` reads all five
  matrix sessions, parses and cross-checks all 915 soak states and their
  terminal reports, checks execution/source hashes, recomputes performance
  medians/CIs and refuses calling the 20 kHz staged control bandwidth-matched
  to the source-confirmed 40 kHz DSD256 mastering profile.
- `--require-release` exits 2 and writes
  `tests/dsd/results/P15_readjudication_2026-10-14/review.json`. Repeated
  same-byte write is idempotent; differing preexisting output is refused.
- Seven new mutation/idempotency tests PASS. Four adapted historical closeout
  tests PASS; 12 corpus audit tests PASS. AVX1 physical evidence checker and
  present/older corpus comparator PASS.
- Disposable build completed; `make -j2` returned 0, P15 CLI tests 134/134
  PASS. `make check` exceeded verification window partway through the generic
  suite and is NOT a successful full gate. `make check-dsd` was not run.
- Definitive bounded decision and next steps in
  `docs/dsd/handoffs/P15_READJUDICATION_2026-10-14.md`: release BLOCKED on
  composite SRC numerical qualification and valid matched DSD256 comparator;
  no P16. Source handoff includes the explicit Intel ruling.

## Checkpoint 3 — preservation and final shipping boundary

The original archive contains **7,803 regular files**. The byte comparison of
all originals against the current source found **zero removed files**, **zero
modified prior handoffs** (59 checked), and **zero modified old result files**
(6,845 checked outside the P00 checksum inventory). The only original files
whose bytes changed are `docs/dsd/DSD_DESIGN.md`,
`docs/dsd/QUALIFICATION.md`, `tests/dsd/p15_closeout_review.py`,
`tests/dsd/test_p15_closeout_review.py`, and the intentionally regenerated
`tests/dsd/results/P00/P00_SHA256SUMS.txt`. Exact digest comparisons and
new-file enumeration are in
`tests/dsd/results/P15_readjudication_2026-10-14/preservation.json`.

The final P00 manifest is **self-excluding**, covers **7,809** files including
new handoff and adjudication records, and must be verified from the source
root with `sha256sum -c tests/dsd/results/P00/P00_SHA256SUMS.txt`. The build
copy and result scratch directories belong outside the authoritative tree.
The source archive SHA-256 is supplied with the handoff as transport metadata
rather than inserted into the tree, avoiding an archive-self-hash cycle.

After reassembly/extraction in a future session, check the archive digest,
verify this P00 manifest, read the latest handoff and execute the
readjudication script with `--require-release`: exit **2** is the required
refusal while two gates are open. Neither hardware Intel unavailability nor
a tool's coverage PASS is release authorization. **Do not start P16.**
