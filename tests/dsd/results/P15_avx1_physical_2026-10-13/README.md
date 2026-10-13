# P15 physical older-AVX throughput: verified on Intel Xeon E5-1680 v2

**Status: artifacts delivered and independently verified.** This supersedes two
earlier states of this file: a first version asserting these figures with no
supporting artifacts, and a second marking them UNVERIFIED after an
adjudication round found the only artifact present described a different
machine. Both earlier defects were ours, recorded below under "Evidence
history" rather than deleted.

## The host, from its own receipt

| field | value |
|---|---|
| CPU | Intel Xeon E5-1680 v2 @ 3.00 GHz (Ivy Bridge-EP) |
| avx / avx2 | **yes / no** — genuine older-AVX silicon |
| virtualization | none, hypervisor flag absent |
| microcode | 0x42e |
| compiler | gcc (Debian 14.2.0-19) 14.2.0 |
| libc | Debian GLIBC 2.41-12 |
| kernel | 6.12.48+deb13-amd64 |
| cflags | -O2 -g |
| bench cpu | 2 of 16 |

The 3.00 GHz base clock is why boost-off yields a flat 3000 MHz rather than a
reduced ceiling.

## Independent verification performed here

- `check_p15_avx1_receipt.py` on the delivered directory:
  **`ADMISSIBLE_FOR_INDEPENDENT_REVIEW`, zero problems**, where the previous
  record returned `BLOCKED` on six missing receipts.
- `sha256sum -c kernel-output-sha256.txt`: **all eight artifacts OK**.
- Every timing figure quoted below matches `kernel/kernel-timing.json` exactly,
  which itself records the host as the E5-1680 v2, status PASS, 15 repetitions.
- The within-host invariant computed from the delivered files, not the console:
  **one distinct FIR hash, two distinct SDM hashes**.
- `a.dsf` is byte-equal to `sdm_scalar.dsf`, confirming it is produced with the
  default scalar SDM, which was previously an inference.
- `in.wav` is **byte-identical** to this project's reference
  `bb23075f...`, so the stimulus was the same and the scalar-SDM output
  difference recorded below is real rather than an input artifact.
- `gate-eligibility.txt` records `gate_relevant=yes` from the script's own
  checks, with the clock flat at 3000 MHz across all three arms, 206 to 221
  busy samples each.

Audio payloads totalling 8.2 MB are deliberately not committed; their SHA-256
digests are in `kernel-output-sha256.txt` and the originals are in the
operator's delivered archive.

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

## Disposition, corrected

We previously wrote that the throughput half of this gate had physical
evidence. That was wrong: it had operator-reported numbers and no artifacts.
The gate is UNRUN. The correctness half is in the same position, since its
hashes also reach us only as console text.

## Original disposition, superseded

We believe the throughput half of this gate now has physical evidence on
prepared silicon with a verified-flat clock, and that the correctness half
passed independently of preparation. We do not issue the gate; the scalar
reproducibility question above may or may not bear on it.

Figures are from one host and are not a property of the code alone.

## The cross-host scalar difference, now adjudicated

`sdm_scalar.dsf` is `9291799b...` here against this project's `83f02d08...`,
from a byte-identical `in.wav`. The adjudication of 2026-10-13 ruled this **not
a defect**: §8.6 states that forcing scalar assists reproducibility under a
pinned build and is not advertised as universal cross-compiler determinism, and
the specification nowhere guarantees cross-host scalar-encoded byte identity. A
different trajectory from a different host is acceptable provided it satisfies
the same numerical and stability gates.

The one toolchain delta we can see is a glibc patch level, 2.41-12 here against
2.41-12+deb13u2 on the reference host, with kernels 6.12.48 and 6.12.85. We did
not establish that either causes the difference, and under the ruling above it
no longer needs establishing for this gate.

## Evidence history, kept rather than erased

1. First version asserted these figures from pasted console output with no
   artifacts in the directory.
2. A local smoke run of the script inside the repository, used to check its ISA
   guard, wrote a `host.txt` describing this AMD Threadripper with `avx2 yes`;
   `git add -A` swept it in beside a README about a different machine. The
   adjudication's section C found the contradiction and correctly ruled the
   receipt inadmissible.
3. That artifact was removed and the record marked UNVERIFIED.
4. The operator delivered the real directory; this version is verified against
   it.

The script now forces `AVX1_SMOKE=1` runs to DIAGNOSTIC regardless of governor
state, which closes the hole that allowed step 2.
