# P02 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: FAIL.** Two comparable workloads exceed the design's 5% median
regression limit, on a host that meets the 2% noise precondition.

| Workload | Regression | 95% CI | Noise | Status |
| --- | --- | --- | --- | --- |
| `dff-2ch-null-large` | **+5.86%** | [+5.11%, +6.17%] | 0.73% | fail-regression |
| `dff-6ch-null-large` | **+6.21%** | [+5.98%, +6.52%] | 0.38% | fail-regression |
| `dff-2ch-repack-large` | +3.27% | [+2.96%, +3.38%] | 0.38% | pass |
| `dff-2ch-null-small` | +2.18% | [+1.37%, +2.90%] | 0.88% | pass |
| `dff-2ch-repack-small` | +1.64% | [+1.15%, +2.13%] | 0.64% | pass |
| `dff-6ch-repack-large` | -0.66% | [-0.81%, -0.40%] | 0.34% | pass |
| `dsf-2ch-repack-small` | -1.08% | [-1.57%, -0.07%] | 0.98% | pass |
| `dsf-2ch-repack-large` | -1.12% | [-1.72%, -0.66%] | 1.10% | pass |
| `dsf-2ch-null-large` | -2.56% | [-2.92%, -1.75%] | 1.04% | pass |
| `dsf-6ch-null-large` | -2.97% | [-3.13%, -2.63%] | 0.31% | pass |
| `dsf-6ch-repack-large` | -5.15% | [-5.31%, -4.87%] | 0.32% | pass |
| `dsf-2ch-null-small` | -1.08% | [-2.36%, +0.87%] | 2.21% | inconclusive-noise |

Baseline `99bc3366` (P01) against candidate `cce14f44` (P02), built identically,
15 randomised AB/BA pairs per workload after 2 discarded warmups, every run
pinned to one CPU with sources and outputs on tmpfs, on a host prepared with
`tests/dsd/benchprep.sh prepare --cpu 8` whose probe reported 0.0% spread.
Four workloads are excluded as not comparable, see below.

## The finding

The DFF read path costs about 6% more in P02 than in P01 when decoding with a
large buffer. Both intervals exclude the 5% limit outright, measurement noise
is under 0.8%, and the result reproduced across two independent runs: the
2-channel case measured +6.62% then +5.86%, the 6-channel case +6.10% then
+6.21%.

Two details make the number credible rather than incidental. The cost is
specific to DFF: every DSF workload is unchanged or faster, as far as -5.15%.
And it dilutes exactly as it should when other work is added - `-t null`
isolates the reader and shows +5.9%, while the same source repacked to a DFF
output shows +3.3%, because the writing shares the total.

This is a cost of correctness, not necessarily a defect to revert. P02 repaired
readers that previously failed to progress on small capacities, and the
retained-bit state machine that fixes them is what the gate is now charging
for. The gate is nevertheless failed as specified, and the design does not
permit relaxing it.

## Why four workloads do not gate

The design gates "no more than 5% median regression on **unchanged** native
repacking or legacy paths". `dff-6ch-repack-small` and `dsf-6ch-repack-small`
produce **different output bytes** under P02 than under P01, because that is
precisely the small-capacity defect P02 repaired. Their measured +134% and
+135% are not slowdowns; the two binaries are doing different amounts of work,
and a ratio between them is not a regression. Their `-t null` counterparts
inherit the exclusion: a null run leaves no artifact, so equivalence cannot be
demonstrated directly and is inferred from the repack workload on the same
source and buffer.

## Harness history

The earlier `tests/dsd/bench_read_p02.py` could not produce this verdict. It
hardcoded `host_unqualified: True`, did not pin, and wrote to `/tmp`, which
left per-workload noise at 13-25%. P02's and P03's handoffs therefore recorded
their throughput gates as open rather than claim a result. The harness now
pins, uses tmpfs, requires at least 15 pairs with warmups, measures
admissibility instead of assuming it, and classifies workloads whose behavior
the phase changed as not comparable.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
