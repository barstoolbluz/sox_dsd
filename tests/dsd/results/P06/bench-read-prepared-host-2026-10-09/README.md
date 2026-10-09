# P06 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: FAIL.** One workload regresses beyond the design's 5% limit with its
whole confidence interval above the threshold, on a host meeting the 2% noise
precondition.

| Workload | Regression | 95% CI | Noise | Status |
| --- | --- | --- | --- | --- |
| `dff-6ch-repack-small` | **+5.65%** | [+5.50%, +5.89%] | 0.43% | fail-regression |
| `dff-6ch-null-small` | +1.26% | [+0.91%, +1.58%] | 0.67% | pass |
| `dsf-*` (all eight) | -0.02% to +0.10% | within +-0.5% | 0.18-0.68% | pass |
| `dff-6ch-repack-large` | -5.62% | [-5.94%, -5.27%] | 0.48% | pass |
| `dff-6ch-null-large` | -11.12% | [-11.26%, -10.91%] | 0.27% | pass |

Baseline `149ea582` (P05) against candidate `d6c8b5e6` (P06), built
identically, 40 randomised AB/BA pairs per workload after 3 discarded warmups,
pinned to CPU 8, tmpfs, on a host prepared with
`tests/dsd/benchprep.sh prepare --cpu 8`. `bench-read.json` is the 15-pair run
at 4x fixtures; `bench-read-40-pairs.json` is the accepted 40-pair run.

## Why this needed three attempts

The finding only appeared as the measurement improved, which is how a real
per-sample cost behaves when short runs dilute it:

| Measurement | Result |
| --- | --- |
| 15 pairs, default fixtures | +3.28%, CI to +5.28%, 2.60% noise, inconclusive |
| 15 pairs, 4x fixtures | +4.98%, CI to +5.83%, 0.73% noise |
| 40 pairs, 8x small fixtures | **+5.65%, CI [+5.50%, +5.89%], 0.43% noise** |

The middle row is the one to learn from. Its point estimate sat inside 5%, so
the harness called it a pass while its interval crossed the limit.
`tests/dsd/BENCHMARKING.md` already said an interval straddling the threshold
is inconclusive, but the harness compared only the median. That is fixed: the
verdict is now taken from the interval, with a distinct
`inconclusive-interval` status, so a comfortable median can no longer stand in
for a conclusion. Without that fix P06 would have been recorded as a clean
pass on a measurement its own written procedure calls inconclusive.

## Unexplained, and recorded as such

`dff-6ch-null-large` is 11.12% faster and `dff-6ch-repack-large` 5.62% faster
under P06, which adds decode code and profile descriptors that should not touch
the read path at all. Linker layout or instruction-cache effects from the new
object files are more plausible than real improvement. Faster does not threaten
the gate, so no claim is made that P06 made reading faster. The slowdown and
the speedups are both unattributed; profiling would settle them, reading the
diff did not.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
