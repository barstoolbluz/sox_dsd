# P11 resumable checkpoint, 2026-10-11

Root: this `sox_ng` source tree, extracted from the user-provided no-git
`sox_ng-P11-cb8eb48d.tar.gz`. Input archive SHA-256:
`2acce5b455aaaf9bd6aedf5082e4490f6af87f593a1cac3d6da114d4f729075f`.

## Source implementation

- `src/dsd_dispatch.c`, `src/dsd_kernels.h`: baseline-ISA CPUID/OSXSAVE/XCR0
  gating, family-independent force hooks and per-context selection.
- `src/dsd_kernels_scalar.c`, `_sse2.c`, `_avx1.c`: scalar reference,
  SSE2 and actual AVX1-only compiled FIR and guarded normal SDM block kernels.
  No AVX2/FMA instructions in the AVX1 object; both SIMD libraries use
  `-fno-lto`, while scalar/dispatch code stays baseline ISA.
- `src/sdm_normal_commit_i.h`, `src/sdm.c`, `src/pcmdsd.c`: shared normal SDM
  monitor/guard commit, scalar recurrence preserved, context-owned SDM
  kernel chosen once per creation.
- `src/dsd_decode.c`: hot-path scalar/SSE2/AVX1 streaming FIR specialization,
  checked context dispatch, independent channel state and scalar tails.
- `configure.ac`, `src/Makefile.am`, `test/Makefile.am`, root `Makefile.am`:
  isolated compilation and phase target wiring.

## Executed receipts and current results

- `autoreconf -fi`, configure `CFLAGS='-O2 -g'`, `make -j4`: all exit 0.
- `make check`: exit 0.
- `make check-dsd`: exit 0, after one harness timeout during the earlier P07
  suite. The interrupted log is retained separately; no test failure occurred.
- `run.py --phase P11`: 36 pass, zero fail/xfail/skip.
- `measure.py --phase P11`: exit 0.
- `bench.py --phase P11`: exit 0 (development-only inherited benchmark).
- `test_p11` unit: scalar, SSE2 and AVX1 pass.
- `test_p11_numeric.py`: analysis-v1 passes DSD64/128/256, both SIMD tiers.
- `test_p11_integration.py`: 28 real forced-ISA CLI cases and clean failure
  of unsupported hooks, plus buffer/thread byte invariance.
- `test_p11_p10_regression.py`: six bit-identical mastering output cases
  compared against the independently rebuilt, original P10 candidate.
- `check_p11_isa.py`: baseline/SSE2/AVX1 instruction isolation checks pass.
- `bench_p11.py`: 15 independent measurements per FIR mode / SDM tier;
  source and host identity recorded. `bench_p11_e2e.py`: 15 measurements per
  CLI family and ISA tier; no portable preference claim.

Receipt directories: `tests/dsd/results/P11/{build,bench,integration,isa,numeric}`.
Run `make -C test dsd_test_p11` before `test_p11_numeric.py`, and build the
uninstalled P10 candidate for full-graph encoding jobs.

The P10 verifier succeeds against the untouched input source and intentionally
fails against the new P11 code hashes, because P10 certified its original
scalar code. The stored certificate stays byte-for-byte unchanged; the P11
handoff explains this historical/source distinction.

## Unrun qualification

No physical AVX1-only machine or AVX-without-AVX2 emulation environment has
been executed. AVX1 object instructions were audited and AVX1 was executed
on this host with AVX2 also present. This does not fulfill the independent
AVX1-without-AVX2 hardware gate; carry that named unrun gate forward.

## Continue and deliver

1. Rerun `autoreconf -fi`, `./configure --disable-shared --without-libltdl
   CFLAGS='-O2 -g'`, `make`, `make check` and `make check-dsd` after any changes.
2. Preserve P00-P10 receipts and source-only P10 certificate. Keep failed
   setup/test receipts as historical records, not production defects.
3. Return a complete source-only archive (never include `.git` or built
   executables/objects), a hash manifest and `docs/dsd/handoffs/P11.md`.
