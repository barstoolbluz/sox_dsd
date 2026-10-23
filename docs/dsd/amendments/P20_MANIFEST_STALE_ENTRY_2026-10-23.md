# P20 residual-asymmetry manifest: one stale entry, disclosed not repaired

`P20_RESIDUAL_ASYMMETRY_SHA256SUMS.txt` has 98 entries. Ninety-seven verify.
One does not:

    tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/README.md
      manifest records 4e73674fb8daf708bf8a6c391f7bcd58bc49b444a8336a58da27631a51f3b0e1
      tree contains   5f5d9a8e9df6d2e8035b006d96535165d61e6768bd264b6a1b00b5eb69c8a790

## Why

Ours, and not a delivery defect. The chronology:

  75f8e8c3b  2026-10-22 01:52  the README is written
  bd63bbe10  2026-10-22 12:09  we rewrite it, correcting the residual-asymmetry
                               finding that a quantized stimulus had produced
  d9876366c  2026-10-22 14:12  we integrate a manifest that hashed the README
                               as it stood before 12:09

The manifest was generated against the copy of the README we had already
shipped, so it was mismatched at birth: at d9876366c the file on disk
already hashed to 5f5d9a8e. We integrated it without re-checking it against
the corrected tree.

## Disposition

The README content is correct; the manifest entry is stale. We are not
editing either. Rewriting the delivered manifest to match would make a
record of what we measured agree with itself by assertion, and the
manifest's remaining 97 entries are the reason to leave it alone.

Treat this single entry as expected-to-fail. Anyone running
`sha256sum -c P20_RESIDUAL_ASYMMETRY_SHA256SUMS.txt` should see exactly one
FAILED line, naming that README, and nothing else.

This is unrelated to the DSD1024 NTF study, which flagged it independently
and correctly declined to touch it.
