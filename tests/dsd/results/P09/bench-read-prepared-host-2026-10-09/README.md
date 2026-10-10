# P09 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS.** All sixteen workloads gate, zero errors, worst +0.33%, the
flattest result of any phase so far.

| | Workload | Regression | 95% CI | Noise |
| --- | --- | --- | --- | --- |
| worst | `dsf-2ch-repack-small` | +0.33% | [-0.06%, +0.62%] | 0.90% |
| | everything else | within +-0.3% | — | 0.21% to 1.16% |

Baseline `377d840c` (P08) against P09, built identically, 40 randomised AB/BA
pairs per workload after 3 discarded warmups, pinned to CPU 8, tmpfs, host
prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

A flat result is the expected outcome rather than a pleasant surprise: P09
changes `src/sdm.c` and `src/sdm.h` only, adding an encoder profile registry
and freezing metrology, and touches no read or repack path. The value of
measuring it is to confirm that rather than assume it, and in particular to
show what happened to `dff-6ch-repack-small`. It measures
-3.69% here, with a 95% interval of
[-3.90%, -3.51%] at 0.50% noise, so it became
faster. That takes its cumulative movement from P05 through P09 to
-0.60%, where the P05-through-P08 figure was +3.20%.

Like the unexplained speedups P06 produced on untouched paths, this is not
attributed. P09 changes no read code, so linker layout or instruction-cache
effects from the altered object set are the plausible explanation, and a
speedup is not evidence of anything beyond itself.

## Why the delivering round could not certify this

Its handoff records all performance statuses as `inconclusive-noise`, with a
bootstrap ratio interval of [0.90251, 1.05363] on 12.15% measurement noise,
under a heading that reads "Performance evidence: INCONCLUSIVE, not a 5% pass",
and states that it did not infer a pass from those numbers. That is correct
practice on a host failing the 2% admissibility precondition.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
