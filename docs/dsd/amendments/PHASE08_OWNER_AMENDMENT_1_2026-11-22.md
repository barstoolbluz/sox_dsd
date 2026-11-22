# SoX DSD binary64 Phase 08: owner amendment 1

**Status:** Decided by the owner on 2026-11-21 and 2026-11-22, as dated below. Signed by the owner on 2026-11-22.

This record amends the signed owner decision record ("the record"). In the tree the record is `docs/dsd/amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md`. Outside the tree it is `SoX_DSD_Binary64_Phase08_Owner_Decisions_2026-11-20.md`; both copies are byte-identical. The record stays unchanged. Where the two differ, this amendment governs. Bare line numbers refer to the record.

## AM1. `main`'s 1.1.2 filters at DSD256–1024 are adopted (amends D7 and D2)

- **Decision (owner, 2026-11-22):** the binary64 line adopts `main`'s 1.1.2 filter change at DSD256, DSD512 and DSD1024 (`3bba2f9a5`, with the matching test expectations in `fbbc36edc`). This covers both sides:
  - the decoder (DSD to PCM): the 1.1.2 mastering FIRs and intermediate clocks;
  - the encoder front end (PCM to DSD): the 1.1.2 mastering rows, that is, the FIR, tap count, working rate, and pass and stop frequencies, for `encode.mastering.v1.dsd256`, `encode.mastering.v2.dsd512` and `encode.mastering.v2.dsd1024`.
- **Not adopted from `3bba2f9a5`:** its version change in `configure.ac`. Under D8 the release stays the owner's decision, and this amendment does not change the version.
- **Qualification:** the 1.1.2 qualification on `main` comes with the filters: the 1.1.2 filter checks in `fbbc36edc`, `24a578b2` (full path through final PCM SRC), `bdcd9b6b` (decoder-bank digests against the filter manifest) and the 1.1.2 acceptance gates in `f895ab0f`. Their assertions about `main`'s own encoder IDs and gain are adapted to D2. Checks of `main`'s encoders themselves, which this line does not have, do not come with them.
- **What this supersedes:**
  - D7, record :182: "are not adopted in Phase 08 (owner, 2026-11-21). They can follow with the later high-rate work."
  - Record :430 (After the decisions), where it excludes the 1.1.2 DSD512/1024 clocks in `fbbc36edc` (D7).
  - Record :431, where it ties `source/tests/dsd/test_p17_numeric.py:119` to the 1.1.2 change on `main`.
  - D2, to the extent that D2 leaves the encoders unchanged at DSD256–1024. Their front-end rows change, as above.
- **What stays as it is:**
  - DSD64 and DSD128, on both sides.
  - The decoder IDs (unversioned, D7) and the encoder IDs at every rate (D2).
  - The modulators at every rate (D2).
  - The archived, inactive rows `encode.mastering.v1.dsd512` and `encode.mastering.v1.dsd1024`.
  - The 0.9 gain and the 0.45 warn-clip ceiling at DSD256–1024. Unity gain at those rates is still later work.
- **Identity and D13:**
  - Under D3, a front end is identified by its front-end manifest and its coefficient tables, not by its ID.
  - The manifest `LSX_PCMDSD_CERTIFICATE_SHA256` = `df25a2a1…` (D3, record :107 and :113) stays, and from now on it identifies the DSD64/128 front end only. The DSD256–1024 rows do not carry it. They carry an identity of the 1.1.2 filters, or none, as on `main`.
  - This is a deliberate version change under D13. D13 (:343) requires that each change "records the reason and keeps the predecessor". The reason is below. The predecessor filters, clocks and their evidence are kept.
  - Approved change to a pinned file: `src/pcmdsd.c`, predecessor Git blob `681739ced15d65b7df0dd3ee9bc5d24f7ffd1133` (the file after AM2). The change is limited to the three encoder rows above and what they need to compile.
- **Evidence that reopens:**
  - The P15 engineering acceptance (record :408) of the DSD256 cells reopens. Their same-transfer obligation (record :225) stays standing.
  - Encoder qualifications at DSD256–1024 that were made with the old front end reopen.
  - No report or certificate presents evidence for the old filters as evidence for the new ones.
- **Reason (owner, 2026-11-22):** "we absolutely should be using wider filters at dsd rates >= dsd256".

## AM2. The CORE-MATH change to `src/pcmdsd.c` is approved (D13)

- **Decision (owner, 2026-11-22):** the owner approves the change to the pinned file `src/pcmdsd.c` that applies CORE-MATH `exp10` to fixed headroom: the `dsd_coremath_gain.h` include and the headroom expression (`a26b55a31` on the owner's line, `17848e20` in the delivery history).
- **Reason:** the owner directed the use of CORE-MATH for the D6 gain.
- **Predecessor:** the `src/pcmdsd.c` of the R3 corrective, Git blob `ab3beae36d5a94efc80f8f718ebb885ea52f06c4` (in `595d401` in the delivery history and in `0d2f7d46f` on the owner's line). It is kept as the predecessor.
- **Approvals in general:** the D13 guard does not grant approvals itself. It accepts a change to a pinned file only when an owner record approves that change, naming the file, its predecessor and the scope of the change. AM1 and AM2 are such approvals.

## AM3. D11 and D6 bounds stay open (disposition of the D11 owner review)

- **Decision (owner, 2026-11-21):** option 1 of `docs/dsd/PHASE08_D11_OWNER_REVIEW_2026-11-21.md` (lines 119-121 of that file at Git blob `e7008bd714202a3a99aa616f90ddc13e417f5e08`), "Defer". The finite gates stay active. D11 and D6 stay OPEN. The delivered computations are engineering evidence only.

## AM4. The `gain` dither change at exact integer factors is accepted (D6)

- **Decision (owner, 2026-11-22):** with CORE-MATH, the `gain` factor at 0, 20, 40, … dB is an exact integer (tested to 140 dB). SoX then keeps the input precision and does not insert automatic dither for 16-bit output. This is accepted as correct behaviour. It is not a regression.
- The gain calculation, the precision tracking and the automatic-dither rules are not changed to restore the old output.
- The ChangeLog states the change.
- **Basis:** the implementing model's verdict of 2026-11-22, "SoX DSD CORE-MATH D6: Gain and Automatic Dither" ("ACCEPT. This is correct behavior, not a defect. Do not restore the old dither behavior."), kept with this amendment as `basis/CORE_MATH_D6_gain_dither_verdict_2026-11-22.md`.

---

**Owner sign-off:** barstoolbluz (owner) Date: 2026-11-22
