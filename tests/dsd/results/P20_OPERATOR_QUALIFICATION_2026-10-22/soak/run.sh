#!/bin/bash
cd /home/daedalus/dev/sox_ng
export PATH=/nix/store/bbx5g6qc1q2bbyypg7az3ckmb4pazm22-python3-3.13.12-env/bin:/usr/bin:/bin
W=/home/daedalus/.claude/jobs/f4718c32/tmp/D512
one() {
  taskset -c $1 python3 tests/dsd/p20_soak_run.py --rate 22579200 --seconds 3600 \
    --mode $2 --prefix $W/soak/$3 --unit test/dsd_test_p10 --timeout-seconds 5400 \
    > $W/soak/$3.log 2>&1
  echo "rc=$?" > $W/soak/$3.done
}
one 24 nominal-v2  p20-nominal &
one 25 original-v1 p20-stress &
wait
echo done > $W/soak/ALLDONE
