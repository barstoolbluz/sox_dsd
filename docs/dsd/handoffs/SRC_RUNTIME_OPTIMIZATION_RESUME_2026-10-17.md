# Production SRC optimization continuation checkpoint — 2026-10-17

## Current decision

The requested production C optimization, local functional/numerical validation,
repeated virtual-host performance measurements, documentation and packaging are
complete. Retain the new ordered rational-FIR implementation as an explicit
opt-in candidate. The ordinary build still executes the inherited code.
P15 remains BLOCKED; `default_promotion_authorized=false` and
`p16_authorized=false`. This is not a prepared physical-host qualification.

The final engineering report is
`docs/dsd/SRC_RUNTIME_OPTIMIZATION_2026-10-17.md`. Read it together with the
separate proof, P15 assessment and reproduction document of the same date.
Those files and the final evidence index supersede prospective wording in
earlier experimental snapshots. Never replace an unfavorable original result
with a later diagnostic repeat.

## Exact source and build identities

| Item | SHA-256 |
| --- | --- |
| Original attached complete archive | `f827eeb830a68f54b99c50ad6073ba1a0febec5478403a37a49f79d4e2f484fc` |
| Frozen `src/rate_poly_fir0.h` | `928f005912f35ca0612a37c99a9a6343be8dea51e23cd41f5286b9f85fede6ff` |
| Final `src/rate_poly_fir0.h` | `c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591` |
| Frozen CLI | `fad06a388cbf112945a1e66a8f4fd6213a156f9a5f8919a66efe7ed1dd94a004` |
| Candidate CLI | `750ea8d25c563ee5f12ebb587b4613f8669c441a3f7b8c8057ef92ce76774f42` |
| Production patch | `354f6c0c824587c9a5767e544bdd139105541810b5fa45cea5de78dbb05d81e8` |
| Consolidated benchmark JSON | `f8c98b616ccc2ba67e98539cfc8a734f38c6b6dc44294b4be8303707a88ea56e` |

The input archive has 235,030,066 bytes and 15,498 original regular files.
The final audit verifies that only the intended header differs and no original
regular file is missing. Frozen reference headers and provenance are in
`tests/dsd/reference/src_optimization/`. Restore its `rate_poly_fir0.h` over
the production header to recover the original source, or reverse the minimal
production patch. All other pre-existing files, including original receipts,
coefficients and Python provers, remain unchanged.

The candidate adds 68 lines, deletes none, and introduces exact quotient/remainder
recurrence plus two independent output accumulators. It retains ascending tap
order and each output's original floating-point operation graph. A call-level
`max_num_out > 2` condition selects it only for larger output-capacity bounds.
There is no persistent state, new allocation, ABI change, CLI change, dependency,
FFT rewrite or DSD reconstruction rewrite.

Measured GCC 13.3.0 flags are `-O2 -g -ffp-contract=off`; the candidate adds
`-DLSX_RATE_ORDERED_OPT=1`. No fast math, reassociation or contraction is allowed
for the stated category-1 contract. The source additionally requires a defined
`FLT_EVAL_METHOD==0`; otherwise it uses the original body. The final default-off
`rate.o` and linked CLI text sections match the frozen build byte for byte.
The older 24-conversion default-off replay belongs to the preserved guard1
revision, not the final guard2 build.

## Validation and performance

The final exact regression passes 768,060 checks: 53,856 direct cases,
288 streaming cases, 50 private binary64 API cases and 5,409,850 binary64 words
compared exactly. Kernel tests cover four rounding modes. The fully instrumented
216-object ASan/UBSan library passes the same regression with empty stderr.
LeakSanitizer explicitly rejected the ptrace environment; leak checking remains
UNRUN. O3 and x87 are focused translation-unit checks linked to baseline support,
not full-application qualifications. All 16 invoked existing focused suites and
148 generic conversions pass; seven unavailable optional formats are skipped.

The reviewed operator comparison passes 24 initialized graphs, 43 stages,
59,854 coefficient words and 123,904 FFT-bin words. Twelve graphs contain the
rational FIR family. Exporting initializes graphs; it does not execute audio.

The accepted CLI summary has 72 records: 70 distinct configurations
(49 primary and 21 revised controls) plus two 30-pair diagnostic repeats.
It records 2,652 correctly sized, exactly matching baseline/candidate
conversions, including 2,220 timed conversions. The corpus contains
40 PCM and 30 DSD configurations. Ratios above one favor the candidate.

Common stereo `rate -v` conversions improve by 1.26756× for 44.1→48 kHz
(95% paired CPU interval 1.21118–1.30206×) and 1.28295× for 48→44.1 kHz
(1.18365–1.34608×). The 44.1→96 kHz case improves 1.37577×
(1.32606–1.41481×). All twelve revised PCM quality/buffer controls have CPU
intervals above one in this run. Most native DSD observations are near parity.

| Sustained original adverse case | Original paired CPU ratio [95% interval] | Diagnostic repeat [95% interval] |
| --- | --- | --- |
| `dsd64_mastering.v2_176400` | 0.975706× [0.928325, 0.997304] | 0.983373× [0.951577, 1.00279] |
| `dsd256_mastering_v1_176400_stereo_continuity` | 0.990731× [0.970026, 0.996971] | 1.01044× [0.980686, 1.04566] |

Both repeat intervals include one; neither proves the absence of a slowdown.
The original adverse observations remain in the final evidence. A short
PCM→88.2 kHz case also has a wall-only interval below one. Per-case intervals
are unadjusted for multiple comparisons. CPU relative MAD exceeds 2% in
129/140 primary/control arms and 4/4 repeat arms, so these VM observations are
not a physical-host acceptance gate. Full wall/CPU throughput and launcher-inclusive
RSS are in `BENCHMARK_TABLES.md` and `benchmark-summary.json`.

The final real-FIFO benchmark has all 765 expected rows. Sustained 4,096-input
calls improve 1.42–1.92× over the original. One/two-input 26-tap calls retain
about 4.45/4.91 ns extra latency, or 15.3%/15.6% higher median time. Returning
to the scalar body under the guard does not restore the old function layout.
The full-CLI small-buffer cases are faster; that does not erase the isolated
tiny-call regression.

## Evidence provenance and inherited findings

Evidence root:
`tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/`.

The original primary `work-evidence/final-paired/measurements.json` remains
RUNNING with 1,761 saved rows, despite a completion message. Its SHA-256 is
`8f7d6edbd8d50edc905eff86b185c06b74093e3ee20001fe1f2f3a033cc70419`.
The extractor verifies and selects 48 complete cases / 1,728 rows, preserving
the parent hash and raw-index mapping. All 33 captured rows from the incomplete
last case are excluded. A new 36-row last-case run uses the identical case and
fixture. No missing timings were reconstructed. The accepted primary therefore
still covers the original 49 configurations. New runs write a separate fsynced
completion record containing the final JSON hash.

The original controls `work-evidence/final-controls/measurements.json` remains
FAIL. For stereo 48→44.1 kHz and ten seconds of input, both builds emit only
2,220 frames with a 32-byte buffer, or 2,234 with 64 bytes, instead of 441,000.
Both produce the correct length at 128 and 256 bytes; their hashes match between
builds at each setting but differ across buffer settings in both builds. This
is an inherited whole-CLI behavior, not a new candidate numerical difference.
The revised reverse control uses 128 bytes, keeps the successful 32-byte forward
case, and preserves the failed receipt and direct diagnostic. No output-length
or equality check was relaxed. CLI bit identity is limited to matching settings.

The current final sources for CLI analysis are `work-evidence/primary-completed/`,
`primary-last-case/`, `final-controls-validated/` and `diagnostic-repeats/`.
The selection policy and cases are retained; the primary and revised-control
corpora are also preserved. Raw historical absolute paths identify the original
workspace. The evidence README maps their prefixes into the delivered folders;
do not rewrite old receipts to point at new binaries. `METADATA_CORRECTIONS.md`
also documents the earlier profiler-instrumentation label, raw-I/O description,
operator-export counter name, incomplete temporary threshold case, LSan failure,
initial P14 invocation error and default-off revision distinction.

## Reproduce or continue

Start with the reproduction document. It gives exact strict build, numerical,
sanitizer, operator and benchmark commands. The helper is Linux x86_64 only;
the exact five-tier ISA controls require scalar, SSE2, AVX1, AVX2 and AVX-512.
On another host, record unsupported tiers as UNRUN and use a distinctly identified
corpus. No hardware-counter or physical-host result can be inferred from this VM.

For a future P15 adoption review, rebind the candidate source/build and all 24
captures explicitly. A reviewed equivalence bridge may reuse unchanged operator
inequalities, but the current prover's raw-source pins do not do so automatically.
Close the existing composite spectral and arbitrary-input FFT4G arithmetic
obligations independently. Preserve the 0.0001 dB ripple and −160 dB coherent-alias
targets. Zero introduced error is relative to the frozen implementation, not a
new absolute filter/FFT error certificate.

The historical eight physical DSD256 comparisons retain their original
PASS-SCOPED status and minimum bootstrap lower bound near 3.629×. Native
mastering identity/DFT routes do not execute this rational kernel. A rebuilt
legacy comparator can become faster, so repeat matched prepared-host comparisons
before transferring the old ratio to a changed comparator or build.

## Delivered artifacts and persistence

The full source archive, evidence archive, minimal production patch, separate
support patch, report, benchmark JSON, complete tables and this checkpoint are
identified by `SRC_RUNTIME_OPTIMIZATION_SHA256SUMS_2026-10-17.txt`. Internal
manifests cover archived regular files, excluding their own manifest file.
External archive hashes remain outside this checkpoint to avoid circular hashes.

The final artifacts are prepared as local downloads. An automatic approval review
rejected the transfer of source code and validation evidence to ChatGPT Library
without explicit user approval for that persistent destination. No upload or
alternative route was attempted after that rejection. Ask for that destination
approval only after presenting the completed files; once authorized, save the
finished package rather than rebuilding it. The earlier working checkpoint is
superseded by this final handoff.
