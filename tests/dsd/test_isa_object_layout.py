#!/usr/bin/env python3
"""Regression: ISA disassembly reads actual compiled static and libtool objects."""
from pathlib import Path
import tempfile
import unittest
from check_p11_isa import resolve_built_object


class ObjectLayoutTests(unittest.TestCase):
    def test_static_object_first(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'src/.libs').mkdir(parents=True)
            direct = root/'src/tier.o'
            shared = root/'src/.libs/tier.o'
            direct.write_bytes(b'direct')
            shared.write_bytes(b'libtool')
            self.assertEqual(resolve_built_object(root, 'src/tier.o'), direct)

    def test_libtool_shared_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'src/.libs').mkdir(parents=True)
            shared = root/'src/.libs/tier.o'
            shared.write_bytes(b'libtool')
            self.assertEqual(resolve_built_object(root, 'src/tier.o'), shared)

    def test_missing_object_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(resolve_built_object(Path(d), 'src/tier.o'))


if __name__ == '__main__':
    unittest.main()
