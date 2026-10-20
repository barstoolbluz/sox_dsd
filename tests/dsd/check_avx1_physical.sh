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
  printf 'compiler    %s\n' "$(cc --version 2>/dev/null | head -1)"
  printf 'libc        %s\n' "$(ldd --version 2>/dev/null | head -1)"
  printf 'kernel      %s\n' "$(uname -r)"
  printf 'cflags      -O2 -g\n'
} | tee "$R/host.txt"

# AVX1_SMOKE permits diagnostic execution on a newer CPU; it MUST NEVER
# bypass physical AVX1-only eligibility for the P15 older-AVX performance gate.
GATE_HOST=yes
if [ "${AVX1_SMOKE:-0}" = 1 ]; then
  GATE_HOST=no
  echo "  AVX1_SMOKE=1: this run is DIAGNOSTIC ONLY, not older-AVX evidence."
fi
if [ "$HAVE_AVX" != yes ] || { [ "$HAVE_AVX2" != no ] && [ "${AVX1_SMOKE:-0}" != 1 ]; }; then
  echo
  echo "FATAL: this gate needs AVX1 WITHOUT AVX2 (Sandy Bridge or Ivy Bridge era)."
  echo "  avx=$HAVE_AVX avx2=$HAVE_AVX2 — wrong host."
  exit 2
fi
if [ "$HAVE_AVX2" != no ]; then
  GATE_HOST=no
  echo "  AVX2 is present: no physical older-AVX qualification possible on this host."
fi

say "bench CPU validity"
# An absent or offline CPU makes taskset fail and silently voids every timing.
ONLINE=$(cat /sys/devices/system/cpu/online 2>/dev/null || echo "0-$(($(nproc)-1))")
cpu_online(){ python3 - "$1" "$ONLINE" <<'PYCPU'
import sys
want=int(sys.argv[1]); ok=False
for part in sys.argv[2].split(','):
    if '-' in part:
        a,b=part.split('-'); ok = ok or (int(a)<=want<=int(b))
    elif part.strip().isdigit(): ok = ok or int(part)==want
sys.exit(0 if ok else 1)
PYCPU
}
command -v python3 >/dev/null 2>&1 || { echo "FATAL: no python3 on PATH; the bench and clock probe need it."; exit 2; }
if ! cpu_online "$CPU"; then
  echo "  cpu $CPU is absent or offline (online set: $ONLINE)"
  for c in $(python3 -c "
import sys
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
if ! make -C test dsd_test_p11 sox_p10_candidate >/dev/null 2>&1; then
  echo "FATAL: could not build test/dsd_test_p11 or test/sox_p10_candidate"
  make -C test dsd_test_p11 sox_p10_candidate 2>&1 | tail -5
  exit 2
fi
for u in test/dsd_test_p11 test/sox_p10_candidate; do
  [ -x "$u" ] || { echo "FATAL: $u missing after build"; exit 2; }
done

say "correctness first: AVX1 must agree with the others on this silicon"
./src/sox -n -r 88200 -b 32 -e signed-integer "$R/in.wav" synth 3 sine 997 vol 0.3
./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" -r 2822400 "$R/a.dsf" pcmdsd 2822400
for k in scalar sse2 avx1; do
  SOX_DSD_KERNEL_FIR=$k ./src/sox --dsd-layout-loss warn "$R/a.dsf" \
    -b 32 -e signed-integer "$R/fir_$k.wav" dsdpcm -l preserve 88200 2>/dev/null
  SOX_DSD_KERNEL_SDM=$k ./test/sox_p10_candidate --dsd-layout-loss warn "$R/in.wav" \
    -r 2822400 "$R/sdm_$k.dsf" pcmdsd 2822400 2>/dev/null
done
sha256sum "$R"/in.wav "$R"/a.dsf "$R"/fir_*.wav "$R"/sdm_*.dsf > "$R/kernel-output-sha256.txt"
sed -i "s|$R/||" "$R/kernel-output-sha256.txt"; cat "$R/kernel-output-sha256.txt"
echo
echo "  cross-host reference, AMD Zen 4 and Intel Sapphire Rapids, gcc 14.2, -O2 -g:"
echo "    in.wav     bb23075f0e133795df9d2f7f66623cddb244ae873461d416e119e9aa37349190"
echo "    a.dsf      83f02d0856c23a50d9b717259fd15c5384ad2303e1b0c99211403d7569ef420b"
echo "    fir_*      ddc48d53afd672850466d0d3cd0b7b8c777ecd5a2c4757ae71dbf92ef6e286c2"
echo "    sdm_scalar 83f02d0856c23a50d9b717259fd15c5384ad2303e1b0c99211403d7569ef420b"
echo "    sdm_vector 65c0cbbd89b8e59be12e3eb0af17442700d4edab454ceaed3dd158b857c666da"
echo "  A within-host split of 1 FIR / 2 SDM is the gate criterion. Differing from"
echo "  the reference above is a separate question about cross-host reproducibility"
echo "  of the same tier, not an ISA-dispatch failure; report both."
echo
printf 'distinct FIR: %s (expect 1)   distinct SDM: %s (expect 2)\n' \
  "$(awk '/fir_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)" \
  "$(awk '/sdm_/{print $1}' "$R/kernel-output-sha256.txt" | sort -u | wc -l)"

say "kernel throughput, scalar-relative, all tiers this host has"
taskset -c "$CPU" python3 tests/dsd/bench_p11.py --unit test/dsd_test_p11 --phase P15 \
  --results "$R/kernel" --repetitions 15 --frames 180000 --tiers scalar sse2 avx1 \
  2>&1 | tee "$R/kernel.log"

say "effective clock per arm"
# Direct sysfs sampling. Three earlier attempts were discarded and the reasons
# matter: a spin-loop proxy conflated contention with clock (32% false spread
# on a host with no downclock); sampling a 3-second workload gave two samples
# per arm, one of which caught the idle floor (28% false spread). This uses a
# deliberately long workload, fast sampling, and discards samples at or below
# the policy minimum, which is what the AMD record used.
F=/sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_cur_freq
FMIN=$(cat /sys/devices/system/cpu/cpu$CPU/cpufreq/scaling_min_freq 2>/dev/null || echo 0)
if [ ! -r "$F" ]; then
  echo "  scaling_cur_freq not readable for cpu $CPU -> clock UNMEASURED"
  echo "  An older-AVX part may downclock under wide instructions. Without this"
  echo "  reading, a tier throughput difference cannot be separated from a"
  echo "  frequency difference; treat the comparison above with caution."
  echo "clock=unmeasured" > "$R/clock.txt"
else
  ./src/sox -n -r 176400 -b 32 -e signed-integer "$R/long.wav" \
    synth 60 sine 997 vol 0.25 2>/dev/null
  : > "$R/clock.txt"
  for tier in scalar sse2 avx1; do
    SOX_DSD_KERNEL_SDM=$tier taskset -c "$CPU" ./test/sox_p10_candidate \
      --dsd-layout-loss warn "$R/long.wav" -r 2822400 "$R/clk.dsf" pcmdsd 2822400 \
      >/dev/null 2>&1 &
    W=$!
    : > "$R/.s"
    while kill -0 $W 2>/dev/null; do cat "$F" >> "$R/.s" 2>/dev/null; sleep 0.05; done
    wait $W
    python3 - "$tier" "$R/.s" "$R/clock.txt" "$FMIN" <<'PYF'
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
  rm -f "$R/.s" "$R/long.wav"
  python3 - "$R/clock.txt" <<'PYS'
import sys
rows=[(l.split()[0],float(l.split()[2])) for l in open(sys.argv[1]) if 'median' in l]
if len(rows)>1:
    lo=min(r[1] for r in rows); hi=max(r[1] for r in rows)
    print("  spread across tiers: %.2f%%" % (100*(hi-lo)/lo))
    print("  a tier at a materially lower clock is downclocking, not")
    print("  algorithmically slower; report both figures if they diverge.")
elif rows:
    print("  only one tier produced a reliable reading; no comparison made")
else:
    print("  no reliable clock readings; treat the tier comparison with caution")
PYS
fi

say "done"
echo "gate_relevant=$GATE   results under $R"
# intermediates retained deliberately: they are what makes a cross-host
# hash mismatch diagnosable. Delete by hand if space matters.
rm -f "$R"/clk.dsf "$R"/long.wav
if [ "$GATE" = yes ]; then
  echo "Timings above are GATE-RELEVANT for P15-physical-older-AVX-performance."
else
  echo "Timings above are DIAGNOSTIC ONLY. Correctness results remain valid either way."
fi
