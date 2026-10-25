#!/usr/bin/env python3
"""Optional SoX decode mutator; set SOX_REAL and MUTATION to exercise the gate.

Probes and encoding must pass through unchanged. Mutations affect f64 stereo
output only, after a successful decode. This shim is test infrastructure.
"""
import os
import subprocess
import sys


def main():
    args = sys.argv[1:]
    real = os.environ.get('SOX_REAL')
    if not real:
        raise SystemExit('SOX_REAL is required')
    proc = subprocess.run([real, *args], stdin=subprocess.DEVNULL)
    if proc.returncode:
        return proc.returncode
    if 'trim' not in args:
        return 0
    # In the reader gate's SoX invocation, the destination is immediately
    # before the trim effect. Never attempt to mutate probes or source encoding.
    dest = args[args.index('trim') - 1]
    import numpy as np
    x = np.fromfile(dest, dtype='<f8')
    if x.size % 2:
        raise SystemExit('incomplete stereo f64 output')
    x = x.reshape(-1, 2)
    mutation = os.environ.get('MUTATION', 'swap')
    if mutation == 'swap':
        x = x[:, ::-1]
    elif mutation == 'gain':
        x = x * 1.05
    elif mutation == 'shift':
        x = np.roll(x, 64, axis=0)
    elif mutation == 'noise':
        x = np.random.default_rng(7).normal(0, x.std(), x.shape)
    elif mutation == 'truncate':
        x = x[:int(len(x) * 0.6)]
    elif mutation == 'dropout':
        pos = len(x) // 2
        hz = int(args[args.index('-r') + 1])
        x[pos:pos + min(len(x) - pos, max(1, int(round(hz * 0.01))))] = 0
    else:
        raise SystemExit(f'unknown MUTATION {mutation!r}')
    x.astype('<f8').tofile(dest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
