# P18 authorization, 2026-10-21

Operator decision. **P18 is authorized. Enablement is not.** P17 is closed.

An authority record, not a measurement.

## What is decided

- P17 is closed. Its DSD512/DSD1024 DSP is integrated, private and
  unreachable from the CLI.
- P18 is authorized to begin against `docs/dsd/sows/P18.md`.
- **No higher-rate capability may be enabled in this phase.** P18's own rule
  is that a capability is enabled only for its passed DSP and format pair,
  and its first named risk is a writer allow-list outrunning DSP
  qualification. P17 returned `PASS_DEVELOPMENT_TESTS_UNQUALIFIED`. The DSP
  gate has therefore not passed, so the format and transport gates stay
  shut regardless of what the containers could hold.

This is not a restriction added here. It is P18's completion criterion read
literally: unverified transports and devices stay unsupported or explicitly
unclaimed, and documentation matches the actual gates.

## What the phase is for, then

The machinery and the closed gates. Per-container and per-operation
capability gates that return a concrete capability error rather than
silently down-rating or substituting coefficients. Transport-rate arithmetic,
including DoP512 at 1.4112 MHz and DoP1024 at 2.8224 MHz. The high-rate
format and transport fixture matrix, the compatibility ledger, the
capability-specific release manifest. uint32 rate and uint64 length
validation, padding, layouts, round trips, long-duration accounting. DSF
high-rate ecosystem extensions and the DFF general versus Edited Master
distinction documented without claiming either.

A phase that ends with every high-rate capability still disabled, each
refusal specific and tested, and an evidence chain showing why, is a
complete P18 by its own terms.

## What we cannot contribute

We hold no DSD512 or DSD1024 media and no hardware that consumes it. The
independent software and player evidence P18 asks for, and any device
claim, are unrun gates on the operator side as well as the model's. They
must be named unrun, not inferred from byte packing.

## What stays open

P15's `P15-v1-and-v2-composite-SRC-acceptance` and
`P15-DSD256-direct-2x-and-matched-comparator` remain OPEN and standing.
P17's rate-specific qualification remains UNQUALIFIED. P00 and
`REVIEWED_P00_INDEX_SHA256` stay frozen.

## Scope

Authorizes the start of P18 only. It authorizes no writer enablement, no DoP
rate, no container capability, no device or interoperability claim, and no
change to the qualified DSD64/128/256 release.
