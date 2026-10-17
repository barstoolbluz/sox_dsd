"""Adversarial atomic and idempotent operator-observation tests."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from p15_src_operator_observations import write_new


class OperatorAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'source-bound-operator'
        self.info = dict(schema='P15/private-src-operator-observations/1',
                         status='OBSERVED_UNCERTIFIED', qualified=False,
                         exporter_source_sha256='f'*64)
        self.array = np.arange(24, dtype='<f8').reshape(3, 8)

    def test_idempotent_same_array(self):
        write_new(self.path,self.info,self.array)
        before = {p.name:p.read_bytes() for p in self.path.iterdir()}
        write_new(self.path,self.info,self.array)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.path.iterdir()})
        self.assertEqual(json.loads(before['operator-observations.json'])['status'],
                         'OBSERVED_UNCERTIFIED')

    def test_mismatched_replay_refused(self):
        write_new(self.path,self.info,self.array)
        with self.assertRaises(FileExistsError):
            write_new(self.path,self.info,self.array+1)

    def test_digest_relabeling_cannot_hide_tamper(self):
        write_new(self.path,self.info,self.array)
        altered = self.path/'phase-f64.npy'
        buf = bytearray(altered.read_bytes())
        buf[-5] ^= 1
        altered.write_bytes(buf)
        import hashlib
        receipt = self.path/'operator-observations.json'
        data=json.loads(receipt.read_text())
        data['phase_array_sha256']=hashlib.sha256(buf).hexdigest()
        receipt.write_text(json.dumps(data))
        with self.assertRaises(FileExistsError):
            write_new(self.path,self.info,self.array)

    def test_empty_incomplete_directory_refused(self):
        self.path.mkdir()
        with self.assertRaises(FileExistsError):
            write_new(self.path,self.info,self.array)

    def test_no_files_exposed_on_serialization_failure(self):
        with self.assertRaises(ValueError):
            write_new(self.path,self.info,np.asarray([object()],dtype=object))
        self.assertFalse(self.path.exists())


if __name__=='__main__': unittest.main()
