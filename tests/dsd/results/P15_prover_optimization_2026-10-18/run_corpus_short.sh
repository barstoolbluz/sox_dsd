#!/bin/sh
set -eu
cd "$(dirname "$0")/../../../.."
E=tests/dsd/results/P15_prover_optimization_2026-10-18
for variant in baseline optimized; do
 case "$variant" in baseline) output="$E/BASELINE_4S.jsonl";; optimized) output="$E/OPTIMIZED_4S.jsonl";; esac
 PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_prover_benchmark.py \
    --variant "$variant" --seconds 4 --first 0 --limit 43 --output "$output"
done
for variant in baseline optimized; do
 case "$variant" in baseline) output="$E/BASELINE_2S.jsonl";; optimized) output="$E/OPTIMIZED_2S.jsonl";; esac
 PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_prover_benchmark.py \
    --variant "$variant" --seconds 2 --first 43 --limit 25 --output "$output"
done
