#!/usr/bin/env python3
"""Offline P17 JSON probe double for collector integration tests."""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

import json
import sys


def main():
    if len(sys.argv) != 6:
        return 2
    _, source, profile, out, tier, mode = sys.argv
    if mode != 'full':
        return 2
    native = 22579200 * 10
    dest = int(out)
    print(json.dumps({'status': 'PASS_FUNCTIONAL_ONLY',
                      'packed_expanded_equal': True,
                      'rate_hz': 22579200, 'channels': 2,
                      'profile': profile, 'destination_hz': dest,
                      'kernel': tier, 'native_frames': native,
                      'pcm_frames': native * dest // 22579200,
                      'decode_wall_seconds': 1.0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
