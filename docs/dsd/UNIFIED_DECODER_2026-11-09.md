# Unified DSD decoder for the 1.1.1 development series

**Behavior as of 2026-11-09.** This change sits on top of the thirteen
`release-1.1.1-v2pin` patches. The source version is still 1.1.0; no release
number is changed here.

## Available paths

- **DSD to PCM:** `--decode mastering`, the default, and exact
  `decode.mastering.v1.dsd64/128/256/512/1024` select the same mastering-v1
  reconstruction banks. The only alternative is `--decode wideband` and its
  exact `decode.wideband.v1.dsdNNN` identities. Native clock pins are enforced.
  The effect-level `dsdpcm -p` uses the same selectors; global settings still
  propagate to an unpinned explicit effect.
- **Removed:** the five mastering-v2 decoder profiles, their three final-stage
  FIR coefficient banks, the retired decoder `conservative` and `legacy`
  spellings, and public decoder enum value 3. Legacy numeric API inputs 2 and
  3 return `SOX_DSD_BAD_ARGUMENT`; neither maps to a different bank.
- **PCM to DSD:** default mastering v1 at all rates. Qualified optional
  `encode.mastering.v2.dsd512` and `encode.mastering.v2.dsd1024` remain exact
  pins for the distinct CLANS-7 modulator, with the old strict/warn mapping.
  The encoder selectors `legacy` and `experimental` remain in the grammar,
  with their existing qualification rules. No encoder recurrence, coefficient
  array, guard bound, or high-rate profile ID was changed.
- **Planning and execution:** `policy.decode` now says `mastering` or
  `wideband`, and for a selected high-rate encoder-v2 pin `policy.encode`
  gives the same exact ID as `encoder.id` rather than falsely saying `mastering`.
  The selected runtime decoder and encoder identities are checked separately.

The historic v2 decoder bandwidth claims of 25/48/66 kHz are not features of
this release. The surviving mastering-v1 passbands are 20 kHz at DSD64,
30 kHz at DSD128, and 40 kHz at DSD256/512/1024. Wideband remains an explicit
choice, subject to the requested PCM clock and bandwidth policy. No claim is
made that one decoding bandwidth is inherently better for all content.

## Reproducible checks and their scope

Results of these gates on the release host are in
`tests/dsd/results/UNIFIED_DECODER_2026-11-09/`. The most relevant executable gates are:

- `python3 tests/dsd/checks/test_unified_decode_111.py --sox "$PWD/src/sox"`
  (65 cases, five native clocks): default/mastering/pinned PCM byte equality,
  distinct wideband output, effect-local routing, planner/runtime profile
  agreement, rejected removed decoder spellings and wrong clock pins.
- `python3 tests/dsd/checks/test_v2_pin_111.py --sox "$PWD/src/sox"`:
  both high-rate encoder-v2 pins, actual output, gain/bitstream, strict/warn,
  headroom replay, wrong-clock/conflict refusal; now also verifies
  `policy.encode` against the exact selected encoder ID.
- `python3 tests/dsd/checks/test_p21_reader_regression.py --sox "$PWD/src/sox" \
  --reference /usr/bin/ffmpeg`: deterministic, self-encoded multichannel
  DSDIFF and DSF comparisons including 1.2345-second fractional seeking and
  a deliberately silent reference-channel negative control. With FFmpeg
  7.1.3 (Debian 13), four 4-/6-channel comparisons passed, with measured offsets
  between -40.5013 and -40.5024 native DSD frames. This **does not** establish
  compatibility with a private music library, other reference versions, or
  every commercial DSDIFF header variant.
- `python3 -m pytest -q tests/dsd/checks/test_reader_gate.py`: 42 passing
  synthetic fault-injection/orchestration checks, including 2/4/6-channel
  stub rows. Stubs are never passed off as independent-decoder qualification.
- `python3 tests/dsd/checks/test_v2_110_compat.py --old-sox OLD --new-sox NEW`:
  20 independently executed byte-for-byte comparisons between a build of the
  `sox_dsd-1.1.0` tag and this candidate:
  DSD512 and DSD1024, DSF and DSDIFF, two PCM stimuli, clip-and-warn and
  strict policies, plus automatic and fixed headroom. This verifies the
  encoder-v2 bitstream in those cases, not all possible audio.
- `python3 tests/dsd/checks/test_p10.py --sox ... --candidate ... --results ...`:
  64 passing CLI-graph cases, including positive high-rate encoder-v2 pins.
  Three bitstream-reference render cases and five DSD-origin/mixed-graph
  cases compare the CLI's default-gain output with the `guarded-cli` oracle.
- `python3 tests/dsd/checks/test_111_receipt_redaction.py`: deterministic 800-row
  release-data sanitization; the historical input remains unchanged.

The correct command to exercise the normal release-facing suite is
`make check-dsd-cli` after `autoreconf -fi && ./configure && make`.
`make check` covers the retained general SoX tests. `make check-dsd
DSD_PHASE=P10` passes in the full tree, which carries the P10 certificate
inputs. An independent P21
full reader gate on private licensed audio and audio-device interoperability
are not established by these synthetic tests.

## Disposition of the 13 later review observations

1. **P10 refusal of qualified v2 encoder pins:** incorrect. The old
   `unbound_qualified_profile_unselectable` expectation is replaced by an
   executable positive selection/report test for both high-rate IDs in
   `tests/dsd/checks/test_p10.py`. The retained legacy test case names bound into
   earlier P10 certificates are not renamed.
2. **Effect manual falsely denies v2 encoding:** corrected in
   `soxeffect_ng.7`, which gives both exact optional high-rate encoder IDs.
3. **FFmpeg silent quad DSF channel:** confirmed to be triggered by `-ac N`
   layout remapping in the supplied workflow. P21 no longer forces `-ac`;
   each channel is measured independently. Quad DSF now passes in the
   executed synthetic-audio comparison.
4. **FFmpeg fractional-seek offset drift:** output-side `-ss` decodes
   continuously before trimming. The 1.2345-second witness passes within
   the existing one-native-frame alignment bound without widening it.
5. **Misattribution of timing:** the archived click experiment measured
   FFmpeg 7.1.3 approximately 40.5 native frames later than SoX, not the
   intrinsic SoX FIR delay. The timing memo and P21 commentary now distinguish
   the observed decoder timing from seek errors and reference-version limits.
6. **Always-stereo fake reader:** the stub reads source channel metadata,
   emits one decoder report row per actual channel, creates distinct PCM
   channels, and has multi-channel offline control fixtures. Commercial
   negative controls are now paired by clock *and* channel count; a source
   without a different compatible control remains unqualified.
7. **Untraceable review validation claims:** `12 further synthetic reader
   cases` and the prior `make check` success claim have no retained output
   in the supplied tree. Both are explicitly withdrawn from the old review
   document. New claims in this note must be backed by receipts in
   `tests/dsd/results/UNIFIED_DECODER_2026-11-09/`.
8. **Incomplete historical CLI build inventory:**
   `tests/dsd/results/V1_HIGH_RATE_ENCODE_2026-11-07/cli-paths/build.txt`
   names four `src/` files that differ from the run's build tree; patch 0009
   later changed six (`src/dsd.c`, `src/dsd.h`, `src/dsd_plan.c`,
   `src/pcmdsd.c`, `src/pcmdsd.h`, `src/sox_ng.c`). `tests/dsd/results/` and
   its original README are untouched:
   `cli-paths/release-1.1.1.jsonl` is a **pre-v2-pin snapshot**, not evidence
   from the finished release branch.
9. **Private paths in release distribution:** the 800-row historical real-
   track receipt remains unchanged under `tests/dsd/results/`. A deterministic
   replacement under `tests/dsd/release_evidence/` redacts filesystem paths
   in `stderr` while preserving warnings and counts. `EXTRA_DIST` now uses
   the redacted copy, not the raw historical receipt. The full research
   source snapshot still contains original historic evidence and is **not**
   a privacy-redacted release distribution.
10. **Review-process wording in release notes:** removed. The notes describe
    1.1.1 behavior, not a temporary review status.
11. **Unproved "9 of 36" statement in patch 0008:** withdrawn as a
    factual qualification claim, and the commit message no longer makes it:
    none of the supplied receipts proves that numerator, and the 36 cases
    covered *both* high-rate clocks rather than just DSD512. No corrected
    count is invented.
12. **`policy.encode` ambiguity:** resolved for exact v2 pins; the plan
    now prints the qualified exact `encode.mastering.v2.dsdNNN` selected, with
    a regression assertion independent of the runtime reported profile.
13. **Usage indentation:** corrected for both newly added encode lines in
    `src/sox_ng.c`.

## Historical scope, changed files and limits

Historical `docs/dsd/handoffs/`, `docs/dsd/briefs/`,
`docs/dsd/amendments/`, and the existing `tests/dsd/results/` records are
**unchanged**; this change only adds `tests/dsd/results/UNIFIED_DECODER_2026-11-09/`.
Current-behavior documents changed here are `README.md`, `sox.1`,
`soxeffect_ng.7`, `docs/dsd/USING_SOX_DSD.md`,
`docs/dsd/RELEASE_NOTES_1.1.1.md`, `docs/dsd/README.md`,
`docs/dsd/MIGRATION_P15.md`, `docs/dsd/CLI_USABILITY_DESIGN.md`, and this note.
The older `docs/dsd/FFMPEG_DSD_OFFSET_2026-11-08.md` preserves its measured
numbers but clarifies that v2 decoder rows are historical and that its
FFmpeg attribution is build-specific. The earlier
`docs/dsd/REVIEW_111_V2_PIN_RESOLUTION_2026-11-08.md` is explicitly marked
superseded and its unsupported claims corrected.

The decoder-only runtime tests `test_p15_r3.py`, `test_p15_r3_numeric.py`,
`test_p15_r3_src_spot.py`, and `test_p15_v2_matrix.py`, along with their
`check-dsd-p15-r3` target, are removed. Historical research tools and
numerical certificates including `generate_p15_r3_coeffs.py`,
`certify_p15_r3_filters.py`, and archived P15-R3 results are retained to
explain prior decisions, **not** to certify present decoder behavior.

No private audio or native hardware was used for these checks. The
20-case byte-for-byte high-rate encoder replay ran against a build of the
`sox_dsd-1.1.0` tag.
