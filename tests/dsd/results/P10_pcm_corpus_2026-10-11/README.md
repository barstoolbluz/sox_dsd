# P10 independent real-world corpus, PCM_AUDIO arm (2026-10-11)

**Coverage: PASS.** 51 measurements, 17 independent commercial PCM releases
at each of the three native rates, all admitted at unity reference with no
attenuation, every frame count exact, every window count exact, every level
comparison inside tolerance, and the DSD64 28-bit population inside 4 to 24
throughout.

This closes the `PCM_AUDIO` half of `independent_realworld_corpus`. It does not
promote anything: `approved_for_profile_promotion` is `False` in the
record, and the collector's own note says this covers only the PCM_AUDIO domain.

## Result

| | |
| --- | --- |
| Measurements | 51 (17 releases x 3 native rates) |
| Admitted at unity | 51 of 51 |
| Needed explicit attenuation | 0 |
| Complete 28-bit windows examined | 40,303,869,246 |
| Population, all rates | 6 to 22 |
| DSD64 population requirement | 4 to 24, met |
| Peak delta range | -0.29 to +0.05 dB (tolerance 0.5) |
| RMS delta range | -0.07 to +0.00 dB (tolerance 0.25) |
| Frame and window counts exact | all |

Genres: 13. Clock families: 44100-family, 48000-family, with
10 releases in the first and 7 in the second.

| Source rate Hz | Releases | Family |
| --- | --- | --- |
| 44100 | 2 | 44100-family |
| 88200 | 3 | 44100-family |
| 96000 | 5 | 48000-family |
| 176400 | 5 | 44100-family |
| 192000 | 2 | 48000-family |

Both profile working rates are represented by native material: 88200 sources
reach DSD64 without source-rate conversion and 176400 sources reach DSD128 and
DSD256 the same way. The 44100, 96000 and 192000 sources all cross to a working
rate and so exercise the source-to-R conversion stage.

## Method

Driven by `tests/dsd/corpus_pcm.py` from the hotfix round, which implements the
criterion in `tests/dsd/reference/p10_ratification_criteria.json`. We executed
it; we did not write it, and we did not write the standard it applies.

60-second excerpts from 30 seconds in, each source read once from its remote
mount and all work done on local temporary copies, never the original. Every
FLAC decode is verified against the stored STREAMINFO MD5 and a `flac` CRC test,
so feeding externally decoded audio to the unchanged binary adds no unverified
transformation. The encoder binary is the audited build with no FLAC handler
compiled in, which keeps the executable identity the criteria record.

Output levels are reconstructed with the **sacd** reference, which is the
correct one for this domain: an ordinary PCM source enters the modulator at the
0.5 reference scale, so reconstructing with `preserve` would read 6.02 dB low
and manufacture risk R7a out of nothing. The `DSD_NATIVE` arm uses `preserve`
for the same reason in reverse.

A gain ladder of -0.1, -0.25, -0.5, -1.0, -2.0 and -3.0 dB was available for any
excerpt rejected at unity. Nothing used it.

## Why nothing was rejected here, unlike the DSD arm

Four of eighteen DSD-origin sources were rejected at unity because preserve
reference maps DSD full scale to 1.0, putting the 0.5 envelope at -6.0206 dBFS,
which commercial DSD masters sit close to. An ordinary PCM source is scaled by
0.5 instead, so the same envelope sits at PCM full scale and the material
carries about 6 dB more headroom. These releases peak well below that, so the
asymmetry is expected rather than surprising, and it is the reason the criterion
requires both domains measured with their own reference.

## Material excluded, and why

Two releases in `pcm-candidate-inventory.json` could not be used. Van Morrison,
*Live At The Grand Opera House*, has no STREAMINFO MD5 and a 66-second first
track, short of a 30-second offset plus 60-second excerpt. Erling Aasgard,
*Bach Toccata and Fugue*, has no STREAMINFO MD5. The driver refuses both, which
is correct: without the stored MD5 a decode cannot be proven bit-exact, and that
proof is what licenses decoding outside the audited binary. The inventory listed
them without recording that their MD5 was absent; that omission is ours.

The remaining 17 clear every cardinality requirement with margin: 17 recordings
per native rate against a minimum of 2, 13 genres against 2, and both clock
families.

Figures are from one host. The audio is not in this repository.
