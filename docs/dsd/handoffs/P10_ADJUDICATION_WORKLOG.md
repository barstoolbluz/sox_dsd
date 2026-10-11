# P10 final certification worklog and resumption record (2026-10-11)

## Starting bytes and custody

- Incoming source archive: `sox_ng-P10adjudicate-ce14dcbe.tar.gz`.
- Incoming archive SHA-256: `e6b3a69b6f74e63a04b6e507f53be1cac3f6a4daec7503fdbc8b2b04eb79c06f`.
- Starting tree has no `.git`, is a source `git archive`, and includes complete
  existing P00-P10 source, proofs, negative certificates and raw measurements.
- Original `tests/dsd/results/` files: **all byte-identical** to the starting
  archive. Previous positive/negative historical reports and original
  `tests/dsd/reference/p10_ratification_criteria.json` were not changed.
- All new artifacts are separate; no commercial music or user-supplied
  adjudication brief was copied into the deliverable.

## Decision and evidence

**P10: CERTIFIED; close P10 and allow P11 to proceed.** The exact profile set is
`encode.mastering.v1.dsd64`, `encode.mastering.v1.dsd128`,
`encode.mastering.v1.dsd256`, with the current guarded **scalar** normal SDM
recurrence. A new explicit reviewer certificate (not a mutated old negative
profile certificate) lives at
`tests/dsd/results/P10_certification_2026-10-11/certification.json`.

The frozen ten-gate collector independently recomputes PASS, with none left.
The certificate pins 35 source/evidence/criteria paths, preserves
operator-reported provenance limitations, and binds the new 16/16 prepared-
host hotfix receipt with the 51 PCM source-to-target measurements. The cert
checker verifies it without writing or re-issuing it.

The separate `P10_ADJUDICATION.md` documents the caveats: no direct access to
private-source audio, no independent machine attestation, no commercial-corpus
state/spectral extrema, no independent proof of no interpolation overshoot, and
residual linker-layout throughput sensitivity. Each absence is accurately
scoped and **does not create a new threshold absent from the frozen criterion**.

## Changes to source continuation

- `tests/dsd/test_p10_ratification.py`: replace the outdated assertion that
  the *new* corpus gate remains PARTIAL. It now expects the returned PASS but
  still verifies that the collector alone cannot certify or promote. Add
  negative tests for missing PCM evidence and incorrect PCM level reference.
- `tests/dsd/check_p10_certification.py`: read-only verifier for the new
  independent positive certificate, gate accounting, input byte hashes,
  cross-file PCM measurements, audio reference, output integrity receipts,
  prepared-host performance and nonactivation of production profiles.
- `tests/dsd/results/P10_certification_2026-10-11/`: new certificate and
  methodology README; no old result or checksum file was replaced.
- `docs/dsd/handoffs/P10_ADJUDICATION.md`: documented verdict, scope, new
  performance authority, kernel-family finding, explicit boundaries.
- `docs/dsd/handoffs/P10.md`: append a new dated disposition while preserving
  all previous handoff claims as historical.
- `Makefile.am`: include newly introduced reviewer documents, checker and
  certificate in the distributable source manifest.
- This final worklog itself.

No production encoder, filter, guard, normalization, linker placement or
kernel implementation changed. No generated build products are included.

## Commands actually executed in a separate validation build

These commands ran on a fresh **copy** of the modified source tree, with all
build outputs/results outside the source archive. Commands/paths are written
portably here; `results` means a new temporary validation folder and is not
an instruction to overwrite retained evidence.

```
autoreconf -fi                                                   exit 0
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'  exit 0
make -j2                                                        exit 0
make check                                                      exit 0
make check-dsd DSD_PHASE=P10 DSD_RESULTS=<results>/dsd           exit 0
test/dsd_test_p10 --unit                                        exit 0, 105474 assertions
python3 tests/dsd/test_p10.py --sox src/sox_ng \
  --candidate test/sox_p10_candidate --results <results>/cli     exit 0, 63 pass
python3 tests/dsd/test_p10_corrective_qualification.py          exit 0, 16 cases
python3 tests/dsd/test_p10_ratification.py                      exit 0, 21 cases
python3 tests/dsd/test_p10_soak_receipts.py \
  --unit test/dsd_test_p10 --results <results>/soak               exit 0, 4 cases
python3 tests/dsd/test_p10_pcm.py                               exit 0, receipt/schema-only
python3 tests/dsd/generate_p10_coeffs.py --check                 exit 0
python3 tests/dsd/generate_p10_profiles.py --check              exit 0
python3 tests/dsd/qualify_p10_ratification.py \
  --output <results>/adjudication.json                            exit 0, all 10 PASS
python3 tests/dsd/check_p10_certification.py                    exit 0, PASS
```

The `test_p10_pcm.py` output says PCM_AUDIO `INCOMPLETE`: this *test harness*
uses synthetic schema setup, not the real PCM recordings; its exit 0 is a
schema-test pass, not another commercial-source qualification. The actual
real-world PCM receipts are separately checked by the gate collector and new
certificate verifier.

### Tests not repeated here

The 3600-second-per-rate actual Threadripper hardware recordings, 17 commercial
PCM files, 18 independent DSD recordings, their native bitstreams, and the
prepared-host performance measurements were **not re-run** in this review.
Their preserved results/IDs were reviewed under the agreed frozen criterion,
not misrepresented as measurements made in this environment. The full
analysis-v1 matrix and nominal 1800-second synthetic recordings were inherited
from accepted evidence; this review reran the ordinary regressions, not the
historical multi-hour jobs. P11's newly introduced ISA kernels have no
qualification under this certificate.

## Next phase / resume instructions

P10 has an explicit positive receipt; **next permitted phase: P11**, subject to
per-new-ISA-family requalification. P15 alone authorizes release/default
activation. The code's `qualified=0`, negative historical certificate inputs,
and original source and evidence hashes remain unchanged. Do not flip them
because a reviewer gate passed without following the subsequent activation
process.

On interruption, continue from the single final source archive and start with:

```
python3 tests/dsd/check_p10_certification.py
python3 tests/dsd/test_p10_ratification.py
python3 tests/dsd/qualify_p10_ratification.py --output <NEW-RESULT-PATH>
```

The last command must not point at existing historic `qualification.json`.
Check `P10_ADJUDICATION.md`, `certification.json`, this worklog and the frozen
criteria before making further changes. Keep subsequent phase evidence
versioned; preserve prior raw measurement bytes.
