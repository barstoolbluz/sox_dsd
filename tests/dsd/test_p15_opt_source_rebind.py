"""Rebinding must preserve immutable source evidence and fail closed on drift."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
from hashlib import sha256

from p15_src_bound_operator import source_identity, UnboundOperator, sha_file
from p15_src_capture_matrix import verify_pair,DEFAULT
from p15_full_band_campaign import canonical_plan,source_operators
from p15_src_opt_build_contract import check_flags,BuildContractError
from p15_src_complete_aliases import all_active_cells

ROOT=Path(__file__).resolve().parents[2]
FROZEN=ROOT/'tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16'


class RebindTests(unittest.TestCase):
    def test_all_24_freshly_bound_operators_and_unchanged_captured_design(self):
        pairs=sorted({(c['intermediate_hz'],c['output_hz']) for c in all_active_cells()})
        self.assertEqual(len(pairs),24)
        for a,b in pairs:
            with self.subTest(pair=(a,b)):
                original=FROZEN/f'{a}-{b}'
                active=DEFAULT/f'{a}-{b}'
                before=json.loads((original/'operator-binding.json').read_text())
                after,op=verify_pair(active,a,b)
                self.assertEqual(after['source_sha256'],source_identity())
                self.assertEqual(after['snapshot_sha256'],before['snapshot_sha256'])
                self.assertEqual((original/'stage-snapshot.json').read_bytes(),
                                 (active/'stage-snapshot.json').read_bytes())
                self.assertEqual(after['status'],'SOURCE_BOUND_UNCERTIFIED')
                self.assertFalse(after['qualified'])
                changed={name for name,h in after['source_sha256'].items()
                         if h!=before['source_sha256'][name]}
                # Frozen 2026-10-16 -> current: first the two optimization
                # changes, then three reviewed 2026-10-20 non-SRC drifts.
                # This exact set stays fail-closed on any subsequent edit.
                self.assertEqual(changed,{'src/rate_poly_fir0.h',
                                          'tests/dsd/p15_src_capture_matrix.py',
                                          'src/dsd.c', 'src/dsd_public.c',
                                          'test/Makefile.am'})
                self.assertEqual((op.input_hz,op.output_hz),(a,b))
        self.assertEqual(len(source_operators(canonical_plan('1000'))),24)

    def test_old_bindings_still_fail_closed_and_tampering_rejected(self):
        with self.assertRaises(UnboundOperator):verify_pair(FROZEN/'88200-48000',88200,48000)
        pair=DEFAULT/'88200-48000'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            snapshot=p/'stage-snapshot.json'
            binding=p/'operator-binding.json'
            snapshot.write_bytes((pair/'stage-snapshot.json').read_bytes())
            doc=json.loads((pair/'operator-binding.json').read_text())
            doc['source_sha256']['src/rate_poly_fir0.h']='0'*64
            binding.write_text(json.dumps(doc))
            with self.assertRaises(UnboundOperator):verify_pair(p,88200,48000)
            binding.write_bytes((pair/'operator-binding.json').read_bytes())
            snapshot.write_bytes(snapshot.read_bytes()+b' ')
            with self.assertRaises(UnboundOperator):verify_pair(p,88200,48000)

    def test_contraction_off_is_mandatory_for_qualified_opt_in(self):
        base='-O2 -g -DLSX_RATE_ORDERED_OPT=1 -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1'
        self.assertTrue(check_flags(base+' -ffp-contract=off')['qualified_opt_in_cflags'])
        for flags in [base,base+' -ffp-contract=fast',base+' -ffp-contract=off -ffp-contract=fast',
                      base+' -ffp-contract=off -ffast-math',
                      base+' -ffp-contract=off -Ofast',
                      base+' -ffp-contract=off -funsafe-math-optimizations',
                      '-O2 -g -DLSX_RATE_ORDERED_OPT=1 -ffp-contract=off',
                      '-O2 -g -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1 -ffp-contract=off']:
            with self.subTest(flags=flags),self.assertRaises(BuildContractError):
                check_flags(flags)

if __name__=='__main__': unittest.main()
