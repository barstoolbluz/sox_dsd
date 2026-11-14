# Using SoX DSD 1.1.1

**A practical guide to native DSD, reconstruction, mastering encoding, DoP, and DSD diagnostics**

> **Scope.** This guide covers the DSD-specific behavior of **SoX DSD 1.1.1**, as implemented in the approved 1.1.1 source (tag `sox_dsd-1.1.1`). It assumes the ordinary SoX command structure and does not repeat general SoX-NG documentation for PCM editing, resampling, audio devices, or codecs. Examples use a POSIX-style shell. The source code and 1.1.1 release notes govern operational behavior; a separate, historical noise-shaper bench provides measured comparisons with stated limits.
>
> **Important:** A DSD output file can contain clipped or otherwise altered audio even when the command succeeds. In particular, the normal PCM-to-DSD encoder warns and clips excess interpolated peaks. Read the [headroom chapter](#5-encoding-levels-clipping-and-headroom) before encoding a loud master.

## Contents

1. [Start here: the commands you will use](#1-start-here-the-commands-you-will-use)
2. [How DSD processing works](#2-how-dsd-processing-works)
3. [Reconstruct DSD to PCM](#3-reconstruct-dsd-to-pcm)
4. [Reconstruction, encoding profiles, and measured tradeoffs](#4-reconstruction-encoding-profiles-and-measured-tradeoffs)
5. [Encoding levels, clipping, and headroom](#5-encoding-levels-clipping-and-headroom)
6. [Preserve native DSD, change rates, or use DoP](#6-preserve-native-dsd-change-rates-or-use-dop)
7. [Channel identity, metadata, and native statistics](#7-channel-identity-metadata-and-native-statistics)
8. [Plans, reports, and reproducible processing](#8-plans-reports-and-reproducible-processing)
9. [DSD command and effect reference](#9-dsd-command-and-effect-reference)
10. [Troubleshooting and verification](#10-troubleshooting-and-verification)

---

## 1. Start here: the commands you will use

SoX DSD normally decides whether to reconstruct, encode, or preserve native bits from the input and output formats. You do not need to select a DSD mode for an ordinary conversion.

| Task | Command |
|---|---|
| Convert DSF to normal WAV | `sox music.dsf music.wav` |
| Choose 24-bit / 96 kHz PCM | `sox music.dsf -r 96k -b 24 music-96k.wav` |
| Convert uncompressed DSDIFF to PCM | `sox music.dff -r 176400 music.wav` |
| Encode WAV to DSD64 | `sox master.wav master.dsf` |
| Encode to DSD128 | `sox master.wav -r dsd128 master.dsf` |
| Encode one track to DSD512 with measured headroom | `sox --auto-headroom master.wav -r dsd512 master.dsf` |
| Encode an album to DSD512 with one fixed cut ([how to choose it](#encoding-an-album)) | `sox --headroom 1.8 track.wav -r dsd512 track.dsf`, same value for every track |
| Change DSF container to DSDIFF, keeping native bits | `sox music.dsf music.dff` |
| Convert DSD64 to DSD128 (not bit-preserving) | `sox music64.dsf -r dsd128 music128.dsf` |
| Package DSD into a DoP WAV | `sox --dop music.dsf transport.wav` |
| Preview a conversion as JSON | `sox --plan music.dsf proposed.wav` |
| Convert and save a JSON report | `sox --report run.json music.dsf music.wav` |
| Inspect a DSD file | `soxi music.dsf` |

Check the installed executable:

```bash
sox --version
sox --help-dsd
sox --help-format dsf
sox --help-effect pcmdsd
```

If a different SoX executable appears on your `PATH`, its DSD behavior may differ. Keep input files and outputs under separate names, and inspect warnings and exit status. `--no-clobber` prompts before replacement; it is not a noninteractive fail-if-exists switch.

For the few format details you need here, the familiar SoX ordering still applies:

```text
sox [global options] input [output format options] output [effects...]
```

For example, `-r dsd256` **before the output filename** selects a DSD256 output bit clock; it does not change the input's declared clock.

## 2. How DSD processing works

Three very different operations can look similar at the command line:

| Operation | What SoX DSD does | Result |
|---|---|---|
| **Reconstruction** | Filters a one-bit source and produces multibit audio | DSD -> listening PCM |
| **Mastering encoding** | Converts PCM through interpolation and a qualified one-bit noise shaper | PCM -> native DSD |
| **Native repack** | Changes a native DSD container without reconstructing samples | DSF <-> DSDIFF at the same bit clock |
| **DoP** | Packages the existing DSD bits in marker-bearing 24-bit words | DSD -> transport, **not** listening PCM |

A native DSD signal has one bit per sample per channel. Its rate is a **bit clock**; `soxi -r` correctly reports millions of samples per second for DSF or DSDIFF. A DoP WAV has an apparent PCM rate, but its sample words carry DSD bytes and markers, not PCM music samples.

### Default profiles for DSD reconstruction and encoding

SoX DSD selects its reconstruction filter or encoder from the conversion direction and DSD bit clock. Decoder and encoder profiles describe separate algorithms.

- **DSD to PCM:** `mastering` is the default reconstruction filter at every clock; `wideband` is the optional alternative.
- **PCM to DSD:** the eighth-order SDM-8 `mastering` composite encoder is the only mastering encoder at every clock. DSD512 and DSD1024 use new, rate-specific SDM-8 coefficient tables.
- **Legacy route:** the original SoX `sdm` effect supports `sdm-4`–`sdm-8` and `clans-4`–`clans-8`. Explicit `rate -v RATE sdm -f NAME` effects are required; the `--encode legacy` selector alone does not insert them.

| DSD clock | Default reconstruction | Mastering encoder | Legacy route |
|---|---|---|---|
| DSD64 | mastering | SDM-8 | explicit `rate` + `sdm` |
| DSD128 | mastering | SDM-8 | explicit `rate` + `sdm` |
| DSD256 | mastering | SDM-8 | explicit `rate` + `sdm` |
| DSD512 | mastering | SDM-8, rate-specific zeros | explicit `rate` + `sdm` |
| DSD1024 | mastering | SDM-8, rate-specific zeros | explicit `rate` + `sdm` |

The mastering SDM-8 encoder descends from sigma-delta modulation work by **Måns Rullgård** in SoX-NG. It combines SoX DSD's interpolation chain, input-level policy, and numerical/state checks. The reconstruction FIR filters are separate designs.

*Qualified* means that a profile passed the release-authorization checks for its documented rate, gain mapping, and use. It does not mean perfect stability for all possible inputs, a guarantee of audible superiority, or universal device support. Section 4 explains the choices, and the separate [noise-shaper measurement report](NOISE_SHAPER_BENCH_2026-11-07.md) provides detailed test data.

### Native clocks and output rates

The `-r` option specifies the sample rate for both PCM and native DSD output. The value depends on the output format:

- **PCM output:** Specify a numeric sample rate in hertz, such as `-r 96000` for 96 kHz.
- **Native DSD output (DSF or DSDIFF):** Specify `-r dsd64`, `dsd128`, `dsd256`, `dsd512`, or `dsd1024`. These names are case-insensitive; numeric DSD bit clocks also work.

Place `-r` before the output filename to set the output rate.

For example:

```bash
# Convert DSD to 96 kHz PCM
sox input.dsf -r 96000 output.wav

# Convert PCM to DSD256
sox input.wav -r dsd256 output.dsf
```

The following table shows each native DSD bit clock, its default decoded PCM output rate, and the PCM carrier rate required for DSD over PCM (DoP).

| DSD rate | Native one-bit clock | Default decoded PCM output rate | DoP carrier rate |
|---|---:|---:|---:|
| DSD64 | 2,822,400 Hz | 88,200 Hz | 176,400 Hz |
| DSD128 | 5,644,800 Hz | 176,400 Hz | 352,800 Hz |
| DSD256 | 11,289,600 Hz | 176,400 Hz | 705,600 Hz |
| DSD512 | 22,579,200 Hz | 176,400 Hz | 1,411,200 Hz |
| DSD1024 | 45,158,400 Hz | 176,400 Hz | 2,822,400 Hz |

**When you omit `-r`:**

- **DSD-to-PCM:** SoX DSD uses the default decoded PCM output rate shown in the table.
- **PCM-to-DSD:** SoX DSD defaults to DSD64 when writing DSF or DSDIFF.
- **DoP:** The PCM carrier rate is determined by the native DSD bit rate. DoP transports DSD bytes inside PCM-formatted words without reconstructing the audio as PCM.

You can explicitly request PCM reconstruction rates of **44.1, 48, 88.2, 96, 176.4, 192, 352.8, 384, 705.6, or 1,411.2 kHz**. The selected decoder, bandwidth policy, and destination container may restrict which rates are valid.

When writing decoded PCM to WAV, SoX DSD defaults to **signed 24-bit PCM**.

### DSD file formats and limitations

SoX DSD supports three native DSD file formats. All three store one-bit DSD audio rather than reconstructed PCM, but they differ in their capabilities and restrictions.

| Format | Read | Write | Key limitation |
|---|---|---|---|
| DSF (`.dsf`) | DSD64–DSD1024 | DSD64–DSD1024 | Supports predefined speaker layouts, from mono through 5.1 surround |
| DSDIFF (`.dff`) | DSD64–DSD1024 | DSD64–DSD1024 | DST-compressed DSDIFF is not decoded |
| WSD (`.wsd`) | DSD64–DSD1024 | No | Input only; SoX DSD cannot write WSD files |

**DSF channel layouts.** DSF identifies audio channels by their speaker positions: front left, front right, center, low-frequency effects (LFE), and rear surrounds. It defines specific layouts rather than arbitrary channel arrangements. For example, four channels can represent either quadraphonic audio (front and rear left/right) or front left/right, center, and LFE. DSF supports up to 5.1 surround, but not 7.1. When converting to DSF, the source channels must correspond to one of its supported layouts. The `--dsd-layout` option assigns speaker roles to existing channels; it does not rearrange or mix them.

**DSDIFF compression.** DSDIFF can contain uncompressed DSD or losslessly compressed DSD using Direct Stream Transfer (DST). SoX DSD reads uncompressed DSDIFF but does not decode DST-compressed files. A `.dff` extension alone therefore doesn't guarantee that a file can be opened.

**DSD over PCM (DoP).** DoP isn't a native DSD file format. It's a transport method that packages native DSD bits into 24-bit PCM-formatted words, allowing DSD to travel over connections designed for PCM. The audio is not converted to PCM. A DoP-capable receiver must recognize the embedded markers and recover the DSD stream. Ordinary PCM processing, including volume changes and resampling, can corrupt it.

SoX DSD can produce DoP WAV files using `--dop`. See [Section 6](#6-preserve-native-dsd-change-rates-or-use-dop) for commands, carrier rates, and playback restrictions.

The read/write rates in the table describe SoX DSD 1.1.1 capabilities, not guaranteed compatibility with every DSD player or DAC.

## 3. Reconstruct DSD to PCM

A normal DSD-to-PCM command inserts the source-matched qualified reconstruction filter automatically. You do not need to name `dsdpcm` or a particular profile unless you want to override the default.

```bash
# Default output: 88.2 kHz for DSD64, 176.4 kHz for higher DSD rates.
sox source64.dsf decoded.wav

# Explicit PCM output format.
sox source128.dsf -r 96k -b 24 decoded-96k.wav

# Decode uncompressed DSDIFF.
sox recording.dff -r 192k -b 24 decoded-192k.wav

# Decode a read-only WSD input.
sox archive.wsd -r 176400 -b 24 decoded.wav

# Run a conventional PCM effect AFTER reconstruction.
sox recording.dsf -r 96k -b 24 filtered.wav highpass 20
```

A higher PCM output clock does **not** automatically select a wider reconstruction profile or create more recorded ultrasonic information. The decoder's own transfer function and the final output clock both influence what survives.

### Reference level: `preserve` and `sacd`

```bash
# Default: do not apply an extra x2 decoder-level gain.
sox --dsd-level preserve source.dsf decoded.wav

# Explicit SACD level convention: multiply reconstructed PCM by 2 (+6.0206 dB).
sox --dsd-level sacd source.dsf sacd-level.wav
```

`preserve` is the default. `sacd` changes amplitude; it is **not** normalization or clipping prevention. A raised reconstruction level can exceed the PCM output range. If you subsequently encode DSD again within the same processing graph, the planner also tracks the reference calibration so that a requested gain is not silently halved or doubled. Saved standalone PCM files do not carry that private in-process reference tag.

## 4. Reconstruction, encoding profiles, and measured tradeoffs

**Separate the two DSP directions.** A DSD-to-PCM *decoder* applies reconstruction FIR filters. A PCM-to-DSD *encoder* interpolates PCM and operates a one-bit noise-shaping modulator. Each profile selects a particular filter or modulator for the relevant native clock.

### 4.1 Reconstruction: the mastering default

A one-bit DSD signal carries shaped quantization noise, much of it ultrasonic. The mastering reconstruction filter retains its specified passband and suppresses unwanted high-frequency content. More output samples do not automatically increase the decoder's chosen source bandwidth.

| Native input | Mastering rated passband | Stopband begins | Intermediate PCM clock |
|---|---:|---:|---:|
| DSD64 | 20 kHz | 40 kHz | 88.2 kHz |
| DSD128 | 30 kHz | 60 kHz | 176.4 kHz |
| DSD256 | 40 kHz | 80 kHz | 176.4 kHz |
| DSD512 | 40 kHz | 80 kHz | 176.4 kHz |
| DSD1024 | 40 kHz | 80 kHz | 176.4 kHz |

The passband edge marks the last frequency covered by the specified flat-response region; the stopband edge marks where specified attenuation begins. Neither is a brick-wall cutoff or a listening-quality ranking. The design's transfer-function targets are described in [DSD design](DSD_DESIGN.md).

Compared with earlier releases, the default reconstruction filter may have a different passband. Record the product release and the selected decoder when comparing rendered PCM.

### 4.2 Selecting a decoder in 1.1.1

| Request | Result |
|---|---|
| No `--decode` | Mastering filter for the native DSD clock |
| `--decode mastering` | The same mastering filter |
| `--decode wideband` | Wideband reconstruction filter for the native DSD clock |
| `--decode decode.mastering.dsd128` | Exact mastering bank; DSD128 input required |
| `--decode decode.wideband.dsd256` | Exact wideband bank; DSD256 input required |
| `--decode conservative` or `--decode legacy` | Rejected obsolete selector |
| Obsolete versioned ID | Rejected |

```bash
# Default and explicit mastering select the same filter.
sox source64.dsf -r 176400 default.wav
sox --decode mastering source64.dsf -r 176400 mastering.wav

# Pin the DSD128 mastering decoder.
sox --decode decode.mastering.dsd128 source128.dsf \
    -r 176400 pinned.wav

# Choose the wideband alternative.
sox --decode wideband source128.dsf -r 352800 wideband.wav
```

To compare mastering and wideband, render the **same source** with the **same final PCM rate and level**. The distinct passbands may pass different amounts of shaped ultrasonic noise. These differences cannot be inferred just from source DSD clock.

### 4.3 Wideband: a deliberate alternative

`--decode wideband` retains a much broader DSD spectrum than mastering:

| Input | Wideband passband | Stopband begins | Intermediate PCM clock |
|---|---:|---:|---:|
| DSD64 | 35.28 kHz | 44.1 kHz | 88.2 kHz |
| DSD128 | 70.56 kHz | 88.2 kHz | 176.4 kHz |
| DSD256 | 141.12 kHz | 176.4 kHz | 352.8 kHz |
| DSD512 | 282.24 kHz | 352.8 kHz | 705.6 kHz |
| DSD1024 | 564.48 kHz | 705.6 kHz | 1,411.2 kHz |

This can help specialist measurement or deliberately broad-spectrum work, but it can also retain considerably more shaped ultrasonic noise. It uses a different reconstruction bank from mastering.

### 4.4 Output-rate policy: `adapt` versus `strict`

The destination PCM clock may be unable to represent the selected filter's full passband. `--dsd-bandwidth adapt` (default) allows a narrower effective result. `--dsd-bandwidth strict` rejects a route that cannot preserve it.

```bash
# DSD128 mastering has a 30 kHz passband; 44.1 kHz PCM cannot retain it.
sox source128.dsf -r 44100 adapted.wav

# The strict request is expected to fail on the same input and output clock.
sox --dsd-bandwidth strict source128.dsf -r 44100 refused.wav

# An output clock that can represent the 30 kHz passband.
sox --dsd-bandwidth strict source128.dsf -r 88200 strict-ok.wav
```

A 44.1 kHz destination is not inherently invalid for every mastering source: for DSD64 the selected passband is 20 kHz. The compatibility decision depends on the *selected filter* and the *destination rate*, not on a blanket rule about 44.1 kHz.

### 4.5 Encoding: one mastering encoder at every rate

The mastering composite encoder interpolates PCM and applies eighth-order SDM-8 noise shaping. The five native clocks have five rate-pinned IDs, with one authorized encoder per clock.

| Output clock | Mastering encoder ID | Coefficients |
|---|---|---|
| DSD64 | `encode.mastering.dsd64` | SDM-8 |
| DSD128 | `encode.mastering.dsd128` | SDM-8 |
| DSD256 | `encode.mastering.dsd256` | SDM-8 |
| DSD512 | `encode.mastering.dsd512` | SDM-8 with rate-specific zeros (`xz-k1p75`) |
| DSD1024 | `encode.mastering.dsd1024` | SDM-8 with rate-specific zeros (`xz-k2`) |

```bash
sox master.wav -r dsd256 master256.dsf
sox --encode mastering master.wav -r dsd1024 master1024.dsf
sox --encode encode.mastering.dsd512 master.wav -r dsd512 pinned512.dsf
```

The explicit encoder ID must match the requested destination clock. Obsolete versioned identifiers and `experimental` do not select an alternative encoder. `pcmdsd -p` accepts only mastering or its exact-rate IDs.

The 0.9 linear mastering gain is applied at every rate in warn and strict mode, unless a fixed or measured headroom setting replaces it. The input mapping and state guards still limit which material can be encoded safely. Full-scale sustained DC with `--headroom 0` has previously stopped the high-rate modulator; a successful bounded test is not an arbitrary-duration stability proof.

### 4.6 Noise-shaper measurements and their limits

The [historical noise-shaper study](NOISE_SHAPER_BENCH_2026-11-07.md) compares the legacy shapers with earlier mastering tables. The subsequent round03 rerun measured the **selected** mastering tables at DSD512 and DSD1024. Its results are in the handoff's `observed/round03/shaper-bench/`; the dated research report has intentionally not been rewritten as part of this change.

| Current mastering rate | Unwindowed in-band noise (dBFS) | Music-notch median (dBFS) | 20–50 kHz energy (dBFS) |
|---|---:|---:|---:|
| DSD512 | −261.8 | −197.3 (12 excerpts) | −208.1 |
| DSD1024 | below bench floor | −198.9 (3 excerpts) | −209.4 |

The digital reference and finite-bit-depth path limit these measurements. The music-notch numbers especially approach the source/reference floor; they cannot establish an unbounded signal-to-noise advantage or predict the output of a particular DAC. The tables are rate-specific production choices backed by the attached screening, DC and corpus evidence; earlier qualification certificates cover the algorithms and test conditions stated in those historical records. They do not independently certify every new coefficient word for arbitrary content. The new high-rate profiles report `certificate_sha256: null` in plans and `coefficient_certificate_sha256: null` in runtime receipts rather than attaching the previous tables' digest.

## 5. Encoding levels, clipping, and headroom

A PCM master may have samples below 0 dBFS but still overshoot between stored sample positions during interpolation. That reconstructed/interpolated peak is relevant to the one-bit encoder. SoX DSD therefore offers three related but distinct choices: **fast warn-and-clip**, **a fixed input cut**, and **measured headroom**.

### Normal one-pass encoding

```bash
sox master.wav -r dsd128 output.dsf
```

In the qualified PCM-origin path, the default:

1. Applies a fixed **0.9 linear gain** (about **-0.91515 dB**) ahead of the encoder's interpolated-peak check, at every DSD rate.
2. Warns and clips any remaining interpolated samples exceeding **0.45 modulator units** in magnitude. Here **0.5 units** corresponds to the PCM full-scale reference.
3. Still stops on nonfinite values, internal numerical failure, or modulator-state guard failure.

The fixed 0.9 gain applies even to quiet recordings. It is **not** an automatic level measurement, normalization, or a transparent limiter. A successful run with a clipping warning did alter the interpolated signal.

### Choose the policy to suit your material

| Goal | Example | Behavior |
|---|---|---|
| Fast default | `sox in.wav -r dsd128 out.dsf` | One pass; 0.9 gain, warn and clip above 0.45 |
| Known fixed attenuation, or one cut for a whole album | `sox --headroom 2 in.wav -r dsd128 out.dsf` | Exactly 2 dB cut **instead of** the implicit 0.9 gain |
| Avoid clipping on a single track while retaining the greatest safe level | `sox --auto-headroom in.wav -r dsd128 out.dsf` | Full interpolated-peak scan; cut chosen for this file, only if needed |
| Refuse clipping | `sox --dsd-clip error in.wav -r dsd128 out.dsf` | Strict bound of 0.5; default 0.9 mastering gain retained |
| Measured headroom plus strict checking | `sox --auto-headroom --dsd-clip error in.wav -r dsd128 out.dsf` | Scan, apply a shared cut, and fail if the final strict check rejects input |

`--headroom` accepts an attenuation from **0 to 120 dB**, not a signed gain or a target peak level. **`--headroom 0` explicitly requests unity gain**; it does not mean the implicit default. A fixed cut may still leave peaks above the warning ceiling, so it does not by itself guarantee zero clipped interpolated samples.

`--auto-headroom` measures the interpolated signal, including the finite tail, then chooses a **single gain across all channels** so their balance does not change. It never boosts quiet material, uses bounded RAM with temporary storage, and takes an additional measurement pass with more I/O. Its target is the **0.45 warning ceiling**, even when combined with strict checking. The scan does not substitute a different mastering profile. It measures each file on its own, so the tracks of an album can receive different cuts; see [Encoding an album](#encoding-an-album).

`--dsd-clip error` uses a **0.5 strict input envelope**, rather than the default warning ceiling of 0.45. It rejects overloads rather than clipping them. The **mastering encoder retains its 0.9 gain at all five native rates** under this policy, just as in warn mode. `--headroom DB` or `--auto-headroom` replaces the default gain, including for strict runs. DSD-origin re-encoding has a different amplitude reference; the PCM-origin peak bound cannot simply be transferred to that path. The separate modulator-state guards apply in either mode.

`--headroom` and `--auto-headroom` are mutually exclusive and apply only to mastering's composite encoder. They have no effect on the legacy low-level `sdm` route, bit-preserving native repacking, or ordinary PCM-only operations.

For a single level-sensitive track, prefer **`--auto-headroom`** when its extra pass and temporary-file I/O are acceptable. For an album, use one fixed `--headroom` for every track so the tracks keep their relative levels. For high-throughput conversion where the fixed reduction and possible clipping warnings are understood, the ordinary one-pass default may be preferable.

**What the prior music tests establish:** A separate high-rate test build completed 800 real-track encodes at DSD512/1024, including sample-peak-raised copies. However, the 1.1.1 release documentation records **194 input-stage clipping warnings among 400 peak-raised runs**. Those are distinct from the composite encoder's 0.45 modulator warnings. Completion shows that the tested encoder did not abort; it does **not** prove the peak-raising command preserved the source waveform. Avoid unnecessary upstream `-v` amplification when waveform preservation is the goal. The no-clipping conclusion from the earlier 27-job benchmark is specific to those fixtures and settings.

### See the actual applied gain and clip count

```bash
sox --plan --auto-headroom master.wav -r dsd128 proposed.dsf > plan.json
sox --auto-headroom --report encode.json master.wav -r dsd128 output.dsf
```

The plan identifies the headroom mode but cannot know the final measured cut before processing. The completed report exposes applied headroom and per-channel interpolated clip counts, plus clipping aggregates. Review those results and stderr warnings; do not infer "no clipping" solely from exit code zero.

### Encoding an album

`--auto-headroom` gives each file its own cut, which changes the levels of an album's tracks relative to one another. To keep them, measure every track, then encode them all with the same fixed cut:

```bash
# 1. Measure each track at the target rate; the audio is discarded
for f in album/*.wav; do
  sox --auto-headroom --report "${f%.wav}.json" "$f" -r dsd128 -t dsf /dev/null
done

# 2. Find the largest cut any track needs
jq -s '[.[].processing.encoder[].headroom_applied_db] | max' album/*.json

# 3. Encode every track with that cut, rounded up (here 1.8 dB)
for f in album/*.wav; do
  sox --headroom 1.8 "$f" -r dsd128 "${f%.wav}.dsf"
done
```

`--headroom` replaces the implicit 0.9 gain rather than adding to it, so `--headroom 1.8` is a 1.8 dB cut in total. If no track needs more than 0.915 dB, the default already avoids clipping, and step 3 can use the plain command. The measurement in step 1 costs a full encode per track.

## 6. Preserve native DSD, change rates, or use DoP

### Native repacking: DSF <-> DSDIFF

```bash
sox original.dsf repacked.dff
sox original.dff repacked.dsf
sox archive.wsd archived.dsf
```

At the same DSD clock, without PCM-domain changes and with representable layout metadata, SoX DSD copies the **native bitstream** into a new container. No reconstruction FIR or mastering encoder is invoked.

To refuse anything other than native bit preservation:

```bash
sox --dsd-mode native original.dsf repacked.dff
```

**Do not compare complete file hashes** to prove bit preservation. DSF and DSDIFF differ in framing, header fields, interleaving, and padding. To prove bit identity, compare correctly unpacked native bits, with channel order and final padding accounted for. `dsdstat` offers useful summary evidence, but identical counters do not prove identical bitstreams.

### Processing DSD or changing its rate

```bash
# Changing the DSD bit clock is a decode -> encode transformation.
sox source64.dsf -r dsd128 encoded128.dsf

# An ordinary audio effect also requires a reconstructed PCM stage.
sox source64.dsf -r dsd128 gain-adjusted128.dsf gain -3
```

Neither command is a native copy, and the result is **not bit-identical** to the original. Ordinary PCM effects (including channel mixing, gain, and filtering) act on reconstructed PCM, not directly on the one-bit pulse values. An explicit `--dsd-mode native` rejects routes that would need those stages.

### DoP is DSD transport, not audio reconstruction

```bash
sox --dop source64.dsf transport64.wav
sox --dop source512.dsf transport512.wav

# Equivalent explicit-effect form for advanced use.
sox source64.dsf -r 176400 -b 24 transport-explicit.wav dop
```

DoP groups native DSD bits into a **signed, lossless 24-bit PCM carrier** with alternating marker bytes. The apparent carrier PCM rate is the DSD bit clock divided by 16; see the clock table in Section 2. `--dop` chooses the exact carrier rate and representation. The explicit `dop` effect must come last.

**Do not play a DoP WAV into an ordinary PCM-only audio path.** The receiver must recognize DoP markers and accept the carrier rate. File creation proves neither that the DAC accepts high-rate DoP nor that software playback preserves the markers. Do not apply gain, resampling, or dither to a DoP carrier after packaging.

WSD is read-only. DST-compressed DSDIFF is not decoded. A conversion to ordinary WAV without `--dop` is **reconstructed PCM**, not DoP.

## 7. Channel identity, metadata, and native statistics

### Speaker roles and layout restrictions

Native DSD files may describe ordered speaker roles. `--dsd-layout` assigns roles to those **existing channel positions**; it does not rearrange samples or perform a downmix.

```bash
# Assign known stereo roles to a source that lacks a reliable layout.
sox --dsd-layout FL,FR source.dff labeled.dsf

# Permit a known layout to be lost, when intentional and supported.
sox --dsd-layout-loss warn source.dsf destination.dff
```

Names include `MONO`, `FL`, `FR`, `FC`, `LFE`, `BL`, `BR`, `SL`, `SR`, and `unknown`. Layout-loss policy defaults to **`error`**. A `warn` override cannot make an invalid DSF channel-role mapping legal. For unusual multichannel files, inspect the plan before committing to a conversion.

### `soxi`: native properties without decoding

```bash
soxi recording.dsf
soxi -r recording.dsf       # The one-bit DSD bit clock in Hz
soxi -c recording.dsf       # Channel count
soxi -b recording.dsf       # One bit per sample
soxi -e recording.dsf       # Encoding
soxi -D recording.dsf       # Duration in seconds
```

### `dsdstat`: statistics on the original native stream

```bash
# Native pass-through with bit statistics on stderr.
sox source.dsf inspected.dff dsdstat

# Additional filtered-level and frequency-band measurements.
sox source.dsf analyzed.dff dsdstat -a

# Keep the analysis separately from console output.
sox source.dsf analyzed-again.dff dsdstat -a 2> dsdstat.txt
```

`dsdstat` analyzes native one-bit data without reconstructing or changing its pulse stream. Its measurements include per-channel bit populations, run and excursion statistics, and (with `-a`) filtered software-level and band-power measurements. Short inputs can lack fully integrated band results because of warm-up exclusion. These statistics do not certify analog playback characteristics or establish full bit identity between two files.

## 8. Plans, reports, and reproducible processing

### Preflight: inspect the route without writing audio

```bash
sox --plan source64.dsf -r 96k proposed.wav > decode-plan.json
sox --plan master.wav -r dsd512 proposed.dsf > encode-plan.json
sox --plan --dop source64.dsf transport.wav > dop-plan.json
```

`--plan` produces JSON describing source/destination domains, clocks, chosen stages, profile IDs, and executability. It does not write an audio output and cannot anticipate every input-dependent clipping, runtime numerical, or I/O failure.

### A report of the conversion that actually ran

```bash
sox --report decode.json source64.dsf -r 96k decoded.wav
sox --report encode.json master.wav -r dsd128 encoded.dsf

# Write the plan to a named JSON file.
sox --plan --report proposed.json source64.dsf proposed.wav
```

`--report` records qualified profile and kernel identities, conversion status, and relevant audio diagnostics. **Adding a report does not change the selected processing route or audio output.** Keep the report path separate from audio inputs and outputs. Using `--report -` for stdout requires stdout not to be carrying audio simultaneously. Reporting is intended for DSD routes, not arbitrary PCM-only work.

### Pin execution kernels for diagnostic reproduction

```bash
SOX_DSD_KERNEL_FIR=scalar SOX_DSD_KERNEL_SDM=scalar \
    sox master.wav -r dsd128 scalar-test.dsf
```

Supported compiled kernel tiers depend on the CPU, OS, and build; named tiers include `scalar`, `sse2`, `avx1`, `avx2`, and `avx512`, with additional FMA variants where available. An unavailable forced tier is an error, not a silent fallback. For everyday work, leave dispatch automatic. These variables apply to qualified composite DSP contexts, not the separate low-level `sdm` effect.

## 9. DSD command and effect reference

### DSD-specific global options

The ordinary conversion syntax requires none of these. Place global options before the effects chain; placing them before the input makes the intent easy to read.

| Control | Accepted choices / meaning |
|---|---|
| `--help-dsd` | Show short built-in DSD examples |
| `-r dsd64` through `-r dsd1024` | Set native DSF/DSDIFF **output** DSD bit clock |
| `--decode PROFILE` | `mastering`, `wideband`, or an exact native-rate decoder ID; obsolete versioned IDs and `conservative`/`legacy` are rejected |
| `--encode PROFILE` | `mastering`, `legacy` (explicit `rate` + `sdm` effects only), or an exact mastering encoder ID |
| `--dsd-mode auto\|native\|legacy` | `auto` selects normal routing; `native` requires bit-preserving native processing; `legacy` is an advanced named policy but **does not bypass DSD planning** |
| `--dsd-bandwidth adapt\|strict` | Permit output-rate bandwidth adaptation (default), or reject loss of the selected decoder's passband |
| `--dsd-level preserve\|sacd` | Default level convention, or +6.0206 dB SACD convention on reconstruction |
| `--dsd-clip warn\|error` | Clip excess interpolated encoder samples and warn (default), or fail on overload |
| `--headroom DB` | Fixed composite encoder attenuation of 0-120 dB, replacing implicit 0.9 gain |
| `--auto-headroom` | Measure the file's full interpolated peak and apply the cut it needs before encoding; per file, so for albums see [Encoding an album](#encoding-an-album) |
| `--dop` | Package native DSD into an exact 24-bit DoP PCM carrier |
| `--plan` | JSON preflight; do not create audio |
| `--report PATH` | JSON conversion result or named preflight record |
| `--dsd-layout ROLES` | Label existing channels with ordered speaker roles |
| `--dsd-layout-loss error\|warn` | Default refusal or explicit warning on loss of channel identity |
| `--sdm-guard on\|off` | Optional state-bound check for the separate low-level `sdm` effect (default off) |

The `legacy` routing selector is not a way to process native DSD pulses as ordinary PCM. If a requested route involves PCM effects, the planner still constructs the necessary stages or rejects the request. In normal work, omit `--dsd-mode` entirely.

### Five DSD-specific effects

Effects appear **after** the output filename. They are advanced controls; use the automatic routes unless you need explicit stage placement or analysis.

| Effect | Syntax | Role |
|---|---|---|
| `dsdpcm` | `dsdpcm [-p PROFILE] [-l preserve\|sacd] [rate]` | Qualified native DSD reconstruction to PCM |
| `pcmdsd` | `pcmdsd [-p PROFILE] [--reference auto\|pcm\|dsd] rate` | Qualified composite PCM-to-DSD interpolator/modulator |
| `dsdstat` | `dsdstat [-a]` | Native DSD pass-through with optional detailed statistics |
| `dop` | `dop` | Final native DSD-to-DoP packaging |
| `sdm` | `sdm [-f FILTER] [-t ORDER] [-n PATHS] [-l LATENCY]` | Separate, low-level one-bit modulator |

```bash
# Explicit, pinned DSD64 reconstruction.
sox input64.dsf -r 176400 decoded.wav \
    dsdpcm -p decode.mastering.dsd64 -l preserve 176400

# Qualified composite encoding with an explicit PCM reference.
sox master.wav -r dsd128 encoded.dsf \
    pcmdsd -p mastering --reference pcm 5644800

# Explicit native analysis and transport.
sox input64.dsf stats.dff dsdstat -a
sox input64.dsf -r 176400 -b 24 transport.wav dop
```

The `pcmdsd --reference` selector controls which amplitude convention enters the modulator: `pcm` uses the ordinary half-scale reference; `dsd` uses the theoretical-DSD reference; `auto` follows the graph's tracked calibration. Do not treat this as a general volume control. An explicit global decoder or level selection is propagated to `dsdpcm` unless that effect overrides it; incompatible settings are rejected.

**Do not confuse `sdm` with `pcmdsd`.** `sdm` operates at its actual input clock using an explicitly selected low-level filter. It does not create the complete qualified multistage interpolation chain, nor does `--sdm-guard` replace composite encoder clipping and numerical checks. This effect is mainly for specialized experiments.

The noise-shaper study exercised the low-level legacy route `rate -v RATE sdm -f NAME` with the ten `sdm-4`–`sdm-8` and `clans-4`–`clans-8` selectors. At **DSD512 and DSD1024**, that legacy route reuses the **DSD256 low-level coefficient tables**; it does not become the rate-specific high-rate mastering encoder. The separate `rate` stage reached about **4.27 GB peak RSS at DSD512** and **8.54 GB at DSD1024** for some benchmark inputs. The 1.1.0 composite path used approximately 10 MB there; its 1.1.1 memory peak was **not measured** in this report. This is one-host, input-dependent evidence, not a universal memory guarantee. Normal users should retain the qualified composite route rather than forcing `rate` plus legacy `sdm` to reproduce a mastering profile.

## 10. Troubleshooting and verification

| Symptom | Explanation / next action |
|---|---|
| DSD source shows a sample rate in the millions | `soxi` reports its **native one-bit clock**, correctly |
| An ordinary DSD-to-WAV command produces an unexpectedly low PCM rate | Check the default reconstruction clock; supply explicit `-r 96k`, `-r 192k`, etc. if desired |
| `--decode conservative` or a versioned decoder ID is rejected | Use mastering, wideband, or a current rate-pinned ID |
| `--decode wideband` retains unexpected ultrasonic noise | This profile deliberately preserves a broader upper-frequency spectrum |
| `--dsd-bandwidth strict` refuses a conversion | Requested PCM output clock cannot keep the decoder profile's passband; choose a higher supported rate or `adapt` |
| An exact profile ID is rejected | Current exact IDs are tied to the input DSD clock (decoder) or output DSD clock (encoder) |
| The DSD512/1024 default differs from a 1.1.0 DSD master | Current mastering uses a single SDM-8 encoder with rate-specific high-rate coefficients; output is not expected to match older releases |
| A fast PCM-to-DSD conversion warns about clipping | Remaining interpolated peaks exceeded the 0.45 warning ceiling; inspect the report and consider measured headroom |
| `--dsd-clip error` fails where default encoding succeeds | Strict mode refuses interpolated overload and keeps the mastering 0.9 gain at every rate. Use adequate headroom or `--auto-headroom` |
| `--headroom 0` gives a different level from no option | Zero is an explicit unity setting; the implicit one-pass default uses 0.9 |
| `--auto-headroom` needs time and scratch space | Its full interpolated-peak measurement requires another pass and temporary storage |
| `--dsd-mode native` rejects an effect or rate change | These need PCM reconstruction and possibly re-encoding; omit native-only policy |
| DSF/DSDIFF repack output has a different file hash | Container headers, layout, and padding differ; compare the native bitstreams instead |
| DSDIFF input fails | It may contain unsupported DST compression |
| WSD output fails | WSD is supported for input only |
| A DoP WAV plays as noise | Stop playback; the path or device may not accept marker-bearing DoP |
| Channel-role write fails | Destination container cannot represent the declared mapping; inspect with `--plan` |
| `--plan` succeeds but real encoding fails | Preflight cannot predict every sample-dependent numerical or disk error |

A useful diagnosis sequence:

```bash
sox --version
soxi source.dsf
sox --plan source.dsf -r 96k proposed.wav
```

For encoding, choose the clipping/headroom policy **before** running the conversion. For native repacking, confirm that you have not requested PCM effects or a different bit clock. A normal exit code with a **warning about clipped samples** is not evidence of an unmodified audio signal.

### Authoritative references and scope of validation

The source of truth for 1.1.1 behavior is the checked-in implementation. The key files and supporting documents are:

- `src/sox_ng.c`: CLI syntax, selector defaults, headroom, plans, and reporting.
- `src/dsd.c`: **mastering and wideband decoder banks**, passband/stopband edges and clocks.
- `src/pcmdsd.c`: **mastering encoder profiles at all five rates**, rate-specific high-rate SDM-8 tables, and the default 0.9 gain in both clip modes.
- `src/dsd_plan.c`, `src/dsdpcm.c`, `src/sdm.c`, `src/dsdstat.c`: route planning, explicit reconstruction, low-level legacy modulation, and native statistics.
- [1.1.1 release notes](RELEASE_NOTES_1.1.1.md): current defaults, strict-mode behavior, and release-evidence limits.
- [High-rate qualification history](V1_HIGH_RATE_ENCODE_2026-11-07.md): earlier table testing and the 0.9/0.45 operating point.
- [Decoder consolidation history](UNIFIED_DECODER_2026-11-09.md): prior decoder-profile changes.
- [DSD design](DSD_DESIGN.md) and [qualification](QUALIFICATION.md): architecture, response design, and test context. Historical design proposals do not override current release behavior.
- [Real-chain noise-shaper benchmark (2026-11-07; updated 2026-11-10)](NOISE_SHAPER_BENCH_2026-11-07.md): experimental methods, measured in-band and ultrasonic performance, results, and limitations. It is a measurement study, not part of the release specification.

**Validation boundary:** This guide describes the updated 1.1.1 source and distinguishes the new round03 high-rate measurements from older research. The original benchmark inputs and detailed outputs are provided separately in the handoff; the dated noise-shaper report remains unchanged. No listening tests, analog output measurements, every-device DoP checks, or exhaustive level-stability proof are claimed.

For ordinary PCM operations, consult the existing SoX/SoX-NG manuals. This document deliberately covers **only SoX DSD-specific functionality**.


---

*Guide: SoX DSD 1.1.1. DSD-focused edition, updated November 10, 2026.*
