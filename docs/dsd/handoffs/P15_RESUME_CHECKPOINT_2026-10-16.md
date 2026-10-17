# P15 adjudication continuation checkpoint — 2026-10-16

1. **Authority**: `docs/dsd/DSD_DESIGN.md` and
   `docs/dsd/amendments/P15_SRC_ACCEPTANCE_METHOD_2026-10-15.md`, with the
   prior dated Intel scope amendment. Original incoming tarball SHA:
   `e119c315d192cb44f8abb1bf3ae61f4e30a4cef9394e5a7f089ebdecd24b5cde`.
   Commit claimed by operator `ab7f0f56`. Archive has no Git metadata.
2. **Decision**: v2 OFF, P15 release BLOCKED, P16 not authorized. DSD256
   2x timings passed as scoped measurements but 66-kHz upper-passband control
   diverges by ~6 dB, so composite DSD256 gate OPEN. Intel now measured in a
   new ledger; historical UNRUN label preserved. Only an AVX-512 block-FIR
   microbenchmark accelerates materially, not the end-to-end graph.
3. **SRC**: 72 active cells, 24 distinct ratio pairs. 75-digit interval
   Taylor checker and private SRC phase-capture tool + one complete 147-phase
   observation are supplied. Both deliberately distinguish witness math from
   independent source-bound acceptance. Arithmetic R5 checker and four
   dependency source modules unavailable. Full continuous composite
   certificate remains OPEN, NOT computed or claimed.
4. **Raw data**: input archive omitted precisely 946 `.npz` files, whose
   original content hashes remain in P00 index. State and graph-raw evidence
   present. Do not synthesize replacements.
5. **Engineering changes**: adjudication Python only; no production C,
   normative design, or frozen measurement JSON rewrite. Changed historic
   5 source/test Python files and added instrument/review/test/docs/one
   observation pair; only regenerated P00 index additionally modified.
   See `P15_ADJUDICATION_2026-10-16.md` for commands.
6. **Known inherited failure**: legacy `test_p15_closeout_review.py` pins an
   obsolete `src/dsd_decode.c` digest (2 fail + 1 error at input, unchanged).
   Keep this distinct from source-current `p15_current_closeout.py`.
7. **Next engineering task**: retrieve and independently verify actual R5
   arithmetic checker source; derive the complete exact private SRC
   polyphase/FFT4G operators and bounds; join to native FIR; enumerate all
   coherent aliases; certify extrema via intervals; replay all 72 cells
   with SHA-matched original raw payloads. Do not relax the spec or change
   release status to conceal incomplete work.

**Resumption rule**: first verify archive SHA-256 and P00 inventory; run
focused tests. Make only source-audited corrections, regenerate the P00
transport hash index *without accepting changes to immutable measured
files*, and add new receipts, never rewrite dated historical ones.
