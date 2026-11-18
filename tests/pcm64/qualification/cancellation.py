#!/usr/bin/env python3
"""Real-signal cancellation checks for an opt-in Phase-08 instrumented SoX.

The five source/replay stage hooks are excluded from production binaries unless
SOX_P08_CANCEL_TEST_BUILD is defined at build time. Test input is deterministic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

STAGES = ("scan_capture", "scan_eof", "precommit", "replay", "replay_eof")
SIGNALS = ("SIGINT", "SIGTERM")
SENTINEL = b"PHASE08-PRESERVE-EXISTING-DESTINATION\n"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def require(ok: bool, explanation: str) -> None:
    if not ok:
        raise AssertionError(explanation)


def call(argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, timeout=90, env=env,
                          check=False)


def make_wav(path: Path) -> None:
    # 0.05 s of signed 16-bit PCM. Native64 ingestion uses exact rational scale.
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(b"".join(struct.pack("<hh",
            round(11000 * math.sin(2 * math.pi * 997 * frame / 48000)),
            round(9000 * math.sin(2 * math.pi * 1571 * frame / 48000)))
            for frame in range(2400)))


def run_all(sox: Path, results: Path) -> dict:
    sox = sox.resolve()
    require(sox.is_file() and os.access(sox, os.X_OK), "missing executable")
    results.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="p08-cancel-", dir=results) as scratch:
        root = Path(scratch)
        pcm = root / "source.wav"
        native = root / "source.dff"
        make_wav(pcm)
        generator = [str(sox), "-R", "--precision", "64", str(pcm),
                     "-r", "dsd64", str(native)]
        cp = call(generator)
        require(cp.returncode == 0 and native.is_file() and native.stat().st_size > 100,
                f"test source DSD generation failed ({cp.returncode}): {cp.stderr!r}")
        # This is a real physical, finalized DSD64 input, not an invented stream.
        inputs = {"encode": pcm, "transcode": native}
        source_hashes = {name: digest(path) for name, path in inputs.items()}
        for mode, source in inputs.items():
            for stage in STAGES:
                for signal_name in SIGNALS:
                    stem = f"{mode}-{stage}-{signal_name}"
                    destination = root / f"{stem}.dsf"
                    report = root / f"{stem}.json"
                    temporary = root / f"temporary-{stem}"
                    temporary.mkdir()
                    destination.write_bytes(SENTINEL)
                    env = dict(os.environ)
                    env.update({"SOX_P08_CANCEL_AT": stage,
                                "SOX_P08_CANCEL_SIGNAL": signal_name})
                    command = [str(sox), "-R", "--temp", str(temporary),
                               "--precision", "64", "--auto-headroom",
                               "--report", str(report), str(source),
                               "-r", "dsd64" if mode == "encode" else "dsd128",
                               str(destination)]
                    cp = call(command, env=env)
                    require(report.is_file(), f"{stem}: report absent, rc={cp.returncode}, stderr={cp.stderr[-1000:]!r}")
                    state = json.loads(report.read_text())
                    require(cp.returncode == 2 and state.get("status") == "cancelled",
                            f"{stem}: expected exit 2/cancelled, rc={cp.returncode} "+
                            f"status={state.get('status')!r}, stderr={cp.stderr[-1200:]!r}")
                    reason = state.get("failure_reason") or ""
                    require("cancel" in reason.lower() and
                            "cancel" in cp.stderr.decode("utf-8", "replace").lower(),
                            f"{stem}: not a recognized cancellation: {reason!r}; {cp.stderr[-900:]!r}")
                    before_output = stage in ("scan_capture", "scan_eof", "precommit")
                    remains = destination.is_file()
                    if before_output:
                        require(remains and destination.read_bytes() == SENTINEL,
                                f"{stem}: premature destination replacement/removal")
                        require("after commit" not in reason.lower() and
                                b"after commit" not in cp.stderr.lower(),
                                f"{stem}: reported precommit failure as after commit")
                    else:
                        require(not remains, f"{stem}: destination remains after post-open abort")
                    require(not tuple(temporary.iterdir()),
                            f"{stem}: spool/temp files leaked: {list(temporary.iterdir())}")
                    rows.append({"name": stem, "mode": mode, "stage": stage,
                        "signal": signal_name, "exit_code": cp.returncode,
                        "status": state["status"], "failure_reason": reason,
                        "destination_preserved": before_output,
                        "destination_removed": not before_output,
                        "temporary_entries": 0,
                        "command": command, "stderr": cp.stderr.decode("utf-8", "replace"),
                        "report_sha256": digest(report),
                        "input_sha256": source_hashes[mode]})
    require(len(rows) == 20, "case count incomplete")
    return {"suite": "phase08-cancellation", "status": "PASS",
            "commit": safe_revision(sox),
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sox_elf_sha256": digest(sox),
            "stage_hooks": "compiled only with SOX_P08_CANCEL_TEST_BUILD",
            "expected_cases": 20, "tested_cases": len(rows), "results": rows}


def safe_revision(sox: Path) -> str | None:
    # An instrumented build can be in its own configured source clone.
    directory = sox.parent.parent
    p = call(["git", "-C", str(directory), "rev-parse", "HEAD"])
    return p.stdout.decode().strip() if p.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sox", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    path = args.results / "cancellation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    try:
        record = run_all(args.sox, args.results)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"PASS phase08-cancellation: {record['tested_cases']} SIGINT/SIGTERM stage cases")
        return 0
    except Exception as exc:
        record = {"suite": "phase08-cancellation", "status": "FAIL",
                  "error": f"{type(exc).__name__}: {exc}"}
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(record["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
