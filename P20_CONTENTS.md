# DSD512 P20 candidate working-set bundle

- **Main handoff:** `docs/dsd/handoffs/P20_DSD512_V2_CORRECTION_2026-10-22.md`
- **Resumable checkpoint:** `docs/dsd/handoffs/P20_DSD512_V2_RESUME_2026-10-22.md` and `P20_CHECKPOINT.json`
- **Machine-checkable candidate digest:** `tests/dsd/reference/p20_dsd512_v2_certificate.json`, verified by `python3 tests/dsd/generate_p20_candidate_certificate.py --check`
- **Evidence:** `tests/dsd/results/P20_DSD512_CORRECTION/` (frozen training/holdout, original training-runner source, binary snapshots, 25 ISA results, independent bit oracle, 300-second smoke snapshots, audio comparison, regression logs)
- **Source:** separate P20 DSD512 v2 candidate headers, opt-in profile and private tests. P17 and P19 definitions retained, P18 capabilities disabled.
- **Integrity:** run `sha256sum -c P20_BUNDLE_SHA256SUMS.txt` from this directory. The manifest intentionally excludes itself.

This bundle is **not a DSD512 release or high-rate capability activation**. A corrected v2 one-hour soak and independent audio assessment remain outstanding. Upstream Git history is not included in the original supplied working set; the baseline import Git commit generated for development must not be mistaken for upstream revision `699e4363`.
