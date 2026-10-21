#!/usr/bin/env bash
set +e
cd /mnt/data/p18-work/sox_dsd || exit 99
E=tests/dsd/results/P18/build
printf 'started: %s\n' "$(date -u +%FT%TZ)" > "$E/release-gates.status"
step() {
  name=$1; shift
  "$@" > "$E/$name.log" 2>&1
  r=$?
  printf '%s\n' "$r" > "$E/$name.exit"
  printf '%s: %s\n' "$name" "$r" >> "$E/release-gates.status"
  if [ "$r" -ne 0 ]; then
    printf 'HALTED: %s\ncompleted: %s\n' "$name" "$(date -u +%FT%TZ)" >> "$E/release-gates.status"
    exit "$r"
  fi
}
step make-check-qualified make check
step run-p18-qualified python3 tests/dsd/run.py --phase P18 --results tests/dsd/results/P18
step measure-p18-qualified python3 tests/dsd/measure.py --phase P18 --results tests/dsd/results/P18/numeric
step bench-p18-qualified python3 tests/dsd/bench.py --phase P18 --results tests/dsd/results/P18/bench
step manifest-seal python3 tests/dsd/seal_p18_manifest.py --seal
step manifest-check python3 tests/dsd/seal_p18_manifest.py --check
printf 'completed: %s\n' "$(date -u +%FT%TZ)" >> "$E/release-gates.status"
