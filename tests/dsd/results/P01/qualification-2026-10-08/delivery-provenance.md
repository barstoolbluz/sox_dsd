# Follow-up delivery provenance

Input: `sox_ng-P01-DSDIFF-writer-repaired-2026-10-08.tar(2).gz`
SHA-256: `1b30629dd8b8bd49aadd6738a64d338b2686ea4f6f0f0f3e5b5e55795f2ead78`

A byte-wise comparison of every regular file against the input tarball found:

- No removed files.
- Exactly three existing files changed: the two P01 handoff documents
  (`docs/dsd/handoffs/P01.md`, `docs/dsd/handoffs/P01_CHECKPOINT.md`)
  and the regenerated distribution manifest
  (`tests/dsd/results/P00/P00_SHA256SUMS.txt`).
- The 76 newly introduced files are confined to
  `tests/dsd/results/P01/qualification-2026-10-08/`.
- No production C/header source, test implementation, or benchmark changed.

Both verification builds and the original pre-P01 source comparison were kept
outside this deliverable. The only source in this tarball is the original
corrected candidate, with fresh qualification results and documentation.
