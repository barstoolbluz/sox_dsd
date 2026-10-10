# P10 corrective read/repack throughput gate, prepared host (2026-10-10)

**Verdict: PASS.** All 16 workloads gate, 0 errors, every
interval inside the design's 5% limit, noise 0.23% to 1.20%.

| | Workload | Regression | 95% CI | Noise |
| --- | --- | --- | --- | --- |
| worst regression | `dff-6ch-null-small` | +1.00% | [+0.81%, +1.27%] | 0.49% |
| widest interval | `dsf-2ch-null-large` | +0.94% | [+0.49%, +1.43%] | 1.20% |
| canary | `dff-6ch-repack-small` | -0.15% | [-0.34%, +0.06%] | 0.34% |

Baseline `8572e029` (P10 as delivered) against the corrective/revalidation
round, built identically with `-O2 -g`, 40 randomised AB/BA pairs per
workload after 3 discarded warmups, pinned to CPU 8, tmpfs, host
prepared with `tests/dsd/benchprep.sh prepare --cpu 8`. Host noise probe
measured 0.0% spread before the run.

This round's only production change is a read-only stage observer in
`src/pcmdsd.c`, inert unless a test installs it, so no movement was expected on
these paths; the gate is recorded because earlier phases moved this matrix while
touching no read code. Output stayed bit-identical on all eight workloads that
produce output (`arms_agree`); the eight `-t null` workloads produce none.

The round's own handoff makes no encoder throughput claim and relies on the
inherited P09-to-P10 read/repack gate. This measurement supplies the corrective
round's own read/repack remeasurement, which
`tests/dsd/results/P10_corrective/qualification.json` records as not performed.
It is not a full-composite encoder benchmark and does not qualify anything:
P10 remains INCOMPLETE with all three profiles unqualified and unpromoted.

The backlog canary `dff-6ch-repack-small` moves -0.15% here. See
`docs/dsd/OPTIMIZATION_BACKLOG.md`.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
