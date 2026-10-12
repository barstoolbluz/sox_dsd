# P13 source-identity reconciliation: CLOSED

**Completed:** 2026-10-12. **Conclusion:** P13 was correctly implemented against an effectively identical source tree. The source-provenance defect is closed without modifying the accepted P13 kernels, dispatcher, arithmetic, build configuration, tests or performance policy.

## Verified archives

- **Specified original:** `sox_ng-P13-20059dbf.tar.gz`, SHA-256 `81c9aa9a98f6e8800af77055e00ea354fd4ffb6ad9bce6f02e0720fb9a879aa1`. Verified against the assignment.
- **Recovered predecessor used initially:** `sox_ng-P12canary-corrected-2026-10-11.tar.gz`, SHA-256 `48324520a7a121b91f9dd954d3fe894c3fe1c5e002ff2b000b83c1c3a7c40642`. Verified.
- **Accepted P13 delivery:** `sox_ng-P13-implementation-2026-10-11.tar.gz`, SHA-256 `b7fed2e88ceae9d1db686105fab1d4f8a088a362c4fd54f1f99048dd29b72708`. Verified.
- **Previously extracted P13 source delta:** `sox_ng-P13-source-delta-from-recovered-P12canary-2026-10-12.patch`, SHA-256 `a8b0bf6e490220d7c62a0cb604c5e487fd6238522c8547ee778dd8c0d9507493`. Verified.

## Complete predecessor comparison

Every regular file was compared by relative path and SHA-256. Tar/gzip packaging metadata was ignored. The specified original has **3,829 files**; the recovered predecessor has **3,827 files**. **3,826 shared files are byte-identical**, with no differences in any runtime code, build input, test source, test fixture, SOW, design document, implementation plan, or P00–P12 handoff. There are no symlinks.

The only content exceptions are:

1. **Different historical P00 hash list:** `tests/dsd/results/P00/P00_SHA256SUMS.txt`. Original SHA-256: `10d0cd27c048bcea68432b0c11283857e2a92aff9c17877b3830e0f805e59a94`. Recovered SHA-256: `b432e0f1aa027d73ab7484685b01c90dce84b32cfebc774d1516dbcb592cf12b`. Some historical hash-list entries differ for `src/effects.c`, `docs/dsd/OPTIMIZATION_BACKLOG.md`, `docs/dsd/handoffs/P12_CANARY.md` and P12 results, but the **referenced actual source and documentation files are byte-identical**.
2. **Original-only canary evidence:** `tests/dsd/results/P12_canary_fix_prepared_host_2026-10-11/README.md`, SHA-256 `a540edacb936dc182f16abb2f497f3c42b16e51f704867b2716b2b24507da3d6`.
3. **Original-only canary evidence:** `tests/dsd/results/P12_canary_fix_prepared_host_2026-10-11/bench-read.json`, SHA-256 `d898ecc37379dfa45492e9a1d1511301f80c1fec63b5817bf5c1719cdd5a83bc`.

There are no recovered-only files. Four non-executable historical evidence/documentation files have mode 0664 (rather than 0644) in the specified original; original modes were preserved. These packaging permissions do not change the source-content equivalence decision.

## Reconciliation procedure and verification

1. Extracted the **specified original** SHA-256-verified archive as the new continuation base.
2. Ran `patch --batch --dry-run -p1 -i <P13-delta>` and `patch --batch -p1 -i <P13-delta>`, both **PASS**. The patch modifies 12 source/build/test files and adds 4 new source/test files.
3. Compared all **16 resulting source/build/test files by SHA-256** to the earlier fully tested P13 delivery: **16/16 PASS**. No performance-relevant code changed relative to that delivery.
4. Copied the two earlier P13 handoff files and all 190 P13 test/benchmark evidence files. Updated only handoff provenance and added the reconciliation record. The original P00 checksum inventory and both prepared-host P12 evidence files were retained without editing.
5. Verified the expected final tree membership and original/previously accepted P13 file continuity. Machine-readable receipt: `tests/dsd/results/P13/source-identity-2026-10-12.json`.

**Functional test disposition:** The accepted P13 build, generic `make check`, inherited P00–P13 DSD replay, forced-ISA, guarded FIR, SDM, channel, numerical, and ISA-isolation tests remain supported by their previously recorded passing execution receipts. A new build/test run is not claimed for the provenance-only repackaging: the source/build/test byte contents did not change. Performance runs were not repeated because performance-relevant code remained byte-identical.

**Other gates:** Physical Intel and AMD AVX-512 performance qualification and inherited P10 long-soak/independent corpus gates remain separate and open. No automatic AVX-512 preference was introduced.
