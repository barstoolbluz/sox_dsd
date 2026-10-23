# Scalar-trained guard bounds hold on every ISA tier, 2026-10-22

Threadripper 7970X, all five tiers present. 20 renders: both finalists x
scalar, SSE2, AVX1, AVX2, AVX-512 x full-scale DC both polarities, every one
enforcing the **scalar-trained** frozen bounds.

This was raised as a question for the design authority. It is not one: it is
an empirical claim, and the measurement settles it.

## Result: 20 of 20 pass, with 18x headroom

| candidate | scalar | sse2 | avx1 | avx2 | avx512 |
|---|---|---|---|---|---|
| o7-r5-a20 | 5.18% | 5.14% | 5.14% | 5.14% | 5.14% |
| o7-r8-a20 | 5.61% | 5.44% | 5.44% | 5.44% | 5.44% |

Peak guard utilisation against each candidate's own scalar-trained ceilings.
Zero nonfinite states in all 20. Population and longest-run figures are
identical across tiers: 13 to 23 on positive DC, 5 to 15 on negative, run 9.

Full-scale DC was chosen deliberately over music. It drives state magnitude
hardest, and the commercial-source test had already shown real material sits
well inside the limits, so music would have been a weak probe.

## Two observations

**The vector kernels use slightly less state than scalar**, 5.14 against
5.18 and 5.44 against 5.61. The margin is small but the direction matters:
bounds derived from scalar training are conservative for the vector paths
rather than optimistic. That is the outcome one would want and it was not
guaranteed in advance.

**Bitstream statistics are identical across tiers** even though the kernels
are not bit-identical. The arithmetic reordering perturbs state trajectories
slightly without moving the population or run figures the gates test.

The minimum population of 5 on negative DC is expected: full-scale DC
fixtures are assessed against the [4,24] monitor band, not the stricter
[7,22] nominal band, as the design study's own report states.

## What this closes, and what it does not

It closes the question of whether scalar-trained bounds are valid for vector
kernels. They are, on this host, for these candidates, under the most
state-stressing input available. No design ruling is needed, because nothing
was violated.

It does not establish all-ISA equivalence in general: one host, one native
rate, 60-second renders rather than sustained soaks, and bit-identity between
tiers is neither claimed nor required. A 3,600-second soak on a vector tier
remains unrun.
