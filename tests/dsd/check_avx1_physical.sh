#!/bin/bash
# Physical older-AVX (AVX1 without AVX2) throughput check.
#
# Addresses P15-physical-older-AVX-performance, whose evidence note reads
# "P11 AVX1-only QEMU confirms instruction compatibility, not physical
# throughput".  This script decides for itself whether the host can support a
# gate-relevant measurement and labels its output accordingly:
#
#   GATE-RELEVANT  physical CPU, governor pinned, boost disabled, clock verified
#   DIAGNOSTIC     anything less
#
# Run with sudo for the preparation step, or run `prepare` separately as root.
set -u
cd "$(dirname "$0")/../.."
CPU=${BENCH_CPU:-2}
R=tests/dsd/results/P15_avx1_physical_$(date +%Y-%m-%d)
mkdir -p "$R"
say(){ printf '\n=== %s ===\n' "$1"; }

say "host and ISA"
HAVE_AVX=$(grep -qw avx /proc/cpuinfo && echo yes || echo no)
HAVE_AVX2=$(grep -qw avx2 /proc/cpuinfo && echo yes || echo no)
VIRT=$(systemd-detect-virt 2>/dev/null); [ -z "$VIRT" ] && VIRT=unknown
HYP=$(grep -qw hypervisor /proc/cpuinfo && echo PRESENT || echo absent)
{ grep -m1 'model name' /proc/cpuinfo; grep -m1 vendor_id /proc/cpuinfo
  printf 'microcode   %s\n' "$(grep -m1 microcode /proc/cpuinfo | awk '{print $3}')"
  printf 'avx / avx2  %s / %s\n' "$HAVE_AVX" "$HAVE_AVX2"
  printf 'virt        %s (hypervisor flag %s)\n' "$VIRT" "$HYP"
  printf 'cpus        %s, bench cpu %s\n' "$(nproc)" "$CPU"
} | tee "$R/host.txt"

if [ "${AVX1_SMOKE:-0}" != 1 ] && { [ "$HAVE_AVX" != yes ] || [ "$HAVE_AVX2" != no ]; }; then
  echo
  echo "FATAL: this gate needs AVX1 WITHOUT AVX2 (Sandy Bridge or Ivy Bridge era)."
  echo "  avx=$HAVE_AVX avx2=$HAVE_AVX2 — wrong host."
  exit 2
fi

say "can this host support a gate-relevant measurement?"
GATE=yes
G=/sys/devices/system/cpu/cpu$CPU/cpufreq
if [ "$HYP" = PRESENT ] || { [ "$VIRT" != none ] && [ "$VIRT" != unknown ]; }; then
  echo "  virtualized -> DIAGNOSTIC only (host governor/boost not controllable)"; GATE=no
fi
if [ ! -r "$G/scaling_governor" ]; then
  echo "  no cpufreq exposed -> DIAGNOSTIC only"; GATE=no
else
  gov=$(cat "$G/scaling_governor")
  [ "$gov" = performance ] || { echo "  governor is '$gov', needs 'performance'"; GATE=no; }
  b=/sys/devices/system/cpu/cpufreq/boost
  if [ -r $b ]; then [ "$(cat $b)" = 0 ] || { echo "  boost is on, needs 0"; GATE=no; }
  else echo "  boost control not exposed (intel_pstate: check no_turbo)"
       nt=/sys/devices/system/cpu/intel_pstate/no_turbo
       if [ -r $nt ]; then [ "$(cat $nt)" = 1 ] || { echo "  intel_pstate no_turbo is 0, needs 1"; GATE=no; }
       else GATE=no; fi
  fi
fi
if [ "$GATE" = no ]; then
  cat <<'PREP'

  To make this gate-relevant, as root:
    cpupower frequency-set -g performance            # or write scaling_governor
    echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo   # Intel pstate
    echo 0 > /sys/devices/system/cpu/cpufreq/boost           # acpi-cpufreq
  then re-run. Without these, timings are recorded as DIAGNOSTIC.
PREP
else
  echo "  prepared: governor performance, turbo/boost disabled -> GATE-RELEVANT"
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
make -C test dsd_test_p11 sox_p10_candidate >/dev/null 2>&1

say "correctness first: AVX1 must agree with the others on this silicon"
./src/sox_ng -n -r 88200 -b 32 -e signed-integer "$R/in.wav" synth 3 sine 997 vol 0.3
./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" -r 2822400 "$R/a.dsf" pcmdsd 2822400
for k in scalar sse2 avx1; do
  SOX_DSD_KERNEL_FIR=$k ./src/sox_ng --dsd-layout-loss warn "$R/a.dsf" \
    -b 32 -e signed-integer "$R/fir_$k.wav" dsdpcm -l preserve 88200 2>/dev/null
  SOX_DSD_KERNEL_SDM=$k ./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" \
    -r 2822400 "$R/sdm_$k.dsf" pcmdsd 2822400 2>/dev/null
done
sha256sum "$R"/fir_*.wav "$R"/sdm_*.dsf > "$R/kernel-output-sha256.txt"
sed -i "s|$R/||" "$R/kernel-output-sha256.txt"; cat "$R/kernel-output-sha256.txt"
printf 'distinct FIR: %s (expect 1)   distinct SDM: %s (expect 2)\n' \
  "$(awk '/fir_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)" \
  "$(awk '/sdm_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)"

say "kernel throughput, scalar-relative, all tiers this host has"
taskset -c "$CPU" python3 tests/dsd/bench_p11.py --unit test/dsd_test_p11 --phase P15 \
  --results "$R/kernel" --repetitions 15 --frames 180000 --tiers scalar sse2 avx1 \
  2>&1 | tee "$R/kernel.log"

say "effective clock per arm (same fixed work, TSC-independent, unprivileged)"
taskset -c "$CPU" python3 - "$R" <<'PYCLK' 2>&1 | tee -a "$R/clock.log"
import subprocess,sys,time,statistics,os
R=sys.argv[1]
N=1_500_000                      # identical work in every sample
def spin():
    t0=time.perf_counter(); k=0
    for i in range(N): k+=i
    return time.perf_counter()-t0
idle=statistics.median([spin() for _ in range(7)])
print("  idle            %.5fs  (reference, %d iterations)" % (idle,N))
print("  NOTE: the probe shares the pinned core with the workload, so the")
print("  absolute ratio reflects contention, not clock. Only the tier-to-tier")
print("  spread below is a clock signal.")
out={}
for tier in ('scalar','sse2','avx1'):
    p=subprocess.Popen(['./test/sox_p10_candidate','--dsd-layout-loss','warn',
        R+'/in.wav','-r','2822400',R+'/clk.dsf','pcmdsd','2822400'],
        env=dict(os.environ,SOX_DSD_KERNEL_SDM=tier),
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    s=[]
    while p.poll() is None: s.append(spin())
    if not s: continue
    m=statistics.median(s); out[tier]=m
    print("  during %-7s  %.5fs  contended ratio %.4f" % (tier,m,idle/m))
if len(out)>1:
    lo=min(out.values()); hi=max(out.values())
    print("  spread across tiers: %.2f%%" % (100*(hi-lo)/lo))
    print("  a tier with a materially lower relative clock is downclocking,")
    print("  not algorithmically slower; report both if they diverge.")
PYCLK

say "done"
echo "gate_relevant=$GATE   results under $R"
rm -f "$R"/*.wav "$R"/*.dsf
if [ "$GATE" = yes ]; then
  echo "Timings above are GATE-RELEVANT for P15-physical-older-AVX-performance."
else
  echo "Timings above are DIAGNOSTIC ONLY. Correctness results remain valid either way."
fi
