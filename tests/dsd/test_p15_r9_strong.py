"""Reject malformed or unbound P15 R9 high-rate global SRC certificates."""
from fractions import Fraction as F
from pathlib import Path
import copy,json,tempfile,unittest

from p15_r9_src_strong import REQUIRED, trusted_header, verify_one, ExactRefusal

HERE=Path(__file__).resolve().parent
WITNESSES=HERE/'results/P15_R9_STRONG_SRC_2026-10-19'
TARGET='dsd256.mastering_v2.pcm96000'

class R9StrongAdversarial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads((WITNESSES/(TARGET+'.json')).read_text())

    def verify_corrupt(self,obj,msg):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.json';path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ExactRefusal,msg):verify_one(TARGET,path)

    def test_source_hash_is_bound(self):
        self.assertEqual(self.original['status'],'CANDIDATE')
        self.assertEqual(self.original['exact_tap_sha256'],trusted_header(TARGET)['exact_tap_sha256'])

    def test_mutated_stage_coeff_digest_refuses(self):
        x=copy.deepcopy(self.original);x['exact_tap_sha256']='0'*64
        self.verify_corrupt(x,'identity mismatch')

    def test_mutated_math_kernel_refuses(self):
        x=copy.deepcopy(self.original);x['method']['p15_r7_fast_fir.py']='0'*64
        self.verify_corrupt(x,'identity mismatch')

    def test_mutated_inequality_refuses(self):
        x=copy.deepcopy(self.original);x['target_cap']='1/1000'
        self.verify_corrupt(x,'identity mismatch')

    def test_missing_entire_src_leaf_refuses(self):
        x=copy.deepcopy(self.original)
        x['leaves']=[v for v in x['leaves'] if v[0]!='0']
        self.verify_corrupt(x,'gap or overlap')

    def test_missing_upper_endpoint_refuses(self):
        x=copy.deepcopy(self.original)
        x['leaves']=[v for v in x['leaves'] if F(v[1])!=F(1,4)]
        self.verify_corrupt(x,'missing high endpoint')

    def test_open_witness_refuses(self):
        x=copy.deepcopy(self.original);x['status']='OPEN'
        self.verify_corrupt(x,'not complete')

    def test_noncanonical_endpoint_refuses(self):
        x=copy.deepcopy(self.original);x['leaves'][0][0]='00'
        self.verify_corrupt(x,'noncanonical endpoint')

    def test_all_stage_manifest_has_three_cells(self):
        self.assertEqual(set(REQUIRED),{p.stem for p in WITNESSES.glob('*.json')})

if __name__=='__main__':unittest.main()
