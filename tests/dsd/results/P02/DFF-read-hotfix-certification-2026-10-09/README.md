# P02 DFF read hotfix: certification on a prepared host (2026-10-09)

**Verdict: PASS.** The regression recorded in
`../bench-read-prepared-host-2026-10-09/` is recovered, and the design's 5%
gate is met with every workload admissible under the 2% noise precondition.

| Workload | Original P02 | With the hotfix | 95% CI | Noise |
| --- | --- | --- | --- | --- |
| `dff-2ch-null-large` | **+5.86% fail** | **+2.95%** | [+2.33%, +3.22%] | 1.07% |
| `dff-6ch-null-large` | **+6.21% fail** | **-3.32%** | [-3.52%, -3.13%] | 0.24% |

All twelve comparable workloads pass, noise 0.24% to 1.42%, zero errors. The
six workloads required to stay byte-identical did so: the hotfix added a
`REQUIRED_COMPARABLE_REPACK` guard to `bench_read_p02.py` that raises a hard
error if any of them stops being comparable, so their survival is asserted
rather than assumed. Four six-channel small-capacity workloads remain excluded,
as they were before, because P02 deliberately decodes them differently.

## Why this measurement and not the hotfix's own

The hotfix handoff reported its gate as `INCONCLUSIVE, not accepted`: its host
measured a 25.6% probe spread on CPU 1, 3.0% at best elsewhere, and being
virtualized it lacked the governor, boost and SMT controls
`tests/dsd/BENCHMARKING.md` requires. It declined to read its own +4.93% as a
pass, noting the noise was nearly four times the threshold, and specified what
would certify it instead. This is that run.

Comparing P01 directly against the current tree does not work, and the handoff
says so. A first attempt here produced 136 failures of the form `destination
'null' cannot carry named channel identity`, which is P04's layout-loss policy
correctly refusing a destination P01 accepted, plus three output differences
from P03 and P04 writer changes. None of that is the hotfix.

The control is therefore P02 at `cce14f44` with **only** the two reader
functions spliced in, `dff_read` and the new `dff_read_fragment`, matching the
isolation the handoff prescribes. That control passes P02's own gate at 30 pass
/ 6 xfail / 0 fail, identical to unpatched P02, so the patch preserves the
phase's correctness.

Baseline is P01 at `99bc3366`. 15 randomised AB/BA pairs per workload after 2
discarded warmups, pinned to CPU 8, tmpfs, on a host prepared with
`tests/dsd/benchprep.sh prepare --cpu 8` whose probe reported 0.0% spread.

`bench-read.json` is the accepted run, at 524288-frame small and 2097152-frame
large fixtures. `bench-read-shorter-runs.json` is an earlier run at the default
sizes, retained because it reached the same conclusion and shows the one
difference: `dsf-2ch-repack-small` measured 2.33% noise there, marginally over
the precondition, which lengthening the runs resolved. Both are kept rather
than the successful one alone.

## What the fix was

The cost was per-cluster retained-state bookkeeping in the read hot loop,
introduced when P02 made the readers streaming state machines. The hotfix
splits an aligned eight-frame fast path, which needs no such bookkeeping and
expands in the same order as P01's reader, from `dff_read_fragment` which
retains state only for partial clusters arising from small reads and
non-byte-aligned seeks. P02's correctness lives in the fragment path; P01's
throughput returns on the aligned path.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
