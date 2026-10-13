# P10 certificate source lineage: expected, documented, needs reconciliation

**This document replaces an earlier version of itself that was wrong.** That
version called the condition a silently-red release gate that no phase had
noticed and that independently blocked P15. A reviewer corrected it and we
confirmed the correction. What follows is the corrected account.

## The condition

`tests/dsd/check_p10_certification.py` pins SHA-256 digests of 35 source inputs
(`check_p10_certification.py:49-50`). On the current tree it exits 1 because
four no longer match: `src/dsd_plan.c`, `src/pcmdsd.c`, `src/pcmdsd.h`,
`src/sdm.c`. Each was changed by a later phase for a reason that phase
documented. 31 of 35 are unchanged.

On the unchanged P10 tree at `63872844` the same checker passes:
`{"gates": 10, "corpus": "PASS", "prepared_host": "PASS", "status": "PASS"}`.

## This is intended behaviour, and P11 said so

`docs/dsd/handoffs/P11.md:223-225` records it:

> The original P10 certificate verifier reports PASS on the unchanged input
> tree. It intentionally rejects P11-modified hashes; the original certificate
> was not broadened or edited.

The verifier is pinned to the P10 revision on purpose. Rejecting later
revisions is what it is built to do. P11 also recorded six independently
rebuilt P10-versus-P11 scalar CLI conversions across three native rates and two
buffer/thread settings producing identical DSF hashes, which is behavioural
equivalence evidence for the scalar path.

## What we got wrong

- We wrote that nobody ran the checker in four phases and that no phase
  noticed. **False.** P11 ran it, understood it and documented it, including
  that the rejection is deliberate. The accurate and narrower statement is that
  *our own* audits of P11 through P14 did not run it, so our gate lists omitted
  it. That is a gap in our auditing, not a project-wide oversight.
- We wrote that P15 cannot close release qualification while the checker is
  red, and led the P15 dispatch with it as a blocker. **Overclaimed.** A
  revision-pinned verifier returning 1 on a later revision is not evidence that
  mastering qualification failed or that P10 must be repeated. What it requires
  is a bounded source-lineage reconciliation.
- Calling it "staleness" framed expected behaviour as decay. This directory was
  renamed from `P10_certificate_staleness_2026-10-12` accordingly.

## What is actually required, per the reviewer

Not a new P10 campaign. A bounded reconciliation:

1. Preserve the original P10 certificate and historical verifier unchanged.
2. Reconcile the four source changes against the accepted P11-P14 handoffs.
3. Reuse existing P10 and P11 numerical and bit-identity evidence where valid.
4. Run a narrowly scoped current-revision regression only where a change is not
   already covered.
5. Record the lineage reconciliation in the P15 qualification evidence.

Explicitly: do not regenerate the P10 certificate to make its old hash checks
pass. That would obscure what the certificate attests.

Unresolved source lineage can legitimately prevent final default activation,
which is a real constraint on P15's promotion step. It is not a reason to defer
P15's substantive qualification work.

## Reproduce

```sh
python3 tests/dsd/check_p10_certification.py --results <dir>          # exit 1 here
git archive 63872844 | tar x -C /tmp/p10 && cd /tmp/p10 && \
  python3 tests/dsd/check_p10_certification.py --results <dir>        # exit 0
```

The per-file digests, with `optimization_changed: false` on all four, are in
`../DECODE_OPTIMIZATION_2026-10-12/validation/p10-certificate-binding.json`.
