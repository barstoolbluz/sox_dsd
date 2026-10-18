#!/bin/sh
set -eu
cd "$(dirname "$0")/../../../.."
E=tests/dsd/results/P15_prover_optimization_2026-10-18
set +e
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_full_band_campaign.py \
 --output "$E/optimized_dispatch_receipts" --start 3001 --limit 1 \
 --interval-seconds 60 > "$E/optimized_dispatch_replay.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$E/optimized_dispatch_exit.txt"
