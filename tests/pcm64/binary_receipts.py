#!/usr/bin/env python3
"""Content identities of runtime linker dependencies for PCM64 test receipts.

Linux/ldd is observational. Callers record explicitly dlopened plugins and
LD_PRELOAD test shims separately, since neither appears in ldd's program list.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def executable_libraries(program: Path) -> dict[str, str]:
    if sys.platform != 'linux' or shutil.which('ldd') is None:
        return {}
    run = subprocess.run(['ldd', str(program)], capture_output=True,
                         text=True, timeout=10)
    if run.returncode:
        return {}
    libraries = {}
    for line in run.stdout.splitlines():
        fields = line.strip().replace('=>', ' ').split()
        path = next((Path(field) for field in fields if field.startswith('/') and
                     Path(field).is_file()), None)
        if path is not None:
            resolved = path.resolve()
            libraries[str(resolved)] = digest(resolved)
    return libraries
