# Commercial-source encode test, DSD512, 2026-10-22

Threadripper 7970X, scalar kernel. Five real tracks through three modulators,
fifteen renders, all completing.

Every encoder result before this was synthetic: tones, full-scale DC, bounded
noise, multitone. This asks whether real program material behaves differently,
because crest factor and transient density are not what synthetic signals
exercise, and because the historical 0.7-amplitude noise program did overload
the 0.5 envelope.

## Result: all three modulators pass on all five tracks

| stim | peak | CLANS-7 | o7-r5-a20 | o7-r8-a20 |
|---|---|---|---|---|
| src1 | 0.356 | 10-17, run 3 | 10-18, run 4 | 10-17, run 4 |
| src2 | 0.174 | 12-16, run 3 | 12-16, run 3 | 12-16, run 3 |
| src3 | 0.332 | 11-17, run 3 | 11-18, run 3 | 11-17, run 3 |
| src4 | 0.369 | 10-18, run 3 | 10-18, run 3 | 10-18, run 4 |
| src5 | 0.451 | 10-18, run 3 | 9-18, run 4 | 10-18, run 4 |

Population range, then longest constant-bit run. Zero nonfinite states, zero
monitor overloads, zero bad frames and exact frame counts in all fifteen:
2,032,128,000 for the 90-second stimuli and 1,807,841,280 for the 80-second
one. Candidates ran under `--render-candidate` with their own host-trained
frozen guards; the baseline ran under `--render` with its compiled P20 guards.

## Real music is gentler than the synthetic composite

This is the finding worth carrying.

| | min ones28 | longest run |
|---|---|---|
| synthetic nominal soak, r8 | 7 | 7 |
| synthetic nominal soak, r5 | 7 | 6 |
| commercial material, worst over 5 tracks | 9 | 4 |

The band is 7 to 22. Real tracks sit at 9 to 18 with runs of 3 to 4, where the
synthetic program reaches 7 to 21 with runs of 6 to 7. Music lacks the
sustained DC and long constant stretches the synthetic composite deliberately
includes.

Two consequences. The `r8` longest-run growth flagged in the 3,600-second
soak, 7 against the baseline's 5, **does not reproduce on real material**,
where r8 and the baseline differ by at most one. And these gates do not
discriminate between the three modulators on commercial input: all three are
equivalent here, so the choice between them rests on spectral performance,
not on stability against real programs.

## Stimulus provenance

`stimulus-manifest.tsv` identifies each stimulus by size, duration and
SHA-256. Source titles and paths are omitted: the material is licensed and
private. Each is a 90-second excerpt taken 30 seconds in, mono-mixed,
resampled to the encoder's 176,400 Hz working rate and scaled to the 0.5
mastering reference. Sources were two 96 kHz 24-bit vinyl rips, a 44.1 kHz
16-bit master, and one deliberately renormalised to land at 0.451, just under
the envelope. Nothing in the source library was modified.

## Scope

Nominal commercial material at one native rate on one kernel. It is not an
audio-quality assessment, has no listener or device component, and does not
qualify a profile or enable a capability. ISA tiers beyond scalar remain a
separate assessment.

## Two invocation errors of ours, corrected

The first baseline attempt used `--render-candidate`, which sets
`experimental=1` and resolves profiles only in the experimental table, so
`encode.mastering.v2.dsd512` was never found and returned code 2 with no
report. The second extracted guard bounds as "the first eight-element list"
in the guard JSON, which can return `training_max_abs_state`, the observed
maxima, instead of `bounds`, the 16x ceilings. Neither was a finding about
CLANS-7. The baseline figures above come from plain `--render` with its
compiled guards, and the failed attempts are not included in this directory.
