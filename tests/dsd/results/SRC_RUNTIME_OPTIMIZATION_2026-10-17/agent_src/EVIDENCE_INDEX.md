# SRC candidate exploration and review evidence

Staged on 2026-10-17. This directory preserves 29 original files (669,938 bytes), including eight small Linux ELF microbenchmark executables. Relative names, contents, modes, and timestamps were preserved; every copied file was checked against its original SHA-256. This index is the only added file. Transient dotfiles are excluded.

## Origin mapping

Original workspace prefix:

`/workspace/scratch/4dd8292178b8/agent_src/`

Repository destination prefix:

`tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/agent_src/`

For every original file, append the same relative filename to either prefix. Original source text is retained, including absolute include paths in exploratory C harnesses; copying does not make those paths relocatable. These binaries and harnesses are historical exploration evidence, not the supported final build recipe.

`FINAL_CANDIDATE_RATIONALE.md` is also copied byte-for-byte to `docs/dsd/SRC_RUNTIME_OPTIMIZATION_PROOF_2026-10-17.md`. Its SHA-256 is `a75508e3a3868c6864d492194bd5ae1ad8231f5cc85e9d5a2537ed8c8a951259`.

## Final controlling evidence

The final production change is `src/rate_poly_fir0.h`, SHA-256 `c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`, with the opt-in macro, conservative floating-point fallback, and `max_num_out > 2` threshold. No prototype header in this directory supersedes it.

The final rationale cites the separately collected real production `rate.c`/FIFO evidence whose original prefix is `/workspace/scratch/4dd8292178b8/agent_dsd/real-fifo-final/`: `metadata.json`, `timing.jsonl`, and `summary.json`. That evidence binds its executable and final production header. Its sustained paired median speedups are 1.42–1.92×. It also records final tiny-call regressions of 29.044→33.491 ns (+15.3%) and 31.510→36.416 ns (+15.6%) for 26 taps, L=80/M=147, and one/two input samples. These results control over the earlier synthetic-FIFO screens and temporary threshold experiment. The complete CLI small-buffer corpus determines the production conversion impact.

The final source-bound correctness, operator-identity, full-CLI timing, and profile records are collected separately by their owning agents. The operator comparison checks initialized stage graphs and coefficient bytes; it does not execute audio processing. None of these development-host results constitutes P15 release certification or a qualified physical-host performance receipt.

## Preserved exploratory files

| Group | Files | Interpretation |
|---|---|---|
| Final rationale and review | `FINAL_CANDIDATE_RATIONALE.md` | Final source hash, recurrence/overflow proof, operation-order contract, controlling FIFO results, and rejection rationale. |
| Initial recurrence/half-FIR screen | `micro.c`, `micro`, `micro_generic.json` | Early combined candidate screen with a minimal FIFO harness. |
| Rejected half-FIR batching | `rate_half_fir_batch2.h`, `rate_half_fir_batch4.h`, `micro_half.c`, `micro_half_O2`, `micro_half_O2.json` | Two/four-output half-band prototypes and tap-by-tap measurements; not production changes. |
| Rational recurrence and pairing | `rate_poly_fir0_recurrence.h`, `rate_poly_fir0_batch2.h`, `micro_pair.c`, `micro_pair`, `micro_pair_O2`, `micro_pair_generic.json`, `micro_pair_O2.json` | Early paired FIR microbenchmarks and exact-output screens, preceding the final guard. |
| Earlier ordered/checkpoint validation | `rate_poly_fir0_ordered.h`, `micro_pair_ordered.c`, `micro_pair_ordered`, `ordered_validation.json`, `micro_pair_final.c`, `micro_pair_final`, `final_validation.json` | Historical checkpoints. The names “ordered” and “final” do not establish the final `> 2` header identity; these small JSON files are preliminary pass summaries. |
| Tiny-call exploration | `micro_short.c`, `micro_short`, `micro_short.json`, `micro_short_guard.c`, `micro_short_guard`, `micro_short_guard.json` | Minimal-FIFO short-call comparisons without the guard and with the earlier `> 1` guard. Superseded for final performance conclusions by the real-FIFO final measurements. |

No production source or test source was changed, and no benchmark was executed during staging.
