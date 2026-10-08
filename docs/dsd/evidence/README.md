# Design-time evidence and reproduction guide

This directory records work actually performed against the attached baseline at
`16aa7e17531dd3612f29247da98c8ea570cd905a`. It does not contain an implementation
of the proposed engine. Keep this distinction when citing the results.

## What ran

The four build commands in `environment.json` succeeded. Their complete captured
logs are included. `make check` passed its available tests and contains VOID
cases; missing optional codec dependencies were not silently treated as coverage.

`reproductions.json` captures independent tiny-format fixtures and C API probes.
It confirms the brief's writer, small-read, bit-order, channel-type and seek
problems. It also demonstrates first-cluster DFF corruption from an uncleared
accumulator and a WAV-private remaining-sample counter that stays stale after
rewinding even after the probe corrects core `olength`. The DFF/MANF result still
supports the brief's single core-position correction rather than a redundant
format-private remaining-audio counter.

`filter_feasibility.json` and `candidate_filter_coefficients.npz` contain the
sampled binary64 feasibility results for the selected half-band/FIR architecture.
The sampled coherent alias bounds are approximately -182.4 dB or lower, versus
the proposed -160 dB public target. These are transfer-function calculations,
not end-to-end THD+N measurements, independent release certification, or measured
performance of an implemented converter. P06 must certify the actual final
coefficient bytes and extrema independently.

`sdm_short_stress.json` contains 192 scalar recurrence cases of 0.125 second each.
They deliberately bypass PCM interpolation. They demonstrate why finite-only
state checks are insufficient, while providing no universal stability claim.
The recorded amplitudes have eight significant digits; exact original command
arguments were not retained for every case. The replay helper discloses this
precision limit. Future qualification must retain full-precision stimuli,
commands, hashes and state checkpoints.

`remodulation_level.json` records a baseline 1 kHz experiment. An explicitly
reconstruct-first path with requested `gain -3` measured approximately -9.02058 dB
relative to the reconstructed source because ordinary PCM half scaling was
applied again. This supports carrying a DSD reference calibration into the new
remodulator. The source and reconstruction both use the baseline sox_ng, so this
is an ordering/level reproduction, not an independent audio-quality oracle.

`environment.json` identifies the source/input hashes, compiler, interpreter,
CPU features and virtualized host. No new-engine speedup, full hardware matrix,
licensed Saracon comparison or player/DAC qualification is claimed.

## Build the baseline

Use a fresh extraction of the supplied source archive. The documentation overlay
does not change production code. `REPO` below must be an absolute path.

```sh
export REPO=/absolute/path/to/sox_ng
cd "$REPO"
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j3
make check
```

## Reproduce format and seek observations

Run from this evidence directory after building the baseline. The explicit link
flags below match this session's static build. On another build, use its actual
optional dependency flags rather than deleting supported dependencies to fit this
example. Binaries/results are intentionally placed outside the evidence folder.

```sh
export RESULTS=/absolute/path/to/new-results
mkdir -p "$RESULTS"
cc -O2 -I "$REPO/src" probe_io.c "$REPO/src/.libs/libsox_ng.a" \
  -lpng -lz -lm -fopenmp -o "$RESULTS/probe_io"
python3 reproduce.py --sox "$REPO/src/sox_ng" \
  --probe "$RESULTS/probe_io" --out "$RESULTS/format"
```

The script constructs tiny files itself and removes temporary fixtures. Nonzero
results for expected baseline defects are recorded in JSON, not concealed as a
successful format conversion. `MALLOC_PERTURB_=85` makes the existing first-byte
accumulator defect repeatable on this allocator. Other allocators need a suitable
nonzero-allocation test mechanism; absence of this allocator feature is not proof
that the code initializes the buffer.

## Reproduce filter feasibility

The probe needs NumPy and SciPy; their observed versions are in `environment.json`.
It writes next to its own script, so copy it to a separate result directory first.

```sh
mkdir -p "$RESULTS/filter"
cp probe_filters.py "$RESULTS/filter/"
python3 "$RESULTS/filter/probe_filters.py"
```

Do not install the generated candidate NPZ as production coefficient authority.
The implementation uses checked-in hexadecimal constants and a separately
certified manifest as specified in P06.

## Replay short scalar SDM stress

The probe includes the reviewed `sdm.c` to inspect its private recurrence state.
This is a test-only technique, not the production extraction architecture. Disable
the x86 include branch so the scalar path is the one measured.

```sh
cc -O2 -ffp-contract=off -DSOX_SDM_X86_H \
  -DSOX_SOURCE=\"$REPO/src/sdm.c\" -I "$REPO/src" \
  probe_sdm.c "$REPO/src/.libs/libsox_ng.a" \
  -lpng -lz -lm -fopenmp -o "$RESULTS/probe_sdm_scalar"
python3 replay_sdm_probe.py --probe "$RESULTS/probe_sdm_scalar" \
  --out "$RESULTS/sdm-replayed.json"
```

A replay uses the rounded amplitudes stored in the original JSON, as noted above.
Do not demand identical chaotic output trajectories or claim the replay is a
full interpolation/stability qualification. New acceptance tests must freeze
full-precision stimulus generation and the complete conversion profile.

## Reproduce the remodulation level observation

```sh
python3 probe_remodulation.py --sox "$REPO/src/sox_ng" \
  --out "$RESULTS/remodulation-level.json"
```

The JSON includes command arrays, exit codes, stderr, measured amplitudes and the
scope of the inference. Source generation and reconstruction remain baseline
sox_ng operations. P10 must add independent analysis for the new encoder.

## Interpretation rules

Baseline reproduction scripts are evidence, not the finished regression harness.
P00 ports them into named expected-failure tests with independently checked
fixtures; later phases remove only the matching expected failure after the fix.
The design specifies tests not yet run as acceptance work. A missing test, host,
codec or reference corpus remains a named gap. Do not reinterpret this package's
successful baseline build as completion of any implementation phase.
