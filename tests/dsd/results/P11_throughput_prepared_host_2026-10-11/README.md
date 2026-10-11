# P11 read/repack throughput gate, prepared host (2026-10-11)

**Verdict: PASS.** All 16 workloads gate with 0 errors. Worst
regression is `dsf-2ch-null-large` at +0.31%; the backlog canary
`dff-6ch-repack-small` measures -2.87% [-3.19%, -2.73%] at
0.41% noise. Worst noise across the matrix is 0.79%.

Baseline is the certified P10 tree against P11, both built from their own
sources in the same session with `-O2 -g`, 40 randomised AB/BA pairs per
workload after 3 discarded warmups, pinned to CPU 8, tmpfs, with a 0.0%
host noise probe beforehand.

This result is worth recording because the phase was expected to disturb it.
P11 adds five translation units and two per-tier convenience libraries, which
changes object sizes and link order, and `docs/dsd/OPTIMIZATION_BACKLOG.md`
documents this workload moving by several percent under exactly that kind of
unrelated change. It did not regress here. The 4096-byte function alignment the
P10 hotfix gave `dff_read` and `dff_read_fragment` is the plausible reason, and
this is the first phase since that fix to add translation units, so it is also
the first evidence that the alignment holds under real churn rather than under a
synthetic perturbation.

Read and repack are not what P11 changes. Its kernels serve the FIR decode and
SDM paths, so this gate tests that the new units did not disturb the container
read path, not that the kernels are fast. Per-tier and end-to-end kernel timings
are the phase's own benchmarks under `tests/dsd/results/P11/`.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
