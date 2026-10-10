# P10 ratification read/repack throughput gate, prepared host (2026-10-10)

**Verdict: FAIL, and attributable.** The ratification round's only production
change is a failure-path diagnostic in `src/pcmdsd.c`. It costs
+6.81% on `dff-6ch-repack-small`, a workload that never calls `pcmdsd`.
Reverting that one file restores the workload to -0.23%.

| Workload | As delivered | noise | status | `pcmdsd` reverted | noise | status |
| --- | --- | --- | --- | --- | --- | --- |
| `dff-6ch-repack-small` | +6.81% [+6.54%, +7.04%] | 0.41% | fail-regression | -0.23% [-0.75%, -0.05%] | 0.70% | pass |
| `dsf-6ch-repack-small` | +3.01% [+2.86%, +3.27%] | 0.47% | pass | -0.28% [-0.54%, -0.04%] | 0.55% | pass |

Baseline `8f52d842` against the ratified tree, both built from their own sources
in the same session with `-O2 -g`, 40 randomised AB/BA pairs per workload after
3 discarded warmups, pinned to CPU 8, tmpfs, host prepared with
`tests/dsd/benchprep.sh prepare --cpu 8` and a 0.0% host noise probe. The
reverted build is the delivered tree with `src/pcmdsd.c` and `src/pcmdsd.h`
replaced by their `8f52d842` versions and nothing else changed.

The gate is 5% median regression admissible below 2% measurement noise, with the
verdict taken from the confidence interval. The interval here is
[+6.54%, +7.04%] at 0.41% noise, entirely above the limit, so this is a
genuine failure and not an inconclusive measurement. In the reverted run the
overall status reads `incomplete` only because the unrelated `dsf-2ch-null-large`
workload measured 2.24% noise; `dff-6ch-repack-small` itself measured 0.70% noise.

## What this establishes

The change adds `#include <stdio.h>`, a 192-byte stack buffer, an `snprintf`
and a `strcpy` to a branch that executes only when the encoder has already
failed. It cannot run during a DFF read, and it cannot alter an output bit. The
cost is therefore not the code being executed; the plausible mechanism is that
growing this translation unit moves the DFF read loop's placement in the linked
image, changing its alignment or instruction-cache behaviour.

`docs/dsd/OPTIMIZATION_BACKLOG.md` has recorded three times that this workload
moves under phases that touch no read code, in both directions, and that nobody
had established why. This is the first causal demonstration in the project: one
file reverted, one 6.8% regression removed, everything else held constant. The
deferred profiling item is no longer optional, because it is now what stands
between a diagnostic improvement and a passing gate.

Nothing here argues against the diagnostic change itself, which is a real
improvement: the previous message invited a reader to under-attenuate. The
question a remedy has to answer is how to keep it without the layout cost, or
how to make this read path insensitive to layout. Figures are from one AMD Ryzen
Threadripper 7970X and are not a property of the code alone.
