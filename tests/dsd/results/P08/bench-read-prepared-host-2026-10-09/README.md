# P08 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS, measured two ways.** Every interval lies wholly inside the
design's 5% limit, with noise from 0.24% to 0.96%.

| Run | Gating | Worst workload | Regression | 95% CI |
| --- | --- | --- | --- | --- |
| auto-mode repack | 8/8 | `dff-6ch-repack-small` | **+2.59%** | [+2.39%, +2.90%] |
| legacy default paths | 16/16 | `dff-6ch-null-small` | **+2.98%** | [+2.70%, +3.59%] |

Baseline `edbe9e19` (P07) against P08, built identically, 40 randomised AB/BA
pairs per workload after 3 discarded warmups, pinned to CPU 8, tmpfs, host
prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

`bench-read-auto-mode.json` is the principal gate, the one P08's own handoff
names: `--operation repack --both-arg=--dsd-mode=auto`, since auto mode is
what the phase activates and repack is where the two arms remain comparable.
`bench-read-legacy-paths.json` is the default paths with no auto mode, included
because the phase must not disturb them either; it covers all sixteen workloads
and also passes.

## Why the delivering round could not certify this

Its handoff reports 8 of 8 statuses inconclusive, with `dff-6ch-repack-small`
at a 95% ratio interval of [0.9459, 1.1142] on 14.10% measurement noise, and
states that the interval crosses the 5% limit so the point estimate alone does
not demonstrate a pass. That is the interval rule applied correctly to refuse a
claim its +0.69% median would have supported. On a prepared host the same
workload measures +2.59% [+2.39%, +2.90%], so the conclusion is the one the
round would have reached had its host allowed it.

## Carried forward

`dff-6ch-repack-small` is again the worst workload, at +2.59% here after
+3.06% under P07, and it has needed a hotfix twice. The cumulative effect on it
from P05 through P08 is +3.20%, which is inside the gate but no longer
negligible, and the design gates each phase rather than the accumulation. A
later phase touching the small-capacity DFF read or repack path should measure
this workload specifically and watch the running total, not only its own delta.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
