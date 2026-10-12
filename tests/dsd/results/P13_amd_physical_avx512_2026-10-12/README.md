# P13 AMD physical AVX-512F qualification (2026-10-12)

**AMD physical arm: CLOSED. Result: do not promote AVX-512F.**
**Intel physical arm: permanently unobtainable. See the disposition below.**

Run on an AMD Ryzen Threadripper 7970X, physical hardware with no hypervisor
flag and `systemd-detect-virt` reporting none, microcode `0xa10810c`, performance
governor, boost disabled, pinned to CPUs 8-23, 15 timed repetitions per case,
`--full-matrix` so single and multithread and short and long cases all run.
Full provenance in `host-provenance.txt`.

Tree `39bc7101`. All seven kernel and dispatch sources are byte-identical to
P13 (`dsd_dispatch.c`, `dsd_kernels_{avx512,avx2,scalar}.c`, `dsd_kernels.h`,
`sdm.c`, `dsd_coeffs.h`), so these timings measure the P13 kernels.

## What the measurements say

Kernel microbenchmarks, median CPU ns per frame, AVX-512F against AVX2:

| family | AVX2 | AVX-512F | speedup |
|---|---|---|---|
| `fir-block` | 19.51 | 10.09 | **1.93x** |
| `fir-single` | 11.65 | 12.59 | 0.925x |
| `sdm` | 17.46 | 18.97 | 0.920x |

End-to-end, all six configurations:

| case | decode | encode |
|---|---|---|
| dsd64-1ch-1t-short | 0.997x | 0.976x |
| dsd128-2ch-1t-short | 1.002x | 0.963x |
| dsd256-6ch-1t-short | 0.996x | 0.950x |
| dsd64-1ch-2t-long | 1.002x | 0.951x |
| dsd128-2ch-2t-long | 0.998x | 0.946x |
| dsd256-6ch-2t-long | 1.001x | 0.943x |

The 1.93x block-FIR win does not reach the conversion graph. Decode is neutral
to within a fifth of a percent in every case.

**Read `decode-tier-sensitivity.md` before relying on the decode column.** A
follow-up measurement prompted by review shows decode moves only 1.6% across
the entire five-tier matrix, scalar through AVX-512F, because the FIR accounts
for well under a percent of decode wall time. The decode column therefore is
not a measurement of AVX-512F efficacy; it shows that no tier choice matters
much to decode. The conclusion below is unaffected and better supported:
nothing to gain on decode, a real loss on encode. Encode is *slower* in all six,
between 2.4% and 5.7%, monotonically worse as the work grows, with median
absolute deviations three to four orders of magnitude below the differences.
Six independent configurations agreeing in direction and magnitude is signal.

**This is the break-even answer P13 asked for: break-even is not reached.** The
one kernel that benefits is not what the real graph spends its time in, and the
tiers that the graph does use are 8% slower under AVX-512F.

## Frequency behaviour

Sampled `scaling_cur_freq` on the pinned CPU for the duration of a sustained
90-second-source encode, discarding idle samples:

| tier | busy samples | median | min |
|---|---|---|---|
| AVX2 | 25 | 3969 MHz | 3969 MHz |
| AVX-512F | 27 | 3969 MHz | 3966 MHz |

No AVX-512 frequency offset is observable on this part. The encode regression is
therefore not a clock effect; it is throughput. The standard account of Zen 4's
AVX-512 is a double-pumped 256-bit datapath, which would predict exactly this
shape — wide block operations gain, everything else does not. We did not measure
that mechanism and offer it only as the conventional explanation.

Caveat: boost was disabled, correct for throughput comparison but it also
suppresses the conditions under which a frequency offset would be most visible.
A boost-enabled run would characterise real-world clock behaviour better and we
did not perform one.

## The harness cannot certify its own host

`bench_p13_matrix.py` recorded `"virtualization": "CPUID is virtualized or
unknown; not independent vendor hardware certification"` and an `unrun` list
still asserting `"Physical AMD AVX-512F host: not independently available in
this environment"`. Both are false for this run. They are static strings from
the phase's VM-era authoring, not detections. We left the raw file unaltered and
`host-provenance.txt` carries the independently gathered truth. Any future
reader should trust the provenance file over the harness's self-description, and
the harness's labels should be made conditional before they mislead someone.

## Disposition, which is ours and may be wrong

The operator has stated that bare-metal Intel silicon with AVX-512 is not
obtainable to this project, now or later. That is consistent with Intel having
disabled AVX-512 on client parts from Alder Lake onward, leaving it on Xeon SP
and older HEDT only.

We therefore believe this gate cannot be closed as written, and that saying so
is better than carrying it as perpetually pending. What is closed is the AMD
half, on physical silicon, with provenance. What cannot be closed is the Intel
half.

We also believe nothing shipped depends on that gap. `dsd_dispatch.c` resolves
the automatic FIR tier to SSE2 and the mastering SDM tier to scalar, verified
empirically: on this AVX-512-capable host the default report records
`fir_kernel_actual: sse2`. AVX1, AVX2 and AVX-512F are reachable only by
explicit environment forcing. The open gate therefore blocks exactly one thing,
promoting a vector tier to automatic selection, and this measurement says the
promotion would be a regression on the only vendor we can measure.

The conservative default is now supported by measurement rather than caution
alone. P15 should decide whether to close the gate as not-required-for-the-
shipped-configuration, or to keep AVX-512F permanently opt-in. We do not make
that determination here.

Figures are from one host and are not a property of the code alone.
