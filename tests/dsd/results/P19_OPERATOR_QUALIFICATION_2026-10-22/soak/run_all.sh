#!/bin/bash
cd /home/daedalus/dev/sox_ng
export PATH=/nix/store/bbx5g6qc1q2bbyypg7az3ckmb4pazm22-python3-3.13.12-env/bin:/usr/bin:/bin
W=/home/daedalus/.claude/jobs/f4718c32/tmp/P19
one() { # core rate mode runner tag
  taskset -c $1 python3 tests/dsd/$4 --rate $2 --seconds 3600 --mode $3 \
    --prefix $W/soak/$5 --unit test/dsd_test_p10 --timeout-seconds 5400 \
    > $W/soak/$5.log 2>&1
  echo "rc=$?" > $W/soak/$5.done
}
one 24 45158400 original-v1 p19_soak_run.py d1024-v1 &
one 25 45158400 nominal-v2  p19_soak_run.py d1024-v2 &
one 26 22579200 original-v1 p17_soak_run.py d512-v1 &
one 27 22579200 nominal-v2  p17_soak_run.py d512-v2 &
wait
echo done > $W/soak/ALLDONE
