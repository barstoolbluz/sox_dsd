# P13 read/repack throughput gate, prepared host (2026-10-12)

**Verdict: PASS.** All 16 workloads gate with 0 errors. Worst
regression is `dff-2ch-null-small` at +0.26%; the backlog canary
`dff-6ch-repack-small` measures +0.07% [-0.12%, +0.36%] at 0.55% noise.
Worst noise across the matrix 0.76%.

Baseline is the P12-corrected tree against P13, both built from their own
sources with `-O2 -g`, 40 randomised AB/BA pairs after 3 warmups, pinned to
CPU 8, tmpfs, 0.0% host noise probe beforehand.

## The P12 remedy generalised

This is the first phase to add a translation unit since the P12 canary fix, and
it is the test of whether that fix survives later churn rather than only the
link it was tuned against. Every hot function holds its address between the two
builds: `sox_flow_effects` at 0x3b000, `dff_read` at 0x72000,
`dff_read_fragment` at 0x71000, `dff_write` at 0x72fb0, `lsx_read_b_buf` at
0x27140 and `lsx_readbuf` at 0x264e0. The 4096-byte alignment absorbed P13's
growth, the canary moved +0.07%, and nothing needed re-diagnosing.

That is the intended behaviour of the remedy rather than a new finding, but it
was not guaranteed: had P13's growth displaced a *different* hot function, the
same investigation would have reopened on a new symbol. It did not.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
