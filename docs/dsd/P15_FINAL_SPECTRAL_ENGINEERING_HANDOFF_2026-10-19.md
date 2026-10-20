# P15 spectral engineering: final closeout and no-recampaign handoff

**Local decision date:** 2026-10-19. **Status:** Spectral ENGINEERING ACCEPTANCE RECORDED, at the scoped source-audited computational-interval tier; global unconditional mathematical theorem **CONDITIONAL**; full P15 release **OPEN**.

## The decision you should implement

**Stop generating new full-band spectral certificates for the original `cc399928` operator.** Treat the initial 11,516 original PASS receipts as accepted *engineering spectral evidence* only in combination with the source-level adversarial audit, independent original-archive receipt checker, and R6–R9 exact-arithmetic corroboration. Never call the 11,516 independently recalculated or the universal mpmath transcendental theorem closed. Preserve the original artifact identities and historical status labels. Make no numerical-tolerance or production DSP changes.

The authoritative scoped acceptance-method ruling is in `docs/dsd/amendments/P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md`. Read it with `docs/dsd/DSD_DESIGN.md` §8.6.1 and `docs/dsd/P15_FINAL_ORIGINAL_PROVER_SOURCE_AUDIT_2026-10-19.md`.

## Anchored identities

- Original source archive: `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.
- R6–R9 cumulative exact-proof archive: `0c779366a483d9336b1f3e43e95dcae37ea73a64ddc08903a892ce89b77871a4`.
- Previous original-prover audit add-on: `962c34370fe44719dd55cc3a5b4e1bb6e83957d61b8b064d4f56a61be5ea7146`.
- Source design (§8.6.1): `458537dbe9a2ea1e687b68f998f43a90de10c369b604f809c78cf80c2389b94b`.
- Historical receipt inventory: `b72841ffb59e5016e12db4360458895223f454271e9d4504e74aa6ee39d34e99`.
- R9 independent proof JSON: `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`.

## Verified short reproduction

Work from a clean extraction of the original source plus the cumulative R9 overlay and the final combined audit/decision overlay. Commands below assume repo root is `sox_ng/`, original archive path is accessible, and Python's listed dependencies are installed.

```sh
# From the directory containing sox_ng/ and the final overlay manifest:
sha256sum -c sox_ng/docs/dsd/P15_SPECTRAL_ENGINEERING_CLOSEOUT_SHA256SUMS_2026-10-19.txt
cd sox_ng

# IMPORTANT: --output is the receipt directory, NOT its parent.
PYTHONPATH=tests/dsd python3 tests/dsd/p15_full_band_campaign.py \
  --output tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/receipts --summary-only

PYTHONPATH=tests/dsd python3 tests/dsd/p15_final_receipt_adjudicator.py \
  --receipts tests/dsd/results/P15_full_band_campaign_certified_2026-10-18/receipts \
  --source-archive /path/to/sox_ng-P15-adjudicate-cc399928.tar.gz

PYTHONPATH=tests/dsd python3 -m unittest -q \
  test_p15_final_prover_audit test_p15_r9_uniform_math test_p15_r9_strong \
  test_p15_src_bound_operator test_p15_src_complete_aliases test_p15_src_continuum_bounds
```

Expected campaign status is `COMPLETE_COVERAGE_CANDIDATE_UNADJUDICATED`, NOT `qualified_release: true`. Expected receipt count is 11,516, with 2,850 PASS band + 8,666 PASS stop. Expected audit JSON has `qualified_mathematical_proof: false` and `qualified_release: false`, intentionally. Test expectation: 58 total, two permitted skips, zero failures. R9 independent full proof result was already replayed to SHA-256 `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`; no need to repeat it solely to raise the count.

**Do not accidentally declare failure by passing the parent folder** `.../P15_full_band_campaign_certified_2026-10-18` to the campaign's `--output`: the driver expects to find individual JSON receipts directly there and will report all as missing otherwise. The independent reader and previous audit work were run on the correct receipts folder.

## Work not permitted to be marked complete by this artifact

- Actual release binary's arbitrary-input `src/fft4g.c` execution roundoff, FFT coefficient twiddles, denormal and edge conditions.
- Independent finite **same-operator** arithmetic bound and source/binary/ELF identity required by §8.6.1.
- Physical/binary provenance and any other release gate that still has an explicit unclosed condition.

These items are outside the original-prover spectral mathematical assurance decision. **Do not assign them PASS** or infer v2 default promotion from this handoff.

## What changes with this handoff

Only the assurance-method classification changes at the engineering review layer: the completed spectral certificates now have an explicit accepted trusted-base/provenance risk tier and a no-recampaign stop-work ruling. Existing proofs, C code, receipts, and normative numerical thresholds remain byte-identical.

This is a terminal **spectral engineering** handoff: no next spectral proof assignment is requested, barring one of the specific reopen triggers in the ratification document.
