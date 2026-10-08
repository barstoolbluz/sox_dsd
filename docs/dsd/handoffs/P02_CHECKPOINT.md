# P02 working checkpoint (October 8, 2026)

Input: `/mnt/data/sox_ng-P02-96e78a55.tar.gz`, SHA-256 `f0c1280fa97937d177f53b66a3c64b4332a5a90be26a02795dcef0d2a94cf471`.

Workspace: `/mnt/data/P02_work/sox_ng`.

Plan: read P02 SOW/DSD_DESIGN; baseline build and seven-failure reproduction; implement local reader fixes; add independent known-answer unit/integration checks and DoP capacity checks; run P02 runner, numeric and benchmarks, generic `make check`; record all exits, measured evidence, affected files and handoff; verify final archive from separate extraction.

Initial source is extracted without changes. No `.git` in input. P00/P01 results are inherited evidence and must remain unchanged, except P00 distribution SHA256SUMS if necessary.

Progress: early checkpoint created before build. The input archive is the immutable recovery baseline. Updated full source checkpoints will be placed at `/mnt/data/P02-checkpoint-*.tar.gz` when implementation begins and before long qualification runs.

Implementation checkpoint 01: `src/dsf.c`, `src/dsdiff.c`, `src/dop.c` contain the initial P02 changes. Built successfully with the baseline flags. `tests/dsd/results/P02/first-pass/run.json` is an executable P02 result: 30 PASS / 6 XFAIL / 0 FAIL; original known P03/P04 failure fingerprints remain. Additional tests and final regressions are not yet complete. Edit sources within this workspace to continue; the immutable original input is always available.

Post-checkpoint verification before finalization:
- P02 phase runner 30 PASS/6 XFAIL/0 FAIL; 705/705 independent streaming assertions; direct DoP unit 29/29 assertions; `make check` exit 0.
- Numerical phase 5/5, development benchmark 36/36.
- Paired original-P01/P02 DFF writer-path comparisons were executed on the same generated configuration. This host is not prepared and measured 7.4% control noise, above the required <2%. The paired run returned 2 (inconclusive), correctly retaining 5% acceptance as open.
- A paired small/large reader/repack benchmark script is now under `tests/dsd/bench_read_p02.py`. No writer implementation has been changed; its benchmark cannot yet qualify the 5% gate.
- P02 supplemental native reads and repacks: 88/88 commands exit 0, paired P01 large-buffer output hashes identical to P02, candidate small buffers execute. The output is unqualified timing evidence, not a formal throughput pass.
- Next: run final tests and replay; create documented handoff and complete tar; update `P00_SHA256SUMS.txt` for changed tracked sources.

Final-validation checkpoint:
- Final phase command set (autoreconf, configure, make, generic make check, make check-dsd, P02 runner, numerical entry point, development bench, direct DoP and 705-case standalone integration) all actually exited 0; logs in tests/dsd/results/P02/build/final-*.
- Baseline and candidate make check each have 73 OK/8 VOID, identical per-case classification; raw logs and generic-coverage.json in P02/build.
- Source differential: 1151 of the original regular-file members unchanged, 7 existing harness/reader files changed, zero missing, zero inherited P00/P01 evidence changes.
- New handoff: docs/dsd/handoffs/P02.md. P00_SHA256SUMS.txt regenerated with actual distributed bytes; stale two nonexistent .la artifacts removed.
- Working checkpoint 02: /mnt/data/P02-checkpoint-02.tar.gz SHA256 989876de2c238e4e191fc100407a5d1f1e9ac364c94d7ebebe36e935b975d644.
- Remaining: test clean extraction, store replay logs, finalize delivery tarball. The ONLY unqualified acceptance is controlled-host throughput (noise 7.4% > 2%; do not label pass).

Archive-extraction replay:
- Preflight archive extracted to /mnt/data/P02_work/replay/sox_ng; its SHA256SUMS manifest verified.
- Standalone autoreconf, configure, make, make check, P02 runner, measure and bench all exit 0. Two separate subsequent make check-dsd invocations complete (exit 0, 705/705 matrix and 29/29 DoP each).
- First replay check-dsd was terminated by the tool execution window after its runner and DoP pass, before the streaming matrix ended; no exit code existed. Preserve this event as uncompleted, not an engineering success/failure. Subsequent full replays pass.
- Final delivery is an original-source-manifest archive plus added test/provenance/evidence paths, never a tar of untracked generated build products.

Post-handoff audit correction (2026-10-08): work on the delivered
`sox_ng-P02-streaming-readers-2026-10-08.tar.gz` source, SHA-256
`6d64b558810c5f723a81e1b16c3fbb849d4d27149f10af2512a4de31a5a51672`.
Only `src/dsdiff.c` parser diagnostic and `tests/dsd/test_streaming.py` extent
warning assertions change in production/test code. Focused tests were proven
red against the previous binary (exactly two legacy-warning cases) and green
after the fix (19/19 extent checks). Corrected full regression gates pass:
30 PASS / 6 XFAIL / 0 FAIL; 706/706 streaming; 29 DoP; generic 73 OK / 8 VOID.
The P02 handoff addendum and evidence folder
`tests/dsd/results/P02/legacy-pad-warning/` record the correction. No writer
or hot read loop edits; native throughput qualification still requires a
controlled prepared-host run with <2% noise and a 5% regression ceiling.
