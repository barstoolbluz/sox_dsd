#!/bin/bash
T=/home/daedalus/.claude/jobs/f4718c32/tmp
D=$T/qual-d1024/source
O=$T/d1024isa/out2; mkdir -p $O
export PATH=$(cat $T/R3/PYPATH)/bin:/usr/bin:/bin
: > $O/progress.txt
for st in dc-positive dc-negative; do
  pol=0.49; [ $st = dc-negative ] && pol=-0.49
  python3 - "$O/$st.f64le" "$pol" <<'PY'
import sys,struct
p,v=sys.argv[1],float(sys.argv[2])
n=60*176400
open(p,'wb').write(struct.pack('<%dd'%n,*([v]*n)))
PY
done
for k in scalar sse2 avx1 avx2 avx512; do
  for st in dc-positive dc-negative; do
    LSX_DSD_SDM_KERNEL=$k $D/test/dsd_test_p10 --render 176400 45158400 \
      encode.mastering.v2.dsd1024 .5 guarded $O/$st.f64le \
      $O/$k-$st.bits $O/$k-$st.json > $O/$k-$st.log 2>&1
    echo "rc=$? $k $st" >> $O/progress.txt
    sha256sum $O/$k-$st.bits 2>/dev/null | cut -d' ' -f1 > $O/$k-$st.sha
    rm -f $O/$k-$st.bits
  done
done
echo done > $O/DONE
