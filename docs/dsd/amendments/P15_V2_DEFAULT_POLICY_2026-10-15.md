# Operator decision: v2 is the intended default; the v1 default is a temporary gate

**Decision (2026-10-15), recorded by the operator. This is not a model
adjudication and not a new DSP tolerance.**

## The decision

Preserving the P10 coefficients and keeping v1 selectable is correct. However
**v1 is not the intended final default.** The approved reconstruction policy
makes **v2 the default for DSD64, DSD128 and DSD256**, with v1 available
through an explicit conservative selection.

Retaining v1 as the default is permissible **only while v2 qualification
remains incomplete.** This is a temporary release gate, not the final policy.

Once the affected qualification gates pass, **promote v2 to the default**
without modifying the preserved v1 coefficients and without changing unrelated
encoder behaviour.

## Why this record exists

`docs/dsd/DSD_DESIGN.md` already carries the policy: "The intended qualified
release's defaults are `auto`, **v2** mastering decode, **v1** mastering
encode..." and records that "while the P15 first-release gate is blocked, the
shipped `mastering` alias and automatic/default decoder choice remain v1".

The R3 handoff, `docs/dsd/handoffs/P15_R3_RECONSTRUCTION_POLICY_HANDOFF.md`,
does **not** state this. It describes v2 as an unqualified candidate and the v1
default as the shipped behaviour, without identifying the v1 default as
temporary or naming v2 as the intended endpoint. Read alone it invites the
conclusion that v1-as-default is settled policy.

This file closes that gap. It does not edit the handoff, which is preserved as
delivered.

## Conditions for promotion

Promotion of v2 to default requires the affected qualification gates to pass.
On our reading, which is ours and may be wrong, those are at least:

- the independent 3x9x2 metrology matrix **re-run against R3 sources**, since
  `p15_readjudication.py` correctly reports the R2 receipts no longer binding:
  four of 17 pinned source digests moved, so the existing 54 cells, 216
  forced-ISA jobs and 96 detailed comparisons are evidence for R2 and not for
  R3;
- an SRC acceptance envelope, which still does not exist;
- whatever the v2 coefficient certification in
  `tests/dsd/certify_p15_r3_filters.py` requires, which we have not yet run to
  a disposition.

Whether that list is complete is a determination for the design authority. We
are recording the decision and its stated condition, not ruling on the
condition.

## What has not been done

No default has been changed. `dsd_dispatch.c` and the planner still resolve to
v1, and v2 remains reachable only by explicit versioned ID. The P10
coefficients, guards, certificate constant, `sdm.c` and `pcmdsd.c` are
byte-identical to their frozen state. This record creates an obligation, not a
change.
