#!/usr/bin/env python3
"""P10 PCM_AUDIO collector contracts (synthetic smoke; never release evidence)."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

import corpus_pcm
import dsd_windows
from ratify_p10_gates import validate_domain, read, CRITERIA

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/dsd/fixtures'


class CollectorContracts(unittest.TestCase):
    def test_stream_matches_oracle_and_all_boundary_windows(self):
        for name in ('empty', 'one', 'seven', 'nine', 'mono_96', 'stereo_96',
                     'six_96', 'msb_stereo_96', 'block_minus_1', 'block_plus_1'):
            with self.subTest(name=name):
                result = dsd_windows.self_check(FIXTURES / (name+'.dsf'))
                self.assertTrue(result['bit_identical_to_oracle'])
                self.assertTrue(result['stream_stats_identical_to_oracle'])

    def test_dsf_rejects_truncation_and_wrong_layout(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'cut.dsf'
            path.write_bytes((FIXTURES/'stereo_96.dsf').read_bytes()[:-3])
            with self.assertRaisesRegex(ValueError, 'truncated'):
                dsd_windows.dsf_window_statistics(path)
            path.write_bytes(b'x'*100)
            with self.assertRaisesRegex(ValueError, 'invalid'):
                dsd_windows.dsf_window_statistics(path)

    def test_gain_ladder_rejects_silent_or_ambiguous_adjustments(self):
        self.assertEqual(corpus_pcm.gains('-0.1,-1,-3'), [0., -.1, -1., -3.])
        for text in ('+1', '0', '-0.1,-0.1', '-2,-1', 'nan', 'inf', 'oops', '-3,, -6'):
            with self.subTest(text=text), self.assertRaises(corpus_pcm.CorpusError):
                corpus_pcm.gains(text)

    def test_inventory_mapping_must_be_unique_and_registered(self):
        catalog = [{'release':'release 1', 'container':'flac', 'bits_per_sample':24,
                    'channels':2}]
        for entries in ([], [{'release':'missing','path':'f'}],
                        [{'release':'release 1','path':'f'}]*2,
                        [{'release':'release 1','path':''}]):
            with self.assertRaises(corpus_pcm.CorpusError):
                corpus_pcm.preflight(catalog,entries)
        self.assertEqual(len(corpus_pcm.preflight(catalog,
            [{'release':'release 1','path':'f'}])), 1)
        for bad in ('/tmp/private.flac', 'C:\\private\\track', 'bad\nlabel'):
            with self.subTest(track=bad), self.assertRaises(corpus_pcm.CorpusError):
                corpus_pcm.preflight(catalog, [{'release':'release 1',
                                               'path':'f', 'track':bad}])

    def test_clock_family_and_rate_are_verified_against_flac_metadata(self):
        item = dict(sample_rate_hz=96000, channels=2, bits_per_sample=24,
                    clock_family='48000-family', first_track_streaminfo_md5='0'*32)
        actual = dict(sample_rate_hz=96000, channels=2, bits_per_sample=24,
                      streaminfo_md5='0'*32, total_samples=100000)
        corpus_pcm.check_inventory(item, actual)
        bad = dict(item, clock_family='44100-family')
        with self.assertRaisesRegex(corpus_pcm.CorpusError, 'clock family'):
            corpus_pcm.check_inventory(bad, actual)
        bad = dict(item, sample_rate_hz=48001)
        with self.assertRaises(corpus_pcm.CorpusError):
            corpus_pcm.check_inventory(bad, actual)

    @unittest.skipUnless(shutil.which('flac') and
                         (ROOT/'test/sox_p10_candidate').is_file() and
                         (ROOT/'src/sox').is_file(), 'compiled smoke tools unavailable')
    def test_pcm_48000_family_and_high_native_rates(self):
        # Cross-family resampling and 176.4-kHz native-rate paths must both
        # preserve the exact excerpt timebase, even on a short smoke fixture.
        cases = ((96000, (2822400,)), (176400, (5644800, 11289600)))
        for rate, targets in cases:
            with self.subTest(source_rate=rate), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                wav = base/'synthetic.wav'
                with wave.open(str(wav),'wb') as writer:
                    writer.setnchannels(2); writer.setsampwidth(3); writer.setframerate(rate)
                    samples = bytearray()
                    for i in range(rate):
                        n = round(8388607*.24*math.sin(2*math.pi*997*i/rate))
                        samples.extend(n.to_bytes(3,'little',signed=True)*2)
                    writer.writeframes(bytes(samples))
                flac = base/'synthetic.flac'
                self.assertEqual(corpus_pcm.commands('flac','-s','-f',wav,'-o',flac).returncode,0)
                meta = corpus_pcm.read_streaminfo(flac)
                inventory = base/'inventory.json'
                source = base/'sources.json'
                inventory.write_text(json.dumps([dict(release=f'SYNTHETIC {rate}',
                    container='flac', bits_per_sample=24, channels=2, sample_rate_hz=rate,
                    clock_family='48000-family' if rate==96000 else '44100-family',
                    first_track_streaminfo_md5=meta['streaminfo_md5'], genre='test')]))
                source.write_text(json.dumps([dict(release=f'SYNTHETIC {rate}', path=str(flac))]))
                out = base/'out'
                args = ['--inventory',str(inventory),'--sources',str(source),
                        '--results',str(out),'--seconds','1','--offset','0']
                for target in targets:
                    args.extend(['--native-hz',str(target)])
                self.assertEqual(corpus_pcm.main(args),0)
                rows = json.loads((out/'pcm-corpus.json').read_text())['entries'][0]['targets']
                self.assertEqual(len(rows),len(targets))
                for target, expected in zip(rows, targets):
                    self.assertEqual(target['status'],'pass')
                    self.assertEqual(target['output_frames_per_channel'],expected)
                    self.assertTrue(target['window_count_exact'])
                    self.assertTrue(target['levels_within_tolerance'])

    @unittest.skipUnless(shutil.which('flac') and
                         (ROOT/'test/sox_p10_candidate').is_file() and
                         (ROOT/'src/sox').is_file(), 'compiled smoke tools unavailable')
    def test_overload_retry_can_still_fail_level_calibration(self):
        # A full-scale step is rejected at unity, then admitted only with
        # explicitly requested attenuation. It is not valid source material:
        # its reconstruction overshoots the permitted source peak tolerance,
        # and the collector must fail rather than certify its level.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            wav = base/'hot.wav'
            with wave.open(str(wav), 'wb') as writer:
                writer.setnchannels(2); writer.setsampwidth(3); writer.setframerate(88200)
                samples = bytearray()
                for i in range(88200):
                    # A full-scale polarity step causes interpolation overshoot
                    # even with the ordinary PCM 0.5 encoder reference.
                    n = -8388607 if i < 44100 else 8388607
                    samples.extend(n.to_bytes(3, 'little', signed=True)*2)
                writer.writeframes(bytes(samples))
            flac = base/'hot.flac'
            self.assertEqual(corpus_pcm.commands('flac', '-s', '-f', wav, '-o', flac).returncode, 0)
            meta = corpus_pcm.read_streaminfo(flac)
            inv = base/'inventory.json'
            src = base/'sources.json'
            inv.write_text(json.dumps([dict(release='SYNTHETIC hot waveform',
                container='flac', bits_per_sample=24, channels=2, sample_rate_hz=88200,
                clock_family='44100-family', first_track_streaminfo_md5=meta['streaminfo_md5'],
                genre='test')]))
            src.write_text(json.dumps([dict(release='SYNTHETIC hot waveform', path=str(flac))]))
            output = base/'results'
            rc = corpus_pcm.main(['--inventory', str(inv), '--sources', str(src),
                '--results', str(output), '--seconds', '1', '--offset', '0',
                '--native-hz', '2822400', '--gain-ladder=-6'])
            self.assertEqual(rc, 1)
            target = json.loads((output/'pcm-corpus.json').read_text())['entries'][0]['targets'][0]
            self.assertEqual(target['status'], 'out-of-spec')
            self.assertFalse(target['levels_within_tolerance'])
            self.assertGreater(target['peak_delta_db'], .5)
            self.assertTrue(target['rejected_at_unity'])
            self.assertEqual(len(target['attempts']), 2)
            self.assertFalse(target['attempts'][0]['admitted'])
            self.assertTrue(target['attempts'][0]['overload_rejected'])
            self.assertIn('lower bound from first overloaded sample',
                          target['attempts'][0]['diagnostic_tail'])
            self.assertEqual(target['explicit_gain_db'], -6.0)
            self.assertTrue(target['attempts'][1]['admitted'])
            ladder = json.loads((output/'pcm-ladder.json').read_text())
            self.assertEqual(len(ladder), 1)
            self.assertEqual(ladder[0]['admitting_gain_db'], -6.0)
            self.assertEqual(ladder[0]['ladder_attempts'][0]['gain_db'], 0.0)

    @unittest.skipUnless(shutil.which('flac') and
                         (ROOT/'test/sox_p10_candidate').is_file() and
                         (ROOT/'src/sox').is_file(), 'compiled smoke tools unavailable')
    def test_pcm_flow_resume_reference_and_adjudication_receipts(self):
        # No generated stimulus can satisfy the independent-recordings gate.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            wav = base/'source.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(2);f.setsampwidth(3);f.setframerate(88200)
                block = bytearray()
                for i in range(88200*2):
                    n = round(8388607 * .24 * math.sin(2*math.pi*997*i/88200))
                    block.extend(n.to_bytes(3,'little',signed=True)*2)
                f.writeframes(bytes(block))
            flac = base/'source.flac'
            cp = corpus_pcm.commands('flac','-s','-f',wav,'-o',flac)
            self.assertEqual(cp.returncode,0,cp.stderr)
            meta = corpus_pcm.read_streaminfo(flac)
            self.assertEqual(meta['bits_per_sample'],24)
            inv = base/'inventory.json'
            source = base/'sources.json'
            original = flac.read_bytes()
            inv.write_text(json.dumps([dict(release='SYNTHETIC: not a commercial source',
                container='flac', bits_per_sample=24, channels=2,
                sample_rate_hz=88200, clock_family='44100-family',
                first_track_streaminfo_md5=meta['streaminfo_md5'], genre='test')]))
            source.write_text(json.dumps([dict(
                release='SYNTHETIC: not a commercial source',path=str(flac))]))
            result = base/'out'
            args = ['--inventory',str(inv),'--sources',str(source),
                    '--results',str(result),'--seconds','1','--offset','1',
                    '--native-hz','2822400', '--chunk-blocks','1']
            self.assertEqual(corpus_pcm.main(args),0)
            data = json.loads((result/'pcm-corpus.json').read_text())
            self.assertEqual(data['coverage']['gate_status'],'INCOMPLETE')
            target = data['entries'][0]['targets'][0]
            self.assertEqual(target['status'],'pass')
            self.assertTrue(target['frames_exact'])
            self.assertTrue(target['window_count_exact'])
            self.assertTrue(target['dsd64_population_4_24'])
            self.assertEqual(target['output_frames_per_channel'],2822400)
            self.assertLessEqual(abs(target['rms_delta_db']),.25)
            self.assertLessEqual(abs(target['peak_delta_db']),.5)
            self.assertEqual(target['reconstructed_reference'],'sacd')
            self.assertEqual(flac.read_bytes(),original)
            self.assertEqual(len(json.loads((result/'pcm-unity.json').read_text())),1)
            self.assertEqual(len(json.loads((result/'pcm-sources.json').read_text())),1)
            self.assertEqual(json.loads((result/'pcm-ladder.json').read_text()),[])
            # Even properly formatted synthetic 1s receipts cannot qualify.
            adjudication = validate_domain(result, read(CRITERIA)['independent_corpus'], 'PCM_AUDIO')
            self.assertEqual(adjudication['status'],'FAIL')
            self.assertEqual(corpus_pcm.main(args+['--resume']),0)
            # A different source pathname with identical size and timestamp
            # must not reuse the original release's measured result.
            substitute = base/'different.flac'
            substitute.write_bytes(original)
            st = flac.stat()
            os.utime(substitute, ns=(st.st_atime_ns, st.st_mtime_ns))
            source.write_text(json.dumps([dict(
                release='SYNTHETIC: not a commercial source',path=str(substitute))]))
            with self.assertRaisesRegex(corpus_pcm.CorpusError,'configuration differs'):
                corpus_pcm.main(args+['--resume'])
            source.write_text(json.dumps([dict(
                release='SYNTHETIC: not a commercial source',path=str(flac))]))
            with self.assertRaisesRegex(corpus_pcm.CorpusError,'result already exists'):
                corpus_pcm.main(args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
