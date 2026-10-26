# P21: the twelve-track collector campaign ran, and what it did not settle

The P21 reader gate landed on 2026-10-25 with its own evidence but without
the collector run that binds that evidence to the P17 decoder profiles. The
collector had only ever been exercised on a two-track smoke set, which is
why `tests/dsd/p17_media_qualification.py` reported the provenance interlock
as `INVALID`: it compares the twelve commercial DSD512 hashes against the
hashes carried in the reader evidence, and two is not twelve.

This amendment records the full campaign, which closes that gap, and one
defect in the evidence it emits.

## The run

    launched   2026-10-25T20:10:01Z
    finished   2026-10-26T00:05:44Z
    wall       03:55:43
    exit       0

    probe            test/dsd_test_p17_dsf
    tracks           12 distinct commercial DSD512, licensed, hash-identified only
    cases            24 (12 tracks x {mastering 176400, wideband 705600}, scalar)
    reader evidence  tests/dsd/results/P21_INDEPENDENT_READER_V2_2026-10-25
    results          tests/dsd/results/P21_COLLECTOR_CAMPAIGN_2026-10-25

    full_file_functional_gate                        PASS
    independent_reader_and_audio_reference_gate      PASS
    media_sha256_match                               true
    distinct_dsd512_tracks                           12 of 12 expected
    failures                                         0

All twenty-four receipts carry `PASS_FUNCTIONAL_ONLY`. That is the designed
per-receipt verdict and not a partial result: a full-file functional decode
establishes framing, channel count, destination rate, kernel tier and exact
PCM frame count, and deliberately claims nothing about audio content. The
audio oracle is the separately generated reader evidence, which the collector
reaches only through a hash-bound reference and re-judges from the bound case
receipts rather than trusting its summary flags.

With the interlock satisfied, three decoder profiles bind to the qualified
commercial `dsf-read-22579200` row:

    decode.mastering.v1.dsd512     qualified
    decode.mastering.v2.dsd512     qualified
    decode.wideband.v1.dsd512      qualified

## What remains unqualified, and why

The four DSD1024 profiles stay false for the reason the report states:
`No independent DSD1024 licensed media provided`. Self-encoded files are not
an independent oracle. This is the same standing blocker recorded at P21 and
nothing in this campaign touches it.

`qualification: UNQUALIFIED` at the top level of the report is a hardcoded
literal, not a derived verdict. The collector never claims overall
qualification, because device interoperability and exhaustive parsing
behaviour are outside what it measures. Read it as "this artifact does not
make that claim", not as a failure.

## Defect: two profile rows that do not exist

`decoder_profile_qualified` is built from a cartesian product over
{mastering, wideband} x {v1, v2} x {512, 1024}, so the report emits

    decode.wideband.v2.dsd512      false
    decode.wideband.v2.dsd1024     false

There is no wideband v2 decode profile at any rate. `src/dsd.c` carries
mastering v1, mastering v2 and wideband v1 only, and the reader gate's own
`PROFILE_IDS` is built from the three real base ids. The enumeration should
be bound to those ids and crossed with the rates, not invented.

The error direction is conservative: it reports `false` for capabilities
that do not exist, so nothing is wrongly claimed qualified. The cost is to
an independent reader, who would reasonably conclude from this report that a
wideband v2 profile exists and has failed to qualify.

The fix is three lines and is deliberately not applied here. Receipt reuse
binds to `runner_sha256`, the digest of the collector itself, so any edit to
`p17_media_qualification.py` invalidates all twenty-four receipts and forces
another four-hour campaign. That property is correct and worth keeping. The
fix should therefore be batched with the next substantive collector change
and the campaign rerun once, rather than spending four hours of licensed
media decode on a cosmetic correction to a field that is already failing
safe.

## Incidental finding: three P10 CLI tests assert pre-P15 behaviour

Replaying the P10 phase against current code during this round surfaced
three failures in `tests/dsd/test_p10.py`:

    release_gate_auto
    release_gate_explicit
    release_plan_discloses_unqualified_profile

All three encode the release gate's refusal of an unqualified DSD64
mastering encoder:

    assert 'unqualified' in cp.stderr or 'unavailable' in cp.stderr \
        or 'no qualified composite' in cp.stderr
    assert data['encoder']['qualified'] is False

`encode.mastering.v1.dsd64` has carried `qualified=1` since
`6c2f949fb P15: promote v2 to default and activate the encoder`. The gate
therefore does not refuse, the encode succeeds with exit 0, and `--dsd-plan`
reports `qualified: true`. The tests are not detecting a regression; they
assert behaviour the project deliberately changed five phases ago.

The `experimental` arm of the same loop still passes, correctly: `-p
experimental` resolves no qualified profile and the gate still refuses.

These did not rot noisily because the default gate does not execute them.
`make check-dsd` at `DSD_PHASE=P18` builds `dsd_test_p10` and runs the
native unit contract, and is green. The three CLI rows run only under an
explicit `tests/dsd/run.py --phase P10` replay. The committed P10 evidence
at `tests/dsd/results/P10/cli/cli.json` records all three as `pass`, which
was accurate when generated and is now a historical record rather than a
current claim.

Filed with the `tests/dsd/test_p15_r3.py` stale-row item. The decision these
need is whether a historical phase replay is supposed to hold against
current code at all; if it is, these three assertions should be inverted to
assert acceptance, not deleted.

## Operational note

Two traps cost time in this round and are worth recording. `make check-dsd`
invokes bare `python3` for its numerical dependency probe, so it exits 2
with `UNRUN: required P06/P07 numerical gate` unless the nix python
environment is ahead of it on `PATH`; it returns 0 when the environment is
correct. Separately, `tests/dsd/run.py` writes to committed evidence paths
by default, including frozen P00, so a replay must be given an explicit
`--results` under scratch. Both are known and both were hit again here.

## Status

The backfill item "the full twelve-track collector campaign is not run, so
the P17 decoder profiles remain unqualified" is closed. The DSD1024 media
gap and the phantom profile rows above are open.
