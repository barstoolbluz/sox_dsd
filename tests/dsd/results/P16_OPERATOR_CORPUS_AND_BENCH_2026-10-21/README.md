# P16 soak: real-corpus parity and a grounded benchmark

2026-10-21, operator-side evidence. Not a phase gate and not a
certification. Two things the model could not do: run real commercial DSD
material, and measure on a prepared physical host.

## Corpus parity: 11 of 11, byte-identical

Packed and expanded output compared by SHA-256 through the real CLI. Every
run asserted the `P16: native packed input enabled` debug marker, so a file
where the packed path silently failed to engage is reported as NOTENGAGED
rather than counted as a pass. None was.

The eleven files cover every structural signature present in a 5,881-file,
2.8 TB pool, chosen by signature rather than by volume:

| signature | why it matters |
|---|---|
| dsf DSD64/128/256 2ch, tail 0 | the common cases |
| dsf DSD64 **5ch** | multichannel, absent from the model's fixtures |
| dsf DSD128 2ch **tail 7** | maximum partial final byte; one such file in 2.8 TB |
| dsf DSD256 2ch **tail 3** | partial final byte at the highest rate, two files |
| dff DSD64/128/256 2ch | third-party DFF cluster layouts |

The bolded rows are the packed path's bit-addressing edges. The model's
6,480-combination matrix covered all eight bit offsets synthetically; these
are the same edges as written by commercial encoders.

`corpus-manifest.tsv` identifies each file by size and SHA-256. Source paths
are deliberately omitted: they are a private media library, not evidence.
Nothing in the source pool was modified; the files were copied to scratch.

## Benchmark: real, small, and now bounded

Prepared host, AMD Ryzen Threadripper 7970X, governor performance, boost
off, pinned to cpu8. `benchprep.sh noise` measured **0.0% spread over 15
runs** against a 2.0% gate before any timing was taken.

Paired and interleaved with alternating arm order, so drift cancels rather
than accumulating in one arm. 20,000-sample bootstrap over the paired
ratios.

| material | expanded | packed | speedup | CI95 |
|---|---|---|---|---|
| real DSD256 DSF, 65 s | 25.961 s | 24.714 s | **1.051x** | [1.039, 1.063] |
| real DSD256 DFF, 122 s | 49.088 s | 45.184 s | **1.084x** | [1.076, 1.087] |

Both intervals exclude 1.0, so the gain is real. Both are small.

`model-harness-at-ceiling.json` is the model's own harness run at its
maximum, 5 s and 20 repetitions pinned to the same core, giving 1.055x DSF
and 1.081x DFF. Its packed DSF arm spread 24.8% on a host whose noise floor
is 0.0%, because a 5-second clip is short enough for process startup to
dominate. On 65 and 122 seconds of real audio the spreads fall to 8.2% and
1.4%. The model's figures were sound; they were just measured on too little
audio to be stable.

## What this does not show

No claim about disk I/O, total RSS or whole-pipeline traffic. The 32:1
figure elsewhere is interstage payload accounting at the reader-to-DSP
boundary; DSF and DFF files are already packed on disk.

One host, one core, one output rate per container, two containers at one
native rate. No multi-host qualification, no long-duration soak of the
borrowed-pointer lifetime contract under seek churn, and nothing about
DSD512 or DSD1024, which P17 owns.

`source-pool-integrity.md` records the 21 damaged files and 14
DST-compressed DFF found while surveying the pool. The DST files are intact
and unsupported, not broken; SoX reports them as "invalid DSDIFF chunk
layout", which is a misleading message worth fixing independently.
