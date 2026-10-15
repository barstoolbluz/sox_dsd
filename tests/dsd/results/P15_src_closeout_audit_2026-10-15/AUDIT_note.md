# Audit of the SRC acceptance bundle

Audited `P15_SRC_CODE_CLOSEOUT_BUNDLE_2026-10-15.tar.gz`, SHA-256
`a20c0e25ac4bd490d953d1c9dfbb587bdfb96fbe573c30975acb97df416665af`, applied to
`fb612f2b`. Our checks, which have been wrong before.

## Form: they complied

100 KB, a cumulative patch plus `CHANGED_FILE_LIST.txt`, not a tree. `git apply
--check` clean on `fb612f2b`. 15 files, 2,488 insertions, 4 deletions. That
avoids the trap of the previous round, where a tree reply built from our
stripped snapshot presented 2,455 spurious deletions.

All three deliverable forms are present: normative language in
`DSD_DESIGN.md` §8.6.1, a machine-readable criterion at
`tests/dsd/reference/p15_src_numerical_criteria.json`, and a checker at
`tests/dsd/p15_src_envelope_review.py`.

## They refused the threshold we asked for, and were right to

We asked for a number bounding the sample-wise residual against the
independent reference. They declined: a residual measured against a
*differently designed* polyphase filter "does not admit an arithmetic-error
threshold", and the criterion records
`different_transfer_samplewise_disposition: DIAGNOSTIC_NOT_AN_ACCEPTANCE_THRESHOLD`.

In its place §8.6.1 asserts transfer-function limits: absolute passband error
<= 0.0001 dB across the effective profile passband, and composite
stopband/folded-alias transfer <= -160 dB. That is a property of the filter
rather than of a comparison between two different filters, which is the right
shape and not what we had in mind.

## What it disposes, and what it opens

Verified by running their reviewer: all **36 fractional cells** disposed
`DIFFERENT_TRANSFER_RESIDUAL_OUT_OF_SCOPE`, 9 identity-FIR numerical cases
accepted scoped, 324 cross-ISA observations inspected, 81 source-bound scalar
cells. So no cell is left measured-with-no-threshold.

It also corrects a reading of ours. We had described the integer-ratio cells as
pure cascade with no SRC. The criterion states `native_hz % pcm_hz != 0 is
historical naming only; never an SRC-bypass test`, and the review records
`integer_ratio_additional_src_cells: 36` with `src_active: 72`. Our earlier
characterisation was wrong.

Two mandatory items are now open that were not named before:

| item | state |
|---|---|
| `mandatory_full_chain_numeric` | `OPEN_MISSING_INDEPENDENT_EFFECTIVE_SRC_OPERATOR` |
| `mandatory_composite_response` | `OPEN_MISSING_CERTIFIED_EXTREMA_AND_COHERENT_ALIASES` |

Their new `p15_current_closeout.py` separates substance from bookkeeping, which
is what we asked for, and names exactly two substantive open gates:
`P15-v1-and-v2-composite-SRC-acceptance` and
`P15-DSD256-direct-2x-and-matched-comparator`. `release_status BLOCKED`,
`p16_authorized False`.

So the envelope question is closed and it was not the last blocker. We told the
operator we could not promise it would be, and it was not.

## The P10 lineage break is not repaired

`p15_release_manifest.py` still reports `unexpected changed/missing P10 pinned
input docs/dsd/DSD_DESIGN.md`. The new closeout reviewer accounts for it
separately, recording `reviewed_design_changes: 1` alongside 30 byte-identical
and 4 later executable source changes, which we read as the design edit being
acknowledged rather than the pin being restored. The manifest and the new
reviewer therefore disagree, and we have changed neither.

## One test of theirs we changed

`test_p15_current_closeout.py` asserted
`sum(missing_expected_bulk_payloads) == 3508`, which is the count of bulk
payloads absent from the stripped 23 MB snapshot we sent: 945 `arrays/*.npz`,
1,807 `*.state`, 756 `graph-raw`. On the full branch those files are present,
so the reviewer correctly reports 0 missing and `full_raw_replay_possible
True`. The assertion now accepts 0 or 3508 and additionally checks replayability
when nothing is missing. Requiring 3508 would have meant asserting our own
evidence is incomplete.

That is the second time a reply has encoded our stripped snapshot as if it were
the repository. The convention needs stating in the dispatch itself, not only
in the reply instructions.

## Gates

`make check` 0, `make check-dsd` 0 at 36 pass / 0 fail, both of their suites
pass, manifest 11,134 entries all verifying.
