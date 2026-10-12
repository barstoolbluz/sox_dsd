#!/bin/bash
# P13 Intel AVX-512 coverage check. Run after cloning the branch on an Intel
# AVX-512 host. Correctness and dispatch only: this is not a prepared
# benchmarking host, so no throughput claim should be read from it.
set -u
cd "$(dirname "$0")/../.."
R=tests/dsd/results/P13_intel_$(date +%Y-%m-%d)
mkdir -p "$R"
say(){ printf '\n=== %s ===\n' "$1"; }

# The DSD numeric gates need mpmath, numpy and scipy. Pick an interpreter that
# has all three and fail early with a clear message rather than mid-run.
PY=""
for cand in /usr/bin/python3 python3 python3.13 python3.12 python3.11; do
  command -v "$cand" >/dev/null 2>&1 || continue
  if "$cand" -c 'import mpmath,numpy,scipy' 2>/dev/null; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "FATAL: no python3 with mpmath, numpy and scipy."
  echo "  Debian/Ubuntu: sudo apt-get install -y python3-mpmath python3-numpy python3-scipy"
  echo "  or:            python3 -m pip install --user mpmath numpy scipy"
  echo "Without them make check-dsd and the numeric suites cannot run."
  exit 2
fi
echo "using interpreter: $PY"
# make check-dsd shells out to plain python3, so put the chosen one first.
PYBIN="$(mktemp -d)"; ln -sf "$(command -v "$PY")" "$PYBIN/python3"; export PATH="$PYBIN:$PATH"
trap 'rm -rf "$PYBIN"' EXIT

say "host"
grep -m1 vendor_id /proc/cpuinfo
grep -m1 'model name' /proc/cpuinfo
for f in avx512f avx512dq avx512bw avx512vl avx2 fma; do
  printf '%-10s %s\n' "$f" "$(grep -qw $f /proc/cpuinfo && echo present || echo absent)"
done | tee "$R/host-isa.txt"

say "build"
autoreconf -fi && ./configure --disable-shared --without-libltdl CFLAGS='-O2 -g' && make -j"$(nproc)"
echo "build exit=$?"

say "generic and DSD regression suites"
make check            > "$R/make-check.log" 2>&1;     echo "make check     exit=$?"
make check-dsd        > "$R/make-check-dsd.log" 2>&1; echo "make check-dsd exit=$?"
grep -oE '\{"verdict":[^}]*\}[^}]*\}' "$R/make-check-dsd.log" | tail -1

say "P13 kernel unit, including AVX-512F executable qualification"
./test/dsd_test_p13 2>&1 | tee "$R/unit-p13.log"; echo "exit=${PIPESTATUS[0]}"

say "ISA isolation and cross-ISA numeric equivalence"
for t in check_p13_isa check_p12_isa test_p11_numeric test_p11_integration test_p12_channels; do
  "$PY" tests/dsd/$t.py --results "$R/$t" > "$R/$t.log" 2>&1
  printf '%-22s exit=%s  %s\n' "$t" "$?" "$(tail -1 "$R/$t.log" | cut -c1-70)"
done

say "forced-tier output equality, all five tiers"
make -C test dsd_test_p10 sox_p10_candidate >/dev/null 2>&1 || echo "WARN: candidate encoder build failed"
./src/sox_ng -n -r 88200 -b 32 -e signed-integer "$R/in.wav" synth 3 sine 997 vol 0.3
./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" -r 2822400 "$R/a.dsf" pcmdsd 2822400
for k in scalar sse2 avx1 avx2 avx512; do
  SOX_DSD_KERNEL_FIR=$k ./src/sox_ng --dsd-layout-loss warn "$R/a.dsf" \
    -b 32 -e signed-integer "$R/fir_$k.wav" dsdpcm -l preserve 88200 2>"$R/fir_$k.err"
  printf 'FIR=%-8s exit=%s %s\n' "$k" "$?" "$(sha256sum "$R/fir_$k.wav" 2>/dev/null | cut -c1-20)"
done
for k in scalar sse2 avx1 avx2 avx512; do
  SOX_DSD_KERNEL_SDM=$k ./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" \
    -r 2822400 "$R/sdm_$k.dsf" pcmdsd 2822400 2>"$R/sdm_$k.err"
  printf 'SDM=%-8s exit=%s %s\n' "$k" "$?" "$(sha256sum "$R/sdm_$k.dsf" 2>/dev/null | cut -c1-20)"
done
printf 'distinct FIR hashes: %s (expect 1)\n' "$(sha256sum "$R"/fir_*.wav | awk '{print $1}' | sort -u | wc -l)"
printf 'distinct SDM hashes: %s (expect 2: scalar, and the vector tiers)\n' "$(sha256sum "$R"/sdm_*.dsf | awk '{print $1}' | sort -u | wc -l)"

say "done"
echo "results under $R"
rm -f "$R"/*.wav "$R"/*.dsf
