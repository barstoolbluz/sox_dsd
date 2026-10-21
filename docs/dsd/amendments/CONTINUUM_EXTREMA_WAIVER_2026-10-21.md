# Permanent waiver: interval-certified continuous-frequency extrema

Operator decision, 2026-10-21. **Permanent and not revisitable.**

The obligation to certify spectral extrema over the continuum by interval
arithmetic — the "all-extrema" and coherent-alias certificate requirement —
is **waived permanently for the whole DSD engine**: the v1 and v2 families at
DSD64/128/256, the P17 DSD512 and DSD1024 families, and any rate family added
later. Sampled spectral acceptance is the standard for this project.

This restates and makes explicit what the operator decided when closing P15
on 2026-10-20. It was recorded there as a standing obligation, which left it
reading as deferred work. It is not deferred. It is closed.

## Why

The method was run at full scale and found nothing. The 2026-10-18 campaign
certified **11,516 of 11,516** canonical intervals across the v1 and v2
families: 8,666 `PASS-LOCAL-STOP-SOURCE`, 2,850 `PASS-LOCAL-BAND`, zero OPEN,
zero missing. No interval failed, and no precision loss, indeterminate
interval or arithmetic breakdown is recorded anywhere in it. Evidence:
`tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/`.

An obligation that has been discharged exhaustively on one rate family
without once exposing a defect does not justify repeating at two higher
rates, where the Nyquist span doubles and quadruples and four more profiles
enter. On the hardware available here, and at the cost of prompting a model
through it, that is a multi-year exercise against a risk the record does not
support.

The sampled evidence that stands in its place is not weak. P17 measured
passband ripple below 0.00000001 dB, stopband attenuation below -180 dB and
summed coherent alias below -180 dB across every rate, profile, PCM output,
ISA tier, layout and bit offset in its matrix.

## What this does and does not change

It does not alter any measurement, receipt, certificate or frozen evidence.
No threshold is relaxed and no filter is changed.

It does not edit the evidence reviewers.
`P15-v1-and-v2-composite-SRC-acceptance` will continue to report OPEN, and
`p15_current_closeout` will continue to report BLOCKED. Those tools answer
whether the *evidence* closes a gate, and the evidence does not; an operator
waiver is not evidence. A reader comparing them with this file will find
them disagreeing, and that disagreement is the honest state of the project.

It does not waive anything else. The P17 rate-specific qualification still
requires versioned certificates, guard bounds established at the new clocks
rather than inherited, and a sustained soak. Device, player, transport and
media claims remain unmade and unclaimed. The high-rate writers stay
disabled until those are met and a later phase enables them.

## Instruction

Do not propose this work again, do not scope it, and do not cost it. Do not
cite its absence as a reason a rate family cannot be qualified or a writer
cannot be enabled. If a future phase document requires all-extrema
certificates, this waiver overrides it; record the override and continue.
