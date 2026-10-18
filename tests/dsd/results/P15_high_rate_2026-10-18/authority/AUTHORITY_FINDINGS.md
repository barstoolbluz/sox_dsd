# P15 high-rate work: inherited integrity and independent obligation review

Date: 2026-10-18. Scope: the supplied third-pass archive and the corresponding
high-rate working tree. **P15 remains BLOCKED. No v2 default promotion or P16
authorization is issued.**

The machine-readable findings are in `SECONDARY_OBLIGATIONS.json`; the complete
inherited-file manifest is `INHERITED_FILES.sha256`. These are new reports.
Historical measurements, their statuses, and the old closeout program are
unchanged.

## 1. Source and historical evidence integrity

The submitted archive SHA-256 is
`d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4`.
`verify_inherited_integrity.py` verified that digest and streamed the archive,
comparing every selected file with the working tree. It verified:

| Scope | Unchanged files |
| --- | ---: |
| Original pinned source set | 35 |
| Original complete-campaign interval receipts | 11,516 |
| Original partial-campaign interval receipts | 5,112 |
| Original budget-sample receipts | 48 |
| **Previously audited subset** | **16,711** |
| **Broader unique-file audit** | **33,487** |

The broader audit includes all 276 original `src/` files, 149 original
`docs/dsd/` files, 33,050 original historical result files, and 12 additional
pinned files outside those prefixes. Overlap with the 16,711-file subset is
counted once in the broader total. It permits newly added files while refusing
changes, removal, or conversion to symlinks of inherited regular files.

The earlier verifier is intentionally bound to the pre-first-pass archive,
SHA-256 `82c6e31d...4365c2`. It was preserved. It must not be altered simply to
accept this different submitted archive.

The third-pass tar enumerates files in another order, so its ordered subset
digest differs from the earlier verifier's digest. This was resolved, rather
than waived: lexical ordering of the verified 16,711 subset reproduces the
original inventory digest **exactly**:

`c9856e34443f81ec390a5c934718deac46ce6bee4aa733cf04e7d01f0f16c059`.

The broader sorted SHA-256 manifest itself has SHA-256:

`173f819d8884f50237c126c71c66c7b3222c8d1f39f0a4270966a402bce12783`.

This establishes both preservation relative to the supplied archive and
continuity of the inherited 16,711-file inventory. `INTEGRITY.json` retains
the initial tar-order audit; `SECONDARY_OBLIGATIONS.json` records the exact
reconstructed original digest.

## 2. DSD256 physical P/S-matched comparison exists

The physical benchmark under
`tests/dsd/results/P15_ps_matched_physical_2026-10-16/` is not missing. Its
receipt records a prepared physical AMD Ryzen Threadripper 7970X, Linux
6.12.85, microcode `0xa10810c`, performance governor, CPU 8 affinity, two
warmups, and 15 repetitions per arm. The fixture is six-channel DSD256.
The recorded host satisfies the instrument's physical-host admission rule.

The corrected matched control has the passband edge P, stopband edge S,
transition width S−P, and transition center (P+S)/2. The prior October 15
control used a different transition convention and was rejected at the v2
66 kHz passband edge. The corrected control was measured on October 16.

An independent implementation of the specified seeded bootstrap recomputed
all eight comparisons from the saved timing arrays. Every point estimate,
both confidence endpoints, and the Boolean threshold outcome agree exactly
with the saved receipts. The bootstrap uses 10,000 draws, seed 20261016,
independent 15-sample resampling of both arms, medians, and the recorded
2.5%/97.5% order-statistic convention.

| DSD256 profile / PCM Hz | Control | Median ratio | 95% bootstrap interval |
| --- | --- | ---: | --- |
| mastering / 176400 | direct | 3.912998 | [3.899404, 3.923272] |
| mastering / 176400 | P/S matched | 4.021263 | [4.005310, 4.031206] |
| mastering / 352800 | direct | 3.784159 | [3.755343, 3.807276] |
| mastering / 352800 | P/S matched | 3.799646 | [3.772831, 3.823466] |
| mastering_v2 / 176400 | direct | 3.779405 | [3.771551, 3.784429] |
| mastering_v2 / 176400 | P/S matched | 3.886603 | [3.880483, 3.893408] |
| mastering_v2 / 352800 | direct | 3.672967 | [3.628940, 3.684383] |
| mastering_v2 / 352800 | P/S matched | 3.688606 | [3.640507, 3.698100] |

All eight lower endpoints exceed 2. The exact minimum is
`3.6289395223087637`.

### Binding and replay limits

All eight recorded source pins still match the current working tree. The
comparator and benchmark name the same two executable hashes, and the
benchmark's comparator-receipt hash matches the actual comparator receipt:

- Benchmark receipt: `5c5f4a479601f833df68cc282730f7f76ed9f8b27875171c1bf903f25ab01511`.
- Comparator receipt: `9af8aefb18e7dc3e557a789960401585f734e10b7cd23cc7b099f020d75b1a7a`.

This is a verification of the **recorded** source scope. That map does not
include `rate_poly_fir0.h`; it does not establish physical timing of the
subsequent October 17 opt-in SRC build. The exact historical executable
paths are unavailable here. The October 17 rebind authority already retains
the physical measurements under their original scope.

Twelve audio payloads are absent: ten comparator audio files and the two
timing input fixtures. Their hashes are retained; the physical README says
the bulk audio was deleted after recording those hashes. Consequently, the
existing strict `--verify-only` path cannot complete here: it requires the
audio and exact binaries. This audit recomputes timing statistics and checks
available provenance without claiming independent audio replay. Recovering
the exact retained originals, if they exist elsewhere, is distinct from
repeating the physical timing experiment.

The saved noise-comparison diagnostics run from **1 kHz through the
guaranteed passband edge**, with zero upper-edge transition exclusion. They
report maximum decoder/control differences of approximately 0.002015,
0.000956, 0.006105, and 0.003639 dB over the four cells. They are comparator
diagnostics, not continuous-frequency absolute-transfer certificates, and
do not prove the 0.0001 dB / −160 dB spectral contract. No DC coverage is
inferred from a diagnostic starting at 1 kHz.

The governor is recorded in the receipt. Boost disabled is stated in its
README, rather than encoded in the JSON. That limitation is preserved.

### Correct gate interpretation

The saved disposition is `MEASURED_PHYSICAL_UNADJUDICATED`, with
`qualified_release: false`. The accompanying README explicitly defers gate
adjudication. `p15_current_closeout.py` still selects the superseded October
15 per-profile control receipts; its `OPEN` is not an adjudication of the
October 16 result. The remaining distinctions are formal review, exact
historical executable scope, and unavailable audio replay—not an absence
of physical measurements. No repeated physical benchmark or changed
release ledger was necessary for this high-rate spectral assignment.

## 3. V2 observed coverage is complete; qualification is incomplete

The old v2 extension handoff described one full-duration cell. The later
retained matrix is more complete. Calling the existing current-source matrix
reviewer directly verified the following from worklists, sessions, cell
receipts, recorded source pins, and hashes of available payloads:

| Observation | v1 rebound matrix | v2 matrix |
| --- | ---: | ---: |
| Scalar cells | 54 | 27 |
| Forced ISA jobs | 216 | 108 |
| Detailed ISA comparisons | 96 | 48 |
| Native frames per full-duration cell | 262,144 | 262,144 |
| Recorded source pins per session, excluding library binary | 17 | 22 |
| SRC-active cells | 48 | 24 |
| True SRC bypass cells | 6 | 3 |
| Omitted numeric `.npz` files | 270 | 135 |
| Missing recorded scalar graph payloads | 0 | 0 |

All recorded source pins matched. The four scalar graph payloads per cell
were present and digest-checked. This was not a new waveform analysis or a
replacement for the omitted numeric arrays. Exact historical executable
reconstruction also remains outside this source-only audit.

Thus the **observed-cell coverage gap** from the early one-cell handoff is
no longer the gap. The relevant remaining work is independent numerical
replay with the original hash-matching arrays, same-operator arithmetic
acceptance for the SRC paths, and complete composite spectral/alias
qualification. Existing observations are not qualified just because their
record count is complete. There is no new requirement to repeat otherwise
valid hardware or soak matrices.

## 4. Arbitrary-input FFT4G execution remains independently OPEN

`DSD_DESIGN.md` §8.6.1 requires the same captured effective operator W and
input-dependent `N_ops`, `B_coeff`, and `B_other` terms, including finite
boundaries. `p15_fft_coefficient_interval.py` certifies captured precomputed
coefficient-bin error. It explicitly does not bound arbitrary runtime
forward/inverse transforms, packed multiplication, accumulation, or
nonstandard/subnormal arithmetic. Source-bound ideal-FIR spectral certificates
cannot discharge that execution obligation.

The authority also allows comparing against exact captured binary64 W;
there is no extra ideal-Kaiser-generator proof required merely to certify
that particular realized W. Such a theorem would be a separate claim.

The intended eventual v2 default remains conditional on qualification. The
temporary v1 default, explicit v2 opt-in, preserved v1 coefficients, and
encoder policy remain unchanged. P15 is BLOCKED and P16 is unauthorized.

## 5. Reproduction and interruption checkpoint

From the corrected repository root, with the supplied archive available:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/authority/verify_inherited_integrity.py \
  --root . \
  --submitted /path/to/sox_ng_P15_prover_third_pass_FULL_SOURCE_2026-10-18.tar.gz \
  --output tests/dsd/results/P15_high_rate_2026-10-18/authority

PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 \
python tests/dsd/results/P15_high_rate_2026-10-18/authority/review_secondary_obligations.py \
  --root . --output tests/dsd/results/P15_high_rate_2026-10-18/authority
```

Both scripts publish new results exclusively, accept an identical replay,
and refuse conflicting evidence. `review_secondary_obligations.py` requires
the integrity manifest from the first command. This environment additionally
prepends `/workspace/scratch/47ef0cb747fa/deps` to `PYTHONPATH` for mpmath.

Eight existing focused tests passed against the frozen third-pass baseline:
the physical-method test class, three v2 worklist/profile tests, and the
mandatory opt-in contraction-guard test. Raw output and the actual command
are preserved in `FOCUSED_TESTS_BASELINE.json`. An earlier run against the
live working tree occurred while the new halfband module was being added;
its expected transient missing-module errors remain in `FOCUSED_TESTS.json`
and are excluded from successful validation. After the module was integrated,
the same eight tests passed against the candidate; that raw run is preserved
separately in `FOCUSED_TESTS_CANDIDATE.json`.

The independent alias-population review added eight adversarial tests in
`tests/dsd/test_p15_high_rate_population.py`. All eight passed in 3.352 seconds.
`POPULATION_REVIEW.md` documents their mathematical scope and the independent
cap review. Those tests assess the new shortcut; they are not release
adjudication or whole-cell spectral certificates.

No physical measurements were performed in this environment. No old receipt,
normative document, production DSP source, or historical status was modified.
