# DSD engine design documentation

The approved design for a planned sox_ng DSD engine refactoring, revision 1.0
(2026-10-07), written against source baseline
`16aa7e17531dd3612f29247da98c8ea570cd905a`. This is documentation and
design-time evidence only: nothing here asserts that the described engine
exists or has been release-qualified.

Read `DSD_DESIGN.md`, then the next permitted phase's entry in
`IMPLEMENTATION_PLAN.md`, then that phase's `sows/Pxx.md`, then prior
`handoffs/`. P00–P15 are the DSD64/128/256 release; P16–P18 are a separately
gated extension for packed input and DSD512/1024 — do not advertise the
extension as present merely because the type system can represent its rates.

## Contents

| Path | Role |
| --- | --- |
| `DSD_DESIGN.md` | Technical specification: architecture, algorithms, interfaces, acceptance contracts. The authority that resolves conflicts with any phase summary. |
| `IMPLEMENTATION_PLAN.md` | Dependency-ordered plan, P00–P18, with per-phase scope, gates and dependencies. |
| `sows/P00.md` … `sows/P18.md` | Standalone fresh-session statements of work, one per phase. Each assumes no chat history. |
| `phase_manifest.json` | The same 19 phases in machine-readable form: id, title, dependencies, files read/changed, steps and test gates. |
| `evidence/` | Probes, logs and results from the design session, with `evidence/README.md` explaining what was actually observed versus what remains future qualification work. |
| `handoffs/` | One `Pxx.md` per completed phase: objective, files changed, commands and exit codes, evidence paths, passed/failed/skipped gates, deviations, next permitted phase. Empty until P00 lands. |
| `DSD_HANDOFF.md` | The combined deliverable as received, sha256 `e1d4218f…`. Frozen for provenance — the files above are split from it byte-for-byte, so make edits there, not here. |

## Provenance

`DSD_DESIGN.md`, `IMPLEMENTATION_PLAN.md`, `sows/`, `evidence/` and
`phase_manifest.json` are installed verbatim from the
`repository_overlay/docs/dsd/` tree of `sox_ng_dsd_design_package.zip`
(sha256 `1a5335f175cc1cae4f01fe1051b5a756867d2ba59c589a9f060da09994ad6c16`),
whose 81 files verified against its own `SHA256SUMS`. That package's
`QA_REPORT.json` records structural checks only — 19 phases present, balanced
Markdown fences, parseable JSON — and is explicitly not a numerical audit.

`evidence/` is design-time material, not the regression harness. P00 ports the
reproductions into named expected-failure tests with independently checked
fixtures; later phases remove only the matching expected failure once the
defect is fixed.

## Paths later phases create

| Path | Created by |
| --- | --- |
| `docs/dsd/BASELINE.md` | P00 |
| `docs/dsd/SEEK_CONTRACT.md` | P03 |
| `docs/dsd/QUALIFICATION.md` | P15 |
| `docs/dsd/handoffs/Pxx.md` | each phase |
| `tests/dsd/{fixtures,reference,results}`, `tests/dsd/run.py`, `measure.py`, `bench.py`, `test_io.c` | P00 |
