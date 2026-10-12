# P12 canary: layout is not the cause (2026-10-11)

**A controlled experiment excludes image growth and data displacement as the
cause of P12's +5.66% regression on `dff-6ch-repack-small`.**

`docs/dsd/OPTIMIZATION_BACKLOG.md` has carried "linker layout or
instruction-cache effects are the plausible explanation" since P02, across five
phases and three hotfixes, always as an untested guess. It is now tested.

## Method

Two builds of the P11-closed tree, each adding dead padding: 62 non-inlined
functions reachable only through one exported symbol that nothing calls. No
behaviour changes. The only variable is where the padding lands in link order.

| Build | Padding placed | text | `dff_read_fragment` | `dff_read` | `.rodata` |
| --- | --- | --- | --- | --- | --- |
| P11 baseline | none | 619,486 | 0x70000 | 0x71000 | 0xac000 |
| padded before reader | `src/formats.c` | 623,582 | 0x71000 | 0x72000 | 0xad000 |
| padded after reader | `src/htk.c` | 623,262 | 0x70000 | 0x71000 | 0xad000 |
| **P12** | real AVX2 code | 623,198 | 0x70000 | 0x71000 | 0xad000 |

The third row reproduces P12's signature: text within 64 bytes, both reader
entry points held at identical addresses, and `.rodata`, `.data` and `.bss`
shifted one page. That is the configuration the displacement hypothesis says
should be slow.

## Result

| Workload | padded after reader | P12 |
| --- | --- | --- |
| `dff-6ch-repack-small` | **+0.25%** [-0.07%, +0.49%] | **+5.66%** |
| `dsf-6ch-repack-small` | +0.00% | +0.15% |
| `dff-6ch-repack-large` | +0.16% | -0.01% |

The padded-before-reader build, where the reader itself moved a page, also shows
nothing: +0.09% on the canary.

So an identical layout signature produced by dead code costs 0.25% while P12
costs 5.66%. Growing the image, shifting every static datum one page, and moving
or holding the reader are each insufficient. The cause is in what P12's code
does, not where the linker put it.

## What that leaves

P12's substantive changes are new AVX2 FIR and SDM kernels in
`src/dsd_kernels_avx2.c`, two `else if (ctx->fir == &lsx_dsd_kernel_avx2)`
branches in the decode stream and finish paths of `src/dsd_decode.c`, and CPUID
leaf 7 detection for AVX2 and FMA in `src/dsd_dispatch.c`. None of these is on
the DFF repack path: repacking does not reconstruct, so the decode branches
never execute, and the reader's instruction bytes are identical to P11's.

One difference our padding did not reproduce is that P12 adds data as well as
text, including the `lsx_dsd_kernel_avx2` descriptor, so the internal
arrangement of `.data` and `.bss` differs rather than merely shifting. We are
not proposing that as the mechanism. Three mechanisms have now been proposed and
three refuted, two of them by this kind of checking, and a fourth guess is worth
less than a measurement.

`perf` 6.12.111 is staged and runs, but counting is blocked by
`kernel.perf_event_paranoid=3`, which needs `sysctl -w
kernel.perf_event_paranoid=1` from root. With counters available, cycles,
instructions, and i-cache and d-cache miss rates on this one workload across the
two binaries would distinguish what remains in a single run.
