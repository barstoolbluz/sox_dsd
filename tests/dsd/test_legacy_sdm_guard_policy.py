#!/usr/bin/env python3
"""Integration checks for the legacy SDM guard CLI and effect paths.

Run from a built checkout:
    python3 tests/dsd/test_legacy_sdm_guard_policy.py --sox src/sox
Uses only the Python standard library. No large fixtures or persistent outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

TRELLIS_REFERENCE_SHA256 = "497a1449829a24e4589451ea064d547d13b9d1cfdb34742d47b2d1d79c4d2412"


def digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def check(condition: bool, name: str, details: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name}: {details}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sox", type=Path, default=Path("src/sox"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    sox = str(args.sox.resolve())
    results = []
    with tempfile.TemporaryDirectory(prefix="sox-sdm-guard-") as folder:
        tmp = Path(folder)

        def run(name: str, flags: list[str], content: list[str],
                *, env: dict[str, str] | None = None) -> tuple[int, str | None]:
            out = tmp / f"{name}.dsf"
            cmd = [sox] + flags + [str(out) if arg == "{output}" else arg for arg in content]
            effective_env = os.environ.copy()
            effective_env.pop("SOX_OPTS", None)
            if env is not None:
                effective_env.update(env)
            proc = subprocess.run(cmd, capture_output=True, env=effective_env, timeout=90)
            output_sha = digest(out) if out.exists() else None
            results.append({"test": name, "exit": proc.returncode,
                            "output_sha256": output_sha,
                            "stderr": proc.stderr.decode(errors="replace")[-1200:]})
            return proc.returncode, output_sha

        trellis = ["-R", "-r", "11289600", "-c", "1", "-n",
                   "-r", "11289600", "-c", "1", "{output}", "synth", "0.08",
                   "sine", "997", "sdm", "-f", "sdm-8", "-t",
                   "3", "-n", "4", "-l", "100"]
        # out path is inserted after second output descriptor, before synth.
        def native_config(mode: str | None) -> list[str]:
            return [] if mode is None else ["--sdm-guard=" + mode]

        for mode in (None, "on", "off"):
            name = "trellis-" + (mode or "default")
            code, value = run(name, native_config(mode), trellis)
            if mode != "on":
                check(code == 0 and value == TRELLIS_REFERENCE_SHA256, name,
                      f"unchecked output differs: exit={code}, sha={value}")
            else:
                check(code == 2 and value is None, name,
                      f"failed output file retained or stop missed: {results[-1]}")
                check(results[-1]["stderr"].count("sdm: modulator state escaped") == 1,
                      name, "diagnostic should be emitted exactly once")

        env = os.environ.copy()
        env["SOX_OPTS"] = "--sdm-guard=off"
        code, value = run("trellis-from-sox-opts", [], trellis, env=env)
        check(code == 0 and value == TRELLIS_REFERENCE_SHA256,
              "SOX_OPTS", "policy did not reach effect startup")

        # Explicit command-line settings must override the SOX_OPTS default.
        code, value = run("cli-overrides-sox-opts", ["--sdm-guard=on"],
                          trellis, env=env)
        check(code == 2 and value is None, "CLI overrides SOX_OPTS",
              str(results[-1]))
        env["SOX_OPTS"] = "--sdm-guard=on"
        code, value = run("cli-unsafe-overrides-sox-opts", ["--sdm-guard=off"],
                          trellis, env=env)
        check(code == 0 and value == TRELLIS_REFERENCE_SHA256,
              "CLI overrides SOX_OPTS both ways", str(results[-1]))

        # Last explicit occurrence wins; both spaced and equals forms parse.
        for first, last in (("on", "off"), ("off", "on")):
            label = "last-option-" + first + "-" + last
            code, value = run(label, ["--sdm-guard=" + first,
                                      "--sdm-guard=" + last], trellis)
            check((code == 2 and value is None) if last == "on" else
                  (code == 0 and value == TRELLIS_REFERENCE_SHA256),
                  label, str(results[-1]))
        code, value = run("separate-option-value", ["--sdm-guard", "off"],
                          trellis)
        check(code == 0 and value == TRELLIS_REFERENCE_SHA256,
              "spaced --sdm-guard off", str(results[-1]))

        # Healthy channels: policy must not alter bit decisions or history.
        healthy = ["-R", "-r", "11289600", "-c", "2", "-n",
                   "-r", "11289600", "-c", "2", "{output}", "synth", "0.02",
                   "sine", "997", "sdm", "-f", "clans-4", "-t",
                   "3", "-n", "4", "-l", "100"]
        hashes = []
        for mode in (None, "on", "off"):
            name = "trellis-stable-" + (mode or "default")
            code, value = run(name, native_config(mode), healthy)
            check(code == 0 and value is not None, name, str(results[-1]))
            hashes.append(value)
        check(len(set(hashes)) == 1, "trellis healthy identity", str(hashes))

        for name, filter_name in (("normal-4", "clans-4"),
                                  ("normal-5", "sdm-5"),
                                  ("normal-6", "clans-6")):
            test = ["-R", "-r", "5644800", "-c", "1", "-n",
                    "-r", "5644800", "-c", "1", "{output}", "synth", "0.04",
                    "sine", "997", "sdm", "-f", filter_name]
            hashes = []
            for mode in (None, "on", "off"):
                label = name + "-" + (mode or "default")
                code, value = run(label, native_config(mode), test)
                check(code == 0 and value is not None, label, str(results[-1]))
                hashes.append(value)
            check(len(set(hashes)) == 1, name + " identity", str(hashes))

        # These full-path hashes were independently recorded from the 1.0.2
        # default (SSE2) build, not learned from a locally rebuilt target.
        # This catches FMA contraction in the generator as well as changes to
        # the legacy modulator's arithmetic and reduction order.
        reference = {
            "clans-4": "0b54f8fa3670cb9d1bdfd81018990ef491272c8ca210888b84b71507148804ce",
            "clans-6": "d9f1512e2548e14d0d9afabf84493e989aa2acb6949fdb952473fab45db9b4b2",
            "sdm-8": "c0b8012f33741b4c3faaf502e24815ad9f4a3ca62a28ed690b8b0440d032df06",
        }
        for filter_name, expected in reference.items():
            native = ["-R", "-r", "5644800", "-c", "2", "-n",
                      "-r", "5644800", "-c", "2", "{output}",
                      "synth", "2", "pinknoise", "gain", "-6",
                      "sdm", "-f", filter_name]
            for mode in (None, "on", "off"):
                label = "default-102-reference-" + filter_name + "-" + (mode or "default")
                code, value = run(label, native_config(mode), native)
                check(code == 0 and value == expected, label,
                      f"1.0.2 default reference mismatch: {results[-1]}")

        # Without an explicit sdm effect the legacy graph applies 1-bit dither
        # via dither.c -> sdm_init().  The global option must be accepted here.
        implicit = ["-R", "-r", "44100", "-c", "1", "-n",
                    "-r", "2822400", "-c", "1", "{output}", "synth", "0.03",
                    "sine", "997"]
        hashes = []
        for mode in (None, "on", "off"):
            label = "implicit-dither-" + (mode or "default")
            code, value = run(label, native_config(mode), implicit)
            check(code == 0 and value is not None, label, str(results[-1]))
            hashes.append(value)
        check(len(set(hashes)) == 1, "implicit dither identity", str(hashes))

        # The ordinary WAV -> DSF route uses rate -> dither -> sdm_init,
        # without an explicit sdm effect. Lock the 1.0.2 default reference:
        # the resampler must not change the modulator's PCM input under FMA.
        pcm = tmp / "reference-pink-44100.wav"
        pcm_command = [sox, "-R", "-n", "-r", "44100", "-c", "2", "-b", "24",
                       str(pcm), "synth", "2", "pinknoise", "gain", "-6"]
        pcm_result = subprocess.run(pcm_command, capture_output=True, timeout=90)
        check(pcm_result.returncode == 0 and pcm.is_file(),
              "1.0.2 input preparation", pcm_result.stderr.decode(errors="replace")[-500:])
        implicit_refs = {
            2822400: "1655f038e3476ce11508f8c8db5ec74c889a24141a9b168cf2350c62afdf5e54",
            5644800: "dcddf504d2c6fcc0bc8ec3894bf8d9cb63896b6c551676d94fa8a9f798d94429",
            11289600: "1ab239fd375e6a6c85e01286b8defdd37efa9c2d0019c5df9e218b762a0c88ed",
        }
        for rate, expected in implicit_refs.items():
            for mode in (None, "on", "off"):
                label = f"implicit-102-reference-{rate}-{mode or 'default'}"
                code, value = run(label, native_config(mode),
                                  ["-R", str(pcm), "-r", str(rate), "{output}"])
                check(code == 0 and value == expected, label,
                      f"1.0.2 default reference mismatch: {results[-1]}")

        for invalid in ("auto", "bogus", "fast", "", "ON"):
            label = "reject-" + (invalid or "empty")
            code, value = run(label, ["--sdm-guard=" + invalid], implicit)
            check(code != 0 and value is None, label, str(results[-1]))
            check("--sdm-guard must be on or off" in results[-1]["stderr"],
                  label, "missing diagnosis")

    evidence = {"schema": "sox-dsd-legacy-sdm-guard-policy/1",
                "binary_sha256": digest(Path(sox)),
                "tests": results, "passed": len(results), "failed": 0}
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"legacy SDM guard CLI tests: {len(results)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
