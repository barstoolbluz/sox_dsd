#!/usr/bin/env python3
"""Paired full-file Phase05B development throughput/RSS comparison.

Identical hand-constructed DSF bytes, reconstruction profile, FIR kernel and
output encoding are used for the legacy and native runs. No claim is made that
legacy's signed-int32 intermediate has the same numerical output as F64.
This is a host-specific preliminary benchmark, not a release performance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/dsd/reference"))
import fixtures


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(path: Path, rate: int, seconds: float, channels: int = 2) -> int:
    """Repeat a deterministic 4096-byte/channel DSF block; no PCM encoder."""
    count = max(1, round(seconds * rate / (8*fixtures.BLOCK)))
    one = fixtures.make_dsf(fixtures.bits(8*fixtures.BLOCK,channels,"distinct"),rate)
    block = one[92:]
    header = bytearray(one[:92])
    total_frames = count * 8 * fixtures.BLOCK
    struct.pack_into("<Q", header, 12, 92 + count*len(block))
    struct.pack_into("<Q", header, 64, total_frames)
    struct.pack_into("<Q", header, 84, 12 + count*len(block))
    path.write_bytes(header + block*count)
    return total_frames


def measure(sox: Path, source: Path, native: int, policy: str,
            kernel: str, threaded: bool) -> dict:
    profile = f"decode.mastering.v2.dsd{64 if native==fixtures.DSD64 else 128}"
    argv = [str(sox), "--precision",policy,"--decode",profile,
            "--dsd-level","preserve","--dsd-bandwidth","adapt",
            "--multi-threaded" if threaded else "--single-threaded",
            "-q","-D",str(source),"-b","64","-e","floating-point",
            "-r","96000","-t","wav","-"]
    env = dict(os.environ, SOX_DSD_KERNEL_FIR=kernel,
               SOX_DSD_PACKED_INPUT="0", OMP_NUM_THREADS="4" if threaded else "1")
    with tempfile.TemporaryDirectory(prefix="p05b-time-") as d:
        clock = Path(d) / "time.txt"
        # /dev/null preserves the exact stdout WAV writer behavior while
        # omitting output disk bandwidth and memory-retained captures.
        timer = ["/usr/bin/time","-f","%e %U %S %M","-o",str(clock)]
        with open(os.devnull,"wb") as null:
            started = time.perf_counter()
            run = subprocess.run(timer+argv,env=env,stdout=null,
                                 stderr=subprocess.PIPE,timeout=240,check=False)
            wall = time.perf_counter()-started
        if run.returncode:
            raise RuntimeError(f"{policy}/{kernel}/{threaded}: {run.stderr[-500:]!r}")
        values = clock.read_text().strip().split()
        if len(values)!=4:
            raise RuntimeError("/usr/bin/time did not supply wall/user/sys/RSS")
        return {"policy":policy,"kernel":kernel,"threaded_option":threaded,
                "env_omp_num_threads":env["OMP_NUM_THREADS"],
                "command":argv,"native_source_sha256":sha(source),
                "wall_seconds":float(values[0]),"user_seconds":float(values[1]),
                "sys_seconds":float(values[2]),"peak_rss_kib":int(values[3]),
                "monotonic_wall_seconds":wall,"exit_code":run.returncode}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sox",type=Path,required=True)
    ap.add_argument("--results",type=Path,required=True)
    ap.add_argument("--seconds",type=float,default=3.0)
    ap.add_argument("--repetitions",type=int,default=2)
    args = ap.parse_args()
    if not 0.25<=args.seconds<=120 or not 1<=args.repetitions<=10:
        ap.error("seconds must be 0.25..120, repetitions 1..10")
    if not Path("/usr/bin/time").is_file():
        ap.error("GNU /usr/bin/time is required for reliable maximum RSS")
    args.results.mkdir(parents=True,exist_ok=True)
    result = {"phase":"05B","status":"RUNNING", "host":platform.platform(),
              "cpu":platform.processor() or platform.machine(),
              "sox_sha256":sha(args.sox),
              "comparison_scope":"same DSF source/profile/kernel/output encoding; different arithmetic routes",
              "threading_caveat":"--multi-threaded requests SoX channel effects threads; it does not prove the native decoder ran threads",
              "qualification":"PRELIMINARY, NOT a formal throughput regression certification",
              "samples":[],"paired_summary":[]}
    receipt=args.results/"performance.json"
    try:
        for hz in (fixtures.DSD64,2*fixtures.DSD64):
            source=args.results/f"bench-{hz}.dsf"
            frames=vector(source,hz,args.seconds)
            for kernel in ("scalar","auto"):
                for threaded in (False,True):
                    grouped={}
                    for policy in ("auto","64"):
                        runs = [measure(args.sox,source,hz,policy,kernel,threaded)
                                for _ in range(args.repetitions)]
                        for r in runs:
                            r["native_hz"]=hz;r["source_frames"]=frames
                            r["native_frames_per_second"]=(frames/r["monotonic_wall_seconds"])
                            result["samples"].append(r)
                        grouped[policy]=runs
                        receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
                    a=grouped["auto"];b=grouped["64"]
                    result["paired_summary"].append({
                        "native_hz":hz,"kernel":kernel,"threaded_option":threaded,
                        "source_frames":frames,
                        "legacy_median_wall_s":statistics.median(r["monotonic_wall_seconds"] for r in a),
                        "native64_median_wall_s":statistics.median(r["monotonic_wall_seconds"] for r in b),
                        "legacy_peak_rss_kib_max":max(r["peak_rss_kib"] for r in a),
                        "native64_peak_rss_kib_max":max(r["peak_rss_kib"] for r in b),
                        "native64_vs_legacy_throughput_ratio":statistics.median(
                            r["monotonic_wall_seconds"] for r in a) / statistics.median(
                            r["monotonic_wall_seconds"] for r in b)})
        result["status"]="PASS"
    finally:
        receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(f"Phase05B throughput PASS: {len(result['samples'])} real full-decode executions, "
          f"{len(result['paired_summary'])} paired comparisons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
