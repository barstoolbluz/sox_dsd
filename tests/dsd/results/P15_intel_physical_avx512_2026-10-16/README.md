# P15 Intel physical AVX-512 throughput (2026-10-16)

**The Intel physical arm has been run. Its gate status is unchanged and is not
ours to change.** `P15_INTEL_AVX512_SCOPE_2026-10-14.md` says "Do not write
PASS ... retain a visibly scoped UNRUN-SCOPE-EXEMPT status", and that
"readjudication creates a new ledger rather than rewriting old UNRUN labels".
This directory is that new ledger entry. The gate in
`p15_current_closeout.py` still reads `UNRUN-SCOPE-EXEMPT`; reclassifying it
belongs to the design authority.

Produced by `tests/dsd/check_intel_avx512_perf.sh` on tree `5f10710f`, which is
byte-identical to HEAD for every file that ran. Raw audio intermediates were
dropped after their hashes were recorded.

## Host

11th Gen Intel Core i9-11900H, Tiger Lake-H, microcode 0x56, physical with no
hypervisor flag and `systemd-detect-virt` reporting none. Governor performance,
`intel_pstate/no_turbo` 1, pinned to cpu 2 with its SMT sibling offlined.
gcc 14.2, glibc 2.41, kernel 6.12.107, `-O2 -g`. `gate_relevant=yes`.

Full AVX-512 set including `avx512_vp2intersect`.

## The question this arm existed to answer

Whether Intel downclocks under 512-bit instructions, which would mean a slower
AVX-512 wall time and a lower AVX-512 clock are different findings.

It does not, on this part:

| tier | median | p10 | p90 |
|---|---|---|---|
| scalar | 2500 MHz | 2500 | 2500 |
| sse2 | 2500 MHz | 2500 | 2500 |
| avx2 | 2500 MHz | 2500 | 2500 |
| avx512 | 2500 MHz | 2500 | 2500 |

-0.00% for AVX-512 against AVX2, locked at the 2.5 GHz base clock with
p10 equal to p90 on every tier. This is the cleanest clock record of the three
microarchitectures measured. Wall-clock timings can be read directly, with no
licence-downclock confound to argue about.

## Result: the same verdict as AMD, now without that confound

Kernel microbenchmarks, median CPU ns per frame:

| family | AVX2 | AVX-512F | Intel speedup | AMD speedup |
|---|---|---|---|---|
| `fir-block` | 30.63 | 15.99 | **1.915x** | 1.93x |
| `fir-single` | 25.18 | 20.89 | 1.206x | 0.925x |
| `sdm` | 33.89 | 34.26 | 0.989x | 0.920x |

End-to-end, all six configurations:

| case | decode | encode |
|---|---|---|
| dsd64-1ch-1t-short | 0.995x | 0.987x |
| dsd128-2ch-1t-short | 1.010x | 0.988x |
| dsd256-6ch-1t-short | 0.992x | 0.992x |
| dsd64-1ch-2t-long | 1.007x | 0.998x |
| dsd128-2ch-2t-long | 1.001x | 0.992x |
| dsd256-6ch-2t-long | 0.988x | 0.988x |

The 1.9x block-FIR win does not reach the conversion graph, on Intel exactly as
on AMD. Every end-to-end case sits within 1.2% of unity, and ten of the twelve
are at or below it.

Two vendors, two microarchitectures, both with verified stable clocks, agree:
the kernel gains and the pipeline does not. The reading we offered for AMD
holds here, that the FIR tier is not what bounds this workload.

## Correctness ran first

`distinct FIR: 1, distinct SDM: 2`, and all five FIR tiers and all five SDM
tiers reproduce the cross-host reference digests byte for byte:

    in.wav      bb23075f0e133795df9d2f7f66623cddb244ae873461d416e119e9aa37349190
    a.dsf       83f02d0856c23a50d9b717259fd15c5384ad2303e1b0c99211403d7569ef420b
    fir_*       ddc48d53afd672850466d0d3cd0b7b8c777ecd5a2c4757ae71dbf92ef6e286c2
    sdm_scalar  83f02d0856c23a50d9b717259fd15c5384ad2303e1b0c99211403d7569ef420b
    sdm_vector  65c0cbbd89b8e59be12e3eb0af17442700d4edab454ceaed3dd158b857c666da

The three dispatch and kernel sources pinned in `benchmark-matrix.json`
(`dsd_dispatch.c`, `dsd_kernels_avx2.c`, `dsd_kernels_avx512.c`) match this
tree, so these timings measure these kernels.

## Scope

Throughput on one prepared host. Not an audio quality result, not a device
claim, and not a promotion decision. Dispatch stays conservative. Nothing here
authorises an Intel preference, and release remains BLOCKED.
