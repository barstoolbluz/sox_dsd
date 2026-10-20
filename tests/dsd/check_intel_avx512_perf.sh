#!/bin/bash
# Physical Intel AVX-512 throughput arm.
#
# Addresses P15-Intel-AVX512-physical-performance, which the closeout records
# as UNRUN-SCOPE-EXEMPT: "Only under unchanged conservative dispatch and no
# Intel physical performance claim". The AMD arm is CLOSED
# (tests/dsd/results/P13_amd_physical_avx512_2026-10-12); this is its Intel
# counterpart and runs the same matrix so the two are directly comparable.
#
# tests/dsd/check_intel_avx512.sh is correctness and dispatch only and makes
# no throughput claim. This script is the throughput half. Run both.
#
# The script decides for itself whether the host can support a gate-relevant
# measurement and labels its output accordingly:
#
#   GATE-RELEVANT  physical Intel CPU, governor pinned, turbo disabled
#   DIAGNOSTIC     anything less, including any virtual machine
#
# The Intel-specific question is licence-based downclocking under 512-bit
# instructions: a tier can be slower in wall time while being faster per clock.
# The clock probe below is therefore not optional colour, it is the arm.
#
#   sudo tests/dsd/benchprep.sh prepare --cpu N
#   tests/dsd/check_intel_avx512_perf.sh
#   sudo tests/dsd/benchprep.sh restore
set -u
cd "$(dirname "$0")/../.."
CPU=${BENCH_CPU:-2}
R=tests/dsd/results/P15_intel_physical_avx512_$(date +%Y-%m-%d)
mkdir -p "$R"
say(){ printf '\n=== %s ===\n' "$1"; }

# The bench shells out to tests/dsd/bench_p11_e2e.py, which needs numpy; the
# numeric gates also want mpmath and scipy. Pick an interpreter that has all
# three and fail early. A smoke run of this script on a host whose PATH
# python3 lacked numpy produced a passing kernel bench and six failed
# end-to-end cases -- a whole session wasted for a missing module.
PY=""
for cand in /usr/bin/python3 python3 python3.13 python3.12 python3.11; do
  command -v "$cand" >/dev/null 2>&1 || continue
  if "$cand" -c 'import mpmath,numpy,scipy' 2>/dev/null; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "FATAL: no python3 with mpmath, numpy and scipy."
  echo "  Debian/Ubuntu: sudo apt-get install -y python3-mpmath python3-numpy python3-scipy"
  echo "  or:            python3 -m pip install --user mpmath numpy scipy"
  exit 2
fi
echo "using interpreter: $PY"
# Child processes resolve plain python3 from PATH; put the chosen one first.
PYBIN="$(mktemp -d)"; ln -sf "$(command -v "$PY")" "$PYBIN/python3"; export PATH="$PYBIN:$PATH"
trap 'rm -rf "$PYBIN"' EXIT

say "host and ISA"
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo | awk '{print $3}')
HAVE_512=$(grep -qw avx512f /proc/cpuinfo && echo yes || echo no)
HAVE_AVX2=$(grep -qw avx2 /proc/cpuinfo && echo yes || echo no)
VIRT=$(systemd-detect-virt 2>/dev/null); [ -z "$VIRT" ] && VIRT=unknown
HYP=$(grep -qw hypervisor /proc/cpuinfo && echo PRESENT || echo absent)
{ grep -m1 'model name' /proc/cpuinfo; grep -m1 vendor_id /proc/cpuinfo
  printf 'microcode   %s\n' "$(grep -m1 microcode /proc/cpuinfo | awk '{print $3}')"
  printf 'avx2/512f   %s / %s\n' "$HAVE_AVX2" "$HAVE_512"
  printf 'avx512 set  %s\n' "$(grep -m1 ^flags /proc/cpuinfo | tr ' ' '\n' | grep '^avx512' | tr '\n' ' ')"
  printf 'virt        %s (hypervisor flag %s)\n' "$VIRT" "$HYP"
  printf 'cpus        %s, bench cpu %s\n' "$(nproc)" "$CPU"
  printf 'compiler    %s\n' "$(cc --version 2>/dev/null | head -1)"
  printf 'libc        %s\n' "$(ldd --version 2>/dev/null | head -1)"
  printf 'kernel      %s\n' "$(uname -r)"
  printf 'tree        %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf 'cflags      -O2 -g\n'
} | tee "$R/host.txt"

if [ "$HAVE_512" != yes ] || [ "$HAVE_AVX2" != yes ]; then
  echo; echo "FATAL: this arm needs a CPU with both AVX2 and AVX-512F."
  echo "  avx2=$HAVE_AVX2 avx512f=$HAVE_512 -- wrong host."; exit 2
fi
GATE_HOST=yes
if [ "$VENDOR" != GenuineIntel ]; then
  echo "  vendor is $VENDOR, not GenuineIntel: this cannot be the Intel arm."
  echo "  The AMD arm is already closed; recording DIAGNOSTIC."; GATE_HOST=no
fi

say "bench CPU validity"
# An absent or offline CPU makes taskset fail and silently voids every timing.
ONLINE=$(cat /sys/devices/system/cpu/online 2>/dev/null || echo "0-$(($(nproc)-1))")
cpu_online(){ "$PY" - "$1" "$ONLINE" <<'PYCPU'
import sys
want=int(sys.argv[1]); ok=False
for part in sys.argv[2].split(','):
    if '-' in part:
        a,b=part.split('-'); ok = ok or (int(a)<=want<=int(b))
    elif part.strip().isdigit(): ok = ok or int(part)==want
sys.exit(0 if ok else 1)
PYCPU
}
if ! cpu_online "$CPU"; then
  echo "  cpu $CPU is absent or offline (online set: $ONLINE)"
  for c in $("$PY" -c "
s='$ONLINE';out=[]
for p in s.split(','):
    if '-' in p: a,b=p.split('-'); out+=list(range(int(a),int(b)+1))
    elif p.strip().isdigit(): out.append(int(p))
out=[x for x in out if x!=0] or out
print(' '.join(str(x) for x in out[:8]))"); do CPU=$c; break; done
  echo "  falling back to cpu $CPU (cpu 0 avoided: it services interrupts)"
fi
taskset -c "$CPU" true 2>/dev/null || { echo "FATAL: taskset cannot pin to cpu $CPU"; exit 2; }
echo "  pinning to cpu $CPU (online set: $ONLINE)"

say "can this host support a gate-relevant measurement?"
GATE=$GATE_HOST
PREP_OK=yes   # tracked apart from vendor: do not tell an operator to fix a prepared host
G=/sys/devices/system/cpu/cpu$CPU/cpufreq
if [ "$HYP" = PRESENT ] || { [ "$VIRT" != none ] && [ "$VIRT" != unknown ]; }; then
  echo "  virtualized -> DIAGNOSTIC only (host governor/turbo not controllable,"
  echo "  and AVX-512 licence downclocking cannot be attributed from inside a guest)"
  # Not a preparation failure: no amount of preparing fixes being a guest, so
  # do not print the prepare advice for this alone.
  GATE=no
fi
if [ ! -r "$G/scaling_governor" ]; then
  echo "  no cpufreq exposed -> DIAGNOSTIC only"; GATE=no; PREP_OK=no
else
  gov=$(cat "$G/scaling_governor")
  [ "$gov" = performance ] || { echo "  governor is '$gov', needs 'performance'"; GATE=no; PREP_OK=no; }
  nt=/sys/devices/system/cpu/intel_pstate/no_turbo
  b=/sys/devices/system/cpu/cpufreq/boost
  if [ -r $nt ]; then [ "$(cat $nt)" = 1 ] || { echo "  intel_pstate no_turbo is 0, needs 1"; GATE=no; PREP_OK=no; }
  elif [ -r $b ]; then [ "$(cat $b)" = 0 ] || { echo "  boost is on, needs 0"; GATE=no; PREP_OK=no; }
  else echo "  neither no_turbo nor boost is exposed -> DIAGNOSTIC only"; GATE=no; PREP_OK=no; fi
fi
if [ "$PREP_OK" = no ]; then
  cat <<'PREP'

  To make this gate-relevant, as root:
    sudo tests/dsd/benchprep.sh prepare --cpu N
  or by hand:
    cpupower frequency-set -g performance
    echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo
  then re-run. Without these, timings are recorded as DIAGNOSTIC.
PREP
elif [ "$GATE" = yes ]; then
  echo "  prepared: governor performance, turbo disabled -> GATE-RELEVANT"
else
  echo "  host preparation is correct; the only disqualifier is above."
fi
echo "gate_relevant=$GATE" > "$R/gate-eligibility.txt"
cat "$R/host.txt" >> "$R/gate-eligibility.txt"

say "build"
MISSING=""
for b in cc make autoreconf autoconf automake aclocal; do command -v $b >/dev/null 2>&1 || MISSING="$MISSING $b"; done
command -v libtoolize >/dev/null 2>&1 || command -v libtool >/dev/null 2>&1 || MISSING="$MISSING libtool"
[ -n "$MISSING" ] && { echo "FATAL: missing:$MISSING"; echo "  sudo apt-get install -y build-essential autoconf automake libtool pkg-config"; exit 2; }
if autoreconf -fi && ./configure --disable-shared --without-libltdl CFLAGS='-O2 -g' && make -j"$(nproc)"; then
  echo "build exit=0"
else echo "build FAILED"; exit 2; fi
if ! make -C test dsd_test_p11 sox_p10_candidate >/dev/null 2>&1; then
  echo "FATAL: could not build test/dsd_test_p11 or test/sox_p10_candidate"
  make -C test dsd_test_p11 sox_p10_candidate 2>&1 | tail -5; exit 2
fi
for u in test/dsd_test_p11 test/sox_p10_candidate; do
  [ -x "$u" ] || { echo "FATAL: $u missing after build"; exit 2; }
done

say "correctness first: AVX-512 must agree with the others on this silicon"
# A throughput number from a tier that computes something different is worthless.
./src/sox -n -r 88200 -b 32 -e signed-integer "$R/in.wav" synth 3 sine 997 vol 0.3
./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" -r 2822400 "$R/a.dsf" pcmdsd 2822400
for k in scalar sse2 avx1 avx2 avx512; do
  SOX_DSD_KERNEL_FIR=$k ./src/sox --dsd-layout-loss warn "$R/a.dsf" \
    -b 32 -e signed-integer "$R/fir_$k.wav" dsdpcm -l preserve 88200 2>/dev/null
  SOX_DSD_KERNEL_SDM=$k ./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" \
    -r 2822400 "$R/sdm_$k.dsf" pcmdsd 2822400 2>/dev/null
done
sha256sum "$R"/in.wav "$R"/a.dsf "$R"/fir_*.wav "$R"/sdm_*.dsf > "$R/kernel-output-sha256.txt"
sed -i "s|$R/||" "$R/kernel-output-sha256.txt"; cat "$R/kernel-output-sha256.txt"
printf '\ndistinct FIR: %s (expect 1)   distinct SDM: %s (expect 2)\n' \
  "$(awk '/fir_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)" \
  "$(awk '/sdm_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)"
echo "  1 FIR / 2 SDM is the criterion: every FIR tier agrees, and SDM splits"
echo "  scalar against the vector tiers exactly as P10 recorded."

say "the matrix, same shape as the closed AMD arm"
taskset -c "$CPU" "$PY" tests/dsd/bench_p13_matrix.py \
  --results "$R" --repetitions 15 --full-matrix 2>&1 | tee "$R/matrix.log"

say "effective clock per tier: the Intel question"
# Intel parts can drop frequency under 512-bit instructions. Without this
# reading a slower AVX-512 wall time cannot be separated from a lower clock.
# Method follows the AMD record: long workload, 0.05 s sampling, discard
# samples at or below the policy minimum. Three earlier designs were discarded
# -- a spin-loop proxy conflated contention with clock, and a 3-second
# workload gave two samples per arm, one of which caught the idle floor.
F=/sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_cur_freq
FMIN=$(cat /sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_min_freq 2>/dev/null || echo 0)
if [ ! -r "$F" ]; then
  echo "  scaling_cur_freq not readable for cpu $CPU -> clock UNMEASURED"
  echo "  On Intel this is the difference between 'AVX-512 is slower' and"
  echo "  'AVX-512 ran at a lower clock'. Treat the matrix above with caution."
  echo "clock=unmeasured" > "$R/clock.txt"
else
  ./src/sox -n -r 176400 -b 32 -e signed-integer "$R/long.wav" \
    synth 60 sine 997 vol 0.25 2>/dev/null
  : > "$R/clock.txt"
  for tier in scalar sse2 avx2 avx512; do
    SOX_DSD_KERNEL_SDM=$tier taskset -c "$CPU" ./test/sox_p10_candidate \
      --dsd-layout-loss warn "$R/long.wav" -r 2822400 "$R/clk.dsf" pcmdsd 2822400 \
      >/dev/null 2>&1 &
    W=$!
    : > "$R/.s"
    while kill -0 $W 2>/dev/null; do cat "$F" >> "$R/.s" 2>/dev/null; sleep 0.05; done
    wait $W
    "$PY" - "$tier" "$R/.s" "$R/clock.txt" "$FMIN" <<'PYF'
import sys,statistics
tier,src,out,fmin=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
raw=[int(x) for x in open(src) if x.strip()]
busy=[v/1000 for v in raw if v > fmin*1.02]        # drop idle-floor samples
if len(busy) < 10:
    line="  %-7s only %d busy samples of %d -> UNRELIABLE, not reported" % (tier,len(busy),len(raw))
    print(line); open(out,'a').write(line+"\n"); raise SystemExit
m=statistics.median(busy)
line="  %-7s median %.0f MHz  p10 %.0f  p90 %.0f  busy samples %d of %d" % (
  tier,m,sorted(busy)[len(busy)//10],sorted(busy)[9*len(busy)//10],len(busy),len(raw))
print(line); open(out,'a').write(line+"\n")
PYF
  done
  rm -f "$R/.s"
  "$PY" - "$R/clock.txt" <<'PYS'
import sys
rows=[(l.split()[0],float(l.split()[2])) for l in open(sys.argv[1]) if 'median' in l]
d=dict(rows)
if 'avx512' in d and 'avx2' in d:
    drop=100*(d['avx2']-d['avx512'])/d['avx2']
    print("  avx512 against avx2: %+.2f%% clock" % -drop)
    if drop > 2:
        print("  AVX-512 is running at a materially lower clock on this part.")
        print("  Per-clock work and wall-clock throughput will disagree; report both.")
    else:
        print("  no material licence downclock: wall-clock timings can be read directly.")
elif rows:
    print("  not both tiers produced a reliable reading; no comparison made")
else:
    print("  no reliable clock readings; treat the tier comparison with caution")
PYS
fi

say "done"
rm -f "$R"/clk.dsf "$R"/long.wav
echo "gate_relevant=$GATE   results under $R"
# Intermediates are retained deliberately: they are what makes a cross-host
# hash mismatch diagnosable. Delete by hand if space matters.
if [ "$GATE" = yes ]; then
  echo "Timings above are GATE-RELEVANT for P15-Intel-AVX512-physical-performance."
  echo "Tar $R and hand it back. Do not read a promotion decision from this"
  echo "script: dispatch stays conservative until the gate is adjudicated."
else
  echo "Timings above are DIAGNOSTIC ONLY. Correctness results remain valid either way."
fi
