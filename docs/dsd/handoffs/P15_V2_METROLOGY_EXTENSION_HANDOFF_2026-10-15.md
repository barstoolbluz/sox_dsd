# P15 mastering-v2 independent metrology extension — source handoff

**Date:** 2026-10-15. **Input:** `093b0eaf` archive, verified SHA-256
`68dfde0b7e7548e2b89eee550e619a4a9c640b71f5b6c784bb6ce786c0943d3a`.
**Authority:** `docs/dsd/DSD_DESIGN.md`, particularly the v2 profile policy and
section 10.4. No production default or code is changed.

## Engineering decision

Extend the v1 instrument; do not waive v2 end-to-end qualification on the
basis of an independent native-FIR certificate plus v1 observations. The C
probe already accepts `mastering_v2`, but the former Python instrument and
worklist could not exercise it; they also lacked an independent v2
finite-FIR reference and pinned graph selection. Only a 27-cell mastering-v2
extension is required: DSD64/128/256 x the same nine PCM destinations.
There is no version-two wideband profile. The existing v1 54-cell worklist
is left semantically identical (its committed worklist JSON agrees exactly).

## Implementation scope

- `p15_matrix_contract.py`: separate `--matrix v2` 27-cell worklist and
  135 total tier-functional jobs / 48 detailed ISA jobs; v1 default unchanged.
- `p15_numerical_reference.py`: independent exact-C99-hex v2 bank import,
  cross-check against the existing v2 manifest, shared checked P06 halfband,
  full 75-digit finite FIR composition, high-precision witnesses and separate
  rational polyphase SRC; no use of the production reconstruction engine.
- `p15_matrix_instrument.py`: v2 probe receipt grammar and profile, checked
  FIR certificate binding, separate versioned session/cell schema, correct
  native policy and passband, provenance pins, resumption, and 27-cell
  completeness guard. The v1 schema and legacy summary keys are preserved.
- `p15_graph_integration.py`: route the graph through explicit
  `decode.mastering.v2.dsd*` IDs (not a non-existent `decode.mastering_v2.v1`
  profile). v1 versioned IDs are unchanged.
- `p15_matrix_receipt_review.py`: separate v2 lineage check, raw replay and
  27/108/48 observed-coverage counts; cannot combine v1 and v2 session claims.
- `test_p15_v2_matrix.py`: regressions for plan counts, unchanged v1 worklist,
  v2 production bank corruption, certificate, exact finite convolution,
  versioned route, real C probe, and reviewer selection/integrity.
- `P15_MATRIX_INSTRUMENT.md`: commands and gate semantics for the new axis.

## Verification completed in the implementation environment

- Original input archive SHA-256: **PASS**.
- Clean autotools configure/build (`--disable-shared --without-libltdl`):
  **PASS**, including `dsd_test_p15_instrument` and `dsd_test_p07_reference`.
- Existing P15 instrument tests against the built test binaries: **22/22 PASS**.
- Additive v2 focused tests against the built exporter: **8/8 PASS**.
- Full test-only output-path smoke runs using actual C exporter, private SRC
  exporter, and SoX CLI: DSD64 -> 88.2 kHz, DSD128 -> 48 kHz, DSD256 ->
  176.4 kHz, DSD256 -> 705.6 kHz: **4/4 development cases PASS**.
  A DSD64 short-run also included SHA-bound raw SRC/graph captures,
  read-only receipt review and a second invocation with `--resume`, which
  reused the existing cell without recomputation.
- **One full-duration 262,144-frame** DSD128-v2 -> 48-kHz cell with
  131,072-frame private SRC observation, forced SSE2 comparison, retained
  binary64 numerical arrays, raw SRC tones and the six-channel public SoX
  graph recordings: **PASS**. The read-only v2 receipt reviewer replayed the
  raw data and reported 1/27 scalar, 1/108 forced-ISA and 1/48 detailed-ISA
  full-duration observations; the remaining obligations stay OPEN. A second
  identical `--resume` invocation preserved the raw arrays and cell JSON
  checksums byte-identically.
- Existing P06 and independent P15-R3 native FIR certificates: **verified**.
- Previously committed P15 evidence under `tests/dsd/results`: **unchanged**;
  the only file under results that must change is P00's file-hash inventory.

A broader discovery of legacy `test_p15*.py` on this deliberately stripped
R3 source snapshot also exercises historical closeout and soak evidence.
It reports **2 failures and 3 errors** unrelated to the new v2 extension:
the old closeout comparison expects a prior `src/dsd_decode.c` digest and
the soak checks require `.state` payloads explicitly absent from the
input archive. None of those historical source files or evidence was
modified here. Do not reclassify these as v2 instrument regressions or
rewrite historical receipts merely to make a stripped-tree suite green.

The short 8,192-native-frame probes are development checks, **not** full
262,144-frame acceptance and not samples of all 27 rows. No physical host
acceptance, all-tier complete coverage or qualified numerical SRC error
bound has been claimed. Full-duration v2 metrology must be executed by the
operator as documented above.

## Next host / interrupted-session procedure

1. Extract the source-only archive; verify its externally supplied SHA-256
   and P00 inventory (retained inventory entries for deliberately omitted
   numerical payloads must not be mistaken for missing newly authored files).
2. Build the ordinary project and the existing C probes. Run the v1
   regression suite plus `test_p15_v2_matrix.py` with `P15_LIVE=1` and the
   built test binary locations.
3. Run the **v2** full 27-cell matrix in a *new*, never-used results directory
   using the command in `docs/dsd/P15_MATRIX_INSTRUMENT.md`, including
   `--capture-src-raw --capture-graph-raw --require-all-observations`. Repeat
   with `--resume` on interruption; do not override source/version pins.
4. Run the v2 reviewer with `--require-coverage`; retain all unverified
   or unsupported tiers as unobserved, and archive full raw receipts.
5. Keep v1 R3 matrix sessions under their original source lineage. Their
   recorded bytes and hashes are retained, but their bulk `.npz`/graph files
   were already excluded from the supplied archive. Retrieve these original
   payloads from the commit if historical cross-host replay is necessary.
6. Do not promote the v2 default until independently justified combined
   SRC numeric/spectral acceptance, physical/performance/corpus gates and
   a release adjudication are complete. This work adds measurements, not
   new DSP tolerances, a waiver or a release certification.

## Source preservation and exclusions

The deliverable is a complete **source** snapshot, not a built tree and not a
new commit. It retains every original file present in the supplied archive;
contains no `.git`, autoconf products, compiled objects, test binaries or the
supplied request note; and keeps the previously excluded historical
`*/arrays/*.npz`, `*/graph-raw/*`, and `*.state` payloads excluded.
The P00 inventory is regenerated from actual bytes for included files,
retaining original hash entries for the prior excluded historical payloads.
This preserves their evidence identity without falsely asserting that the
bulk payloads are inside this source-only transport.
