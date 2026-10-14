# P15 independent DSD-to-PCM metrology instrument

October 13, 2026. Authority: `DSD_DESIGN.md` §§6.1–6.6, 8.6 and 10.4; `P15_QUESTIONS_ADJUDICATION_2026-10-13.md`. Current phase: P15. This is an **execution instrument**, not a newly qualified production implementation, new decoder profile, revised signal policy, nor completed release certificate. The original P00–P15 numerical and physical evidence is unmodified.

## Decisions needed to execute the matrix

**All 54 cells are mandatory for release**: native DSD64/128/256 × PCM 44.1/48/88.2/96/176.4/192/352.8/384/705.6 kHz × mastering/wideband. Thirty destinations are integer arithmetic ratios; twenty-four are fractional ratios. The arithmetic label does not allow bypassing the **actual** optional final SRC. A 705.6-kHz output from an 88.2-kHz reconstruction, for example, still includes interpolation, and the mathematical reference does too. `analysis-v1` is the separate frozen PCM-to-DSD/SDM oracle and intentionally lacks the decoder bandwidth required here.

**Independence is by implementation and mathematical route, not by author name.** The C probe exports the unchanged decoder's **public binary64** values, without independent DSP calculations or a new production entrance. The mathematical reference separately composes actual certified C hex bank values at 75 decimal digits, applies finite centered convolution, constructs its own 180-dB-design-target Kaiser-sinc rational SRC, and sums the correct zero-extended polynomial phases in longdouble (with selected full-precision mpmath witnesses). Neither the production native scalar FIR routine, the private rate backend, nor `scipy.signal.resample_poly` is called by that oracle. SciPy is used **only** for optional window construction (`scipy.special.i0`) and a separately tested mathematical cross-check; the spectral fitting is an independent output-domain least-squares fit.

A **different, deliberately independently designed SRC filter** does not have the same output samples as the production SRC. Its finite-file boundary differences can dominate floating-point roundoff. The reference records full-stream residuals, first/last frames, relative phase, finite count, sampled 75-digit witnesses, and exact references; it does not call the §8.6 FIR accumulated-roundoff limit an allowable end-to-end SRC delta, nor silently trim extrema. Each final SRC combined-stage residual still requires an independently justified, predeclared numerical acceptance envelope before release.

## Test-only components

| Path | Purpose |
|---|---|
| `test/dsd_test_p15_instrument` (`tests/dsd/test_p15_instrument.c`) | Built on request; ingests native chronological **0/1 bytes**, exports exact little-endian F64 values from public DSD decoder for scalar/forced ISA and real one-bit streams; verifies selected tier/count and EOF. No production DSP source changed. |
| `tests/dsd/p15_numerical_reference.py` | Exact-bank 75-digit composed FIR; centered finite convolution; zero-extended rational polyphase SRC using an independent Kaiser-sinc reconstruction; 75-digit FIR and SRC witnesses. |
| `tests/dsd/p15_matrix_instrument.py` | Deterministic 54-cell execution, pulse/phase/count/level/channel and ISA comparison, captured binary64 numerical arrays, separate case files and strict resume binding. |
| `test/dsd_test_p07_reference` (`tests/dsd/test_p07_reference.c`) | Extends the existing test-only private F64 SRC exporter with `--tone`; original behavior preserved. |
| `tests/dsd/p15_src_spectral.py` | Directly measures **production** SRC selected passband tones, folded downsampling aliases and upsampling images with independent sine/cosine fits; optional raw binary64 outputs. |
| `tests/dsd/p15_graph_integration.py` | Independent DSF fixture → actual SoX graph and int32 WAV comparison, small/large buffer, one/two threading modes, one-LSB comparison and explicit clipping `error`/`warn`. |
| `tests/dsd/test_p15_instrument.py` | Pure-reference, built-probe, P06 hash, malformed native bit/count, SRC mismeasurement, forced tier and corrupted/changed evidence tests. |

`p15_matrix_contract.py` and `P06/numeric/filter-certificate.json` are inherited. The P06 adaptive envelope certifies the native FIR's six rate/profile configurations and coherent native aliases **only** when its exact coefficient set still matches; it cannot certify the final SRC or whole graph. The source checker aborts on a manifest hash mismatch.

## Build and run on the prepared host

From the extracted source root, with NumPy, SciPy and mpmath available:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
make -C test dsd_test_p15_instrument dsd_test_p07_reference
P15_LIVE=1 python3 -m unittest discover -s tests/dsd -p test_p15_instrument.py -v
```

The temporary build writes only into the operator's checkout. A source-only archive deliberately does not contain autoconf products, executables, objects or generated makefiles. A clean/out-of-tree build is also supported if the repository's existing autotools workflow supports it; construct the probes in that build tree and pass their paths explicitly.

For an **out-of-tree build**, run the focused tests with explicit probe locations instead of relying on the default in-tree test binary names:

```sh
P15_LIVE=1 \
P15_PROBE=/your/build/test/dsd_test_p15_instrument \
P15_SRC_PROBE=/your/build/test/dsd_test_p07_reference \
python3 -m unittest discover -s tests/dsd -p test_p15_instrument.py -v
```

Run the complete host matrix with raw spectral receipts. Set an **absolute, new** results directory on a filesystem with adequate free space (raw 64-bit tone traces may occupy many gigabytes over 54 cells, particularly for upsampling):

```sh
python3 tests/dsd/p15_matrix_instrument.py \
  --probe test/dsd_test_p15_instrument \
  --src-probe test/dsd_test_p07_reference \
  --sox src/sox_ng \
  --tier sse2 --tier avx1 --tier avx2 --tier avx512 \
  --capture-src-raw --capture-graph-raw \
  --require-all-observations \
  --results /YOUR/NEW/P15/METROLOGY/RESULTS
```

Use `--resume` with the **same configuration, binaries and reference sources** after interruption. It refuses a different Python/numerical dependency version, changed binary hash, altered source/checksum or changed selected row list. It locks one writer, validates SHA-256-bound saved rows and raw vectors, redoes any interrupted cell rather than inheriting an uncommitted spectrum, and never assumes an unsupported ISA is a pass. Host-dependent tool paths are not stored in receipts; relative filenames and captured source/binary/version hashes are. Never recopy receipts from another host as if they were produced by this build. Preserve the source tar checksum and record distinct external ISA, build flags, CPU/FP control, and physical-clock evidence separately.

`--require-all-observations` rejects missing SRC or actual SoX graph probes, filtered subsets, and shortened stimulus windows. It requires all 54 local full-duration scalar/SRC/graph observations. This is an **instrument-completeness** guard, not a full spectral certificate, a cross-host ISA pass, or permission to change production defaults. On a machine without an ISA tier, the corresponding forced entries are `UNSUPPORTED_ON_THIS_HOST` and remain an open obligation elsewhere. Removing `session.json` or `worklist.json` prevents resumption of existing rows; never rebind prior results to a newly invented session descriptor. For an independently auditable handoff, **use both raw-capture flags**; the reviewer will remeasure SRC tone fits from the recorded binary64 stream and compare the actual graph WAV samples to the separately captured six-channel binary64 reference.

On a host that lacks one tier, that tier is `UNSUPPORTED_ON_THIS_HOST` and its physical qualification must be performed elsewhere. To run fewer selected cells or a short development sample, pass `--native 2822400`, `--pcm 48000`, `--profile mastering`, and/or `--frames 8192 --src-frames 8192`. **Short captures are diagnostic**, especially when PCM output has too few frames for a measured native program-noise fit; this condition is explicitly `UNRUN_SHORT_DEVELOPMENT_CAPTURE`. The normal 262144-native-frame source and 131072 intermediate-frame tone windows are the intended baseline, not an assertion that a finite window contains all spectral extrema. A result directory from a different choice of flags must be new; avoid overwriting accepted/committed evidence.

### Reading results and honest limits

The results directory holds:

- `session.json`: deterministic row selection, worklist hash, bank/reference/source/checker hashes, built binaries, longdouble precision and Python/NumPy/SciPy/mpmath version bindings.
- `worklist.json`: unchanged 54-cell obligation list and all 270 forced-tier functional jobs / 96 selected detailed comparisons.
- `cells/<id>.json` and matching `.sha256`: measured properties, scalar-vs-independent FIR and combined-stage residuals, complete finite-file output count/edges, channel/partition, optional ISA, graph/clipping results. Every successful cell says `qualified: false`.
- `arrays/<id>.npz`: SHA-bound original bit chronology, actual and expected binary64 output vectors, isolated native-FIR output, zero-bit baseline and paired-bit-difference impulse responses including first, middle and last. When forced ISA tiers are requested, it also retains their measured program/FIR vectors and the detailed tier impulse responses. Exact raw input chronology is versioned and reproducible; a reviewer can recompute numerical comparisons from the saved vectors.
- `src-spectral/<id>.json`: private production SRC sampled passband/image/alias tests and limits. `src-raw/<id>/...f64` contains optional signed-off little-endian binary64 tone outputs, one file per actual production SRC call, including hashes and sample counts.
- `graph-raw/<id>/`: when requested, the actual native one-bit DSF source, both 32-bit graph output WAVs and the explicit clip-warning WAV, each with a row-bound relative SHA-256 receipt. The numerical NPZ contains the corresponding six-channel one-bit chronology and F64 graph comparator; the offline reviewer verifies file bytes, timeline, sample count, and the one-int32-LSB allowance.
- `summary.json`: current failures, missing rows, the distinction between a short development capture and a full measurement attempt, and `release_gate_closed: false` in all cases.

### Reviewing observations from multiple ISA hosts

Each host keeps its own **new** result directory, binding its exact binary/source and numerical dependencies. After moving the completed directories to the reviewing machine, use the **same source revision** and run:

```sh
python3 tests/dsd/p15_matrix_receipt_review.py \
  --session /evidence/host-1 \
  --session /evidence/host-2 \
  --session /evidence/host-3 \
  --output /evidence/P15-cross-host-coverage.json \
  --require-coverage
```

Repeat `--session` for every available source-compatible host; provide paths in a declared stable order. The reviewer accepts multiple separately built exporters, but **never combines incompatible source/reference revisions**. It verifies source SHA-256 identities, session worklists, per-cell digests and the raw NPZ data; recomputes program/FIR, impulse and forced-tier discrepancy statistics; and, when raw recordings were requested, rechecks SRC tone fits and six-channel graph WAVs against the underlying F64 samples. It counts the **54** full-duration scalar cells, **216** additional tier-functional jobs (54 scalar + 216 additional = **270** total), and **96** predetermined detailed scalar-relative comparisons. It reports raw SRC/graph coverage separately so missing captures are visible. Unsupported tiers remain missing; failures from one host cannot be cancelled by passing observations elsewhere. `--require-coverage` exits 2 if those *observation counts* are incomplete. The report contains relative evidence identities and hashes, **not** machine-specific paths.

This cross-host report is **not** a trusted signature, cannot verify the physical silicon or replace raw benchmark/soak/corpus receipts, and never sets `release_gate_closed: true`. Per-sample SRC differences against the deliberately different independently designed reference still require an externally adjudicated bound; sampled production-SRC tones still require a separate full transfer/extrema and coherent-alias proof before the numerical gate closes. Review the original raw receipts and externally attest host identity before accepting a physical-tier claim.

This instrument **asserts** numerical safety for exact count, tiny-stream behavior, output finiteness, source validity, independent native FIR roundoff, buffer/channel determinism, explicit level x2, and when requested the actual graph's one-LSB/thread/clipping behavior. Selected private SRC tone results fail where an observed 0.0001-dB pass envelope or -160-dB rejection criterion is violated. It **measures but does not certify** composite SRC sample differences against a distinct SRC filter. The selected SRC sine/image set (seven pass tones and three groups of alias probes) cannot prove the absence of **unsampled** extrema or all mathematically coherent alias images. Its native FIR component inherits P06's independent adaptive all-image proof, conditional on exact coefficients. A complete final spectral gate needs an adjudicated, independent **full composite SRC extrema/coherent-alias certificate** in addition to these receipts. Do not relabel a sampled pass as that certificate, or change the product's published P/S boundary.

The operator must likewise supply, separately, current physical forced-tier, thermal/performance, soak and commercial-corpus evidence. An actual P15 release decision must apply the `DSD_DESIGN.md` boundaries, externally qualified composite numeric error and physical/codec gates. **No default policy, profile, FIR/SDM engine, or existing certificate is changed by this work.**

### Exit conditions

- `0`: selected measurements completed without a detected numerical/functional error. **Not a release pass.**
- `1`: a detected failing cell or invalid/tampered setup/evidence. `summary.json` records detected per-cell failures; a resume-binding/setup exception is deliberately fatal.
- `2` with `--require-qualified`: measurement completed without detected error, but no separately signed-off complete release certificate exists. No instrument execution alone can return a qualified release status.

The detailed checkpoint and next steps are in `docs/dsd/handoffs/P15_INSTRUMENT_CHECKPOINT_2026-10-13.md`. This section is not a replacement for `docs/dsd/DSD_DESIGN.md` or the previously frozen evidence.
