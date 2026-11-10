# Phase 01 owner decision: remove the legacy modulator-protection level cut

**Authority:** November 9, 2026 project-owner requirement, superseding
`architecture/DECISIONS.md` D10 and `architecture/phases/PHASE-01.md` where they
prescribe unchanged 0.9/0.45 frontend behavior at certified rates. Those
historical architecture records are retained verbatim for provenance.

## Implemented 2.0.0 development policy

| Output clock | Production modulator | Proof status | Default linear gain | Warning clip threshold |
| --- | --- | --- | ---: | ---: |
| DSD64 | `encode.mastering.v3.dsd64` switched resonator | mathematical certificate for `abs(x) <= 0.5 + 2^-28` | **1.0** | **0.5** nominal native full scale |
| DSD128 | `encode.mastering.v3.dsd128` switched resonator | same certified input envelope | **1.0** | **0.5** nominal native full scale |
| DSD256 | mastering v1 SDM | no equivalent theorem | 0.9 | 0.45 protective |
| DSD512 | mastering v2 CLANS-7 | finite qualification, no equivalent theorem | 0.9 | 0.45 protective |
| DSD1024 | mastering v2 CLANS-7 | finite qualification, no equivalent theorem | 0.9 | 0.45 protective |

The 0.5 warning threshold is **not** the old instability-avoidance margin.
It is the nominal full-scale amplitude reference: 0 dBFS PCM maps to 0.5
native modulator input at the PCM reference scale. Genuine inter-sample
overshoots above this may still require user-level amplitude handling.

`--dsd-clip warn` (the CLI default) clips **only** native samples above that
nominal full scale for certified rates, reporting their count. Input samples
within (0.45, 0.5] are never clamped or reduced merely to protect a modulator.
`--dsd-clip error` disables all clipping; if a sample exceeds the admitted
native envelope, the conversion fails closed without publishing partial
output. The kernel also independently rejects values outside its proven
bound. No certification is implied for arbitrary inputs above that bound.

`--headroom DB` is explicitly requested attenuation. `--auto-headroom` is
also opt-in and targets 0.5 at the certified rates. It protects programme
fidelity by measuring the **actual post-interpolation peak** (including EOF
and every channel), not by adding unconditional gain reduction. It may
reduce a programme with a true overshoot so it remains in the certified
nominal range. Neither option changes the kernel recurrence or coefficients.

## Engineering boundary

Only the source policy in `src/pcmdsd.c`, corresponding acceptance assertions,
and operator-facing documentation change. Rate selection derives from the
**qualified resonator profile**, not a new user-tunable bypass or a blanket
promise at every DSD rate. The legacy gain and clip policy remains for other
rates. The previous frozen kernel certificates, code and arithmetic flags
are unchanged. Historic tests that explicitly required .9/.45 at DSD64/128
are superseded, not proof that the new policy is defective.

The delivery's `evidence/owner-level-policy/` contains the new independent
build, synthetic test outputs, and regression receipts. Historical real-music
results were measured under the earlier .9/.45 frontend, and are not falsely
rebranded as new-policy real-music qualification.
