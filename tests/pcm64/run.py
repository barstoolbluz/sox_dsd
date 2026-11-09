#!/usr/bin/env python3
"""Fail-closed independent dyadic oracle for the private PCM64 foundation.

All PCM values are constructed from IEEE-754 integer payloads, not SoX output.
Do not replace Fraction arithmetic with Python double rounding of half ties.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
from fractions import Fraction

SEED = 0x2026110901


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, input=input_text, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)


def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def ieee_word(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def from_word(bits: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def finite_words():
    rng = random.Random(SEED)
    words = {
        0, 1, (1 << 52)-1, 1 << 52, (1 << 52)+1,
        0x001fffffffffffff, 0x3fefffffffffffff, 0x3ff0000000000000,
        0x3ff0000000000001, 0x4000000000000000,
        0x7fefffffffffffff, 0x7fe0000000000000,
    }
    for power in [1, -1, -2, -8, -24, -31, -32, -40, -53, -80, -500, -1022, -1074]:
        v = math.ldexp(1.0, power)
        for v in (v, math.nextafter(v, 0.0), math.nextafter(v, math.inf)):
            words.add(ieee_word(v))
    for bits in (8, 16, 24, 32):
        h = math.ldexp(1.0, -bits)
        for x in (h, math.nextafter(h, 0.0), math.nextafter(h, math.inf),
                  1.0, math.nextafter(1.0, 0.0), math.nextafter(1.0, math.inf)):
            words.add(ieee_word(x))
    # Every finite exponent class, endpoints and independent mantissas.
    for exp in range(0x7ff):
        for mant in (0, (1 << 52)-1, rng.getrandbits(52)):
            words.add((exp << 52) | mant)
    for _ in range(1600):
        words.add(rng.getrandbits(63) & ~((0x7ff) << 52) | (rng.randrange(0x7ff) << 52))
    return sorted(words | {x | (1 << 63) for x in words})


def quant_oracle(bits: int, x: float) -> tuple[int, bool, bool]:
    signed = Fraction.from_float(x)
    negative = math.copysign(1.0, x) < 0
    limit = 1 << (bits - 1)
    scaled = abs(signed) * limit
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    magnitude = whole + (2 * rem >= scaled.denominator)
    q = -magnitude if negative else magnitude
    saturated = q < -limit or q >= limit
    q = max(-limit, min(limit-1, q))
    aligned = (q * (1 << (32 - bits))) & 0xffffffff
    nominal = signed >= 1 or signed < -1
    return aligned, saturated, nominal


def run_stream(probe: Path, jobs: list[tuple[str, str]], counts: dict):
    req = "".join(query + "\n" for query, expected in jobs)
    completed = run([str(probe), "--stream"], input_text=req)
    assert_true(completed.returncode == 0,
                f"stream process failed ({completed.returncode}): {completed.stderr[:1000]}")
    lines = completed.stdout.splitlines()
    assert_true(len(lines) == len(jobs),
                f"zero, missing or extra tests: received {len(lines)}, expected {len(jobs)}")
    for i, ((query, expected), actual) in enumerate(zip(jobs, lines)):
        if actual != expected:
            raise AssertionError(f"case {i}: {query}: expected {expected!r}, got {actual!r}")
    counts["stream_cases"] = len(jobs)
    counts["stream_stderr_bytes"] = len(completed.stderr)


def generate_jobs(counts: dict):
    rng = random.Random(SEED ^ 0xfeedcab)
    jobs = []
    words = finite_words()
    counts["finite_input_words"] = len(words)
    for bits in (8, 16, 24, 32):
        for u in words:
            aligned, saturation, nominal = quant_oracle(bits, from_word(u))
            jobs.append((f"Q {bits} {u:016x}",
                         f"Q {aligned:08x} {int(saturation)} {int(nominal)}"))
    counts["quantizer_cases"] = len(words) * 4
    for bits in (8, 16, 24, 32):
        bound = 1 << (bits - 1)
        codes = {-bound, -bound+1, -bound//2, -1, 0, 1, bound//2, bound-2, bound-1}
        for _ in range(240):
            codes.add(rng.randrange(-bound, bound))
        for code in sorted(codes):
            f64 = float(Fraction(code, bound))
            jobs.append((f"N {bits} {code}", f"N {ieee_word(f64):016x}"))
        counts[f"signed{bits}_cases"] = len(codes)
    for code in range(256):
        f64 = float(Fraction(code-128, 128))
        jobs.append((f"U {code}", f"U {ieee_word(f64):016x}"))
    counts["u8_cases"] = 256
    aligned_codes = {-(1 << 31), -(1 << 31)+1, -1, 0, 1, (1 << 31)-1}
    for _ in range(500):
        aligned_codes.add(rng.randrange(-(1 << 31), (1 << 31)))
    for code in sorted(aligned_codes):
        f64 = float(Fraction(code, 1 << 31))
        jobs.append((f"A {code}", f"A {ieee_word(f64):016x}"))
    counts["aligned32_cases"] = len(aligned_codes)
    for u in words:
        jobs.append((f"C {u:016x}", "C 0"))
    nonfinite = {
        0x7ff0000000000000: 1,
        0xfff0000000000000: 1,
        0x7ff8000000000001: 2,
        0xfff800000000dead: 2,
        0x7ff0000000000001: 3,
        0xfff0000000000001: 3,
        0x7ff7ffffffffffff: 3,
    }
    for u, cls in nonfinite.items():
        jobs.append((f"C {u:016x}", f"C {cls}"))
        for bits in (8, 16, 24, 32):
            jobs.append((f"Q {bits} {u:016x}", "ERR NUMERIC"))
    counts["classifier_cases"] = len(words) + len(nonfinite)
    gain1 = ieee_word(1.0)
    for u in words[::max(1, len(words)//2000)]:
        jobs.append((f"G {gain1:016x} {u:016x}", f"G {u:016x}"))
    for x in (0.0, -0.0, 0.5, -0.5, 1.25, -1.25, 2.0, -2.0,
              math.ldexp(1.0, -40), math.ldexp(-1.0, -80),
              math.ldexp(1.0, -1022)):
        for gain in (0.0, -1.0, 0.5, 2.0):
            expected = ieee_word(x * gain)
            jobs.append((f"G {ieee_word(gain):016x} {ieee_word(x):016x}",
                         f"G {expected:016x}"))
    counts["gain_cases"] = sum(1 for q, _ in jobs if q.startswith("G "))
    return jobs


def run_all(sox: Path, probe: Path, results: Path):
    assert_true(sox.is_file() and os.access(sox, os.X_OK), "SoX executable missing")
    assert_true(probe.is_file() and os.access(probe, os.X_OK), "probe executable missing")
    counts: dict[str, int] = {}
    cp = run([str(probe), "--selftest"])
    assert_true(cp.returncode == 0 and "status=PASS" in cp.stdout,
                f"private C invariants failed: rc={cp.returncode} {cp.stderr} {cp.stdout}")
    counts["c_assertions"] = int(cp.stdout.split("assertions=")[1].split()[0])
    assert_true(counts["c_assertions"] > 50, "zero or stale C selftest selection")
    env = run([str(probe), "--environment"])
    assert_true(env.returncode == 0 and "ENV workers=" in env.stdout,
                f"fenv/worker test failed: rc={env.returncode} {env.stderr} {env.stdout}")
    counts["environment_assertions"] = int(env.stdout.split("assertions=")[1].split()[0])
    assert_true(counts["environment_assertions"] >= 18,
                "fenv controls not sufficiently exercised")
    jobs = generate_jobs(counts)
    assert_true(len(jobs) > 1000, "test set is empty or incomplete")
    run_stream(probe, jobs, counts)

    # Independent negative: the common old abs(s)*scale+0.5 method incorrectly
    # rounds the immediate predecessor to the positive half-quantizer step.
    for bits in (24, 32):
        x = math.nextafter(math.ldexp(1.0, -bits), 0.0)
        naive = math.floor(abs(x) * (1 << (bits - 1)) + 0.5)
        correct = quant_oracle(bits, x)
        assert_true(naive == 1 and correct[0] == 0,
                    f"half-step mutation was not detected at {bits} bits")
    counts["halfstep_negative_controls"] = 2
    zero = run([str(probe), "--stream"], input_text="")
    unknown = run([str(probe), "--no-such-mode"])
    assert_true(zero.returncode != 0 and unknown.returncode != 0,
                "probe accepted empty input or unknown suite")
    counts["fail_closed_negative_controls"] = 2

    source = Path(__file__).resolve().parents[2]
    core_paths = [source / "src/pcm_f64.c", source / "src/pcm_f64.h",
                  source / "configure.ac", source / "src/Makefile.am",
                  source / "test/Makefile.am", source / "Makefile.am",
                  source / "test/pcm64_probe", source / "src/sox"]
    for path in core_paths:
        assert_true(path.is_file(), f"required input absent: {path}")
    revision = run(["git", "-C", str(source), "rev-parse", "HEAD"])
    record = {
        "suite": "foundation",
        "status": "PASS",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_directory": str(source),
        "source_git_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "sox_version": run([str(sox), "--version"]).stdout.strip(),
        "command": [sys.executable, str(Path(__file__).resolve()), "--suite", "foundation",
                    "--sox", str(sox), "--probe", str(probe), "--results", str(results)],
        "actual_checks": counts,
        "fenv_result": env.stdout.strip(),
        "c_selftest_result": cp.stdout.strip(),
        "source_and_binary_sha256": {str(p.relative_to(source)): sha256(p) for p in core_paths},
        "python": sys.version,
        "platform": sys.platform,
        "seed": SEED,
        "float_oracle": "Fraction.from_float raw IEEE dyadic, integer divmod, nearest ties away",
    }
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--sox", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    results = args.results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    output = results / (args.suite.replace("/", "_") + ".json")
    output.unlink(missing_ok=True)     # never reuse a stale receipt on failure
    if args.suite != "foundation":
        parser.error(f"suite {args.suite!r} is not implemented (nonzero selection required)")
    try:
        record = run_all(args.sox.resolve(), args.probe.resolve(), results)
    except Exception as exc:
        failure = {"suite": args.suite, "status": "FAIL",
                   "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "error": f"{type(exc).__name__}: {exc}"}
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        print(f"FAIL foundation: {failure['error']}", file=sys.stderr)
        return 1
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"PASS foundation: {record['actual_checks']}; bound to {record['source_git_commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
