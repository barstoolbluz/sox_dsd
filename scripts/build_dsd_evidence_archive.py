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


def sanitize_material(raw: bytes, relative: str) -> tuple[bytes, dict[str, int], bool]:
    """Publish only safe redactions; never resize a structured binary."""
    is_binary = b'\x00' in raw[:4096]
    binary_redacted = False
    if is_binary and any(pat.search(raw) for pat in PATH_PATTERNS.values()):
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
    return sanitized, counts, binary_redacted


def historical_blobs(root: Path, policy: dict) -> tuple[list[tuple[str, str]], int]:
    """Collect ALL distinct historical file contents removed by the rewrite.

    A checkout only exposes HEAD. Earlier versions and files deleted before
    HEAD would otherwise disappear from both rewritten history and evidence.
    """
    index = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-s', '-z'])
    current = {}
    for item in index.split(b'\x00'):
        if not item:
            continue
        meta, raw_path = item.split(b'\t', 1)
        mode, oid, stage = meta.split()
        if stage != b'0':
            raise RuntimeError('unmerged Git index in evidence source')
        name = raw_path.decode('utf-8', 'surrogateescape')
        if selected(name, policy):
            if mode not in (b'100644', b'100755'):
                raise RuntimeError(f'unsupported evidence file mode: {name}')
            current[name] = oid.decode('ascii')

    command = ['git', '-C', str(root), 'log', '--all', '-m', '--raw',
               '--no-abbrev', '--no-renames', '--format=']
    log = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert log.stdout is not None
    pairs = set()
    try:
        for line in log.stdout:
            if not line.startswith(b':'):
                continue
            meta, separator, raw_path = line.rstrip(b'\n').partition(b'\t')
            if not separator:
                raise RuntimeError('unparseable Git raw history record')
            name = raw_path.decode('utf-8', 'surrogateescape')
            if not selected(name, policy):
                continue
            fields = meta[1:].split()
            if len(fields) != 5:
                raise RuntimeError(f'unsupported Git raw history record: {line[:100]!r}')
            old_mode, new_mode, old_oid, new_oid, _operation = fields
            if any(mode not in (b'000000', b'100644', b'100755')
                   for mode in (old_mode, new_mode)):
                raise RuntimeError(f'unsupported historical evidence mode: {name}')
            for oid in (old_oid, new_oid):
                if oid != b'0' * 40:
                    if not re.fullmatch(rb'[0-9a-f]{40}', oid):
                        raise RuntimeError(f'unsupported historical Git hash: {name}')
                    pairs.add((name, oid.decode('ascii')))
    finally:
        log.stdout.close()
    if log.wait():
        raise RuntimeError('Git historical evidence scan failed')
    if not set(current.items()) <= pairs:
        raise RuntimeError('current evidence missing from historical file scan')
    extra = pairs - set(current.items())
    vanished_paths = len({path for path, _ in extra} - set(current))
    return sorted(extra), vanished_paths


def stream_git_blobs(root: Path, versions: list[tuple[str, str]]):
    """Use one Git batch process rather than 1 subprocess per revision."""
    process = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert process.stdin is not None and process.stdout is not None
    try:
        for path, oid in versions:
            process.stdin.write((oid + '\n').encode('ascii'))
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[0] != oid.encode() or header[1] != b'blob':
                raise RuntimeError(f'missing or non-blob historical evidence: {oid}')
            length = int(header[2])
            raw = process.stdout.read(length)
            if len(raw) != length or process.stdout.read(1) != b'\n':
                raise RuntimeError(f'truncated historical Git blob: {oid}')
            actual = hashlib.sha1(b'blob ' + str(length).encode() + b'\x00' + raw).hexdigest()
            if actual != oid:
                raise RuntimeError(f'Git blob SHA-1 mismatch: {oid}')
            yield path, oid, raw
    finally:
        process.stdin.close()
        process.stdout.close()
        if process.wait():
            raise RuntimeError('Git historical blob stream failed')


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
    versions, historical_only_paths = historical_blobs(source, policy)
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
            sanitized, counts, binary_redacted = sanitize_material(raw, relative)
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

        historic_records = []
        for relative, oid, raw in stream_git_blobs(source, versions):
            archive_path = f'history/{oid}/{relative}'
            sanitized, counts, binary_redacted = sanitize_material(raw, archive_path)
            write_bytes(stage / archive_path, sanitized)
            record = dict(path=relative, git_blob_oid=oid, archive_path=archive_path,
                          original_sha256=sha(raw), published_sha256=sha(sanitized),
                          size=len(sanitized))
            if binary_redacted:
                record['binary_path_scrubbed'] = True
                totals['historical_binary_path_scrubbed'] += 1
            if counts:
                record['redactions'] = counts
                totals['historical_modified_files'] += 1
                for k, n in counts.items():
                    totals['historical_' + k] += n
            historic_records.append(record)
            totals['historical_entries'] += 1
            totals['historical_original_bytes'] += len(raw)
            totals['historical_published_bytes'] += len(sanitized)
        totals['historical_only_paths'] = historical_only_paths

        manifest = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n'
                           for r in records).encode('utf-8')
        write_bytes(stage / 'MANIFEST.jsonl', manifest)
        history_manifest = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n'
                                   for r in historic_records).encode('utf-8')
        write_bytes(stage / 'HISTORY_MANIFEST.jsonl', history_manifest)
        write_bytes(stage / 'REDACTIONS.json',
                    (json.dumps({'counts': dict(totals),
                                 'changed': [{k: r[k] for k in ('path','redactions')}
                                             for r in records if 'redactions' in r],
                                 'history_changed': [{k: r[k] for k in
                                                      ('archive_path','path','git_blob_oid','redactions')}
                                                     for r in historic_records if 'redactions' in r]},
                                indent=2, sort_keys=True) + '\n').encode())
        readme = f'''# SoX DSD 1.1.1 qualification and process archive

Source: `sox_dsd-1.1.1` at `{revision}` (before history rewrite).
Released separately from the source tarball. All entries under `files/` retain
repository-relative paths for forensic traceability. This is NOT a checkout
and is not required to build or run SoX DSD.

`MANIFEST.jsonl` records the original and published SHA-256 of every item.
`HISTORY_MANIFEST.jsonl` records distinct earlier file revisions removed from
the rewritten Git history, including files that were deleted before 1.1.1.
Each `history/<Git blob ID>/<original path>` entry records its original Git
blob ID as well as SHA-256 values before and after redaction. No earlier
evidence version is silently lost to the history rewrite.
Publication redacts host-specific filesystem paths in textual material.
`REDACTIONS.json` lists changed current and historical entries and counts
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
Additional historical versions: {totals['historical_entries']:,}
Paths present only in history: {totals['historical_only_paths']:,}
Additional historical original bytes: {totals['historical_original_bytes']:,}
Additional historical published bytes: {totals['historical_published_bytes']:,}
Additional historical versions redacted: {totals['historical_modified_files']:,}
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
