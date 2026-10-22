# Operator qualification run, 2026-10-22

Prepared host, AMD Ryzen Threadripper 7970X. Executed on the operator side
because neither half can be done by the model: commercial DSD512 media, and
hour-long runs on real hardware.

Two results, and they point in opposite directions.

## DSD512 decoding: 12 of 12 tracks pass

`p17_media_qualification.py` over 12 commercial NativeDSD DSD512 tracks,
22,579,200 Hz stereo, 22 GB, whole files, both reconstruction profiles.
Every case `PASS_FUNCTIONAL_ONLY`, no failure and no timeout.

Tracks are identified by hash. No filename, path or PCM appears in any
receipt, by the harness's design: the media is licensed and private.

Worth carrying into any capability decision: reconstruction runs at
**0.63x real time**, 14.3M native frames/sec against a 22.58 MHz clock.
Adequate for file conversion, not for playback on this host.

The receipts also stamp their own limits. `device_interoperability` is
`NOT_CLAIMED` and `independent_reference_qualification` is
`UNRUN_NOT_COLLECTED`; this is functional evidence, not an audio-quality
certificate.

## DSD512 encoding: a real defect, found only by the soak

Four uninterrupted 3,600-second soaks, dedicated cores, 81.3 and 162.6
billion native frames.

| run | profile | input | min ones28 | longest run | verdict |
|---|---|---|---|---|---|
| `d1024-v2` | `encode.mastering.v2.dsd1024` | nominal | 7 | 5 | **PASS_SOAK_INPUT_GATE** |
| `d512-v2` | `encode.mastering.v1.dsd512` | nominal | **6** | 10 | **FAIL** |
| `d1024-v1` | `encode.mastering.v2.dsd1024` | overload | 6 | 5 | UNVERIFIED_EXECUTION |
| `d512-v1` | `encode.mastering.v1.dsd512` | overload | 6 | 8 | UNVERIFIED_EXECUTION |

`encode.mastering.v1.dsd512` fails the 28-bit population gate on a
**nominal, non-overloading** program: one 28-bit window held 6 ones where
the band is 7 to 22. Its longest constant run is 10 against 5 for the
corrected DSD1024 candidate.

Everything else is clean. Zero nonfinite states, zero monitor overloads,
every expected frame processed, all 61 segment snapshots present and
matching, and peak guard utilisation 6.3%, far inside the frozen ceilings.
The failure is bitstream population, not state divergence.

The two `original-v1` runs stopped at the interpolation-envelope gate on
peak 0.500287, marginally above the 0.5 reference. That is a deliberate
overload being correctly rejected, not a defect, and it is why their
execution is unverified rather than failed.

The corrected seventh-order DSD1024 candidate passed, which is the second
thing sustained testing has settled that short runs could not: the model's
own reproduction found the eighth-order candidate going nonfinite after
~33.1M frames, and this run carries its replacement past 162 billion.

## What this supports

**DSD512 read-only: the evidence supports enabling it.** Decoding is
unaffected by an encoder bitstream defect, and 12 of 12 commercial tracks
decode whole under both profiles.

**DSD512 writing: blocked, on a measured failure.** Not a missing
certificate or an unrun gate. `encode.mastering.v1.dsd512` fails a gate the
project already enforces, on ordinary input, over an hour.

Nothing here qualifies a profile or enables a capability. All twelve P18
high-rate rows remain disabled.

## Omitted

Per-segment `.state` snapshots, 134 files of intermediate checkpoints; the
final state of each run is retained and its digest is recorded in the
execution receipt.
