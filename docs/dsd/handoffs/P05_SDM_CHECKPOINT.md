# P05 SDM normalization corrective checkpoint

**State:** IMPLEMENTED AND FUNCTIONALLY VERIFIED, October 9, 2026. The full source-only delivery is the authoritative resumption state; no prior local working directory, `.git` history or machine-specific build product is required.

## Provenance and authority

- Input: `sox_ng-P05-corrected-2026-10-09.tar.gz`, SHA-256 `b770c16083a74cc31512dbcca1665a3ce26bc1ffe48ef7407e7dac6f183fef45`.
- Authority: `docs/dsd/sows/P05.md`, sections 5.2-5.4 of `docs/dsd/DSD_DESIGN.md`, and `docs/dsd/IMPLEMENTATION_PLAN.md` P05.
- Corrected issue: `--norm` followed by low-level `sdm` previously planned PCM normalization before modulation but executed automatic gain after modulation. New opt-in preflight preserves the correct plan and marks this specific effects-ordering mismatch nonexecutable. This is an execution-placement limitation, not missing low-level SDM DSP.

## Changed source and tests

- `src/dsd_plan.c`: small preflight-only guard for normalization ahead of SDM without an earlier explicit dither boundary. The unavailable reason identifies the present effects-pipeline ordering limitation. Both default behavior and runnable ordinary SDM/dither paths are unchanged.
- `tests/dsd/test_plan.py`: eight new regression cases, 155 total. Existing C planner checks remain 168 assertions.
- `tests/dsd/results/P05/sdm_normalization/{plan.json,nonzero_smoke.json}`: independently executed plan matrix and nonzero-signal reproduction/control evidence, with file paths normalized.
- `docs/dsd/handoffs/P05.md`: new final corrective addendum; earlier handoff retained as historical evidence.
- This checkpoint and updated P05 source inventory. P00 evidence and prior P05 evidence remain unchanged.

## Verified gates

- Fresh configured static build: `autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`, `make -j2`: all exit 0, zero compiler warnings.
- `make check`: exit 0, eight inherited VOID cases remain unrun.
- `make check-dsd`: exit 0, 168/168 P05 unit assertions and 155/155 CLI tests.
- Independent `tests/dsd/run.py --phase P05`: 36 PASS, zero XFAIL, XPASS, FAIL or SKIP.
- `tests/dsd/measure.py --phase P05`: 5 PASS, 0 FAIL; later DSP qualifications still unrun.
- `tests/dsd/bench.py --phase P05`: 36/36 development workloads, not a controlled regression certification.
- `tests/dsd/bench_plan.py`: 44/44 neutral-directory startup/RSS measurements.
- Eight nonzero-signal smoke checks: normalized SDM plan valid but nonexecutable; execution with and without `-D` exits 2 and creates no output; plain SDM, normalized `dither -p 1` and `dither -p 16` before SDM remain executable.

## Known limitation and continuation

The required less-than-2%-noise controlled-host 5% throughput regression gate remains INCOMPLETE, independently of this P05 defect. No new composite reconstruction, modulation or rate-changing DSP is implemented here. Run independent acceptance on the **delivered archive bytes**. If accepted, P06 is the next permitted implementation phase; do not expand this P05 correction beyond the evidenced ordering defect.
