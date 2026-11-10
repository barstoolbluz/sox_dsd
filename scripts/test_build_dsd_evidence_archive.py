#!/usr/bin/env python3
"""Small regression for the evidence exporter's full-history file inventory."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from build_dsd_evidence_archive import historical_blobs, sanitize_material, stream_git_blobs


class EvidenceHistoryTests(unittest.TestCase):
    def test_retired_files_and_overwritten_versions_are_retained(self):
        with tempfile.TemporaryDirectory(prefix='sox-dsd-history-regression-') as temp:
            repo = Path(temp)

            def git(*args: str) -> str:
                return subprocess.check_output(['git', '-C', str(repo), *args],
                                               text=True, stderr=subprocess.DEVNULL).strip()

            git('init', '-q')
            git('config', 'user.name', 'Evidence Regression')
            git('config', 'user.email', 'evidence@example.invalid')
            (repo / 'evidence').mkdir()
            (repo / 'evidence/current.txt').write_bytes(b'original\n')
            (repo / 'evidence/retired.txt').write_bytes(b'old retired\n')
            (repo / 'source.c').write_text('int main(void) { return 0; }\n')
            git('add', '.')
            git('commit', '-qm', 'initial')
            (repo / 'evidence/current.txt').write_bytes(b'/home/alice/private-audio\n')
            git('rm', '-q', 'evidence/retired.txt')
            git('add', '.')
            git('commit', '-qm', 'replace current and retire old evidence')
            (repo / 'evidence/current.txt').write_bytes(b'current\n')
            git('add', '.')
            git('commit', '-qm', 'latest')

            policy = {'exact_paths': [], 'prefixes': ['evidence/']}
            versions, vanished = historical_blobs(repo, policy)
            self.assertEqual(len(versions), 3)
            self.assertEqual(vanished, 1)
            payloads = {(path, raw) for path, oid, raw in stream_git_blobs(repo, versions)}
            self.assertEqual(payloads, {
                ('evidence/current.txt', b'original\n'),
                ('evidence/current.txt', b'/home/alice/private-audio\n'),
                ('evidence/retired.txt', b'old retired\n'),
            })
            redacted, counts, binary = sanitize_material(b'/home/alice/private-audio\n',
                                                         'evidence/current.txt')
            self.assertNotIn(b'/home/alice', redacted)
            self.assertEqual(counts, {'unix-user-or-workspace': 1})
            self.assertFalse(binary)
            self.assertEqual(git('show', 'HEAD:evidence/current.txt'), 'current')


if __name__ == '__main__':
    unittest.main()
