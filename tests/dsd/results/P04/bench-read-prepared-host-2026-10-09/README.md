# P04 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS on the comparable paths**, worst case +0.70%, nothing
inconclusive.

Four workloads gate, all four pass, between -0.02% and +0.70% with noise from
0.36% to 1.01%:

| Workload | Regression | Noise |
| --- | --- | --- |
| `dff-6ch-repack-large` | -0.02% | 0.36% |
| `dff-6ch-repack-small` | +0.24% | 1.01% |
| `dsf-2ch-repack-large` | +0.55% | 0.65% |
| `dsf-2ch-repack-small` | +0.70% | 0.57% |

Baseline `21ac0e78` (P03) against candidate `32d4b29e` (P04), built
identically, 15 randomised AB/BA pairs after 2 discarded warmups, pinned to
CPU 8, tmpfs, host prepared with `tests/dsd/benchprep.sh prepare --cpu 8`.

## Why coverage is narrower here than for P05 and P06

This boundary admits fewer comparable workloads than any other, for two
reasons that are properties of the phase rather than of the measurement.

P04 introduced the layout-loss policy, so from P04 onward a `-t null`
destination refuses a named channel layout unless `--dsd-layout-loss warn` is
given. P03 does not accept that option at all, so the eight `-t null`
workloads cannot be run symmetrically across this boundary and are excluded;
the recorded errors are those runs exiting 2 under the candidate, which is the
designed behavior and not a failure.

P04 also writes channel identity into DFF headers, so four of the eight repack
workloads produce different output bytes under the candidate. The design gates
unchanged paths, so those four are excluded as not comparable rather than
counted as regressions.

This closes the gate P04's handoff left open, which measured 4.6% probe spread
on an unprepared host against the 2% precondition and declined to state a
percentage.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.

## Reclassified, 2026-10-09

`bench-read-reclassified.json` supersedes the run above. It records
**PASS with zero errors**, worst +0.31%, after two harness corrections that
changed only how this boundary is reported, not what it measures.

| Class | Count | Why |
| --- | --- | --- |
| gating | 4 | all pass, -0.38% to +0.31% |
| unavailable | 8 | no `-t null` invocation both binaries accept |
| not comparable | 4 | P04 deliberately changes these outputs |

The original run recorded `failed` with 139 errors, for two reasons that were
both bookkeeping. The eight `-t null` workloads cannot run symmetrically here:
P03 rejects `--dsd-layout-loss` as an invalid option while P04 requires it, so
the harness now probes both binaries, picks the invocation they share, and
records these as unavailable with that reason rather than as errors. And the
six workloads pinned byte-identical for the P01-to-P02 hotfix comparison were
being asserted on every boundary, so three of them were reported as violations
when P04 legitimately writes channel identity into DFF headers; that assertion
is now opt-in via `--require-comparable-preset p01p02`.

Neither correction touched a measurement. The four comparable workloads passed
in the original run too, at worst +0.70% on shorter fixtures.
