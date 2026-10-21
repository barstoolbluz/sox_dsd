# P18 corrective closeout: writer refusal and DFF diagnostics

Date: 2026-10-21. This is a **corrective appendix** to `P18.md`, not a new capability authorization. All 12 DSD512/DSD1024 file/transport capability rows remain **disabled**. P17 high-rate DSP is `PASS_DEVELOPMENT_TESTS_UNQUALIFIED`, both standing P15 source obligations remain open, and there is still no independent high-rate media, external-player or physical-device qualification.

## Defects reproduced before the correction

1. Default CLI and explicit `--dsd-mode legacy` with `-r 22579200` on a DSD64 input, output to DSF, returned exit 0, warned that DSD512 was unavailable, and created an output at DSD256. Auto/native modes already refused. The cause was `set_output_format()` adjusting unsupported rates before the DSF/DSDIFF writer startup saw the requested rate. This violated the P18 contract prohibiting silent down-rating, including when accompanied by a warning.
2. Auto-mode preflight for `.DFF` and `-t DFF` returned a correct denial with an incorrect **DSF** container label. The cause was case-sensitive matching in `src/dsd_plan.c`, not in generic format selection.

## Smallest coherent correction

- `src/formats.c`: after `sox_write_handler()` resolves the actual DSF or DFF destination and before allocating an output file, validate the **original** explicitly supplied DSD512 or DSD1024 rate. Use `lsx_dsd_integer_rate()`, `lsx_dsd_capability_check()`, `lsx_dsd_capability_description()` and the resolved handler identity. Return a format/operation-specific failure if unqualified. This covers default and legacy CLI and direct `sox_open_write()`/`sox_open_write_dsd()`/memory writer callers. Generic PCM format negotiation, writer rate allow-lists and DSP/audio hot paths are unchanged.
- `src/dsd_plan.c`: use `lsx_strcasecmp()` for DFF type and `.dff` filename suffix only; do **not** alter generic `is()` semantic effect matching.
- `tests/dsd/test_p18.c`: test direct `sox_open_write()` at each high-rate/DSF-DFF combination and prove the preexisting output sentinel is never truncated; core suite now exercises 398 checks (previously 372).
- `tests/dsd/test_p18.py`: eight default/legacy high-rate DSF/DFF refusals, four uppercase `.DFF`/`-t DFF` refusal diagnostics, and six positive writer round trips spanning DSD64/128/256 and DSF/DFF, in addition to the prior 88 tests. The result is 106 CLI cases, each retaining command, exit, stderr, explicit expectation, and output-file absence or verified lower-rate chronology.
- `tests/dsd/seal_p18_manifest.py`: includes `src/formats.c` in the P18 source SHA-256 inventory and requires 106/106 passing CLI checks. Release notes and compatibility ledger describe enforcement at the pre-open boundary. No fixture or historical acceptance threshold was changed.

## Executable correction evidence

The corrective replay was launched from synthetic Git source commit `ad8d9f7` after `make clean`, `autoreconf -fi`, reconfigure, and `make -j2`. Commands, process exit codes and stdout/stderr are preserved under `tests/dsd/results/P18/build/` (see `corrective-gates.status`); the real SoX and P18 native binary were built from the changed source. Existing source-archive mtimes were not trusted. The Python P18 and P16 CLI receipts were explicitly removed after retaining dated snapshots in `build/` so the replay would exercise all cases from scratch.

Recorded gates (status is per saved `.exit` and raw evidence):

- `make clean`, `autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`, `make -j2`: **all exit 0**, built from source in the corrected tree. Evidence `corrective-make-clean`, `corrective-autoreconf`, `corrective-configure` and `corrective-make`.
- `test/dsd_test_p18`: **exit 0; 398 native C checks PASS**, including four direct-public-API writer denials and no truncation of existing sentinel bytes. Evidence `unit-p18.exit`/`.log`.
- `python3 tests/dsd/test_p18.py --fixtures-only`: **exit 0; 198** independent structural format cases, **36** DoP reference records, unchanged frozen 40 byte vectors. Evidence `corrective-fixtures.exit`/`.log` and `reference/p18_fixture_matrix.json`.
- `python3 tests/dsd/test_p18.py --sox src/sox --results tests/dsd/results/P18/integration`: **exit 0; 106/106 PASS**, source/fixture/binary-bound JSON receipt `integration/capability-integration.json`. Output-denial cases have no output files; positive lower-rate writer cases compare exact rate, channel count and chronological DSD bits.
- `make check`: **exit 0**, inherited generic SoX regression. Evidence `make-check.exit`/`.log`.
- `python3 tests/dsd/test_p16.py --sox src/sox --unit test/dsd_test_p16 --results tests/dsd/results/P18/integration`, twice: **both exit 0; 219/219 PASS**, once after removing the previous receipt (full fresh CLI replay), then fully cached (idempotency replay). Evidence `p16-fresh-qualified` and `p16-cached-qualified`, `integration/packed-cli.json`.
- `make check-dsd DSD_PHASE=P18`: **exit 0; 45/45 PASS**, inherited P00-P17 and P18. Evidence `check-dsd-qualified.exit`/`.log`, `run.json`.
- `python3 tests/dsd/run.py --phase P18 --results tests/dsd/results/P18`: **exit 0; 45/45 PASS**. Evidence `run-p18-qualified.exit`/`.log`.
- `python3 tests/dsd/measure.py --phase P18 --results tests/dsd/results/P18/numeric`: **exit 0; 11/11 development checks PASS**, still `P18 FAIL_CLOSED` and no P17 high-rate certification. Evidence `measure-p18-qualified.exit`/`.log`, `numeric/measure.json`.
- `python3 tests/dsd/bench.py --phase P18 --results tests/dsd/results/P18/bench`: **exit 0; 36/36 inherited low-rate cases**, classification `pass-development-only` (not an end-to-end DSD512/1024 result). Evidence `bench-p18-qualified.exit`/`.log`, `bench/bench.json`.
- `make check-rename`: **exit 0**, evidence `check-rename-qualified.exit`/`.log`.
- `python3 tests/dsd/seal_p18_manifest.py --seal` followed by `--check`: **both exit 0**; `P18_COMPLETE_FAIL_CLOSED`, **15 PASS** implementation/evidence gate entries, **12 disabled** capability rows, no device claims. `source_sha256` includes `src/formats.c` and the corrected P18 test harness.

**All corrective gates completed with exit code 0** in `tests/dsd/results/P18/build/corrective-gates.status` (2026-10-21 18:53:21Z to 18:57:59Z). Previous P18 receipt timestamps remain historical; the corrected receipts above are authoritative for this source.


The P18 fixture matrix remains 198 deterministic high-rate format examples, 36 DoP reference records and 40 checked-in byte vectors; these are *synthetic format/transport checks*, not independent interoperability. Numerical and benchmark observations apply only to existing qualified lower rates or development-only P17 candidates. No physical high-rate file or DoP transport was exercised because enablement remains withheld.

## Corrective integration and limitations

This appendix preserves the previous P18 receipts and records the correction in new `corrective-*` build logs and refreshed canonical qualified gate receipts. The corrected `P18_RELEASE_MANIFEST.json` is resealed from the changed source and current evidence; `--check` must reproduce the same 12 disabled rows with `P18_COMPLETE_FAIL_CLOSED`. Do not interpret implementation PASS as a P17 production DSP certificate or permission for any writer/transport enablement.

The original working-set archive omitted Git metadata. Local Git commits (`69678ff` synthetic baseline, `66155d1` P18, `ad8d9f7` corrective source) are reproducible archive history, **not** fast-forward commits on upstream `sox_dsd/main` at claimed `51c391f2`. Integrate by comparing/applying the source patch against the accepted P18 tree, not by assuming a shared repository ancestry.
