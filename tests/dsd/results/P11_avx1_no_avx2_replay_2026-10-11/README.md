# P11 AVX1-without-AVX2 qualification replay (2026-10-11)

**All 21 checks PASS.** This is the executable qualification the adjudication
round named as the one remaining mandatory item, run with its own test
`tests/dsd/qualify_p11_avx1_emulator.py` and `qemu-x86_64` 10.0.13 TCG.

## Why our earlier evidence did not establish this

`tests/dsd/results/P11_avx1_no_avx2_2026-10-11/` forced only the FIR tiers under
`-cpu SandyBridge`. Every forced-tier row in it reads `forced_fir_tier`. The
composite defaults its SDM to scalar, so the AVX1 **SDM** kernel never executed
on an AVX2-less CPU, which is the path that matters most since it is the
vectorised counterpart of the recurrence P10 certified. The adjudication round
identified that gap precisely, and it was a real one.

## What the replay establishes

| Group | Result |
| --- | --- |
| Trap probes under SandyBridge: AVX executes, AVX2 and FMA SIGILL | PASS |
| Kernel unit suite under SandyBridge, all three tiers, FIR and SDM | PASS |
| Kernel unit suite under Nehalem, scalar and SSE2, AVX1 correctly UNRUN | PASS |
| Baseline CLI starts under Nehalem and core2duo | PASS |
| SDM scalar, sse2, avx1: emulated and native | PASS, 6 checks |
| FIR scalar, sse2, avx1: emulated and native | PASS, 6 checks |
| Forced FIR AVX1 and forced SDM AVX1 refused on Nehalem | PASS |

The output hashes are the substance. Emulated and native agree exactly within
each tier, and the vector tiers agree with each other:

- SDM scalar, emulated and native: `22a6f1f93fad...`
- SDM sse2 and avx1, emulated and native, all four: `f0b2b6093dae...`

So the AVX1 SDM kernel produces identical output on a CPU without AVX2 and on
the bare host, and identical output to SSE2. Had the AVX1 unit contained an AVX2
or FMA encoding reachable on this path, it would have faulted under the
emulator, as the trap probes in the same run demonstrate it would.

Under Nehalem the unit suite reports `P11 host feature mask=1 (SSE2=1 AVX1=0)`
and marks the AVX1 tier UNRUN rather than attempting it; under SandyBridge it
reports `mask=3` and runs all three. Forcing AVX1 where the CPU lacks it is
refused by preflight for both families, with distinct FIR and SDM diagnostics.

## Standing and limits

Design section 8 states that "a VM with AVX2/AVX-512 CPUID disabled can validate
instruction isolation and AVX1 correctness, but not Sandy Bridge/Ivy Bridge
performance", so this environment is the sanctioned route for the correctness
question and carries no performance claim. The emulator is TCG, not silicon. We
ran the test; we did not write it, and the ruling on whether it discharges the
gate belongs to the round that set it.
