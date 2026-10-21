#!/usr/bin/env bash
set +e
cd /mnt/data/p18-work/sox_dsd || exit 99
printf 'started: %s\n' "$(date -u +%FT%TZ)" > tests/dsd/results/P18/build/final-replay.status
make check-dsd DSD_PHASE=P18 > tests/dsd/results/P18/build/check-dsd-final.log 2>&1
r=$?
printf '%s\n' "$r" > tests/dsd/results/P18/build/check-dsd-final.exit
printf 'check-dsd: %s\n' "$r" >> tests/dsd/results/P18/build/final-replay.status
if [ "$r" -eq 0 ]; then
  make check-rename > tests/dsd/results/P18/build/check-rename.log 2>&1
  r=$?
  printf '%s\n' "$r" > tests/dsd/results/P18/build/check-rename.exit
  printf 'check-rename: %s\n' "$r" >> tests/dsd/results/P18/build/final-replay.status
fi
printf 'completed: %s\n' "$(date -u +%FT%TZ)" >> tests/dsd/results/P18/build/final-replay.status
