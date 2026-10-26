# Independent register-SDM qualification

`test_sdm_register.c` compares the implementation under test with the surviving
original scalar source. `reference/sdm_register_oracle/` contains byte-for-byte
copies of that source and the arithmetic headers it includes. The provenance
file records the input archive and every frozen file's SHA-256. The runner
verifies those hashes before compiling the oracle under renamed public symbols.
Candidate monitor/acceptance code is not shared with the oracle.

## Run

Use a configured native build directory containing `src/soxconfig.h`:

```sh
python3 tests/dsd/run_sdm_register.py \
  --build /absolute/path/to/build \
  --output /absolute/path/to/evidence/register \
  -- --exceptions

python3 tests/dsd/run_sdm_register.py \
  --build /absolute/path/to/build \
  --output /absolute/path/to/evidence/register-sanitized \
  --sanitize address,undefined \
  -- --exceptions
```

The standalone runner currently targets GCC/Clang with GNU-compatible Linux
linker flags. It compiles scalar, dispatcher and every configured SIMD tier
separately, then tests only tiers supported by the host and OS. Its strict
floating-point settings include `-ffp-contract=off`, `-fno-fast-math` and
`-frounding-math`. GCC's normal `-O3` strict-aliasing behavior remains enabled.
Each run records commands, compiler identity, source/configuration hashes,
binary hash, console output and exit status.

For an ASan run, the runner looks for `libsox_native.a` or
`src/.libs/libsox_ng.a` in the build directory. `--support-library PATH` can
select another static SoX archive. ASan's global registry retains otherwise
unused legacy effect callbacks; the archive resolves their support routines.
Every kernel and the oracle exercised by this test is compiled with the
requested sanitizer instrumentation.

If LeakSanitizer cannot inspect `/proc` in a sandbox, run with
`ASAN_OPTIONS=detect_leaks=0`. This disables only leak detection; address and
undefined-behavior instrumentation remain active. Report that limitation rather
than treating a LeakSanitizer startup/exit failure as a passing leak check.

The following binary arguments reduce the matrix for diagnosis and are not
substitutes for a complete qualification run:

```sh
/path/to/evidence/register/test_sdm_register --quick --tier avx2 --case 12
```

`--quick` uses round-to-nearest with DAZ/FTZ disabled. `--tier NAME` selects one
supported tier. `--case N` selects one case family, numbered 0–32. The
`--exceptions` option additionally compares all standard sticky FP exception
flags after each call and, on SSE2 x86, all six MXCSR status bits including the
denormal-operand flag omitted by C's `FE_ALL_EXCEPT`. The complete qualification
command enables it.

## Coverage

The full matrix includes all 16 registered profiles, five available tiers,
four rounding modes, and four DAZ/FTZ combinations when the FXSAVE MXCSR mask
advertises optional DAZ support. On a CPU without DAZ it uses the two supported
FTZ modes. No optional MXCSR bit is set without checking the hardware mask.

Every pair compares the return status, committed prefix, failing coordinate,
both complete state banks, previous decision, frame index, every monitor byte,
all output slots (including the untouched suffix), input/bound mutations and
peak bits. It also checks equality of the original/candidate profile
coefficients and order before running each profile.

Cases exercise:

- 512-frame production blocks and continuation across lengths 0, 1, 2, 7,
  27, 28, 29, 511, 512, 513 and 521, including monitor attach/detach.
- Positive/negative zero, minimum and maximum subnormal values, minimum
  normals, extreme finite values, infinities, and quiet/signaling NaNs with
  distinct payloads. These enter input, active/inactive state, previous
  decision, bounds, the independent peak, and monitor maxima.
- Rejections at block starts and after committed prefixes, frame limits,
  envelope crossings, first failing coordinate, and inactive-tail preservation.
- Saturation of 64-bit frame/window/excursion/overload/nonfinite counters and
  the 32-bit run-length counter, plus the 27-to-28-bit history transition.
- Every state coordinate as a peak alias; peak aliases to input, bounds,
  previous decision and monitor maxima; input aliases to either state bank,
  bounds or monitor maxima; and bounds aliases to state, input or monitor.
- Committed-count aliases to frame counters when `size_t` and `uint64_t` have
  the same underlying type, and failing-coordinate aliases to existing
  `unsigned` fields. These tests use existing objects with compatible types.
- Deterministic random bit-pattern states, invalid arguments, null optional
  pointers and empty blocks.

This is an extensive finite differential suite, not an exhaustive enumeration
of all binary64 values. The transformation's correctness argument remains in
the engineering proof. Unmasked trap timing, other compilers/operating systems,
physical AVX-only machines and 32-bit x87 builds require separate qualification.
