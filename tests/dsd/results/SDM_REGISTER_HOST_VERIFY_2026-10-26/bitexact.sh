#!/bin/bash
# usage: bitexact.sh REF_SOX NEW_SOX WORKDIR
REF=$1; NEW=$2; T=$3; mkdir -p $T
pass=0; fail=0; err=0
gen() { # name rate ch -> wav
  local n=$1 r=$2 c=$3 f=$T/in-$1-$2-$3.wav
  [ -f $f ] && { echo $f; return; }
  case $n in
    sine)   $REF -n -r $r -b 32 -e signed -c $c $f synth 2 sine 997 gain -6 ;;
    sweep)  $REF -n -r $r -b 32 -e signed -c $c $f synth 2 sine 20:20000 gain -3 ;;
    noise)  $REF -n -r $r -b 32 -e signed -c $c $f synth 2 whitenoise gain -1 ;;
    hot)    $REF -n -r $r -b 32 -e signed -c $c $f synth 2 square 60 gain -0.1 ;;
    silence)$REF -n -r $r -b 32 -e signed -c $c $f trim 0 2 ;;
  esac 2>/dev/null
  echo $f
}
for dr in 2822400 5644800 11289600 22579200 45158400; do
 for c in 1 2 6; do
  for sig in sine sweep noise hot silence; do
   for sr in 88200 176400; do
    in=$(gen $sig $sr $c)
    ref=$T/ref.dsf; rm -f $ref
    SOX_DSD_KERNEL_SDM=scalar $REF -D $in -r $dr $ref pcmdsd $dr 2>$T/err || { echo "REF ERR $dr $c $sig $sr: $(head -1 $T/err)"; err=$((err+1)); continue; }
    rh=$(sha256sum $ref | cut -c1-16)
    for t in auto scalar sse2 avx1 avx2 avx512; do
      o=$T/new-$t.dsf; rm -f $o
      if [ $t = auto ]; then $NEW -D $in -r $dr $o pcmdsd $dr 2>$T/err; else SOX_DSD_KERNEL_SDM=$t $NEW -D $in -r $dr $o pcmdsd $dr 2>$T/err; fi
      if [ $? -ne 0 ]; then echo "NEW ERR $t $dr $c $sig $sr: $(head -1 $T/err)"; err=$((err+1)); continue; fi
      nh=$(sha256sum $o | cut -c1-16)
      if [ "$nh" = "$rh" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "DIFF $t $dr ch=$c $sig $sr ref=$rh new=$nh"; fi
    done
   done
  done
 done
done
echo "PASS=$pass FAIL=$fail ERR=$err"
