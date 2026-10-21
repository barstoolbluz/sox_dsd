# P17 authorization, 2026-10-21

Operator decision. **P17 is authorized.** P16 is closed.

An authority record, not a measurement. It opens a phase on the operator's
judgment and asserts nothing about what that phase will prove.

## What is decided

- P16 is closed. Its packed input path is integrated, gated and soaked.
- P17 is authorized to begin against `docs/dsd/sows/P17.md`.
- No writer enablement is authorized. Higher-rate output stays disabled
  until container and transport qualification, which is P18's subject and
  needs its own authority.

## What P16 leaves behind

The packed front end is optional, off by default, and selected by
`SOX_DSD_PACKED_INPUT=1`. Packed and expanded agree bit for bit across the
model's 6,480-combination matrix and across real commercial material we
measured separately.

P17's own acceptance asks for expanded versus packed benchmarks, so the
figure it inherits should be the better-grounded one. On a prepared host at
a 0.0% noise floor, paired and interleaved on real DSD256 rips, packed is
**1.051x on DSF, CI95 [1.039, 1.063]**. The interval excludes parity, so the
gain is real, and it is small. Evidence:
`tests/dsd/results/P16_OPERATOR_CORPUS_AND_BENCH_2026-10-21/`.

## What stays open

P15's two proof obligations remain OPEN and are not discharged here:
`P15-v1-and-v2-composite-SRC-acceptance` and
`P15-DSD256-direct-2x-and-matched-comparator`. The authority ruled them
standing rather than blocking on 2026-10-19; that ruling is unchanged.

The evidence reviewers continue to report `BLOCKED` and `p16_authorized:
false`, and will not be edited to say otherwise. They answer whether the
evidence authorizes a step; an operator decision is not evidence. P16's
edits to P00-indexed sources are unadmitted drift by design, tracked with
`scripts/p16_dev_input_drift.py` and reviewed at a checkpoint, per
`docs/dsd/P00_P16_EVIDENCE_WORKFLOW_2026-10-20.md`. P00 and
`REVIEWED_P00_INDEX_SHA256` stay frozen.

## Scope

Authorizes the start of P17 only. No numerical tolerance, no spectral or
alias qualification, no high-rate interoperability claim, no ISA preference,
no permission to rewrite frozen evidence, and no implicit DSD512 or DSD1024
enablement from the P16 descriptor existing.
