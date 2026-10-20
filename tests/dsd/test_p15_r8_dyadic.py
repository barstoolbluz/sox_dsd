#!/usr/bin/env python3
"""R8 exact outward-quantization tests and fail-closed witness tampering."""
import unittest
import json
import tempfile
from pathlib import Path
from fractions import Fraction as F
from p15_r8_dyadic_engine import floor_dyadic,ceil_dyadic,DyadicComposite,GRID
from p15_r8_highrate_witness import verify,canonical_context
from p15_r6_exact_composite import ExactRefusal

class R8ProofTests(unittest.TestCase):
    def test_exact_signed_outward(self):
        for num in [-1023,-100,-7,-3,-2,-1,0,1,2,3,7,100,1023]:
            for den in [1,3,7,13,1009,2**205-7]:
                x=F(num,den);lo=floor_dyadic(x);hi=ceil_dyadic(x)
                self.assertLessEqual(lo,x);self.assertLessEqual(x,hi)
                self.assertGreaterEqual(x-lo,0);self.assertGreaterEqual(hi-x,0)
                self.assertLess(hi-lo,F(1,GRID)*2)
    def test_unsupported_type_rejected(self):
        for f in (floor_dyadic,ceil_dyadic):
            for x in (1.5,'1/2',None):
                with self.assertRaises(ExactRefusal):f(x)
    def test_source_operator_binds(self):
        job,op,binding=canonical_context()
        self.assertEqual(job['cell_id'],'dsd256.mastering_v2.pcm384000')
        self.assertEqual(job['lo'],'0');self.assertEqual(job['hi'],'1000')
        self.assertTrue(binding['source']['p15_r8_dyadic_engine.py'])
    def test_proof_mutations_refuse_early(self):
        original=Path(__file__).parent/'results/P15_R8_INDEPENDENT_2026-10-19/highrate_0_1000.json'
        if not original.exists():self.skipTest('live campaign proof unavailable')
        proof=json.loads(original.read_text())
        for field,new in [('schema','bad-schema'),('status','OPEN')]:
            with self.subTest(field=field):
                mutated=json.loads(json.dumps(proof));mutated[field]=new
                with tempfile.TemporaryDirectory() as td:
                    file=Path(td)/'mutation.json';file.write_text(json.dumps(mutated))
                    with self.assertRaises(ExactRefusal):verify(file)
        mutated=json.loads(json.dumps(proof));mutated['binding']['source']['p15_r8_dyadic_engine.py']='0'*64
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'mutation.json';file.write_text(json.dumps(mutated))
            with self.assertRaises(ExactRefusal):verify(file)
        mutated=json.loads(json.dumps(proof));mutated['leaves'][0]['lo']='1'
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'mutation.json';file.write_text(json.dumps(mutated))
            with self.assertRaises(ExactRefusal):verify(file)

if __name__=='__main__':unittest.main()
