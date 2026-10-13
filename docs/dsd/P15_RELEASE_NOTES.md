# P15 qualification build: release notes

**Correctness/build notes only. Not a mastering-profile general release.**

This continuation accepts the P10 positive historical scalar-mastering
certificate as authentic for its documented inputs, validates its revision
lineage without altering any old receipt, and introduces a P15 release gate
manifest that is intentionally marked blocked when mandatory evidence is
missing. It restores the complete predecessor check-dsd invocation for the
P15 phase rather than silently skipping P06-P14 gates.

New CLI support accepts rate-pinned `decode.mastering.v1.dsd64|128|256`,
`decode.wideband.v1.dsd64|128|256` and
`encode.mastering.v1.dsd64|128|256` aliases under `--dsd-decode` /
`--dsd-encode`, matching the already-supported effect-level IDs. Invalid
rates, incompatible native clocks in selected conversion paths, and
contradictory explicit options fail preflight before opening output. The
P15 regression executes and byte-compares all 54 native/profile/PCM-rate
versioned and human-alias conversion pairs; this is not spectral qualification. This adds no DSP coefficients or kernel
implementation and leaves the previous ordinary PCM and native DSD processing
policies unchanged.

Previously accepted native DFF/DSF size, chronology, channel, seek and DoP
corrections remain in the tree. They are not newly claimed P15 changes.
Versioned labels identify profiles; they do not prove a hardware/quality
certificate. Automatic migration to DSD source-aware `auto`, promotion of
mastering encode flags, and any ISA preference change are **not** part of this
blocked release. Consult `QUALIFICATION.md` for the open-gate evidence ledger
and `MIGRATION_P15.md` for explicit current syntax and level/domain semantics.
