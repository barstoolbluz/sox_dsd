# Build and validation evidence

This directory retains byte-for-byte copies of the original workspace evidence. The copied JSON records retain their original absolute paths; they were not rewritten. The original workspace prefix was `/workspace/scratch/4dd8292178b8/`. Replace that prefix with this evidence directory for paths in the table below.

| Original suffix | Staged relative directory | Copied files | Bytes |
|---|---|---:|---:|
| `agent_build/` | `agent_build/` | 331 | 3,635,408 |
| `build-baseline/` | `build-baseline/` | 10 | 14,365,296 |
| `build-candidate/` | `build-candidate/` | 14 | 8,268,318 |
| `build-default-off/` | `build-default-off/` | 2 | 3,567,695 |
| `build-sanitize/` | `build-sanitize/` | 7 | 14,894,990 |
| `build-candidate-guard1/` | `build-candidate-guard1/` | 13 | 8,258,253 |
| `build-default-off-guard1/` | `build-default-off-guard1/` | 2 | 3,567,581 |
| `build-sanitize-guard1/` | `build-sanitize-guard1/` | 7 | 40,206,428 |

The production repository prefix `/workspace/scratch/4dd8292178b8/sox_ng/` maps to the repository containing this directory. Production sources and the new test/build helpers are retained in that repository, rather than duplicated here. [STAGED_MANIFEST.json](agent_build/STAGED_MANIFEST.json) records each copied file's original path, staged path, size and SHA256. Its totals exclude the manifest and this index.

## Final results and source binding

- [Final build and validation summary](agent_build/final-build-validation-summary.json) binds the final `max_num_out > 2` candidate to header SHA256 `c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591` and CLI SHA256 `750ea8d25c563ee5f12ebb587b4613f8669c441a3f7b8c8057ef92ce76774f42`.
- [Exact SRC result](agent_build/candidate-guard2-exact-src.json): 768,060 checks and 5,409,850 exact sample words, including four rounding modes.
- [ASan/UBSan result](agent_build/asan-ubsan-guard2-exact-src.json): the same regression passed with all 216 library objects instrumented. Leak detection was unavailable in the sandbox and is recorded as UNRUN; the diagnostic is retained.
- [Existing focused suites](agent_build/candidate-guard2-validation/summary.json): all 16 suite invocations passed.
- [Generic conversions](agent_build/candidate-guard2-generic-summary.json): 148 checks passed; unavailable optional formats are explicitly skipped. The sample conversion macro test also returned zero.
- [Default-off emitted-code identity](agent_build/default-off-evidence/summary-guard2.json): both the rate object and complete CLI `.text` match the frozen baseline byte-for-byte.

The final candidate and sanitizer [dependency rebuild receipts](build-candidate/guard2-dependency-rebuild.json) and [sanitizer receipt](build-sanitize/guard2-dependency-rebuild.json) record the commands used after the guard adjustment. The original baseline build predates the helper's `build-inputs.json` feature, and that file was not invented. The default-off controls replace only the rate object within a baseline library; their records state that scope.

## Intentionally retained executables

| Staged directory | Executables retained |
|---|---|
| `build-baseline/` | Measured `sox_ng`; `sox_dsd_profile_cli_instrumented`; `sox_dsd_profile_linkonly`; current `sox_dsd_profile` alias; `sox_sample_test` |
| `build-candidate/` | Final measured `sox_ng`; exact regression and stage-export probes under `test/`; `sox_sample_test` |
| `build-default-off/` | Final default-off `sox_ng` for the emitted-code control |
| `build-sanitize/` | Final exact regression probe under `test/` |
| `build-candidate-guard1/` | Preserved guard1 `sox_ng`, exact regression and stage-export probes, and sample test |
| `build-default-off-guard1/` | Preserved guard1 default-off `sox_ng` |
| `build-sanitize-guard1/` | Preserved guard1 sanitized `sox_ng` and exact regression probe |

The two baseline profiler variants are distinct: the earlier variant instruments only `src/sox_ng.c`, while the corrected variant applies `-pg` at link time with uninstrumented CLI and DSP objects. The current `sox_dsd_profile` alias has the corrected link-only bytes. The baseline build record explicitly maps earlier profiler measurements to the preserved `sox_dsd_profile_cli_instrumented` binary.

Guard1 build records retain the paths they used when generated. Resolve historical guard1 references inside the corresponding `build-*-guard1/` copy; their old header hash and binary hashes distinguish them from the final candidate. [The preserved guard1 summary](agent_build/guard1-build-validation-summary.json) and earlier logs remain intact. The 24-conversion default-off output replay belongs to guard1; final guard2 evidence establishes emitted-code identity.

Objects, complete archives, generated audio fixtures and scratch compilation intermediates were omitted. The new reusable build helper is `tools/build_src_optimization.py` in the repository; the exact original helper and dependency/validation scripts are also retained under `agent_build/`. This evidence describes local correctness and build reproducibility; it does not constitute physical-host performance qualification or P15 certification.
