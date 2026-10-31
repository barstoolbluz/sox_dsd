# Legacy `sdm` guard (2026-10-31)

## Decision

The **legacy** 1-bit modulator keeps the fail-closed guard introduced by
`8a626afe5`, but it runs **only on request**. It is set by a process-wide SoX CLI
option (a global option, placed before the first effect):

```sh
sox in.wav -r 5644800 out.dsf                   # default: unchecked, full speed
sox --sdm-guard=on  in.wav -r 5644800 out.dsf   # full check on every filter and mode
sox --sdm-guard=off in.wav -r 5644800 out.dsf   # explicit default
```

| Setting | Legacy filters and modes checked | CPU |
| --- | --- | --- |
| `off` (default) | none | below SoX DSD 1.0.2 (see below) |
| `on` | all: normal and trellis, every order | higher (see below) |

`on` checks for non-finite or out-of-bounds modulator state (trellis: per
speculative branch, plus non-finite cost). Repeated `--sdm-guard` options are
ordinary global CLI options: the last one parsed wins. An invalid value,
including the earlier `auto`, is an error before the output file is opened.

The option governs both explicit `sdm` effects and implicit precision-1 `dither`
(`sox in.wav -r <native-rate> out.dsf`), since both use the same `sdm_init()`.
It does **not** affect versioned or mastering `pcmdsd` encoders, reconstruction
filters, clipping policy, or the unrelated `-G`/`--guard` temporary-file option.
Callers of the internal legacy `sdm_init()` API that do not run the CLI get the
same unchecked default.

Unchecked, an input that drives the legacy modulator unstable can produce
corrupt 1-bit output while `sox` exits 0. Use `on` where that matters more than
CPU. Even `on` is a runtime limit check, not proof of boundedness or audio
fidelity. The composite mastering encoder has separate, mandatory guards.

When enabled, the check rejects the failing sample before its bit is
published. It discards output from the failing `flow()` call, latches the
error, and returns failure on subsequent flow/drain calls. Normal file output
is removed on failure. Bytes previously written to pipes cannot be retracted:
**never use stream output unless the SoX process exits zero**.

## Basis

The owner chose the default: fast unchecked conversion unless the guard is
requested. The earlier per-filter `auto` default (full checks on `clans-4`,
orders 6–8 and trellis; non-finite only on `sdm-4`, `clans-5`, `sdm-5`) was
dropped.

Measured on one AMD Ryzen Threadripper 7970X, GCC 14.2.0 `-O2`, one pinned
core, median CPU over 11 rounds, 60 s 44.1 kHz stereo to DSD128 (plain route)
and 10 s `sdm -f clans-4` alone at DSD128:

* By default the plain route takes 10.6% less CPU than SoX DSD 1.0.2 (7.645 s
  against 8.556 s), `rate -v 5644800 sdm -f clans-6` 10.9% less, and `sdm`
  alone on `clans-4`, `sdm-4`, `clans-5` and `sdm-5` 12.2–12.7% less, with
  identical output. The unchecked path is a separate per-buffer loop
  (`4e9f04155`) that keeps the SSE2 modulator state in registers (`0a98e6e13`).
  Before that loop, the guard build cost about 10% more even when off.
* With `--sdm-guard=on`, the plain route costs 8.9% more than 1.0.2,
  `rate -v 5644800 sdm -f clans-6` 11.9% more, and `sdm` alone on those four
  low-order filters 2.8–3.3% more. Earlier measurements, before the checked
  loop was reworked (`66c5b5f91`), put normal orders 6–8 at about 7–10% and
  trellis (`-t 13`, after the `836314057` optimization) at about 13% more.

Evidence for keeping the check available (from the 2026-10-30 enablement
package, `SoX_DSD_Legacy_Guard_Enablement_2026-10-30.tar.zst`):

* In a 420-case sweep, 405 outputs match the unchecked control. Fifteen guard
  stops change the result; all are order 6–8, five of them `sdm-8 -t 13`.
* A 20-second DSD256 normal `sdm-8` +0.9999 DC input made the unchecked
  modulator run away at about 12.63 s and write an all-zero tail while
  exiting 0; the check exits 2 and removes the output file.
* One native-rate `clans-4` run on a synthetic jitter program went non-finite.
* 400 real tracks (DSD128, plain `clans-4` and explicit `clans-6`) stopped none
  under the check: a false-positive observation, not coverage of all banks,
  trellis, ISAs, near-full-scale DC or long running times.

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
