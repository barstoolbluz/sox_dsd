# SoX DSD binary64 Phase 08: owner decision record

**Status:** Decided and signed by the owner on 2026-11-21.
**Date:** 2026-11-20
**Applies to:** Phase 08 R3 (`894833ff`) and its corrective (`595d401a`).
**Companion:** `PHASE08_SPECIFICATION_AND_LOGICAL_GROUNDING_CORRECTED_2026-11-20.md` (sha256 `937632423a5896b5…`), called "the spec" below. IDs C1–C6, P1–P9 and A1–A8 are the spec's.

**Upstream context, decided by the owner on 2026-11-20.**
- The 1.1.x release line on `barstoolbluz/sox_dsd` `main` (`5d1e0f40e`, 1.1.2) has changed since the Phase 08 baseline:
  - `af5d9afdc` (2026-11-09) removed the v2 decoder, the `conservative` alias and the `legacy` decoder. `mastering` names the former v1 bank, and `wideband` is the only alternative. Decoder IDs stayed versioned (`decode.mastering.v1.dsd64`).
  - `0adac40c6` (2026-11-13) made SDM-8 the only composite encoder, with a 0.9 default gain. The same commit dropped the version from every profile ID, decoder IDs included (`decode.mastering.dsd64`, `decode.wideband.dsd64`, …). `main` no longer parses versioned decoder IDs (`origin/main:src/dsd.c:241-260`).
  - `3bba2f9a5` (1.1.2) put new decoder and encoder filters at DSD256–1024. DSD64/128 are unchanged.
- The binary64 line (`sox_dsd-2.0.0`; Phase 08 at `894833f`/`595d401`, from snapshot `4548be78c`) has none of these changes. In `history.bundle` that snapshot is the redacted root commit `4d3fdfd`, so the model's history shares no commits with `main`. Its merge-base with `main` is `a4a14b4f5` (2026-08-29); since then the two lines carry parallel copies of much of the DSD work.
- **Owner decision 1:** the binary64 line adopts `main`'s unified decoder. See D7.
- **Owner decision 2:** the binary64 line keeps its own encoders as they are: `encode.mastering.v3.dsd64/128`, `v1.dsd256` and `v2.dsd512/1024`, with the certified resonator and unity gain at DSD64/128. `main`'s single SDM-8 encoder is not adopted. See D2.

This record settles the questions that the governing documents do not settle. Once the owner decides an item, that decision governs on this route over any earlier document, and the spec is read as amended by it.

**Paths.**
- Paths are relative to the R3 full archive.
- Bare names refer to these locations:
  - `DSD_DESIGN.md`, `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md`, `USING_SOX_DSD.md`, `MIGRATION_P15.md` and `README.md`: under `source/docs/dsd/`.
  - Records named `P15_*`, `P16_*`, `P17_*`, `P18_*`, `P21_*` and `CONTINUUM_EXTREMA_WAIVER_*`: under `source/docs/dsd/amendments/`.
  - `ARCHITECTURE.md`, `VALIDATION_PLAN.md`, `SOURCE_AUDIT.md` and `DECISIONS.md`: under `architecture/`.
  - `PHASE-*.md`: under `architecture/phases/`.
  - Phase 05B owner briefs (`phase05b-*/START.md`): under `inputs/previous-briefs/`. Return 5 is `inputs/RETURN5_START_owner.md`. The Phase 05A return-2 brief they import is not in the archive; the implementation bundle carries it as `phase05a-return2/START.md`.
  - `sox.1` and `soxeffect_ng.7`: under `source/`.
- Bare source and test file names (`pcmdsd.c`, `dsd.c`, `dsdpcm.c`, `sox_ng.c`, `src/dsd_coeffs.h`, `decode.py`, `qualification.py`, `audited_spectrum.py`) are under `source/` at `894833f`, unless `origin/main:` is given. `qualification.py` is cited at `595d401`.
- `RECONSTRUCTION_REFERENCE.md` is in the `595d401` corrective (`changed-files/tests/pcm64/qualification/reference/`).
- `review/clip7/` (with its `commands.txt`), `review/corroboration.md`, `inputs/R3_RETURN_START.md`, `anchor_check.py` (in `inputs/R3_RETURN_review/scripts/`) and the correction `START.md` are in the Phase 08 spec-correction bundle.

Each item gives the question, the sources on each side, a recommendation and a place for the decision.

---

## Part 1. Authority

### D1. How conflicts are settled

The sources contain these precedence statements:

- **Owner and operator records.**
  - `inputs/OWNER_OVERRIDE.md:23-25`: where source history, architecture and phase documents disagree with the owner decision, "the owner decision and this supersession record govern".
  - `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md:3-6` supersedes `DECISIONS.md` D10 and `PHASE-01.md` on 0.9/0.45.
  - `CONTINUUM_EXTREMA_WAIVER_2026-10-21.md:58-59`: "this waiver overrides" any phase document that requires all-extrema certificates.
  - `P16_AUTHORIZATION_2026-10-20.md:5-6`: closing a phase is "the operator's judgment, which is the only thing that can close one".
  - `inputs/PHASE06A_START.md:29`: the owner override stays in force where PHASE-06A states a 0.9 warn factor.
  - The owner's Phase 05B return briefs state required outcomes. Later briefs say the earlier outcomes still hold (for example `phase05b-return3/START.md:12`).
  - The correction `START.md` item 2: code, tests and audits govern only where a governing document adopts them by reference.
- **Other documents.**
  - `P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md:52`, a design-authority record (P16:26), supersedes earlier recommendations to keep generating spectral proofs.
  - `architecture/DECISIONS.md:3`: its decisions "govern implementation". A phase may not silently change them.
  - `README.md:33`: `DSD_DESIGN.md` is "the authority that resolves conflicts with any phase summary". At :38, the design wins over a dispatched brief.
- No source ranks the manuals, `ARCHITECTURE.md` and `DSD_DESIGN.md` against each other. The spec's ranking (spec §1.1, items 2–6) and its rule that "A specific rate/mode option policy takes precedence over a general admonition" (spec :20) are the spec's own.

**Recommendation.**
1. Owner and operator records govern. A later record governs over an earlier one on the same point. Supersession clauses inside those records apply as written.
2. `DECISIONS.md:3` and `README.md:33,38` apply within their stated scopes.
3. Any other conflict among the manuals, the architecture and the design is settled by an owner decision, as in this record, and not by document type.
4. The spec's §1.1 items 2–6 are read as the spec's own reasoning, not as adopted rules.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

---

## Part 2. Encoder

### D2. Default encoder at DSD64 and DSD128

- **v1 side.**
  - `DSD_DESIGN.md:340`: the release defaults include "**v1** mastering encode".
  - `DSD_DESIGN.md:572`: an encoder policy change "would require separate authorization and qualification".
  - `P16_AUTHORIZATION_2026-10-20.md:13-14`: confirms "mastering v1 encoder activation".
- **v3 side.**
  - `sox.1:1481-1485`: the default `mastering` selects `encode.mastering.v3.dsd64/128`, `v1.dsd256` or `v2.dsd512/1024` by output clock.
  - `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md:12-13`: the "Production modulator" at DSD64/128 is v3.
- The closest owner statement is the PHASE01 table's "Production modulator" column (:10-16). `OWNER_OVERRIDE.md:10-11` says only that its level policy "applies to" v3.
- Outside the governing set:
  - `source/docs/dsd/USING_SOX_DSD.md:232-233` says the v1 IDs at DSD64/128 "were retired".
  - `MIGRATION_P15.md:18` (`encode.mastering.v1.dsd128`) and the P21 records (`P21_COLLECTOR_CAMPAIGN_2026-10-25.md:103-105`, `P21_BACKFILL_CORRECTIONS_2026-10-26.md:152-154`; `encode.mastering.v1.dsd64`) predate Phase 01 and treat those IDs as qualified.
- Code: the composite profile table (`source/src/pcmdsd.c:50-88`) has no v1 rows at DSD64/128. The comment at :52 says v3 replaces "the v1 sdm-8 recurrence outright". `encode.mastering.v1.dsd64/128` appear only in the low-level `sdm` table (`source/src/sdm.c:708-709`). This was read, not run.
- The spec does not name this conflict.

**Recommendation.**
- This record provides the authorization that `DSD_DESIGN.md:572` requires. The qualification it also requires is the Phase 08 qualification and its sign-off. The production encoder is v3 at DSD64/128, v1 at DSD256 and v2 at DSD512/1024, as `sox.1:1481-1485` states.
- It supersedes `DSD_DESIGN.md:340` and P16:13-14 on this point.
- At DSD64/128, v1 is not a production encoder option. The low-level `sdm` path is outside this route (spec §1.2).
- Owner decision 2 (above) keeps these encoders and their versioned IDs. `main`'s single SDM-8 encoder and its 0.9 default gain are not adopted on this line.
- Added at the owner's request (2026-11-21): the 0.9 gain and 0.45 ceiling at DSD256/512/1024 are the current state, not the final one. Certified modulators at those rates, with unity gain under `inputs/OWNER_OVERRIDE.md:3-8`, are later 2.0.0 work, after the binary64 path. They are outside Phase 08.

**Decision:** ☒ Accept (owner, 2026-11-21: "the default encoder at dsd64 and dsd128 is the one that is specific to sox dsd 2.0.0", that is, v3) ☐ Amend: ____________________

### D3. The v3 front end is the v1 front end

- `DSD_DESIGN.md:572` (§7.1) specifies the front end for `encode.mastering.v1`:
  - DSD64: 20/40 kHz pass/stop at an 88.2 kHz working clock.
  - DSD128: 30/60 kHz at 176.4 kHz.
- The governing documents state the chain, without naming the profiles or values:
  - `PHASE-06A.md:20`: "Keep the complete existing source SRC -> frontend FIR/interpolation -> native interpolation -> … frozen DSD64/128 kernel".
  - `ARCHITECTURE.md:19-27` and :33-43: flowcharts with the existing binary64 SRC, FIR and interpolation in front of the frozen resonator.
  - `DECISIONS.md:7` (D01, "Reuse … current filters") and `ARCHITECTURE.md:329` ("Existing … frontend descriptors … are adequate").
  - The statements that name v3 and the values are in an audit and in code:
    - `SOURCE_AUDIT.md:87` ("deliberately retains the frontend");
    - `source/src/pcmdsd.c:53` ("The SRC and prefilter stay unchanged");
    - `pcmdsd.c:58-61`: the v3 rows carry 88200/20000/40000 and 176400/30000/60000.
- **Front-end identity.**
  - The front-end coefficient manifest is `LSX_PCMDSD_CERTIFICATE_SHA256` = `df25a2a11855e8a3…` (`source/src/pcmdsd_guards.h:11`). The v3 rows use it (`pcmdsd.c:59,61`). The v1.dsd256 and v2 rows use the same constant (:63 and later), so it identifies the front-end coefficient set as a whole. Each v3 row names its table in a separate field: `lsx_pcmdsd_coeff_master64_256` (61 taps) and `lsx_pcmdsd_coeff_master128` (77 taps).
  - The hashes at `SOURCE_AUDIT.md:84-85` are the modulator certificate hashes, a separate identity.
  - `VALIDATION_PLAN.md:24` and `SOURCE_AUDIT.md:87` require receipts to keep both.
- `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md:40-41` says that only the source policy in `src/pcmdsd.c`, the acceptance assertions and the operator documentation change. It does not state front-end identity explicitly. Two documents read it as doing so: the spec (:18, C3 :66, S3 :80, §2.2B :111, P9 :286, §8 :317) and our correction brief (observation 1; `review/corroboration.md:9`). That reading is withdrawn.

**Recommendation.**
- Adopt: `encode.mastering.v3.dsd64/128` use the `DSD_DESIGN.md` §7.1 v1 front end. It is identified by the front-end manifest `df25a2a1…` and the two named coefficient tables.
- The modulator is identified separately by its certificate hash (`SOURCE_AUDIT.md:84-85`).
- This names the profiles and values that `PHASE-06A.md:20` and the architecture leave implicit. Front-end identity becomes a governed requirement, not a code-only value.

**Owner amendment (2026-11-21).** This holds pending a design review of the v1 front end and its possible refactoring. That review is later work, outside Phase 08. A refactored front end is a deliberate version change under D13: it gets a new identity, is qualified against the §7.1 limits or limits the owner sets, and needs owner approval. Until then, Phase 08 qualifies the front end identified above.

**Decision:** ☐ Accept ☒ Amend (owner, 2026-11-21): accepted with the amendment above.

### D4. Which v1 and analysis-v1 limits apply to v3 (spec P9)

"Gate" means a release requirement. "Report" means the value is measured and recorded, without a pass or fail.

| Limit | Source | Recommendation |
|---|---|---|
| Front-end transfer: prefilter ≤0.0001 dB passband error and 185 dB rejection target; both SRC stages (input to R, R to native) 180 dB, 95% 0-dB bandwidth | `DSD_DESIGN.md:572` (§7.1) | **Gate.** Follows from D3: the same coefficients. |
| An unnoticed extra 6.0206 dB loss is release-blocking | `DSD_DESIGN.md:849` | **Gate.** Route-independent. |
| DSD64: every complete 28-bit window holds 4–24 ones, in the qualified nominal corpus | `DSD_DESIGN.md:611`, :845 | **Gate.** The R3 evidence already records it on v3. In the 9 DSD64 cases of `evidence/phase08/native64-family/dsd64-*.decode.json`, the ones count is 9–19 and `28_bit_excursions` is 0. The companion `dsd64-*.encode.json` files name `encode.mastering.v3.dsd64`. That is a synthetic matrix. Until the owner names a nominal corpus, the Phase 08 matrix serves as one. |
| Cross-ISA: fundamental gain ≤0.001 dB; THD+N and ultrasonic noise ≤1 dB worse; pairwise residual with a 3 dB margin; no spur >3 dB worse than the scalar control | `DSD_DESIGN.md:853-855`, :845 | **Gate** wherever a non-scalar v3 kernel variant ships. These are analysis-v1 comparisons (:853). We found no analysis-v1 cross-ISA result in the R3 evidence. |
| Spurs ≤−110 dBFS (DSD64), ≤−120 dBFS (DSD128), under analysis-v1, for silence and low-level input | `DSD_DESIGN.md:845` | **Report first, then decide.** It is the project's stated qualification target. We found no analysis-v1 result in the R3 evidence. Making it a gate now could block release on an unmeasured value. This defers the pass/fail use of this limit for v3 (`DSD_DESIGN.md:845`) until the first analysis-v1 measurement. Analysis-v1 itself stays the procedure (D12). |
| `sdm-8` promotion: ≥6 dB lower residual at DSD64; ≤1 dB worse at DSD128/256 | `DSD_DESIGN.md:623` (§7.4) | **Not applicable.** It is a criterion for promoting `sdm-8`. At DSD64/128 the production modulator is v3 (`PHASE01…:12-13`; `pcmdsd.c:51-52`). |

**Decision:** ☒ Accept all (owner, 2026-11-21) ☐ Amend rows: ____________________

### D5. Overload in warn mode (spec C2)

- `DSD_DESIGN.md:601` says overrange values are "not a license to clamp". :603 says "fail on overload". :849 says overload must fail without a successful status.
- `OWNER_OVERRIDE.md:10-14` and `sox.1:1538-1547` set warn mode at DSD64/128 to clip at 0.5, and to count and warn.

**Recommendation.**
- For v3 at DSD64/128, warn mode clips at 0.5, counts each clip and warns. Error mode refuses. Basis: `OWNER_OVERRIDE.md:23-25` under D1, not the spec's "specific over general" rule.
- Off this route, at DSD256/512/1024, the same conflict exists. `sox.1:1544-1546`, `OWNER_OVERRIDE.md:17-19` and `PHASE01…:14-16` give warn-mode clipping at 0.45. That conflict is not decided here.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

### D6. Gain arithmetic (spec P1)

- `soxeffect_ng.7:1172` says `gain` "adjusts the signal power level by the given number of dB". A power change of d dB is an amplitude factor of 10^(d/20), so this formula restates the manual. It is not a new rule.
- `ARCHITECTURE.md:297` already states the headroom factor `pow(10, -DB/20)`.

**Recommendation.**
- Adopt amplitude factor 10^(d/20) for `gain` and 10^(−d/20) for `--headroom d`, each applied once at its documented position.
- A 0 dB gain performs no arithmetic transform (spec P1: "Ordinary identity gain should not perform an unnecessary arithmetic transform").
- Do not adopt a numeric `pow` error limit now. The implementation brief derives one under D11.

**Decision:** ☒ Accept (owner, 2026-11-21, with the 0 dB point added) ☐ Amend: ____________________

---

## Part 3. Decoder

### D7. The decoder: `main`'s unified decoder (owner decision 1)

**Decided by the owner on 2026-11-20.** The binary64 line adopts `main`'s unified decoder (`af5d9afdc`):
- At DSD64/128, `mastering` names the former v1 bank: `--decode mastering`, the automatic default, and the effect's `-p mastering`.
- `wideband` is the only alternative.
- The v2 decoder, the `conservative` alias and the `legacy` decoder are removed.

**Sub-decision: decoder ID names.**
- `main`'s unversioned decoder IDs came with `0adac40c6`, the encoder commit that owner decision 2 does not adopt.
- Adopting them takes only the decoder part of that commit. Decoder IDs would then be unversioned (`decode.mastering.dsd64`), while encoder IDs stay versioned (`encode.mastering.v3.dsd64`).
- **Recommendation:** adopt the unversioned decoder IDs, to match `main`, whose reader no longer accepts versioned ones (`b40332a1f`).

**Decision on decoder IDs:** ☒ Unversioned, as `main` (owner, 2026-11-21) ☐ Keep versioned (`decode.mastering.v1.*`)

**The v1 bank on this route.**
- The coefficients in `src/dsd_coeffs.h` are the same on `main` and at `4548be78c`; only a comment line differs.
- P/S/R: DSD64 20/40/88.2 kHz, DSD128 30/60/176.4 kHz (`source/src/dsd.c:171-172`; restated at `DSD_DESIGN.md:572`).
- Reconstruction: Master64 G = 1,348, phase 4, discard 42; Master128 G = 1,636, phase 4, discard 51 (`DSD_DESIGN.md:503-504`).
- The decoder limits of `DSD_DESIGN.md:429` apply to all decoder profiles: passband error ≤0.0001 dB, alias/stopband transfer ≤−160 dB.
- `main`'s 1.1.2 changes to decoder filters and clocks at DSD256–1024 (`3bba2f9a5`, with the matching test expectations in `fbbc36edc`) are not adopted in Phase 08 (owner, 2026-11-21). They can follow with the later high-rate work.

**What this supersedes.**
- On the decoder default: `sox.1:1462-1466`, `P15_V2_DEFAULT_POLICY_2026-10-15.md:9-11` and `P16_AUTHORIZATION_2026-10-20.md:13-14`.
- `DSD_DESIGN.md:340`, in full for the decoder: the v1 default "while P15 is blocked", "`conservative` selects v1", and the versioned-ID rule ("Exact versioned IDs survive future alias migration"), since the sub-decision above takes unversioned IDs.
- `sox.1:1467-1477`: `conservative`, the v1/v2 ID examples and `legacy`.
- `soxeffect_ng.7:3688-3696` (v2 selected without `-p`; v2 passbands 25/48/66 kHz) and :3705-3710 (the `decode.mastering.v2.dsd128` pin, `-p legacy`).
- `soxeffect_ng.7:3699-3703` (`-p mastering` → v1) agrees with this decision, except that `-p conservative` is removed.

**Effect on Phase 08 evidence.**
- **v2 results:**
  - 18 of the 19 accepted reconstruction fixtures, from `evidence/phase08/native64-family/*.decode.json`, which name `decode.mastering.v2.dsd64` and `.dsd128` (9 each). The 19th, `gain_effect`, has no recorded decoder ID. It used the tree's implicit default, which is v2 (`source/src/dsd.c:281,308`).
  - The clip7 run (`profile_id` `decode.mastering.v2.dsd64`).
  - Our review's anchor decode. `anchor_check.py` passes no `--decode`, so it used the same default. This is an inference; no ID was recorded.
- **v1 results.** `evidence/phase08-all/decode-fixtures/` holds 48 matrix reports, 8 each of:
  - `decode.mastering.v1.dsd64` and `.dsd128`;
  - `decode.wideband.v1.dsd64` and `.dsd128`;
  - `decode.mastering.v2.dsd64` and `.dsd128`.

  The v1 results compare the CLI with the public API, so they are agreement checks, not independent references (spec §2.1).
- The Phase 08 harness passes versioned decoder IDs (`source/tests/pcm64/decode.py:129`).

See D16.

**Decision:** ☒ Recorded (owner, 2026-11-20; decoder IDs 2026-11-21)

### D8. First release and the open P15 obligations

- **Blocked side.**
  - `DSD_DESIGN.md:764-765` (§8.6.1): "The first release remains blocked until both the same-transfer arithmetic and complete-chain transfer evidence exist". :340 calls v2 a candidate only.
  - `P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md:48`: arbitrary-input FFT4G roundoff and the same-operator finite transfer are "NOT DISCHARGED", and "mandatory §8.6.1 release-execution requirements". :50: overall P15 release authorization is "OPEN / NOT AUTHORIZED".
- **Authorized side.**
  - `P16_AUTHORIZATION_2026-10-20.md:13`: "First release is authorized." :19-24 keeps two gates OPEN. :26-32 says the formal-proof obligation is "no longer required for release" and calls the obligations "standing, not blocking".
  - P16:92 limits its scope: "Authorizes the start of P16 only".
  - `P17_AUTHORIZATION_2026-10-21.md:32-35` and `P18_AUTHORIZATION_2026-10-21.md:48-49` repeat that both gates remain OPEN and standing.
- **Waiver.** `CONTINUUM_EXTREMA_WAIVER_2026-10-21.md:5-13` permanently waives the all-extrema/coherent-alias certificate requirement for the whole DSD engine. That is part of P16 gate 1 (P16:23). The other part of gate 1, an independent same-transfer arithmetic certificate for the 72 SRC-active cells, is not waived. Gate 2 (DSD256) is off this route.
- **P16's account of P15_SPECTRAL.** P16:26-30 reports P15_SPECTRAL as saying that the formal-proof obligation is no longer required for release. P15_SPECTRAL:48-50 also keeps the same-operator execution requirements mandatory and the release unauthorized. The spec places P16 and the open items side by side (§1.1 item 2 :19; L6 :201), but names none of these as conflicts in C1–C6.

**Recommendation.**
- **Release.** First release is authorized, as P16:13 states. P16 is an operator record (D1 item 1). It governs over P15_SPECTRAL:48-50, a design-authority record (D1, other documents), and over `DSD_DESIGN.md:764-765`. This record confirms P16:13 despite P16:92's narrower scope line.
- **Gate 1.** The all-extrema part is closed by the waiver. The same-transfer arithmetic part stays open as a standing obligation, not a release blocker.
- **The open part overlaps D11.** Gate 1 covers 72 SRC-active cells: 48 v1 and 24 v2 (`DSD_DESIGN.md:712-714`).
  - With the v2 decoder removed (D7), the 24 v2 cells no longer describe a shipped decoder.
  - The 48 v1 cells span DSD64/128/256 and the mastering and wideband profiles. The D11 decoder bound (spec P3) covers the mastering and wideband cells at DSD64/128, which are on this route. The DSD256 cells stay standing.
- **Native routing.** Automatic routing to native binary64 still needs its own owner authorization (spec line 6).
- **Scope (owner, 2026-11-21).** D8 clears the old P15 blockers only. P16:13 authorized the first release, which shipped as `sox_dsd-1.0.0` (2026-10-23); the 1.x releases followed. Releasing 2.0.0 stays the owner's decision, when the work is done.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

### D9. Decoder float output above unity (spec C6, P8)

There are three positions in the sources.

- **Clip at the graph boundary, for float output too.**
  - `sox.1:1538-1540`: `--dsd-clip` means "warning and clipping" for reconstructed PCM overshoots.
  - `DSD_DESIGN.md:543`: "Float WAV/AIFF output does not bypass that boundary". :547: "The same clipping policy applies" to finite-boundary overshoot.
- **Preserve float output; `--dsd-clip` applies only at integer endpoints.**
  - `ARCHITECTURE.md:160` (§5.4): "F64 output does not clamp to ±1". :164: over-unity F64 is not an integer clip.
  - `VALIDATION_PLAN.md:66`: for F32, "Over-unity finite output is preserved when representable". :183 lists "Clamp float samples to unity" as a defect that an adversarial gate must detect.
  - `PHASE-05.md:25`: "F64 sink stores finite >1 without clipping … `--dsd-clip error|warn` applies at the integer endpoint". `PHASE-05A.md:21` says the same.
- **Owner outcomes for error mode: parity with the default route.**
  - `phase05b-return1/START.md:23`: under `--precision 64`, `--dsd-clip error` fails a run that the default route rejects for clipping, "for every output encoding, floating point included". "The run's report says it failed and names the clipping as the cause."
  - `phase05b-return2/START.md:24`: error mode fails exactly the runs the default route fails, and completes the ones it completes, "with `-v`, `--dsd-level` and every output encoding the native route runs". Commands that run natively still run natively. :50 is an observation under outcome 5 (:22): a check that ran only with a report would pass `--dsd-clip error` runs without `--report`. Outcome 7 (:24) covers those runs, since the default route needs no `--report`. :51-53 record that the native route then checked before `-v`, while the default route checks after it.
  - `phase05b-return3/START.md:12` says these outcomes still hold.
  - These owner returns postdate `PHASE-05.md`. Under D1 they govern its integer-endpoint scope for error mode.
- **Owner record for warn mode.**
  - No owner brief sets a warn-mode outcome for decoded float output. We checked the Phase 05B start brief and returns 1–5, `inputs/*START*.md`, and the Phase 05A return-2 brief they import.
  - `phase05b-return1/START.md:37` records under "What held": "Values above full scale were kept in floating-point output."
- **A related conflict, not named in the spec.** `DSD_DESIGN.md:543` also says "This release does not add a parallel direct-to-writer float CLI pipeline". The native binary64 route (`ARCHITECTURE.md` §§4–5) is such a pipeline.
- **Observed.**
  - `review/clip7/`: an overrange DSD64 file, decoded with `--dsd-level sacd` to F64.
    - `warn`: exit 0, samples preserved (peak 1.0143159955083783; 19003 samples above 1), no warning on stderr, `warnings` empty, `graph_clips` 19003.
    - `error`: exit 2 at frame 3, channel 1, magnitude 1.00163917.
    - The tree is attributed to `595d401` by `commands.txt` only. The report's build field gives `source_baseline=d940cc93` and no digest.
  - The R3 evidence also has error-mode F64 clip fixtures, for example `evidence/phase08-all/decode-fixtures/clip-float64.json` (status `failed`).
  - These runs used the v2 decoder (`review/clip7/rep-warn.json` names `decode.mastering.v2.dsd64`). Under D7 the behaviour must be observed again with the unified decoder.

**Error mode (owner outcome, confirmed here).**
- Float output fails exactly when the default route fails for clipping, for every output encoding the native route runs, with or without `--report`.
- The report says the run failed and names the clipping as the cause.
- Commands that run natively still run natively.
- **Check position.** After `-v` (`phase05b-return2/START.md:51-53`). Also after the `--dsd-level` gain, which the default route applies before its graph-boundary count (`DSD_DESIGN.md:543`).
- **Predicate.**
  - The default route's decoded output passes through `sox_sample_t` (`DSD_DESIGN.md:543`), so +1.0 is out of range there. Parity therefore implies the integer predicate `x >= 1 || x < -1` (`ARCHITECTURE.md:164`, `VALIDATION_PLAN.md:64`).
  - Both routes already use it in code: the default route at `src/dsdpcm.c:69` and the native route at `src/sox_ng.c:4342`. No governing document states it for float output.
  - The native route counts excursions only when a report is active or the mode is error (`src/sox_ng.c:4328`). Option (a) below needs counting and a warning in warn mode without `--report`.
  - It amends spec P8 and §2.3, which use `abs(y) > 1` and allow exact ±1.
- **Nonfinite values fail.** Basis: `ARCHITECTURE.md:299` ("Generated nonfinite intermediates fail the transformed stream"), and parity with the default route, which fails them (`src/dsdpcm.c:63-66`). No owner brief states it.
- This supersedes the integer-endpoint scope of `PHASE-05.md:25` and `PHASE-05A.md:21` for error mode. Option (a) below changes it for warn mode.

**Warn mode: options.**
- **(a) Preserve and warn.**
  - Finite F64 samples above unity are written unchanged. F32 samples get their one specified rounding and are not clipped.
  - Excursions are counted in `graph_clips`, documented as excursions, using the same predicate as error mode.
  - The peak is recorded.
  - One warning is printed on stderr and recorded in `warnings[]`.
- **(b) Clip and warn, as the default route does.** This supersedes `ARCHITECTURE.md` §5.4, `VALIDATION_PLAN.md:66` and :183, `PHASE-05.md:25` and `PHASE-05A.md:21` for this boundary.

**Recommendation: (a).**
- Float output exists to carry values above unity without loss. Option (a) keeps the float preservation in §5.4, `VALIDATION_PLAN.md:66` and :183, `PHASE-05.md:25` and `PHASE-05A.md:21`, and the observed sample behaviour.
- It extends warn-mode counting and the warning to the float endpoint, which `PHASE-05.md:25` and `PHASE-05A.md:21` place at the integer endpoint.
- It matches the owner record at `phase05b-return1/START.md:37`. The owner briefs require parity only in error mode.
- (a) supersedes `DSD_DESIGN.md:543` and :547 for float output on the native route, including the :543 "no direct-to-writer float pipeline" statement. `sox.1:1538-1540` is amended to say that float output warns without clipping.

**Effect on `595d401`.**
- Under (a), the `warn` path must emit the warning.
- The observed `error` cases fail as required.
- The implementation brief tests error-mode parity with the default route: exact +1.0 and −1.0, nonfinite values, `-v`, `--dsd-level`, and runs with and without `--report`.

**Decision:** ☒ (a) (owner, 2026-11-21; error-mode predicate `x >= 1 || x < -1` also accepted, so exact +1.0 counts and −1.0 does not) ☐ (b) ☐ Amend: ____________________

### D10. Error-mode failure and output already written

- `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md:26-28`: error mode "fails closed without publishing partial output".
- `ARCHITECTURE.md:103`, `DSD_DESIGN.md:609` and `VALIDATION_PLAN.md:120`: no part of a failed block is published. Earlier completed blocks may already be in the stream, and a pipe cannot be retracted.
- Under D1 the owner text would govern. Read literally, it asks for more than a pipe can give.

**Recommendation.**
- The owner states the meaning of PHASE01:26-28 as `ARCHITECTURE.md:103` gives it: no part of the failed block is published.
- The run ends with a non-zero status, a failed report and no completion record.
- Bytes already sent to a pipe are not retracted.
- For a regular output file, the implementation brief states and tests what remains on disk after a failure.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Require stronger file behaviour: ____________________

---

## Part 4. Proof, evidence and scope

### D11. Scope of "for all inputs" (spec P6)

- **(a)** All eligible finite streams for the named source, build, CPU, OS, format and route matrix, subject to resources and the specified refusals.
- **(b)** A smaller, defined input class (peak, energy, bandwidth or length bound).

**Recommendation: (a)**, with the matrix named in the sign-off. The implementation brief then:
- adds the remaining same-operator error bounds (spec P2 encoder front end, P3 decoder), starting from the existing `DSD_DESIGN.md` §8.6 envelope (:693) and the §8.6.1 `B_fir` term (:728). The P3 decoder bound is for the decoders of D7 at DSD64/128: `mastering` (the former v1 bank) and `wideband`;
- adds independent checks of each stage against them.

**Owner wording (2026-11-21).** Every input that the route accepts, that is, one the clip rules and the documented refusals do not reject, produces output that matches the exact result within the stated error bound. Inputs that are too hot are handled by D5 and D9. This holds on the builds, CPUs, operating systems and formats named at sign-off.

**Decision:** ☒ (a) (owner, 2026-11-21, with the wording above) ☐ (b), class: ____________________

### D12. Spectral metrology

- `PHASE-08.md:27` (item 7) and `VALIDATION_PLAN.md:172` adopt the audited harness's analysis semantics.
- The adopted source is the harness's `dsdqual/analysis.py`, at `audited-harness-working-copy/harness/dsdqual/analysis.py`. It is byte-identical to the copy in the immutable harness tarball.
- `source/tests/pcm64/qualification/audited_spectrum.py` is a Phase 08 re-implementation that says it "follows" that file (:3). The spec cites the re-implementation as the adopted source, as our corroboration did.
- `DSD_DESIGN.md` §10.2 (:805-813) defines a different procedure, analysis-v1. :805 requires it "before setting or comparing encoder quality results". :815: "The primary pass/fail numbers remain analysis-v1".
- We found no analysis-v1 result in the R3 evidence.

**Recommendation.**
- Phase 08's finite residual measurements use the harness's `dsdqual/analysis.py`. `audited_spectrum.py` must agree with it.
- Analysis-v1 stays the primary pass/fail procedure for encoder quality limits (`DSD_DESIGN.md:815`), including the D4 spur and cross-ISA rows. The other D4 gate rows are not analysis-v1 measurements. D4 defers only the pass/fail use of the spur limit until the first measurement. The implementation brief generates analysis-v1 for v3, as :805 requires.
- Neither procedure's dBFS numbers are converted into the other's without a documented crosswalk.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

### D13. Accepted references (spec P7)

This is already required by `R3_RETURN_START.md` item 4 and `RECONSTRUCTION_REFERENCE.md:15-16`. The spec states it as mandatory.

**Recommendation.** Confirm the spec's P7 as written. Accepted outputs, hashes, source identity and constants are never regenerated automatically. Each change needs an explicit owner approval that records the reason and keeps the predecessor.

**Decision:** ☒ Confirm (owner, 2026-11-21) ☐ Amend: ____________________

### D14. The 2^-48 cross-backend allowance

- `RECONSTRUCTION_REFERENCE.md:18-22` sets exact SSE2 words, or an absolute 2^-48, for alternate backends on the 19 reconstruction fixtures.
- No governing document states it.

**Recommendation.** Adopt it as an interim regression allowance for those 19 fixtures only. D11's P3 bound replaces it for general input.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

### D15. Remaining proposals and premises

**Recommendation.**
- **P4:** Confirm. Spectral claims stay at the engineering tier of `P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md`, with the waiver in D8.
- **P5:** Defer. It is a container-specification authority, and low priority.
- **A1, A2, A5, A7:** Accept as named premises of any sign-off (arithmetic model, source-to-binary correspondence, the v3 certificate, container semantics). Each must appear in the sign-off text.
- **A3, A4:** Discharged by the implementation brief.
- **A6:** Discharged by this record for the other proposals. P5 stays deferred. P2, P3 and the numeric `pow` limit of P1 (D6) stay open until the owner adopts the bounds that D11 asks the implementation to derive.
- **A8:** Covered by P4 and D8.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________

### D16. Reconstruction references after the decoder change

- The 19 accepted reconstruction fixtures (`accepted-reconstruction-sse2.zlib`, sha256 `dde0a8fb…`; `RECONSTRUCTION_REFERENCE.md:3-13`) are v2 decoder outputs (D7). Under D7 they no longer describe the shipped decoder.
- The Phase 08 v1 matrix results (D7) are CLI-versus-API agreement checks. They are not accepted references.
- The same verifier also checks encoder-side facts: exact DSD decisions and post-clip inputs (`RECONSTRUCTION_REFERENCE.md:22-24`). Those do not depend on the decoder and are not affected.
- D13 forbids regenerating accepted references automatically. A deliberate algorithm change may be approved, without weakening the unchanged version's gate (spec P7).

**Recommendation.**
- Approve the decoder change as a deliberate version change under D13.
- Retain the v2 fixtures as the versioned predecessor. Do not delete them.
- Do not accept a re-recorded unified-decoder output as a reference by itself. New references for the unified decoder need independent justification: the D11 P3 bound, or values computed independently of the code under test.
- Until then, the reconstruction gate is OPEN for the unified decoder, not PASS.
- In the meantime, decoder output stays checked against values computed outside the code under test, from the first patch on (owner, 2026-11-21).
- D14's 2^-48 allowance stays attached to the v2 predecessor fixtures. A new allowance for the unified decoder comes from the D11 P3 bound.

**Decision:** ☒ Accept (owner, 2026-11-21) ☐ Amend: ____________________


---

## Corrections to our own review material

These came from our review, not from the model, and are withdrawn:

1. The correction brief (observation 1) and `review/corroboration.md:9` cited `PHASE01_OWNER_LEVEL_POLICY_2026-11-09.md:40-41` as stating that v3 keeps the v1 front end. It does not. See D3.
2. `review/corroboration.md` item 2 cited `audited_spectrum.py` as the source of the adopted analysis numbers. The adopted source is the harness's `dsdqual/analysis.py`. See D12.

## Effect on the spec

D7 changes the decoder parts of the spec. These are read as amended:
- **§1.1 item 2 (:19), §1.2 (:38), A6 (:260), §8 (:324-325) and §9 (:346):** P16 and P15_V2 no longer set the decoder default. D7 does. The §1.2 domain reads "`mastering` (the former v1 bank) by default, `wideband` if chosen".
- **S9:** the mastering decoder is the former v1 bank, with P/S/R 20/40/88.2 and 30/60/176.4 kHz. The v2 values and selectors no longer apply.
- **S10:** reconstruction is G = 1,348 / 1,636, phase 4, discard 42 / 51 (`DSD_DESIGN.md:503-504`). The v2 values 1,636 / 3,428 and 51 / 107 no longer apply.
- **L6 (:201):** "rate-dependent mastering-v2 bank" reads as the former v1 bank.
- **S11, L7 (:211-217) and P3:** the 19 fixtures and the 2^-48 allowance describe v2 (D16).
- **§2.3 (:124-128):** the clip7 table is a v2 run. It stays as evidence about v2 only (D9).
- **§4 (:233-239):** the ablation's 8 accepted-output comparisons and the anchor decode were against v2 output. Their conclusions about the decoder apply to v2. Their conclusions about the encoder stages are unaffected.
- **§7 matrix (:298-299):** "Selected v2 ideal stationary reconstruction" reads as the D7 decoders. The 19-fixture row describes v2.
- **C5** is settled by D7.
- **A8 and P4:**
  - The P15 engineering-tier acceptance covers the v1 family as well: 11,516 jobs in 72 SRC-active cells (`P15_SPECTRAL…:25`), 48 of them v1 (`DSD_DESIGN.md:712-714`; also `CONTINUUM_EXTREMA_WAIVER_2026-10-21.md:17-19`). So it still applies to the unified decoder, provided the ported banks and SRC are unchanged. A change to taps, stage topology or ratios reopens it (`P15_SPECTRAL…:56`, criterion (c)).
  - A8's sentence on the P16 v2 default no longer applies.

The other decisions amend the spec as follows:
- **D1:** §1.1 items 2–6 and the "specific over general" rule (:20) are the spec's own reasoning, not adopted rules.
- **D3:** front-end identity is a governed requirement, as amended. The spec's reading of `PHASE01…:40-41` (:18, C3 :66, S3 :80, §2.2B :111, P9 :286, §8 :317) is withdrawn.
- **D4:** settles P9.
- **D5:** C2 is settled by `OWNER_OVERRIDE.md:23-25` under D1, not by the spec's rule at :20.
- **D6:** adopts P1, with the 0 dB point.
- **D8:** settles the spec's treatment of P16 and the open P15 gates (§1.1 item 2 :19, L6 :201).
- **D9:** settles C6 and P8 (option (a), predicate `x >= 1 || x < -1`). It amends §2.3, S11 and L7.
- **D10:** sets the meaning of error-mode partial output.
- **D11:** settles P6. **D12:** amends S12. **D13:** confirms P7. **D14, D16:** settle the 2^-48 allowance and the 19 fixtures.
- **D15:** confirms P4, defers P5, and settles A1–A8 as stated there.

Owner decision 2 keeps the encoders. It does not leave the encoder parts of the spec unamended.

## After the decisions

The spec, as amended by this record, is the input to the Phase 08 implementation brief. That brief covers:
- porting `main`'s unified decoder onto the binary64 line. What we found, which may be incomplete:
  - `af5d9afdc` and its companion commits of 2026-11-09: `e301af6bc`, `eecefed66` (including `UNIFIED_DECODER_2026-11-09.md`), `9944c5fe0` and `443b3099c`.
  - For unversioned decoder IDs: the decoder part of `0adac40c6`; the decoder-ID test and documentation changes in the encoder commits `71de5ae77` and `144f5a271`; the ID part of the P21 reader change in `fbbc36edc`, whose 1.1.2 DSD512/1024 clocks are not adopted (D7); and the test change in `b40332a1f`.
  - On this line, the tests that `b40332a1f` changes are `source/tests/dsd/test_reader_gate.py` and `source/tests/dsd/fake_decoder.py`, and the P21 reader is `source/tests/dsd/p21_independent_reader.py`. `fbbc36edc` also changes a decoder ID in its `test_p17_numeric.py`; on this line that ID is at `source/tests/dsd/test_p17_numeric.py:119`, tied on `main` to the 1.1.2 high-rate change.
  - Phase 08 code that names v2 or versioned decoder IDs, which no `main` commit changes: in `source/tests/pcm64/`, `decode.py:128-131`, :182-184 and :509-580; `qualification.py:224`, :230 and :267 (at `595d401`); `qualification/verify.py:214` and :234 (:218 and :238 at `595d401`); `bench_phase05b.py:49`; `phase05b_corrective.py:259` and :275; `transcode.py:104`; `transcode_probe.c`; and `decode/api_oracle.c`.
- the documentation that follows from D7. What we found, which may be incomplete: `sox.1:1409-1410`, :1462-1477 and :1665; `soxeffect_ng.7:3688-3711`; `DSD_DESIGN.md:324`, :333, :340 and :358-359; `USING_SOX_DSD.md:15`, :210-220 and :287-289; `MIGRATION_P15.md:15-17` (and :18, an encoder row, for D2);
- new reconstruction references for the unified decoder under D16;
- D9 behaviour, including the D9 error-mode parity tests, observed with the unified decoder;
- analysis-v1 for v3 (D12), and the first measurement of the D4 "report first" limit;
- agreement of `audited_spectrum.py` with the harness's `analysis.py` (D12);
- the D10 file-state statement;
- the D11 bounds and independent checks, including the on-route cells of the open same-transfer part of D8;
- a check that enforces the D13 rule;
- the other documentation fixes that the decisions imply (`sox.1:1538-1540`, and a note at `DSD_DESIGN.md:543` and :547 that D9 supersedes them for native float output).

**Owner sign-off:** barstoolbluz (owner) Date: 2026-11-21
