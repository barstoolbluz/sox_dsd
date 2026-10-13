# Preliminary timing supervision correction

The first three `controlled/decode-*` runs used the preserved
`profile_decode_before_wait_fix.py`. Their CPU accounting and sampled profiles
remain usable, but their Python `wait(timeout=...)` supervision can add up to
about 50 ms of POSIX polling delay to a wall observation. Those wall medians
must not be used for small tier comparisons. The final script uses a blocking
wait plus a sleeping watchdog, preserves disk-backed logs and records timeouts.
The final report uses fresh reruns, not the affected wall timings.

This is a correction to investigation tooling, not a claimed defect in the
supplied physical measurements (the existing e2e runner captures pipes).
