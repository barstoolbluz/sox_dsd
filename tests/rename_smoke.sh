#!/bin/sh
# Functional sanity check of the canonical binary, companion entry points,
# and retained _ng aliases. Does not touch tests/dsd/results/.
set -eu

if [ "$#" -ne 3 ]; then
  echo 'usage: rename_smoke.sh BUILDDIR/SRC SYMLINKS PLAYRECLINKS' >&2
  exit 2
fi
bindir=$1
aliases=$2
playrec=$3

if [ ! -x "$bindir/sox" ]; then
  echo "FAIL: missing $bindir/sox" >&2
  exit 1
fi
"$bindir/sox" --version 2>&1 | grep 'SoX DSD v' >/dev/null || {
  echo 'FAIL: incorrect SoX DSD version banner' >&2
  exit 1
}

for name in soxi soxi_ng play play_ng rec rec_ng; do
  case "$name" in
    play*|rec*) want=$playrec ;;
    *) want=$aliases ;;
  esac
  if [ "$want" = yes ]; then
    if [ ! -L "$bindir/$name" ] || [ "$(readlink "$bindir/$name")" != 'sox' ]; then
      echo "FAIL: $name is not an alias of sox" >&2
      exit 1
    fi
  elif [ -e "$bindir/$name" ]; then
    echo "FAIL: unexpected alias $name with symlinks disabled" >&2
    exit 1
  fi
done

work=$(mktemp -d "${TMPDIR:-/tmp}/sox-dsd-rename.XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
"$bindir/sox" -V0 -n -r 44100 -c 1 -b 16 "$work/sample.wav" synth 0.02 sine 440
[ -s "$work/sample.wav" ] || { echo 'FAIL: synthesis missing' >&2; exit 1; }
format=$("$bindir/sox" --info -t "$work/sample.wav")
[ "$format" = wav ] || { echo "FAIL: sox --info reported $format" >&2; exit 1; }
if [ "$aliases" = yes ]; then
  # In a shared Libtool build, src/sox is a shell launcher which execs
  # .libs/sox with argv[0] = sox. Running src/soxi (a link to that
  # launcher) cannot exercise the real executable's basename dispatch.
  # Link the actual uninstalled binary under each name in a private temp
  # directory; make check-rename provides its shared-library search path
  # via libtool --mode=execute -dlopen libsox_ng.la.
  actual="$bindir/sox"
  if [ -x "$bindir/.libs/sox" ]; then
    actual="$bindir/.libs/sox"
  fi
  for name in soxi soxi_ng; do
    ln -s "$actual" "$work/$name"
    format=$("$work/$name" -t "$work/sample.wav")
    [ "$format" = wav ] || { echo "FAIL: $name reported $format" >&2; exit 1; }
  done
fi
printf 'PASS rename smoke (sox + installed alias policy)\n'
