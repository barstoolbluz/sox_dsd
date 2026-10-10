# P10 corrective engineering handoff: fixture classified; release incomplete

**Disposition: `INCOMPLETE`, all three profiles `qualified=false`; promotion blocked.**
This is an authoritative P10 continuation, not a P11 transition. The original
P10 handoff and failure evidence remain intact; do not interpret their old
`FAILED` release verdict as a new failed nominal-v2 soak.

Revalidation corrected the nominal-soak receipt writer and the qualification
collector; see `P10_REVALIDATION.md`. The original measurements and release
disposition are unchanged.

## Determination and why it is supported

The human reviewer's proposed guidance was correct *conditionally*: §7.2 of
`docs/dsd/DSD_DESIGN.md` admits a post-interpolation modulator-domain maximum
of 0.5 plus two source-int32 LSBs, requires explicit overload rejection, and
allows explicit PCM attenuation. The original 0.7-peak noise stimulus exceeded
that envelope, but the originally measured first overload did not by itself
establish whether SRC/prefilter gain was wrong. We independently resolved that
question by observing the real composite signal at source -> R SRC -> centered
non-decimating prefilter at R -> native SRC -> half reference scale. The staged
measurement implementation adds an optional, read-only test observer to the
private encoder; production leaves it null. No coefficient, guard, modulator,
limit, reference convention, public API, or default activation changes.

The actual measured 9 source/target DC paths (48 kHz, native working R, and
705.6 kHz for each of three DSD rates) have SRC/prefilter steady-DC ratios
within approximately 3.1e-10 of unity; the final source-reference ratio is
**exactly 0.5** in each run. This settles unity DC transfer, not universal
frequency-domain gain. The measured noise RMS falls after prefiltering while
its *sample peak* rises because of filter ringing/intersample overshoot; the
30-second direct stage histograms and counts are in
`tests/dsd/results/P10_corrective/stage-audit/`. The existing acceptance
envelope correctly rejects this prefilter/interpolation peak. The inferred
sigma from the first failure time was not used.

Observed 30-second direct scaled noise probes (original 0.7 source / nominal
0.45 source / explicitly attenuated 0.7 source):

- DSD64: original fails, original observed prefix peak 0.51616310; nominal
  peak 0.34366698, RMS 0.10484492; attenuated peak 0.34366698.
- DSD128: original fails, original observed prefix peak 0.50024823; nominal
  peak 0.32251858, RMS 0.09082474; attenuated peak 0.32251858.
- DSD256: original fails, original observed prefix peak 0.52544043; nominal
  peak 0.34603014, RMS 0.10497812; attenuated peak 0.34603014.

The original noise measurements are **rejected prefixes**, not representative
full-run RMS estimates. Nominal peak headroom in these probes is respectively
3.2566, 3.8083 and 3.1971 dB. Explicit source PCM attenuation of
`20 log10(0.45/0.7) = -3.837710525 dB` gives the same intended noise level. The extra int32 re-quantization can
change individual source samples by one quantization step; the two source
streams are not bit-identical. Both versions pass the observed admission and
stability checks without silently attenuating inside the encoder. The original error's
`minimum_attenuation_db` is a minimum from the first *observed* crossing, not
a guaranteed attenuation for the remainder of a longer stream.

## Versioned fixtures and exact failure reproduction

- **Original-v1**: `test_p10.c --soak`, repeated 0.7 source-peak noise, retained
  in `tests/dsd/results/P10/soak/`; remains an **expected-error** case.
- **Nominal-v2**: `test_p10.c --soak-nominal-v2` has *only* the deterministic
  noise segment's source peak changed from 0.7 to 0.45. Other segment levels,
  timing, seed, ramps, scale, rates, FIR, SDM and guard bounds stay unchanged.
  The separately versioned manifest is
  `tests/dsd/reference/p10_soak_nominal_v2.json`. It makes no claim that an
  arbitrary signal whose stored samples peak at 0.45 will always be admitted.
- Exact original-error regression: DSD64 first bad frame 679,008,316
  (failure value -0.50326254060808184); DSD128 frame 1,480,795,051
  (-0.50024823454607048); DSD256 frame 2,711,912,887
  (-0.50191309275781371). New replay reports and checkpoint states match
  their preserved originals byte-for-byte. Failure remains fatal and no
  successful completion is reported.

## Completed 30-minute qualification sequences (nominal-v2)

All three executed one continuous 1,800-audio-second mastering pipeline, with
30 per-minute states, a final state, exactly recorded input/native sample
counts, guard checks, no nonfinite states, no resets and no overloads.

- **DSD64**: 5,080,320,000/5,080,320,000 native frames, peak 0.400000,
  zero 28-bit excursions; 28-bit population 7–21; highest eighth-order state
  magnitude 3,044,464.3244, within its frozen guard.
- **DSD128**: 10,160,640,000/10,160,640,000 native frames, peak 0.400000,
  zero 28-bit excursions (diagnostic), population 6–22; highest eighth-order
  state magnitude 3,082,463.5880, within frozen guard.
- **DSD256**: 20,321,280,000/20,321,280,000 native frames, peak 0.400000,
  zero 28-bit excursions (diagnostic), population 6–22; highest eighth-order
  state magnitude 3,177,425.8374, within frozen guard.

The `soak.json` checker verifies all 31 snapshot hashes per rate and the
executable and source-generator identities, reported frame counts, bounded
states, final EOS and complete DSD64 28-bit monitoring. A passing 1,800-second
synthetic soak is explicitly not the one-hour representative-hardware gate.

## Numerical, regression, performance, and release gates

- Original analysis-v1 is unchanged (all nine locked resources). Frozen P09
  exact-rate NTF identities, FIR coefficients, training bounds and original
  negative certificates remain unchanged. The original P10 51-case training
  and 183-run holdout/control numerical evidence retains its measured results.
  The new corrective executable produced **183/183 bit-identical** native
  streams and identical significant state/frame fields against those records.
  This establishes fidelity of the unchanged numeric results; it is not a new
  independent analysis. The original 13-case DSD64 residual aggregate was
  **35.9083618657 dB better** than legacy, with no material matched-case
  regressions and admitted-window/spur/guard checks passing.
- Clean compiler/configuration, `make check` **PASS**, `make check-dsd`
  **PASS (36 pass, 0 fail, 0 skip)**, 105,474 unit assertions with 0 failures,
  63 CLI cases with 0 failures, three replay-contract tests and fourteen
  qualification-accounting tests. The corrective adversarial verifier passed
  seven scenarios including modified stages, corrupt bits, changed original
  failure frame, short native output, tampered snapshots and a false-positive
  nominal certificate.
- Controlled-host P09→P10 native read/repack gate **PASS** as inherited:
  `tests/dsd/results/P10/bench-read-prepared-host-2026-10-09/bench-read.json`,
  sixteen cases and worst +1.02% median regression, with qualifying confidence
  intervals/noise. This is **the previous P10 executable**, not a new timing
  claim for the observer-augmented corrective binary, nor an encoder throughput
  speedup claim. No native read/repack source changed in this round.
- Independent clean-source extraction: Autotools, build, `make check`,
  `make check-dsd`, the frozen-reference lock and adversarial checker passed.
  A second binary compiled at a different source path had a **different debug
  executable SHA-256** but reproduced all **183/183** inherited native-bit
  hashes and significant state/frame fields without discrepancies. Both
  executable identities are kept separately in
  `results/P10_corrective/source-archive-verification.json` and
  `results/P10_corrective/rebuilt-bit-equivalence/bit-equivalence.json`.
  These are re-execution checks, not newly analyzed reference audio.
- **UNRUN: one-hour mixed-content soak per released profile/ISA family on
  representative hardware**, as required by design §10.5.
- **UNRUN: independent real-world PCM/DSD mastering-source corpus**. Generated
  deterministic stimuli, even 30 minutes long, cannot substitute for it.

This round **does not qualify or activate** the three profiles. The new
`tests/dsd/reference/p10_profiles_corrective.json` records the passing
corrective gates and remaining obligations for each native rate; original
`p10_profiles.json` stays byte-identical. Production continues to decline
unqualified mastering profiles; test-only candidate access remains explicit.
No defaults change before P15 regardless of these results.

## Reproduce from a clean extraction

Use a supported C toolchain, Autotools, and P10's documented dependencies.
Commands are relative to the repository root; results are isolated from P00–P10:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
make -j2 check
make -j2 check-dsd DSD_RESULTS="$PWD/tests/dsd/results/P10_corrective/regression"
test/dsd_test_p10 --unit
python3 tests/dsd/test_p10.py --sox src/sox_ng --candidate test/sox_p10_candidate --results tests/dsd/results/P10_corrective/cli
python3 tests/dsd/test_p10_qualification.py
python3 tests/dsd/soak_p10.py --test-replay --results tests/dsd/results/P10_corrective/replay
python3 tests/dsd/verify_p10_corrective.py --verify-only --results tests/dsd/results/P10_corrective/stage-audit
python3 tests/dsd/test_p10_corrective_qualification.py
python3 tests/dsd/generate_p10_corrective_profiles.py --check
python3 tests/dsd/qualify_p10_corrective.py
```

All acceptance commands above finished exit **0** in this corrective run,
except the final qualification collector, which deliberately exits
**2 (`INCOMPLETE`)**. `--verify-only` rechecks recorded stage distributions
without rerunning probes. The numeric replay that originally generated
`bit-equivalence/` exited 0 after all 183 cases, but it is **not** rerun
against a newly compiled binary using the old pinned receipt directory.
Likewise `--inspect` of recorded 30-minute soaks requires their original
executable hash, not merely a compatible rebuilt executable: that identity
mismatch is an appropriate failure, not a changed DSP result. The portable
qualification collector validates the archived evidence itself without
asserting a newly rebuilt executable was bit-tested.

For a fresh binary, run:

```sh
python3 tests/dsd/replay_p10_numeric_bits.py --results tests/dsd/results/P10_corrective/rebuilt-bit-equivalence
python3 tests/dsd/verify_p10_corrective.py --results tests/dsd/results/P10_corrective/rebuilt-stage-audit
python3 tests/dsd/soak_p10.py --fixture nominal-v2 --seconds 1800 --segment-seconds 60 --results tests/dsd/results/P10_corrective/rebuilt-nominal-soaks
```

These are new, versioned executions and may take substantial CPU time. Do not
pass `--unit` to the main collector unless its SHA-256 actually matches the
executable pinned in the original receipts; a fresh `-g` build at another
filesystem root may legitimately have a different binary hash. The
original-v1 soak exits **nonzero** by design; its identical fatal failure is
verified in `original-overload/verification.json`. Existing completed results
are retained unless `--replay` is explicitly requested, which verifies state
identities rather than pretending to deserialize the opaque SRC state.
This source-only handoff retains all new raw evidence, including the original
failure reproduction, and a regenerated P00 archive-member SHA-256 index.

The runs took place on Linux x86_64, Debian 13, AMD EPYC 9V74 virtual host,
with a four-CPU cgroup quota; it is not asserted to be representative hardware
for all required ISA families. Source tree archive verification and frozen
resource hashes are checked separately at delivery.

## Changed components and continuation

Changed existing files: `src/pcmdsd.c`, `src/pcmdsd.h`, `tests/dsd/test_p10.c`,
`tests/dsd/soak_p10.py`, `Makefile.am`, and the regenerated
`tests/dsd/results/P00/P00_SHA256SUMS.txt`. New versioned fixture, new
stage/soak/bit-equivalence collectors and adversarial test, new corrective
profile manifests, this handoff and checkpoint, and new results only under
`tests/dsd/results/P10_corrective/`.

**Next permitted work:** complete representative-hardware/ISA one-hour tests
and an independently sourced real-world corpus for the three selected rates;
use separate versioned evidence paths. Fail closed on any new result that
breaches the held-out guard/envelope, 28-bit requirement, numerical quality or
source/output accounting. Do not redesign, normalize, raise guard bounds,
overwrite previous evidence or promote while mandatory gates remain unrun.
