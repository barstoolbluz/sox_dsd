# P15 final spectral assurance decision

**19 October 2026. Original source:** SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Verdict

**Original spectral prover:** No demonstrated mathematical false-PASS defect after adversarial source review of interval arithmetic, branch completeness, composite magnitude recurrences, pruning and caching. There is a reproducible receipt-reader integrity-check omission, for which a read-only independent checker is included; the original immutable evidence passes that stronger checker.

**Historical campaign:** all 11,516 canonical receipts, spanning 72 SRC-active cells, are byte-identical to the SHA-verified original archive. All 2,850 passband and 8,666 source-stop receipts report strict compliance with the original thresholds. Reported PASS results were not individually independently recomputed.

**Independent math:** 1,023 distinct canonical intervals qualified by R6-R9 without double counting. R9's complete, source-bound exact source-stop proof for eight DSD256-v2 cells (958 jobs) replayed independently, byte-identically to earlier QA, SHA-256 `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`.

**Mathematical proof gate:** **CONDITIONAL.** The original `mpmath.iv` transcendental interval padding/argument-reduction implementation was inspected but not proved universally outward for all historical anchors; full historical proof-runtime correspondence is not retained. These are explicit assumptions, not counterexamples.

**Engineering spectral acceptance:** **YES, conditionally on accepting the source-audited `mpmath.iv` directed interval backend as a numerical trusted base and the historical method/source correspondence documented in the archive.** This is a defensible, nonformal engineering assurance standard; it is not blanket formal proof.

**Remaining spectral proof campaigns:** **NOT RECOMMENDED.** Another large certificate-generation effort is not technically justified by a demonstrated defect. Reopen only on an actual counterexample, newly changed operator, substantive backend defect, or an explicit decision that a stricter proof tier is required.

**Full P15 release:** **NOT AUTHORISED by this decision.** The independent final-binary arbitrary-input FFT4G/same-operator execution-roundoff and other P15 release checks remain separate gates under `DSD_DESIGN.md` section 8.6.1.

## Artifacts and commands

This additive overlay introduces only a source-audit report, this decision, an independent read-only receipt adjudicator, 17 targeted regression tests, and supporting receipts. No original C or original historical evidence is replaced.

From an original cc399928 archive with the R9 cumulative addon and this audit overlay unpacked, run:

```sh
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_final_prover_audit
PYTHONPATH=tests/dsd python3 tests/dsd/p15_final_receipt_adjudicator.py \
  --receipts tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/receipts \
  --source-archive /path/to/sox_ng-P15-adjudicate-cc399928.tar.gz
```

The exact source citations, mathematical recurrence, backend limitations, evidence reconciliation and test coverage are in `P15_FINAL_ORIGINAL_PROVER_SOURCE_AUDIT_2026-10-19.md`.
