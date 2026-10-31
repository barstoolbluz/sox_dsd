# Legacy SDM guard: trellis candidate check consolidation

Date: 2026-10-30. This is a narrow performance change on top of the
`legacy-sdm-guard` policy implementation (`a76a183`). It does not change the
policy, coefficients, quantizer, trellis sorting, error handling or user-facing
options. It does not remove guard checks on the ordinary PCM-to-DSD `clans-4`
route.

This record predates the 2026-10-31 change that made the guard opt-in
(`--sdm-guard on|off`, default `off`; see `LEGACY_SDM_GUARD_POLICY.md`). Its
`auto` measurements are of the then-default mode, which checked trellis fully.

## Why the shared-tail check is equivalent

`sdm_filter_calc2()` constructs two successors for each trellis candidate. The
SSE2, AVX and scalar implementations write identical values to all successor
`state[1..order-1]` components; only `state[0]` differs, by the quantizer's
`+1` and `-1` choices. For either successor, the old predicate was:

`all_bound(state[0..order-1]) && isfinite(cost)`.

The equivalent predicate is:

`shared_tail_bound && bound(state[0]) && isfinite(cost)`.

We now evaluate `shared_tail_bound` once against the first successor, then
check each successor's head and cost independently. The exact original power-
of-two thresholds, including the ordered `<=` test that rejects NaN, are
retained. A bad tail still rejects *both* successors, while a bad head or cost
rejects only the corresponding successor. A trellis step still fails closed
when no admissible candidate remains. The normal (non-trellis) kernel retains
its complete state scan. `--sdm-guard=off` still skips all guard work.

## Measurements

The following **local** measurements used an Intel Xeon Platinum 8573C,
GCC `-O2` default SSE2 build, Linux, one CPU pinned via `taskset -c 2`,
10 alternating rounds (first discarded), SoX `-R`, and an 11,289,600 Hz
synthetic mono `clans-4 -t 3 -n 4 -l 100` trellis conversion lasting 0.20 s.
Median *process CPU* seconds, not elapsed wall time:

| Binary | `auto` | `off` | Extra CPU from guard |
| --- | ---: | ---: | ---: |
| Before this change (`a76a183`) | 0.38909 | 0.32654 | +19.15% |
| With shared-tail check | 0.35725 | 0.32359 | +10.40% |

The guarded conversion's total CPU time fell **8.18%** on this one case.
The separate earlier 0.12-second, 8-round trellis comparison found a 9.48%
reduction. An additional 0.12-second stereo `clans-8 -t 13` synthetic test
showed a 5.94% median reduction in guarded CPU (0.65755 to 0.61851 seconds),
but had large outliers and is **indicative, not a qualified speed claim**.
All four combinations of checked/unchecked and before/after gave the same
successful output SHA-256 in the 0.20-second comparison. All 18 differential
CLI cases (normal/trellis, orders 4-8, `auto`/`on`/`off`) matched output hashes,
exit statuses and guard diagnostics. The unstable `sdm-8` trellis tests continued
to stop with exit status 2 and no partial output file. See the handoff's
machine-readable logs for individual results.

These are not comprehensive performance qualifications. The owner previously
measured around 26-27% full-guard overhead on *different trellis configurations*
on a Ryzen Threadripper 7970X. Do not extrapolate the reduction to those
configurations without profiling. The ordinary `clans-4` guard's previously
measured 9.4% full-route CPU overhead remains a separate problem.

## Alternatives rejected

A branchless scalar scan, a hoisted guard-policy dispatch, and an SSE2 scan
separate from the vector filter update either regressed important paths or
showed no material consistent `clans-4` improvement on this host. Fusing the
normal-path checks with the SIMD filter update produced small or noisy gains
and required substantially more platform-specific code. None is included in
this commit. A subsequent normal-path optimization needs a convincing,
repeated A/B benchmark on the actual production CPU, with bit-exact healthy
output and preserved fail-closed behavior.

## Validation limits

`make check`, `make check-sdm-guard-policy` (34 cases) and a subsequent full
`make check-dsd` passed on the local Linux build. An earlier `check-dsd`
attempt timed out during the numeric suite, without reporting a test failure.
The two-branch state-tail identity is supported by source inspection of the
scalar, SSE2 and AVX kernels.
This change is suitable for review and target-host qualification, not a claim
that the original modulator is stable for all possible inputs.
