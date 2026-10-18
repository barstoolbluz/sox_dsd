# P15 SRC optimization: production disposition and source/operator rebinding

2026-10-17. Controlling input archive `sox_ng-P15-rebind-f9468ad7.tar.gz`,
SHA-256 `204e3ee322a3d54579dbab30cb73596fa448efa04ed58d465df5db1f1efaf215`.

## Disposition

**APPROVE integration as an explicitly opt-in production SRC optimization,
subject to the build contract below. DO NOT switch the default on. DO NOT
promote P15 or native DSD v2. Release remains BLOCKED.**

The optimized path pairs two independent outputs in the non-interpolated
polyphase FIR stage; each dot product retains its coefficient/input sequence.
The integer quotient/remainder recurrence is equivalent to the original
positive-integer division scheduling under the supported, bounded stage
invariants. No filter coefficient, native DSD kernel, FFT4G algorithm,
interpolation policy, or halfband implementation changes here. Existing
physical-host trials report positive but modest and workload-dependent whole-
CLI speedups; several cases have overlapping confidence intervals and tiny
stage calls show a measurable regression. An opt-in path is appropriate;
a default flip would require stronger platform/workload evidence.

The exact-output test on the newly guarded build passes 768060 assertions,
53856 direct cases, 288 streaming cases, 50 API cases, and 5409850 binary64
output words across four rounding modes. This is an operational equivalence
test, not a continuum spectral certificate or arbitrary-input FFT4G proof.

## Active stage binding, immutable history

The archive's `P15_SRC_STAGE_BOUND_2026-10-16` was source-locked to the frozen
`rate_poly_fir0.h` SHA-256 `928f005912f35ca0612a37c99a9a6343be8dea51e23cd41f5286b9f85fede6ff`.
It is preserved unmodified. It must not be used to verify the candidate.

`tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/` is a separate,
current-source bound capture created by the test-only exporter compiled from
the current source with `LSX_RATE_ORDERED_OPT=1`, `-ffp-contract=off` and
`LSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1`. The exporter SHA-256 refers to the
actual ELF (not the libtool wrapper) and a build-provenance record also pins
the linked library. The source-identity map includes the *entire* optimized
header; no opt-in code was excluded from the hash.

For all 24 distinct SRC clock pairs, the new `stage-snapshot.json` is byte-for-
byte identical to the independently archived snapshot. All 72 cells and
214432 individually enumerated families at 1 kHz pass the source-bound
matrix verifier. The binding SHA map changes only for `src/rate_poly_fir0.h`
and `tests/dsd/p15_src_capture_matrix.py` (the latter selects the new evidence
folder). The whole current source map is recorded on each new operator receipt.

The campaign's `source_operators(canonical_plan('1000'))` now accepts all 24
realizations. A baseline receipt presented as a candidate binding still fails.
The earlier 5112 partial-campaign receipts remain tied to their frozen source
identity. **They were not relabeled, overwritten, or silently imported.** A
new-source campaign must publish receipts under a fresh output path, or a
separate mathematical equivalence/replay argument must establish reuse. This
rebind alone does not complete the 11516-interval continuum proof.

## FP contraction guard

`-ffp-contract=off` is a **hard opt-in build-qualification requirement**,
not an undocumented assumption. The header now rejects an opt-in compile
without `-DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1`. This macro is an explicit
statement by the build, **not** an intrinsic check of the compiler setting:
standard C exposes no reliable `#if` test for the effective contraction flag.
The independent `p15_src_opt_build_contract.py` rejects a captured build's
flags unless they explicitly contain the opt-in macro, the acknowledgement,
and a last effective `-ffp-contract=off` without known reassociation flags.
Compiler/toolchain correctness remains an explicit assumption.

Under these conditions the C preprocessed text is byte-identical before and
after adding the admission guard for both the default-off and enabled cases.
The default C computation remains the historical implementation. Running
with a claimed acknowledgment but different actual flags is unqualified.

## Reproduce from the attached corrected source tree

On a supported GNU/Linux Autotools host with the required build dependencies:

```sh
autoreconf -fi
mkdir -p /tmp/sox-opt-rebind-build
cd /tmp/sox-opt-rebind-build
CFLAGS='-O2 -g -ffp-contract=off -DLSX_RATE_ORDERED_OPT=1 -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1' \
  /path/to/sox_ng/configure --without-libltdl
make -j8 all
make -C test dsd_test_p15_src_stage_export
cd /path/to/sox_ng
python3 tests/dsd/p15_src_opt_build_contract.py \
  --makefile /tmp/sox-opt-rebind-build/src/Makefile
LD_LIBRARY_PATH=/tmp/sox-opt-rebind-build/src/.libs \
PYTHONPATH=tests/dsd python3 tests/dsd/p15_src_capture_matrix.py \
  --output tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17 \
  --exporter /tmp/sox-opt-rebind-build/test/.libs/dsd_test_p15_src_stage_export
PYTHONPATH=tests/dsd python3 -m unittest -v \
  test_p15_opt_source_rebind test_p15_src_bound_operator \
  test_p15_final_obligations test_p15_remaining_math
```

The re-capture command is idempotent with identical source, build and file
hashes, and fails closed rather than replacing stale or conflicting evidence.
Use a new output name when changing compiler/build identity.

`tests/dsd/test_src_optimization.c` includes the real `rate.c` and compares
against frozen reference headers restored under
`tests/dsd/reference/src_optimization/` from the input's own preserved support
patch. The recorded original header hashes were independently verified.

## Known gaps and separate work

1. The supplied branch has a stale `test_p15_campaign_dispatch_corrective.py`:
   it imports `BranchBoundary`, but this branch's continuum module lacks it.
   The 2026-10-17 campaign scheduler/timeout correction was not coherently
   integrated into this supplied snapshot. This is **not** addressed by the
   present production SRC rebinding; integrate that already separate correction
   deliberately before attempting a full long-running campaign.
2. No new prepared-physical-host benchmark or complete full-CLI platform
   qualification was run in this rebinding environment. Historical timings
   remain scoped to their exact historical source/build identities.
3. The FFT4G arbitrary-input execution-roundoff proof and complete composite
   spectral continuum acceptance remain open. No stage identity evidence is
   upgraded into a release pass.
4. The archived DSD256 physical benchmark retains its earlier scoped
   disposition; it is not remeasured or promoted here.

## Deliverable integrity

`RECAPTURE_AUDIT.json` compares every current stage snapshot with the frozen
one, `BUILD_PROVENANCE.json` records compiler and executable identities, and
`VALIDATION.json` records the bounded tests. Historical files are unchanged.
