#!/usr/bin/env python3
"""Release evidence redaction: determinism, path privacy, history immutability."""

# Allow standalone test tools to resolve their relocated sibling modules.
from pathlib import Path as _DSDPath
import sys as _DSDSys
_DSD = _DSDPath(__file__).resolve().parents[1]
_DSDSys.path[:0] = [str(_DSD / _part) for _part in
                    ('support', 'phases', 'generators', 'qualification',
                     'benchmarks', 'checks')] + [str(_DSD)]

from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[3]
script=root/'tests/dsd/qualification/sanitize_111_real_track_receipts.py'
source=root/'tests/dsd/results/V1_HIGH_RATE_ENCODE_2026-11-07/real-tracks/results.jsonl'
expected=root/'tests/dsd/release_evidence/v1_high_rate_real_tracks_redacted.jsonl'
sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if not source.is_file():
    # A distribution tarball ships only the redacted copy: check that alone.
    data=expected.read_bytes()
    assert len(data.splitlines())==800, 'redacted receipt is not 800 rows'
    for marker in (b'/home/',b'/Users/',b'/mnt/'):
        assert marker not in data, marker
    print('PASS: 800 shipped release rows carry no local paths (no source receipt)')
    sys.exit(0)
source_sha=sha(source)
subprocess.run([sys.executable,str(script),'--check'],check=True)
with tempfile.TemporaryDirectory(prefix='sox-release-redaction-') as temp:
    new=Path(temp)/'fresh.jsonl'
    subprocess.run([sys.executable,str(script),'--output',str(new)],check=True)
    assert new.read_bytes()==expected.read_bytes()
    assert b'/home/' not in new.read_bytes()
    assert b'/Users/' not in new.read_bytes()
    assert b'/mnt/' not in new.read_bytes()
    assert sha(source)==source_sha, 'historical receipt was changed'
print('PASS: 800 release rows sanitized, reproducible, source unchanged')
