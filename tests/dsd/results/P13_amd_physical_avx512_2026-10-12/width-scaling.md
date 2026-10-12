# All five tiers in the pure kernel: FIR scales with width, SDM does not

Prompted by a reviewer asking why vector tiers were only ~1.1x faster than
scalar, which is far below what register width predicts for doubles. The
earlier rounds only ever compared AVX-512F against AVX2, so the scalar-relative
picture had never been measured. It answers the question and splits in two.

`bench_p11.py`, 15 repetitions, 180000 frames, CPU 8, prepared host.

| family | scalar | sse2 | avx1 | avx2 | avx512 |
|---|---|---|---|---|---|
| `fir-block` | 42.53 ns | 1.57x | 1.92x | 2.18x | **4.21x** |
| `fir-single` | 42.83 ns | 1.81x | 3.45x | **3.95x** | 3.42x |
| `sdm` | 20.64 ns | 1.17x | 1.09x | 1.17x | 1.09x |

## The FIR vectorises; the reviewer's premise was wrong about it

`fir-block` reaches 4.21x at AVX-512F and trends with width. `fir-single`
reaches 3.95x at AVX2. These are effective vector kernels. The "only 1.x over
scalar" impression came from our own reporting, which had only ever shown the
AVX-512F-over-AVX2 ratio and never the scalar baseline.

## The SDM does not vectorise, and width is irrelevant to it

2-wide, 4-wide and 8-wide all land between 1.09x and 1.17x, and the widest
tiers are among the worst. The gain is capped at about 1.17x and does not
respond to width at all. That is a measurement, repeated across 15 timed
repetitions per tier.

## Both reconcile with the end-to-end figures

- In-kernel SDM gain 1.17x against a measured end-to-end encode gain of 1.115x
  implies the SDM is roughly 80% of encode wall time. The ~11% available on
  encode is therefore close to the whole of what the SDM kernel can give.
  Encode is near its ceiling, not neglected.
- In-kernel FIR gain up to 4.21x against a measured decode movement of under 1%
  implies the FIR is a very small share of decode. The win is real and cannot
  be harvested through this path.

## Consequence for the optimisation question

On our reading: the vector FIR work is complete and inconsequential, and the
SDM is consequential and close to exhausted. If that is right, further kernel
width work on either family is not where remaining decode or encode time lives,
and the open question becomes what *does* dominate decode, which we still have
not established.

## Mechanism we are not asserting

The conventional account of a sigma-delta modulator is a feedback recurrence in
which each output depends on prior state, so samples cannot be processed in
parallel and only the order-4/6/8 inner product within a single step is
vectorisable. That would explain width-independence exactly. We did not
establish it, our mechanism claims in this area have been withdrawn twice
already, and it is offered only as the standard explanation for you to confirm
or reject. The width-independence itself is measured.

Figures are from one host and are not a property of the code alone.
