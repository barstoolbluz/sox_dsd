# P15 scoped engineering spectral closeout: final QA evidence

Date (America/New_York): 2026-10-19.

## Independently rechecked in the final decision session

1. `sha256sum` of the original 368-MB source archive: **MATCH** `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.
2. Prior original-prover audit overlay: **8 of 8 SHA-256 manifest entries verified**.
3. R9 exact-proof cumulative overlay: prior **145/145** entries verified (spot-checked in this session; all entries are retained unchanged).
4. `test_p15_final_prover_audit`: **17 tests PASS**.
5. Five original/R9 source and mathematical test modules: **41 tests, 2 skipped, zero failures**.
6. `p15_final_receipt_adjudicator.py`, pointed at original archive + actual receipts folder: **11,516** byte-identical original receipts, **2,850** passband + **8,666** source-stop in-range PASS reports, original receipt inventory digest `b72841ffb59e5016e12db4360458895223f454271e9d4504e74aa6ee39d34e99`.
7. Original campaign's `--summary-only`, with `--output` aimed at its `receipts/` directory: `local_intervals_proven=11516`, `missing_receipts=0`, `mathematical_intervals_open=0`, `status=COMPLETE_COVERAGE_CANDIDATE_UNADJUDICATED`, `qualified_release=false`.
8. Existing fresh independent R9 full replay JSON SHA: **MATCH** `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`; the original proof-computation replay was completed in the source audit session and its output is included in the prior audit overlay. It was not needlessly repeated in this ratification session.
9. Numerical §8.6.1 thresholds and design hash: confirmed unchanged: **0.0001 dB**, **-160 dB**, `458537dbe9a2ea1e687b68f998f43a90de10c369b604f809c78cf80c2389b94b`.

## Interpretations that are expressly prohibited

- The original campaign summary's `COMPLETE_COVERAGE_CANDIDATE_UNADJUDICATED` **does not alone** prove every reported value mathematically correct. The chosen engineering tier adds a justified source audit and independent exact corroboration.
- 1,023 distinct independently qualified R6–R9 jobs **are not** 11,516 independent recalculations.
- The R9 native continuum source-stop theorem **does not** independently qualify other profiles' passband jobs.
- The engineering spectral closeout does not constitute an unconditional mathematical theorem or a final release decision.
- The old receipt reader's acceptance of a forged over-limit PASS label is an evidence-reader validation defect, not a reproduced spectral-numerical false PASS; the independent read-only checker refuses the forgery and audits the real receipts.

## Final reviewer determination

**Accept at the documented engineering trusted-base tier; stop extending the spectral proof campaign.** Preserve the CONDITIONAL universal-mathematical classification and OPEN P15 release gate as distinct, explicit statuses.

No production source changes. No new proof campaign. No numerical limit changes. No unsupported promise of final-release readiness.
