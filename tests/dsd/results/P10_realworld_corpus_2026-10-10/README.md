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

## Why these four and not the others: the envelope is the SACD reference level

The envelope of 0.5 is -6.0206 dBFS, and in preserve reference DSD full
scale maps to 1.0, so the admitted ceiling sits exactly at the PCM-full-scale to
0 dB SACD convention that section 5.4 describes. Measuring each excerpt's
reconstructed sample peak shows that this, and not interpolation overshoot, is
what decides admission.

| Source | Native Hz | Preserve peak dBFS | Amplitude | Admitted | Predicted from level | Actually needed |
| --- | --- | --- | --- | --- | --- | --- |
| `01 - Out On The Weekend` | 11289600 | -13.05 | 0.2226 | yes | - | - |
| `01 - Shine On You Crazy Diamond (Parts` | 2822400 | -11.39 | 0.2695 | yes | - | - |
| `Pink_Floyd~Wish_You_Were_Here~side1` | 11289600 | -11.33 | 0.2713 | yes | - | - |
| `A1 Do Nothin' Till You Hear From Me` | 5644800 | -10.07 | 0.3137 | yes | - | - |
| `Genesis~Foxtrot~side1` | 5644800 | -10.00 | 0.3162 | yes | - | - |
| `Kate_Bush~The_Dreaming_-_(1982)_[Japan` | 11289600 | -9.44 | 0.3373 | yes | - | - |
| `01 - Cantata BWV 110_ 1. Chorus` | 2822400 | -7.53 | 0.4202 | yes | - | - |
| `01 - Better Git It In Your Soul` | 11289600 | -7.53 | 0.4202 | yes | - | - |
| `Michael_Jackson~Thriller~side1` | 5644800 | -7.21 | 0.4360 | yes | - | - |
| `01 - Start Me Up` | 5644800 | -7.20 | 0.4365 | yes | - | - |
| `01 - Birdland` | 2822400 | -7.17 | 0.4380 | yes | - | - |
| `Pink_Floyd~Meddle~side1` | 5644800 | -7.17 | 0.4380 | yes | - | - |
| `01-So What` | 11289600 | -7.12 | 0.4406 | yes | - | - |
| `01. Born Under A Bad Sign` | 11289600 | -7.01 | 0.4462 | yes | - | - |
| `01 - Little Girl Blue` | 2822400 | -6.02 | 0.5000 | no | 0.00 dB | 0.10 dB |
| `01 - ROCKIT` | 2822400 | -5.83 | 0.5111 | no | 0.19 dB | 0.25 dB |
| `A1. Too Hot To Handle` | 5644800 | -5.40 | 0.5370 | no | 0.62 dB | 1.00 dB |
| `01 - Bone Machine` | 2822400 | -5.22 | 0.5483 | no | 0.80 dB | 1.00 dB |

Amplitude 0.5 separates the two groups with no exceptions across all 18 sources.
The 14 admitted sources peak between -13.05 and -7.01 dBFS, so all are at
least 7 dB below DSD full scale, which is the ordinary mastering practice for
this format. The 4 rejected sources peak between -6.02 and -5.22 dBFS: each is
mastered hotter than the convention the envelope encodes.

Interpolation overshoot is the marginal term rather than the cause. Subtracting
the attenuation predicted from the sample peak alone from the attenuation that
actually admitted each source leaves between 0.06 and 0.38 dB, and for
`Little Girl Blue`, whose peak sits at the convention exactly, the whole
0.10 dB requirement is overshoot. An earlier reading of this evidence framed
overshoot as the cause; the measurement above does not support that, and the
level threshold does.

The practical consequence, which we believe but have not established beyond
this corpus, is that a DSD-origin remodulation workflow at unity reference
admits material mastered to the SACD convention and rejects anything mastered
above it, with the required correction equal to roughly the amount by which the
master exceeds -6.0206 dBFS plus a small overshoot allowance. Whether that is
the right product behaviour is a policy question this evidence does not settle.

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
