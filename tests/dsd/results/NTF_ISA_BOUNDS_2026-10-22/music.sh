#!/bin/bash
T=/home/daedalus/.claude/jobs/f4718c32/tmp
O=$T/isa/music; mkdir -p $O
: > $O/progress.txt
for c in o7-r5-a20 o7-r8-a20; do
  Q=$T/qual-$c/source
  B=$(cat $T/isa-bounds-$c.txt)
  prof="encode.experimental.ntf.$c.dsd512"
  for k in scalar sse2 avx1 avx2 avx512; do
    for s in src5 src1; do
      LSX_DSD_SDM_KERNEL=$k $Q/test/dsd_test_p10 --render-candidate 176400 22579200 \
        "$prof" .5 guarded $T/commercial/$s.f64le \
        $O/$c-$k-$s.bits $O/$c-$k-$s.json $B > $O/$c-$k-$s.log 2>&1
      echo "rc=$? $c $k $s" >> $O/progress.txt
      sha256sum $O/$c-$k-$s.bits | cut -d' ' -f1 >> $O/$c-$k-$s.sha
      rm -f $O/$c-$k-$s.bits
    done
  done
done
echo done > $O/DONE
