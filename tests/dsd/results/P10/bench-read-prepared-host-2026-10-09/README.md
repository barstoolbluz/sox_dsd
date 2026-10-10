# P10 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS.** All sixteen workloads gate, zero errors, every interval
inside the design's 5% limit, noise 0.31% to 0.95%.

| | Workload | Regression | 95% CI | Noise |
| --- | --- | --- | --- | --- |
| worst | `dff-6ch-repack-small` | +1.02% | [+0.82%, +1.43%] | 0.50% |

Baseline `807ea603` (P09) against P10, built identically, 40 randomised AB/BA
pairs per workload after 3 discarded warmups, pinned to CPU 8, tmpfs, host
prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

This gate measures the read and repack paths, which P10 does not target: its
work is the PCM-to-DSD encoder. The result confirms the encoder work did not
disturb them. Note that P10's own qualification FAILED on other grounds
entirely, recorded in `docs/dsd/handoffs/P10.md` and the evidence beside it; a
passing throughput gate is not a passing phase.

The backlog canary `dff-6ch-repack-small` moves +1.02% here, taking its
cumulative movement from P05 through P10 to +0.42%. See
`docs/dsd/OPTIMIZATION_BACKLOG.md`, which records that this workload also moves
under phases touching no read code, so the running total is not wholly
attributable to deliberate work.

Its own handoff reported the gate inconclusive on host noise and declined to
claim it.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
