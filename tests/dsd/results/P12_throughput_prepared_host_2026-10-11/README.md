# P12 read/repack throughput gate, prepared host (2026-10-11)

**Verdict: FAIL on one workload, confirmed in both directions.**
`dff-6ch-repack-small` regresses +5.66% [+5.48%, +5.91%] at 0.41% noise.
Swapping the arms reports -5.48% [-5.60%, -5.24%], with consistent absolute
medians either way: 0.0217 s for the P11-closed binary and
0.0229 s for P12. The other fifteen workloads pass, worst +0.46%.

Baseline is the P11-closed tree against P12, both built from their own sources
in the same session with `-O2 -g`, 40 randomised AB/BA pairs after 3 warmups,
pinned to CPU 8, tmpfs, 0.0% host noise probe before each run.

## What is established

P12 changes no container read code and nothing on the read path moved. The
complete path is `dff_read` to `dff_read_fragment` to `lsx_read_b_buf` to
`lsx_readbuf` to `fread`/`memcpy`, established by disassembling each function's
call sites. Every member sits at an identical address in both builds, and
`dff_read` and `dff_read_fragment` have identical size and identical instruction
bytes. So the slowdown is not this code changing or moving.

What did change is everything after `.text`. The section starts move from
`.rodata` 0xac000 to 0xad000, `.data` 0xef480 to 0xf0480 and `.bss` 0xf45e0 to
0xf55e0, one page each, while `.text` still starts at 0x14000. Of uniquely named
symbols, 956 of 1340 text symbols moved, and **every** data, bss and rodata
symbol moved: 303 of 303 and 197 of 197.

## A second corroboration pass, and what it rules out

The first pass traced only the read side. The workload repacks, so it writes as
well, and the complete DFF path is `dff_read`, `dff_read_fragment`,
`lsx_read_b_buf`, `lsx_readbuf`, `fread` on the way in and `dff_write`,
`dff_write_buf`, `lsx_write_b_buf`, `lsx_writebuf`, `fwrite` on the way out.
**All eight project symbols on that path hold identical addresses in both
builds.**

Three workloads then discriminate between explanations:

| Workload | Path code | Result |
| --- | --- | --- |
| `dff-6ch-repack-small` | entirely held | **+5.66%, fail** |
| `dsf-6ch-repack-small` | `dsf_write` and `dsf_write_bits` moved | +0.15%, pass |
| `dff-6ch-repack-large` | identical held code | -0.01%, pass |

The format whose writer moved is unaffected, and the format whose code is
identically placed is the one that regressed. That is the opposite of what
displacement of this code would predict, so instruction-cache placement of the
path itself is not supported as the mechanism. It also only affects the small
buffer case, not the large one, on the same code.

## What is not established

We do not know the mechanism, and both explanations we offered are unsupported.
Displacement of the path is ruled out above. A one-page shift of all static data
is still possible through cache-set or 4K-aliasing effects, but DSF repack also
touches static data and did not regress, so the data story is weakened as well
without being excluded, since the two formats have different hot loops.

`docs/dsd/OPTIMIZATION_BACKLOG.md` has carried "linker layout or
instruction-cache effects are the plausible explanation" since P02. For this
phase that explanation is now contradicted for the path's own code. What remains
is a narrow, reproducible, unexplained 5.5% on one of sixteen workloads, and a
profile is what would settle it.

Two earlier claims of ours were wrong and are withdrawn. We reported that
`lsx_rawread` had moved "among the read path's callees"; it moved, but it is not
on this path at all, as `lsx_readbuf` calls `fread` and `memcpy` rather than
`lsx_rawread`. We also reported 8,489 of 8,897 text symbols moving, which came
from a join that formed a cartesian product over 16 duplicated symbol names; the
correct figure over uniquely named symbols is 956 of 1,340.

The P10 hotfix's 4096-byte alignment on the two reader entry points is intact
and held their addresses exactly, and the workload still slowed, so pinning
those two functions is not sufficient on its own.

Nothing here implicates the AVX2 kernels. This workload is DFF container read
and repack; P12's new code serves FIR and SDM and is not reached. The four new
text symbols are `accept_frame_avx2`, `fir_avx2_block`, `lsx_dsd_fir_avx2_direct`
and `sdm_avx2_block`.

Third time this workload has broken or threatened a gate, after P05-to-P06 and
the P10 ratification round. The profiling deferred since P02 is what would
replace these inferences with a measurement.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
