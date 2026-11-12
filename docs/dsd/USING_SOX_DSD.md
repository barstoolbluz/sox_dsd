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

SoX DSD selects a profile from the conversion direction and DSD clock. **Reconstruction and encoding use independent algorithm families; their version numbers are not paired.**

- **Reconstruction (DSD → PCM):** the default at every DSD clock is **mastering v1**. `--decode mastering` selects the same qualified filter bank. `--decode wideband` is the separate qualified wideband-v1 alternative. The mastering-v2 *decoder* found in 1.1.0 was removed from 1.1.1.
- **Encoding (PCM → DSD):** the default at every DSD clock is the qualified **eighth-order mastering v1** composite encoder. At DSD512 and DSD1024 only, qualified **seventh-order CLANS-7 mastering v2** remains available by exact encoder ID; it is no longer the default.

| DSD clock | Default reconstruction | Default composite encoder | Optional encoder |
|---|---|---|---|
| DSD64 | mastering v1 | mastering v1 (eighth-order) | — |
| DSD128 | mastering v1 | mastering v1 (eighth-order) | — |
| DSD256 | mastering v1 | mastering v1 (eighth-order) | — |
| DSD512 | mastering v1 | mastering v1 (eighth-order) | mastering v2 (CLANS-7) |
| DSD1024 | mastering v1 | mastering v1 (eighth-order) | mastering v2 (CLANS-7) |

The mastering-v1 encoder descends from the sigma-delta modulation work of **Måns Rullgård** in SoX-NG, used here within SoX DSD's own qualified interpolation chain and numerical/state guards. The reconstruction FIR filters are separate SoX DSD designs. A v2 **encoder** does not imply a v2 **decoder** or a wider decoder passband.

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

A normal DSD-to-PCM command inserts the source-matched qualified reconstruction filter automatically. You do not need to name `dsdpcm` or a particular version unless you want to override the default.

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

**Separate the two DSP directions.** A DSD-to-PCM *decoder* applies reconstruction FIR filters. A PCM-to-DSD *encoder* interpolates PCM and operates a one-bit noise-shaping modulator. Profile versions refer to designs inside each direction, not to the product version or a matched decoder/encoder pair.

### 4.1 Reconstruction: the mastering v1 default

A one-bit DSD signal carries shaped quantization noise, much of it ultrasonic. The mastering reconstruction filter retains its specified passband and suppresses unwanted high-frequency content. More output samples do not automatically increase the decoder's chosen source bandwidth.

| Native input | Mastering v1 rated passband | Stopband begins | Intermediate PCM clock |
|---|---:|---:|---:|
| DSD64 | 20 kHz | 40 kHz | 88.2 kHz |
| DSD128 | 30 kHz | 60 kHz | 176.4 kHz |
| DSD256 | 40 kHz | 80 kHz | 176.4 kHz |
| DSD512 | 40 kHz | 80 kHz | 176.4 kHz |
| DSD1024 | 40 kHz | 80 kHz | 176.4 kHz |

The passband edge marks the last frequency covered by the specified flat-response region; the stopband edge marks where specified attenuation begins. Neither is a brick-wall cutoff or a listening-quality ranking. The design's transfer-function targets are described in [DSD design](DSD_DESIGN.md).

**Historical compatibility:** In 1.1.0, mastering v2 decoding was the default, with nominal passbands of 25 kHz for DSD64, 48 kHz for DSD128, and 66 kHz for DSD256 and above. **Those v2 decoder banks and IDs are no longer available in 1.1.1.** The retained v2 *encoder* is a different algorithm. Existing render comparisons must identify the SoX DSD version as well as their encoder and decoder IDs.

### 4.2 Selecting a decoder in 1.1.1

| Request | Result |
|---|---|
| No `--decode` | Qualified mastering v1 for the source DSD clock |
| `--decode mastering` | The same mastering v1 decoder |
| `--decode wideband` | Qualified wideband v1 for the source DSD clock |
| `--decode decode.mastering.v1.dsd128` | Exact mastering v1 bank; DSD128 source required |
| `--decode decode.wideband.v1.dsd256` | Exact wideband v1 bank; DSD256 source required |
| `--decode conservative` or `--decode legacy` | **Rejected** (retired 1.1.0 selectors) |
| `--decode decode.mastering.v2.dsd128` | **Rejected** (v2 decoder removed) |

```bash
# Automatic and explicit mastering-v1 reconstruction select the same filter.
sox source64.dsf -r 176400 default-v1.wav
sox --decode mastering source64.dsf -r 176400 mastering-v1.wav

# Pin the released DSD128 mastering decoder.
sox --decode decode.mastering.v1.dsd128 source128.dsf \
    -r 176400 pinned-v1.wav

# Choose the qualified wideband alternative.
sox --decode wideband source128.dsf -r 352800 wideband.wav
```

To compare mastering and wideband, render the **same source** with the **same final PCM rate and level**. The distinct passbands may pass different amounts of shaped ultrasonic noise. These differences cannot be inferred just from source DSD clock.

### 4.3 Wideband v1: a deliberate alternative

`--decode wideband` retains a much broader DSD spectrum than mastering v1:

| Input | Wideband v1 passband | Stopband begins | Intermediate PCM clock |
|---|---:|---:|---:|
| DSD64 | 35.28 kHz | 44.1 kHz | 88.2 kHz |
| DSD128 | 70.56 kHz | 88.2 kHz | 176.4 kHz |
| DSD256 | 141.12 kHz | 176.4 kHz | 352.8 kHz |
| DSD512 | 282.24 kHz | 352.8 kHz | 705.6 kHz |
| DSD1024 | 564.48 kHz | 705.6 kHz | 1,411.2 kHz |

This can help specialist measurement or deliberately broad-spectrum work, but it can also retain considerably more shaped ultrasonic noise. It is not a mastering-v2 alias.

### 4.4 Output-rate policy: `adapt` versus `strict`

The destination PCM clock may be unable to represent the selected filter's full passband. `--dsd-bandwidth adapt` (default) allows a narrower effective result. `--dsd-bandwidth strict` rejects a route that cannot preserve it.

```bash
# DSD128 mastering v1 has a 30 kHz passband; 44.1 kHz PCM cannot retain it.
sox source128.dsf -r 44100 adapted.wav

# The strict request is expected to fail on the same input and output clock.
sox --dsd-bandwidth strict source128.dsf -r 44100 refused.wav

# An output clock that can represent the 30 kHz passband.
sox --dsd-bandwidth strict source128.dsf -r 88200 strict-ok.wav
```

A 44.1 kHz destination is not inherently invalid for every mastering-v1 source: for DSD64 the selected passband is 20 kHz. The compatibility decision depends on the *selected filter* and the *destination rate*, not on a blanket rule about 44.1 kHz.

### 4.5 Encoding: mastering v1 is standard at every rate

The qualified composite PCM-to-DSD encoder combines interpolation and one-bit noise shaping. In **1.1.1**, the eighth-order mastering-v1 design is the default at all native DSD clocks. The **seventh-order CLANS-7 mastering-v2** design remains an explicit, qualified option only at DSD512 and DSD1024.

| Output clock | Default encoder ID | Additional qualified encoder ID |
|---|---|---|
| DSD64 | `encode.mastering.v1.dsd64` | — |
| DSD128 | `encode.mastering.v1.dsd128` | — |
| DSD256 | `encode.mastering.v1.dsd256` | — |
| DSD512 | `encode.mastering.v1.dsd512` | `encode.mastering.v2.dsd512` |
| DSD1024 | `encode.mastering.v1.dsd1024` | `encode.mastering.v2.dsd1024` |

The high-rate v1 designs had failed earlier qualification checks at a higher **0.5** modulator mapping, including sustained DC and nominal-soak conditions. They subsequently passed the release's tested checks with the **0.9 implicit gain** and **0.45 clipping ceiling**. This qualification applies to that documented policy. Explicit unity input mapping at full-scale sustained DC can still trip a high-rate v1 state guard, particularly with `--headroom 0 --dsd-clip error`. A qualified profile does **not** mean unrestricted level tolerance.

```bash
# Standard 1.1.1 mastering-v1 encoding.
sox master.wav -r dsd256 master256.dsf
sox master.wav -r dsd1024 master1024-v1.dsf

# Pin the qualified high-rate v2 CLANS-7 encoder when explicitly wanted.
sox --encode encode.mastering.v2.dsd512 master.wav -r dsd512 master512-v2.dsf
sox --encode encode.mastering.v2.dsd1024 master.wav -r dsd1024 master1024-v2.dsf
```

`--encode mastering` means v1 at **all five rates**, not the former 1.1.0 high-rate v2 default. Exact IDs must match the destination DSD clock. The terms `sdm-8` in the **low-level legacy effect** and *eighth-order mastering v1* in the **qualified composite encoder** do not designate identical high-rate processing routes. Their coefficient selection, interpolation path, gain and guard behavior differ; see Section 9.

### 4.6 What the noise-shaper study found

The standalone [noise-shaper bench report](NOISE_SHAPER_BENCH_2026-11-07.md) compares the legacy shapers, the 1.1.0 high-rate v2 default, and the 1.1.1 high-rate v1 default **through their real encoding paths**, not from abstract filter plots. **It does not compare DSD-to-PCM reconstruction filters** or resurrect the removed v2 decoder. Its 1.1.0 experiments used 18 signals/excerpts per rate, except nine at DSD1024; the 1.1.1 tagged rerun added **27 default-route jobs** across DSD512 and DSD1024. The high-rate v1 real-music completion study used a separate **1.1.0-based test build with v1 selected**, not the final 1.1.1 release binary.

The most useful high-rate comparison, copied from the report's tables, is:

| Tested route | Music-notch in-band median (dBFS) | 20–50 kHz energy (dBFS) | 100 kHz–1 MHz energy (dBFS) |
|---|---:|---:|---:|
| DSD512, v1 default (1.1.1) | −197.3 | −209.2 | −15.5 |
| DSD512, v2 option (1.1.0 default) | −195.1 | −176.9 | −26.7 |
| DSD1024, v1 default (1.1.1) | −198.9 | −209.4 | −28.1 |
| DSD1024, v2 option (1.1.0 default) | −197.4 | −199.5 | −43.8 |

The music-notch medians use **12 excerpts at DSD512 but only three at DSD1024**. The ultrasonic figures use the study's **−20 dBFS sine**, not the music excerpts. A more negative dBFS reading indicates less measured energy in the stated band. The benchmark's absolute 32-bit reference level depends on source rate and its test chain; the comparison does **not** certify a universal noise floor for all possible inputs or processing paths.

**Interpretation:** The 1.1.1 v1 default has lower measured in-band noise and less energy immediately above 20 kHz in these tests. It also has **more** energy in the 100 kHz–1 MHz band: **11.2 dB at DSD512 and 15.7 dB at DSD1024** relative to v2. A user cannot infer the analog output or listening result from either band without measuring the player, DAC, and analog reconstruction chain.

The report's synthetic distortion estimator was **not calibrated**. Its 32-bit reference signals already contain periodic quantization products. The report judged several v2 excesses significant by its own rule but found **no established excess** for the 1.1.1 v1 default at the high rates. That is **not** a claim of zero v1 distortion or a statistically established ranking in every situation.

**The useful practical conclusion:** The qualified v1 default is a sensible starting point. Select high-rate v2 when a specific need warrants it, such as matching 1.1.0 encoder output or comparing the higher-frequency noise spectrum against the requirements of your playback chain. Neither profile has a demonstrated universal listening advantage. For controlled comparisons, hold source, input level, DSD clock, headroom/clip policy, and measurement bandwidth constant. Read the [complete report](NOISE_SHAPER_BENCH_2026-11-07.md) for the synthetic stimuli, observed noise, distortion-verdict method, ultrasonic tradeoff, and limitations.

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
| Refuse clipping | `sox --dsd-clip error in.wav -r dsd128 out.dsf` | Strict bound of 0.5; unity gain at DSD128 (but high-rate v1 retains 0.9) |
| Measured headroom plus strict checking | `sox --auto-headroom --dsd-clip error in.wav -r dsd128 out.dsf` | Scan, apply a shared cut, and fail if the final strict check rejects input |

`--headroom` accepts an attenuation from **0 to 120 dB**, not a signed gain or a target peak level. **`--headroom 0` explicitly requests unity gain**; it does not mean the implicit default. A fixed cut may still leave peaks above the warning ceiling, so it does not by itself guarantee zero clipped interpolated samples.

`--auto-headroom` measures the interpolated signal, including the finite tail, then chooses a **single gain across all channels** so their balance does not change. It never boosts quiet material, uses bounded RAM with temporary storage, and takes an additional measurement pass with more I/O. Its target is the **0.45 warning ceiling**, even when combined with strict checking. The scan does not substitute a different mastering profile. It measures each file on its own, so the tracks of an album can receive different cuts; see [Encoding an album](#encoding-an-album).

`--dsd-clip error` without explicit headroom uses a **0.5 strict input envelope**, rather than the default warning ceiling of 0.45; it rejects overshoots rather than clipping them. **The applied gain depends on the encoder**: DSD64/128/256 v1 and explicitly pinned high-rate v2 use **unity gain**; **high-rate v1 retains its implicit 0.9 gain even in strict mode**. This protects its qualified operating point, but it does not make an arbitrary input safe. An explicit `--headroom DB` replaces that implicit gain. DSD-origin re-encoding uses a different amplitude reference and is not covered by PCM-origin peak thresholds. The modulator's separate state guards apply in either mode. `--headroom` and `--auto-headroom` are mutually exclusive; both control the qualified **composite encoder**, not conventional PCM output processing or native repacking.

For a single level-sensitive track, prefer **`--auto-headroom`** when its extra pass and temporary-file I/O are acceptable. For an album, use one fixed `--headroom` for every track so the tracks keep their relative levels. For high-throughput conversion where the fixed reduction and possible clipping warnings are understood, the ordinary one-pass default may be preferable.

**What the music qualification establishes:** The separate high-rate v1 test build completed 800 real-track encodes at DSD512/1024, including sample-peak-raised copies. However, the 1.1.1 release documentation records **194 input-stage clipping warnings among 400 peak-raised runs**. Those are distinct from the composite encoder's 0.45 modulator warnings. Completion shows that the tested encoder did not abort; it does **not** prove the peak-raising command preserved the source waveform. Avoid unnecessary upstream `-v` amplification when waveform preservation is the goal. The benchmark's no-clipping statement applies to its separate 27-job rerun, not to these peak-raised real tracks.

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
| `--decode PROFILE` | `mastering` (v1 default), `wideband` (v1), or an exact qualified v1 decoder ID; older v2 and `conservative`/`legacy` decoder names are rejected |
| `--encode PROFILE` | `mastering` (v1 at all five rates) or an exact qualified encoder ID; only DSD512/1024 have an optional v2 CLANS-7 ID |
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
    dsdpcm -p decode.mastering.v1.dsd64 -l preserve 176400

# Qualified composite encoding with an explicit PCM reference.
sox master.wav -r dsd128 encoded.dsf \
    pcmdsd -p mastering --reference pcm 5644800

# Explicit native analysis and transport.
sox input64.dsf stats.dff dsdstat -a
sox input64.dsf -r 176400 -b 24 transport.wav dop
```

The `pcmdsd --reference` selector controls which amplitude convention enters the modulator: `pcm` uses the ordinary half-scale reference; `dsd` uses the theoretical-DSD reference; `auto` follows the graph's tracked calibration. Do not treat this as a general volume control. An explicit global decoder or level selection is propagated to `dsdpcm` unless that effect overrides it; incompatible settings are rejected.

**Do not confuse `sdm` with `pcmdsd`.** `sdm` operates at its actual input clock using an explicitly selected low-level filter. It does not create the complete qualified multistage interpolation chain, nor does `--sdm-guard` replace composite encoder clipping and numerical checks. This effect is mainly for specialized experiments.

The noise-shaper study exercised the low-level legacy route `rate -v RATE sdm -f NAME` with the ten `sdm-4`–`sdm-8` and `clans-4`–`clans-8` selectors. At **DSD512 and DSD1024**, that legacy route reuses the **DSD256 low-level coefficient tables**; it does not become the qualified high-rate v1 composite encoder. The separate `rate` stage reached about **4.27 GB peak RSS at DSD512** and **8.54 GB at DSD1024** for some benchmark inputs. The 1.1.0 composite path used approximately 10 MB there; its 1.1.1 memory peak was **not measured** in this report. This is one-host, input-dependent evidence, not a universal memory guarantee. Normal users should retain the qualified composite route rather than forcing `rate` plus legacy `sdm` to reproduce a mastering profile.

## 10. Troubleshooting and verification

| Symptom | Explanation / next action |
|---|---|
| DSD source shows a sample rate in the millions | `soxi` reports its **native one-bit clock**, correctly |
| An ordinary DSD-to-WAV command produces an unexpectedly low PCM rate | Check the default reconstruction clock; supply explicit `-r 96k`, `-r 192k`, etc. if desired |
| `--decode conservative` or a mastering-v2 decoder ID is rejected | 1.1.1 retains mastering v1 and wideband v1 reconstruction; old decoder names and banks were removed |
| `--decode wideband` retains unexpected ultrasonic noise | This profile deliberately preserves a broader upper-frequency spectrum |
| `--dsd-bandwidth strict` refuses a conversion | Requested PCM output clock cannot keep the decoder profile's passband; choose a higher supported rate or `adapt` |
| An exact profile ID is rejected | Versioned IDs are tied to a specific input DSD clock (decoder) or output DSD clock (encoder) |
| The DSD512/1024 default differs from a 1.1.0 DSD master | 1.1.1 defaults to v1 at high rates; the old v2 CLANS-7 encoder remains selectable with an exact ID |
| A fast PCM-to-DSD conversion warns about clipping | Remaining interpolated peaks exceeded the 0.45 warning ceiling; inspect the report and consider measured headroom |
| `--dsd-clip error` fails where default encoding succeeds | Strict mode refuses input overload; gain is unity at lower rates and for high-rate v2, but high-rate v1 retains 0.9. Use adequate headroom or `--auto-headroom` |
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
- `src/dsd.c`: **current mastering-v1 and wideband-v1 decoder banks**, passband/stopband edges and clocks; no v2 mastering decoder exists here.
- `src/pcmdsd.c`: qualified **mastering-v1 encoder profiles at all five rates**, optional high-rate v2 pins, default 0.9 gain, and strict-mode gain selection.
- `src/dsd_plan.c`, `src/dsdpcm.c`, `src/sdm.c`, `src/dsdstat.c`: route planning, explicit reconstruction, low-level experimental modulation, and native statistics.
- [1.1.1 release notes](RELEASE_NOTES_1.1.1.md): current defaults, strict-mode behavior, and release-evidence limits.
- [High-rate v1 qualification](V1_HIGH_RATE_ENCODE_2026-11-07.md): history of the failed 0.5 mapping and the qualification evidence for the 0.9/0.45 operating point.
- [Unified decoder notes](UNIFIED_DECODER_2026-11-09.md): mastering-v2 decoder removal and the remaining v1 decoder identities.
- [DSD design](DSD_DESIGN.md) and [qualification](QUALIFICATION.md): architecture, response design, and test context. Historical design proposals do not override current release behavior.
- [Real-chain noise-shaper benchmark (2026-11-07; updated 2026-11-10)](NOISE_SHAPER_BENCH_2026-11-07.md): experimental methods, measured in-band and ultrasonic performance, results, and limitations. It is a measurement study, not part of the release specification.

**Validation boundary:** This guide updates the earlier 1.1.0 user document against the 1.1.1 source and integrates selected results from the noise-shaper report. The spectral tables were checked for internal consistency with the report; the underlying `results.jsonl`, `combined.jsonl`, and `derived.txt` benchmark evidence is not published with the repository. No listening tests, analog output measurements, every-device DoP checks, or exhaustive level-stability proof are claimed.

For ordinary PCM operations, consult the existing SoX/SoX-NG manuals. This document deliberately covers **only SoX DSD-specific functionality**.


---

*Guide: SoX DSD 1.1.1. DSD-focused edition, updated November 10, 2026.*
