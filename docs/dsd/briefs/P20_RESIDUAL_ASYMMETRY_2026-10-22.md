# Why does the DSD512 order reduction cost 37 dB where DSD1024 cost 3.67?

Working-set bundle `sox_dsd-75f8e8c3-working-set.tar.zst`, 8 MB
sha256 9cc1b8e058bbee966c9a527f35a447b399d643292d226eaecbffe2bcb92f4345
`sox_dsd/main` at 75f8e8c3. One file, no parts.

2,462 files present, 49,964 omitted, plus the 1,351 `.npz`.
`INCLUDED_FILES.txt` and `OMITTED_FILES.txt` ship beside it. The P15
historical validators and the sixteen `test_p15_*.py` refuse on the
omissions; do not repair those by editing assertions, fabricating
receipts or touching the P00 index.

The measurement in question is
`tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/verify/audio-compare.json`.
Our full soak evidence is beside it, including all 66 `.state`
snapshots this time, so every digest can be recomputed independently.

## What we want

An explanation, and a statement of intent.

Your own `p20_audio_compare.py`, run unmodified on the prepared host, puts
the corrected DSD512 candidate's reconstruction residual **37.1 dB above**
the original's. Your DSD1024 correction measured 3.67 dB for what looks like
the same change.

| | v1, 8th order | v2, 7th order | delta |
|---|---|---|---|
| DSD1024, your figures | -202.45 dBFS | -198.77 dBFS | 3.67 dB |
| DSD512, ours | -200.14 dBFS | **-163.04 dBFS** | **37.1 dB** |

Same order reduction, the same CLANS-7 binary64 coefficient words, only the
native clock differs. Lower oversampling at DSD512 should cost more, so the
direction is unsurprising; the magnitude is what we cannot account for.

Two questions.

**Is 37 dB the expected cost of seventh order at 22,579,200 Hz?** If it
follows from the clock and the order, say so and we will record it as
designed rather than as a surprise. If it does not, we would rather find out
now than after a capability decision cites this evidence.

**Is -163 dBFS where you intended to land?** It is roughly 19 dB below what
24-bit PCM can represent, so we are not calling it a defect and we are not
asking you to chase it. We are asking whether it is the number you chose.

## What we measured

One invocation, your tool, your in-tree frozen mastering coefficients, your
SciPy upfirdn chain, 128:1, six halfbands and one mastering stage, fitted
fundamental and DC over 0.4 to 1.2 seconds.

    stimulus            282,240 frames, peak 0.5012, RMS 0.3407
    analysed            141,120 PCM frames per version
    fundamental peak    0.2506 for both
    fitted DC           -1.7e-13 and -2.0e-13
    clipping            0 for both
    fund/residual       188.12 dB v1, 151.02 dB v2
    source digest       b8e8d07fa56c346147850c32e1faeead2ef3aab0dbd681435083176a8a52cd4d

The tool declares itself `comparison_only` and not an audio oracle, and we
are treating it that way.

## What we think may make the comparison unfair

Your DSD1024 v1 is the eighth-order candidate that goes nonfinite after
roughly 33.1M frames. Its -202.45 dBFS was necessarily measured in a window
before that failure. If the two deltas were taken under materially different
conditions then the 3.67 against 37.1 contrast is not a like-for-like
comparison and the asymmetry may be an artifact of ours. Say so if that is
the case.

## What this does not block

The DSD512 sustained-soak obligation is closed. The v2 candidate passed the
nominal gate at min28 7, longest run 5, over 81,285,120,000 frames with zero
nonfinite states and 6.0% guard utilisation. We are not reopening it.

No capability is enabled, `qualified=0` stands, and all twelve P18 rows
remain disabled. The continuum-extrema waiver is unchanged:
`docs/dsd/amendments/CONTINUUM_EXTREMA_WAIVER_2026-10-21.md`.

Our reading is fallible, and on this one we are explicitly unsure.
