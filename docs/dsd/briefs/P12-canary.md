# P12 read/repack gate: fix the canary, or rule that we have it wrong

Work in the attached tree, a `git archive` snapshot with no `.git`; the dispatch
note carries its filename and SHA-256. `docs/dsd/sows/P12.md` is the statement of
work for the phase itself, which is already delivered and whose own gates pass.
This round is about one failing gate.

P12's implementation we found sound: the AVX2 tier is genuine rather than AVX1
relabelled, the no-FMA baseline holds, defaults were not promoted, and every
functional gate passes. `make check`, `make check-dsd` at 36 pass / 0 fail, the
P12 and inherited P11 suites, and forced-tier output equality all pass. The
prepared-host read/repack gate does not.

**Outcomes wanted, either one:**

1. A fix for the gate that you judge sound, or
2. A ruling that we have mis-measured or mis-apprehended this, with what you
   think is actually true.

The second is a real option and not a courtesy. Our record on this specific
workload is three mechanisms proposed and three refuted, listed below so you can
weight the fourth accordingly.

## What we measure

`dff-6ch-repack-small` regresses +5.66%, interval [+5.48%, +5.91%] at 0.41%
noise, against a 5% limit. Swapping the arms gives -5.48% with consistent
absolute medians, 0.0217 s for the P11-closed binary and 0.0229 s for P12. The
other fifteen workloads pass, worst +0.46%. We believe the measurement is sound;
the method is `tests/dsd/BENCHMARKING.md` and the host was prepared with a 0.0%
noise probe before each run.

## What we believe the cause is, and why we could be wrong

Our reading of `perf` counters on the exact failing command, five repetitions
pinned to CPU 8. It is a report to be checked, not a finding to inherit.

Instructions are identical between the two binaries to six thousandths of a
percent. Branch misses, data-cache misses, L1 instruction-cache misses and ITLB
misses are all unchanged. Cycles rise 5.50%. Decoded-uop-cache misses rise from
1,296,842 to 4,403,301, hits fall by 3.05 million, and front-end stalls rise 2.7
million cycles against a 4.6 million cycle regression. We read that as the same
work being delivered worse, in the uop cache specifically rather than in
instruction memory.

The code we think moved is `sox_flow_effects` in `src/effects.c`, the per-buffer
loop, from 0x39d30 to 0x39df0, a 192-byte shift. At `--buffer 32` it runs
millions of times per execution. Nothing on the container read or write path
moved: all eight symbols from `dff_read` through `lsx_writebuf` hold identical
addresses, and the two reader entry points are identical in size and instruction
bytes.

Giving `sox_flow_effects` 4096-byte alignment in a scratch build returns
uop-cache misses to 1,505,167, elapsed time to 0.021555 s against the
P11-closed 0.021446 s, and the gate to +0.23% [+0.03%, +0.43%] passing with all
sixteen workloads green. We did not put that change in the tree.

Where this is weak. It is one Zen 4 part and the decisive counters are
AMD-specific, so the magnitude is a property of this microarchitecture as much
as of the code. We have not shown *why* a 192-byte shift costs this much, only
that moving the function and then pinning it tracks the regression and its
recovery. And alignment is a remedy we reached by experiment rather than from
an understanding of the uop cache's allocation rules.

## Three explanations of ours that were wrong

Offered so you can discount us appropriately rather than to pad the brief.

- Instruction-cache placement of the read path, which
  `docs/dsd/OPTIMIZATION_BACKLOG.md` has carried as the plausible cause since
  P02. Excluded: that path never moved.
- `lsx_rawread` and later `lsx_rawwrite` moving "among the read path's
  callees". Both moved and neither is on the path; `lsx_readbuf` and
  `lsx_writebuf` call `fread` and `fwrite`.
- Generic image growth and one-page data displacement. Excluded by a
  dead-padding build that reproduced the section signature exactly, held the
  reader at its address, shifted all static data one page, and measured +0.25%.
  That experiment failed because unexecuted padding does not occupy uop-cache
  entries, which we only understood afterwards.

## Situational notes, possibly wrong or incomplete — trust the tree over them

- The AVX2 kernels are not implicated. This workload is DFF container read and
  repack and never reaches them; P12's new code serves FIR and SDM.
- `dff_read` and `dff_read_fragment` already carry a 4096-byte alignment
  attribute from the P10 hotfix. A second instance starts a list, and whether
  per-function pinning is the right structural answer is a question we are not
  placed to settle.
- Evidence is in `tests/dsd/results/P12_perf_diagnosis_2026-10-11/`,
  `P12_layout_experiment_2026-10-11/` and
  `P12_throughput_prepared_host_2026-10-11/`, the last containing both arm
  orders.
- Counters needed `kernel.perf_event_paranoid` lowered from 3 to 1 on the host.
  `perf` is not otherwise available to this environment.
- The gate is 5% median regression, admissible only when noise is under 2%, with
  the verdict from the confidence interval rather than the median.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, leave previously recorded evidence as
  delivered, do not ship copies of this brief in the tree, and flag anything
  here you find to be mistaken.
