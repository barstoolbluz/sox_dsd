# PCM_AUDIO arm: available material and staging constraints (2026-10-10)

The ratification round ruled `independent_realworld_corpus` **PARTIAL**: the
committed corpus covers `DSD_NATIVE` only, and
`tests/dsd/reference/p10_ratification_criteria.json` requires `PCM_AUDIO` too.
This directory is not evidence of a run. It records what independent PCM
mastering material is available on the host that will execute that arm, so the
driver for it can be written against real metadata rather than assumptions.

## Candidates

19 commercial high-resolution PCM releases, all 24-bit stereo FLAC,
10 in the 44100 family and 9 in the 48000 family, spanning 14 genres.
Each entry's `first_track_streaminfo_md5` is the MD5 of the unencoded audio as
stored by the encoder, which makes a decode verifiable rather than merely
asserted. None of it was produced by this project or by any SoX writer.

| Release | Genre | Rate Hz | Clock family | First track |
| --- | --- | --- | --- | --- |
| `1954. Thelonious Monk Trio - Thelonious Monk Trio (2014)` | jazz | 44100 | 44100-family | 459 s |
| `1956. Anita O'Day - Pick Yourself Up With Anita O'Day (2` | vocal-jazz | 44100 | 44100-family | 156 s |
| `1976. Joachim Kuhn - Hip Elegy (2014) [24-88.2]` | jazz | 88200 | 44100-family | 519 s |
| `1977. Albert Mangelsdorff, Alphonse Mouzon, Jaco Pastori` | jazz-fusion | 88200 | 44100-family | 362 s |
| `Gerhard Gnann - Bach Complete Organ Works Vol. 17 (2018)` | classical-organ | 88200 | 44100-family | 232 s |
| `Neil Young & Crazy Horse - re-ac-tor (1981) [FLAC] {DVD-` | hard-rock | 176400 | 44100-family | 213 s |
| `Neil Young - American Stars 'N Bars (1977) [FLAC] {DVD-A` | country-rock | 176400 | 44100-family | 180 s |
| `Neil Young - Hawks & Doves (1980) [FLAC] {DVD-A  24-176.` | folk-rock | 176400 | 44100-family | 136 s |
| `Neil Young - On the Beach (1974) [FLAC] {DVD-A  24-176.4` | folk-rock | 176400 | 44100-family | 163 s |
| `Neil Young - Songs for Judy (1976) [FLAC] {HDTracks  24-` | folk-live | 176400 | 44100-family | 205 s |
| `10,000 Maniacs - In My Tribe (1987) [LP][24-96][FLAC]` | rock | 96000 | 48000-family | 292 s |
| `1958. Sam Cooke - Encore (2020) [24-96]` | soul | 96000 | 48000-family | 115 s |
| `1983. Waylon Jennings - It's Only Rock & Roll (2019) [24` | country-rock | 96000 | 48000-family | 216 s |
| `1984. Van Morrison - Live At The Grand Opera House Belfa` | rock-live | 96000 | 48000-family | 66 s |
| `Bruno Walter - Beethoven- Symphony No. 9 (2019) [24-96]` | classical-orchestral | 96000 | 48000-family | 973 s |
| `Isabelle Faust, Alexander Melnikov - Mozart - Sonatas fo` | classical-chamber | 96000 | 48000-family | 278 s |
| `(1960) Nat Adderley - Work Song [Riverside 24-192]` | jazz | 192000 | 48000-family | 255 s |
| `1958. Thelonious Monk Quartet - Thelonious In Action (20` | jazz-live | 192000 | 48000-family | 314 s |
| `Erling With Aasgård - J. S. Bach- Toccata and Fugue in D` | classical-organ | 192000 | 48000-family | 562 s |

## Why the rate mix matters

| Rate Hz | Releases | Family | Relation to the profiles |
| --- | --- | --- | --- |
| 44100 | 2 | 44100-family | needs source-rate conversion |
| 88200 | 3 | 44100-family | DSD64 working rate |
| 96000 | 6 | 48000-family | needs source-rate conversion |
| 176400 | 5 | 44100-family | DSD128 and DSD256 working rate |
| 192000 | 3 | 48000-family | needs source-rate conversion |

Both working rates are now covered by native material, which matters for
interpreting results. A source already at the working rate reaches the modulator
without source-rate conversion, so 88200 exercises that path for DSD64 and
176400 exercises it for DSD128 and DSD256. The 44100, 96000 and 192000 sources
all cross to a working rate and therefore exercise the source-to-R conversion
stage, which the corrective round's stage audit measured only at 48000 and
705600. An earlier version of this inventory had no 176400 material at all, so
the no-conversion path would have been tested at DSD64 only.

The 176400 releases are all one artist, which is a narrower provenance than the
rest of the set. They are distinct commercial albums from different years and
two different transfer routes, DVD-Audio and HDTracks, but a round weighing
independence should know they share an artist and catalogue lineage.

## Staging constraints

The audited `sox_ng` has no FLAC handler: `no handler for detected file type
'flac'`. Enabling it would change the build configuration under which every
committed gate was measured, and would change the executable identity the
criteria record, so the intended route is to decode externally with `flac -d`
and feed the resulting PCM to the unchanged binary. `flac -t` and the STREAMINFO
MD5 above let each decode be proven bit-exact, so staging adds no unverified
transformation. FLAC is lossless: the decode changes container, not audio.

Two host facts a driver must respect. The 176400 material lives in a **read-only
library** that must not be mutated: copy a source out before doing anything with
it, and never decode, rename or write in place. Both that library and the other
material sit on sshfs mounts, so reads are slow and each source should be read
once rather than repeatedly.

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
