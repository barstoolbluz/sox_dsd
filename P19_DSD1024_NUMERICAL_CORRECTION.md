# P19 DSD1024 numerical correction — 2026-10-21

**Engineering result: PASS (experimental v2). Production qualification: NOT COMPLETE.**

This archive replaces the prior P17 qualification bundle with an additive, independently versioned **seventh-order** DSD1024 encoder candidate. It removes the reproduced positive/negative DC numerical failures without modifying qualified DSD64/128/256 or enabling high-rate capabilities. The original unstable eighth-order candidate remains present and blocked. New training **17/17**, guarded holdout **36/36**, and cross-ISA **25/25** pass. The frozen v2 bounds, exact executable captures, source-bound evidence, independent FIR diagnostic, inherited regressions and resumption procedure are included.

See `docs/dsd/handoffs/P19_DSD1024_V2_CORRECTION_2026-10-21.md` and `docs/dsd/handoffs/P19_DSD1024_V2_RESUME_2026-10-21.md`.

**Open requirements:** prepared-host one-hour unreset tests in both modes, independent source/reference audio, performance qualification, and a subsequent separately authorized high-rate writer/transport integration. None has been silently waived.

Verify every file with `sha256sum -c P19_BUNDLE_SHA256SUMS.txt`. Historical P17 manifests and candidate records are archived under the P19 `preimage` directory. No Git commit is asserted by this source-only working set.
