# SoX DSD R3: shared-build test integration and release-guide corrective

Date: 2026-10-20. Parent source: R2 complete snapshot built from GitHub
`68f42359`, SHA-256
`66372253e572464a84c46f59125f9b097fdbf3d63f16a224eca8844a879898e0`.

The independent R1/R2 audit identified three implementation gaps:

1. `make check-rename` executed `src/soxi`, a link to the Libtool **launcher**
   rather than an alias of the real executable. The launcher discards the alias
   basename. The smoke now checks links in the build directory, but invokes
   the real `.libs/sox` (shared build) or `src/sox` (static build) through
   alias names in an isolated temporary directory. Libtool's `--mode=execute
   -dlopen` supplies the configured runtime library search path. Normal and
   disabled-alias policies remain covered.
2. Tests P09, P10, P11, and P13 directly call private `sdm_*` functions not
   exported by shared `libsox_ng`. Each uninstalled test now compiles the
   unchanged `src/sdm.c` directly, without expanding the public ABI or changing
   the library build. P10 was the first failure reported; the full shared
   runner exposed P09 after P10 was corrected. Code inspection identified
   P11 and P13 as using the same private API.
3. CLI `--help` and the README-linked `docs/dsd/MIGRATION_P15.md` incorrectly
   described the superseded pre-activation state. They now identify v2 as the
   unpinned decoder default, explicitly selected v1 as preserved, the unchanged
   legacy mode default, and activated, guarded DSD64/128/256 mastering-v1
   encoding. Historical context remains explicitly dated and linked.

**Not changed:** production DSP implementations, decoder/modulator
coefficients, runtime CLI policy and options, `libsox_ng` exported symbol
policy, installed headers, historical DSD result files, or proof receipts.

Test and source integrity receipts and remaining environmental limitations
are in the separate R3 QA bundle. `make check-dsd DSD_PHASE=P15` is a
regression test suite, not a new formal proof of P15 source-bound numerical
certification. Toolchain-specific CMake/Nix/MXE builds require the target
build environments and are not implied by Autotools passing.
