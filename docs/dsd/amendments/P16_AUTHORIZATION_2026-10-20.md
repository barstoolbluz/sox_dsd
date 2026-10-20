# P16 authorization and P15 close, 2026-10-20

Operator decision. P15 is closed and **P16 is authorized.**

This is an authority record, not a measurement. It closes a phase on the
operator's judgment, which is the only thing that can close one; it does not
assert that any gate was met.

## What is decided

- P15 is closed. No further adjudication rounds.
- P16 is authorized to begin against `sows/P16.md`.
- First release is authorized. The v2 decode default and mastering v1
  encoder activation, already live in the tree, are confirmed rather than
  newly permitted here.

## What remains true, and is not altered by this

Two gates remain OPEN on the evidence, and stay OPEN:

| gate | state |
|---|---|
| `P15-v1-and-v2-composite-SRC-acceptance` | OPEN. 72 SRC-active cells have no independent same-transfer arithmetic certificate and no all-extrema/coherent-alias certificate. |
| `P15-DSD256-direct-2x-and-matched-comparator` | OPEN. 8 of 8 comparisons clear 2x at the CI lower bound; the matched control is not spectrally verified at v2's 66 kHz passband edge. |

The design authority recorded its engineering acceptance on 2026-10-19 and
stated that completion of the outstanding formal-proof obligation is no
longer required for release
(`amendments/P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md`).
These obligations are therefore standing, not blocking. They remain
discharged by proof or not at all; this record does not discharge them and
nothing here may be cited as having done so.

## Why the reviewers still say BLOCKED

`p15_current_closeout.py`, `p15_closeout_review.py` and
`p15_src_envelope_review.py` continue to report `status: BLOCKED`,
`p16_authorized: false` and `default_promotion_authorized: false`, and their
tests continue to assert it. That is deliberate and is left alone.

Those tools answer one question: *does the evidence authorize this?* The
answer is still no, and it will stay no until certificates exist. An
operator decision is not evidence, and writing it into an evidence reviewer
would destroy the only property that makes the reviewer worth reading. The
authorization lives here instead, where a reader can see who decided it and
on what basis.

So a reader comparing this file with the tooling will find them disagreeing.
That disagreement is the honest state of the project: the work ships by
operator decision while two proof obligations stand open.

## Sixteen proof-campaign test files fail, and are closed over

Outside the phase gates there are sixteen `tests/dsd/test_p15_*.py` files that
fail on this tree:

```
campaign_dispatch_corrective  final_obligations      final_prover_audit
high_rate_census              opt_source_rebind      prover_fixed_interval
prover_second_pass            prover_third_pass      r6_exact_composite
r7_fast_fir                   r8_dyadic              r9_strong
r9_uniform_math               remaining_math         src_bound_operator
src_complete_aliases
```

They are one failure family: each binds to prover or campaign receipts
recorded against an earlier source revision, and refuses when the source no
longer matches. Representative messages are `receipt source/binary/schema
drift` and source-digest set mismatches. This is the same unbinding the
matrices had, which was re-bound on 2026-10-20; these bind to the spectral
prover campaigns instead, and re-binding them means re-running those
campaigns rather than re-measuring a 54-cell matrix.

Verified pre-existing, not introduced by the rename integration, the matrix
re-bind or this authorization: the identical sixteen fail with the identical
counts in a clean worktree at `68f42359`, before any of that work. Two
differ only by a skip becoming a run, because this tree has a built `src/sox`
and the worktree did not; the test then fails for the same source-drift
reason.

None of the sixteen is wired into `make check-dsd`, which is why the phase
gate reports 223 PASS 0 FAIL while they fail. That gap is why they went
unnoticed, and it is recorded here rather than closed quietly.

This record closes over them. It does not repair them, and it is not a
finding that their underlying proofs are wrong; it states that their receipts
no longer bind to the shipping source and that P15 is closed anyway, on the
operator's decision.

## Scope

Authorizes the start of P16 only. It carries no numerical tolerance, no
spectral or alias qualification, no ISA preference, no hardware or device
compatibility claim, and no permission to rewrite, rebase or repoint frozen
evidence under `tests/dsd/results/`.
