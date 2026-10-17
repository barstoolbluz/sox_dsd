#!/usr/bin/env python3
"""Summarize the three-arm, real-FIFO C timing output; no audio processing."""
import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path


def dispersion(values):
    median = statistics.median(values)
    return {"median": median,
            "mad": statistics.median(abs(x - median) for x in values),
            "min": min(values), "max": max(values)}


def compare(rows, baseline, candidate, rng):
    ratios = [r[baseline]["cpu_seconds"] / r[candidate]["cpu_seconds"]
              for r in rows]
    resampled = sorted(statistics.median(rng.choices(ratios, k=len(ratios)))
                       for _ in range(4000))
    return {"speedup": dispersion(ratios),
            "paired_median_bootstrap_ci95": [resampled[100], resampled[3899]],
            "bootstrap_repetitions": 4000}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    raw_path = args.directory / "timing.jsonl"
    metadata = json.loads((args.directory / "metadata.json").read_text())
    raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
    rng = random.Random(20261017)
    summary = {"schema": "production-src-opt/real-fifo-summary/1",
               "status": "PASS" if metadata["complete"] else "INCOMPLETE",
               "qualification": "Session virtual host, same executable, stage only; no prepared-host qualification. Intervals describe this run's repeat variation.",
               "metadata": metadata,
               "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
               "raw_rows": len(raw), "cases": []}
    for case in sorted({row["case"] for row in raw}):
        all_rows = [r for r in raw if r["case"] == case]
        measured = [r for r in all_rows if not r["warmup"]]
        paired = [{r["variant"]: r for r in measured if r["repeat"] == repeat}
                  for repeat in sorted({r["repeat"] for r in measured})]
        assert len(paired) == 15
        assert all(set(p) == {"original", "recurrence", "ordered"} for p in paired)
        assert all(len({(r["outputs"], r["checksum"], r["iterations"])
                        for r in p.values()}) == 1 for p in paired)
        assert all(not r["allocation_changed"] for r in measured)
        item = {key: measured[0][key] for key in
                ("case", "taps", "L", "M", "num_in", "iterations", "effective_ordered")}
        item["variants"] = {}
        for variant in ("original", "recurrence", "ordered"):
            rows = [p[variant] for p in paired]
            item["variants"][variant] = {
                "cpu_seconds": dispersion([r["cpu_seconds"] for r in rows]),
                "wall_seconds": dispersion([r["wall_seconds"] for r in rows]),
                "nanoseconds_per_stage_call": dispersion(
                    [r["cpu_seconds"] / r["iterations"] * 1e9 for r in rows]),
                "output_samples_per_cpu_second": dispersion(
                    [r["outputs"] / r["cpu_seconds"] for r in rows]),
                "stage_calls_per_cpu_second": dispersion(
                    [r["iterations"] / r["cpu_seconds"] for r in rows])}
        for baseline, candidate in (("original", "ordered"),
                                    ("original", "recurrence"),
                                    ("recurrence", "ordered")):
            item[candidate + "_vs_" + baseline] = compare(paired, baseline, candidate, rng)
        summary["cases"].append(item)
        ratio = item["ordered_vs_original"]
        print(item["taps"], item["L"], item["num_in"],
              f"original/ordered={ratio['speedup']['median']:.4f}",
              "ci95=", ratio["paired_median_bootstrap_ci95"],
              f"recurrence/ordered={item['ordered_vs_recurrence']['speedup']['median']:.4f}")
    (args.directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
