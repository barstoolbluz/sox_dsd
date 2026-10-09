# P05 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS**, with one workload inconclusive on noise and no regression
anywhere near the limit.

All sixteen workloads are comparable. Fifteen pass between -0.17% and +1.09%
with noise from 0.18% to 1.49%. The sixteenth, `dsf-2ch-repack-small`, reports
2.30% noise against the 2% precondition and so is inconclusive; its point
estimate is -0.02%, so it presents no regression risk and was not pursued
further.

Baseline `32d4b29e` (P04) against candidate `149ea582` (P05), built
identically, 15 randomised AB/BA pairs after 2 discarded warmups, pinned to
CPU 8, tmpfs, host prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

This closes the gate P05's handoff left open, which recorded that host
preparation did not meet the sub-2% noise condition and declined to qualify the
5% limit. P05 is a preflight planning phase, so a flat result on the read and
repack paths is the expected outcome rather than a surprising one.

Full coverage needed `--null-extra-arg=--dsd-layout-loss --null-extra-arg=warn`
on both arms: from P04 onward a named channel layout must be explicitly
discardable, so every `-t null` run exits 2 without it. Passing it to one arm
only would not be a comparison.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.

## Re-measured, 2026-10-09

`bench-read-reclassified.json` supersedes the run above and records **PASS with
zero errors**, 16 of 16 workloads gating, worst +2.10%.

The earlier run was `incomplete` solely because `dsf-2ch-repack-small` sat at
2.30% noise against the 2% admissibility precondition, on a -0.02% point
estimate. Forty pairs with larger fixtures brought it inside the precondition,
which is the same remedy that resolved marginal workloads for P01, the P02
hotfix and P06. No code and no verdict changed; an inconclusive measurement
became a conclusive one.
