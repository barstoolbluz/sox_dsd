# P05 corrective checkpoint and resumption record

This file is inside the *source-only* deliverable so a subsequent session can resume without the ephemeral working environment.

## Provenance and scope

- Input archive: `sox_ng-P05-complete-2026-10-09.tar.gz`, SHA-256 `93a6c79fcf0703178ab47355407ee29d3ce1d1f212d78a62771cd8192cfd8d15`.
- P05 authority: `docs/dsd/sows/P05.md`, `docs/dsd/DSD_DESIGN.md` sections 5.1-5.4, `docs/dsd/IMPLEMENTATION_PLAN.md` and prior handoffs.
- Seven defects corrected only in planner/CLI integration, read-only private effect-option queries, tests and handoff. No default, existing audio sample loop, public ABI, or deferred DSP implementation changed.
- Worktree Git checkpoints (not included in archive): `ec303a4` original P05 baseline and `22a740d` initial 139-case corrective implementation. The source in this deliverable is the complete later authoritative state; `.git` is intentionally absent.

## Reproduced gates on delivered source state

- Static build: `autoreconf -fi`; `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`; `make -j2` - PASS from a source-only clean copy; no compiler warnings.
- `make check` - PASS (73 OK, 8 VOID).
- `make check-dsd` - PASS on the clean retry and configured build: 36 inherited DSD regressions, 706 P02 streaming checks, 59 P03 seek, 46 P04 layout, 168 P05 C assertions, 147 P05 CLI cases. One earlier clean attempt was externally timed out; not claimed passed.
- `tests/dsd/run.py --phase P05` - 36 pass, zero xfail/xpass/fail/skip.
- `tests/dsd/measure.py --phase P05` - 5 passed, 0 failed; later DSP certification unrun.
- `tests/dsd/bench.py --phase P05` - 36/36 development workloads, not a throughput performance certification.
- `tests/dsd/bench_plan.py` - 44/44 startup/RSS measurements from a neutral working directory.
- 5% controlled-host throughput gate - INCOMPLETE: host preparation and <2% measurement noise not established.

## Continuation

The current accepted P05 planning implementation is complete; proceed to P06 only after downstream audit/acceptance. The full corrective report and raw normalized results are in `docs/dsd/handoffs/P05.md` and `tests/dsd/results/P05/corrective/`. Preserve all historical evidence and checksum manifests. Re-run `make check` and `make check-dsd` from a freshly configured copy of these delivered bytes if the tree changes. Reopen the P05 planner only for a reproduced contract defect; do not expand into later DSP engineering.
