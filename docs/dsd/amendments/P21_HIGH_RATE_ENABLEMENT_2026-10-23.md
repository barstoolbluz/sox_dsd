# P21: all twelve high-rate capability rows opened

On 2026-10-23 the operator declared the high-rate evidence satisfied and
authorized every closed row:

> "i declare the evidence satisfied. flip all of these golden and we'll
> continue iterating on this on our own."

This amendment records what that opened, what stood behind each row at the
time, and which rows opened on declaration rather than on evidence. It is
deliberately explicit, because four of the twelve had no supporting
measurement at all and that should stay legible to whoever reads this next.

## What changed

  src/dsd.c        DSD512 and DSD1024 gain CAPS_QUALIFIED and profile ids;
                   the p18_closed[] table is removed, having no rows left;
                   the `native_hz>=22579200` hard stop becomes a bound at
                   the top supported rate
  src/pcmdsd.c     encode.mastering.v2.dsd512 and .v2.dsd1024 become
                   qualified=1 with the coefficient certificate, and are
                   ordered ahead of their v1 rows
  src/dsd_plan.c   the planner consults the capability table instead of
                   refusing both high rates unconditionally
  src/dsf.c        512x and 1024x added to write_rates so the negotiator
  src/dsdiff.c     stops substituting DSD256

## v2 decode at both clocks

Opening the capability rows was not sufficient for decode. The CLI's default
decode kind is v2, and v2 decode profiles stopped at DSD256, so the planned
path could not resolve one: `--dsd-mode auto` and `--dsd-plan` both failed
with `no decoder profile for <rate> Hz`, while the default path worked only
because the default mode is legacy, which skips domain planning.

Two rows were added to `dsd_frontends[]`. They introduce no new
coefficients. The final bank, intermediate clock and band edges are the
DSD256 v2 profile's, and only the half-band cascade grows, exactly as v1
reuses MASTER64_256 across DSD256, 512 and 1024. The edges stay at 66k/80k
because the intermediate clock stays at 176400 and its Nyquist is 88200, so
the stop edge cannot usefully move; v1 holds its own edges constant from
DSD256 upward for the same reason.

`delay_native_frames` is derived, not chosen. With the 57-tap half-band
contributing a group delay of 28 at its own input rate,

    delay_native = 28*(2^(stages-1) - 1) + ((taps-1)/2) * 2^(stages-1)

reproduces all eight pre-existing published delays exactly, and gives 12132
at seven stages and 24292 at eight.

Before committing, the extension was compared against the qualified DSD256
v2 profile on one source. The per-band difference between v2 and v1 matched
to two decimals at both clocks: -0.01 dB in 0-20k, +1.16 against +1.15 in
40-66k, +8.63 in 66-80k and +6.69 in 80-88.2k. In-band against ffmpeg it
scored 0.99996, the same as v1. That is a comparison against an already
qualified profile, not a qualification of this one.

## The v1 encoders stay disabled

`encode.mastering.v1.dsd512` and `encode.mastering.v1.dsd1024` remain
qualified=0. They are not simply older revisions: v1.dsd512 failed the
sustained nominal gate at min28 6, and v1.dsd1024 is the defective eighth
order. Both stay reachable by exact id for archived replay and must not be
promoted without new evidence. The operator's declaration was read as
covering the capability rows, not as a direction to expose a modulator we
measured as broken.

## What each row rested on

**Write, all four rows.** Fully supported. Both v2 encoders passed training
17/17, `verify` 17, holdout 36/36, cross-ISA identity, and an uninterrupted
3,600-second nominal soak: DSD512 at 81,285,120,000 native frames and 6.0%
guard utilisation, DSD1024 at 162,570,240,000 frames and 6.93%. The DSD1024
training maxima were reproduced exactly on our own hardware.

**DSD512 read, DSF.** Partially supported. Twelve commercially mastered
NativeDSD tracks decoded end to end under both mastering and wideband
profiles, 24 receipts, all PASS. That gate is explicitly functional-only:
`independent_reader_and_audio_reference_gate` was never implemented, and
reports the literal string `UNRUN` from
`tests/dsd/p17_media_qualification.py`.

After the declaration we ran the cross-check that gate was meant to be,
informally, and it supports the decision: ffmpeg and SoX DSD decoding the
same commercial track agree at correlation 0.99996 and 0.99995 with levels
matching to 0.01 dB. Evidence in
`tests/dsd/results/P21_HIGH_RATE_ENABLEMENT_2026-10-23/`. This is a sanity
check against one independent implementation on one album, not the gate.

**DSD512 read, DFF.** Opened on declaration. We hold no DSD512 DFF media of
any kind. Note also that DST-compressed DFF remains unreadable.

**DSD1024 read, DSF and DFF.** Opened on declaration. No DSD1024 media
exists for us to test against, and the design authority's position is that
self-encoded files are not an independent read oracle.

**DoP transport, both rates.** Opened on declaration. No device has ever
been exercised: `device_claims` is empty. DSD512 implies a 1,411,200 Hz PCM
carrier and DSD1024 implies 2,822,400 Hz; whether any hardware accepts
either is unknown here.

**WSD read, both rates.** Opened on declaration. WSD was previously excluded
by design rather than for want of evidence.

## The frozen P18 fixture manifest keeps its historical labels

`tests/dsd/reference/p18_fixture_matrix.json` still carries
`high_rate_capability: DISABLED` and `REFUSED_UNQUALIFIED` on every reader,
writer and transport case. That is deliberate and should not be "fixed".
Those fields describe the regime under which the P17 and P20 evidence was
sealed, and two tools re-assert them in order to regenerate that archived
evidence faithfully: `tests/dsd/generate_p20_candidate_certificate.py` and
`tests/dsd/seal_p18_manifest.py`. Flipping the labels would make those
tools reproduce certificates that never existed.

Live capability state is recorded where it belongs instead: in the code, in
this amendment, and in `high_rate_enabled` / `authorization` in
`tests/dsd/results/P18/integration/capability-integration.json`.

## Re-closing a row

Authorization stays table-driven. Reinstate a table of
`{rate, endpoint, operation, LSX_DSD_CAP_UNQUALIFIED}` in `src/dsd.c` and
consult it first in `lsx_dsd_capability_check()`. Do not reintroduce a size
check: refusing by magnitude is what P18 was written to avoid.
