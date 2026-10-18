# Operator verification of the corrected delivery, 2026-10-17

`P15_SRC_INDEPENDENT_CORRECTED_FULL_2026-10-17.tar.gz`, SHA-256
`25d124e4...`, verified on arrival. Its 22441-entry internal manifest
verifies. Header `src/rate_poly_fir0.h` is `bd86a881...` as declared.

## Both things we reported blocked are fixed

| | before | now |
|---|---|---|
| `source_operators(canonical_plan('1000'))` | `UnboundOperator` | 24 realizations |
| `BranchBoundary`, `interval_deadline`, `IntervalBudgetExpired` | absent | present |
| `test_p15_final_obligations.py` | FAIL | OK |
| `test_p15_campaign_dispatch_corrective.py` | ImportError | OK |

The re-derived bindings arrived as a new directory,
`P15_SRC_STAGE_BOUND_OPT_2026-10-17`, leaving the 2026-10-16 receipts in
place.

## Reproduced on this host

Both GNU Autotools builds PASS, GCC 14.2.0, out-of-tree, exactly the flags in
their reproduction section. `p15_src_opt_build_contract.py` reports
`qualified_opt_in_cflags: true` against the generated `src/Makefile`.

Compiled C exact regression, both configurations, matching their counts
exactly:

    opt-in       PASS  768060 checks  5409850 sample words  4 rounding modes  effective_ordered=1
    default-off  PASS  768060 checks  5409850 sample words  4 rounding modes  effective_ordered=0

Python integration suite: 31 tests, OK, zero skips once the test exporter is
exposed in the source tree as their instructions describe. Without that step
one test skips, which is how their "zero skips" claim is reached.

CLI cross-build equality: at 176400 to 48000 and 88200 to 44100, stereo
binary64, the opt-in and default-off builds produced byte-identical output at
the declared lengths of 768000 and 705600. Our digests differ from theirs
because their input fixture is not published and ours is a different signal;
the claim reproduced is the equality between builds, not their absolute hash.

## The FP-contraction question is answered

The header now carries a hard `#error` requiring
`-DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1` alongside the opt-in, with a note
that no portable macro reports `-ffp-contract=off` so the build must declare
it. Tested: the guard fires without the acknowledgement macro and compiles
with it. That is as far as C allows, and the build-contract checker covers
the rest.

## What this costs us

`import_archived_partial` refuses our 5112 campaign receipts as a
"stale/invented source-bound receipt". They are preserved in the tree but
cannot serve as proof under the new source identity, so the continuum
campaign starts from zero whenever it is next run. Their addendum says the
same.

## Their Clang finding, not re-run here

They report Clang 17 failing the four-rounding-mode harness at FE_DOWNWARD in
an unchanged h8 halfband, with the optimization disabled as well as enabled,
and passing under `-frounding-math` or `-ffp-model=strict`. We verified the
GCC path only and did not reproduce the Clang diagnostic.

## Scope

Opt-in. Default build unchanged. P15 remains unqualified; nothing here closes
a gate or changes a default.
