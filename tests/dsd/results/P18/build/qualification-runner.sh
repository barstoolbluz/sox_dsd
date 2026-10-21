#!/usr/bin/env bash
set +e
cd /mnt/data/p18-work/sox_dsd || exit 99
E=tests/dsd/results/P18/build
printf 'started: %s\n' "$(date -u +%FT%TZ)" > "$E/qualification.status"
step() {
  name=$1; shift
  "$@" > "$E/$name.log" 2>&1
  r=$?
  printf '%s\n' "$r" > "$E/$name.exit"
  printf '%s: %s\n' "$name" "$r" >> "$E/qualification.status"
  if [ "$r" -ne 0 ]; then
    printf 'HALTED: %s\ncompleted: %s\n' "$name" "$(date -u +%FT%TZ)" >> "$E/qualification.status"
    exit "$r"
  fi
}
step autoreconf-qualified autoreconf -fi
step configure-qualified ./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
step make-qualified make -j2
step p16-fresh-qualified python3 tests/dsd/test_p16.py --sox src/sox --unit test/dsd_test_p16 --results tests/dsd/results/P18/integration
step p16-cached-qualified python3 tests/dsd/test_p16.py --sox src/sox --unit test/dsd_test_p16 --results tests/dsd/results/P18/integration
step check-dsd-qualified make check-dsd DSD_PHASE=P18
step check-rename-qualified make check-rename
step p18-fixtures-qualified python3 tests/dsd/test_p18.py --fixtures-only
printf 'completed: %s\n' "$(date -u +%FT%TZ)" >> "$E/qualification.status"
