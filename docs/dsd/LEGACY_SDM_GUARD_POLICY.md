# Legacy `sdm` guard enablement (2026-10-30)

## Decision

The **legacy** 1-bit modulator retains the fail-closed guard introduced by
`c6d64c6`, with the following process-wide SoX CLI option (a global option,
placed before the first effect):

```sh
sox --sdm-guard=auto in.wav -r 5644800 out.dsf  # default
sox --sdm-guard=on   in.wav -r 5644800 out.dsf  # full check everywhere
sox --sdm-guard=off  in.wav -r 5644800 out.dsf  # unsafe legacy compatibility
sox --sdm-guard=on   -r 11289600 -c 1 -n -r 11289600 out.dsf \
    synth 0.08 sine 997 sdm -f sdm-8 -t 3 -n 4 -l 100
```

| Selected legacy filter/mode | `auto` (default) | `on` | `off` |
| --- | --- | --- | --- |
| Trellis, any filter/order | State bounds, non-finite state/cost | Same | No guard |
| Normal `clans-4` | State bounds, non-finite decision | Same | No guard |
| Normal order 6, 7, or 8 (`clans-*`, `sdm-*`) | State bounds, non-finite decision | Same | No guard |
| Normal `sdm-4`, `clans-5`, `sdm-5` | Non-finite quantizer decision **only** | State bounds, non-finite decision | No guard |

The decision uses the **selected** coefficient bank at the **actual input clock**,
not just the literal `-f` string. Any trellis selection receives full checks,
including low-order trellis. Repeated `--sdm-guard` options are ordinary global
CLI options: the last one parsed wins. An invalid mode is an error before the
output file is opened.

The option governs both explicit `sdm` effects and implicit precision-1 `dither`
(`sox in.wav -r <native-rate> out.dsf`), since both use the same `sdm_init()`.
It does **not** affect versioned or mastering `pcmdsd` encoders, reconstruction
filters, clipping policy, or the unrelated `-G`/`--guard` temporary-file option.
There is no new per-effect flag; one global setting makes the ordinary route
and explicit effect agree. Defaults also apply to callers of the internal
legacy `sdm_init()` API that do not run the CLI.

`off` is expressly **not** recommended for production DSD: legacy code can
exit successfully with invalid 1-bit output. `auto`'s non-finite-only cases
**do not** detect finite bound escapes and do not guarantee good audio. Use
`on` for mastering-like or safety-sensitive use of these legacy filters. Even
`on` is a runtime limit check, not proof of boundedness or audio fidelity.
The composite mastering encoder has separate, mandatory guards and policies.

When enabled, the check rejects the failing sample before its bit is
published. It discards output from the failing `flow()` call, latches the
error, and returns failure on subsequent flow/drain calls. Normal file output
is removed on failure. Bytes previously written to pipes cannot be retracted:
**never use stream output unless the SoX process exits zero**. This is not a
transactional streaming protocol, and the guard cannot cure an already-broken
or unqualified coefficient bank.

## Basis for the defaults

Source and original evidence: `SoX_DSD_Legacy_Guard_Enablement_2026-10-30.tar.zst`
(SHA-256 `062fd11fcec3bc2f876b269f975256082386c535eebe87c4a87743ec54fc457d`).
The archive contains the unmodified base, the `c6d64c6` guard patch, the
branch `d6ed7ec`, original logs, and deterministic reproduction records.

* In the supplied 420-case sweep, 405 outputs match the unguarded control.
  Fifteen guard stops change the result; **all** are order 6–8, five of them
  `sdm-8 -t 13`. That is positive evidence for default full checks on
  order 6–8 and trellis, but **not** proof that 4/5 can never fail.
* In the shipped 17-second DSD256 normal `sdm-8` +0.9999 DC case, the unguarded
  control returned success with a flatlined tail, while the full guard
  returned failure and removed the output file. At the same native rate in
  the 20-second case, the control's first detected runaway was ~12.63 s,
  and its DSD output was all zeros after ~13.49 s. The `pipe` control can
  also fail downstream during finalization, so a nonzero **pipe** exit alone
  does not establish that the SDM guard caught the numerical defect.
* The separate CLI transient handoff reports **one normal `clans-4`**
  native-direct non-finite result (`jitter01-neg`). We cannot safely exempt
  this filter merely because no normal music track in that small corpus
  stopped. The ordinary implicit PCM-to-DSD route selects `clans-4`.
* The 400 real-track runs reportedly stopped none under the earlier
  `c0ebf9e` guard for plain `clans-4` or explicit `clans-6`. That is a useful
  false-positive observation, not coverage for all banks, trellis, ISAs,
  near-0-dBFS DC, or extended running times.
* The supplied CPU medians (Ryzen Threadripper 7970X; ISA tier not recorded)
  are control 8.6226 s vs full-guard 9.4298 s (**+9.4%**) for a typical
  44.1kHz-to-DSD128 route; 9.0823 vs 10.0827 (**+11.0%**) for explicit
  `clans-6`; and ~+26–27% on two trellis measurements. Performance is
  workload- and machine-dependent.

The cost is material, but the data **do not justify removing full default
protection from `clans-4`**. Auto therefore does not reduce the reported
plain-route 9.4% overhead. It reduces state-bound-check work for the three
low-order normal modes without documented failures while retaining a
non-finite fail-closed stop. `off` provides an explicit, clearly named unsafe
fast path for users who deliberately accept its risk. No performance claims
are made for `auto` until measurements on the target workload and ISA tier
have been completed. This deliberately prioritizes a known failure mode over
an unsupported CPU promise.

A shipped `guard_classify.json` from a prior handoff is cited in the supplied
README but **is not in this archive**. Its claim that all fifteen unguarded
outputs are broken has not been independently reclassified here; the above
policy does not depend on that claim.

## Implementation and compatibility

The option changes **checks**, not filter coefficients, quantization or the
recurrence. Healthy guarded streams must be byte-identical to unchecked
streams. `off` is tested against the original `sdm-8` trellis reference hash.
Normal/trellis paths are separate; in trellis mode an invalid **speculative**
branch is rejected without killing a healthy surviving branch, while total
loss of viable branches stops the effect. This behavior is unchanged.

The mode is selected during `sdm_init()` after determining the active filter;
there are no per-sample allocations, locks, logging, or extra copies. The CLI
sets the policy during option parsing, before effect construction. This is
single-process CLI configuration, not a dynamically reconfigurable library
setting for concurrently running effects.

## Verification and limits

The added standard-library integration test
`tests/dsd/test_legacy_sdm_guard_policy.py` exercises the option parser,
`SOX_OPTS`, normal/trellis routes, two channels, implicit dither, known
terminal failure, file cleanup, reference hash, and healthy-path identity.
Run `make check-sdm-guard-policy`. It is also part of `make check-dsd`.

The following remain unqualified until run on the intended target machines:

* Program material on every low-order filter and all trellis settings; the
  known classifier has only partial coverage of actual audio.
* The known candidate false-positive reproduction; sustained near-full-scale
  DC on the plain `clans-4` route; long-duration DSD64–DSD1024 soaks.
* More than one channel on failure, repeated-invocation/error-lifecycle
  coverage, stream-consumer abort/finalization behavior, and restart behavior
  beyond the focused integration tests.
* Alternative compiler/ISA tiers, OSes, CPU profiles, Nix closure, and
  actual `pcmdsd`/P21 non-regression of the new mode (no changes to their
  source paths).
* Full independent numerical and audio analysis. No finite-duration runtime
  check is a mathematical stability certificate or a mastering qualification.
