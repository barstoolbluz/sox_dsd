#!/usr/bin/env python3
"""Build a deterministic, redacted release-asset archive from a PRE-CLEANUP checkout.

Run from any directory with --source pointing to the original pre-rewrite
sox_dsd-1.1.1 checkout. This script lives in the cleaned repository, which
intentionally has no source evidence left to archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

POLICY = Path(__file__).with_name('repo_cleanup_policy.json')
# Host-specific locations, not stable system dependencies (e.g. /usr, /dev,
# /nix/store). Keep useful paths in original build commands and test recipes.
PATH_PATTERNS = {
    'unix-user-or-workspace': re.compile(
        rb'/(?:(?:home|Users|mnt|tmp|private|media|Volumes|workspace|workspaces|'
        rb'var/tmp|var/folders|run/user)/)[^\s\x00<>\x22\x27\x60\\]+'),
    'windows-profile': re.compile(
        rb'(?i:(?:[a-z]:\\(?:Users|Documents and Settings)\\|\\\\[^\\\s]+\\Users\\))'
        rb'[^\s\x00<>\x22\x27\x60]+'),
}
REPLACEMENT = b'[LOCAL_PATH_REDACTED]'


def git_files(root: Path) -> list[str]:
    completed = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                               capture_output=True, check=True)
    return sorted(p.decode('utf-8', 'surrogateescape')
                  for p in completed.stdout.split(b'\x00') if p)


def selected(path: str, policy: dict) -> bool:
    return (path in policy['exact_paths'] or
            any(path.startswith(prefix) for prefix in policy['prefixes']))


def sha(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as reader:
        for chunk in iter(lambda: reader.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize(data: bytes) -> tuple[bytes, dict[str, int]]:
    counts: dict[str, int] = {}
    out = data
    for name, pat in PATH_PATTERNS.items():
        out, count = pat.subn(REPLACEMENT, out)
        if count:
            counts[name] = count
    for pat in PATH_PATTERNS.values():
        if pat.search(out):
            raise RuntimeError('path redaction failed')
    return out, counts


def write_bytes(path: Path, buf: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf)
    path.chmod(0o644)


def run_archive(source: Path, output: Path, policy: dict, *, compression: int) -> None:
    if not (source / '.git').exists():
        raise SystemExit('--source must be the original checked-out git repository')
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != policy['base_commit']:
        raise SystemExit(f'wrong source revision {revision}; expected {policy["base_commit"]}')
    # HEAD alone does not establish which bytes are in a working checkout.
    # Never silently archive modified tracked evidence under a baseline ID.
    status = subprocess.run(['git', '-C', str(source), 'status', '--porcelain',
                             '--untracked-files=no'], capture_output=True,
                            text=True, check=True)
    if status.stdout.strip():
        raise SystemExit('original evidence checkout has uncommitted tracked changes')
    selected_files = [p for p in git_files(source) if selected(p, policy)]
    if not selected_files or 'P15_HIGH_RATE_SOURCE_MANIFEST.json' not in selected_files:
        raise SystemExit('source appears already cleaned; original evidence is required')
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    totals = Counter()
    output_temp = output.with_name(output.name + '.incomplete')
    if output_temp.exists():
        raise SystemExit(f'refusing to overwrite incomplete output: {output_temp}')

    with tempfile.TemporaryDirectory(prefix='sox-dsd-evidence-') as tmp:
        stage = Path(tmp) / 'SoX_DSD_1.1.1_Evidence'
        stage.mkdir()
        content_dir = stage / 'files'
        for idx, relative in enumerate(selected_files, 1):
            src = source / relative
            if src.is_symlink() or not src.is_file():
                raise RuntimeError(f'unsafe or missing archive source: {relative}')
            dest = content_dir / relative
            raw = src.read_bytes()
            # Redact byte patterns in all formats where they can occur as raw
            # strings. A binary item containing a path must be rejected, not
            # silently corrupted by replacing bytes inside its structure.
            is_binary = b'\x00' in raw[:4096]
            binary_redacted = False
            if is_binary and any(pat.search(raw) for pat in PATH_PATTERNS.values()):
                # Some archived host-built ELF test executables contain full
                # checkout paths in debug sections. Keep the binary layout
                # byte-for-byte *sized*, but not its original hash or claims
                # of executable validity: the asset is forensic evidence.
                # Unknown binary formats fail closed rather than risk breaking
                # a structured archive such as NPZ or ZIP.
                if not raw.startswith(b'\x7fELF'):
                    raise RuntimeError(f'unsupported binary needs redaction: {relative}')
                sanitized = raw
                counts = {}
                for name, pat in PATH_PATTERNS.items():
                    sanitized, n = pat.subn(lambda m: b'_' * len(m.group(0)), sanitized)
                    if n:
                        counts[name] = n
                binary_redacted = True
            else:
                sanitized, counts = (raw, {}) if is_binary else sanitize(raw)
            if not is_binary:
                try:
                    sanitized.decode('utf-8')
                except UnicodeDecodeError:
                    if sanitized != raw:
                        raise RuntimeError(f'non-UTF8 material needs manual redaction: {relative}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if raw == sanitized:
                try:
                    os.link(src, dest)
                except OSError:
                    shutil.copyfile(src, dest)
            else:
                write_bytes(dest, sanitized)
                dest.chmod(src.stat().st_mode & 0o777)
            record = dict(path=relative, original_sha256=sha(raw),
                          published_sha256=sha(sanitized), size=len(sanitized))
            if binary_redacted:
                record['binary_path_scrubbed'] = True
                totals['binary_path_scrubbed'] += 1
            if counts:
                record['redactions'] = counts
                totals['modified_files'] += 1
                for k, n in counts.items():
                    totals[k] += n
            records.append(record)
            totals['files'] += 1
            totals['original_bytes'] += len(raw)
            totals['published_bytes'] += len(sanitized)
            if idx % 5000 == 0:
                print(f'Prepared {idx}/{len(selected_files)} archived paths', file=sys.stderr, flush=True)

        manifest = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n'
                           for r in records).encode('utf-8')
        write_bytes(stage / 'MANIFEST.jsonl', manifest)
        write_bytes(stage / 'REDACTIONS.json',
                    (json.dumps({'counts': dict(totals),
                                 'changed': [{k: r[k] for k in ('path','redactions')}
                                             for r in records if 'redactions' in r]},
                                indent=2, sort_keys=True) + '\n').encode())
        readme = f'''# SoX DSD 1.1.1 qualification and process archive

Source: `sox_dsd-1.1.1` at `{revision}` (before history rewrite).
Released separately from the source tarball. All entries under `files/` retain
repository-relative paths for forensic traceability. This is NOT a checkout
and is not required to build or run SoX DSD.

`MANIFEST.jsonl` records the original and published SHA-256 of every item.
Publication redacts host-specific filesystem paths in textual material.
`REDACTIONS.json` lists changed file paths, redaction categories and counts
without redisclosing sensitive path values. Placeholder: `[LOCAL_PATH_REDACTED]`.
Archived ELF debug-path tokens are masked at their original byte width;
these modified executable files are forensic evidence, not runnable tools.
Other binary formats containing private path tokens cause a build error.
Non-identifying system paths such as `/usr`, `/dev` and immutable Nix store
references remain to preserve the meaning of build and test evidence.
Historical checksum manifests may refer to original, unredacted bytes;
compare them with `original_sha256`, not `published_sha256`.

Files: {totals['files']:,}
Original bytes: {totals['original_bytes']:,}
Published bytes: {totals['published_bytes']:,}
Files modified for path redaction: {totals['modified_files']:,}
Archived ELF files scrubbed at fixed byte width: {totals['binary_path_scrubbed']:,}
Redaction token counts: {json.dumps({k: v for k, v in totals.items() if k in PATH_PATTERNS}, sort_keys=True)}

This archive preserves historical test observations; it does not represent
newly rerun qualification. Raw private source recordings were not supplied.
'''
        write_bytes(stage / 'README.md', readme.encode())
        try:
            tar = subprocess.Popen(['tar', '--sort=name', '--mtime=@0',
                                    '--owner=0', '--group=0', '--numeric-owner',
                                    '--format=gnu', '-cf', '-', '-C', tmp,
                                    stage.name], stdout=subprocess.PIPE)
            assert tar.stdout is not None
            zstd = subprocess.Popen(['zstd', '-q', '-T4', f'-{compression}',
                                     '-o', str(output_temp)], stdin=tar.stdout)
            tar.stdout.close()
            zstd_rc = zstd.wait()
            tar_rc = tar.wait()
            if tar_rc or zstd_rc:
                raise RuntimeError(f'archive pipeline failed: tar={tar_rc}, zstd={zstd_rc}')
            subprocess.run(['zstd', '-tq', str(output_temp)], check=True)
            output_temp.replace(output)
        except BaseException:
            output_temp.unlink(missing_ok=True)
            raise
    print(json.dumps({'output': str(output), 'sha256': sha_file(output),
                      'bytes': output.stat().st_size, 'counts': dict(totals)}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compression', type=int, choices=range(1, 13), default=5)
    args = parser.parse_args()
    policy = json.loads(POLICY.read_text())
    run_archive(args.source.resolve(), args.output.resolve(), policy,
                compression=args.compression)


if __name__ == '__main__':
    main()
