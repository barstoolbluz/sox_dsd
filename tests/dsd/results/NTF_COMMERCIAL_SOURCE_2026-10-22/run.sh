#!/bin/bash
export PATH=/nix/store/bbx5g6qc1q2bbyypg7az3ckmb4pazm22-python3-3.13.12-env/bin:/usr/bin:/bin
T=/home/daedalus/.claude/jobs/f4718c32/tmp
O=$T/commercial/out; mkdir -p $O
one() { # workspace candKey stim
  local ws=$1 key=$2 s=$3
  local Q=$T/qual-$key/source
  local prof="encode.experimental.ntf.$key.dsd512"
  local g=$Q/tests/dsd/reference/ntf_new_$(echo $key|tr - _)_guard.json
  local bounds=$(python3 -c "
import json,sys
b=json.load(open('$g'))['bounds']
print(' '.join(float(x).hex() for x in b))")
  LSX_DSD_SDM_KERNEL=scalar $Q/test/dsd_test_p10 --render-candidate 176400 22579200 "$prof" .5 guarded     $T/commercial/$s.f64le $O/$key-$s.bits $O/$key-$s.json $bounds > $O/$key-$s.log 2>&1
  echo "rc=$? $key $s" >> $O/progress.txt
}
base() { # stim  -- CLANS-7 baseline via the v2 profile, P20 guards
  local s=$1
  local Q=$T/qual-o7-r8-a20/source
  local bounds=$(python3 -c "
import json
b=json.load(open('$Q/tests/dsd/reference/p20_dsd512_v2_guard.json'))
k=[v for v in b.values() if isinstance(v,list) and len(v)==8][0]
print(' '.join(float(x).hex() for x in k))")
  LSX_DSD_SDM_KERNEL=scalar $Q/test/dsd_test_p10 --render-candidate 176400 22579200 encode.mastering.v2.dsd512 .5 guarded     $T/commercial/$s.f64le $O/base-$s.bits $O/base-$s.json $bounds > $O/base-$s.log 2>&1
  echo "rc=$? base $s" >> $O/progress.txt
}
: > $O/progress.txt
for s in src1 src2 src3 src4 src5; do
  one x o7-r5-a20 $s &
  one x o7-r8-a20 $s &
  base $s &
  wait
done
echo done > $O/DONE
