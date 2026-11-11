# SoX DSD

**SoX with first-class Direct Stream Digital support.**

SoX DSD is an independently versioned fork of [SoX-NG](https://codeberg.org/sox_ng/sox_ng), itself a continuation of [SoX](https://sox.sourceforge.net/). It keeps SoX's general-purpose audio conversion, effects, formats, command-line model, and library interfaces. The additional work concentrates on native DSD, controlled DSD/PCM conversion, and measurable numerical quality.

**Current version: 1.1.1**, based on **SoX-NG 14.8.1**. This is the behavior of the 1.1.1 release and the current `main` branch as of November 2026. The commits after the release tag reorganize tests and repository evidence without changing the audio engine.

## Why this fork exists

SoX already handles a wide range of audio tasks. SoX DSD builds on that foundation rather than replacing it with a DSD-only tool. Its distinguishing work is:

| Area | What SoX DSD adds |
| --- | --- |
| **Native DSD** | DSF and DSDIFF read/write at DSD64, DSD128, DSD256, DSD512, and DSD1024, with native-bitstream repacking when no audio processing is required. |
| **DSD reconstruction and encoding** | Qualified, rate-specific reconstruction filters and noise-shaping encoders with explicit, versioned profile identities. |
| **Transport** | DSD-over-PCM (DoP) packaging without reconstructing audio PCM; native WSD input is also supported. |
| **Predictable routing** | DSD-aware planning distinguishes native repacking from operations that need PCM reconstruction, processing, and re-encoding. |
| **Headroom and diagnostics** | Interpolated-peak handling, explicit and measured headroom, strict clipping policy, JSON preflight plans, and execution reports. |
| **Numerical verification** | Independent references, regression and qualification tests, SIMD checks, and separately published historical evidence. |

The project also pursues better numerical results in conventional PCM processing. That is an engineering direction, **not** a claim that every inherited SoX effect has already been replaced or that more computation automatically produces better audio.

## What works in 1.1.1

### Native rates, files, and transport

| Native rate | One-bit clock | Default DSD-to-PCM output | DoP carrier rate |
| --- | ---: | ---: | ---: |
| DSD64 | 2,822,400 Hz | 88,200 Hz | 176,400 Hz |
| DSD128 | 5,644,800 Hz | 176,400 Hz | 352,800 Hz |
| DSD256 | 11,289,600 Hz | 176,400 Hz | 705,600 Hz |
| DSD512 | 22,579,200 Hz | 176,400 Hz | 1,411,200 Hz |
| DSD1024 | 45,158,400 Hz | 176,400 Hz | 2,822,400 Hz |

- **DSF (`.dsf`) and DSDIFF (`.dff`)** support native DSD reading and writing at all five rates. **WSD is read-only.** DST-compressed DSDIFF is not supported.
- **Native repacking** between DSF and DSDIFF at the same bit clock preserves the one-bit audio stream when no PCM-domain operation is requested. Changing the DSD clock, applying gain or effects, or resampling requires a processing path.
- **DoP** carries DSD bits in a lossless signed 24-bit PCM stream with markers. It is not a DSD-to-PCM audio conversion; the receiver must recognize DoP. File and carrier support do not imply that a particular DAC, player, or connection accepts every rate.
- Channel-layout metadata is handled explicitly. Operations that would lose a known channel identity are not silently treated as lossless native transfers.

### Reconstruction and modulation profiles

**Decoder and encoder versions refer to different algorithms.** They are not a matched v1/v2 pair.

- **DSD to PCM:** the default is the qualified **mastering v1 decoder** at every native clock. `--decode mastering` selects the same bank. Its rated passband is 20 kHz for DSD64, 30 kHz for DSD128, and 40 kHz for DSD256 and above. `--decode wideband` selects the qualified **wideband v1** alternative, subject to the selected PCM output rate and bandwidth policy.
- **PCM to DSD:** the default is the qualified **eighth-order mastering v1 encoder** at all five rates. `--encode mastering` selects it explicitly.
- **Optional high-rate encoder:** `encode.mastering.v2.dsd512` and `encode.mastering.v2.dsd1024` select the distinct qualified **seventh-order CLANS-7** encoder, retained for explicit compatibility with 1.1.0 output. These are **encoder** profiles; there is no mastering v2 decoder in 1.1.1.
- **Exact IDs** such as `decode.mastering.v1.dsd64` and `encode.mastering.v1.dsd256` pin a qualified profile to a native rate. An incompatible pin is rejected rather than silently substituted.

Compared with **1.1.0**, 1.1.1 selects mastering **v1**, not mastering v2, as its standard decoder. Default decoded PCM can therefore differ between those releases. The older `--decode conservative` and `--decode legacy` aliases and mastering-v2 decoder IDs are no longer supported. The separately named high-rate v2 *encoder* remains available.

A *qualified* profile has passed the project's release-authorization checks for its stated scope. The term does not promise universal hardware compatibility, unconditional modulator stability, or superiority for every recording. See the [1.1.1 release notes](docs/dsd/RELEASE_NOTES_1.1.1.md).

### Clipping and headroom

PCM and DSD use different level conventions. Under the [SACD standard](https://www.sonicstudio.com/pdf/dsd/SACD_SignalPropertiesV13.pdf), 0 dB SACD corresponds to 50% of the theoretical maximum DSD signal amplitude. SoX DSD follows this reference convention at all supported DSD rates.

SoX DSD retains the original SoX noise shapers, but uses a qualified eighth-order mastering encoder based on SDM-8 by default at all five DSD rates. Our [noise-shaper research](docs/dsd/NOISE_SHAPER_BENCH_2026-11-07.md) found that SDM-8 delivers exceptional in-band noise performance, outperforming the alternatives overall on that measure, although other designs can produce less ultrasonic noise.

Eighth-order noise shapers have a known limitation, however: they can become unstable with unusually demanding, sustained signals, such as near-full-scale DC or high-level test tones. This behavior has also been [documented in earlier DSD-capable SoX builds](https://archimago.blogspot.com/2021/10/measurements-look-at-dsd-and-using-sox.html).

To operate within its qualified limits, the default encoder applies 0.915 dB of additional headroom. This maps full-scale PCM to approximately 45%, rather than the SACD reference level of 50%, of theoretical maximum DSD modulation. **The adjustment lowers the overall signal level without compressing the music's dynamics.**

Our [noise-shaper research](docs/dsd/NOISE_SHAPER_BENCH_2026-11-07.md) demonstrates exceptionally low noise with the default SDM-8-based mastering encoder within the audio band: At DSD64, the default encoder's in-band noise floor is about 141 dB below full scale (121 dB below a −20 dBFS test tone), comparable to 23-bit PCM. At higher DSD rates, the measured signal-to-noise ratio was substantially greater, eventually reaching the limits of the experiment's 32-bit signal path. If interpolated peaks still exceed the encoder's limit, SoX DSD clips them and issues a warning. Separate safeguards detect modulator instability.

- `--headroom DB` replaces the implicit cut with an explicit fixed attenuation.
- `--auto-headroom` measures the full interpolated signal and chooses the smallest non-amplifying, shared multichannel cut that stays within the warning ceiling. It needs additional passes and temporary storage.
- `--dsd-clip error` rejects overloads instead of clipping. Its default gain differs by rate/profile; strict mode does **not** universally mean unity gain. Modulator state and numerical guards remain active under every policy.

If retaining source level or avoiding clipping is important, choose the headroom policy explicitly. The default headroom exists for a reason. In testing without it, at unity gain, we encoded 200 real music tracks at DSD64, DSD128 and DSD256, each once at its original level and once normalized to a 0 dBFS peak. Six of those 1,200 encodes, all at DSD256, drove the SDM-8-based encoder unstable. In each case SoX DSD detected the instability and stopped with an error instead of writing a damaged file. With the default 0.915 dB cut, all 1,200 encodes completed. At DSD512 and DSD1024, the SDM-8-based encoder with `--headroom 0` is likewise **not** guaranteed stable for full-scale inputs. The [user guide](docs/dsd/USING_SOX_DSD.md) explains the policies and their limits.

## Start converting

SoX DSD retains the ordinary SoX command structure:

```text
sox [options] input [output-options] output [effects]
```

Most DSD operations need no DSD-specific switches:

```sh
# Native DSD to 24-bit PCM
sox concert.dsf -r 96000 -b 24 concert.wav

# PCM to native DSD128 with the default qualified encoder
sox master.wav -r dsd128 master.dsf

# Repack native DSD without decoding or re-encoding
sox concert.dsf concert.dff

# Package native DSD as DoP in a 24-bit WAV carrier
sox --dop concert.dsf concert-dop.wav

# Measure interpolated peaks and apply only the required headroom
sox --auto-headroom master.wav -r dsd256 master.dsf

# Inspect the intended DSD processing graph without writing audio
sox --plan concert.dsf concert.wav

# Convert and save the actual processing details as JSON
sox --report conversion.json concert.dsf concert.wav
```

For advanced selection:

```sh
# Choose qualified wideband reconstruction
sox --decode wideband concert.dsf -r 176400 wideband.wav

# Pin the optional 1.1.0-compatible high-rate v2 encoder
sox --encode encode.mastering.v2.dsd512 master.wav -r dsd512 v2.dsf

# Reject interpolated overload rather than clipping it
sox --dsd-clip error --auto-headroom master.wav -r dsd128 strict.dsf
```

Use `sox --help-dsd` for a short DSD reference. The full [Using SoX DSD](docs/dsd/USING_SOX_DSD.md) guide covers PCM clock selection, native versus reconstructed processing, DoP restrictions, layout controls, decoder bandwidth, the `dsdpcm`/`pcmdsd` effects, and profile compatibility.

## Build and install

### Nix

The repository includes a pinned flake. With Nix flakes enabled:

```sh
nix build                 # full build, with optional format support
./result/bin/sox --version

nix build .#bare          # smaller build, without optional codecs or FFmpeg
nix build .#checked       # bare build plus the DSD checks
```

`nix run github:barstoolbluz/sox_dsd -- --version` runs the full variant from the hosted source. The full Nix package also places FFmpeg and URL-fetch helpers on the executable's runtime `PATH`.

### Source release

A release archive includes generated Autotools files:

```sh
./configure
make
make check
sudo make install
```

### Git checkout

A development checkout needs a C compiler, Make, Autoconf, Automake, and Libtool:

```sh
autoreconf -i
./configure
make
make check
```

Add `--with-ffmpeg` to `./configure` when FFmpeg format support is wanted and available. Optional codec libraries depend on the formats you want. See [INSTALL](INSTALL), [README-cmake.md](README-cmake.md), and [README.win32](README.win32) for alternative build environments.

The executable is **`sox`**, alongside the familiar `soxi`, `play`, and `rec` commands where supported. The inherited library/header names remain **`libsox_ng`** and **`sox_ng.h`**; this fork has not renamed the library ABI. Compatibility command aliases may be installed where symlinks are enabled.

## Tests and reproducibility

The ordinary SoX tests and DSD-specific checks coexist:

```sh
make check                     # inherited SoX regression suite
make check-dsd-cli             # DSD CLI, release, and loud-encode acceptance
make check-dsd-release-111     # 1.1.1 profile and compatibility regressions
make check-dsd-optimization    # DSD numerical and optimization checks
make check-dsd                # DSD phase runner (defaults to P18)
```

The DSD phase suite uses Python 3 and, for numerical checks, `numpy`, `scipy`, and `mpmath`. Its CPU-specific checks exercise only the instruction-set tiers supported by the running machine. A pass on one host does not certify unexecuted CPU tiers, hardware transports, or private media collections.

`tests/dsd/` groups executable checks, native probes, phase studies, qualification tools, benchmarks, generators, fixtures, numerical references, and shared support code. Run outputs go under `.dsd-check-results/` or a caller-specified `DSD_RESULTS` directory, not into tracked evidence. See [tests/dsd/README.md](tests/dsd/README.md) and [Qualification](docs/dsd/QUALIFICATION.md).

The repository cleanup after 1.1.1 also restored the original identities of untouched upstream commits, retained the release tags, and moved historical receipts and repository-rewrite utilities into **separate release evidence/tooling assets**. The in-tree `scripts/` directory contains the eight inherited SoX-NG scripts. That separation keeps the source and build inputs available without treating historical results as fresh test executions.

## Documentation

- [Using SoX DSD](docs/dsd/USING_SOX_DSD.md): practical commands and behavior.
- [1.1.1 release notes](docs/dsd/RELEASE_NOTES_1.1.1.md): exact defaults, changed behavior, and compatibility limits.
- [DSD documentation index](docs/dsd/README.md): engine design, API-related behavior, profiles, and technical contracts.
- [CLI migration table](docs/dsd/MIGRATION_P15.md): earlier SoX DSD option spellings.
- [Qualification](docs/dsd/QUALIFICATION.md): executable checks and the boundaries of the historical evidence.
- [Upstream relationship](docs/UPSTREAM.md): separate versioning and the intended SoX-NG merge model.

## Relationship to SoX and licensing

SoX DSD stands on the work of SoX, SoX-NG, their contributors, and the libraries used by optional formats. **The upstream SoX-NG repository and its releases are not SoX DSD releases.** This fork retains upstream source structure where future merges expect it and versions its own work independently.

SoX is distributed under the **GNU General Public License, version 2**; individual files may carry other compatible notices. See [COPYING](COPYING) and [AUTHORS](AUTHORS).
