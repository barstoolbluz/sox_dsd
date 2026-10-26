#!/usr/bin/env python3
"""Build/run the independent scalar differential harness on configured sources.

Example:
  python3 tests/dsd/run_sdm_register.py --build ../../build/candidate \
      --output ../../evidence/register -- --exceptions

The immutable oracle is hash-checked before every build. The test's C compiler
flags disable contraction, reassociation, finite-only arithmetic and LTO;
each ISA object is compiled separately. A separate output directory is useful
for each compiler, build configuration or sanitizer run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--source", type=Path, default=here.parents[1])
    parser.add_argument("--build", type=Path, required=True,
                        help="configured native build directory containing src/soxconfig.h")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    parser.add_argument("--support-library", type=Path,
                        help="static SoX archive for unused legacy references retained by ASan")
    parser.add_argument("--sanitize", choices=["address,undefined", "undefined"])
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    source, build, output = [p.resolve() for p in (args.source, args.build, args.output)]
    oracle = here / "reference" / "sdm_register_oracle"
    manifest = json.loads((oracle / "provenance.json").read_text())
    for name, expected in manifest["files"].items():
        actual = digest(oracle / name)
        if actual != expected:
            raise RuntimeError(f"frozen oracle hash mismatch: {name}: {actual}")
    config = build / "src" / "soxconfig.h"
    if not config.is_file():
        raise RuntimeError(f"configure the project first; missing {config}")
    output.mkdir(parents=True, exist_ok=True)
    compiler = shlex.split(args.cc)
    flags = ["-std=gnu11", "-O3", "-g", "-ffp-contract=off", "-fno-fast-math",
             "-frounding-math", "-fexcess-precision=standard", "-fno-lto",
             "-ffunction-sections", "-fdata-sections", "-Wall", "-Wextra",
             "-Wno-unused-parameter", "-Wno-unused-label"]
    if args.sanitize:
        flags += ["-fsanitize=" + args.sanitize, "-fno-omit-frame-pointer",
                  "-fno-sanitize-recover=all"]
    includes = ["-I" + str(build / "src"), "-I" + str(source / "src")]
    baseline_isa = ["-mno-avx", "-mno-avx2", "-mno-avx512f", "-mno-fma"]
    macros = config.read_text()
    tiers = []
    for name, macro, isa in [
        ("sse2", "HAVE_DSD_SSE2", ["-msse2", "-mno-avx", "-mno-fma"]),
        ("avx1", "HAVE_DSD_AVX1", ["-mavx", "-mno-avx2", "-mno-fma"]),
        ("avx2", "HAVE_DSD_AVX2", ["-mavx2", "-mno-fma"]),
        ("avx512", "HAVE_DSD_AVX512", ["-mavx512f", "-mno-avx512dq",
                                       "-mno-avx512bw", "-mno-avx512vl", "-mno-fma"]),
    ]:
        if f"#define {macro} 1" in macros:
            tiers.append((name, isa))
    # Rename every exported symbol in both original translation units. Types,
    # internal identifiers, source bytes and arithmetic remain unchanged.
    symbols = [
        "sdm_init", "sdm_process", "sdm_drain", "sdm_close",
        "sdm_legacy_allocation_bytes", "sdm_profile_find", "sdm_profile_id",
        "sdm_profile_filter_name", "sdm_profile_rate", "sdm_profile_working_rate",
        "sdm_profile_coefficients", "sdm_normal_monitor_init", "sdm_normal_init",
        "sdm_normal_attach_monitor", "sdm_normal_decision", "sdm_normal_step",
        "sdm_normal_step_guarded", "lsx_sdm_filter_valid_for_rate",
        "lsx_sdm_effect_filter_name", "lsx_sdm_filter_selected_name",
        "lsx_sdm_effect_fn", "lsx_dsd_fir_scalar", "lsx_dsd_fir_halfband57",
        "lsx_dsd_kernel_scalar",
    ]
    renames = [f"-D{name}=original_{name}" for name in symbols]
    entries = [
        (source / "src" / "sdm.c", "candidate_sdm.o", baseline_isa, []),
        (source / "src" / "dsd_kernels_scalar.c", "candidate_scalar.o", baseline_isa, []),
        (source / "src" / "dsd_dispatch.c", "candidate_dispatch.o", baseline_isa, []),
        (oracle / "sdm.c", "original_sdm.o", baseline_isa, renames),
        (oracle / "dsd_kernels_scalar.c", "original_scalar.o", baseline_isa, renames),
        (here / "test_sdm_register.c", "harness.o", baseline_isa, []),
    ]
    entries += [(source / "src" / f"dsd_kernels_{name}.c", f"candidate_{name}.o", isa, [])
                for name, isa in tiers]
    record = {
        "compiler": subprocess.check_output(compiler + ["--version"], text=True).splitlines()[0],
        "source": str(source), "build": str(build),
        "soxconfig_sha256": digest(config), "oracle_provenance": manifest,
        "sanitize": args.sanitize, "commands": [], "files": {},
        "sanitizer_environment": {key: os.environ[key] for key in
                                  ("ASAN_OPTIONS", "UBSAN_OPTIONS", "LSAN_OPTIONS")
                                  if key in os.environ},
    }
    # Include every private header containing candidate scalar/SIMD arithmetic
    # in the record, not just the translation-unit entry files.
    for path in sorted((source / "src").glob("sdm*.h")):
        record["files"][str(path)] = digest(path)
    objects = []
    with (output / "build.log").open("w") as log:
        for src, name, isa, defines in entries:
            dst = output / name
            cmd = compiler + flags + isa + includes + defines + ["-c", str(src), "-o", str(dst)]
            record["commands"].append(cmd)
            record["files"][str(src)] = digest(src)
            log.write(shlex.join(cmd) + "\n")
            log.flush()
            subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
            objects.append(str(dst))
        binary = output / "test_sdm_register"
        support = []
        if args.support_library:
            support = [str(args.support_library.resolve()), "-ldl"]
        elif args.sanitize:
            for library in (build / "libsox_native.a", build / "src" / ".libs" / "libsox_ng.a"):
                if library.is_file():
                    support = [str(library), "-ldl"]
                    break
        if support:
            record["support_library_sha256"] = digest(Path(support[0]))
        # ASan's global registry can retain the unrelated legacy effect's
        # static handler and callbacks. Resolve their unexecuted utility
        # references from SoX; every exercised kernel is instrumented above.
        cmd = compiler + flags + ["-Wl,--gc-sections"] + objects + support + ["-lm", "-o", str(binary)]
        record["commands"].append(cmd)
        log.write(shlex.join(cmd) + "\n")
        log.flush()
        subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    record["binary_sha256"] = digest(binary)
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"built {binary}; isolated tiers: scalar,{','.join(name for name, _ in tiers)}", flush=True)
    if args.compile_only:
        return 0
    test_args = args.arguments
    if test_args and test_args[0] == "--":
        test_args = test_args[1:]
    started = time.monotonic()
    with (output / "test.log").open("w") as log:
        child = subprocess.Popen([str(binary)] + test_args, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert child.stdout is not None
        for line in child.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        rc = child.wait()
    (output / "result.json").write_text(json.dumps({
        "returncode": rc, "elapsed_seconds": time.monotonic() - started,
        "arguments": test_args, "binary_sha256": record["binary_sha256"],
    }, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
