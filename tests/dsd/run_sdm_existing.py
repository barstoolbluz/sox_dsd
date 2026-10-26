#!/usr/bin/env python3
"""Replay existing contracts against a completed static Linux native build.

Example:
  python3 tests/dsd/run_sdm_existing.py --source . --build /path/to/build \
      --output /path/to/evidence/existing

Python integrations require the dependencies of the original test scripts,
including NumPy and jsonschema. --python-path can supply task-local packages.
Results state the selected scope, retain every command and output, and check
that the tested library, executable and test sources did not change during a
run. This runner does not rebuild production objects.
Both Autotools (src/.libs/libsox_ng.a) and the supplemental build layout are
recognized. Optional external codecs should be disabled for standalone linking.
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


UNITS = {
    "test_p09": [("test_p09", ["--unit"])],
    "test_p10": [("test_p10", ["--unit"])],
    "test_p11": [("test_p11", [])],
    "test_p12_bounds": [("test_p12_bounds", [])],
    "test_p13": [("test_p13", [])],
    "test_p14": [("test_p14", ["--json", "512", "analysis"])],
    "test_p16": [("test_p16", []), ("test_p16-matrix", ["matrix"])],
    "test_p17": [("test_p17", []), ("test_p17-matrix", ["matrix"]),
                 ("test_p17-encode", ["encode"])],
    "test_p18": [("test_p18", [])],
    "test_sdm_auto": [("test_sdm_auto", [])],
}
INTEGRATIONS = ("p11-cli", "p12-channels", "p14-cli", "p16-cli")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decoded(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--python-path", type=Path)
    parser.add_argument("--units", nargs="+", choices=list(UNITS), default=list(UNITS))
    parser.add_argument("--integrations", nargs="*", choices=INTEGRATIONS,
                        default=list(INTEGRATIONS))
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--tiers", nargs="+", choices=["scalar", "sse2", "avx1", "avx2", "avx512"],
                        default=["scalar", "sse2", "avx1", "avx2", "avx512"],
                        help="forced CLI tiers; select only tiers supported by the target host")
    args = parser.parse_args()
    source, build, output = [p.resolve() for p in (args.source, args.build, args.output)]
    supplemental = (build / "libsox_native.a").is_file()
    library = build / ("libsox_native.a" if supplemental else "src/.libs/libsox_ng.a")
    cli = build / ("sox" if supplemental else "src/sox")
    config = build / ("soxconfig.h" if supplemental else "src/soxconfig.h")
    for path in (library, cli, config):
        if not path.is_file():
            parser.error(f"incomplete static native build: missing {path}")
    integrations = [] if args.skip_integration else args.integrations
    units = list(dict.fromkeys(args.units))
    for integration, unit in (("p14-cli", "test_p14"), ("p16-cli", "test_p16")):
        if integration in integrations and unit not in units:
            units.append(unit)
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    if args.python_path:
        paths = [str(args.python_path.resolve())]
        if environment.get("PYTHONPATH"):
            paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(paths)
    flags = ["-O3", "-g", "-fno-fast-math", "-ffp-contract=off", "-frounding-math",
             "-fno-lto", "-fno-strict-aliasing", "-I" + str(config.parent),
             "-I" + str(source / "src"), "-DHAVE_CONFIG_H"]
    manifest = {
        "source": str(source), "build": str(build), "selected_units": units,
        "selected_integrations": integrations, "commands": [], "status": "RUNNING",
        "input_sha256": {str(p): sha(p) for p in (library, cli, config)},
        "python_path": str(args.python_path.resolve()) if args.python_path else None,
        "integration_tiers": args.tiers,
        "build_layout": "supplemental" if supplemental else "autotools",
    }

    def save() -> None:
        (output / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def run(name: str, command: list[str | Path], timeout: int = 180) -> bool:
        argv = list(map(str, command))
        start = time.monotonic()
        try:
            result = subprocess.run(argv, capture_output=True, text=True,
                                    timeout=timeout, env=environment)
            status, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as exc:
            status, stdout, stderr = "TIMEOUT", decoded(exc.stdout), decoded(exc.stderr)
        record = {"name": name, "command": argv, "exit": status,
                  "elapsed_seconds": time.monotonic() - start,
                  "stdout": stdout, "stderr": stderr}
        manifest["commands"].append(record)
        (output / (name + ".log")).write_text(stdout + stderr)
        save()
        print(name, status, flush=True)
        if status != 0:
            print(stderr[-1500:], flush=True)
        return status == 0

    compiler = shlex.split(args.cc)
    for name in units:
        test_source = source / "tests" / "dsd" / (name + ".c")
        manifest["input_sha256"][str(test_source)] = sha(test_source)
        if run("build-" + name, compiler + flags +
               [test_source, library, "-lm", "-ldl", "-o", output / name]):
            for key, arguments in UNITS[name]:
                run(key, [output / name, *arguments])
    tiers = args.tiers
    integration_args = {
        "p11-cli": ("test_p11_integration.py", ["--candidate", cli, "--tiers", *tiers]),
        "p12-channels": ("test_p12_channels.py", ["--candidate", cli, "--tiers", *tiers]),
        "p14-cli": ("test_p14.py", ["--unit", output / "test_p14", "--candidate", cli]),
        "p16-cli": ("test_p16.py", ["--unit", output / "test_p16"]),
    }
    for name in integrations:
        filename, extra = integration_args[name]
        script = source / "tests" / "dsd" / filename
        manifest["input_sha256"][str(script)] = sha(script)
        run(name, [sys.executable, script, "--sox", cli,
                   "--results", output / name, *extra], timeout=300)
    changed = [name for name, digest in manifest["input_sha256"].items()
               if sha(Path(name)) != digest]
    manifest["changed_during_run"] = changed
    manifest["status"] = "PASS" if not changed and all(
        row["exit"] == 0 for row in manifest["commands"]) else "FAIL"
    save()
    return int(manifest["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
