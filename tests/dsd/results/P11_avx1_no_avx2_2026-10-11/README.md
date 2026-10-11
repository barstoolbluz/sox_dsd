# P11 AVX1 compatibility in an AVX-without-AVX2 environment (2026-10-11)

**The AVX1 tier runs, byte-identically, on a CPU model that has AVX and lacks
AVX2 and FMA.** `docs/dsd/handoffs/P11.md` records this as UNRUN, and an earlier
integration note of ours claimed this host could not provide the environment.
That claim was wrong and was made without testing it.

## The environment

`qemu-user` x86-64, TCG, version 10.0.13, run as
`qemu-x86_64 -cpu SandyBridge`. Under that model CPUID reports `avx=1`,
`avx2=0`, `fma=0`, where the bare host reports all three.

It is trap-accurate rather than a CPUID mask, which is the property that makes
it usable here. Probing with hand-written instructions under the same model:

| Instruction class | Probe | Result |
| --- | --- | --- |
| AVX | `vaddpd %ymm1,%ymm2,%ymm0` | executes |
| AVX2 | `vpaddq %ymm1,%ymm2,%ymm0` | SIGILL |
| FMA | `vfmadd132pd %ymm1,%ymm2,%ymm0` | SIGILL |

So an accidental AVX2 or FMA encoding in the AVX1 unit would fault here rather
than quietly execute, which is what distinguishes this from masking CPUID on a
capable part. SOW section 48's warning concerns claiming *hardware performance*
from CPUID masking; no performance claim is made from this environment, and none
should be read into it.

## Results

| Check | Outcome |
| --- | --- |
| `sox_ng` starts under SandyBridge | yes |
| Forced FIR scalar | exit 0, byte-identical to the native run |
| Forced FIR SSE2 | exit 0, byte-identical to the native run |
| Forced FIR AVX1 | exit 0, byte-identical to the native run |
| Baseline starts with no AVX at all (`Nehalem`, `core2duo`) | yes, exit 0 |
| Forced AVX1 on a CPU without AVX | refused by preflight, exit 2 |

The last line is the dispatcher declining rather than crashing: "P05 preflight:
requested DSD FIR kernel tier is unavailable on this CPU/build".

Machine-readable detail, including the executable hash and per-run output
hashes, is in `avx1-environment.json`.

## What this does and does not establish

It establishes that the AVX1 unit contains and executes no instruction outside
AVX1, since any such instruction would have faulted, and that the three tiers
agree bit for bit under a CPU lacking AVX2 and FMA. Taken with the static
instruction audit of the built objects, which found zero AVX2 and zero FMA
encodings, the compatibility question looks settled to us.

It is emulation under TCG and not silicon. A reviewer who requires bare metal
for this gate is entitled to say so, and genuine AVX-without-AVX2 hardware would
be Sandy or Ivy Bridge Intel, or AMD Bulldozer, Piledriver or Jaguar. We have
none and did not test on any. Whether a trap-accurate emulated environment
discharges the SOW's "AVX-without-AVX2 environment" is a judgement for the round
that owns the criterion; this directory is the measurement, not that judgement.
