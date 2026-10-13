#!/usr/bin/env python3
"""Audit *recorded* P10/P15 commercial-corpus continuity, including channels.

This deliberately does not synthesize evidence about unavailable audio, prove
an encoded-bitstream match, or qualify P15 release defaults. Requires only
Python's standard library; output is deterministic and atomically replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OLD = ROOT / "tests/dsd/results/P10_realworld_corpus_2026-10-10"
DEFAULT_NEW = ROOT / "tests/dsd/results/P15_corpus_independent_material_2026-10-13/dsd"
ARMS = {"unity": ("corpus-unity.json", 18),
        "attenuated": ("corpus-attenuated.json", 18),
        "ladder": ("corpus-ladder.json", 4)}
COMMON = ("admitted", "encode_exit", "excerpt_sha256", "excerpt_seconds",
          "native_hz", "working_hz", "explicit_gain_db", "expected_frames",
          "frames_exact", "output_bytes", "output_channels", "output_frames",
          "output_rate", "peak_delta_db", "rms_delta_db",
          "source_excerpt_level", "remodulated_level", "windows28",
          "population_within_4_24")
CHANNEL = ("min_ones", "max_ones", "windows", "ones_fraction")


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def index(path: Path, expected: int) -> dict[tuple[str, int], dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f"{path}: expected {expected} entries")
    data = {}
    for row in rows:
        key = (row["source"], row["native_hz"])
        if key in data:
            raise ValueError(f"duplicate source/rate in {path}: {key}")
        data[key] = row
    return data


def validate(row: dict, arm: str, key: tuple[str, int], label: str, errors: list[str]) -> None:
    ident = f"{arm}/{key}/{label}"
    if not row.get("excerpt_sha256") or len(row["excerpt_sha256"]) != 64:
        errors.append(f"{ident}: no excerpt SHA-256")
    if row.get("admitted") is not True:
        return
    ch = row.get("per_channel")
    if not isinstance(ch, list) or not ch:
        errors.append(f"{ident}: admitted recording has no channel accounting")
        return
    try:
        count = row["output_frames"]
        if (row["frames_exact"] is not True or count != row["expected_frames"] or
                row["population_within_4_24"] is not True or
                len(ch) != row["output_channels"] or
                row["windows28"] != sum(c["windows"] for c in ch) or
                row["min_ones28"] != min(c["min_ones"] for c in ch) or
                row["max_ones28"] != max(c["max_ones"] for c in ch)):
            errors.append(f"{ident}: inconsistent frames/channel/window record")
        for i, c in enumerate(ch):
            if c["channel"] != i or c["windows"] != count - 27 or not (
                    4 <= c["min_ones"] <= c["max_ones"] <= 24):
                errors.append(f"{ident}: channel {i} violates 28-bit contract")
    except (KeyError, TypeError, ValueError) as e:
        errors.append(f"{ident}: invalid channel stats: {e}")


def run(old_dir: Path, new_dir: Path) -> dict:
    errors: list[str] = []
    changes: list[dict] = []
    scope: list[dict] = []
    source_keys: set[tuple[str, int]] = set()
    hashes = {}
    total = 0
    for arm, (filename, expected) in ARMS.items():
        old_path, new_path = old_dir / filename, new_dir / filename
        hashes[arm] = {"P10": digest(old_path), "P15": digest(new_path)}
        a = index(old_path, expected)
        b = index(new_path, expected)
        if a.keys() != b.keys():
            errors.append(f"{arm}: source/rate set changed: "
                          f"removed={sorted(a.keys()-b.keys())} added={sorted(b.keys()-a.keys())}")
        total += len(a)
        for key in sorted(a.keys() & b.keys()):
            x, y = a[key], b[key]
            source_keys.add(key)
            ident = f"{arm}/{key[0]} ({key[1]} Hz)"
            validate(x, arm, key, "P10", errors)
            validate(y, arm, key, "P15", errors)
            for field in COMMON:
                if x.get(field) != y.get(field):
                    errors.append(f"{ident}: changed common field {field}: "
                                  f"{x.get(field)!r} -> {y.get(field)!r}")
            if x.get("original_bytes", x.get("source_bytes")) != y.get("source_bytes"):
                errors.append(f"{ident}: original source byte count differs")
            if y.get("staged") is not True:
                errors.append(f"{ident}: current excerpt was not staged")
            if x.get("admitted") is True and y.get("admitted") is True:
                for field in ("min_ones28", "max_ones28"):
                    if x[field] != y[field]:
                        if abs(x[field] - y[field]) > 1:
                            errors.append(f"{ident}: >1-bit aggregate extremum change ({field})")
                        changes.append({"arm": arm, "source": key[0],
                                        "native_hz": key[1], "channel": None,
                                        "field": field, "P10": x[field], "P15": y[field]})
                if x["output_channels"] == y["output_channels"]:
                    for u, v in zip(x["per_channel"], y["per_channel"]):
                        for field in CHANNEL:
                            if u[field] != v[field]:
                                if field not in ("min_ones", "max_ones"):
                                    errors.append(f"{ident}: nonextremum channel metric {field} changed")
                                elif abs(u[field] - v[field]) > 1:
                                    errors.append(f"{ident}: >1-bit channel {u['channel']} extremum change ({field})")
                                changes.append({"arm": arm, "source": key[0],
                                                "native_hz": key[1],
                                                "channel": u["channel"],
                                                "field": field, "P10": u[field],
                                                "P15": v[field]})
            if arm == "ladder":
                if x.get("admitting_gain_db") != y.get("admitting_gain_db"):
                    errors.append(f"{ident}: changed admitting ladder gain")
                if x.get("ladder_exhausted") != y.get("ladder_exhausted"):
                    errors.append(f"{ident}: changed ladder exhaustion")
                old_attempts = {t["gain_db"]: t["admitted"] for t in x["ladder_attempts"]}
                new_attempts = {t["gain_db"]: t["admitted"] for t in y["ladder_attempts"]}
                for gain, result in new_attempts.items():
                    if old_attempts.get(gain) != result:
                        errors.append(f"{ident}: changed ladder trial at {gain} dB")
                if set(new_attempts) != set(old_attempts):
                    scope.append({"arm": arm, "source": key[0],
                                  "native_hz": key[1],
                                  "P10_trial_gains_db": list(old_attempts),
                                  "P15_trial_gains_db": list(new_attempts)})
    pairs = {(c["arm"], c["source"], c["native_hz"]) for c in changes}
    summary = {"records_compared": total, "source_rate_identities": len(source_keys),
               "changed_numeric_fields": len(changes),
               "arm_source_pairs_with_changed_extrema": len(pairs),
               "sources_with_changed_extrema": len({c["source"] for c in changes}),
               "ladder_trial_scope_differences": len(scope), "errors": len(errors)}
    return {"schema": "P15/P10-P15-commercial-corpus-adjudication/1",
            "status": "PASS-BOUNDED-DRIFT" if not errors else "FAIL",
            "scope": "Comparison of previously recorded manifests; commercial audio not supplied",
            "not_evidence_for": ["re-encoding the private recordings", "raw DSD byte equality",
                                 "cross-ISA encode identity", "P15 release qualification"],
            "hashes": hashes, "summary": summary,
            "numeric_extrema_changes": changes,
            "ladder_trial_scope_differences": scope, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p10", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--p15", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.p10, args.p15)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Corpus comparison could not complete: {exc}", file=sys.stderr)
        return 2
    args.results.mkdir(parents=True, exist_ok=True)
    output = args.results / "comparison.json"
    temp = output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")
    os.replace(temp, output)
    print(json.dumps({"status": report["status"], "summary": report["summary"],
                      "report": str(output)}, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
