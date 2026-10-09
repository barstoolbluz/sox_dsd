# P07 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS.** All sixteen workloads gate, zero errors, every interval
inside the design's 5% limit.

| Workload | Regression | 95% CI | Noise |
| --- | --- | --- | --- |
| `dff-6ch-repack-small` | +3.06% | [+2.79%, +3.54%] | 0.63% |
| all others | within +-1% | — | 0.37% to 1.41% |

Baseline is P06 plus its read hotfix, the isolated control described in
`../../P06/hotfix-certification-2026-10-09/`, against the full P07 tree. 40
randomised AB/BA pairs per workload after 3 discarded warmups, pinned to CPU 8,
tmpfs, host prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

## Worth carrying forward

P07's cost falls on `dff-6ch-repack-small`, the same workload the P06 hotfix had
just recovered from +5.65% to -2.39%. At +3.06% it passes with its whole
interval below the limit, and the cumulative effect from P05 through P07 on that
workload is about +0.6%, so nothing is accumulating unseen.

That path has now needed attention twice, under P02 and under P06, and takes
the largest single-phase cost here. A later phase touching the small-capacity
DFF read or repack path should measure this workload specifically rather than
rely on an aggregate.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
