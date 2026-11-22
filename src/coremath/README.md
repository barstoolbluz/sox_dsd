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
allow independent reconstruction. To verify the vendored corrected source in any re-authored checkout,
without depending on an implementation commit ID:

```sh
sha256sum src/coremath/exp10.c src/coremath/exp10-llp64.patch
test "$(git hash-object src/coremath/exp10.c)" = \
  94f9f21eec1ea74bbc169bd4937c6792e933f26a
```

To reproduce the correction from the external *unmodified upstream blob*,
apply `exp10-llp64.patch` with `patch -p3` in a scratch directory, then
compare the result against the recorded corrected blob and SHA-256. The
unmodified upstream blob is not assumed present in an integrating clone.

The source was retrieved using GitHub's immutable commit-addressed file API;
its Git blob was independently checked. Mapping the mirror revision to the
official GitLab revision remains unverified.

Only `cr_exp10` is used. It is statically included in `libsox_ng` and excluded
from its public dynamic-symbol export list. There is no runtime download or
extra library dependency. Callers require binary64, nearest-even rounding, the implementation's
fused-multiply-add semantics and gradual underflow. The shipped `exp10.c`
contains its own binary64 helpers; it does not introduce undefined
`fma` or `roundeven` references that need to be resolved by libm.
Other SoX code can still link libm for unrelated functions. Unsafe
floating-point optimizations and whole-program LTO remain forbidden by
build flags.
Windows runtime qualification still requires execution on a supported Windows
host; source changes and Linux or cross-compiled object tests alone do not
establish that qualification.
