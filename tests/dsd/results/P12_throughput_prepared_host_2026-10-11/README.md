# P12 read/repack throughput gate, prepared host (2026-10-11)

**Verdict: FAIL on one workload.** `dff-6ch-repack-small` regresses
+5.66%, interval [+5.48%, +5.91%] at 0.41% noise, entirely above the
5% limit, so a genuine failure rather than an inconclusive measurement. The
other 15 workloads pass; worst among them is dsf-2ch-repack-large at
+0.46%. Worst noise across the matrix 0.94%.

Baseline is the P11-closed tree against P12, both built from their own sources
in the same session with `-O2 -g`, 40 randomised AB/BA pairs after 3 warmups,
pinned to CPU 8, tmpfs, 0.0% host noise probe beforehand.

## This is the backlog canary again, and the alignment fix did not hold

P12 changes no container read code. `src/dsdiff.c` is not in its diff, and in the
linked image the read path's own functions sit at **identical addresses** in both
builds: `dff_read_fragment` at 0x70000 and `dff_read` at 0x71000, both still
page-aligned, with the P10 hotfix attribute intact. The regression is therefore
not this code moving.

What did move is almost everything else. Text grew 619,486 to 623,198 bytes, a
0.6% increase from the new AVX2 translation unit and its convenience library,
and **8,489 of 8,897 text symbols changed address**. Among the read path's
callees, `lsx_read_b_buf` and `lsx_readbuf` happen to sit before the insertion
point and did not move, but `lsx_rawread` moved from 0x90a20 to 0x915e0.

Our reading, which is an inference from address comparison and not a profile: the
P10 hotfix pinned the two functions it names, and that is not sufficient, because
the deeper callees on the same path are still free to move and change their cache
set mapping relative to the pinned code. This is consistent with the perturbation
test recorded in
`tests/dsd/results/P11_throughput_prepared_host_2026-10-11/`, where growing an
unrelated object moved this workload 2.70% while both named functions stayed
aligned.

Nothing here suggests a defect in the AVX2 kernels. They are not on this path at
all: this workload is DFF container read and repack, and P12's new code serves
FIR and SDM. The phase's own per-tier and end-to-end kernel benchmarks are under
`tests/dsd/results/P12/`.

Third time this workload has broken or threatened a gate, after P05-to-P06 and
the P10 ratification round. `docs/dsd/OPTIMIZATION_BACKLOG.md` has deferred the
profiling that would settle it since P02.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
