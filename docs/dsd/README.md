# SoX DSD documentation

SoX DSD 1.1.1 extends SoX-NG with native DSD processing while retaining the
upstream audio formats, effects, libraries and build system.

## Start here

- [Using SoX DSD](USING_SOX_DSD.md): formats, native rates, conversion examples,
  profile selection and limitations.
- [1.1.1 release notes](RELEASE_NOTES_1.1.1.md): defaults, compatibility and
  version-specific behavior.
- [CLI migration reference](MIGRATION_P15.md): options and renamed profiles.
- [Unified decoder](UNIFIED_DECODER_2026-11-09.md): mastering and wideband
  reconstruction, and independent high-rate encoder selection.
- [High-rate v1 encoder](V1_HIGH_RATE_ENCODE_2026-11-07.md): encoder qualification
  and high-rate default changes.
- [Qualification and tests](QUALIFICATION.md): checks, test inputs and evidence
  publication boundaries.

## Technical references

These describe algorithms or interface contracts, not instructions to reopen
past engineering phases:

- [DSD engine design](DSD_DESIGN.md) (historical design specification; shipping
  behavior is defined by the current source and release notes)
- [SDM register stability proof](SDM_REGISTER_PROOF.md)
- [Guard policy](LEGACY_SDM_GUARD_POLICY.md)
- [Seek contract](SEEK_CONTRACT.md) and [channel-layout contract](LAYOUT_CONTRACT.md)
- [CLI design](CLI_USABILITY_DESIGN.md)

## Source tests versus historical evidence

`tests/dsd/` contains runnable tests, fixtures, numerical references and
research scripts. Test runs write new receipts under `.dsd-check-results/`
(or the explicitly supplied `DSD_RESULTS` path); generated receipts are not
tracked. The `tests/dsd/release_evidence/` fixture is retained because the
1.1.1 evidence review and redaction regression consume it.

Archived phase briefs, handoffs, statements of work, gate reports, raw run
receipts, checksum inventories and numerical experiment outputs belong to the
**SoX DSD 1.1.1 evidence archive**, distributed as a separate GitHub release
asset (`SoX_DSD_1.1.1_Evidence_2026-11-09.tar.zst`). It preserves the original
repository-relative paths, lists source and published SHA-256 values, and
records host-path redactions. It is not required to build or run the project.
The scripts and policy under `scripts/` explain how that asset was made and
how the repository history is rewritten.

SoX DSD remains a fork intended to merge upstream SoX-NG releases. Upstream
files and project build conventions have not been reorganized.
