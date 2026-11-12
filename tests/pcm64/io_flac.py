#!/usr/bin/env python3
"""Phase 02B independent FLAC integer-to-binary64 qualification.

Decode fixtures through the ACTUAL libSoX FLAC handler. Independent integer
oracle never calls the same codec/bridge to derive expected sample values.
Tests are explicit NOT_RUN when built-in FLAC or native FP is unavailable.
"""
from __future__ import annotations
import argparse
import datetime as dt
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time

from flac_fixtures import SPECS, RATE, codes, name
from binary_receipts import executable_libraries


def insist(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def source_git_head(source: Path) -> str | None:
    try:
        result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, OSError):
        return None


class Runner:
    def __init__(self, sox: Path, probe: Path, results: Path):
        self.sox = sox.resolve()
        self.probe = probe.resolve()
        self.results = results.resolve()
        self.root = results/'fixtures'/'io-flac'
        self.root.mkdir(parents=True, exist_ok=True)
        self.fixture_dir = Path(__file__).with_name('fixtures')
        self.gates: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        self.commands: list[dict] = []
        self.executed: dict[str, str] = {}
        self.fixture_hashes: dict[str, str] = {}
        self.linkage = None
        self.native = None
        self.status = None
        self.performance: dict = {}

    def tick(self, name_: str, n: int = 1) -> None:
        self.counts[name_] = self.counts.get(name_, 0) + n

    def record_exe(self, p: Path) -> None:
        if str(p) not in self.executed:
            self.executed[str(p)] = digest(p)
            self.executed.update(executable_libraries(p))

    def invoke(self, args: list[str | Path], *, program: Path | None = None,
               expect: int | None = 0, label: str = '', data: bytes | None = None,
               env: dict | None = None) -> bytes:
        exe = program or self.probe
        self.record_exe(exe)
        argv = [str(exe)] + [str(x) for x in args]
        t = time.perf_counter()
        proc = subprocess.run(argv, input=data, capture_output=True,
                              env=env, timeout=60)
        row = {'label':label or str(args[0]), 'argv':argv, 'exit':proc.returncode,
               'bytes':len(proc.stdout),
               'stdout_sha256':hashlib.sha256(proc.stdout).hexdigest(),
               'stderr':proc.stderr.decode('utf-8','replace')[:1024],
               'wall_seconds':round(time.perf_counter()-t,6)}
        self.commands.append(row)
        if expect is not None:
            insist(proc.returncode == expect,
                   f'{label}: exit {proc.returncode} expected {expect}: {row["stderr"]}')
        else:
            insist(proc.returncode != 0, f'{label}: malformed input returned success')
        return proc.stdout

    def fixture(self, bits: int, channels: int, frames: int) -> Path:
        f = self.fixture_dir/name(bits, channels, frames)
        insist(f.is_file(), f'missing checked-in FLAC fixture: {f}')
        self.fixture_hashes[str(f.relative_to(Path(__file__).resolve().parents[2]))] = digest(f)
        return f

    def capability(self) -> None:
        insist(self.probe.is_file() and self.sox.is_file(), 'missing SoX or FLAC probe binary')
        raw = self.invoke(['capabilities'], label='actual-linkage').decode('ascii')
        parts = raw.splitlines()
        fields = [line.split('=',1) for line in parts]
        insist(len(fields)==2 and all(len(x)==2 for x in fields) and
               set(k for k,_ in fields)=={'linkage','native_dsp'},
               f'invalid codec linkage receipt: {raw}')
        data = dict(fields)
        self.linkage, self.native = data['linkage'], data['native_dsp']
        insist(self.linkage in ('builtin','plugin','absent') and
               self.native in ('OK','UNSUPPORTED','NUMERIC'), 'invalid native status')
        self.gates['actual_handler_linkage']='PASS'
        if self.linkage == 'builtin' and self.native == 'NUMERIC':
            self.gates['built_in_integer_flac']='FAIL: arithmetic environment rejected by required runtime guard'
            raise AssertionError('built-in FLAC native arithmetic environment guard rejected the runtime')
        if self.linkage != 'builtin' or self.native == 'UNSUPPORTED':
            reason = (f'actual linkage={self.linkage}, native arithmetic={self.native}')
            # A hostile runtime fenv on an otherwise supported built-in
            # build is a failed guard, not a skip. Disabled native builds
            # cannot run positive ingress tests by design.
            if self.native == 'NUMERIC' and self.linkage == 'builtin':
                self.gates['built_in_integer_flac'] = 'FAIL: runtime arithmetic guard refused'
                raise AssertionError('enabled built-in native arithmetic guard refused runtime')
            self.status = 'NOT_RUN: '+reason
            self.gates['built_in_integer_flac']='NOT_RUN: '+reason
            if self.linkage == 'plugin':
                # Plugin is an eligible legacy format, never a native adapter.
                fixture = self.fixture(*SPECS[-2])
                if sys.platform == 'linux':
                    raw_module = self.invoke(['module', fixture], label='plugin-dlopen-module')
                    data = raw_module.decode('utf-8').strip()
                    insist(data.startswith('module='), 'plugin did not report its loaded module')
                    plugin = Path(data.split('=',1)[1]).resolve()
                    insist(plugin.is_file() and 'fmt_flac.so' in plugin.name,
                           f'dlopen FLAC identity missing: {plugin}')
                    self.record_exe(plugin)
                    self.gates['plugin_loaded_binary_identity']='PASS'
                else:
                    self.gates['plugin_loaded_binary_identity']=(
                        'NOT_RUN: Linux /proc/self/maps module observation unavailable')
                check = self.invoke(['capability',fixture],expect=0,label='plugin-native-refusal')
                insist(check.strip() == b'status=UNSUPPORTED',
                       f'plugin incorrectly admitted to native FLAC: {check!r}')
                self.gates['plugin_native_rejection']='PASS'
            elif self.linkage == 'absent':
                self.gates['plugin_loaded_binary_identity']='NOT_RUN: no FLAC plugin'
                self.gates['plugin_native_rejection']='NOT_RUN: no FLAC plugin configured'
            else:
                self.gates['plugin_loaded_binary_identity']='NOT_RUN: built-in codec, not a plugin'
                self.gates['plugin_native_rejection']='NOT_RUN: built-in FLAC, no plugin'
        else:
            self.status = 'OK'
            self.gates['built_in_integer_flac']='PENDING: native fixture qualification'
            self.gates['plugin_loaded_binary_identity']='NOT_RUN: built-in codec, not a plugin'
            self.gates['plugin_native_rejection']='NOT_RUN: built-in FLAC, not a plugin build'

    def oracle(self, values: list[int], bits: int) -> bytes:
        scale = 1 << (bits-1)
        return b''.join(struct.pack('<d',float(Fraction(q,scale))) for q in values)

    def fixtures(self) -> None:
        if self.status != 'OK':
            for name_ in ('exact_integer_words','boundaries_and_channels',
                          'decoder_eof_and_short_output','stream_corruption_refusals',
                          'short_pipe_io','flac_ingest_performance'):
                self.gates[name_] = self.status
            if self.linkage != 'absent':
                for bits, channels, frames in SPECS:
                    f = self.fixture(bits, channels, frames)
                    expected = codes(bits, channels, frames)
                    raw = self.invoke(['legacy',f,257], label=f'legacy-fallback-{f.name}')
                    truth = b''.join(struct.pack('<i',q << (32-bits)) for q in expected)
                    insist(raw == truth, f'legacy codec regressed: {f.name}')
                    probe = self.invoke(['capability',f], label=f'capability-refused-{f.name}')
                    insist(probe.strip() == b'status=UNSUPPORTED',
                           f'native admission unexpectedly succeeded: {f.name}: {probe!r}')
                    self.tick('legacy_integer_samples',len(expected))
                    self.tick('ineligible_native_refusal_fixtures')
                self.gates['legacy_integer_transport']='PASS'
                self.gates['ineligible_native_refusal_all_fixtures']='PASS'
            else:
                self.gates['legacy_integer_transport']=self.status
                self.gates['ineligible_native_refusal_all_fixtures']=self.status
            return
        for bits, channels, frames in SPECS:
            f = self.fixture(bits, channels, frames)
            expected = codes(bits, channels, frames)
            want = self.oracle(expected, bits)
            cap = self.invoke(['query',f],label=f'metadata-{f.name}').decode('ascii').strip()
            insist(cap == f'rate={RATE} channels={channels} bits={bits} known=1 frames={frames}',
                   f'codec STREAMINFO mismatch: {f.name}: {cap}')
            self.tick('metadata_queries')
            for block in (1, 7, 31, 128, 257, 4096):
                got = self.invoke(['dump',f,block],label=f'exact-{f.name}-block-{block}')
                insist(got == want, f'FLAC binary64 samples differ from independent oracle: '
                                   f'{f.name}, block={block}, first_bad_byte=' +
                       str(next((i for i,(a,b) in enumerate(zip(got,want)) if a!=b),
                                min(len(got),len(want)))))
                self.tick('exact_double_samples',len(expected))
                self.tick('independent_decode_checks')
            actual_legacy = self.invoke(['legacy',f,257],label=f'legacy-{f.name}')
            expected_legacy = b''.join(struct.pack('<i',q*(1 << (32-bits)))
                                       for q in expected)
            insist(actual_legacy == expected_legacy,
                   f'legacy FLAC integer transport changed: {f.name}')
            self.tick('legacy_integer_samples',len(expected))
            self.invoke(['zero',f],label=f'zero-capacity-{f.name}')
            self.tick('zero_capacity_backpressure')
            if frames >= 3:
                self.invoke(['mixed',f],label=f'mixed-native-legacy-{f.name}')
                self.tick('shared_decoder_seek_checks')
        self.gates['exact_integer_words']='PASS'
        self.gates['boundaries_and_channels']='PASS'
        self.gates['decoder_eof_and_short_output']='PASS'
        self.gates['legacy_integer_transport']='PASS'
        # Run an actual compiled C mutant through the same binary probe,
        # compare its output bits to an independent Fraction oracle, and
        # reject it only when its arithmetic demonstrably differs.
        for q in (1,-1,(1<<31)-1,-(1<<31)):
            mutated_word = int(self.invoke(['mutant-int32max',q],
                        label=f'compiled-int32max-mutant-{q}').decode('ascii').strip(),16)
            truth = struct.unpack('<Q',struct.pack('<d', float(Fraction(q,1<<31))))[0]
            insist(mutated_word!=truth,
                   f'executed INT32_MAX mutant escaped detection at {q}')
            self.tick('int32max_mutant_negative_controls')
        self.corruption()
        self.pipe_io()
        self.benchmark()
        # Completion, not just capability, authorizes PASS.
        self.gates['built_in_integer_flac']='PASS'

    def corruption(self) -> None:
        original = self.fixture(32,2,5193).read_bytes()
        cases = {'bad-magic':b'xxxx'+original[4:],
                 'short-metadata':original[:9],
                 'short-audio':original[:len(original)//2],
                 'partial-audio':original[:-101]}
        # Audio payload begins after the sequence of FLAC metadata blocks.
        offset=4
        while offset+4<=len(original):
            flags=original[offset]
            size=int.from_bytes(original[offset+1:offset+4],'big')
            offset+=4+size
            if flags & 0x80:
                break
        insist(0 < offset < len(original)-32,'could not locate FLAC audio frame')
        bad=bytearray(original)
        bad[offset+8] ^= 0x40
        cases['bad-audio-frame']=bytes(bad)
        for title,blob in cases.items():
            f=self.root/(title+'.flac')
            f.write_bytes(blob)
            self.fixture_hashes[str(f)] = digest(f)
            self.invoke(['dump',f,31],expect=None,label='corrupt-'+title)
            self.tick('corrupt_or_truncated_refusals')
        self.gates['stream_corruption_refusals']='PASS'

    def pipe_io(self) -> None:
        if os.name != 'posix':
            self.gates['short_pipe_io']='NOT_RUN: POSIX anonymous pipe required'
            return
        f = self.fixture(24,2,4973)
        expected = self.oracle(codes(24,2,4973),24)
        self.record_exe(self.probe)
        # Redirect output to a file so a full codec response never deadlocks
        # the pipe while input is deliberately delivered in short writes.
        output = self.root/'pipe-f64.bin'
        args = [str(self.probe),'dump','-','7']
        t = time.perf_counter()
        with output.open('wb') as fout:
            proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=fout,
                                  stderr=subprocess.PIPE)
            assert proc.stdin is not None
            payload=f.read_bytes()
            try:
                for i in range(0,len(payload),97):
                    proc.stdin.write(payload[i:i+97])
                    proc.stdin.flush()
                proc.stdin.close()
                proc.stdin=None
                _,err=proc.communicate(timeout=30)
            except Exception:
                proc.kill()
                proc.communicate()
                raise
        self.commands.append({'label':'short-97-byte-input-pipe','argv':args,
                              'exit':proc.returncode,
                              'wall_seconds':round(time.perf_counter()-t,6),
                              'stdout_sha256':digest(output),
                              'stderr':err.decode('utf-8','replace')[:1024]})
        insist(proc.returncode==0, f'FLAC input pipe failed: {err!r}')
        insist(output.read_bytes()==expected,'short input pipe lost PCM words')
        self.tick('short_pipe_input_words',len(expected)//8)
        self.gates['short_pipe_io']='PASS'

    def benchmark(self) -> None:
        cases = [((32,2,5193),'short'),((32,1,8193),'long')]
        results = {}
        for spec, label in cases:
            f=self.fixture(*spec)
            for mode in ('legacy','dump'):
                durations=[]
                for i in range(5):
                    begin=time.perf_counter()
                    self.invoke([mode,f,128],label=f'benchmark-{label}-{mode}-{i}')
                    durations.append(time.perf_counter()-begin)
                durations.sort()
                results[label+'_'+mode+'_median_seconds']=round(durations[2],6)
        results['native_adapter_cached_heap_bytes_upper_bound']=4096*8*4
        results['native_adapter_allocation_note']=(
            'one reader-owned buffer, grows on demand up to 128KiB; no per-sample '
            'allocation. Decoder allocations are not counted by this microprobe; '
            'see independent allocation/RSS measurements in phase02b/performance')
        results['wall_clock_includes_subprocess_startup']=True
        self.performance=results
        self.gates['flac_ingest_performance']='PASS'

    def execute(self) -> dict:
        self.capability()
        self.fixtures()
        if self.status != 'OK' and self.linkage == 'plugin':
            insist(self.gates.get('legacy_integer_transport') == 'PASS' and
                   self.counts.get('ineligible_native_refusal_fixtures')==len(SPECS),
                   'plugin fallback did not complete all fixture checks')
            self.gates['legacy_plugin_transport']='PASS'
        elif self.linkage == 'absent':
            self.gates['legacy_plugin_transport']='NOT_RUN: codec unavailable'
        else:
            self.gates['legacy_plugin_transport']='NOT_RUN: plugin path not selected'
        source = Path(__file__).resolve().parents[2]
        return {
            'suite':'io-flac',
            'status':'PASS_WITH_NOT_RUN' if any(v.startswith('NOT_RUN') for v in
                                          self.gates.values()) else 'PASS',
            'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'git_commit':source_git_head(source),
            'linkage':self.linkage, 'native_dsp':self.native,
            'checks':self.counts, 'gate_execution':self.gates,
            'performance':self.performance,
            'commands':self.commands,
            'fixture_sha256':self.fixture_hashes,
            'executed_binary_sha256':self.executed,
            'source_and_binary_sha256':{
                str(p.relative_to(source)):digest(p) for p in
                [source/'src/flac.c',source/'src/pcm_f64_io.c',
                 source/'src/pcm_f64_io.h',source/'tests/pcm64/io_flac.py',
                 source/'tests/pcm64/flac_fixtures.py',
                 source/'tests/pcm64/flac_io_probe.c',
                 source/'tests/pcm64/binary_receipts.py']},
            'platform':sys.platform,
            'oracle':'original signed raw integer code / 2^(bit_depth-1), Fraction to IEEE binary64',
        }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    args.results.mkdir(parents=True,exist_ok=True)
    receipt=args.results.resolve()/'io-flac.json'
    receipt.unlink(missing_ok=True)
    runner=Runner(args.sox,args.probe,args.results)
    try:
        result=runner.execute()
    except Exception as exc:
        result={
            'suite':'io-flac','status':'FAIL',
            'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'error':f'{type(exc).__name__}: {exc}',
            'completed_checks':runner.counts,
            'gate_execution':runner.gates,
            'commands':runner.commands,
            'executed_binary_sha256':runner.executed,
            'source_and_binary_sha256':{
                'src/sox':runner.executed.get(str(runner.sox)),
                'test/pcm64_flac_probe':runner.executed.get(str(runner.probe))},
        }
        receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print('FAIL io-flac:',result['error'],file=sys.stderr)
        return 1
    receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(result['status'],'io-flac:',result['checks'])
    return 0


if __name__=='__main__':
    sys.exit(main())
