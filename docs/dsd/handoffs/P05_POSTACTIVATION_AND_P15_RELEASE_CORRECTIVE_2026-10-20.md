# SoX DSD — P05/P08 post-activation and P15 release regression corrective

Date: 2026-10-20
Original source revision: `68f42359`
Applied prerequisite: SoX DSD `sox_ng` → `sox` rename R1

## Scope and explanation

Four assertions in the historical P05 planner C tests, and two execution
expectations in the P05 CLI suite, still assumed that DSD reconstruction
and/or mastering modulation were unavailable. Those expectations predated
P07/P08 reconstruction and P10 mastering modulation. The four C failures
were independently reproduced in the unmodified `68f42359` source snapshot
before this corrective pass. Changing production DSP to satisfy these
stale assertions would have been wrong.

A P08 integration test similarly expected mastering modulation to be
unavailable, and three P15 CLI qualification cases still expected a
production encode hold that the operator explicitly lifted on 2026-10-20
(`P15_RELEASE_ACTIVATION_2026-10-20.md`). The corresponding tests now
validate real processing and retain negative tests for invalid layouts,
unsupported rates, and fail-closed modulator overload.

## Genuine runtime default-policy defect

The operator's 2026-10-20 release activated mastering v2 as the default
DSD-to-PCM decoder in `src/dsd.c` and `src/dsd_public.c`. The CLI's default
policy in `src/sox_ng.c` nevertheless remained mastering v1. Thus an
implicitly inserted decoder differed from an otherwise equivalent unpinned
explicit `dsdpcm` effect. An independently generated fixture produced
different PCM bytes before correction. A single CLI policy initializer now
selects `LSX_DSD_PROFILE_MASTERING_V2`. Explicit v1 remains available under
`-p mastering` and its versioned IDs.

No signal-processing filter, modulator, encoder, decoder, certificate,
source-bound mathematical receipt, or other production DSP implementation
was changed in this corrective pass.

## Changed paths

- `src/sox_ng.c`: default CLI decode policy (one initializer; documentation
  comment).
- `tests/dsd/test_plan.c`: four post-activation planner expectations.
- `tests/dsd/test_plan.py`: post-activation execution, strict guard refusals,
  and versioned/default decoder selection assertions.
- `tests/dsd/test_p08.py`: plan-plus-actual DSF mastering-modulator coverage
  replaces an obsolete pre-activation rejection case.
- `tests/dsd/test_p15.py`: release-activated encoder planning and real
  DSD64/128/256 encoding with independent DSF structure verification.
- This handoff note.

## Verification performed

Using the patched binary, an external results directory outside
`tests/dsd/results/`, and the available host ISA:

- `./test/dsd_test_plan`: 168 assertions, 0 failures.
- `python3 tests/dsd/test_plan.py`: 160 pass, 0 fail.
- `python3 tests/dsd/test_p08.py`: 28 pass, 0 fail.
- `python3 tests/dsd/test_p15.py`: 137 pass, 0 fail.
- `make check-rename`: passed.
- `make check`: passed.
- `make check-dsd DSD_PHASE=P15 DSD_RESULTS=<external-directory>`: exit 0.
- For the tested DSD64 fixture, implicit and unpinned explicit `dsdpcm`
  produced byte-identical PCM after aligning the v2 default.

## Preservation, qualifications and resumption

The retained evidence tree `tests/dsd/results/` is immutable and must
remain byte-identical to the supplied archive. Generate new test records
in a separate results directory; do not regenerate or replace old receipts.
The original snapshot omitted 946 `.npz` files; this corrective snapshot
retains that omission and does not pretend to supply them.

These test results do not close independent mathematical proof/source-bound
qualification obligations; see the original P15 authority documents for
those distinct release/proof decisions. Full Nix, CMake 4 and cross-target
MXE builds were not established by this corrective pass.

To resume, first read this handoff, then inspect the incremental patch and
its SHA-256 manifest. Re-run the three build/test targets above with an
external DSD results directory before further engineering changes. Keep
future DSP changes out of this rename and test-rebase corrective.
