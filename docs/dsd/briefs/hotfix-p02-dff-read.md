# Hotfix round: recover the P02 DFF read regression

Work in the attached tree, `sox_ng-hotfix-149ea582.tar.gz`, SHA-256
`e99eb6a2e88613e1ba14654ef046d4a5ce6ca4beb3aeeccbee737cce1cdbf2d0`, no `.git`.
It contains P00 through P05 accepted. `docs/dsd/DSD_DESIGN.md` and
`docs/dsd/IMPLEMENTATION_PLAN.md` remain the authority. This is a corrective
round, not P06.

P02's throughput gate now has a measured verdict and it **fails**. The DFF read
path costs about 6% more than P01 with a large buffer:

```
dff-2ch-null-large  +5.86%  95% CI [+5.11%, +6.17%]  noise 0.73%
dff-6ch-null-large  +6.21%  95% CI [+5.98%, +6.52%]  noise 0.38%
```

Both intervals exclude the design's 5% limit, and it reproduced across two
independent runs. The cost is DFF-specific: every DSF workload is unchanged or
faster, by as much as 5.15%. It dilutes as expected when writing is added,
+5.9% decoding to null against +3.3% repacking the same source, which points at
the reader rather than the writer.

**Outcome wanted:** the DFF read path comes back inside the 5% gate with no loss
of the correctness P02 established — the small-capacity repairs stay repaired,
`run.py --phase P05` stays at 36 pass / 0 fail, and `make check` stays clean. If
the cost turns out to be irreducible, say so with evidence and propose the
deviation the design would require, rather than relaxing the threshold.

Decoded output must stay byte-identical to the attached tree on every workload
that currently agrees between the arms. Be aware that our own harness will not
catch you if it does not: a workload whose two arms stop agreeing is
reclassified `not-comparable` and drops out of the gating set, so recovering the
5% by changing what is decoded would read as a pass without being one. The six
workloads that currently agree are `dff-2ch-repack-large`,
`dff-2ch-repack-small`, `dff-6ch-repack-large`, `dsf-2ch-repack-large`,
`dsf-2ch-repack-small` and `dsf-6ch-repack-large`.

Evidence, method and host preparation are already in the tree:
`tests/dsd/results/P02/bench-read-prepared-host-2026-10-09/`,
`tests/dsd/BENCHMARKING.md`, and `tests/dsd/benchprep.sh`. Reproduce with
`tests/dsd/bench_read_p02.py --baseline-sox <P01 build> --cpu N` on a prepared
host.

Return a complete source tree with a handoff describing what you changed and
the re-measured gate.

Situational notes, possibly wrong or incomplete — trust the tree over them:

- `dff-6ch-repack-large` sits at -0.66%, so the DFF path is not inherently
  slower under P02. That is our reason for thinking the null-decode cost is
  recoverable, but it is an inference, not a measurement of the cause.
- We did not attribute the cost. Profiling would settle it; reading the diff did
  not.
- Two workloads, `dff-6ch-repack-small` and `dsf-6ch-repack-small`, are excluded
  from the gate because P02 deliberately decodes them differently. Their +134%
  figures are different work, not slowdowns. Do not optimise toward making
  those numbers smaller.
- The gate is 5% median regression, admissible only when measurement noise is
  under 2%. Two different numbers; an inadmissible measurement is inconclusive,
  never a pass.
- Please return a source tree rather than a built one, and keep
  machine-specific paths out of recorded results.
- Please leave previously recorded evidence as delivered, and flag anything here
  you find to be mistaken.
