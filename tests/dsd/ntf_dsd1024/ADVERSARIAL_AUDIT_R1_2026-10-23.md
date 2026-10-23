# SoX DSD1024 NTF Research R1 — Independent Adversarial Engineering Audit

**Audit date:** October 23, 2026  
**Scope:** Original `sox_dsd-dsd1024-ntf-brief.md`; baseline `sox_dsd-a5e77be5d-working-set.tar.zst`; R1 full source `sox_dsd_DSD1024_NTF_RESEARCH_R1_2026-10-23.tar.zst`; accompanying SHA-256 and source inventories.  
**Mode:** Read-only audit of supplied source; independent native builds, measurements, and scratch-only test receipts. No corrective implementation or production changes.

## Verdict

**REJECT the delivered candidate-advancement recommendation and research screening as ready for the next candidate-qualification phase.** The underlying source-bound, short-duration research is substantially authentic and numerically reproducible. The incumbent CLANS-7 remains unchanged and previously qualified. But 15 of the 23 advertised research-improvement candidates fail ordinary full-scale native nonlinear inputs omitted from the required screening set. In particular the preferred historical SDM-8 goes nonfinite on both polarities of full-scale DC, and the independent-family CLANS-8 goes nonfinite on those as well as full-scale 997 Hz. That contradicts the brief's express requirement to gate fidelity on nonlinear stability.

The alternative **SDM-8 with doubled resonators** survives the three added cases; that is encouraging evidence for further exploration, **not** a release, deployment, or P19 qualification certificate. The delivered report itself correctly denies production authorization; this audit rejects its **research shortlist and next-phase candidate recommendation as screened**, not the untouched production implementation or the validity of its original measured low-band differences.

## 1. Input integrity and preserved authority — PASS

| Item | Verified result |
|---|---|
| Baseline archive SHA-256 | `bf0ae0b2344abb22c6592a5acf7cb2c586155ad7e5d9d219f58ce329ca3960c2` |
| R1 full-source archive SHA-256 | `0fe159346a3c2c7c7c5aa51cc57e855ca3c94af03c41e83440b55d6c1db1b0c1` |
| Included/omitted inventory hashes | Match supplied R1 manifest |
| Baseline original files | 3,056 present |
| Original files changed / removed | **0 / 0**, independently SHA-256 compared |
| Files added | 445, only under `tests/dsd/ntf_dsd1024/` |
| Research internal manifest | All 444 entries PASS |
| Archive extraction checks | No unsafe archive-member traversal or unsafe symlink found |
| Production state | Production `src/sdm.c`, candidate header, guards, P00 identity, P19/P20 evidence all unchanged relative to baseline |

The original working set intentionally omits 49,964 source files and 1,351 `.npz` files. It is not evidence that the entire upstream repository or all original P15 certificate validators passed. The sidecar also names an optional `STUDY_ONLY_R1` archive that was not attached; this audit did not authenticate that optional archive. These are clearly delimited scope limits, not demonstrated regressions.

## 2. Independently reproduced results — PASS where specifically indicated

A second experimental native executable was built under a disposable independent checkout; its binary SHA-256 differed from the delivery's while the bound experimental C source and coefficient-header SHA-256 identifiers matched. No production source was edited. The P10 native `--unit` suite passed **105,489 assertions, zero failures**.

| Claim | Independent assessment |
|---|---|
| All ten historical CLANS/SDM orders and three DSD512 seed profiles | PASS; exact source-bound binary64 hex coefficients |
| 55 candidate profiles | PASS; 55 distinct coefficient vectors |
| 220 four-case short screens | PASS; **220/220 exact packed-bitstream hashes** on new native executable |
| 55 primary native renders | PASS; **55/55 exact packed-bitstream hashes** |
| 55 primary spectral comparisons | PASS; **55/55 exact published band metrics** by independently replaying the provided reconstruction method |
| 23 candidates satisfying the published formula | PASS as arithmetic; 23/23 selection-rule matches, but screening formula is incomplete |
| Five continuous 32-second tests | PASS; 5/5 exact packed streams (each 1,445,068,800 native frames), reported zero nonfinite/overload/28-bit excursions |
| Alternative reconstruction FIR | PASS; all four reruns match; maximum 0.01788 dB change over three selection bands |
| 12 research unit tests | PASS |
| `verify_evidence.py` | PASS for its **stated limited remit**; not an independent numerical oracle |
| Fresh independent P19 incumbent guard regeneration | PASS; all eight historical training maxima and guard bounds exactly reproduced, all 17 training cases and 36/36 guarded holdouts passed |
| Candidate-specific 3,600-second native soaks | NOT RUN / NOT PROVIDED |
| Candidate-specific P19 guards, 36-case holdouts | NOT RUN / NOT PROVIDED |
| Candidate-specific five-tier ISA, production native performance, actual external material | NOT RUN / NOT PROVIDED |
| Complete historical P15 proving campaign on omitted source files | NOT RUN; cannot responsibly certify against this reduced working set |

The primary reconstructed low-band comparison is independently confirmed under **the paper's stated analysis method**. Example sine-equivalent residual levels (dBFS, more negative = less level):

| Bank | 0–40 kHz | 40–100 kHz | 100–150 kHz |
|---|---:|---:|---:|
| CLANS-7 | -203.53 | -182.03 | -143.72 |
| CLANS-8 | -237.53 | -212.73 | -168.88 |
| SDM-8 | -243.92 | -226.21 | -181.71 |
| SDM-8 ×2 resonators | -229.65 | -226.01 | -193.34 |

These values support a real low-reconstructed-band distinction. They do not prove native nonlinear behavior for omitted inputs, whole-DSD-spectrum superiority, or analog-DAC preference.

## 3. Itemized demonstrated defects

### F-01 — HIGH — Missing normal full-scale stress inputs invalidate the stability-gated shortlist

**Classification:** Demonstrated screening/design failure, not a production regression.  
**Location:** `tests/dsd/ntf_dsd1024/study.py:169-203` (stimulus definitions), `:391-457` (screen and advancement rule); `verify_evidence.py:19-22,118-147` (mandated screens and published 23 design-selection consistency); `REPORT_2026-10-23.md` (candidate investigation recommendation).

**Trigger:** The four official screens use a tapered 997-Hz tone with 0.95 peak, noise bounded to ±0.4, a DC step bounded to ±0.7, and silence. The study does not run the P19-style +1.0 DC, -1.0 DC, or full-scale (0 dBFS) 997-Hz stimuli before ranking. Independently regenerated P10 corpus holdouts were rendered at 176,400 source Hz to 45,158,400 native Hz, scalar, reference scale 0.5, with the same scratch native test binary. The untouched CLANS-7 incumbent was the control.

**Observed results (all are native nonlinear results, not threshold opinions):**

| Candidate | +1.0 DC | -1.0 DC | 0 dBFS 997 Hz |
|---|---|---|---|
| CLANS-7 incumbent | PASS | PASS | PASS |
| CLANS-8 | **NONFINITE** | **NONFINITE** | **NONFINITE** |
| SDM-8 | **NONFINITE** | **NONFINITE** | PASS |
| SDM-8, resonators ×2 | PASS | PASS | PASS |
| Transferred DSD512 `g3p0` | **NONFINITE** | **NONFINITE** | **NONFINITE** |

For +1.0 DC the first stopped/native nonfinite frames are CLANS-8 **15,485,608** (~0.3430 s), SDM-8 **33,108,316** (~0.7332 s), and `g3p0` **9,972,463** (~0.2208 s). Each failed with nonzero native return code, failure status 3, recorded nonfinite state, and large 28-bit excursion counts. Both polarities produce the same failure frames for these cases. The CLANS-7 and SDM-8 ×2 controls complete 72,253,440 frames per case with no nonfinite or 28-bit excursion. A separate amplitude sweep found SDM-8 passes 0.95-peak DC but fails 0.99-peak DC, so this is not confined to a mathematical singularity at exactly ±1.

**Complete independent 55-design battery:** +1 DC: 37 pass, 18 nonfinite; -1 DC: 37 pass, 18 nonfinite; full-scale 997 Hz: 40 pass, 15 nonfinite. **36/55 pass all three. Of the original 23 research shortlist winners, 15 fail one or more; only eight pass all.** Those eight are `d512-r5-a20`, `d512-r5-a20-g0p25`, `d512-r5-a20-g0p5`, `d512-r8-a20`, `d512-r8-a20-g0p25`, `d512-r8-a20-g0p5`, `sdm-8-g0p25`, and `sdm-8-g2p0`.

**Consequence:** “220/220 screened” is arithmetically true but misleading if used as evidence that stability reasonably gates candidate fidelity. The primary SDM-8 and CLANS-8 recommendation should not advance on the current screen. These tests exercise **unbounded experimental recurrence**, so they are not claims that a production-guarded SDM-8 profile exists or that current production CLANS-7 has regressed. The brief explicitly highlighted near-full-scale nonlinear divergence even when linearized metrics appeared healthy, making omission especially material.

**Recommended correction (implementing session):** Add both polarities of full-scale P19 DC, zero-dBFS tonal, near-fullscale intermediate levels, and suitably extended high-energy programme-like cases to the mandatory per-candidate native gate; treat any nonfinite/28-excursion/overload as a hard rejection before spectral ranking. Rebuild the shortlist and reconsider whether unscaled SDM-8 or CLANS-8 belongs in any finalist track. Only after this prequalification should independent candidate-specific P19, long soaks and cross-ISA qualification begin.

### F-02 — MEDIUM — Incorrect final-holdout spectral replay window causes a 189-dB false discrepancy

**Classification:** Demonstrated documentation/reproducibility defect; archived original holdout numbers appear correct.  
**Location:** `tests/dsd/ntf_dsd1024/REPLAY.md:78-84`, `study.py:169-188`, `study.py:341-388`; archived `evidence/holdout-spectra/tone-20k/*.json` and `tone-40k/*.json`.

**Trigger:** REPLAY instructs a 20-kHz/40-kHz tone with `--window-start .4 --window-stop 1.2`, but those sources are only 1.2 seconds long and have a 25-ms end taper. All ten archived tonal holdout spectrum receipts instead use **0.25–0.95 seconds**, a plateau without the taper. The analysis regression fits a constant-amplitude sinusoid; including the end taper leaves legitimate source energy in the alleged residual.

**Independent measured consequence:** Rerendered SDM-8's 20-kHz packed input matched its archived SHA-256. The correct archived interval 0.25–0.95 yields **-236.0423466 dBFS** for 0–40 kHz. Following the documented 0.4–1.2 interval on the *same identical bitstream* yields **-46.8059533 dBFS**, an apparent increase of **189.2364 dB**. The error is an invalid source-fitting window, not lost NTF performance; the archived 0.25–0.95 figure reproduced correctly.

**Recommended correction:** Align replay instructions and explicit `spectrum` invocations with the archived holdout-specific 0.25–0.95 analysis interval. Ensure future spectral windows are completely inside the steady-state portion of each source, and test reproduction of their actual record fields and values.

### F-03 — MEDIUM — Evidence verifier does not validate spectral analysis parameters or numerical values

**Classification:** Demonstrated verifier coverage gap; not proof that the shipped original records are fraudulent.  
**Location:** `tests/dsd/ntf_dsd1024/verify_evidence.py:61-76`, `:129-155`. Contrast with the numerical `study.py:341-369` spectral method.

**Trigger:** `verified_spectrum()` checks structural identity, render bitstream hash, `last_fir_taps`, and existence/finiteness of integrated bands, but **does not check** the analysis `fit_tone_hz`, `start_s`, `stop_s`, source taper constraints, `last_fir_beta`, `halfband_taps`, or any independently recomputed band values. Thus the verifier can confirm an internally consistent *record identity* but cannot detect the replay-window error described in F-02 or a materially miscomputed spectral value.

**Independent challenge:** In a disposable copy of a genuine, hash-matched SDM-8 holdout record, I replaced the analysis window with 0.4–1.2 and the low band with the independently measured erroneous **-46.8059533 dBFS**. Direct invocation of `verified_spectrum()` **accepted it**. The full study-level SHA256 manifest would detect mutation of the delivered original file, so this is a *semantic verifier gap*, not a failure of outer tamper detection. All 55 actual primary spectra were separately recomputed in this audit and matched.

**Recommended correction:** Bind expected per-stimulus tone frequency, steady-state window, filter parameters and analysis source digest in the verifier, and where practical independently reconstruct numeric metrics from regenerated packed bits (or preserve externally generated independent check vectors). Clearly separate cryptographic record integrity from numerical correctness.

### F-04 — MEDIUM — Shaper selection omits a demonstrated native ultrasonic-power tradeoff

**Classification:** Demonstrated evaluation omission and spectral trend; impact on an actual DAC is an **unverified risk**, not a demonstrated audible defect.  
**Location:** `tests/dsd/ntf_dsd1024/study.py:341-369` reconstructs only to 352.8 kHz; `study.py:434-456` applies selection solely to 0–40, 40–100 and 100–150 kHz; `REPORT_2026-10-23.md`, `Decision and next qualification gates` recommends SDM-8 investigation.

**Trigger/method:** The final decision-band analysis stops at 150 kHz. I independently decoded the **same bit-exact raw native DSD bitstreams** to ±1 and measured integrated native-bitstream power with power-normalized Hann-window Welch PSD, 65,536-point FFT, nonoverlapping segments in the 0.4–0.8-s primary plateau at 45,158,400 samples/s. This PSD is a different absolute reference from the source-fitted reconstructed sine-equivalent residual; compare **candidate-to-control differences only within this PSD method**.

| Candidate | Raw 0.5–1 MHz power (dB) | Raw 1–2 MHz power (dB) |
|---|---:|---:|
| CLANS-7 | -51.65 | -34.48 |
| CLANS-8 | -54.90 | -33.32 |
| SDM-8 | -36.71 | -24.01 |
| SDM-8 resonators ×2 | -36.69 | -23.87 |

SDM-8 places **14.94 dB** more raw 0.5–1-MHz power and **10.47 dB** more 1–2-MHz power than CLANS-7, despite its much lower reconstructed noise below 150 kHz. The ×2 variant behaves similarly. The broad trend was also seen on independently screened high-peak tone, noise and silence. No specific DAC, analog filter or system transfer function has been characterized, so audible impact, converter headroom, EMI, or intermodulation cannot responsibly be asserted from these numbers alone.

**Consequence:** The published spectral differences below 150 kHz are real but insufficient to establish whole-chain superiority of either SDM-8 variant. A candidate can move shaped energy into regions not captured by the chosen objective, with hardware-dependent consequences. The delivered report explicitly admits its 100–150-kHz band is noise-only; the omission is evaluation scope, not a falsification of its reported low-band numbers.

**Recommended correction:** Before selecting a final shaper, report the native-spectrum noise and tonal-spur distribution in relevant higher bands; define analog/DSD playback filter and converter constraints (or multiple representative transfer functions); assess wideband load/intermodulation with qualified hardware or justified models. Keep native higher-band objectives distinct from the 176.4-kHz source-fidelity objective.

## 4. Risks and unverified matters, not demonstrated defects

- **Candidate-specific qualification (high consequence, appropriately disclosed):** No challenger has full 3,600-second uninterrupted candidate-specific soak, frozen guard calibration, independent 36-case holdouts, cross-ISA five-tier bitstream qualification, or external-media playback/read qualification. Fullscale F-01 should be corrected *before* spending time on these gates. These missing gates were already disclosed, so they are not counted again as an R1 misrepresentation.
- **Performance is not established:** The 32-s research render workloads used a private scalar training kernel and varied strongly in elapsed times due to system contention. The independent 32-s replay had CPU times approximately **59–63 s** per candidate, so it does not prove real-time performance at the native clock. This is not a production benchmark nor an acceptable basis for implementation-performance preference; the original report explicitly defers native performance qualification.
- **Cross-environment reproducibility:** `study.py:56-60` requires exact JSON equality for source-derived `linearized_ntf` floating values. `model.py` derives those using floating eigensolvers/linear-algebra operations. Cross-BLAS and cross-Python numerical variation could cause a harmless mismatch and prevent a fresh replay. No cross-platform failure was observed; this is a portability risk and an opportunity to distinguish authoritative exact coefficient identity from descriptive rounded linear metrics.
- **Scratch isolation guard:** `study.py:63-73` refuses instrumentation of the source tree or a parent but does not reject a manually pre-created marked scratch *descendant* of the source tree; `prepare()` correctly does reject descendants at `:76-85`. A maliciously/mistakenly constructed in-tree scratch clone could pass the narrower instrument guard. No such production modification was observed; harden the secondary guard if isolation from the entire authority tree is mandatory.
- **Native-bitstream raw outputs omitted by design:** The large streams are not packaged. This limits offline-only auditing, but the hashes and exact replay procedure are sufficient for external recomputation, and this audit actually reconstructed **all 275** short/primary outputs and **all five** 32-s outputs exactly. Omission was disclosed and is not a defect by itself.
- **Preexisting P20 manifest mismatch:** The original baseline already has one mismatch in `P20_RESIDUAL_ASYMMETRY_SHA256SUMS.txt`, for `tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/README.md` (expected prefix `4e73674f`, archived SHA prefix `5f5d9a8e`). The new study neither caused nor concealed it. The independent `P20_BUNDLE_SHA256SUMS.txt` fully passes. Do not fabricate evidence or change the baseline to make this appear green.
- **Source rate/media scope:** All signal testing uses 176.4-kHz binary64 input; above its 88.2-kHz Nyquist the 100–150-kHz reconstructed band is shaped-noise characterization, not proof of actual source-content fidelity. The research correctly warns of this. It also correctly refuses self-generated DSD1024 media as **independent read qualification**.

## 5. Resumption, idempotency and evidentiary workflow

- `CHECKPOINT.json` identifies input/source SHA-256, model and receipt counts, pending gates, decisions and replay entry points. That is sufficient to resume an exploratory audit without guessing prior work.
- `REPLAY.md` contains an end-to-end scratch build and regeneration procedure, including non-production registry instrumentation, published receipt identity and failure-closed replays. **F-02 must be corrected** before it can be described as a complete exact tonal-holdout replay recipe.
- `study.py:218-303` uses hash-bound source/binary identities and immutable receipt publication, checks replayed bitstream SHA-256 and native monitor fields, and refuses conflicting or unreceipted artifacts. These are good controls. Removing a packed stream and replaying under different binaries properly refuses reuse. A crash between packed-link and receipt publication fails closed instead of silently replacing evidence; conservative manual intervention is intentional.
- `requalify.py` closes the brief's former P19 host requalification problem in a **private source clone**. The independent 17-case training, eight exact maxima/bounds, rebuild and 36-case holdout replay succeeded without changing the baseline frozen proof.
- The full set of original source files remains bit-identical after the audit. All corrective actions belong to the implementing session, not this report.

## 6. Brief-by-brief adjudication

| Substantive brief objective | Finding |
|---|---|
| Cover all ten production CLANS/SDM orders | PASS |
| Seed from original DSD512 `o7-r8-a20` redesign and related candidates | PASS |
| CLANS-7 frozen incumbent/control, not a presumptive ideal | PASS |
| Native nonlinear testing before fidelity selection | **FAIL for adequately covering ordinary full-scale stress**, despite correct sequencing of the chosen four tests |
| Clearly identify source bandwidth and target spectral bands | PASS disclosure; **CONDITIONAL** completeness due native-power tradeoff F-04 |
| Define what makes CLANS-7 win | PASS; release/qualification gates clearly stated |
| Decide self-generated DSD1024 read media eligibility | PASS; explicitly inadmissible as independent qualification |
| Select DSD1024 independently rather than mirroring DSD512 | PASS decision principle; candidate recommendation needs rescreen |
| Close host P19 requalification/re-freeze workflow gap | PASS; independently reproduced all 17+36 cases |
| Preserve all production source, credentials/authority, historical evidence | PASS |
| Avoid claiming missing P15 validators passed | PASS; properly NOT RUN |
| Persist coherent test/results checkpoints and source identities | PASS with F-02/F-03 verifier/replay deficiencies |
| Supply supported numerical advantages over incumbent | PASS for stated 0–150-kHz metric; NOT an end-to-end quality proof |

## 7. Recommended handoff order (no patches included)

1. **Block candidate advancement on F-01.** Add full-scale plus near-fullscale P19-derived sources as mandatory native screens. Re-run all 55; reconstruct the research selection from candidates that pass. Keep omitted-input failure receipts as permanent regression evidence.
2. Repair the replay specification **F-02** and strengthen parameter/numeric checks **F-03**; rerun tonal holdout verification without changing or rewriting historical original results.
3. Add objective/reconstruction tradeoff analysis **F-04** before calling any shaper the best choice for downstream hardware; explicitly define which native ultrasonic bands and physical constraints count.
4. Only then carry the survivors to candidate-specific guard/freeze, 36 holdouts, one-hour native soak, five-tier ISA, throughput/latency and qualified independent programme material. **Do not change the production CLANS-7 default, guards, coefficients or waiver on the basis of these research spectra.**

## Final decision

**REJECT — narrow but material correction required to the experimental stability screen, shortlist and candidate-advancement recommendation.** The scientific low-band measurements, source preservation, archive integrity, reproducible native bitstreams, independent incumbent requalification, and explicit limitations are credible. Nevertheless, the current advancement recommendation fails the brief's stability-first premise because its preferred unscaled SDM-8 and independent CLANS-8 challengers exhibit reproducible nonfinite states under omitted, ordinary full-scale input. The candidate recommendation is **not ready for the next qualification phase as delivered**. Retain the existing CLANS-7 production choice unchanged; none of the supplementary passing candidates is thereby certified.
