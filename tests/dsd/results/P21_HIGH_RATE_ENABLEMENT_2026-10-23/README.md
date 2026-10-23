# P21 high-rate enablement, 2026-10-23

All twelve P18 capability rows opened by operator declaration. The
authorization, and what each row did and did not rest on, is recorded in
`docs/dsd/amendments/P21_HIGH_RATE_ENABLEMENT_2026-10-23.md`. This directory
holds what we measured on the host afterwards.

## Contents

  roundtrip.json           write then reparse, four rows, both containers
  commercial-read.json     twelve licensed DSD512 tracks, by hash only
  ffmpeg-cross-check.json  our decode against an independent reader
  cli/                     the P21-regime CLI matrix, 106 cases
  suites.log               check-dsd, make check, check-rename

## Results

Round trip: all four write rows produce a file at the rate requested, not a
silently substituted DSD256. DSD512 565,340 and 564,610 bytes for DSF and
DFF, DSD1024 1,130,588 and 1,129,090, from a 0.1-second 176,400 Hz source.

Commercial read: 12 of 12 licensed DSD512 DSF tracks open and report
22,579,200 Hz. Opening a file and reporting its rate is not a correctness
oracle; it is the functional gate that already passed before P21.

Independent reader: our decode of one track and ffmpeg's agree in the audio
band at Pearson 0.99996 and 0.99995, with RMS matching to 0.01 dB. The
residual at -41.6 and -39.8 dB is the two reconstruction filters differing,
not container parsing. One implementation, one album, three seconds: a
sanity check, not the `independent_reader_and_audio_reference_gate`, which
remains unimplemented and still returns a hardcoded `UNRUN` from
`tests/dsd/p17_media_qualification.py`.

CLI matrix: 106 of 106. Every case that previously asserted a refusal now
asserts the authorized behaviour, and every output case reparses the written
file and requires the requested rate, because the negotiator's substitution
to DSD256 was previously blocked by the refusal itself. Two refusals remain
asserted because neither came from P18: native mode cannot change DSD rate
without reconstruction, and the channel-layout guard still fires on
destinations that cannot carry a named layout.

Suites: `check-dsd`, `make check` and `check-rename` all pass.

## Sealed P18 evidence is unchanged

`tests/dsd/results/P18/` and `tests/dsd/reference/p18_fixture_matrix.json`
still describe the closed regime, deliberately. Two tools re-assert those
labels to regenerate pre-P21 certificates. This directory is the live state.
