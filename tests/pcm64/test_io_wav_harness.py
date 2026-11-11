#!/usr/bin/env python3
"""Small negative controls for io-wav qualification accounting."""
import os
from pathlib import Path
import signal
import tempfile
import unittest

from io_wav import CaseRunner, classify_native_capability, digest


class ArithmeticAccounting(unittest.TestCase):
    def test_capability_matrix(self):
        for build, host, status, expected in (
            ('ENABLED', 'SUPPORTED', 'OK', True),
            ('ENABLED', 'UNSUPPORTED', 'UNSUPPORTED', False),
            ('DISABLED', 'SUPPORTED', 'UNSUPPORTED', False),
            ('DISABLED', 'UNSUPPORTED', 'UNSUPPORTED', False),
        ):
            with self.subTest(build=build, host=host, status=status):
                self.assertEqual(classify_native_capability(build, host, status), expected)

    def test_broken_guard_is_never_not_run(self):
        for build, host, status in (
            ('ENABLED', 'SUPPORTED', 'NUMERIC'),
            ('ENABLED', 'SUPPORTED', 'UNSUPPORTED'),
            ('ENABLED', 'UNSUPPORTED', 'OK'),
            ('ENABLED', 'UNSUPPORTED', 'NUMERIC'),
            ('DISABLED', 'SUPPORTED', 'OK'),
            ('DISABLED', 'SUPPORTED', 'NUMERIC'),
            ('unexpected', 'SUPPORTED', 'UNSUPPORTED'),
        ):
            with self.subTest(build=build, host=host, status=status):
                with self.assertRaises(AssertionError):
                    classify_native_capability(build, host, status)


@unittest.skipUnless(os.name == 'posix', 'needs POSIX executable scripts and signals')
class CommandRefusalAccounting(unittest.TestCase):
    def run_command(self, contents, expected, should_pass):
        with tempfile.TemporaryDirectory(prefix='io-wav-refusal-accounting-') as tmp:
            root=Path(tmp)
            probe=root/'probe'
            probe.write_text('#!/bin/sh\n'+contents+'\n')
            probe.chmod(0o700)
            runner=CaseRunner(probe, probe, root)
            if should_pass:
                runner.invoke(['anything'],expect=expected)
            else:
                with self.assertRaisesRegex(AssertionError, 'unexpected exit'):
                    runner.invoke(['anything'],expect=expected)
            self.assertEqual(runner.executed_binary_sha256[str(probe)], digest(probe))
            self.assertEqual(len(runner.commands), 1)

    def test_expected_refusal_exits(self):
        self.run_command('exit 1', 1, True)
        self.run_command('exit 2', 2, True)

    def test_wrong_refusal_exit_cannot_pass(self):
        self.run_command('exit 2', 1, False)
        self.run_command('exit 1', 2, False)

    def test_signal_cannot_pass_as_refusal(self):
        self.run_command('kill -TERM $$', 1, False)


class ExactMetadataAccounting(unittest.TestCase):
    def test_exact_metadata(self):
        with tempfile.TemporaryDirectory(prefix='io-wav-metadata-') as tmp:
            root=Path(tmp)
            probe=root/'unused-probe'
            runner=CaseRunner(probe,probe,root)
            values={'rate':'44100','channels':'2','frames':'10','bits':'64',
                    'valid':'64','mask':'00000003','ext':'1','big':'0',
                    'bytes':'160'}
            def exercise(fields, passes):
                runner.invoke=lambda *a, **kw: (
                    (' '.join(f'{k}={v}' for k,v in fields.items())+'\n').encode(), b'')
                if passes:
                    runner.query(root/'fixture.wav',frames=10,channels=2,bits=64,
                                 mask=3,ext=True)
                else:
                    with self.assertRaisesRegex(AssertionError,'metadata mismatch'):
                        runner.query(root/'fixture.wav',frames=10,channels=2,bits=64,
                                     mask=3,ext=True)
            exercise(values,True)
            for key,wrong in (('rate','48000'),('channels','20'),
                              ('frames','100'),('bits','640'),('valid','32'),
                              ('mask','000000030'),('ext','0'),('big','01'),
                              ('bytes','1600')):
                with self.subTest(key=key):
                    exercise({**values,key:wrong},False)
            # A duplicate key cannot be silently overwritten by dict().
            runner.invoke=lambda *a, **kw: (
                (' '.join(f'{k}={v}' for k,v in values.items())+' frames=10\n').encode(),b'')
            with self.assertRaisesRegex(AssertionError,'metadata mismatch'):
                runner.query(root/'fixture.wav',frames=10,channels=2,bits=64,
                             mask=3,ext=True)


if __name__ == '__main__':
    unittest.main()
