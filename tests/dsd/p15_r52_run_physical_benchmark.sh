#!/usr/bin/env bash
# P15 DSD256 P/S matched physical measurement, final-built executables only.
# Results are evidence for independent adjudication, NEVER auto-release.
set -euo pipefail
if [ "$#" != 4 ]; then
  echo 'usage: p15_r52_run_physical_benchmark.sh /absolute/sox /absolute/sox_p10_candidate CPU /absolute/new-result-dir' >&2
  exit 2
fi
SOURCE_ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
SOX=$(realpath -e "$1")
CANDIDATE=$(realpath -e "$2")
CPU=$3
OUT=$4
PYTHON=${PYTHON:-python3}
case $CPU in ''|*[!0-9]*) echo 'REFUSED: CPU must be a non-negative integer' >&2; exit 2;; esac
[ -x "$SOX" ] && [ -x "$CANDIDATE" ] || { echo 'REFUSED: executable missing' >&2; exit 2; }
# Prohibit libtool shell wrappers: their digest is not the DSP executable's.
for binary in "$SOX" "$CANDIDATE"; do
  if [ "$(od -An -N4 -tx1 "$binary" | tr -d ' \n')" != 7f454c46 ]; then
    echo "REFUSED: $binary is not an ELF executable; hash the true built binary, not a wrapper" >&2
    exit 2
  fi
done
[ "${OUT:0:1}" = / ] && [ ! -e "$OUT" ] || { echo 'REFUSED: result directory must be an unused absolute path' >&2; exit 2; }
# This is screening, not cryptographic physical-host attestation.
[ "$(uname -s)" = Linux ] || { echo 'REFUSED: requires physical Linux host' >&2; exit 2; }
if grep -qw hypervisor /proc/cpuinfo; then
  echo 'REFUSED: hypervisor reported; this is not physical benchmark evidence' >&2
  exit 2
fi
"$PYTHON" - "$CPU" <<'PY'
import os,sys
cpu=int(sys.argv[1])
if cpu not in os.sched_getaffinity(0):
    raise SystemExit('REFUSED: CPU is outside process affinity mask')
PY
GOV="/sys/devices/system/cpu/cpu${CPU}/cpufreq/scaling_governor"
if [ ! -r "$GOV" ] || [ "$(cat "$GOV")" != performance ]; then
  echo 'REFUSED: selected CPU governor not recorded as performance; prepare host explicitly' >&2
  exit 2
fi
if [ -r /sys/devices/system/cpu/cpufreq/boost ] && [ "$(cat /sys/devices/system/cpu/cpufreq/boost)" != 0 ]; then
  echo 'REFUSED: CPU boost remains enabled; prepare host explicitly' >&2
  exit 2
fi
# Operator must independently review host isolation/noise, thermal and clocks.
# Preserve receipts and all stimulus audio rather than deleting the payloads.
mkdir "$OUT"
( cd "$SOURCE_ROOT"; 
  printf 'P15/R5.2 physical six-channel benchmark; NO AUTOMATIC ACCEPTANCE\n' > "$OUT/IDENTITY.txt"
  printf 'source_root=%s\nsox=%s\ncandidate=%s\npinned_cpu=%s\n' "$SOURCE_ROOT" "$SOX" "$CANDIDATE" "$CPU" >> "$OUT/IDENTITY.txt"
  printf 'binary_and_source_sha256_before:\n' >> "$OUT/IDENTITY.txt"
  sha256sum "$SOX" "$CANDIDATE" src/rate.c src/rate_poly_fir0.h src/fft4g.c src/sinc.c src/effects_i_dsp.c src/dsd_decode.c src/dsd_coeffs.h src/dsd_coeffs_v2.h tests/dsd/verify_dsd256_control_match.py tests/dsd/p15_dsd256_comparator_2026.py tests/dsd/bench_p15_dsd256_ps_matched.py > "$OUT/BEFORE.sha256"
  cat "$OUT/BEFORE.sha256" >> "$OUT/IDENTITY.txt"
  printf "ELF dependencies (not a complete loader/ISA attestation):\n" >> "$OUT/IDENTITY.txt"
  ldd "$SOX" >> "$OUT/IDENTITY.txt" 2>&1
  ldd "$CANDIDATE" >> "$OUT/IDENTITY.txt" 2>&1
  export PYTHONPATH=tests/dsd
  "$PYTHON" tests/dsd/p15_dsd256_comparator_2026.py --sox "$SOX" --candidate "$CANDIDATE" --seconds 6 --output "$OUT/comparator"
  "$PYTHON" tests/dsd/p15_dsd256_comparator_2026.py --sox "$SOX" --candidate "$CANDIDATE" --verify-only --output "$OUT/comparator"
  "$PYTHON" tests/dsd/bench_p15_dsd256_ps_matched.py --sox "$SOX" --candidate "$CANDIDATE" --spectral-receipt "$OUT/comparator" --output "$OUT/bench" --cpu "$CPU" --seconds 2 --warmups 2
  "$PYTHON" tests/dsd/bench_p15_dsd256_ps_matched.py --sox "$SOX" --candidate "$CANDIDATE" --spectral-receipt "$OUT/comparator" --output "$OUT/bench" --verify-only
  printf 'binary_and_source_sha256_after:\n' >> "$OUT/IDENTITY.txt"
  sha256sum "$SOX" "$CANDIDATE" src/rate.c src/rate_poly_fir0.h src/fft4g.c src/sinc.c src/effects_i_dsp.c src/dsd_decode.c src/dsd_coeffs.h src/dsd_coeffs_v2.h tests/dsd/verify_dsd256_control_match.py tests/dsd/p15_dsd256_comparator_2026.py tests/dsd/bench_p15_dsd256_ps_matched.py > "$OUT/AFTER.sha256"
  cat "$OUT/AFTER.sha256" >> "$OUT/IDENTITY.txt"
  cmp "$OUT/BEFORE.sha256" "$OUT/AFTER.sha256" || {
    echo 'REFUSED: source/binary changed during measurement' >&2
    exit 2
  }
)
echo 'MEASURED_UNADJUDICATED: collect complete results; independently check clock/noise/binary identity and 8 confidence bounds. P15 release is still OPEN.'
