#!/usr/bin/env python3
"""Small, independent invariants for the nonproduction residual diagnostic."""
import hashlib
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import diagnose_residual_asymmetry as diagnostic


class ResidualAnalysisInvariants(unittest.TestCase):
    def test_source_is_exact_frozen_prequantization_signal(self):
        _, frozen, meta, unquantized = diagnostic.reference_source()
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         'b8e8d07fa56c346147850c32e1faeead2ef3aab0dbd681435083176a8a52cd4d')
        rounded = np.rint(np.frombuffer(unquantized, '<f8') * (2**31 - 1)).astype('<i4')
        self.assertEqual(hashlib.sha256(rounded.tobytes()).hexdigest(), meta['source_i32le_sha256'])
        source = np.frombuffer(frozen, '<f8')
        high = np.frombuffer(unquantized, '<f8')
        samples = slice(int(.4 * diagnostic.SAMPLE_HZ), int(1.2 * diagnostic.SAMPLE_HZ))
        floor = math.sqrt(float(np.mean(((source[samples] - high[samples])/2.)**2)))
        self.assertAlmostEqual(diagnostic.dbfs_equivalent(floor), -200.42907562, delta=.001)

    def test_spectral_partition_and_sinusoid_rejection(self):
        # One almost-periodic multi-band noise surrogate plus fitted tone/DC.
        sr = diagnostic.SAMPLE_HZ
        n = np.arange(round(1.6 * sr), dtype=np.float64)
        waveform = (.25*np.sin(2*np.pi*997*n/sr) + .012345
                    + 1e-6*np.sin(2*np.pi*11003*n/sr)
                    + 3e-6*np.sin(2*np.pi*50123*n/sr))
        measured = diagnostic.residual_and_bands(waveform)
        total_power = measured['residual_rms']**2
        partition_power = sum(b['rms']**2 for b in measured['bands'].values())
        self.assertAlmostEqual(partition_power/total_power, 1., delta=1e-10)
        self.assertAlmostEqual(measured['fundamental_peak'], .25, delta=1e-7)
        self.assertAlmostEqual(measured['residual_rms'], math.sqrt(5)*1e-6, delta=3e-8)
        self.assertGreater(measured['bands']['40000-60000Hz']['rms'],
                           measured['bands']['0-20000Hz']['rms'])

    def test_compromised_replay_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'digest changed'):
            diagnostic.check_reference({'packed_sha256': '0'*64}, 'dsd512', 'v1')

    def test_atomic_write_once_idempotent_but_not_overwriting(self):
        with tempfile.TemporaryDirectory() as t:
            dest = Path(t) / 'evidence.json'
            diagnostic.publish_write_once(dest, b'{"test":true}\n')
            diagnostic.publish_write_once(dest, b'{"test":true}\n')
            self.assertEqual(dest.read_bytes(), b'{"test":true}\n')
            with self.assertRaisesRegex(RuntimeError, 'Refusing to overwrite'):
                diagnostic.publish_write_once(dest, b'{"test":false}\n')
            self.assertEqual(dest.read_bytes(), b'{"test":true}\n')
            self.assertEqual(list(Path(t).iterdir()), [dest])


if __name__ == '__main__':
    unittest.main()
