# P15-R3 decoder reconstruction policy — R2-anchored corrective handoff

**2026-10-15. Implementation disposition: ACCEPTED AS AN UNQUALIFIED V2 DECODER CANDIDATE. P15 FIRST RELEASE: BLOCKED. P16: NOT AUTHORIZED.**

This corrects the *baseline ancestry* defect in the original October 14 R3 candidate. The 25/48/66-kHz decoder-only v2 changes have been applied to the **verified P15 R2 adjudicated source tree**, not to its pre-R2 predecessor. The existing FIR implementation was not redesigned; the R2 gate decisions and all prior archived evidence remain in place.

## Verified custody and source history

| Input | SHA-256 | Checked fact |
| --- | --- | --- |
| `sox_ng-P15-R2-readjudicated-source-2026-10-14.tar.gz` (six transport parts joined) | `5662a845e3a21a38ec9219b91d5c33a8d5964ee5407099a82538ebd2657f0dd7` | Authenticated R2 starting point, 7,809/7,809 P00 entries PASS |
| `sox_ng_P15_R3_reconstruction_policy_candidate_2026-10-14.tar.gz` | `b451ecc83b59ee9a516b598fe38d34dc4d5f2fda30b1bd16332d387537c16f77` | R3 candidate decoder-only modifications imported selectively, not overlaid wholesale |

Of 7,810 original R2 regular files, **none was deleted**. Exactly **15** existing paths changed: the 12 intended implementation/build/test files (`Makefile.am`, `src/Makefile.am`, nine `src/dsd*.c/.h` and selection/report files itemized below, and `tests/dsd/test_p15_instrument.c`) plus three up-to-date policy/docs files. The R3-only coefficient header, generator, independent certifier, profile manifest, regression scripts, earlier candidate receipts, and new reconciled receipts were added. The full auditable path/digest inventory is in `tests/dsd/results/P15_R3_R2_reconciliation_2026-10-15/reconciliation.json`.

**Preservation proven byte-for-byte:** 6,847 original R2 result files outside the self-excluding P00 inventory; 61 prior handoff files; 26 reference/legacy coefficient files; all seven R3 candidate raw result JSON files; and the exact original text of `docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md`. The R2-only 2,252 source/evidence files omitted by the older R3 candidate are retained, including the five-session matrix raw arrays, the 915 1-hour encoder continuation snapshots, the 15 soak execution receipts, the R2 source-bound reviewers, and the Intel amendment. No historical JSON/array/soak result was overwritten. `DSD_DESIGN.md` retains its operative §10.7 Intel exception verbatim, along with the additive R3 decoder policy; `QUALIFICATION.md` retains its R2 lead-in and explicit release block.

### Exact modified existing paths

```text
Makefile.am
src/Makefile.am
src/dsd.c
src/dsd.h
src/dsd_decode.c
src/dsd_plan.c
src/dsd_public.c
src/dsd_stats.c
src/dsdpcm.c
src/sox_dsd.h
src/sox_ng.c
tests/dsd/test_p15_instrument.c
docs/dsd/DSD_DESIGN.md
docs/dsd/QUALIFICATION.md
docs/dsd/MIGRATION_P15.md
```

The **only** change to existing historical data is regeneration of `tests/dsd/results/P00/P00_SHA256SUMS.txt` for the newly delivered tree. Source archive SHA-256 is external shipping metadata, not a self-referential in-tree hash.

## New product semantics: qualified-release proposal, not active migration

| Native stream | `conservative` / `decode.mastering.v1.*` (retained) | Explicit candidate `decode.mastering.v2.*` | Stopband v2 | Implicit PCM output | Last-stage v2 taps | SHA-256, C99 binary64 words |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DSD64 | 20 kHz | **25 kHz** | 40 kHz | 88.2 kHz | 153 | `1cf7807a6be4651bfd264873dd09075f7f532b22ab3b9638223857f4af09107b` |
| DSD128 | 30 kHz | **48 kHz** | 60 kHz | 176.4 kHz | 377 | `8f84430b2f0113d4b2055073833b8ab9acba2cd145b300f0f75b7cccc0faaf1b` |
| DSD256 | 40 kHz | **66 kHz** | 80 kHz | 176.4 kHz | 325 | `2b908ebaa0cacc23965d63e46b3838d7eff4149dee5dd01e2d8f12996ee20231` |

The v1 wideband options remain unchanged (DSD64/128/256 guaranteed passbands 35.28/70.56/141.12 kHz). Original v1 and v2 canonical IDs select distinct immutable banks. `legacy` remains the pre-existing unrelated algorithm. Explicit DSD256 352.8 kHz PCM and supported lower output rates remain available, with existing `adapt` / `strict` Nyquist policy and **without** rate-triggered bank switching. The encoder's `encode.mastering.v1.*` filters, SDM kernel selection, native DSD transport, and input-reference/gain semantics are unchanged.

**While first-release qualification remains blocked, the generic `mastering` alias and automatic decoder default intentionally still use v1.** V2 is explicitly selectable by its exact native-rate-pinned canonical ID to permit independent qualification. Reports identify the resolved bank, coefficient hash, effective bandwidth and v2 candidate status; no v2 bank is mislabeled v1 or reported as qualified. The desired future `mastering` alias migration is not performed here.

## Independently reproduced validation on the *merged* tree

The build and tests ran in a disposable copy; all newly shipped test receipts are under `tests/dsd/results/P15_R3_R2_reconciliation_2026-10-15/`, distinct from historical R2 and earlier candidate R3 results. Recorded result JSON contains no environment-local absolute paths.

| Test or command | Observed exit/status | Boundaries |
| --- | --- | --- |
| R2 original P00 inventory (`sha256sum -c`) | **0 PASS**, 7,809 files | Verified *before* modifications |
| `autoreconf -fi`; `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'` | **0 PASS** each | Disposable source copy |
| `make -j4` | **0 PASS** | Resumed after initial `make -j2` was interrupted by command window while linking; same build, no code correction |
| `make check` | **0 PASS** | Full generic suite, with its ordinary optional `VOID` tests |
| `make check-dsd` | **0 PASS** | Full inherited DSD phase P15 suite on merged source |
| `make check-dsd-p15-r3` | **0 PASS** | Generator idempotence, 3 FIR banks and 3 decimation cascades, 36 numerical/ISA cases, 76 actual CLI/rate/chunking/integration cases, 4 sampled production-SRC ratios (38 checks) |
| `python3 tests/dsd/test_p15.py --sox src/sox_ng --results <scratch>` | **0 PASS, 134/134** | Original P15 CLI regression replayed on merged executable |
| P15-R3 generator `--check` twice | **0 PASS** | Same C99 header and manifest bytes |
| R2 matrix reviewer on original R2 5 sessions with `--require-coverage` | **0 PASS** | 54 scalar cells, 216 non-scalar jobs, 96 detailed comparisons; **not** a numerical release certificate |
| R2 original `test_p15_readjudication.py` | **0 PASS, 7/7** | Same source/evidence reviewer; mutation/idempotence cases |
| R2 original `test_p15_closeout_review.py` | **0 PASS, 4/4** | Replayed on verified original R2 source, which matches measured source identities |
| R2 `p15_readjudication.py --output <scratch> --require-release` on unchanged R2 baseline | **2 EXPECTED BLOCKED** | Independently reproduced **byte-identical** `review.json`, SHA-256 `5217c16f64b93ecb5a8d6584c55846a68313e40f22636dad093da1fa8ba559ed` |

**Historical source-binding is intentional:** the two historical R2/closeout reviewers compare matrix evidence against the actual *current* source-file hashes. When run directly against the newer merged R3 source, those source comparisons refuse with `source/reference hash mismatch` (exit 1), and the older closeout unit tests fail for that reason. They **must** be replayed against the verified R2 snapshot, as above; do not modify their hashes, overwrite archived receipts, or weaken this negative test merely to make a changed revision appear identical. Current R3 qualification is assessed through the new merged-tree tests and receipts. This is not an R3 regression or a claim that historical R2 evidence was obtained with R3 source bytes.

New FIR response extrema are reproduced from compiled binary64 words. Bank/cascade certifier reports 3/3 passes against original §6.1 flatness and decimation alias bounds, not an independent full production FIR+fractional-SRC acceptance proof. V2 numerical/ISA 36/36, conversion and bank-ID integration 76/76, sampled SRC 4/4 all pass with source-bound new receipt content. The new binary's SHA-256 and source-file digests are recorded in `reconciliation.json`. No new performance advantage is claimed from the exploratory unmatched v1/v2 timing receipt retained from the earlier candidate.

## Exact scope of remaining gates

| Requirement | Status | Minimum remaining work |
| --- | --- | --- |
| V2 decoder implementation, correct versioned identity and decimation FIR response | **PASS-SCOPED**, candidate unqualified | No code rewrite justified by the audited evidence |
| Full effective v2 FIR + *production* fractional SRC spectral/coherent alias extrema and predeclared like-for-like numerical arithmetic | **OPEN** | Independently certify the actual full production operator at required output rates; don't borrow a different-filter SRC's per-sample tolerance |
| Complete 3 × 9 = 27 actual v2 numerical/ISA release matrix with vector-bounded evidence | **OPEN** | Extend source-bound raw numerical measurements beyond the 27 successful functional conversion smoke tests |
| Six-channel DSD256 v2 66/80-kHz physical ≥2× performance gate | **OPEN / UNRUN** | Independently certify one **bandwidth-matched** staged legacy transfer and perform 15 controlled repetitions per comparator arm at 176.4 and 352.8 kHz with CI and source/fixture bindings; do not recycle `sinc -20000` |
| Original R2 full composite SRC numerical gate | **OPEN** | Retained R2 adjudication, its arrays and reviewer remain authoritative for v1 history |
| Original R2 DSD256 40/80-kHz matched-performance gate | **OPEN** | Retained R2 direct-speedup observations are not a valid matched-bandwidth control |
| Physical Intel AVX-512 performance | **UNRUN-SCOPE-EXEMPT** | Only for §10.7 conservative dispatch/no Intel-specific preference/claim; never mark as physically passed |
| Physical older AVX1, encoder one-hour soaks, independent software corpus | **PASS-SCOPED (R2)** | Prior source-bound results retained; no encoder re-soak or upstream refactor ordered by decoder-only policy |

**Release_status: BLOCKED.** This artifact permits continued targeted P15/R3 numerical/performance qualification and independent review, **not** first-release activation, a v2/encoder-v2 default change, a new CPU preference, a hardware compatibility claim, or P16. No existing first-release gate is silently marked PASS by this integration.

## Resume and delivery procedure

1. Verify the separate archive SHA-256 and run `sha256sum -c tests/dsd/results/P00/P00_SHA256SUMS.txt` from the extracted source root. The updated inventory is intentionally self-excluding.
2. Read `DSD_DESIGN.md` §6.1, §7.1, §10.4 and §10.7, `QUALIFICATION.md`, the retained `P15_READJUDICATION_2026-10-14.md`, this handoff, and `P15_R3_RECONSTRUCTION_POLICY_CHECKPOINT.md`.
3. Build a disposable source copy using the commands above. Run `make check`, `make check-dsd`, `make check-dsd-p15-r3` and the generator's `--check` if needed; write all new results to a **new** results namespace, not historical folders.
4. Review `tests/dsd/results/P15_R3_R2_reconciliation_2026-10-15/reconciliation.json`, its four current-run numerical/integration JSONs, and the original R2 review from its source-pinned snapshot. Do not reattribute old R2 or candidate-R3 measurements to a different source revision.
5. Complete only the independent full SRC/v2 numerical and valid physical matched DSD256 gates. Preserve P00/checkpoint provenance and obtain a separate release adjudication **before** changing `mastering` or enabling P16.

The definitive in-tree checkpoint persists the work and the precise restart path. The downloadable **full source-only archive** is accompanied externally by its SHA-256, a tested R2-to-R3 delta, and optional checksummed transport parts; no build outputs or copies of the implementation prompt are inside the source archive.
