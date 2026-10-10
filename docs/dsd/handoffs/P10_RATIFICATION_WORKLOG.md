# P10 ratification continuation and handoff checkpoint — 2026-10-10

## Original bytes and scope

Starting archive: `sox_ng-P10ratify-8f52d842.tar.gz`.
SHA-256: `876d1c2466990947a6218b7daa7c59c87d6093db8d03df9530b51adba7fb0dbc`.
This was a git-archive snapshot with no `.git`, so the delivered source tree
contains the complete P00–P10 continuation, not a standalone patch.

All 1,945 historical files under `tests/dsd/results/` were independently
byte-compared with the original archive during staging, with zero changes.
`tests/dsd/test_p10.c` remains byte-identical (SHA-256
`21932da61612638336e90b862c8f528657f051f4d2406da6ff60bc8a58eacc30`),
so its pinned hardware and numeric generator identity stays verifiable.
The source archive omits the in-tree copy of this round's brief
(`docs/dsd/briefs/P10-ratify.md`) and all generated build objects and executables.
No commercial source audio is redistributed.

## Final ruling and changes

**P10 INCOMPLETE. DSD64, DSD128 and DSD256 profiles remain UNQUALIFIED;
promotion BLOCKED.** The ratification authority and full arguments are in
`P10_RATIFICATION.md`. The new collector lives at
`tests/dsd/qualify_p10_ratification.py`, with frozen reviewer criteria in
`tests/dsd/reference/p10_ratification_criteria.json` and its versioned result
in `tests/dsd/results/P10_ratification_2026-10-10/qualification.json`.

- Representative hardware hour: **PASS**, three 3600-second native rates, one
  current *scalar* sdm-8 kernel family, 71,124,480,000 native frames, 183
  independently hashed snapshots, zero observed guard/finite/window failures.
  The historic 1800-second equality caused the one-hour summary's false
  `release_sequence` report; that receipt is intentionally untouched.
- Independent real-world source corpus: **PARTIAL**, with 18 commercial
  DSD-origin excerpts (14 unity admissions, four rejected then recovered with
  explicit attenuation) and **no independent ordinary PCM source receipts**.
  All eight other inherited acceptance gates remain PASS.
- `minimum_attenuation_db` describes the first failing sample only. The new
  CLI diagnostic explicitly warns it is a lower bound and that later peaks
  may require more. No extra DSP pass, state change, or gain fallback was
  introduced. A non-overload failure reports no attenuation estimate.
- Current guarded P10 code is scalar even when compiled for an SSE2 baseline.
  P11 must repeat hardware qualification for any optimized kernels it adds.
  Source peaks vs the 0.5 envelope do not establish interpolation overshoot.

The original `qualify_p10_corrective.py` and original negative certificates
remain available for historical replay, but their hardcoded UNRUN fields
are not the current ratification judgment. New results never modify old ones.

## Commands verified on the final changed source

- `autoreconf -fi`: exit **0**.
- `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`: exit **0**.
- `make -j2`: exit **0**, no compiler warnings on final rebuild.
- `make check`: exit **0**.
- `make check-dsd DSD_PHASE=P10 DSD_RESULTS=<outside-source>`: exit **0**
  on the full inherited suite, including P07, P08 and P09.
- `test/dsd_test_p10 --unit`: exit **0**, 105,474 assertions.
- `python3 tests/dsd/test_p10.py --sox src/sox_ng --candidate test/sox_p10_candidate --results <outside-source>`:
  exit **0**, 63/63 cases.
- `python3 tests/dsd/test_p10_corrective_qualification.py`: exit **0**,
  16 inherited adversarial cases.
- `python3 tests/dsd/test_p10_ratification.py`: exit **0**,
  18 new adversarial cases; its fake PCM positive receipt is a *schema-only*
  test, not a real-world audio run.
- `python3 tests/dsd/test_p10_soak_receipts.py --unit test/dsd_test_p10 --results <outside-source>`:
  exit **0**, 4/4 idempotence cases.
- `python3 tests/dsd/qualify_p10_ratification.py --check`: exit **2**, the
  documented nonzero disposition for an **INCOMPLETE**, non-promoted phase.

The first full DSD run timed out during P07; two subsequent full runs exited
0, including a final run after correcting uninitialized-report compiler
warnings. Structured command/exit evidence and machine-path-sanitized logs
are stored under `tests/dsd/results/P10_ratification_2026-10-10/`.
No new real-world hardware soak, external PCM corpus, spectral analysis or
prepared-host performance benchmark was claimed in this round.

## Continuation instructions

To complete P10, obtain **genuine independently sourced ordinary PCM** audio
outside this archive, including 44.1-kHz and 48-kHz source-clock families.
Run the candidate PCM-to-DSD composite at all three native rates, and commit
actual source provenance/hashes, candidate CLI exit and render records, gain
retries if required, exact frame counts, independently checked DSD bit-window
statistics and source/output levels normalized to the *SACD* reference.
The current `corpus_realworld.py` only handles DSD-origin audio: a separate
PCM runner or careful external collection is needed. The collector accepts
`pcm-sources.json`, `pcm-unity.json` and optional `pcm-ladder.json` in the
existing corpus result folder. The schema/criteria are in
`ratify_p10_gates.py` and its pinned JSON standard. Check the claimed
provenance against the real external PCM before any positive certificate.

Re-run reviewer collector, review the versioned receipt and still keep P15
release activation separate. Do not mutate prior raw evidence or flip
profile `qualified` fields in anticipation of a future result. This worklog,
source checksums, immutable earlier evidence, new criteria and versioned
certificate allow resumption from the delivered tree without relying on
any context outside the bundle.
