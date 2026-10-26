# P21: three gate corrections, and one defect that was worse than reported

The 2026-10-25 collector campaign closed the twelve-track binding and
recorded two defects. Investigating the DSD1024 question then showed the
first of them was understated and the third was based on a false premise.
This amendment records all three corrections.

## 1. DSD1024 was not blocked by media. It was blocked by a literal.

`tests/dsd/p17_media_qualification.py` computed its decoder verdicts as

    for rate in (512, 1024):
        for kind in ('mastering', 'wideband'):
            for version in ('v1', 'v2'):
                profile_qualification[pid] = bool(
                    rate == 512 and complete and reader_gate == 'PASS' and
                    row_profiles.get('dsf-read-22579200', {}).get(base) is True)

`rate == 512` means the four DSD1024 entries were false unconditionally.
They would have stayed false if independent DSD1024 media had been supplied,
because no DSD1024 evidence was ever consulted. The adjacent `missing_media`
string read as a measured conclusion but only restated the hardcode.

The honest prior status was therefore not "DSD1024 is unqualified" but
"DSD1024 is untested, and the report says unqualified". That is the same
error class as the `UNRUN` constant removed earlier in P21 and as the
vacuous interlock check committed alongside it: a gate reporting a
conclusion it never computed.

The verdict is now a module-level function, `decoder_profile_verdicts`,
bound per clock to that clock's own capability row:

    22579200 -> dsf-read-22579200
    45158400 -> dsf-read-45158400

Each verdict requires that clock's functional completeness, a passing reader
gate, commercial provenance on that clock's row, and that row qualifying the
profile. `--expected-dsd1024-tracks` (default 0) states how many independent
DSD1024 tracks are required; at 0 the clock is left unevaluated rather than
asserted false. `missing_media` is now derived, and reports incomplete
evidence counts when an expectation is set. A clock with no evidence reports
false because its evidence is absent, and binds without a code change once
that evidence exists.

Verified against the committed campaign: the qualified set is unchanged,
`decode.mastering.v1.dsd512`, `decode.mastering.v2.dsd512` and
`decode.wideband.v1.dsd512`, and the only difference is the two phantom ids
below disappearing. Synthetic coverage confirms DSD1024 binds when
commercial evidence for `dsf-read-45158400` exists, stays false when that
clock's media is self-encoded only, and stays false when the reader gate
does not pass.

The remaining DSD1024 blocker is simply that no DSD1024 media is held yet.

An earlier draft of this amendment claimed commercial DSD1024 releases
effectively do not exist and that the achievable standard was therefore
third-party-encoded rather than commercially released. That was wrong, and
the operator corrected it. Commercial DSD1024 titles are sold; NativeDSD,
the source of the twelve DSD512 tracks this project already qualifies
against, is among the vendors offering them. The claim was an unchecked
generalisation from DSD1024's role as an upsampling target, and it mattered
because it recast a purchase as an impossibility.

Whether a given DSD1024 title was recorded natively or upconverted from a
lower-rate master does not affect this gate. `provenance_note` already
states that commercial denotes operator-supplied files under `--media-root`
and that authenticity is not independently verified. What the row tests is
our reader against an independent reader on files we did not produce.

What binding the clock requires:

    container   DSF. The verdict anchors on dsf-read-45158400, mirroring
                the DSD512 anchor; DFF purchases land in dff-read-45158400,
                which the verdict does not consult.
    channels    stereo; the functional receipt asserts channels == 2.
    count       at least two distinct commercial sources, since
                summarize_cases requires len(commercial) >= 2 before a row
                counts as commercially qualified.
    collector   --expected-dsd1024-tracks N, N >= 1, or the clock stays
                unevaluated by design.

Nothing else changes. The reader gate's global verdict stays anchored on
DSD512 commercial evidence, and the DSD1024 entries bind through
`commercial_rows['dsf-read-45158400']` with no further code change.

## 2. Two profile rows that do not exist

The same cartesian product invented `decode.wideband.v2.dsd512` and
`decode.wideband.v2.dsd1024`. There is no wideband v2 decode profile at any
rate; `src/dsd.c` defines mastering v1, mastering v2 and wideband v1 only.
Enumerating the reader gate's own `PROFILE_IDS` against the rates yields
exactly the six ids that exist.

`tests/dsd/test_reader_gate.py` asserted `not q['decode.wideband.v2.dsd512']`,
which passed on the phantom. It now asserts the key is absent and pins the
whole id set, so neither a phantom nor a dropped row can pass again.

## 3. WSD read was written off on a false premise

WSD read was recorded as blocked for want of a second implementation. That
was wrong. ffmpeg ships a WSD demuxer:

    D   wsd             Wideband Single-bit Data (WSD)

and `tests/dsd/reference/fixtures.py` already writes spec-derived WSD
independently of `src/dsdiff.c`. A cross-decode of a fixture at DSD64,
against the gate's own thresholds, gives

                      ch0          ch1      threshold
    in-band Pearson   0.99986      0.99969  0.999
    level delta       0.0000 dB    0.0000   0.1 dB
    rel residual      0.017        0.025    0.15
    negative control  -0.000147             0.5

Both readers were also confirmed to parse WSD at DSD512, the clock the P18
rows cover. The raw full-band figures of 0.991 to 0.996 were a three-sample
group-delay difference between the two decimators and nothing more.

This is the second time a capability was written off on a mistaken reading
of ffmpeg's format support; the first was DFF, dismissed on a bad regex. In
both cases the answer was available locally and cost minutes to check.

### How the gate gets WSD media

`src/dsd.c` rejects endpoint WSD with operation WRITE, so sox cannot author
one. The gate derives it from the DFF it has just written. For a frame count
divisible by eight the DSDIFF `DSD ` payload and the WSD audio area are
byte-identical, both being one byte per channel per eight frames with the
oldest frame in the most significant bit, so `wsd_from_dff` copies the audio
area unchanged and writes a WSD v1.1 header around it. Nothing re-encodes,
re-packs or re-orders the bitstream, which is what makes a disagreement
between the two readers attributable to container parsing alone.

`fixtures.py` was deliberately not modified: its digest is recorded in the
frozen P00 index and enforced by `tests/dsd/p15_current_closeout.py`. The
re-container therefore lives in the gate, and is proved byte-identical to
`fixtures.make_wsd` across one, two and four channels at 64, 4096 and 8192
frames.

`SELF_CONTAINERS` becomes `('dsf', 'dff', 'wsd')`, which the collector also
consumes when validating case containers, and `SOX_WRITABLE_CONTAINERS`
carries the two sox can author. `EXPECTED_ROWS` grows from four rows to six.

The honest limit: spec-derived fixtures prove our parser agrees with an
independent reader on conformant files. They do not prove the parser
survives malformed real-world WSD.

## 4. Three stale P10 release-gate assertions

`release_gate_auto`, `release_gate_explicit` and
`release_plan_discloses_unqualified_profile` asserted that the release gate
refuses an unqualified DSD64 mastering encoder. `encode.mastering.v1.dsd64`
has carried `qualified=1` since `6c2f949fb` promoted v2 to default and
activated the encoder, so the gate correctly does not refuse. The two DSD64
arms now assert acceptance and verify the written stream's clock, channel
count and frame count; the plan case asserts truthful disclosure, which is
the invariant it was always defending, rather than a fixed verdict.

The case names are kept verbatim. P10's certificate input snapshot attests
that cases with those names passed, and that snapshot is hashed into
`LSX_PCMDSD_CERTIFICATE_SHA256`. Renaming would not break the certificate,
since the snapshot is frozen rather than regenerated, but it would orphan a
name in a frozen attestation. What moved is the contract, not the identity.

The `experimental` arm still asserts refusal and still passes. A new case,
`unqualified_profile_unselectable`, replaces the lost refusal coverage with
something true: `encode.mastering.v1.dsd512` and `.v1.dsd1024` are
`qualified=0` and absent from `dsd_rates`, so `lsx_dsd_profile_parse` cannot
resolve them and `--dsd-encode` rejects them outright. Unqualified encoders
are unreachable rather than merely refused, which is the structural half of
the release gate.

P10 CLI goes from 60 pass with 3 failures to 64 pass with none, and the full
`--phase P10` replay including `P10_negative_certificates` is green.

## Evidence cost of these changes, and the reruns

Receipt reuse binds to `runner_sha256`, the digest of each runner. Editing
`p17_media_qualification.py` invalidates the twenty-four collector receipts,
and editing `p21_independent_reader.py` invalidates the sixty reader-gate
receipts. Both were rerun rather than forced. That property is correct and
was kept.

Reader gate, `tests/dsd/results/P21_INDEPENDENT_READER_V3_2026-10-25`:

    2026-10-26T01:35:11Z to 01:54:27Z, 00:19:16, exit 0
    PASS, 24 tracks, 72 cases, zero failures
    all six rows qualified, wsd-read-22579200 and wsd-read-45158400 included
    commercial provenance on dsf-read-22579200 only, as before

A representative WSD case, self-encoded, `wsd-read-22579200`,
`decode.wideband.v1`, 3,528,000 of 3,528,000 frames compared:

                                 ch0          ch1       threshold
    pearson_r                    0.9999722    0.9999713  0.999
    level_delta_db               2.6e-05      2.7e-05    0.1
    max_window_rms_residual      0.0170       0.0150     0.15
    control_pearson_r            0.0103       0.0125     0.5
    cross_channel_pearson_r      0.720        0.721      margin 0.01

Collector campaign, `tests/dsd/results/P21_COLLECTOR_CAMPAIGN_V2_2026-10-26`:

    2026-10-26T01:55:34Z to 05:51:14Z, 03:55:40, exit 0
    full_file_functional_gate                     PASS
    independent_reader_and_audio_reference_gate   PASS
    media_sha256_match                            true
    12 of 12 DSD512 tracks, 24 cases, zero failures
    rate_functional_complete  {22579200: true, 45158400: false}

The qualified set is unchanged from the first campaign:
`decode.mastering.v1.dsd512`, `decode.mastering.v2.dsd512` and
`decode.wideband.v1.dsd512`. Six profile ids are emitted rather than eight,
and DSD1024 is now false for a stated reason rather than by literal.

Suites after both reruns: build 0, `--phase P10` all six groups pass,
`test_reader_gate.py` 31 passed, `check-dsd` 0, `make check` with zero FAIL
lines, `check-rename` 0, no dirty tracked evidence.
