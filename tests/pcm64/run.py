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
from binary_receipts import executable_libraries

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


def run_stream(probe: Path, jobs: list[tuple[str, str]], counts: dict, run_command=run):
    req = "".join(query + "\n" for query, expected in jobs)
    completed = run_command([str(probe), "--stream"], input_text=req)
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


def run_all(sox: Path, probe: Path, results: Path, executed: dict[str, str]):
    assert_true(sox.is_file() and os.access(sox, os.X_OK), "SoX executable missing")
    assert_true(probe.is_file() and os.access(probe, os.X_OK), "probe executable missing")

    def run_test(command: list[str], *, input_text: str | None = None):
        # Bind the exact executable selected by --probe, not a same-named
        # binary in the source tree. Retain identities even on suite failure.
        path = Path(command[0])
        if path in (probe, sox) and str(path) not in executed:
            executed[str(path)] = sha256(path)
            executed.update(executable_libraries(path))
        return run(command, input_text=input_text)

    counts: dict[str, int] = {}
    cp = run_test([str(probe), "--selftest"])
    assert_true(cp.returncode == 0 and "status=PASS" in cp.stdout,
                f"private C invariants failed: rc={cp.returncode} {cp.stderr} {cp.stdout}")
    counts["c_assertions"] = int(cp.stdout.split("assertions=")[1].split()[0])
    assert_true(counts["c_assertions"] > 50, "zero or stale C selftest selection")
    env = run_test([str(probe), "--environment"])
    assert_true(env.returncode == 0 and "ENV workers=" in env.stdout,
                f"fenv/worker test failed: rc={env.returncode} {env.stderr} {env.stdout}")
    fields = dict(part.split("=", 1) for part in env.stdout.split() if "=" in part)
    assert_true(set(fields) == {"workers", "mxcsr", "x87", "status", "assertions"},
                f"environment probe did not report every gate: {env.stdout!r}")
    counts["environment_assertions"] = int(fields["assertions"])
    assert_true(fields["status"] in ("OK", "UNSUPPORTED"),
                f"unexpected environment status: {fields['status']}")
    assert_true(fields["workers"] in ("3", "UNSUPPORTED") and
                fields["mxcsr"] in ("PASS", "NOT_RUN") and
                fields["x87"] in ("PASS", "NOT_RUN"),
                f"invalid environment qualification: {env.stdout!r}")
    assert_true(fields["mxcsr"] == fields["x87"],
                "register checks must run or be omitted together")
    gates = {
        "portable_fenv_rounding": "PASS",
        "worker_fenv_isolation": ("PASS" if fields["workers"] == "3"
                                  else "NOT_RUN: pthread worker checks not compiled"),
        "mxcsr_control_mutations": ("PASS" if fields["mxcsr"] == "PASS"
                                    else "NOT_RUN: x86 SSE2 register checks not compiled"),
        "x87_control_mutations": ("PASS" if fields["x87"] == "PASS"
                                  else "NOT_RUN: x86 SSE2 register checks not compiled"),
    }
    if fields["status"] == "UNSUPPORTED":
        assert_true(fields["workers"] == "UNSUPPORTED" and
                    fields["mxcsr"] == "NOT_RUN",
                    "compiled-out native DSP guard cannot qualify environment gates")
        gates = {name: "NOT_RUN: native binary64 DSP guard unavailable"
                 for name in gates}
    assert_true(counts["environment_assertions"] >= 18,
                "fenv controls not sufficiently exercised")
    jobs = generate_jobs(counts)
    assert_true(len(jobs) > 1000, "test set is empty or incomplete")
    run_stream(probe, jobs, counts, run_test)

    # Independent negative: the common old abs(s)*scale+0.5 method incorrectly
    # rounds the immediate predecessor to the positive half-quantizer step.
    for bits in (24, 32):
        x = math.nextafter(math.ldexp(1.0, -bits), 0.0)
        naive = math.floor(abs(x) * (1 << (bits - 1)) + 0.5)
        correct = quant_oracle(bits, x)
        assert_true(naive == 1 and correct[0] == 0,
                    f"half-step mutation was not detected at {bits} bits")
    counts["halfstep_negative_controls"] = 2
    zero = run_test([str(probe), "--stream"], input_text="")
    unknown = run_test([str(probe), "--no-such-mode"])
    assert_true(zero.returncode == 2 and unknown.returncode == 2,
                f"probe refusal exit mismatch: empty={zero.returncode}, unknown={unknown.returncode}; "
                "expected 2 (not an unrelated failure or signal)")
    counts["fail_closed_negative_controls"] = 2

    source = Path(__file__).resolve().parents[2]
    core_paths = [source / "src/pcm_f64.c", source / "src/pcm_f64.h",
                  source / "tests/pcm64/pcm64_probe.c", source / "tests/pcm64/run.py",
                  source / "tests/pcm64/binary_receipts.py",
                  source / "configure.ac", source / "src/Makefile.am",
                  source / "test/Makefile.am", source / "Makefile.am"]
    for path in core_paths:
        assert_true(path.is_file(), f"required input absent: {path}")
    try:
        revision = run(["git", "-C", str(source), "rev-parse", "HEAD"])
    except FileNotFoundError:
        revision = subprocess.CompletedProcess([], 127, "", "git not installed")
    record = {
        "suite": "foundation",
        "status": ("PASS_WITH_NOT_RUN" if any(v.startswith("NOT_RUN")
                   for v in gates.values()) else "PASS"),
        "gate_execution": gates,
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_directory": str(source),
        "source_git_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "sox_version": run_test([str(sox), "--version"]).stdout.strip(),
        "command": [sys.executable, str(Path(__file__).resolve()), "--suite", "foundation",
                    "--sox", str(sox), "--probe", str(probe), "--results", str(results)],
        "actual_checks": counts,
        "fenv_result": env.stdout.strip(),
        "c_selftest_result": cp.stdout.strip(),
        "source_and_binary_sha256": {
            **{str(p.relative_to(source)): sha256(p) for p in core_paths},
            "test/pcm64_probe": executed[str(probe)],
            "src/sox": executed[str(sox)],
        },
        "executed_binary_sha256": dict(executed),
        "python": sys.version,
        "platform": sys.platform,
        "seed": SEED,
        "float_oracle": "Fraction.from_float raw IEEE dyadic, integer divmod, nearest ties away",
    }
    return record


def io_main_wrapper(io_main, args):
    previous = sys.argv
    try:
        sys.argv = [str(Path(__file__).with_name("io_wav.py")),
                    "--sox", str(args.sox),
                    "--probe", str(Path(args.probe).with_name("pcm64_wav_probe")),
                    "--results", str(args.results)]
        return io_main()
    finally:
        sys.argv = previous


def flac_main_wrapper(flac_main, args):
    previous = sys.argv
    try:
        sys.argv = [str(Path(__file__).with_name("io_flac.py")),
                    "--sox", str(args.sox),
                    "--probe", str(Path(args.probe).with_name("pcm64_flac_probe")),
                    "--results", str(args.results)]
        return flac_main()
    finally:
        sys.argv = previous


def safe_git_head(source):
    try:
        result = run(["git", "-C", str(source), "rev-parse", "HEAD"])
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, OSError):
        return None


def aggregate_io(args, results, output):
    # Persist independent suite results first.  A child's NOT_RUN or FAIL
    # cannot be converted to PASS by an unrelated successful child.
    children = []
    for suite in ("io-wav", "io-flac"):
        command = [sys.executable, str(Path(__file__).resolve()), "--suite", suite,
                   "--sox", str(args.sox), "--probe", str(args.probe),
                   "--results", str(results)]
        cp = run(command)
        path = results / (suite + ".json")
        try:
            receipt = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            receipt = {"suite":suite,"status":"FAIL",
                       "error":f"child receipt unavailable: {exc}"}
        children.append({"suite":suite,"returncode":cp.returncode,
                         "status":receipt.get("status"),
                         "stdout":cp.stdout[-4000:],"stderr":cp.stderr[-4000:],
                         "receipt":receipt})
    ok = all(c["returncode"] == 0 or
             (c["returncode"] == 2 and c["status"] == "NOT_RUN")
             for c in children)
    ok &= all(c["status"] in ("PASS", "PASS_WITH_NOT_RUN", "NOT_RUN")
              for c in children)
    skipped = any(c["status"] != "PASS" for c in children)
    executed = {}
    inputs = {}
    for c in children:
        executed.update(c["receipt"].get("executed_binary_sha256", {}))
        inputs.update(c["receipt"].get("source_and_binary_sha256", {}))
    record = {
        "suite":"io", "status":("FAIL" if not ok else
                 "PASS_WITH_NOT_RUN" if skipped else "PASS"),
        "utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_git_commit":safe_git_head(Path(__file__).resolve().parents[2]),
        "children": [{k:v for k,v in c.items() if k != "receipt"} for c in children],
        "gate_execution": {f"{c['suite']}.{name}": value for c in children
                           for name,value in c["receipt"].get("gate_execution", {}).items()},
        "checks":{c["suite"]:c["receipt"].get("checks", c["receipt"].get("completed_checks", {}))
                  for c in children},
        "executed_binary_sha256":executed,
        "source_and_binary_sha256":inputs,
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"{record['status']} io: " + ", ".join(
        c['suite'] + "=" + str(c['status']) for c in children))
    return 0 if ok else 1


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
    if args.suite not in ("foundation", "io-wav", "io-flac", "io", "large-wav", "routing"):
        parser.error(f"suite {args.suite!r} is not implemented (nonzero selection required)")
    if args.suite == "io":
        return aggregate_io(args, results, output)
    if args.suite == "routing":
        from routing import main as routing_main
        return io_main_wrapper(routing_main, args)
    if args.suite == "io-wav":
        from io_wav import main as io_main
        return io_main_wrapper(io_main, args)
    if args.suite == "large-wav":
        from large_wav import main as large_wav_main
        return io_main_wrapper(large_wav_main, args)
    if args.suite == "io-flac":
        from io_flac import main as flac_main
        return flac_main_wrapper(flac_main, args)
    executed: dict[str, str] = {}
    try:
        record = run_all(args.sox.resolve(), args.probe.resolve(), results, executed)
    except Exception as exc:
        failure = {"suite": args.suite, "status": "FAIL",
                   "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "error": f"{type(exc).__name__}: {exc}",
                   "executed_binary_sha256": dict(executed),
                   "source_and_binary_sha256": {
                       ("test/pcm64_probe" if path == str(args.probe.resolve())
                        else "src/sox"): content_hash
                       for path, content_hash in executed.items()}}
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        print(f"FAIL foundation: {failure['error']}", file=sys.stderr)
        return 1
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"{record['status']} foundation: {record['actual_checks']}; bound to {record['source_git_commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
