#!/bin/sh
cd "$(dirname "$0")/../../../../.." || exit 99
OUT=tests/dsd/results/P18/build
run() {
 name="$1"; shift
 printf '%s\n' "$*" > "$OUT/$name.command.txt"
 "$@" > "$OUT/$name.log" 2>&1
 rc=$?
 printf '%s\n' "$rc" > "$OUT/$name.exit"
 printf '%s: %s\n' "$name" "$rc" >> "$OUT/sequential-tests.status"
}
run make-check make check
run measure-p18 python3 tests/dsd/measure.py --phase P18 --results tests/dsd/results/P18/numeric
run bench-p18 python3 tests/dsd/bench.py --phase P18 --results tests/dsd/results/P18/bench
