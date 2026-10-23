# DSD1024 NTF R2: host reproduction of the stability screen

Independent replay of the R2 nonlinear screen on the 7970X host, from the
delivered `tests/dsd/ntf_dsd1024/` harness, using a locally built
experimental binary. Four designs across all eight R2 cases, 32 native
renders at 45,158,400 Hz, scalar kernel, scale 0.5.

The purpose was to test whether the R2 failure frames reproduce on
different hardware with a different binary. They do, exactly.

## Identities

    design_sha256                  f6ef9af08482ed3bbd7f5e88297e95ce419252dfbd56e87fdfe686f2e9400d12
    experimental_header_sha256     777dfa2cf1a15f7776811976ff813ef6d752a2ae959d91e36674e3ce02a57298
    experimental_sdm_sha256        f569382454fc898e9e4b92935dd48e060c98dc3707940144b521d9038530fa8c
    original_sdm_sha256            6f845c659185f58b07fb4c38d72dc29b734931c7b0bbfaebaef8bee82a6da61f

`design_sha256` regenerated here matches the value `REPLAY.md` pins,
f6ef9af08482ed3bbd7f5e88297e95ce419252dfbd56e87fdfe686f2e9400d12.

Native `dsd_test_p10 --unit`: 105,489 assertions, zero failures, matching
the delivery and the adversarial audit.

## Screen outcome

    case                                 clans-7           clans-8             sdm-8      d512-sdm7-g3
    dc-negative-0p99                        PASS   fail@17,223,812   fail@16,476,430    fail@8,211,544
    dc-negative-1p0                         PASS   fail@15,485,608   fail@33,108,316    fail@9,972,463
    dc-positive-0p99                        PASS   fail@17,223,812   fail@16,476,430    fail@8,211,544
    dc-positive-1p0                         PASS   fail@15,485,608   fail@33,108,316    fail@9,972,463
    programme-unclipped-0p90                PASS              PASS              PASS              PASS
    tone997-0dbfs                           PASS   fail@14,577,472              PASS   fail@10,924,323
    tone997-0dbfs-inverted                  PASS   fail@14,577,472              PASS   fail@10,924,323
    tone997-minus0p1dbfs                    PASS   fail@72,217,530              PASS    fail@8,039,403

## First nonfinite frame, claimed against reproduced

    design         case                  R2 report    this host
    clans-8        dc-negative-1p0      15,485,608   15,485,608  match
    clans-8        dc-positive-1p0      15,485,608   15,485,608  match
    d512-sdm7-g3   dc-negative-1p0       9,972,463    9,972,463  match
    d512-sdm7-g3   dc-positive-1p0       9,972,463    9,972,463  match
    sdm-8          dc-negative-1p0      33,108,316   33,108,316  match
    sdm-8          dc-positive-1p0      33,108,316   33,108,316  match

Six of six exact. Both polarities fail at the same frame, as reported.

## The incumbent across all eight cases

    case                             frames  nonfin  exc28  ovl             peak   28-window
    dc-negative-0p99             72,253,440       0      0    0   0.495000000086      [6,15]
    dc-negative-1p0              72,253,440       0      0    0   0.499999999978      [6,15]
    dc-positive-0p99             72,253,440       0      0    0   0.495000000086     [13,22]
    dc-positive-1p0              72,253,440       0      0    0   0.499999999978     [13,22]
    programme-unclipped-0p90    144,506,880       0      0    0   0.451743156594      [7,21]
    tone997-0dbfs                72,253,440       0      0   11   0.500000000023      [6,22]
    tone997-0dbfs-inverted       72,253,440       0      0   11   0.500000000023      [6,22]
    tone997-minus0p1dbfs         72,253,440       0      0    0   0.494276547335      [6,22]

`encode.mastering.v2.dsd1024` passes every added case with zero nonfinite
states and zero 28-bit excursions. The eleven
`monitor_overloads_nominal_half` counts on both 0 dBFS tones reproduce at
peak 0.500000000023, the interpolator boundary roundoff the R2 report
documents and bounds; it is not a candidate property.

## What this does and does not establish

It confirms the R2 screen is reproducible and that the withdrawal of the
R1 shortlist rests on real native behaviour, not an artefact of their
host. It qualifies nothing: these renders use the unguarded experimental
recurrence, so a failure is a property of that recurrence and not a defect
in the guarded production profile.

One observation worth recording. CLANS-8 fails the -0.1 dBFS tone at frame
72,217,530 of 72,253,440, inside the last 36 thousand frames of the case.
A screen even slightly shorter would have passed it. That is an argument
for duration margin in any future gate, not a finding about CLANS-8.

Receipts for all 32 renders are in `receipts/`, named `<case>--<design>.json`.
Packed bitstreams, 195 MB, are not retained; each receipt carries its
`packed_sha256` so they can be regenerated and checked.

## Bitstream-exact reproduction of the archived tonal holdout

A stronger check than matching a reported frame number: regenerate the
stimulus, render it locally, and compare the one-bit output byte for byte.

The 20 kHz holdout's `input_sha256` in their archive is
693e2e146f91c37046089b86b4ed9bcf7abe1ffc41cbb1942493627c7cd68d8d, which is
`tone20000.f64le` from the DSD512 study's replay-holdouts. `study.py
stimuli` regenerated it to that digest here, and `tone-40k` likewise to
b07f7f9ef1bce88b70ccaacde9118f12907948269045a71328f607990ac9f514. Both
agree with the DSD512 `generate_holdouts.py` manifest, so the stimulus
chain is closed independently of either study.

Rendering tone-20k for the five finalists, 54,190,080 native frames each:

    design                              packed sha256   match
    clans-7          1d072ab05f72639e2f45f3405427d7b7   exact
    clans-8          940d6f2a9e4c209bf235234f6c4bfb3b   exact
    d512-sdm7-g3     4c2ef849f64eccbe64a064b2013be89b   exact
    sdm-8            cf36429a4d96caa2c14d1131161f476d   exact
    sdm-8-g2p0       eaa41686c049b72fa8f9eb25e3d94f3a   exact

5 of 5 byte-identical to the delivered archive, from a
regenerated input and a locally built binary. Their F-03 claim of
independent SHA-matched replay holds on this host.
