# P15 final original-prover audit: execution QA

Date: 2026-10-19. Original SHA-256: `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

Performed independently against the supplied source and cumulative R9 add-on:

1. Source archive SHA-256 matched; cumulative add-on checksum table 145/145 PASS.
2. Original `p15_full_band_campaign.py --summary-only`: 11,516/11,516, 72 cells, no OPEN/missing, still `COMPLETE_COVERAGE_CANDIDATE_UNADJUDICATED`.
3. Preexisting targeted suite `test_p15_r9_uniform_math test_p15_r9_strong test_p15_src_bound_operator test_p15_src_complete_aliases test_p15_src_continuum_bounds`: 41 tests, OK, 2 skipped.
4. New `test_p15_final_prover_audit`: 17 tests, OK, 0 skipped.
5. New `p15_final_receipt_adjudicator.py`: all 11,516 receipts byte-identical to verified original archive, one method label, all recorded bounds strictly meet stated limits, 2,850 pass and 8,666 stop.
6. Fresh `p15_r9_src_strong.py --prove-all`: exit 0, native PASS, eight cells/958 jobs; 179 native leaves and 165+66+99 strengthened SRC-stage leaves recomputed, exact replay JSON SHA-256 `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`.
7. No source compilation, production C source edits, 11,516-certificate campaign rerun, or release-execution FFT4G qualification performed.

Independent report and executive decision: `P15_FINAL_ORIGINAL_PROVER_SOURCE_AUDIT_2026-10-19.md` and `P15_FINAL_SPECTRAL_ACCEPTANCE_DECISION_2026-10-19.md`. The audit isolates an original historical *reader* integrity weakness but makes no claim that the original *mathematical prover* emitted a numeric false PASS.

The new `FINAL_HISTORICAL_RECEIPTS.json` proves archive/receipt correspondence and reported-bound consistency, **not** independent recomputation of every stored mathematical interval. The R9 replay remains separately qualified within its explicitly limited source-stop scope.
