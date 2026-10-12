# P14 continuation checkpoint: final tested source (2026-10-12)

**Authority:** `docs/dsd/sows/P14.md`, `docs/dsd/DSD_DESIGN.md` sections 9 and 10.2, and `docs/dsd/handoffs/P14.md` (full disposition). Original SHA-256 `7b745ebaeb50dce8b2bb16b9aed81b89643fc37c06422111915fb32aafe2c6e7`, archive `sox_ng-P14-dispatch-d940cc93-2026-10-12.tar.gz`; input is a source-only `git archive` without `.git`. The current date is October 12, 2026, not the October 11 date in the covering instruction.

## Source state and interruption-safe handoff

- Authoritative unbuilt source tree was edited independently of the test/build tree. No `.git` or generated build binaries have been added to the deliverable.
- New source modules: `src/dsd_stats.{c,h}`, `src/dsdstat.c`; new independent tests `tests/dsd/test_p14.{c,py}`, `tests/dsd/test_p14_numeric.py`, `tests/dsd/bench_p14.py`, `tests/dsd/reference/p14_report_{schema_v1,golden}.json`; supporting changes to the frontend, profile/report getters, make inputs, inherited runner scripts and manpages. See `docs/dsd/handoffs/P14.md` for complete changed-file and contract details.
- Functional coverage: versioned CLI JSON; actual decode/encoder provenance and SDM monitors; original native-bit 28-window stats; native effect unmodified bytes; optional fifth-order SOS analysis; failed/clipped/cancelled status; report/audio output stream separation (including stdout aliases); unknown/null and lossless counters.
- P13 physical-silicon performance **OPEN**, default FIR SSE2 and normal SDM scalar, neither FMA variant installed. Intel coverage means 10 matching **80-bit hash prefixes** on the specified stimulus, not general whole-hash equality. No P15 promotion authorized.
- Input P00 checksum manifest **4032** records, all verified. Deliverable inventory must be regenerated and validated **after** all P14 docs and results have been copied. Do not modify the final source after regenerating without regenerating again.

## Executed build and tests

`autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`, `make -j2`, `make check`, inherited `make check-dsd DSD_PHASE=P14`, standalone `run.py --phase P14` (36/36), `measure.py --phase P14` (10/10), `bench.py --phase P14` (36/36) and separately repeated P14 observer overhead tests all exited **0** on virtualized AMD EPYC 9V74/GCC 14.2 Linux x86_64. P14 integration **12/12** and independent numerical **3/3** passed in final `make check-dsd`. Build commands and sanitized logs are in `tests/dsd/results/P14/build` and raw evidence is in adjacent runner/run/numeric/bench directories. No P10 real-world material, physical clocked performance or certification is claimed.

**Resume/verify:** (1) extract the delivered archive; (2) run `sha256sum -c tests/dsd/results/P00/P00_SHA256SUMS.txt` within its `sox_ng` directory; (3) verify no `.git`, `*.o`, `.libs` or configure-generated `Makefile` files are present; (4) inspect `docs/dsd/handoffs/P14.md` and qualified result files; (5) run `autoreconf -fi` before configure in a separate build copy. Preserve P00-P13 historical evidence byte-identically except the mandated regenerated P00 manifest.
