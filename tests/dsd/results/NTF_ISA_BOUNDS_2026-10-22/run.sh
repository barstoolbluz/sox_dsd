#!/bin/bash
T=/home/daedalus/.claude/jobs/f4718c32/tmp
O=$T/isa/out; mkdir -p $O
: > $O/progress.txt
for c in o7-r5-a20 o7-r8-a20; do
  Q=$T/qual-$c/source
  B=$(cat $T/isa-bounds-$c.txt)
  prof="encode.experimental.ntf.$c.dsd512"
  for k in scalar sse2 avx1 avx2 avx512; do
    for st in dc-positive-60s dc-negative-60s; do
      LSX_DSD_SDM_KERNEL=$k $Q/test/dsd_test_p10 --render-candidate 176400 22579200 \
        "$prof" .5 guarded $T/qual-$c/stress/$c/$st.f64le \
        $O/$c-$k-$st.bits $O/$c-$k-$st.json $B > $O/$c-$k-$st.log 2>&1
      echo "rc=$? $c $k $st" >> $O/progress.txt
      rm -f $O/$c-$k-$st.bits
    done
  done
done
echo done > $O/DONE
