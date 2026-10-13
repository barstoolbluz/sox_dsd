# P15 physical older-AVX throughput, and a cross-host scalar question

Addresses `P15-physical-older-AVX-performance`, whose delivered evidence note
read "P11 AVX1-only QEMU confirms instruction compatibility, not physical
throughput". Run by the operator on physical AVX1-without-AVX2 silicon.

Two runs: one before host preparation and one after. The script judged the
second `gate_relevant=yes` on its own criteria — governor `performance`,
`intel_pstate/no_turbo` 1, clock verified flat.

## Correctness, which does not depend on preparation

Within-host forced-tier split is the criterion and it passes: **one FIR hash
across scalar, sse2 and avx1; two SDM hashes**, scalar separate from the vector
pair. That is the same invariant verified on AMD Zen 4 and on Intel Sapphire
Rapids, now on a third microarchitecture.

## Throughput, gate-relevant

Clock verified flat at 3000 MHz in all three arms, 206 to 221 busy samples
each, spread across tiers **0.00%**. So no older-AVX downclock on this part,
and the tier comparison is not contaminated by frequency.

Median CPU ns per frame, 15 repetitions, pinned:

| family | scalar | sse2 | avx1 | sse2 gain | avx1 gain |
|---|---|---|---|---|---|
| `fir-single` | 86.16 | 51.89 | 35.06 | 1.660x | **2.458x** |
| `fir-block` | 85.54 | 67.88 | 66.34 | 1.260x | **1.289x** |
| `sdm` | 48.20 | 43.43 | 44.40 | 1.110x | 1.086x |

## The unprepared run is an independent cross-check

The operator noted that disabling boost dropped every core from about 4000 MHz
to a flat 3000 MHz on this board, so the earlier unprepared run is the same
measurement at a 4/3 higher clock. Comparing the two:

- Every one of the nine absolute figures scales by **1.331 to 1.371** against a
  clock ratio of **1.3333**. Eight of nine agree within 0.3%.
- Scalar-relative ISA gains are unchanged between the two clocks, within 0.5%
  except `avx1 fir-single` at 2.7%.

Two independently prepared runs agreeing to the frequency ratio corroborates
both the timings and the clock probe. It also shows the ISA ratios are
clock-independent, which is the property a dispatch-preference decision needs.

Worth recording as methodology: on this board under Linux, `boost = 0` yields a
flat 3000 MHz rather than a held 4000 MHz, so determinism costs about 25% of
absolute throughput. `BENCHMARKING.md` asks for a flat clock rather than a fast
one, and this is what that trade looks like in practice.

## Compared with AMD Zen 4

| family | tier | this AVX1 part | Zen 4 |
|---|---|---|---|
| `fir-single` | avx1 | 2.458x | 3.451x |
| `fir-block` | avx1 | 1.289x | 1.921x |
| `sdm` | avx1 | 1.086x | 1.091x |

Vector FIR gains less on the older part, consistent with narrower execution
resources. The SDM cap near 1.09x is the same on both, which is the
width-independence recorded in `P13_amd_physical_avx512_2026-10-12/`.

## A separate question this run isolated

`in.wav` is **byte-identical** to our cross-host reference, and `a.dsf` is not:
`9291799b` here against `83f02d08`. Since `a.dsf` is produced with the default
scalar SDM, the same tier on the same input bytes yields different output on
this machine, and every FIR hash differs downstream of that one difference
rather than independently.

This is not the cross-ISA case `DSD_DESIGN.md:60` permits; it is one tier
failing to reproduce across machines. We have not established a cause and are
not guessing. The first run could not even isolate it, because the script did
not hash the stimulus and deleted it; that was our defect, fixed in `f8831565`,
and the fix is what made the input-identical finding available.

Compiler, libc and kernel for this host are in `host.txt`. Comparing those
against gcc 14.2 / glibc 2.41 on the reference host is the first step, and
whether cross-host scalar reproducibility is promised at all is a design
question we are not placed to answer.

## Disposition, which is ours

We believe the throughput half of this gate now has physical evidence on
prepared silicon with a verified-flat clock, and that the correctness half
passed independently of preparation. We do not issue the gate; the scalar
reproducibility question above may or may not bear on it.

Figures are from one host and are not a property of the code alone.
