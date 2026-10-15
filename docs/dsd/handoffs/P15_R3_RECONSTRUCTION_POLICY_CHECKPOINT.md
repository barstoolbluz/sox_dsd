# P15-R3 R2-anchored reconstruction policy — resume checkpoint (2026-10-15)

## Verified inputs
- Source authority: R2 `sox_ng-P15-R2-readjudicated-source-2026-10-14.tar.gz` SHA-256 `5662a845e3a21a38ec9219b91d5c33a8d5964ee5407099a82538ebd2657f0dd7`, verified from six transport parts. Original P00 7,809-entry inventory verified: PASS.
- Candidate decoder addition: `sox_ng_P15_R3_reconstruction_policy_candidate_2026-10-14.tar.gz` SHA-256 `b451ecc83b59ee9a516b598fe38d34dc4d5f2fda30b1bd16332d387537c16f77`.
- R3 candidate was descended from an older pre-R2 closeout tree; this integration deliberately begins with the authentic R2 tree.

## Integration checkpoint 1
- Port 12 R3 modified source/build/test files, R3-appended migration guidance, and 17 R3-only coefficient, test, manifest, receipt and handoff files.
- Merge only R3 decoder sections into R2's design authority; leave R2 Intel AVX-512 scoped amendment exactly intact.
- Merge v2 candidate note into R2 QUALIFICATION lead-in, retaining R2 BLOCKED disposition.
- Leave both R2's evidence (matrix arrays, 915 encoder-soak states, earlier source-bound adjudication and unaltered reports) and the candidate's R3 numerical/functional results unchanged.
- Pending: independently verify historical preservation, disposable build and tests, R2 adjudication, generation/idempotence, final handoff and P00 manifest regenerated last.

## Restart
Start from the source root. Inspect `docs/dsd/handoffs/P15_R3_RECONSTRUCTION_POLICY_HANDOFF.md` and `DSD_DESIGN.md`, verify the P00 manifest, and run `make check-dsd-p15-r3` on a disposable configured build. R2 `tests/dsd/p15_readjudication.py --output <new receipt path> --require-release` must still exit 2 while release remains BLOCKED. Full composite SRC numerical acceptance, 27-cell independent v2 numerical release matrix, and 66/80 kHz matched physical DSD256 2x test remain OPEN. Do NOT qualify/promote v2 or authorize P16.

## Integration checkpoint 2 — complete independent verification, 2026-10-15

- R2 original source archive + self-excluding 7,809-file inventory: PASS. 6,847 original historical result files and 61 handoffs preserved byte-for-byte; no R2 file missing. All seven candidate-R3 numeric/functional result files retained byte-for-byte. Original Intel scope amendment identical and present in normative authority §10.7.
- Decoder v2 candidate source is confined to exactly 15 modified R2 paths plus additive R3/reconciliation files. Generator `--check` run twice: PASS, same coefficients/manifest. Filter-cascade certifier: 3 banks and 3 profiles PASS at grid 8,192; 36/36 finite/ISA, 76/76 integration, and 4/4 sampled SRC ratio holdouts PASS.
- Disposable build: `autoreconf -fi` exit 0, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'` exit 0. Initial `make -j2` was interrupted in linked-library phase by the command window; resumed `make -j4` exits 0. `make check` exit 0; `make check-dsd` exit 0; `make check-dsd-p15-r3` exit 0; original P15 CLI 134/134 PASS.
- Original R2 adjudication reviewed against the verified R2 source: exact archived result hash reproduced, expected exit 2 (BLOCKED). Seven R2 readjudication unit tests PASS and four earlier closeout unit tests PASS on their original measured source. Five-session R2 matrix coverage rerun exit 0 (not release certificate). Historical reviewers deliberately reject on newly changed R3 source hashes: do NOT replace old evidence hashes to force a pass.
- Reconciled-run receipts: `tests/dsd/results/P15_R3_R2_reconciliation_2026-10-15/` (four new numerical/integration receipts and a machine-readable custody/gate ledger). Runtime path names are not written into these receipts. Previous R3 candidate receipts and all R2 historical evidence remain intact.
- The **full original-R2 SRC and staged 40/80 kHz DSD256 gates**, plus v2 full composite SRC/27-cell numerical and staged physical 66/80 kHz DSD256 gates, remain OPEN. Intel physical timing remains UNRUN-SCOPE-EXEMPT only for the bounded conservative-dispatch policy. Encoder v1 15-hour soak evidence retained PASS-SCOPED; **P15 RELEASE BLOCKED / P16 NOT AUTHORIZED**.

## Final packaging restart boundary

Only the source-only P00 checksum inventory regeneration remains after this checkpoint. Generate it **last** (excluding itself), verify the complete inventory, create the deterministic complete source archive and an R2-relative delta, reextract and compare all delivered files. Include the archive SHA-256 externally, not in this self-referential source tree. Do not re-run code generation or mutate any receipt after inventory finalization.
