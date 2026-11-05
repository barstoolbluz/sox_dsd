# Using SoX DSD

SoX DSD converts PCM, native DSD, and DSD-over-PCM files with the familiar
`sox [options] input [output-options] output [effects]` command line. The
input and output formats decide whether to decode, encode, or simply repack
DSD. You normally do not need DSD-specific flags.

This guide describes the interface implemented by the November 2, 2026 CLI
redesign and the November 4, 2026 loud-encode controls, built from SoX
DSD 1.0.4. For all SoX options and effects, consult
`man sox`, `man soxeffect_ng`, and `man soxformat_ng`. `sox --help-dsd` displays
short examples.

## Basic conversions

```sh
# DSD to an ordinary WAV. Qualified mastering v2 reconstruction is automatic.
sox music.dsf music.wav

# Specify a PCM output rate and bit depth. File-specific flags precede output.
sox music.dsf -r 96k -b 24 music-96k.wav

# A different PCM container, if supported by this build.
sox music.dff -b 24 music.flac

# PCM to DSD128; bit clock and qualified encoder are chosen automatically.
sox music.wav -r dsd128 music.dsf

# PCM to DSD64: omitting -r selects DSD64 for PCM-origin native DSD output.
sox music.wav music.dsf

# Change DSD container without decoding or encoding.
sox music.dsf music.dff
sox music.dff music-copy.dsf
```

The format suffix identifies WAV, DSF, or DSDIFF (`.dff`). For filenames
without recognizable suffixes, use SoX's normal `-t` format option. WSD is
read-only. DST-compressed DSDIFF is not supported.

### Sample rate and precision

`-r 96k` specifies 96,000 PCM frames per second. `-r dsd128` specifies
5,644,800 **one-bit DSD frames per second**, and is valid only for DSF/DSDIFF
output. Both forms retain the normal SoX placement rule: `-r` before the
output filename changes **output** format. Existing numeric rates such as
`-r 5644800` remain valid. Named rates are `dsd64`, `dsd128`, `dsd256`,
`dsd512`, `dsd1024` (case-insensitive).

Without `-r`, DSD64 decoding produces 88.2 kHz PCM; DSD128/256/512/1024
decoding produces 176.4 kHz PCM. WAV output defaults to signed 24-bit PCM.
Other PCM containers use their closest supported conventional lossless depth.
Specify `-b 24` when a particular output format allows it and you require it.
Supported explicit reconstruction PCM rates are 44.1, 48, 88.2, 96, 176.4,
192, 352.8, 384, 705.6 and 1411.2 kHz; the selected profile and container
must also support the request.

## Loud PCM masters: clipping and headroom

PCM samples below 0 dBFS can overshoot **between** samples after
reconstruction/interpolation. Plain `sox in.wav out.dsf` uses a fast, one-pass
clip-and-warn path with a rate-dependent ceiling. At DSD128/256, its default
also applies a constant 0.9 linear gain (-0.91515 dB) **before** the clip
check. This avoids hard-clipping ordinary PCM peaks below full scale, but
reduces the overall output level even for quiet inputs. At DSD64/512/1024 the
default gain is 1. Clipping warnings report any remaining overloads; the
modulator state/numerical guards remain active.

```sh
# Normal, fast, one-pass conversion; report if interpolation clips.
sox loud.wav -r dsd128 loud.dsf

# Fixed 2 dB cut before modulation. No scan, no automatic normalization.
sox --headroom 2 loud.wav -r dsd128 reduced.dsf

# Measure the full interpolated peak and cut to the rate's clipping ceiling.
sox --auto-headroom loud.wav -r dsd128 measured.dsf

# Alternatively, reject an over-limit peak instead of clipping it.
sox --dsd-clip error loud.wav -r dsd128 strict.dsf

# Require strict behavior after measured headroom, and keep the measurements.
sox --dsd-clip error --auto-headroom --report encode.json \
  loud.wav -r dsd128 measured.dsf
```

`--headroom` accepts a **nonnegative attenuation** in dB (`0` through `120`),
not a signed gain: `--headroom 2` means exactly a 2 dB cut and replaces the
implicit 0.91515 dB reduction. `--headroom 0` explicitly requests unity gain;
it is **not** equivalent to the DSD128/256 default. `--auto-headroom`
measures the actual source-rate conversion, prefilter, final interpolation
and its finite tail. It applies **one shared attenuation across all channels**,
without boosting quiet audio. The limit is 0.45 for DSD128/256 and 0.5 for
DSD64/512/1024 (in modulator units, with 0.5 corresponding to 0 dBFS).
At DSD128/256 the plain default and measured mode may produce different
levels even when neither clips: default reduces all input by 0.91515 dB,
whereas measured mode leaves already-safe material unchanged. The latter is
preferable if retaining the original level is important. The two choices
cannot be combined. Both work with an explicit `pcmdsd` effect, and both
leave native DSD bit-preserving repacks and PCM-only operations unchanged
(the flags are rejected when no composite encoder is present).

Automatic measurement uses a PCM-rate temporary file to handle long
programmes and non-seekable inputs without storing them in memory. It runs
the interpolation twice, uses more disk space/I/O, and takes longer than
one-pass encoding. It does **not** silently substitute a different SDM
profile. The `--plan` policy names the selected mode and
`encoder.warning_clip_ceiling` and `encoder.planned_linear_gain` (null for
the not-yet-measured automatic mode), while `--report` records
`clip_ceiling_applied`, `headroom_applied_db` (including the implicit cut), and
`clipped_interpolated_samples` for each executed encoder channel, as well as an
`encoder_interpolation` clipping aggregate and a report warning when clipping
occurs. A strict-mode failure removes a partial regular output file. The other
numeric and state bounds still apply in every mode.

## Native DSD versus processing

A direct DSF-to-DSDIFF conversion (or the reverse) at the same bit clock,
with no PCM-domain operations, **repackages the native bitstream**. It does
not run a reconstruction FIR or noise-shaping encoder. A different output
DSD bit clock, gain, resampling, or ordinary audio effects require a PCM
processing stage and usually a re-encode for native DSD output.

```sh
# Native repacking, without altering the DSD pulses.
sox concert.dsf concert.dff

# DSD64 to DSD128 is NOT a native repack: it requires decode/re-encode.
sox concert.dsf -r dsd128 concert-upconverted.dsf

# Apply an audio effect in reconstructed PCM, then write a WAV.
sox concert.dsf filtered.wav highpass 20
```

Native channel identity is preserved where the output format can represent
it. The command rejects a change that would silently discard a known
identity unless you explicitly select `--dsd-layout-loss warn` and the
writer supports the resulting layout. The optional `--dsd-layout` assigns
speaker roles when input metadata does not provide them.

## DoP transport

DoP packages each group of 16 chronological native DSD bits into a 24-bit
PCM word with an alternating marker. It **does not** reconstruct musical PCM.
Its apparent PCM rate is the source DSD rate / 16. DoP audio requires a
receiver that understands this transport.

```sh
sox --dop concert.dsf transport.wav
sox --plan --dop concert.dsf transport.wav

# The equivalent low-level SoX effect remains available.
sox concert.dsf transport.wav dop
```

| Source | DoP PCM carrier rate |
| --- | ---: |
| DSD64 | 176,400 Hz |
| DSD128 | 352,800 Hz |
| DSD256 | 705,600 Hz |
| DSD512 | 1,411,200 Hz |
| DSD1024 | 2,822,400 Hz |

`--dop` uses the existing terminal `dop` effect, not an independent
conversion engine. The output must support lossless signed 24-bit PCM. Do
not add PCM resampling, ordinary audio effects, or a second `dop` effect
when packaging unmodified native bits. Wrong carrier rates and output
precision are errors, not automatic substitutions. File support does not
guarantee that a particular DAC or media player can accept the stream.

## See what will happen without converting

```sh
sox --plan concert.dsf planned.wav
sox --plan concert.wav -r dsd512 planned.dsf
sox --plan --dop concert.dsf transport.wav
```

The command prints JSON showing the input/output domains, sample rates,
steps, qualified identities, and `executable` result. It reads input
metadata but never opens an audio output. `--plan` is a preflight, not a
promise that source decoding or modulation cannot fail at runtime.

## Record what actually happened

```sh
sox --report decode.json concert.dsf concert.wav
sox --report encode.json concert.wav -r dsd128 concert.dsf

# Put a plan into a named JSON file rather than stdout.
sox --plan --report planned.json concert.dsf planned.wav
```

`--report` writes a final JSON record after closing audio, with native-bit
statistics, profile and kernel identities, clipping/stability diagnostics,
and conversion status as available. It does not request different audio
processing. Report paths cannot alias the input or audio output. `--report -`
writes JSON to stdout only if audio does not use stdout. Reports are for
DSD conversions; PCM-only commands continue to use normal SoX diagnostics.

## Qualified profiles for advanced use

The normal profile is **mastering**; you do not need to specify it. For DSD
reconstruction, `--decode mastering` and omitting `--decode` select the
identical qualified mastering-v2 bank matched to the source bit clock.
`--decode conservative` selects the older mastering-v1 bank, while
`--decode wideband` selects the qualified wideband-v1 bank. Exact versioned
identities are available when reproducibility matters:

```sh
# An exact decoder bank, tied to DSD64 input.
sox --decode decode.mastering.v1.dsd64 source64.dsf older.wav

# An exact decoder bank, tied to DSD128 input.
sox --decode decode.mastering.v2.dsd128 source128.dsf current.wav

# Wideband reconstruction with explicit bandwidth policy.
sox --decode wideband --dsd-bandwidth strict source64.dsf \
  -r 176400 wide.wav

# An exact qualified encoder, tied to DSD128 output.
sox --encode encode.mastering.v1.dsd128 source.wav -r dsd128 output.dsf
```

For encoding, `--encode mastering` selects the qualified mastering-v1
modulator for DSD64/128/256 and qualified mastering-v2 CLANS-7 for
DSD512/1024. A mismatched version-pinned native bit clock causes an error.
Unsupported or unqualified legacy composite profiles do not acquire
qualification through these selectors. Only interpolated samples above the warning ceiling are clipped;
nonfinite samples and modulator-state guard failures still stop the
conversion. At DSD128/256 that ceiling is below the strict 0.5 envelope. Use
`--dsd-clip error` to turn input-level overshoots into fatal errors, or
`--headroom` / `--auto-headroom` to avoid clipping without modifying the
mastering profile. See [Loud PCM masters](#loud-pcm-masters-clipping-and-headroom).

The low-level `rate -v` effect changes the resampling response and can
therefore change one-bit output relative to an unqualified legacy `rate`
followed by `dither -p 1`. It is not the default qualified encoder path.

Additional controls: `--dsd-bandwidth adapt|strict` (default `adapt`, which
allows a reduced passband when decoding to a lower PCM rate),
`--dsd-level preserve|sacd` (default `preserve`, with `sacd` multiplying the
reconstructed amplitude by two), `--dsd-clip warn|error` (default `warn`),
`--headroom DB`, `--auto-headroom`, `--dsd-layout`,
`--dsd-layout-loss`, and `--dsd-mode native` (rejects any
route that would require PCM processing). For compatibility,
`--dsd-mode legacy` still accepts PCM-only SoX operations, but **never**
bypasses qualified routing for a DSD input or output. DSD rate changes,
DSD-to-PCM decoding and PCM-to-DSD encoding use the same planned graph
as automatic mode, whether or not `--plan` or `--report` is present.
To select unqualified low-level modulation explicitly, use the `sdm`
effect; do not rely on implicit legacy container conversion.

With an explicit `dsdpcm` effect, the global `--decode` and `--dsd-level`
settings also control the decoder and reconstruction gain. Effect-local `-p`
and `-l` settings remain available; incompatible global and local selections
are rejected before conversion.

The `SOX_DSD_KERNEL_FIR` and `SOX_DSD_KERNEL_SDM` environment variables
select supported execution tiers for reproducible numerical checks. The traditional `sdm`, `dsdpcm`,
`pcmdsd`, and `dop` effects remain accessible in the normal SoX grammar.

## Common mistakes and how to fix them

| Error | What to do |
| --- | --- |
| `-r dsd128` used with a WAV output | Use `-r 96k` for PCM, or write `.dsf`/`.dff` for DSD128. |
| Named DSD rate placed before the input filename | Place `-r dsd128` between input and output. |
| Pinned decoder native clock differs from the source | Select the matching `decode.*.dsdNNN` ID or omit `--decode`. |
| Pinned encoder native clock differs from the destination | Select the matching encoder ID or omit `--encode`. |
| DoP rejected for 16-bit / lossy output | Use a 24-bit-capable lossless destination, such as `.wav`. |
| DoP fails with PCM processing effects | Convert to ordinary PCM instead, or remove the effects for native DoP. |
| Strict bandwidth refuses the requested PCM rate | Increase the output PCM rate, or use the default `adapt` policy. |
| Native repacking refuses channel roles | Inspect the source and destination layout; use advanced role policy only when metadata loss is acceptable. |

## Older 1.0.4 DSD-specific command spellings

The new interface replaces `--dsd-decode`, `--dsd-encode`, `--dsd-plan`,
and `--dsd-report` with `--decode`, `--encode`, `--plan`, and `--report`.
It changes the DSD-routing default from legacy to automatic, and makes
explicit `--decode mastering` select the same mastering-v2 profile as the
implicit default. Earlier mastering-v1 behavior remains available using
`--decode conservative` or an exact `decode.mastering.v1.dsdNNN` ID.
These changes affect SoX DSD-specific 1.0.4 controls, not conventional
SoX/SoX-NG syntax. See [the migration table](MIGRATION_P15.md).
