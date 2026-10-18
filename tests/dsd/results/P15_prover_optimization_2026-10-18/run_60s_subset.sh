#!/bin/sh
set -eu
cd "$(dirname "$0")/../../../.."
E=tests/dsd/results/P15_prover_optimization_2026-10-18
for variant_index in 'baseline 24' 'optimized 13' 'optimized 26' 'optimized 31' 'optimized 35' 'optimized 15' 'optimized 37'; do
 set -- $variant_index
 variant=$1
 i=$2
 case "$variant" in
  baseline) output="$E/BASELINE_60S.jsonl";;
  optimized) output="$E/OPTIMIZED_60S.jsonl";;
 esac
 PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_prover_benchmark.py \
   --variant "$variant" --seconds 60 --first "$i" --limit 1 --output "$output" || exit 1
done
