# P18 early recovery checkpoint (development; not sign-off)

Authority: `amendments/P18_AUTHORIZATION_2026-10-21.md`. No capability enabled.
Source snapshot: input archive SHA-256 `66cf9668d7db8130989905a856ae2310b9ad833ed327f13ec77a6bf687cccd21` (claimed 51c391f2; original .git absent).
This checkout has a **synthetic Git baseline commit** `69678ff` created from the supplied working set, not a claimed ancestor of the original git history.

Implementation so far: private closed P18 rate/endpoint/operation registry, checked DoP rate arithmetic, DSF/DFF physical extent math and high-rate reader/writer refusal, DoP start refusal, planner refusal, WSD input refusal, high-rate synthetic fixtures and independent reference checks, P18 runner integration, frozen vector hashes. The C P18 core unit passes 372 assertions; initial P18 integration passes 82/82 high-rate refusal + legacy smoke cases. Full P18 regression/numeric/bench are pending as of this checkpoint. Files under `tests/dsd/results/P18` contain early build/CLI evidence. No enablement is authorized.

Next steps: produce P18 compatibility ledger and release manifest + schema; run full make check, check-dsd P18, run.py P18, measure.py P18, bench.py P18, validation script; repair any genuine defects; update `handoffs/P18.md`, hashes and final source bundle.

Do NOT edit the frozen P00 index or P15 historical exclusions. Original .git unavailable, so continuation is represented as a synthetic-baseline Git history plus complete source tree, not a fast-forwardable commit on actual `51c391f2`.

## Final P18 closeout (2026-10-21)

This supersedes the early-development "pending" status above without deleting the chronological checkpoint. All high-rate capabilities remain **disabled**. Full source build and DSD suite: `build/qualification.status` records exit 0 for autoreconf, configure, make, P16 fresh and cached integration (219/219 each), complete P18 `make check-dsd` (45/45), `make check-rename` and frozen P18 fixture validation. An earlier `build/check-dsd-final.exit=2` is retained: the inherited P16 harness skipped all cached cases, then failed with `KeyError: 'verdict'`. A one-line unconditional end-of-run `save()` fixed the actual idempotency defect and passed both fresh and cached tests; no acceptance was relaxed.

`build/release-gates.status` records exit 0 for generic `make check`, explicit `run.py P18` (45/45), `measure.py P18` (11 checks), `bench.py P18` (36 inherited low-rate development observations), and manifest seal/check. `integration/capability-integration.json` records 88/88 real SoX refusal/lower-rate smoke checks. `docs/dsd/P18_RELEASE_MANIFEST.json` reports `P18_COMPLETE_FAIL_CLOSED`, 12 disabled high-rate rate/endpoint/operation rows, 15 passing local evidence gates, P17 DSP unqualified and zero device claims. Six deliberate in-memory schema corruption probes were rejected; results in `build/manifest-negative-probes.json`.

**No independent high-rate real-media/player/device evidence exists.** P15 standing source obligations remain OPEN; P17 production DSP qualification remains UNQUALIFIED. These remain explicitly UNRUN/OPEN, not inferred PASS. Resume with `docs/dsd/handoffs/P18.md` and the saved raw evidence; follow the file's clean build commands and reseal only after an authorized source/evidence change. The source history is synthetic because the supplied working set omitted `.git`. The complete post-P18 output is archived as a fresh clone, so no stale built object may override source on a later host.
