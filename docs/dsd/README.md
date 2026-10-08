# DSD engine design documentation

Design and implementation documentation for the planned sox_ng DSD engine
refactoring, revision 1.0 (2026-10-07), against source baseline
`16aa7e17531dd3612f29247da98c8ea570cd905a`. This is documentation only:
nothing here asserts that the described engine exists or has been
release-qualified.

## Contents

| File | Role |
| --- | --- |
| `DSD_DESIGN.md` | Technical specification: architecture, algorithms, interfaces, acceptance contracts. The authority that resolves conflicts with any SOW summary. |
| `IMPLEMENTATION_PLAN.md` | Dependency-ordered plan, P00–P18, with per-phase scope, gates and dependencies. |
| `sows/P00.md` … `sows/P18.md` | Standalone fresh-session SOWs, one per phase. Each is self-contained and assumes no chat history. |
| `EVIDENCE.md` | Design-time evidence and reproduction guide for the probes run during the design session. |
| `handoffs/` | One `Pxx.md` per completed phase: objective, files changed, commands and exit codes, evidence paths, passed/failed/skipped gates, deviations, next permitted phase. |
| `DSD_HANDOFF.md` | The combined deliverable exactly as received. Frozen for provenance — make edits in the split files above, not here. |

## Reading order

`DSD_DESIGN.md`, then the entry for the next permitted phase in
`IMPLEMENTATION_PLAN.md`, then that phase's `sows/Pxx.md`, then any prior
phase handoffs. P00–P15 are the DSD64/128/256 release; P16–P18 are a
separately gated extension for packed input and DSD512/1024. Do not advertise
the extension as present merely because the type system can represent its
rates.

## Paths the plan expects

The SOWs reference these; each is created by the phase that owns it.

| Path | Created by |
| --- | --- |
| `docs/dsd/BASELINE.md` | P00 |
| `docs/dsd/SEEK_CONTRACT.md` | P03 |
| `docs/dsd/QUALIFICATION.md` | P15 |
| `docs/dsd/handoffs/Pxx.md` | each phase |
| `tests/dsd/{fixtures,reference,results}`, `tests/dsd/run.py`, `measure.py`, `bench.py`, `test_io.c` | P00 |
| `evidence/` — `reproduce.py`, `probe_io.c`, `probe_filters.py`, `probe_sdm.c`, `probe_remodulation.py` and their result JSON | companion package, installed by P00 |

`evidence/` is not yet present in this tree; `EVIDENCE.md` describes what it
should contain.
