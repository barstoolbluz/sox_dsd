# P15 independent numerical instrument — resumable implementation checkpoint

Date: October 13, 2026. Governing authority: `docs/dsd/DSD_DESIGN.md`, §§6.1–6.6, 8.6, 10.4; `docs/dsd/sows/P15.md`; `docs/dsd/P15_QUESTIONS_ADJUDICATION_2026-10-13.md`. Starting snapshot: git archive `cb6f10b2`, uploaded SHA-256 `ebcd0355344a058012b49d4a73ba592e28000d09ecf77b280090add0dab8bb1f`, no `.git`. The uploaded build request itself was *not* copied into the source tree.

## Current state and decisions

The test-only independent P15 scalar metrology instrument has been implemented and integrated in source. It supplies an executable 54-cell scalar harness, actual binary64 decoder output probe, independent 75-digit coefficient-composed finite convolution with exact native-count boundary semantics, independently constructed Kaiser-sinc rational SRC, real private SRC spectral tone probes, actual graph clipping/partition/thread checks, supported ISA comparisons, append-only scoped P15 handoff and focused integrity/mutation tests. Reference output, impulse, native-bit, pre-SRC and SRC raw values have a portable relative-path+SHA-256 receipt schema.

Both questions raised by the operator are resolved in the affirmative as regards scope/feasibility: **all 24 fractional destination cells are mandatory**, and mathematical/implementation independence does **not** require a different author. Using an independently authored mpmath/longdouble polyphase implementation with separately constructed coefficients is acceptable; no shared production FIR/SRC evaluator acts as the numerical oracle. SciPy is an independent cross-check only. `analysis-v1` is frozen for the *encoder*, not substituted for the full-band decoder.

The independent SRC deliberately does not use the private SoX window, so composite sample discrepancies are **measured, not certified** against an invented tolerance. The §8.6 scalar-relative FIR roundoff rule is tested at the isolated native reconstruction output, not borrowed for the composite SRC. The P06 certified native-FIR P/S and all-native-image coherent alias bound is inherited with exact bank and six-profile SHA binding. Production SRC transfer is tested on deterministic passband, folded-alias and upsampled-image tones. Those are sampled frequency checks rather than all-extrema/coherent-composite release certification. `qualified` and `release_gate_closed` remain `false` even after 54 successful development rows.

### Real corrections found while testing

- Native streams with 1/33/etc frames (in the no-SRC path) may produce `ceil(N/D)` centered intermediate frames but round to fewer final PCM frames. The independent identity reference now retains only the correctly rounded native-timeline prefix. The first live mutation test caught this before handoff.
- Numerical 75-digit FIR witnesses now use the **original high-precision composed coefficients**, rather than promoting already-rounded longdouble taps back into mpmath.
- On every exception, the single-writer lock is released by `finally`. Resume rejects changed Python/numerical libraries, binary files, coefficients, full cell JSON, raw vector data or SRC tone evidence and refuses illegal `qualified` status.
- Cross-ISA scalar-relative envelope is enforced on the *isolated FIR* at its native intermediate rate. Combined SRC comparison is measured separately; P07 selected-stream limits are labelled **examples only**.
- Short diagnostic captures with too few PCM frames for an analog two-tone gain/noise fit report `UNRUN_SHORT_DEVELOPMENT_CAPTURE` instead of misdiagnosing a production DSP defect. All short runs have `DEVELOPMENT_SAMPLE_ONLY` status; they never close the numerical release matrix.

## Locally executed checks (development environment, not physical-host qualification)

| Command or gate | Observed result |
|---|---|
| `autoreconf -fi` / configured `make -j6` | Successful source generation and compilation of full app/library and both test-only binary64 exporters. |
| `make check` | Exit **0**; normal SoX inherited generic tests passed/expected optional VOID. |
| `python3 tests/dsd/test_p15.py --sox src/sox_ng --results <outside source>` | Exit **0**, **134/134** existing P15 CLI cases. |
| `P15_LIVE=1 python3 -W error::ResourceWarning -m unittest discover -s tests/dsd -p test_p15_instrument.py` | Exit **0**, **17/17** focused numerical/integration/mutation tests; no warning leaks. |
| 54-cell diagnostic `p15_matrix_instrument.py --probe ... --frames 8192` | Exit **0**; **54/54** scalar rows emitted, 0 observed failures. This is explicitly **short-capture only**. |
| 54-cell diagnostic additionally with `--src-probe ... --sox ... --src-frames 8192` | Exit **0**; **54/54** scalar, SRC sampled-tone, actual six-channel SoX graph/clipping/thread rows, 0 detected failures. Not a complete all-extrema spectral certificate. |
| Additional forced-tier probe: `--tier sse2 --tier avx1 --tier avx2 --tier avx512` on DSD64/wideband/48k, 8192 frames | Exit **0**; all four requested tiers available on the development host, isolated scalar-relative FIR differences ~1e-16, composite measured separately, phase tests and graph tests passed. |
| One selected DSD64/mastering/48k captured SRC case | Exit **0**, SHA-bound original sampled SRC output `.f64` files written and verified again on `--resume`. |
| Full-duration DSD128/wideband/48-kHz fractional-SRC sample (`--frames 262144 --src-frames 131072`, raw SRC tone capture and all four forced SIMD tiers) | Exit **0**; finite composite/reference measured (max ~7.20e-5), no execution failure, release still `MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW`. |
| Full-duration DSD256/mastering/705.6-kHz integer-family but SRC-upsampled sample (`--frames 262144 --src-frames 131072`) | Exit **0**; finite composite/reference measured (max ~6.13e-5), no execution failure, release still pending spectral review. |
| Generic P07 SciPy polyphase check | 5 fractional and integer ratios agree with the independently indexed implementation to within floating-point construction/accumulation error (~1e-15), including correct endpoint alignment. |
| Independent replay and corruption tests | Source/manifest mutation, invalid bit/EOF, bad ISA, modified numerical `.npz`, modified session descriptor rejected. |

The inherited multi-phase `make check-dsd DSD_PHASE=P15` was attempted here, and its log reached a **PASS 134/134** P15 CLI stage, but the enclosing command did not return a verified normal final exit before the execution environment stopped observation. The **full gate remains UNVERIFIED**, even though the narrower repeated P15 CLI invocation independently returned exit 0. Never infer aggregate success from preceding phase output. The focused and generic gates above are independently verified.

## Remaining required operator work

1. Unpack delivered **source** in a clean checkout and independently verify the P00 SHA-256 inventory and artifact checksum. Build, then run the 17 focused tests. `docs/dsd/P15_MATRIX_INSTRUMENT.md` contains the exact command; if reproducing in a build dir other than the root, pass the compiled probe paths explicitly.
2. On each real host, execute **all 54 cells** at the baseline duration with `--src-probe`, `--sox`, supported `--tier` arguments, and preferably `--capture-src-raw`. The command is intentionally resumable only under unchanged source, binary, dependency, selected filters and build environment. Unsupported ISA must be covered by another physical/instruction-validating host, not counted as PASS here.
3. Produce/adjudicate an **independent full composite SRC transfer/alias extrema certificate** for the actual P/S, including all coherent contributors through the final SRC. The existing P06 native FIR certificate, full-finite sample reference and sampled SRC tones are strong groundwork, but **not** a mathematically complete cross-band SRC proof. Define and verify the permitted complete-chain output-sample error with the actual nonidentical reconstruction filters; do not borrow P07's isolated examples or FIR roundoff as a universal threshold.
4. Finish the still-open P15 physical performance, selected ISA, continuous soak and independent commercial-corpus gates. The operator previously stated physical Intel AVX-512 throughput cannot be obtained; explicitly carry that unqualified gate rather than invent a result or prefer AVX-512 by default. Maintain P10 certificate scope and historical evidence unchanged.
5. Only after independently reviewing signed-off receipts against design can the release coordinator decide whether P15 is qualified or blocked. No automatic default or production DSP change is authorized by this instrument.

## Interruption and provenance rules

- Per-cell JSON rows and companion SHA-256 digests are atomic; raw `.npz` and optional SRC F64 tone files are fsync-and-rename written with their checksums. No machine-specific absolute path enters their contents. An interrupted cell is recomputed; a complete row is verified and skipped only after source+binary+dependency+raw content binding matches.
- A `.sha256` sidecar is an **integrity check**, not a cryptographic signature from a trusted reviewer; tamper-resistant external release approval still needs external provenance and archiving.
- Do not ship built binaries, objects, generated autotools files, temporary result directories or a copy of the operator's attached request. Never overwrite original `tests/dsd/results` files; the one permitted existing change is the root self-excluding `tests/dsd/results/P00/P00_SHA256SUMS.txt` index, regenerated for new source/checkpoint paths.
- This checkpoint is part of the clean deliverable. If a later session must continue, start here, inspect the exact source and P00 index, replay the 17 tests and 134 P15 CLI tests, then take **one narrowly justified corrective change at a time**. Never claim physical/release acceptance from the development-only test outcomes.
