# P07 continuation checkpoint, 2026-10-09

Work was resumed in the original extracted source directory at `<WORKTREE>`. The isolated P06 hotfix exists separately in `sox_ng-P06-hotfix-isolated-checkpoint.tar.gz` and must not be benchmarked against P07. P05 `149ea582` source is unavailable in this turn. Prior timing measurements on this host are high-noise and do not certify the prepared-host gate.

P07 implementation at this checkpoint: a private `rate.c` double SRC, public per-channel DSD decoder, explicit `dsdpcm`, private fatal propagation through effects and CLI, CLI count/rate planning, and P07 numerical/API/integration tests.

Observed prior tests: `make check` exit 0; `make check-dsd` exit 0 after full run; private P07 C tests 170499 assertions / 0 failures; P07 CLI matrix 66 / 0 failures; P07 independent rational SRC reference 6 comparisons; P07 composite reference 8 comparisons; `measure.py --phase P07` 7 pass / 0 fail; explicit performance benchmark completed but lacked matched bandwidth controls. All prior results should be reproduced after final changes, not interpreted as a certified 5% gate. Numerical 48k-family comparisons include separate, measured edge tolerance, not P06 one-LSB bound.

Need finish: audit/fix semantic bugs, run phase harness against final code, remove machine-local paths in only newly collected evidence, write final hotfix and P07 handoffs, regenerate P00_SHA256SUMS, create source-only archive. No final handoff approval until this is done.
