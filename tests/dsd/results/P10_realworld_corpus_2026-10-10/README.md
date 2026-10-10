# P10 independent real-world corpus, prepared host (2026-10-10)

**What ran: 18 commercial DSD releases, six per native rate, through the real
CLI effect graph.** 14 were admitted at unity reference with no attenuation;
the remaining 4 were admitted once an explicit attenuation between 0.1 and 1.0 dB
was applied. Every admitted encode produced an exact frame count, a 28-bit
window population inside the required 4 to 24, and a reconstructed level equal
to its source.

This is evidence toward design 10.5's `independent_realworld_corpus` gate. It
does not mark that gate passed; see "What this does not claim".

## Corpus

18 tracks spanning 12 genres (alt-rock, art-pop, blues, classical, folk-rock, funk-electronic, fusion, hard-rock, jazz, pop, prog-rock, rock) and labels
including MFSL One-Step, Analogue Productions, Audio Fidelity, Venus, BIS, HDTT
and Stax. The DSD64 arm was extracted from SACD ISOs with
`sacd_extract -s -2 -c -t 1`; the DSD128 and DSD256 arms are native release
files, one of them DSDIFF rather than DSF. None of this material was produced
by this project or by any SoX writer, which is what makes it independent.
`sources.json` records release identity, genre, rate and each excerpt's sha256,
and deliberately records no filesystem paths. The audio is not in the repository.

Each source contributes a fixed 120-second excerpt from 30 seconds in, cut in
the DSD domain so no reconstruction precedes the measurement.

## Chain

    native DSD input -> automatic reconstruction at the profile working rate
      -> trim (-> explicit gain) -> one composite pcmdsd at the native rate

Working rates are 88.2 kHz for DSD64 and 176.4 kHz for DSD128 and DSD256. The
composite is unqualified, so the graph is exercised with the uninstalled
`test/sox_p10_candidate`; the release executable refuses these profiles by
design. The explicit `trim` matters: a composite placed directly after native
DSD input is refused by the P05 preflight, which is correct, and that rejection
must not be mistaken for an envelope overload.

## Unity reference, no attenuation

| Source | Genre | Native Hz | Result |
| --- | --- | --- | --- |
| `01 - Little Girl Blue` | jazz | 2822400 | rejected, peak 0.500009841, first-report minimum 0.000171 dB |
| `01 - Shine On You Crazy Diamond (Parts I` | rock | 2822400 | admitted, ones 10-19, frames exact, ΔRMS +0.00 dB |
| `01 - Bone Machine` | alt-rock | 2822400 | rejected, peak 0.500589558, first-report minimum 0.0102 dB |
| `01 - Cantata BWV 110_ 1. Chorus` | classical | 2822400 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `01 - ROCKIT` | funk-electronic | 2822400 | rejected, peak 0.500377380, first-report minimum 0.00655 dB |
| `01 - Birdland` | fusion | 2822400 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `Pink_Floyd~Meddle~side1` | rock | 5644800 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `Genesis~Foxtrot~side1` | prog-rock | 5644800 | admitted, ones 9-20, frames exact, ΔRMS +0.00 dB |
| `01 - Start Me Up` | rock | 5644800 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `Michael_Jackson~Thriller~side1` | pop | 5644800 | admitted, ones 7-22, frames exact, ΔRMS +0.00 dB |
| `A1 Do Nothin' Till You Hear From Me` | jazz | 5644800 | admitted, ones 9-20, frames exact, ΔRMS +0.00 dB |
| `A1. Too Hot To Handle` | hard-rock | 5644800 | rejected, peak 0.500124000, first-report minimum 0.00215 dB |
| `Pink_Floyd~Wish_You_Were_Here~side1` | rock | 11289600 | admitted, ones 9-19, frames exact, ΔRMS +0.00 dB |
| `01-So What` | jazz | 11289600 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `01 - Better Git It In Your Soul` | jazz | 11289600 | admitted, ones 7-21, frames exact, ΔRMS +0.00 dB |
| `01 - Out On The Weekend` | folk-rock | 11289600 | admitted, ones 10-19, frames exact, ΔRMS +0.00 dB |
| `01. Born Under A Bad Sign` | blues | 11289600 | admitted, ones 7-22, frames exact, ΔRMS +0.00 dB |
| `Kate_Bush~The_Dreaming_-_(1982)_[Japan_P` | art-pop | 11289600 | admitted, ones 8-19, frames exact, ΔRMS +0.00 dB |

Across the 14 admitted cases: 25,062,911,244 complete 28-bit
windows, population 7 to 22 against the admitted 4 to 24, every
frame count exact, RMS delta +0.00 dB in every case, and peak delta between
-0.01 and +0.02 dB.

That level result is the regression for risk R7a. Ordinary half scaling after a
preserve-level reconstruction would cost an extra 6.0206 dB, which the design
calls release-blocking. Reconstructing each encoded output reproduces its source
excerpt's level instead, so the reference calibration survives the round trip on
real material.

## Rejections, and what they actually require

The 4 rejected sources are the most heavily mastered in the corpus. Their
post-interpolation peaks exceed the section 7.2 envelope of 0.5 plus two
source-int32 LSBs by between 1e-5 and 6e-4, so rejection is the specified
behaviour rather than a defect.

The encoder's reported `minimum explicit attenuation` is a **lower bound only**.
It is computed at the first overloading sample, where the encoder stops, so it
describes that sample and not the excerpt. Given exactly that much headroom the
run proceeds further and meets a later, larger peak. Escalating until the
encoder admits the material measures the real requirement:

| Source | Native Hz | First-report minimum | Actually admitted at | Ladder steps | ones |
| --- | --- | --- | --- | --- | --- |
| `01 - Little Girl Blue` | 2822400 | 0.000171 dB | -0.10 dB | 2 | 6-22 |
| `01 - Bone Machine` | 2822400 | 0.0102 dB | -1.00 dB | 5 | 6-21 |
| `01 - ROCKIT` | 2822400 | 0.00655 dB | -0.25 dB | 3 | 6-22 |
| `A1. Too Hot To Handle` | 5644800 | 0.00215 dB | -1.00 dB | 5 | 7-22 |

The first report understates the requirement by roughly ten to one hundred
times. `Bone Machine` still overloads at -0.5 dB, implying unattenuated
interpolation peaks near 0.53. Reading that field as a sufficient correction
will under-attenuate and fail again later in the stream. A fixed -0.1 dB pass in
`corpus-attenuated.json` admits 15 of 18, the same point from the other side.

Once admitted, these four behave like the rest: exact frames, population inside
4 to 24, and level preserved.

## Why these four and not the others: source level against the SACD reference

The envelope of 0.5 is -6.020600 dBFS. In preserve reference DSD full scale
maps to 1.0, so the admitted ceiling sits at the PCM-full-scale to 0 dB SACD
convention of section 5.4. Each rejected excerpt's reconstructed source maximum
exceeds 0.5 on its own, before any interpolation is considered:

| Source | Source max abs | Attenuation implied by level alone | Ladder bracket | Level-implied value inside bracket |
| --- | --- | --- | --- | --- |
| `01 - Little Girl Blue` | 0.500128 | 0.0022 dB | (0.00, 0.10] dB | yes |
| `01 - Bone Machine` | 0.548224 | 0.7998 dB | (0.50, 1.00] dB | yes |
| `01 - ROCKIT` | 0.510970 | 0.1885 dB | (0.10, 0.25] dB | yes |
| `A1. Too Hot To Handle` | 0.536729 | 0.6157 dB | (0.50, 1.00] dB | yes |

The ladder tested 0, 0.1, 0.25, 0.5, 1.0, 2.0 and 3.0 dB, so each result bounds
the true requirement to the interval between the step that failed and the step
that admitted. For all four sources the attenuation implied by source level
alone falls inside that interval. **This corpus therefore establishes no
interpolation contribution at all**: every rejection is fully accounted for by
source level, and a contribution of exactly zero is consistent with every
measurement here.

An earlier version of this file attributed 0.06 to 0.38 dB to interpolation
overshoot. That was wrong. Those figures were the difference between the
level-implied minimum and whichever ladder step happened to succeed, so they
measured the ladder's step size and not the DSP. The error is recorded here
rather than quietly removed.

Quantifying interpolation overshoot needs the maximum absolute post-interpolation
sample compared against the maximum absolute source sample, which this evidence
does not contain. `report.peak` in `src/pcmdsd.c` tracks that maximum, but it is
logged only on the failure path, so a successful run never surfaces it and the
fourteen admitted sources yield no overshoot figure. On a failing run the logged
value is the running maximum at the abort point, which is why `Little Girl Blue`
reports 0.50000984 while its source maximum is 0.500128: the first offending
sample is not the largest. Surfacing that field on success, or a harness mode
that feeds an external file through the stage observer the corrective round
added, would measure it.

## Scope of this explanation

Two limits matter. First, this applies to preserve-reference DSD remodulation,
where the reference tag is 1.0. An ordinary PCM mastering source is scaled by
0.5 instead, so it carries about 6 dB more headroom before the same envelope and
nothing here describes its behaviour. Second, amplitude 0.5 separated admitted
from rejected across these 18 sources with no exceptions, but that is an
observation about this corpus and not an admission rule. The design deliberately
tests the signal after interpolation and reference scaling rather than the stored
samples, so a source below 0.5 may still exceed the envelope once filtered, and
filtering may equally reduce a transient so that a source above 0.5 is not
guaranteed to be rejected. Nothing in this corpus exercises either case: the
fourteen admitted sources all peak at or below 0.4462 and the four rejected all
exceed 0.5, so the interesting region immediately around 0.5 is untested.

## Method and reproduction

    python3 tests/dsd/dsd_windows.py --self-check <small.dsf>
    python3 tests/dsd/corpus_realworld.py --sox src/sox_ng \
      --candidate test/sox_p10_candidate --sources <sources with paths> \
      --results <dir> [--gain -0.1 | --gain-ladder 0,-0.1,-0.25,-0.5,-1.0,-2.0,-3.0]

Bitstream statistics come from `tests/dsd/dsd_windows.py`, a vectorised reader
of the same container layouts `reference/verify.py` walks one bit at a time.
The slow decoder is the authority and is far too slow for hundreds of millions
of frames, so the fast reader is checked against it first:
`reader-self-check.json` records `bit_identical_to_oracle: true` over
564,480 frames and 2 channels. Window counting is chunked with a 27-bit
overlap so no window straddling a chunk boundary is missed.

Taken on CPU 8 of an AMD Ryzen Threadripper 7970X with the bench preparation
still active. Timings here are not a performance claim.

## What this does not claim

`qualify_p10_corrective.py` hardcodes `independent_realworld_corpus` to `UNRUN`
and inspects no evidence path. Nothing here was edited to change that. The
design states no acceptance criterion for this gate: it was raised by P09's own
list of what it had not run and carried forward by P10's accounting, so what
constitutes a passing corpus - how much material, which rates, what tolerance -
is undefined. Setting that criterion while also executing the run would be
self-certification, so this records the corpus and its measurements and leaves
the criterion to be set.

Not covered: integrator state maxima and nonfinite-state counts, which are
internal to the encoder and not observable from a CLI run, since no harness mode
accepts an external audio file; those remain evidenced only by the generated
soaks. Analysis-v1 spur and residual measurement was not re-run against this
material.

P10 remains INCOMPLETE with all three profiles unqualified and promotion
blocked. Figures are from one host and one 120-second excerpt per release.
