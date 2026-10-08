# DSD P00 baseline: source, reference inputs and executable evidence

**Scope:** P00 test/evidence infrastructure only, as defined by
`docs/dsd/sows/P00.md` and sections 1, 4, 10 and 14 of `DSD_DESIGN.md`.
No production DSP, container handlers, seek code, public APIs, defaults or
runtime dispatch were modified. This is a reproducible baseline, not a
quality certification of the proposed DSD engine.

## Provenance and toolchain

- Supplied continuation archive SHA-256:
  `3fd6547e0118c61e9877644658ecf5d928865e9cfa4195b7ac4e4af655ed7cfa`.
  It already contained the approved design/plan/P00–P18 SOW overlay; it is not
  the older standalone source archive cited inside the design specification.
- Design-identified source commit:
  `16aa7e17531dd3612f29247da98c8ea570cd905a`. The continuation archive
  contains no `.git` history; the commit ID is provenance from the provided
  design, **not** an independently executed `git rev-parse` verification.
- SHA-256 of prebuild per-source-file manifest:
  `95bb8222c423cb66c295612c144d60222a52070fac7fd20af80d15330f45ac9a`.
  All **230** original `src/*.c` and `src/*.h` hashes match the extracted
  prebuild snapshot after P00; no production source changed.
- Design file SHA-256: `a3cecb47019006375d0c760a57df97849900144dca36301585f63509dea347bb`.
  Plan SHA-256: `01479e30d989bf81d3bc0ba036863a6b40202538764fd38214eae030a0b84130`.
  P00 SOW SHA-256: `5fd628961c92e4e83986ecb65d1a30065471f945a8dddd4913c8c49390656a8c`.
- Host: Linux x86_64 virtualized AMD EPYC 9V74. GCC 14.2.0,
  Autoconf 2.72, Automake 1.17, libtoolize 2.5.4, Python 3.13.5.
  Static build, `CFLAGS='-O2 -g'`, `--without-libltdl`.
  Libtool links `test/dsd_test_io` against the configured local library so
  optional codec/link flags are resolved by the build, not hard-coded.
  PNG/zlib, bundled GSM/LPC10/Dolby B/EBU R128, OpenMP and ffmpeg were
  available; FLAC, Ogg/Vorbis, Opus, WavPack, MP3, libsndfile and FFTW were
  not configured. The actual configuration log is authoritative.

Machine-readable hashes, tool executable paths, SHA-256 of the test binary,
compiler versions, CPU affinity and commands/exit codes are in
`tests/dsd/results/P00/build/provenance.json`, with individual source hashes
in `source_prebuild.sha256`. Each gate has a full stdout/stderr log and an
independent `.command.txt` and `.exit` record in that directory.

## Deterministic reference and expectations

The checked-in `tests/dsd/fixtures/manifest.json` describes **33** small,
hand-constructed DSF, DFF, WSD, DoP and PCM-source fixtures. It records bytes
and chronological-bit SHA-256 separately, source/license, rate, logical frames,
interleaved sample count and channel order. The checked-in seed is
`0x5D640126`. `reference/fixtures.py` never calls a native writer;
`reference/verify.py` independently parses DSF and DFF spans and reconstructs
bit chronology. A separate DoP parser checks alternating 0x05/0xFA markers.
The 0x69 chronological bit pattern yields DFF MSB byte `69`, DSF LSB byte
`96` and a single DoP payload word `05 69 69` (stored little-endian `69 69 05`).
Fixture regeneration has a byte-for-byte determinism test; the chunk walker
also rejects a corrupted enclosing size. DFF zero-completed tail frames are
counted separately from the source's logical frames.

The C API observer at `tests/dsd/test_io.c` reports public interleaved-sample
counts, `sox_seek` outcome, logical position, and chronological sample signs.
The harness corrects `olength` **only in specifically named diagnostic probes**
to distinguish generic core bookkeeping from DFF and WAV private state; no
production state is modified. `run.py` records exact invocations and
recognizes a baseline xfail only when its defect-specific executable
fingerprint matches. If the defect disappears unexpectedly (XPASS), changes
signature, or survives its declared repair phase, the runner fails.

**P00 final regression:** 17 PASS; 19 explicitly named XFAIL; 0 XPASS,
0 unexplained FAIL, 0 skipped. These cover DFF FRM8, CMPR, completed tail,
odd payload padding, and allocator-perturbed first-cluster corruption;
DSF/DFF/WSD tiny reads; DSF MSB rejection; generic/DFF/DSF multichannel
seek unit errors; DFF MANF, DSF Type 5 loss; and WAV private rewind state.
The fixture, control, DoP transport and xfail policy tests pass independently.
The new integration mutation test proves unchanged real baseline failures stay
XFAIL while altered reader/seek bits and deterministic writer tails turn to FAIL
with counts unchanged; simulated corrections are XPASS before and PASS at their
approved phases. Reader bits come only from the independent fixture decoder;
DFF first-cluster allocator garbage is deliberately not pinned.
The mutation test now checks baseline fingerprints only while their defects
await repair. The new P01 transition unit test confirms corrected P01 DFF
writers no longer require an obsolete xfail, with P03/P04 checks still active.
See `tests/dsd/results/P00/run.json` for per-case oracle, observed values,
commands and exact defect IDs.

## Executed build and integration gates

The untouched production baseline was built **before** adding test registration:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
make check
```

After adding P00 test registration, the same four commands and the following
P00 commands completed with exit code zero; exact logs are preserved:

```sh
make check-dsd
python3 tests/dsd/run.py --phase P00 --results tests/dsd/results/P00
python3 tests/dsd/measure.py --phase P00 --results tests/dsd/results/P00/numeric
python3 tests/dsd/bench.py --phase P00 --results tests/dsd/results/P00/bench
```

The generic `make check` was not changed. Exit zero is **not a complete
qualification**: it skips seven format groups (`wv`, `w64`, `paf`, `mat5`,
`mat4`, `flac`, `caf`) and marks eight regression cases `VOID` (unrun):
`BUG-305`, `BUG-327`, `BUG-334`, `BUG-libsndfile-float-level`, `ebu-r-128`,
`equiv-chorus-flanger`, `ffmpeg-command-execution`, `playlist-with-pipe`.
The newly executed generic log contains 73 `OK` named regressions, none of
which converts a `VOID` or skipped case into a pass. The complete per-case
record, prerequisites and log-line evidence are in
`tests/dsd/results/P00/build/corrective-generic-coverage.json`; its script
and original log are preserved. These skipped/unrun cases require additional
codecs/format support, `bc`, or Windows/Wine. Do not expand the P00 code
change to implement those prerequisites. P00's 36 named DSD cases have
zero skips and zero unexpected outcomes.

An additional optional `make distdir` attempt exited 2 because this host lacks
`tbl`, `nroff` and `pdfroff` required by the existing man-page build recipe.
See `tests/dsd/results/P00/build/distdir.log`; it was **not** counted as a
passed gate. The delivered continuation archive is checked independently
against a SHA-256 file manifest.

## Metrology scaffolding, not numerical acceptance

`reference/metrology.py` implements the explicitly defined normalized power
`10 log10(P/0.5)`, SNR as fitted signal/residual ratio, least-squares
DC/sine/cosine fitting, four-term periodic Blackman-Harris window (plus ENBW),
and bounded-baseband residual integration. The four metrology self-tests pass.
Synthetic 997/1000 Hz PCM WAVs at 88.2, 352.8 and 705.6 kHz are committed
as source fixtures, not independent DSD quality claims.

`measure.py --prepare-analysis-v1` produces a schema-defined generation request
for the 20 kHz passband / 24 kHz stopband, 180 dB analysis FIR. **No**
analysis-v1 coefficients, latency alignment, output spectra or independent
THD+N/SNR acceptance numbers have been generated or qualified in P00.
Existing `docs/dsd/evidence/filter_feasibility.json` is design-time candidate
feasibility evidence only; it is not a release filter or numerical pass.
`tests/dsd/results/P00/numeric/measure.json` records both passing scaffold
checks and these named unrun gates.

## Performance measurements and their limits

The development matrix executed **27** jobs with zero command failures:
for DSD64/DSD128/DSD256 and 1/2/6 channels, native DSF-to-DSF transcode,
and direct baseline `rate -v` output to **352.8** and **705.6 kHz** binary64
PCM WAV. All input bits are generated deterministically and input hashes are
recorded; each job records the actual command, exit, native rate, channels,
per-channel frames, audio seconds, wall/CPU seconds, RSS, bytes and rates.
`tests/dsd/results/P00/bench/bench.json` is the raw source of timing values.

The default input is only **0.006 seconds**, with one measurement per case:
startup and virtualized-host variability make medians/ratios inappropriate for
engineering performance acceptance. 88.2/176.4 kHz outputs, warmups and 15
repetitions, bandwidth-matched staging, long-duration memory/I/O controls,
physical AVX-only and multi-vendor ISA hardware coverage are **unrun** and
must not be interpreted as passing gates. The full matrix is executable with
`bench.py --profile full --duration N --warmups 2 --repetitions 15` on a
controlled host. Benchmarks record native and direct legacy baselines, not
performance of the future architecture.

The benchmark runner writes one atomic checkpoint per repetition. A simulated
interruption (26 complete cases, one missing repetition) was successfully
resumed from matching configuration/input/binary and host hashes; reruns
refuse changed hashes. The original pre-benchmark checkpoint archive is
referenced by `docs/dsd/handoffs/P00_CHECKPOINT.txt`.

## Limitations and next gate

No independent commercial converter, proprietary recording, specialized DAC,
profile-specific analysis filter, numerical release test or vendor-specific
ISA qualification was available or attempted in P00. This is not an excuse
to infer results from design estimates or to patch defects outside the phase.
The next permitted phase is **P01**, the localized DSDIFF writer fix; it must
turn P01's named DFF writer xfails into hard passes while preserving all
previously accepted tests. See `docs/dsd/handoffs/P00.md`.
