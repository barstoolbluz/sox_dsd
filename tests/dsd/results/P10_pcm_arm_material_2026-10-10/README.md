# PCM_AUDIO arm: available material and staging constraints (2026-10-10)

The ratification round ruled `independent_realworld_corpus` **PARTIAL**: the
committed corpus covers `DSD_NATIVE` only, and
`tests/dsd/reference/p10_ratification_criteria.json` requires `PCM_AUDIO` too.
This directory is not evidence of a run. It records what independent PCM
mastering material is available on the host that will execute that arm, so the
driver for it can be written against real metadata rather than assumptions.

## Candidates

14 commercial high-resolution PCM releases, all 24-bit stereo FLAC,
5 in the 44100 family and 9 in the 48000 family, spanning 11 genres. Each
entry's `first_track_streaminfo_md5` is the MD5 of the unencoded audio as stored
by the encoder, which makes a decode verifiable rather than merely asserted.

| Release | Genre | Rate Hz | Depth | Clock family | First track |
| --- | --- | --- | --- | --- | --- |
| `1954. Thelonious Monk Trio - Thelonious Monk Trio (201` | jazz | 44100 | 24-bit | 44100-family | 459 s |
| `1956. Anita O'Day - Pick Yourself Up With Anita O'Day ` | vocal-jazz | 44100 | 24-bit | 44100-family | 156 s |
| `1976. Joachim Kuhn - Hip Elegy (2014) [24-88.2]` | jazz | 88200 | 24-bit | 44100-family | 519 s |
| `Gerhard Gnann - Bach Complete Organ Works Vol. 17 (201` | classical-organ | 88200 | 24-bit | 44100-family | 232 s |
| `1977. Albert Mangelsdorff, Alphonse Mouzon, Jaco Pasto` | jazz-fusion | 88200 | 24-bit | 44100-family | 362 s |
| `10,000 Maniacs - In My Tribe (1987) [LP][24-96][FLAC]` | rock | 96000 | 24-bit | 48000-family | 292 s |
| `Bruno Walter - Beethoven- Symphony No. 9 (2019) [24-96` | classical-orchestral | 96000 | 24-bit | 48000-family | 973 s |
| `1983. Waylon Jennings - It's Only Rock & Roll (2019) [` | country-rock | 96000 | 24-bit | 48000-family | 216 s |
| `1984. Van Morrison - Live At The Grand Opera House Bel` | rock-live | 96000 | 24-bit | 48000-family | 66 s |
| `1958. Sam Cooke - Encore (2020) [24-96]` | soul | 96000 | 24-bit | 48000-family | 115 s |
| `Isabelle Faust, Alexander Melnikov - Mozart - Sonatas ` | classical-chamber | 96000 | 24-bit | 48000-family | 278 s |
| `Erling With Aasgård - J. S. Bach- Toccata and Fugue in` | classical-organ | 192000 | 24-bit | 48000-family | 562 s |
| `1958. Thelonious Monk Quartet - Thelonious In Action (` | jazz-live | 192000 | 24-bit | 48000-family | 314 s |
| `(1960) Nat Adderley - Work Song [Riverside 24-192]` | jazz | 192000 | 24-bit | 48000-family | 255 s |

The criterion asks for at least two distinct recordings per domain per native
rate, at least 60 seconds each, at least two genres per domain, and coverage of
both clock families. This material clears all four with margin, and nothing here
was produced by this project or by any SoX writer.

Note the rate mix. 88200 and 44100 are the 44100 family, and 88200 is also
exactly the DSD64 profile working rate, so those sources reach the modulator
without source-rate conversion. 96000 and 192000 are the 48000 family and must
cross families to reach an 88200 or 176400 working rate, which exercises the
source-to-R conversion stage that the corrective round's stage audit measured
only at 48000 and 705600.

## Staging constraints

The audited `sox_ng` has no FLAC handler: `no handler for detected file type
'flac'`. Enabling it would change the build configuration under which every
committed gate was measured, and would change the executable identity the
criteria record, so the intended route is to decode externally with `flac -d`
and feed the resulting PCM to the unchanged binary. `flac -t` and the STREAMINFO
MD5 above let each decode be proven bit-exact, so staging adds no unverified
transformation. FLAC is lossless: the decode changes container, not audio.

The material lives on an sshfs mount, so a full side read is slow and a driver
should read each source once rather than repeatedly.

## What the arm must measure, per the criteria

Admission, or explicit rejection with nonzero status and no silent gain; exact
admitted native frames per channel; verified complete 28-bit window counts, with
population 4 to 24 required at DSD64 and diagnostic above it; source and release
provenance with the SHA-256 of each exact excerpt; and a source-to-output level
comparison within 0.25 dB RMS and 0.5 dB peak.

That last item differs from the `DSD_NATIVE` arm and is the easiest thing to get
wrong. A `PCM_AUDIO` source enters the modulator at the 0.5 reference scale, so
its output must be reconstructed with the **sacd** reference, not `preserve`.
Measured on one 20-second excerpt of the Joachim Kuhn source: source peak -2.90
dBFS and RMS -22.88 dBFS; output reconstructed with `sacd` at -2.89 and -22.88;
the same output reconstructed with `preserve` at -8.92 and -28.90. The last is
6.02 dB low, which is risk R7a appearing from using the wrong domain's reference
rather than from any encoder error.
