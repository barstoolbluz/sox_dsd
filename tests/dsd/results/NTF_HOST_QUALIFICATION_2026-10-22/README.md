# Host qualification of the new DSD512 NTF finalists, 2026-10-22

Threadripper 7970X. Both finalists completed the full 3,600-second nominal
soak the design study could not run; it reached 360 seconds and correctly
refused to call that sustained.

Run with the delivered `host_7970x_qualification.sh`, one patch described
below, in two parallel disposable workspaces. Guards are trained against
*our* executable, as the replay instructions require, not reused from the
archive.

## Result: both pass the sustained gate

| | o7-r5-a20 | o7-r8-a20 | gate |
|---|---|---|---|
| verdict | PASS_SUSTAINED_INPUT_GATE | PASS_SUSTAINED_INPUT_GATE | |
| native frames | 81,285,120,000 | 81,285,120,000 | exact |
| 28-bit windows | 81,285,119,973 | 81,285,119,973 | exact |
| min / max ones28 | 7 / 21 | 7 / 21 | 7 to 22 |
| longest constant run | 6 | **7** | |
| excursions28 | 0 | 0 | 0 |
| nonfinite states | 0 | 0 | 0 |
| unexpected overloads | 0 | 0 | 0 |

Preceding each soak, in the same workspace: 17/17 unguarded training, freeze,
verify, 36/36 guarded holdout with the deliberate overload rejecting at code
2 as intended, and post-freeze 60-second full-scale DC screens passing both
polarities.

## One number moved with duration

`r8`'s longest constant-bit run is **7**, against `r5`'s 6, the study's
reported 6 for both at 360 seconds, and the P20 CLANS-7 baseline's 5. It
remains inside the population band and is not a failure. It is the only
metric that grew when the run lengthened tenfold, and `r8` is the study's
preferred candidate on spectral grounds, so it is recorded here explicitly
rather than left in a receipt.

## The delivered helper needed one fix

`host_7970x_qualification.sh` asserts `test ! -e test/dsd_test_p10` after
`make distclean`. That binary is an automake `EXTRA_PROGRAM`, so distclean
does not remove it, and the assertion always trips. Under `set -eu` the
script aborted with no output at all.

The patch deletes the stale `EXTRA_PROGRAMS` and `src/sox` before the
assertions, so the guard is satisfied rather than bypassed. The intent of
the check, that no archived object or executable can be reused, is preserved
and in fact enforced. `host_qual_one.sh.patched` is the exact script used;
its only other change makes the candidate list overridable so the two
finalists could run concurrently in separate workspaces.

## What this does not establish

Nominal sustained operation only. It does not prove arbitrary-input
nonlinear stability, all-ISA equivalence, commercially mastered source
fidelity or production suitability. The scalar kernel was used throughout as
the replay specifies; AVX2 and AVX-512 remain a separate assessment.

The historical six-minute original composite remains an invalid source
control: it violates the 0.5 envelope before modulation and is not eligible
for a sustained claim. Only the nominal composite was run.

No capability is enabled, no production coefficient changed, and no profile
promoted. CLANS-7 remains the qualified reference.
