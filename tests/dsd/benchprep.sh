#!/bin/sh
#
# benchprep.sh - put this host into a state where a 2% throughput gate means
# something, and put it back afterwards.
#
#   sudo tests/dsd/benchprep.sh prepare [--cpu N]
#        tests/dsd/benchprep.sh status
#        tests/dsd/benchprep.sh noise [--cpu N] [--runs N]
#   sudo tests/dsd/benchprep.sh restore
#
# prepare saves every value it changes to a state file and restore replays it.
# Nothing is guessed on restore: if a value was not saved, it is not touched.
# See tests/dsd/BENCHMARKING.md.

set -eu

STATE=${DSD_BENCHPREP_STATE:-/var/tmp/dsd-benchprep.state}
CPUDIR=/sys/devices/system/cpu
CPU=8
RUNS=15
TOLERANCE=2.0

die() { echo "benchprep: $*" >&2; exit 1; }
note() { echo "  $*"; }

need_root() {
	[ "$(id -u)" = 0 ] || die "'$1' needs root; re-run with sudo"
}

# Read a sysfs file, or print nothing if it is absent/unreadable.
get() { [ -r "$1" ] && cat "$1" 2>/dev/null || true; }

# Write a value only if the file exists and the value is non-empty.
put() {
	_f=$1 _v=$2
	[ -n "$_v" ] || return 0
	[ -w "$_f" ] || { note "skip (not writable): $_f"; return 0; }
	printf '%s\n' "$_v" > "$_f" 2>/dev/null || note "skip (write failed): $_f"
}

sibling_of() {
	_list=$(get "$CPUDIR/cpu$1/topology/thread_siblings_list")
	# "8,40" -> 40 ; a single-entry list means SMT is already off
	case "$_list" in
	*,*) echo "$_list" | cut -d, -f2 ;;
	*)   echo "" ;;
	esac
}

parse_args() {
	while [ $# -gt 0 ]; do
		case $1 in
		--cpu)   CPU=${2:?--cpu needs a value}; shift 2 ;;
		--runs)  RUNS=${2:?--runs needs a value}; shift 2 ;;
		--state) STATE=${2:?--state needs a value}; shift 2 ;;
		*) die "unknown option: $1" ;;
		esac
	done
	case $CPU in ''|*[!0-9]*) die "--cpu must be a number" ;; esac
	[ -d "$CPUDIR/cpu$CPU" ] || die "cpu$CPU does not exist"
}

cmd_prepare() {
	need_root prepare
	[ -e "$STATE" ] && die "state file $STATE already exists; run 'restore' first
(or delete it if you are certain the saved values no longer apply)"

	sib=$(sibling_of "$CPU")
	tmp=$STATE.$$
	: > "$tmp"
	echo "# saved by benchprep.sh; do not edit" >> "$tmp"
	echo "bench_cpu=$CPU" >> "$tmp"
	echo "sibling=$sib" >> "$tmp"

	echo "saving and applying:"

	# Per-policy governor and energy preference. Policies can differ, so each
	# is recorded individually rather than assuming a single global value.
	for p in "$CPUDIR"/cpufreq/policy*; do
		[ -d "$p" ] || continue
		n=$(basename "$p")
		g=$(get "$p/scaling_governor")
		e=$(get "$p/energy_performance_preference")
		[ -n "$g" ] && echo "gov_$n=$g" >> "$tmp"
		[ -n "$e" ] && echo "epp_$n=$e" >> "$tmp"
		put "$p/scaling_governor" performance
		[ -n "$e" ] && put "$p/energy_performance_preference" performance
	done
	note "governor -> performance, energy preference -> performance"

	b=$(get "$CPUDIR/cpufreq/boost")
	if [ -n "$b" ]; then
		echo "boost=$b" >> "$tmp"
		put "$CPUDIR/cpufreq/boost" 0
		note "boost -> 0 (flat clock, not merely a high one)"
	fi

	nt=$(get "$CPUDIR/intel_pstate/no_turbo")
	if [ -n "$nt" ]; then
		echo "no_turbo=$nt" >> "$tmp"
		put "$CPUDIR/intel_pstate/no_turbo" 1
		note "intel_pstate no_turbo -> 1"
	fi

	# Offline just the bench core's SMT sibling. Narrower and far easier to
	# undo than disabling SMT machine-wide.
	if [ -n "$sib" ] && [ -w "$CPUDIR/cpu$sib/online" ]; then
		echo "sibling_online=$(get "$CPUDIR/cpu$sib/online")" >> "$tmp"
		put "$CPUDIR/cpu$sib/online" 0
		note "cpu$sib offlined (SMT sibling of cpu$CPU)"
	elif [ -z "$sib" ]; then
		note "cpu$CPU has no SMT sibling; nothing to offline"
	fi

	mv "$tmp" "$STATE"
	echo "state saved to $STATE"
	echo
	echo "next: tests/dsd/benchprep.sh noise --cpu $CPU"
	echo "when finished: sudo tests/dsd/benchprep.sh restore"
}

cmd_restore() {
	need_root restore
	[ -r "$STATE" ] || die "no state file at $STATE; nothing to restore"
	echo "restoring from $STATE:"

	sib=$(sed -n 's/^sibling=//p' "$STATE")
	so=$(sed -n 's/^sibling_online=//p' "$STATE")
	[ -n "$sib" ] && [ -n "$so" ] && {
		put "$CPUDIR/cpu$sib/online" "$so"
		note "cpu$sib online -> $so"
	}

	b=$(sed -n 's/^boost=//p' "$STATE")
	[ -n "$b" ] && { put "$CPUDIR/cpufreq/boost" "$b"; note "boost -> $b"; }

	nt=$(sed -n 's/^no_turbo=//p' "$STATE")
	[ -n "$nt" ] && { put "$CPUDIR/intel_pstate/no_turbo" "$nt"; note "no_turbo -> $nt"; }

	# Restore energy preference before governor: some drivers reset the
	# preference when the governor changes.
	sed -n 's/^epp_\(policy[0-9]*\)=\(.*\)$/\1 \2/p' "$STATE" | while read -r n v; do
		put "$CPUDIR/cpufreq/$n/energy_performance_preference" "$v"
	done
	sed -n 's/^gov_\(policy[0-9]*\)=\(.*\)$/\1 \2/p' "$STATE" | while read -r n v; do
		put "$CPUDIR/cpufreq/$n/scaling_governor" "$v"
	done
	note "per-policy governor and energy preference restored"

	rm -f "$STATE"
	echo "done; state file removed"
}

cmd_status() {
	echo "host:"
	note "$(get /proc/cpuinfo | sed -n 's/^model name[[:space:]]*: //p' | head -1)"
	note "governor: $(get "$CPUDIR/cpufreq/policy0/scaling_governor")  driver: $(get "$CPUDIR/cpufreq/policy0/scaling_driver")"
	note "energy preference: $(get "$CPUDIR/cpufreq/policy0/energy_performance_preference")"
	note "boost: $(get "$CPUDIR/cpufreq/boost")"
	[ -r "$CPUDIR/intel_pstate/no_turbo" ] &&
		note "no_turbo: $(get "$CPUDIR/intel_pstate/no_turbo")"
	note "smt: $(get "$CPUDIR/smt/control")"
	iso=$(grep -oE 'isolcpus=[^ ]*|nohz_full=[^ ]*|rcu_nocbs=[^ ]*' /proc/cmdline 2>/dev/null | tr '\n' ' ')
	note "isolation: ${iso:-none}"
	if [ -r "$STATE" ]; then
		note "prepared: yes (state $STATE, bench cpu $(sed -n 's/^bench_cpu=//p' "$STATE"))"
	else
		note "prepared: no"
	fi
	echo "live frequency spread (MHz), online cpus:"
	lo=; hi=
	for d in "$CPUDIR"/cpu[0-9]*; do
		c=${d#"$CPUDIR"/cpu}
		[ "$(get "$d/online")" = 0 ] && continue
		f=$(get "$d/cpufreq/scaling_cur_freq"); [ -n "$f" ] || continue
		f=$((f / 1000))
		[ -z "$lo" ] && lo=$f && hi=$f
		[ "$f" -lt "$lo" ] && lo=$f
		[ "$f" -gt "$hi" ] && hi=$f
	done
	if [ -n "$lo" ]; then
		note "min $lo, max $hi"
		[ "$hi" -gt $((lo * 105 / 100)) ] &&
			note "WARNING: cores differ by more than 5%; clocks are not pinned"
	fi
}

# Time a fixed CPU-bound workload repeatedly and report the host's own spread.
# This measures the machine, not sox_ng: if the floor here exceeds the gate's
# tolerance, no sox_ng comparison on this host can resolve the gate.
cmd_noise() {
	command -v python3 >/dev/null 2>&1 || die "noise needs python3"
	[ "$(get "$CPUDIR/cpu$CPU/online")" = 0 ] &&
		die "cpu$CPU is offline (is it the sibling you offlined?)"
	pin=; command -v taskset >/dev/null 2>&1 && pin="taskset -c $CPU"
	echo "measuring host repeatability on cpu$CPU, $RUNS runs"
	i=0
	: > /tmp/benchprep-times.$$
	while [ "$i" -lt "$RUNS" ]; do
		$pin python3 -c '
import time
t=time.process_time()
x=0
for i in range(8_000_000): x+=i*i
print("%.6f"%(time.process_time()-t))
' >> /tmp/benchprep-times.$$
		i=$((i + 1))
	done
	# The timings arrive as a file argument: a heredoc already occupies stdin.
	python3 - "$TOLERANCE" "/tmp/benchprep-times.$$" <<'PY'
import sys, statistics as st
tol = float(sys.argv[1])
v = sorted(float(x) for x in open(sys.argv[2]) if x.strip())
med = st.median(v)
spread = (v[-1] - v[0]) / med * 100
print(f"  min {v[0]:.4f}s  median {med:.4f}s  max {v[-1]:.4f}s")
print(f"  spread {spread:.1f}%  (gate tolerance {tol}%)")
if spread <= tol:
    print(f"  VERDICT: usable - host noise is within the {tol}% gate")
else:
    print(f"  VERDICT: too noisy - a {tol}% effect cannot be resolved here.")
    print("  Report the gate inconclusive, or prepare the host further")
    print("  (see tests/dsd/BENCHMARKING.md: isolcpus, boost, SMT).")
PY
	rm -f /tmp/benchprep-times.$$
}

[ $# -ge 1 ] || die "usage: benchprep.sh {prepare|restore|status|noise} [--cpu N] [--runs N]"
action=$1; shift
parse_args "$@"
case $action in
prepare) cmd_prepare ;;
restore) cmd_restore ;;
status)  cmd_status ;;
noise)   cmd_noise ;;
*) die "unknown action '$action'; expected prepare, restore, status or noise" ;;
esac
