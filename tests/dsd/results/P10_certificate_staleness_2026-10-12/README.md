# The P10 certificate checker has been failing since P11

Surfaced by the decode-optimization delivery, which correctly reported it as an
inherited condition rather than something it caused. We confirmed it
independently and dated it.

## What fails

`tests/dsd/check_p10_certification.py` pins SHA-256 digests of 35 source
inputs and requires each to match (`check_p10_certification.py:49-50`). Four no
longer match:

| bound input | changed by |
|---|---|
| `src/dsd_plan.c` | later phases, report plumbing |
| `src/pcmdsd.c` | later phases |
| `src/pcmdsd.h` | later phases |
| `src/sdm.c` | later phases |

The checker reports only the first, `certificate evidence changed:
src/dsd_plan.c`, and exits 1.

## When it broke

Run against successive integration commits:

| commit | verdict | subject |
|---|---|---|
| `63872844` | **PASS** | P10 CERTIFIED and CLOSED |
| `39998c36` | FAIL | P11 COMPLETE and P12 AUTHORIZED |
| `1a69979d` | FAIL | P12 AVX2 kernels |
| `20059dbf` | FAIL | P12 canary fixed |
| `5c2e3bcb` | FAIL | P13 AVX-512F kernels |
| `39bc7101` | FAIL | P14 reports |

So it has failed continuously since P11, across four phases.

## The part that is ours

Nobody ran it in those four phases. We audited each of P11, P12, P13 and P14
and did not run it once. Every one of those audits reported gates passing
without this one among them. The delivery that found it was not looking for it
either; it ran the checker as part of its own validation sweep and reported the
failure instead of omitting it.

We do not think the underlying condition is a defect. The four inputs changed
for reasons each phase documented, and the decode optimization's own binding
record shows `optimization_changed: false` for all four. What is wrong is that a
release-gating check was silently red and no phase noticed.

## Why it matters now

P15's contract is to close release qualification and promote defaults, with
completion requiring that "every advertised first-release feature has a passing
evidence ID". A red certificate checker is incompatible with that, so P15 has to
resolve it one way or another before promotion. Whether the right resolution is
re-binding the certificate to current digests with recorded justification,
narrowing what the certificate binds, or re-certifying P10 against the present
sources, is a design decision we are not placed to make.

Our reading, which may be wrong: the certificate's intent was to bind the
coefficient and admission evidence, and binding whole translation units that
later phases legitimately edit makes it fail for reasons unrelated to that
intent. If so the fix is in what it binds rather than in the sources. We did not
verify that the DSP-relevant content of those four files is unchanged, and that
verification is the thing that would justify a re-bind.

## Reproduce

```sh
python3 tests/dsd/check_p10_certification.py --results <dir>   # exit 1
```
