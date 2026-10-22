# Resume P20/P19 residual-asymmetry diagnosis — 2026-10-22

**Status: question answered; code and the frozen qualification state remain unchanged.** See `docs/dsd/handoffs/P20_RESIDUAL_ASYMMETRY_ADJUDICATION_2026-10-22.md` for the full numerical evidence and direct answers.

- Baseline: source-only working set labeled `75f8e8c3`, supplied as `sox_dsd-75f8e8c3-working-set.tar.zst`, SHA-256 `9cc1b8e058bbee966c9a527f35a447b399d643292d226eaecbffe2bcb92f4345`. No upstream `.git` objects were available; do not mint a synthetic upstream Git commit.
- No production C files, SDM coefficients, P00 index, P15 historic receipt, P17 registry, P18 capability, frozen P19/P20 receipt or waiver was changed. Only an additive Python diagnostic, four small tests, the original question, an adjudication report and new experimental evidence/checkpoints are delivered.
- All 66 included operator state digests check out. The documented 81,285,120,000-frame P20 nominal soak remains a passed input-program gate; do not rerun it to answer the audio asymmetry question.
- Both unmodified P19/P20 audio scripts were replayed successfully: all four regenerated bitstreams were SHA-256-identical to their frozen receipts.
- `tests/dsd/diagnose_residual_asymmetry.py` also uses exactly the frozen prequantization PCM waveform for the F64 control (the control rounds to the original 32-bit input). Main results: DSD512 seventh-vs-eighth +40.9873 dB, DSD1024 +37.4675 dB under F64 control, explaining the historical +37.1008 / +3.6725 dB mismatch. -163.04 dBFS was not an optimization target.
- Build and tests independently reproduced: `make` PASS, `make check` PASS, P10 unit 105,489/0, P17 unit 32,859/0, P18 native 398/0, and 4 diagnostic unit tests PASS. P19/P20 certificate checks PASS and still experimental/unqualified.
- The diagnostic record is at `tests/dsd/results/P20_RESIDUAL_ASYMMETRY_2026-10-22/analysis.json`. Verify original files with `sha256sum -c --quiet P20_BUNDLE_SHA256SUMS.txt` and additive file digests with `sha256sum -c --quiet P20_RESIDUAL_ASYMMETRY_SHA256SUMS.txt` from the source root.
- For further research, use new receipt paths. Avoid regenerating missing P15 historical records, touching the P00 index, or authorizing disabled capabilities. Any independent audio/quality qualification is a separate project with its own acceptance criteria.
