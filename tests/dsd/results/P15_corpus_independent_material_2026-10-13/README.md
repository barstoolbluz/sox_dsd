# P15 independent-material corpus: DSD and PCM arms

Addresses `P15-current-independent-codec-and-hardware-corpus`, whose delivered
evidence note read "Historical external excerpts not present for independent
rerender". These are current-revision runs on the integrated P15 tree against
the same privately held commercial material the P10 corpus used.

The recordings are not bundled with this software. What is recorded here is
measurement output only: no absolute paths, no external audio.

## DSD arm, 18 commercial releases, six per native rate

| arm | result | agreement with P10 |
|---|---|---|
| unity | 14 of 18 admitted, 4 refused | **18 of 18 verdicts identical** |
| attenuated, -0.1 dB | 15 of 18 admitted | 15/18 identical, one field differs (below) |
| ladder, the 4 refused sources | all 4 admitted | **all 4 admitting gains identical**: -0.1, -0.25, -1.0, -1.0 |

All 18 excerpt SHA-256 digests are byte-identical to the P10 record, so the
material and the excerpt extraction are provably the same, not merely similar.

## PCM arm, 17 commercial releases at three native rates

51 measurements, **all admitted at unity, zero failures**, reproducing P10's
PCM result. Every source was identity-checked by FLAC STREAMINFO MD5 against
`P10_pcm_arm_material_2026-10-10/pcm-candidate-inventory.json` before use, so
these are provably the same recordings that inventory describes. FLAC is
decoded by the external `flac` binary, leaving the audited executable's build
configuration unchanged.

Two of the 19 inventoried releases carry no STREAMINFO MD5 and the driver
refuses them, as at P10. 17 is the usable set, not a sample.

## One difference from P10, located to a phase window

`01 - Cantata BWV 110_ 1. Chorus.dsf` reports `min_ones28` 7 where P10 recorded
8, under identical gain, with identical excerpt SHA-256 and identical output
byte count (84672604), and `max_ones28` unchanged at 21. So the encoded
bitstream content differs for this one source by one window's population.

Measured, not inferred:

| build | `min_ones28` |
|---|---|
| P10 `63872844`, rebuilt and rerun today | 8 |
| `f13dda14`, pre-decode-optimization | 7 |
| P15 tree, run 1 | 7 |
| P15 tree, run 2 | 7 |

That rules out two explanations. The decode optimization did not cause it,
since `f13dda14` predates it and already reads 7. And it is not environment or
measurement drift, since P10's own build still yields 8 on this host today. The
change is in our code, between `63872844` and `f13dda14`.

**Not a criterion failure.** Both 7 and 8 sit well inside the required 4 to 24.
Nothing else moved across 18 sources: every admission verdict, every ladder
gain, every excerpt digest and every other recorded field matches P10.

A bisect across P11, P12, P13 and P14 was running when this was written; its
result belongs in a follow-up. Our suspicion is P11 replacing P10's
compile-time inline FIR with runtime-dispatched tier kernels, which would alter
the reconstruction feeding the encoder, and this is the one source of eighteen
whose minimum population sits nearest the edge. P11's own bit-identity evidence
would not have caught it: those six comparisons were native repack, not the
reconstruct-then-encode composite path this corpus exercises. **That is a
hypothesis, not a finding.**

## What this gate does and does not cover

It covers independent **material**: 35 commercial releases the project did not
generate, through the real CLI effect graph, at every supported native rate.

It does **not** cover independent **hardware**. No playback device or DSD DAC is
exercised. We considered it and judged it near-worthless without a digital
capture path: a DoP or `.dsf` file is the same serialisation already verified
bit-exactly against baseline, so handing it to a player tests the player, and a
device locking would only confirm what byte inspection already shows. With an
S/PDIF, AES or ADAT input available, a send-and-capture comparison would test
something genuinely untested, that the bytes survive a real transport and clock.
Absent that, the hardware half is **unmet for a stated reason**, not passed.

Whether the gate closes therefore depends on what "hardware" was meant to
require. We state the coverage and leave the determination.

No default changed, no profile promoted, no gate status altered in the delivered
release manifest.
