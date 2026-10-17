"""Adversarial scope/coverage/replay tests; no invented numerical PASS."""
import json
import tempfile
import unittest
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from p15_full_band_campaign import (canonical_plan,windows,summarize,
                                     bindings,Unproved as CoverageError)
from p15_src_complete_aliases import all_active_cells
from p15_src_stagewise_continuum import PROFILE_BANDS
from bench_p15_dsd256_ps_matched import (commands,bootstrap_ratio,
        admissible_host,verify_report,ARMS,PROFILES,RATES,REPS,SCHEMA,
        BenchmarkError,BOOTSTRAP,SEED,sha)
from p15_dsd256_comparator_2026 import sources

class CoverageTests(unittest.TestCase):
    def test_exact_windows_no_overlap_or_gap(self):
        for end,step in [('20000','1000'),('20947.5','200'),('352800','1000')]:
            ints=list(windows(Fraction(0),Fraction(end),Fraction(step)))
            self.assertEqual(ints[0][0],0)
            self.assertEqual(ints[-1][-1],Fraction(end))
            self.assertTrue(all(a<b and (j==0 or ints[j-1][1]==a)
                                for j,(a,b) in enumerate(ints)))
    def test_exact_72_cell_profile_rates(self):
        jobs=canonical_plan('10000')
        groups=defaultdict(list)
        for j in jobs:groups[(j['cell_id'],j['mode'])].append(j)
        self.assertEqual(len(groups),144)
        source={c['id']:c for c in all_active_cells()}
        self.assertEqual(set(k for k,_ in groups),set(source))
        for (cid,mode),items in groups.items():
            c=source[cid];p=PROFILE_BANDS[c['profile']][0]
            edge=(min(Fraction(p),Fraction(475,1000)*min(c['intermediate_hz'],c['output_hz']))
                  if mode=='pass' else Fraction(c['output_hz'],2))
            self.assertEqual(Fraction(items[0]['lo']),0)
            self.assertEqual(Fraction(items[-1]['hi']),edge)
            self.assertTrue(all(Fraction(items[i]['hi'])==Fraction(items[i+1]['lo'])
                          for i in range(len(items)-1)))
        # A 44.1-kHz output must NOT be wrongly certified up to 30/48 kHz.
        adapt=next(j for j in jobs if j['profile']=='decode.mastering.v2.dsd128'
                   and j['output_hz']==44100 and j['mode']=='pass')
        self.assertEqual(Fraction(adapt['effective_p']),Fraction(475,1000)*44100)
    def test_missing_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            result=summarize(Path(d),chunk_hz='500000')
            self.assertEqual(result['status'],'OPEN')
            self.assertEqual(result['local_intervals_proven'],0)
            self.assertGreater(result['missing_receipts'],0)

class PhysicalBenchmarkTests(unittest.TestCase):
    def test_full_passband_command_shape_all_cells(self):
        for profile,p,s in PROFILES:
            for rate in RATES:
                cmds=commands(Path('/tmp/sox'),Path('/tmp/input.dsf'),profile,rate,p,s,Path('/tmp'))
                self.assertEqual(set(cmds),set(ARMS))
                ctl=cmds['legacy_ps_matched']
                self.assertEqual(ctl[-8:],['sinc','-a','180','-t',str(s-p),'-'+str((p+s)//2),'rate','-v'])
                self.assertNotIn('20000',ctl)
                self.assertEqual(ctl[ctl.index('sinc')-2:ctl.index('sinc')],['-v','352800'])
    def test_bootstrap_adversarial(self):
        slow=[3.0+i*.001 for i in range(REPS)]
        fast=[1.0+i*.001 for i in range(REPS)]
        proof=bootstrap_ratio(slow,fast)
        self.assertGreater(proof['ci95'][0],2)
        self.assertGreater(proof['point'],2)
        self.assertFalse(bootstrap_ratio(fast,slow)['exceeds_two_at_lower_bound'])
        with self.assertRaises(BenchmarkError):bootstrap_ratio(slow[:-1],fast)
        with self.assertRaises(BenchmarkError):bootstrap_ratio(slow,fast[:-1]+[float('nan')])
    def test_vm_unconditionally_refused(self):
        host=dict(system='Linux',machine='x86_64',cpu='x',microcode='1',
                  hypervisor=True,allowed_cpus=[0])
        self.assertFalse(admissible_host(host,0))
        host['hypervisor']=False
        self.assertTrue(admissible_host(host,0))
        self.assertFalse(admissible_host(host,1))
    def test_independent_receipt_replay_rejects_tamper(self):
        # A synthetic physical host is used ONLY to test replay logic. No
        # benchmark/host measurement or gate is claimed here.
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'report';folder.mkdir()
            (folder/'input-6ch.dsf').write_bytes(b'dummy-native')
            (folder/'input-6ch.wav').write_bytes(b'dummy-pcm')
            sox=Path(root)/'sox';sox.write_bytes(b'fake-executable')
            candidate=Path(root)/'candidate';candidate.write_bytes(b'fake-candidate')
            spectral=Path(root)/'spectral';spectral.mkdir()
            (spectral/'RECEIPT.json').write_text('fake-spectral')
            raw={arm:[1.+.001*i if arm=='decoder' else 3.+.001*i
                 for i in range(REPS)] for arm in ARMS}
            rows={}
            for profile,p,s in PROFILES:
                for rate in RATES:
                    rows[profile+'@'+str(rate)]=dict(pass_hz=p,stop_hz=s,rate=rate,
                       commands=commands(sox,Path('<fixture>'),profile,rate,p,s,Path('<output>')),
                       seconds=raw,comparisons={arm:bootstrap_ratio(raw[arm],raw['decoder'])
                                                for arm in ARMS[1:]})
            report=dict(schema=SCHEMA,qualified_release=False,
                 source_sha256=sources(),executable_sha256=dict(sox=sha(sox),candidate=sha(candidate)),
                 spectral_receipt_sha256=sha(spectral/'RECEIPT.json'),target=2.,
                 repetitions=REPS,warmups=2,bootstrap=dict(iterations=BOOTSTRAP,seed=SEED),
                 host=dict(system='Linux',machine='x86_64',cpu='test',microcode='1',
                           allowed_cpus=[0],hypervisor=False),
                 physical_host_admissible=True,pinned_cpu=0,
                 six_channel_native_sha256=sha(folder/'input-6ch.dsf'),
                 six_channel_pcm_sha256=sha(folder/'input-6ch.wav'),
                 status='MEASURED_PHYSICAL_UNADJUDICATED',rows=rows)
            file=folder/'RECEIPT.json';file.write_text(json.dumps(report))
            with patch('bench_p15_dsd256_ps_matched.verify_spectral',
                       return_value={'spectrally_matched_on_fixture':True}):
                self.assertEqual(len(verify_report(folder,spectral,sox,candidate)['rows']),4)
                report['rows'][next(iter(rows))]['comparisons']['legacy_direct']['ci95'][0]=99
                file.write_text(json.dumps(report))
                with self.assertRaises(BenchmarkError):
                    verify_report(folder,spectral,sox,candidate)
                file.write_text(json.dumps({**report,'rows':rows}))
                (folder/'input-6ch.dsf').write_bytes(b'changed')
                with self.assertRaises(BenchmarkError):
                    verify_report(folder,spectral,sox,candidate)

if __name__=='__main__':unittest.main()
