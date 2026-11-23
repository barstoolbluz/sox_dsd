# SoX DSD binary64 Phase 08: owner amendment 2

**Status:** Decided by the owner on 2026-11-22. Signed by the owner on 2026-11-22.

This record adds to the signed owner decision record ("the record", `docs/dsd/amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md`) and to owner amendment 1 (`docs/dsd/amendments/PHASE08_OWNER_AMENDMENT_1_2026-11-22.md`). Both stay unchanged. Where this amendment differs from them, it governs.

Git blob and tree IDs below are the same in the delivery history and on the owner's line.

## AM5. DSD256–1024 encoders: usable, stability untested with the 1.1.2 front end (follows AM1)

- **Decision (owner, 2026-11-22):** the encoders `encode.mastering.v1.dsd256`, `encode.mastering.v2.dsd512` and `encode.mastering.v2.dsd1024` stay usable as now, behind the 1.1.2 front end that AM1 adopts.
- Their stability results were obtained with the old front end: the P21 results at DSD512/1024, and the earlier results at DSD256. Under AM1 they reopen. Documents, source comments and reports say so: these encoders are not yet retested with the 1.1.2 front end. They do not present those results as evidence for the new front end.
- The `qualified` flag of these rows in `src/pcmdsd.c` stays as it is, because it gates encoding.
- **Approved change to a pinned file (D13):** comment-only changes in `src/pcmdsd.c` that describe the DSD256–1024 rows and their evidence. Predecessor: Git blob `681739ced15d65b7df0dd3ee9bc5d24f7ffd1133` (the file after AM2). This includes the comment changes already made in Return 1.
- **Later work (owner, 2026-11-22):** "we're going to extend the new modulator to these rates, too. after we ship sox dsd 2.0.0". The new modulator at DSD256–1024 is not part of Phase 08 or of the 2.0.0 release.

## AM6. What the D13 guard pins (D13, AM1, AM2)

- **Decision (owner, 2026-11-22):** the D13 guard may pin the following. Each entry names the file or tree and its predecessor, and the scope of the approved change.
  - **The R3 corrective reference folder:** tree `0c6e4628a1545c75f07bdecf1bb979732096875e` (`tests/pcm64/qualification/reference/`). No change is approved: no edit, no new file and no removed file.
  - **From the R3 corrective `src/` tree `5acbc0d8dc554ce234e3b4fe5f2b62a890f94c6c`:** `src/dsd_coeffs.h` (blob `c48c9e2534e616a2bdb251c0a4ae49f13c534454`), `src/pcmdsd.h` (blob `d9a0ecbdd76c02debe0b3e01d799500b47c2dc02`) and `src/pcmdsd_coeffs.h` (blob `542ce5b5a6ea437e411d755566980fb4c4e58887`), unchanged. No change is approved. The tree also supplies the AM2 predecessor of `src/pcmdsd.c` (blob `ab3beae36d5a94efc80f8f718ebb885ea52f06c4`). No other file in `src/` is pinned through this tree.
  - **`src/dsd.c`:** predecessor blob `510f689377fb2a393ff8928fcac56d7f8050219e`. Approved change (AM1): the DSD256–1024 mastering decoder rows of `3bba2f9a5`, what they need to compile, and comment-only changes to the comment above those rows, including the one made in Return 1.
  - **`src/dsd_decode.c`:** predecessor blob `1a98ea1f07b91ab6918c64853bb58eafcbb7793b`. Approved change (AM1): the 1.1.2 DSD256–1024 mastering banks of `3bba2f9a5`, and what they need to compile.
  - **`src/dsd_stats.c`:** predecessor blob `128266d72ba4acf978d8ee41975f48fafd10eecd`. Approved change (AM1): the identity reporting of the 1.1.2 banks and of encoder rows with no certificate, as in `3bba2f9a5`.
  - **`src/dsd_coeffs_112.h`** (blob `ce7a16ded4c63383a7f45ee5fbd40e2544c1f42f`) and **`src/pcmdsd_coeffs_112.h`** (blob `efffdc263b6f917f76a70e1fb356ef518bc7b6be`): new files, byte-identical to `main` at `5d1e0f40e`. Approved as the 1.1.2 filter tables (AM1). No further change is approved.
  - **`src/pcmdsd.c`:** as AM2 and AM5 approve. Under AM1, the three DSD256–1024 encoder rows and what they need to compile.
  - **The owner records:** the record and the amendments, by their SHA-256 as signed.
- A pinned file that is missing fails the guard.
- **No record after delivery:** the owner does not add a record after a delivery. If a further pin or approval is needed, the delivery states what it must contain. It then comes in a later round.

---

**Owner sign-off:** barstoolbluz (owner) Date: 2026-11-22
