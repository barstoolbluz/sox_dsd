# P15 question adjudication: resumable checkpoint

Date: 2026-10-13. Input: `sox_ng-P15-questions-1a2d9992.tar.gz`, SHA-256 `7b4b75ab7320e9469221880f80f3d93eacb83931c2b089100bbf37ada10b7bb3`.

Status: QUESTION ADJUDICATION DELIVERED; P15 release remains BLOCKED. The source tree is a git archive of `1a2d9992` without `.git`. Initial P00 checksum inventory verified clean (4,800 entries). Governing references: DSD_DESIGN §§6,8.6,10.2,10.4,10.6 and P15 SOW.

Intent: clarify the two actual questions, implement deterministic **planning and evidence-review tools** (not counterfeit spectral measurements), capture a blocked physical AVX1 receipt review, keep compiled DSP sources/policy intact. No hardware or external signal corpus attached.

Verified finding: `tests/dsd/results/P15_avx1_physical_2026-10-13/host.txt` identifies `AMD Ryzen Threadripper 7970X`, `avx / avx2 yes / yes` despite README claiming an older physical AVX1-only CPU. This shipped subdirectory has no kernel timing or clock raw receipts. Disposition is not certified.

No new P15 metrology values or cross-host scalar root cause have been measured in this session. The frozen analysis-v1 FIR is encoder-focused, 20 kHz / 24 kHz and 88.2 kHz output; it cannot prove wideband decoder response at 705.6 kHz.

Resume: read this checkpoint, docs/dsd/P15_QUESTIONS_ADJUDICATION_2026-10-13.md, run `python3 -m unittest tests/dsd/test_p15_question_resolution.py` and tool commands in that document. Do not alter P10 historical certificate, P09 frozen analysis, or release automatic defaults. Archive checksum inventory only after finalization.

## Current execution record and final disposition

* Input checksum inventory: PASS, 4800/4800 original entries.
* `autoreconf -fi`: exit 0. `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`: exit 0.
* `make -j2`: **INTERRUPTED by 200-second tool timeout** while linking `libsox_ng.la`; not a compiler failure. Incremental `make -j4`: exit 0.
* `make check`: exit 0, generic suite passed; optional format VOID cases remain as normally reported.
* `python3 tests/dsd/test_p15.py --sox src/sox_ng --results <session-results>`: exit 0, 134 PASS / 0 FAIL.
* `python3 -m unittest tests/dsd/test_p15_question_resolution.py -v`: exit 0, 9 PASS / 0 FAIL.
* `bash -n tests/dsd/check_avx1_physical.sh` and `python3 -m py_compile` on the new Python tools: exit 0.
* Full `make check-dsd` (with results redirected outside the tree): **INCOMPLETE**, killed by 180-second environment timeout while linking `dsd_test_p12_bounds`. The completed earlier P00-P11/P12 stages shown in `verification/make-check-dsd.log` did not report failures; no completed full-suite exit 0 is claimed.
* `python3 tests/dsd/check_p15_avx1_receipt.py` against the attached claimed older-AVX evidence: exit 2 as designed, `BLOCKED` with seven explicit provenance/raw-evidence problems.
* `python3 tests/dsd/p15_release_manifest.py --require-qualified`: exit 2 as designed, `BLOCKED`, original six mandatory gaps open, no unexpected P10 source-lineage deviation.

All verification logs in `tests/dsd/results/P15_questions_2026-10-13/verification/` are *current-session* results. Historic P10 certificates and P00-P15 accepted evidence files remain unedited in the delivery. This work did not run the independent 54-cell spectral measurement, change the compiler/decoder/SDM code, or collect unavailable physical silicon/corpus tests.

The next permitted task remains P15 release qualification; the 54-cell worklist is a concrete executable schedule, **not** completed spectral test data. To resume, run the independent integer and rational combined-chain oracles with per-cell calibrated spectra, phase/count/alias and cross-ISA receipts; separately supply authentic physical hardware evidence. Do not turn smoke/plan output into a release pass.
