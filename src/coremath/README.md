# Pinned CORE-MATH binary64 exp10

`exp10.c` is the **unaltered** CORE-MATH `src/binary64/exp10/exp10.c`
(Copyright (c) 2023 Alexei Sibidanov, MIT). Its complete license and
copyright notice are at the top of the source file.

- Examined public mirror: `https://github.com/mockingbirdnest/core-math`
- Immutable mirror commit: `5dd63f1ba80eb17488e0e43558269a4c61d1aca9`
- Git blob: `ebcf7c82b3caed3c7f4f6a10893479ac171bb1da`
- Project's official home: `https://gitlab.inria.fr/core-math/core-math`
- File SHA-256: recorded in the package manifest.

This file was fetched through GitHub's commit-addressed file API and the
blob identity checked independently with `git hash-object`. The official
GitLab repository's corresponding commit was **not independently verified**;
the mirror alone is not a claim of official revision equivalence.

Only `cr_exp10` is used. It is statically included in `libsox_ng` and excluded
from its public dynamic-symbol export list. No runtime download or extra
library is required. The caller must use IEEE binary64, nearest-even,
functional fused multiply-add and gradual underflow. Unsafe floating-point
optimizations and whole-program LTO are forbidden by the build flags.
