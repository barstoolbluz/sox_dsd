# CORE-MATH binary64 exp10: pinned source plus local LLP64 correction

`exp10.c` derives from CORE-MATH `src/binary64/exp10/exp10.c`
(Copyright (c) 2023 Alexei Sibidanov, MIT). The complete original
copyright, permission notice, and warranty disclaimer remain at the start
of the C source. **The locally corrected file is not byte-identical to
upstream.**

- Examined public mirror: `https://github.com/mockingbirdnest/core-math`
- Immutable mirror commit: `5dd63f1ba80eb17488e0e43558269a4c61d1aca9`
- Unmodified upstream Git blob: `ebcf7c82b3caed3c7f4f6a10893479ac171bb1da`
- Unmodified upstream SHA-256: `29ac9ccbd16dec7ee6836bf3e5baab0fc42b3aafc35990242c3bcd62431ebe7f`
- Local corrected Git blob: `94f9f21eec1ea74bbc169bd4937c6792e933f26a`
- Local corrected SHA-256: `cdcba66976e9096d9bec332b4a4659472751b8f20135ca5766edeaffdd0e5d03`
- Local correction: `exp10-llp64.patch`; SHA-256:
  `bf931829ecae3357c12a4dd530bb5e9a9bb2710e75491ea93cacbb92fb52cad5`
- Project official repository: `https://gitlab.inria.fr/core-math/core-math`

The local patch replaces `unsigned long` width-dependent bit masks with
explicit 64-bit values and avoids signed left shifts, including shifts of
negative exponent offsets. The algorithm, polynomial coefficients, exception
paths, and `cr_exp10` interface are otherwise unchanged. The patch applies
to the **unmodified upstream blob**, and its hash and the local file hash
allow independent reconstruction. To replay it from the pinned D6 source and verify byte identity:

```sh
git show 17848e20:src/coremath/exp10.c > /tmp/exp10.c
(cd /tmp && patch --batch -p3 < /path/to/src/coremath/exp10-llp64.patch)
test "$(git hash-object /tmp/exp10.c)" = 94f9f21eec1ea74bbc169bd4937c6792e933f26a
```

The `-p3` is intentional: it selects the target `exp10.c` from the
`b/src/coremath/exp10.c` path in the patch. The exact before/after SHA-256
values above can be checked independently.

The source was retrieved using GitHub's immutable commit-addressed file API;
its Git blob was independently checked. Mapping the mirror revision to the
official GitLab revision remains unverified.

Only `cr_exp10` is used. It is statically included in `libsox_ng` and excluded
from its public dynamic-symbol export list. There is no runtime download or
extra library dependency. Callers require binary64, nearest-even rounding,
functional fused multiply-add and gradual underflow. Unsafe floating-point
optimizations and whole-program LTO remain forbidden by build flags.
Windows runtime qualification still requires execution on a supported Windows
host; source changes and Linux or cross-compiled object tests alone do not
establish that qualification.
