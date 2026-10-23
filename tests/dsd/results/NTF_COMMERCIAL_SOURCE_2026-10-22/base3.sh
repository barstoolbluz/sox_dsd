#!/bin/bash
T=/home/daedalus/.claude/jobs/f4718c32/tmp
O=$T/commercial/out
Q=$T/qual-o7-r8-a20/source
: > $O/progress3.txt
for s in src1 src2 src3 src4 src5; do
  LSX_DSD_SDM_KERNEL=scalar $Q/test/dsd_test_p10 --render 176400 22579200 \
    encode.mastering.v2.dsd512 .5 guarded \
    $T/commercial/$s.f64le $O/base3-$s.bits $O/base3-$s.json > $O/base3-$s.log 2>&1
  echo "rc=$? base3 $s" >> $O/progress3.txt
done
echo done > $O/DONE3
