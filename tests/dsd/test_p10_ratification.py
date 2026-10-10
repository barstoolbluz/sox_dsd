#!/usr/bin/env python3
"""Adversarial, source-free tests of P10 gate ratification (no new DSP claim)."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from ratify_p10_gates import HARDWARE, CORPUS, check_hardware, check_corpus, digest
from qualify_p10_ratification import assess


def mutate_json(path, change):
    obj=json.loads(path.read_text())
    change(obj)
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')


def trial(source, edit, checker, expected):
    with tempfile.TemporaryDirectory(prefix='p10-review-test-') as temp:
        base=Path(temp)/'evidence'
        shutil.copytree(source,base)
        edit(base)
        observed=checker(base)
        assert observed['status']==expected, (observed,expected)


def pcm_schema_example(base):
    """Synthetic *receipt schema* test, not independent PCM qualification."""
    dsd=json.loads((base/'corpus-unity.json').read_text())
    chosen=[]
    for native in (2822400,5644800,11289600):
        chosen.extend([r for r in dsd if r['native_hz']==native and r['admitted']][:2])
    sources=[];renders=[]
    for index,row in enumerate(chosen):
        r=copy.deepcopy(row)
        source=f'validator-only-source-{index:02d}.wav'
        rate=44100 if index%2==0 else 48000
        hash_value=hashlib.sha256(source.encode('ascii')).hexdigest()
        release=f'synthetic validator-only-{index}'
        s=dict(source=source, native_hz=row['native_hz'],
               excerpt_sha256=hash_value, excerpt_seconds=120,
               source_domain='PCM_AUDIO',source_rate_hz=rate,
               genre='validator-genre-'+str(index%3),
               release=release,origin='SYNTHETIC: NOT MASTERING EVIDENCE',
               original_bytes=10000000)
        r.update(source=source,excerpt_sha256=hash_value,release=release,
                 genre=s['genre'],source_rate_hz=rate,reconstruction_reference='sacd',
                 explicit_gain_db=0)
        sources.append(s);renders.append(r)
    (base/'pcm-sources.json').write_text(json.dumps(sources)+'\n')
    (base/'pcm-unity.json').write_text(json.dumps(renders)+'\n')


def main():
    original=assess()
    assert original['status']=='INCOMPLETE' and not original['qualified']
    assert original['promotion']=='BLOCKED'
    assert original['gates']['representative_hardware_1hour_per_profile_isa']['status']=='PASS'
    assert original['gates']['independent_realworld_corpus']['status']=='PARTIAL'
    assert original['remaining_release_gates']==['independent_realworld_corpus']
    assert assess()==original, 'assessing fixed receipts should be idempotent'
    cases=['immutable original receipts -> hardware PASS, corpus PARTIAL, unpromoted']
    def test(name,src,mutation,validator,status='FAIL'):
        trial(src,mutation,validator,status);cases.append(name)
    test('missing hardware report fails closed',HARDWARE,
        lambda b:(b/'soak-2822400-result.json').unlink(),check_hardware)
    test('altered hardware summary cannot conceal bad result',HARDWARE,
        lambda b:mutate_json(b/'soak-2822400-result.json',
            lambda x:x.update(committed_native_frames=x['committed_native_frames']-1)),check_hardware)
    test('one damaged continuation state fails despite SHA receipt',HARDWARE,
        lambda b:(b/'soak-11289600-0030.state').write_text('corrupt'),check_hardware)
    test('missing intermediate snapshot fails',HARDWARE,
        lambda b:(b/'soak-5644800-0049.state').unlink(),check_hardware)
    test('fabricated qualifying status conflicts with immutable receipt',HARDWARE,
        lambda b:mutate_json(b/'soak.json',
            lambda x:x['profiles'][0]['admission_checks'].update(release_sequence=True)),check_hardware)
    test('wrong generator hash fails',HARDWARE,
        lambda b:mutate_json(b/'soak-2822400-execution.json',
            lambda x:x.update(source_generator_sha256='0'*64)),check_hardware)
    test('changed frozen state maxima fail even with stale PASS',HARDWARE,
        lambda b:mutate_json(b/'soak-2822400-result.json',
            lambda x:x['max_abs_state'].__setitem__(7,1e99)),check_hardware)
    test('missing DSD source cannot pass independent corpus',CORPUS,
        lambda b:mutate_json(b/'sources.json',lambda x:x.pop()),check_corpus)
    test('changed DSD excerpt hash cannot be silently accepted',CORPUS,
        lambda b:mutate_json(b/'sources.json',lambda x:x[0].update(excerpt_sha256='0'*64)),check_corpus)
    test('missing native windows fails',CORPUS,
        lambda b:mutate_json(b/'corpus-unity.json',
            lambda x:next(r for r in x if r['admitted'])['per_channel'][0].update(windows=1)),check_corpus)
    test('false DSD64 window population fails',CORPUS,
        lambda b:mutate_json(b/'corpus-unity.json',
            lambda x:next(r for r in x if r['admitted'])['per_channel'][0].update(min_ones=2)),check_corpus)
    test('unexpected unity failure cannot be relabeled overload',CORPUS,
        lambda b:mutate_json(b/'corpus-unity.json',
            lambda x:next(r for r in x if not r['admitted']).update(encode_stderr_tail='disk full')),check_corpus)
    test('rejected original with no explicit gain retry is insufficient',CORPUS,
        lambda b:(b/'corpus-ladder.json').unlink(),check_corpus)
    test('extra 6 dB lost during remodulation fails level check',CORPUS,
        lambda b:mutate_json(b/'corpus-unity.json',
            lambda x:next(r for r in x if r['admitted']).update(rms_delta_db=-6.02)),check_corpus)
    test('source reader not checked against oracle fails',CORPUS,
        lambda b:mutate_json(b/'reader-self-check.json',
            lambda x:x.update(bit_identical_to_oracle=False)),check_corpus)
    with tempfile.TemporaryDirectory(prefix='p10-pcm-schema-') as temp:
        b=Path(temp)/'evidence';shutil.copytree(CORPUS,b)
        pcm_schema_example(b)
        assert check_corpus(b)['status']=='PASS', 'two real-source input domains should satisfy the structural gate'
        cases.append('complete PCM/DSD receipt schema passes structural checker (synthetic schema test only)')
        mutate_json(b/'pcm-unity.json',
            lambda x:x[0].update(rms_delta_db=-6.02))
        assert check_corpus(b)['status']=='FAIL'
        cases.append('ordinary PCM half-gain misclassification fails calibration check')
    print(json.dumps(dict(status='PASS',cases=len(cases),tests=cases,
        scope='adversarial receipt verification; not a new hardware or commercial-source run'),sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
