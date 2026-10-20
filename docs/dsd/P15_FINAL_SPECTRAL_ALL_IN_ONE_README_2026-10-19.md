# SoX-NG P15 — spectral engineering final accepted overlay

**Decision date (New York): 2026-10-19.** This archive is the cumulative R6–R9 exact-proof overlay **plus** the independent final original-prover audit, checker/tests, acceptance-method decision, and final handoff. The immutable source snapshot remains a separate archive.

## Input identities

| Artifact | SHA-256 |
| --- | --- |
| Original `sox_ng-P15-adjudicate-cc399928.tar.gz` | `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210` |
| R6–R9 exact-proof add-on included here | Original distributed archive: `0c779366a483d9336b1f3e43e95dcae37ea73a64ddc08903a892ce89b77871a4` |
| Original-prover audit add-on included here | Original distributed archive: `962c34370fe44719dd55cc3a5b4e1bb6e83957d61b8b064d4f56a61be5ea7146` |

The integrated add-on is **additive** to the original source tree: no original source file, mathematical receipt, production DSP file, or existing design document is overwritten. Numeric limits are unchanged. All its files are covered by one integrated checksum manifest.

## Apply and verify (from the folder containing both archives)

```sh
sha256sum sox_ng-P15-adjudicate-cc399928.tar.gz
mkdir -p verify_p15_spectral_final
tar -xzf sox_ng-P15-adjudicate-cc399928.tar.gz -C verify_p15_spectral_final
tar -xzf P15_SPECTRAL_ENGINEERING_ALL_IN_ONE_ADDON_2026-10-19.tar.gz -C verify_p15_spectral_final
(
  cd verify_p15_spectral_final
  sha256sum -c sox_ng/docs/dsd/P15_ALL_IN_ONE_ADDON_SHA256SUMS_2026-10-19.txt
)
```

**Note:** Confirm the initial original source SHA matches the value above; `sha256sum` printing a hash alone is not a comparison. Run checks from the extraction root so all manifest paths resolve. The add-on is well below 140 MB.

## The decision and its limits

Read `sox_ng/docs/dsd/amendments/P15_SPECTRAL_ENGINEERING_ASSURANCE_ACCEPTANCE_2026-10-19.md` and `sox_ng/docs/dsd/P15_FINAL_SPECTRAL_ENGINEERING_HANDOFF_2026-10-19.md`.

- **Engineering spectral acceptance: recorded, scoped, complete for this unchanged source.** No new full-band re-proving is justified absent a specific reopen trigger.
- **Unconditional formal mathematical proof: CONDITIONAL**, with explicit mpmath transcendentals and historical execution identity assumptions.
- **Full P15 release: OPEN**, pending distinct FFT4G/same-operator execution and release-binary checks. Do not infer any release approval.

The full final source audit, old and new tests, R6–R9 proof evidence, replay outputs, historical receipt consistency checker and machine-readable acceptance record are all part of this overlay. The large original historical receipt population remains in the immutable source archive.
