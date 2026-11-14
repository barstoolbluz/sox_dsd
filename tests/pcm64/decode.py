#!/usr/bin/env python3
"""Phase 05B end-to-end native DSD decoder qualification.

An independently compiled caller drives the frozen *public* decoder API using
independently constructed DSF/DFF/WSD native bits; this harness parses the
actual WAV structure and checks every IEEE754 binary64 *word*, not a tolerance
or a printed decimal sample. The oracle never uses CLI planner/PCM bridge.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any

from binary_receipts import executable_libraries, safe_git_head

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/dsd/reference"))
import fixtures  # independent hand-built chronology and container serializer


def sha(path: Path) -> str:
    with path.open("rb") as fp:
        h = hashlib.sha256()
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def demand(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def call(cmd: list[str], env: dict[str, str] | None = None,
         timeout: int = 45, stdout=None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, env=merged, stdout=stdout or subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, check=False)


def checked_rate(frames: int, native_rate: int, pcm_rate: int) -> int:
    # Fractions checked by independent integer arithmetic, no float rounding.
    return (2 * frames * pcm_rate + native_rate) // (2 * native_rate)


def parse_wav(path: Path, expected_frames: int, channels: int,
              rate: int) -> tuple[bytes, int]:
    raw = path.read_bytes()
    demand(raw[:4] in (b"RIFF", b"RIFX", b"RF64") and raw[8:12] == b"WAVE",
           f"{path}: missing RIFF/WAVE header")
    order = "<" if raw[:4] != b"RIFX" else ">"
    pos, found_fmt, payload, mask = 12, False, None, 0
    while pos + 8 <= len(raw):
        name = raw[pos:pos+4]
        length, = struct.unpack_from(order+"I", raw, pos+4)
        pos += 8
        demand(length <= len(raw) - pos, f"{path}: truncated {name!r} chunk")
        data = raw[pos:pos+length]
        if name == b"fmt ":
            demand(length >= 16, "truncated fmt")
            tag, nch, hz, byte_rate, align, bits = struct.unpack_from(order+"HHIIHH", data)
            demand(tag in (3, 0xfffe) and nch == channels and hz == rate and bits == 64 and
                   align == channels * 8 and byte_rate == channels * 8 * rate,
                   f"{path}: wrong format/rate/channel/float64 header: {tag,nch,hz,bits}")
            if tag == 0xfffe:
                demand(length >= 40 and data[24:28] == b"\x03\x00\x00\x00",
                       "WAV extensible GUID does not designate IEEE float")
                mask, = struct.unpack_from(order+"I", data, 20)
            found_fmt = True
        if name == b"data":
            payload = data
            break
        pos += length + (length & 1)
    demand(found_fmt and payload is not None, f"{path}: missing fmt/data")
    demand(len(payload) == expected_frames * channels * 8,
           f"{path}: binary64 data size {len(payload)} != {expected_frames*channels*8}")
    if order == ">":
        payload = b"".join(payload[i:i+8][::-1] for i in range(0, len(payload), 8))
    return payload, mask


def write_source(path: Path, n: int, ch: int, rate: int,
                 kind: str, pattern: str) -> None:
    bits = fixtures.bits(n, ch, pattern)
    fn = {"dsf": fixtures.make_dsf, "dff": fixtures.make_dff,
          "wsd": fixtures.make_wsd}[kind]
    path.write_bytes(fn(bits, rate))


def decode_case(sox: Path, oracle: Path, folder: Path, ident: str,
                source: Path, rate: int, profile: str, level: str,
                kernel: str = "auto", report: bool = True,
                other_options: tuple[str, ...] = (),
                speaker_mask: int | None = None,
                output_order: tuple[int, ...] = (),
                packed: bool = False) -> dict[str, Any]:
    wav = folder / f"{ident}.wav"
    raw = folder / f"{ident}.oracle.f64"
    report_path = folder / f"{ident}.report.json"
    native_rate = {"64": fixtures.DSD64, "128": 2*fixtures.DSD64}
    native = next((hz for hz in native_rate.values()
                   if str(hz) in source.name), None)
    # Source-rate identity comes from the hand-built test vector, not filename.
    blob = source.read_bytes()
    if blob[:4] == b"DSD ":
        native = struct.unpack_from("<I", blob, 56)[0]
    elif blob[:4] == b"FRM8":
        offset = blob.index(b"FS  ")+12
        native = struct.unpack_from(">I", blob, offset)[0]
    elif blob[:4] == b"1bit":
        native = struct.unpack_from(">I", blob, 36)[0]
    demand(native in (fixtures.DSD64, 2*fixtures.DSD64),
           f"invalid independent native-rate extraction: {native}")
    profile_arg = {
        "mastering-v1": f"decode.mastering.v1.dsd{native // fixtures.DSD64 * 64}", "wideband": "wideband",
        "mastering-v2": f"decode.mastering.v2.dsd{native // fixtures.DSD64 * 64}",
    }[profile]
    env = {"SOX_DSD_KERNEL_FIR": kernel, "SOX_DSD_PACKED_INPUT": "1" if packed else "0"}
    argv = [str(sox), "--precision", "64", "--decode", profile_arg,
            "--dsd-level", level, "--dsd-bandwidth", "adapt"]
    if report:
        argv += ["--report", str(report_path)]
    argv += [*other_options, str(source), "-b", "64", "-e", "floating-point",
             "-r", str(rate), str(wav)]
    cp = call(argv, env, timeout=90)
    demand(cp.returncode == 0,
           f"{ident}: CLI rc={cp.returncode}: {cp.stderr.decode(errors='replace')[:600]}")
    api = call([str(oracle), str(source), str(raw), str(rate), profile,
                level, "adapt", kernel], env, timeout=90)
    demand(api.returncode == 0 and b"finish=done" in api.stdout,
           f"{ident}: independent public decoder rc={api.returncode}: {api.stderr[:400]!r}")
    receipt = dict(field.split("=", 1) for field in api.stdout.decode().strip().split())
    actual, mask = parse_wav(wav, int(receipt["pcm"]), int(receipt["channels"]), rate)
    expected = raw.read_bytes()
    if output_order:
        demand(sorted(output_order) == list(range(int(receipt["channels"]))),
               f"{ident}: invalid independent speaker order")
        # Compute the speaker permutation from the independent decoder words,
        # without asking either production planner or WAV writer for a map.
        words = [expected[i:i+8] for i in range(0, len(expected), 8)]
        expected = b"".join(words[f*len(output_order)+ch]
                            for f in range(len(words)//len(output_order))
                            for ch in output_order)
    if speaker_mask is not None:
        demand(mask == speaker_mask,
               f"{ident}: WAV speaker identity {mask:#x} != {speaker_mask:#x}")
    demand(actual == expected,
           f"{ident}: API oracle binary64 mismatch first byte " +
           str(next((i for i, (a, b) in enumerate(zip(actual,expected)) if a!=b),
                    min(len(actual), len(expected)))))
    decoded_count = checked_rate(int(receipt["native"]), native, rate)
    demand(int(receipt["pcm"]) == decoded_count,
           f"{ident}: oracle output count fails independent rational count")
    actual_report = None
    if report:
        actual_report = json.loads(report_path.read_text())
        demand(actual_report["status"] == "complete" and
               actual_report["precision"]["actual_route"] == "native-binary64-pcm" and
               actual_report["precision"]["binary64_pcm_processing"] is True and
               actual_report["output"]["frames_written"] == receipt["pcm"],
               f"{ident}: false plan or report output receipt")
        dec = actual_report["processing"]["decoder"]
        demand(len(dec) == 1 and dec[0]["source_native_hz"] == native and
               dec[0]["output_pcm_hz"] == rate and
               dec[0]["frames_consumed"] == receipt["native"] and
               dec[0]["frames_produced"] == receipt["pcm"],
               f"{ident}: actual decoder counter, kernel or rate missing")
        expected_id = {"mastering-v1": "decode.mastering.v1",
                       "mastering-v2": "decode.mastering.v2",
                       "wideband": "decode.wideband.v1"}[profile]
        demand(dec[0]["profile_id"].startswith(expected_id) and
               dec[0]["fir_kernel_actual"] == ("scalar" if kernel=="scalar" else
                 "sse2" if kernel=="sse2" else dec[0]["fir_kernel_actual"]),
               f"{ident}: actual requested backend/profile selection mismatch")
        demand(actual_report["precision"]["input_normalization"][0]["source_decode_exact"] is False,
               f"{ident}: reports must not claim reconstruction is an exact source code")
        if kernel == "auto":
            demand(dec[0]["fir_kernel_actual"] in
                   ("scalar", "sse2", "avx1", "avx2", "avx512"),
                   f"{ident}: decoder failed to identify a compiled FIR kernel")
    return {"case": ident, "source_sha256": sha(source), "api_sha256": sha(raw),
            "wav_sha256": sha(wav), "pcm_frames": receipt["pcm"],
            "native_frames": receipt["native"], "intermediate_frames": receipt["intermediate"],
            "kernel": actual_report["processing"]["decoder"][0]["fir_kernel_actual"] if report else kernel,
            "channels": int(receipt["channels"]), "profile": profile,
            "level": level, "wav_mask": hex(mask), "words_identical": True,
            "packed_native_input": packed, "speaker_permutation": output_order}


def negative_tests(sox: Path, folder: Path, source: Path) -> dict[str, Any]:
    results = {}
    for label, args, expected in [
        ("invalid_rate", [str(source), "-r", "abc", str(folder/"n-rate.wav")], "rate"),
        ("invalid_channels", [str(source), "-c", "abc", str(folder/"n-chan.wav")], "channels"),
        ("missing_comment", ["--comment-file", str(folder/"nonexistent"),
                              str(source), str(folder/"n-comment.wav")], "comment file"),
    ]:
        report = folder / f"{label}.json"
        # Invalid file options must be captured even before --report is parsed.
        cmd = [str(sox), "--precision", "64", "--report", str(report), *args]
        cp = call(cmd)
        demand(cp.returncode != 0 and report.exists(),
               f"{label}: CLI error missing JSON report")
        j = json.loads(report.read_text())
        demand(j["status"] in ("failed", "refused") and
               j["executable"] is False and expected in j["failure_reason"],
               f"{label}: report does not describe actual option fault: {j['failure_reason']!r}")
        results[label] = j["failure_reason"]
    # Also exercise reports found *after* the invalid argument: argv prescan.
    later = folder / "report_after_bad_arg.json"
    cp = call([str(sox), "--precision", "64", str(source), "-r", "abc",
               "--report", str(later), str(folder / "never.wav")])
    demand(cp.returncode != 0 and later.exists() and
           "rate" in json.loads(later.read_text())["failure_reason"],
           "early option error before --report was not captured")
    results["report_after_bad_arg"] = "PASS"

    for ext in ("dsf", "dff", "wsd"):
        original = folder / f"negative-{ext}.{ext}"
        write_source(original, 512, 2, fixtures.DSD64, ext, "distinct")
        truncated = folder / f"truncated-{ext}.{ext}"
        truncated.write_bytes(original.read_bytes()[:-19])
        report = folder / f"truncated-{ext}.json"
        cp = call([str(sox), "--precision", "64", "--report", str(report),
                   str(truncated), "-b", "64", "-e", "floating-point",
                   str(folder / f"bad-{ext}.wav")])
        demand(cp.returncode != 0 and report.exists() and
               json.loads(report.read_text())["status"] != "complete",
               f"{ext}: truncated source accepted or no failure report")
        results[f"truncated_{ext}"] = cp.returncode

    # A positional output aliases the source and must never clobber it.
    before = sha(source)
    cp = call([str(sox), "--precision", "64", str(source), "-t", "wav",
               str(source)])
    demand(cp.returncode != 0 and sha(source) == before,
           "native DSD alias overwrote the input")
    link = folder / "input-alias.wav"
    link.symlink_to(source)
    cp = call([str(sox), "--precision", "64", str(source), "-b", "64",
               "-e", "floating-point", str(link)])
    demand(cp.returncode != 0 and sha(source) == before,
           "symlink output alias overwrote the input")
    results["source_identity_protection"] = "PASS"

    existing = folder / "existing.wav"
    existing.write_bytes(b"SENTINEL\n")
    cmd = [str(sox), "--precision", "64", "--no-clobber", str(source),
           "-b", "64", "-e", "floating-point", str(existing)]
    plan = call([cmd[0], "--plan", *cmd[1:]])
    demand(plan.returncode == 0 and
           json.loads(plan.stdout)["precision"]["actual_route"] == "refused-before-output",
           "--no-clobber preflight plan falsely accepts existing file")
    refuse_report = folder / "no_clobber.json"
    cp = call([str(sox), "--precision", "64", "--report", str(refuse_report),
               "--no-clobber", str(source), "-b", "64", "-e", "floating-point", str(existing)])
    j = json.loads(refuse_report.read_text())
    demand(cp.returncode != 0 and existing.read_bytes() == b"SENTINEL\n" and
           j["status"] == "refused" and not j["executable"] and
           "--no-clobber" in j["failure_reason"],
           "no-clobber plan vs execution vs report mismatch")
    results["no_clobber"] = "PASS"

    # Eligible known-length audio sent to a real stdout character device.
    with open(os.devnull, "wb") as null:
        cmd = [str(sox), "--precision", "64", str(source), "-b", "64",
               "-e", "floating-point", "-r", "96000", "-t", "wav", "-"]
        cp = call(cmd, stdout=null)
        demand(cp.returncode == 0, f"stdout character descriptor incorrectly refused {cp.stderr!r}")
        plan = call([cmd[0], "--plan", *cmd[1:]])
        demand(json.loads(plan.stdout)["precision"]["runner_available"] is True,
               "stdout plan lacks native binary64 runner")
    results["stdout_device"] = "PASS"

    # A parse error may predate complete audio-name classification. The
    # best-effort early reporter must not overwrite source bytes when the
    # nominated report is also an unparsed source, even via an inode alias.
    original = source.read_bytes()
    alias = folder / "early-report-source-hardlink"
    os.link(source, alias)
    for ident, report_target in (("direct", source), ("inode", alias)):
        cp = call([str(sox), "--precision", "64", "--report",
                   str(report_target), "-r", "abc", str(source),
                   str(folder / f"early-alias-{ident}.wav")])
        demand(cp.returncode != 0 and source.read_bytes() == original,
               f"early report clobbered unparsed input: {ident}")
    results["preparse_source_alias_safe"] = "PASS"

    # Report FIFO: retained nonblocking writer from preflight through publish.
    fifo = folder / "receipt.fifo"
    fifo_result = folder / "receipt_fifo_bytes.json"
    os.mkfifo(fifo)
    with fifo_result.open("wb") as output:
        reader = subprocess.Popen(["cat", str(fifo)], stdout=output)
        try:
            time.sleep(0.1)
            cp = call([str(sox), "--precision", "64", "--report", str(fifo),
                       str(source), "-b", "64", "-e", "floating-point",
                       "-r", "96000", str(folder / "fifo.wav")], timeout=25)
            reader.wait(timeout=5)
        finally:
            if reader.poll() is None:
                reader.kill()
                reader.wait(timeout=5)
    demand(cp.returncode == 0 and json.loads(fifo_result.read_text())["status"] == "complete",
           "FIFO report endpoint hung, discarded receipt or misreported run")
    results["fifo_report"] = "PASS"
    return results


def run_suite(sox: Path, oracle: Path, work: Path) -> dict[str, Any]:
    demand(sox.is_file() and oracle.is_file(), "built binaries not found")
    source_files = [ROOT / "src/dsd_f64_decode.c", ROOT / "src/dsd_plan.c",
                    ROOT / "src/sox_ng.c", ROOT / "src/dsd_public.c",
                    ROOT / "tests/pcm64/decode/api_oracle.c"]
    identity = {str(f.relative_to(ROOT)): sha(f) for f in source_files}
    binaries = {str(sox): sha(sox), str(oracle): sha(oracle)}
    binaries.update(executable_libraries(sox))
    binaries.update(executable_libraries(oracle))
    cases = []
    # Fully crossed native-rate, profile, PCM-rate and level coverage, with
    # 1/7/256/511/4096 source/output partitions in the independent probe.
    for hz in (fixtures.DSD64, 2*fixtures.DSD64):
        for profile in ("mastering-v1", "mastering-v2", "wideband"):
            for rate in (88200, 96000, 176400, 192000):
                for level in ("preserve", "sacd"):
                    idx = f"matrix-dsf{hz}-p{profile}-r{rate}-l{level}"
                    src = work / f"{idx}.dsf"
                    write_source(src, 511, 2, hz, "dsf", "random")
                    cases.append(decode_case(sox, oracle, work, idx, src, rate, profile, level))
    # Explicitly cross a truly empty input, a one-bit input, partial-byte
    # tails, block boundaries, longer continuous material and isolated roles.
    extents = [(0, 1, "dsf", "zeros"), (1, 1, "dsf", "ones"),
               (7, 2, "dsf", "distinct"), (9, 1, "dsf", "69"),
               (256, 3, "dsf", "random"), (4096, 2, "dsf", "distinct"),
               (32769, 2, "dsf", "random"), (100000, 2, "dsf", "zeros"),
               (32769, 2, "dff", "distinct"), (4096, 6, "dff", "random"),
               (16, 1, "wsd", "ones"), (4096, 2, "wsd", "random")]
    for j, (n, channels, kind, pattern) in enumerate(extents):
        hz = fixtures.DSD64 if j % 2 else 2*fixtures.DSD64
        idx = f"extent-{j}-{kind}-n{n}-c{channels}"
        src = work / f"{idx}.{kind}"
        write_source(src, n, channels, hz, kind, pattern)
        # DFF 6-channel default IDs are not necessarily WAV speaker roles.
        # Explicitly assign a representable, canonical WAV speaker order.
        roles = (("--dsd-layout", "FL,FR,FC,LFE,BL,BR") if channels == 6 else
                 ("--dsd-layout", "FC" if channels == 1 else "FL,FR") if kind == "wsd" else ())
        cases.append(decode_case(sox, oracle, work, idx, src, 96000,
                                 "mastering-v2", "sacd", other_options=roles,
                                 speaker_mask=0x3f if channels == 6 else None))
    # Exercise the original channel order and canonical WAV speaker-order
    # permutation separately: a six-channel DFF with named surround channels.
    src = work / "role-permutation-dff-6.dff"
    write_source(src, 8193, 6, fixtures.DSD64, "dff", "distinct")
    cases.append(decode_case(sox, oracle, work, "role-permutation-dff6", src,
                             96000, "mastering-v2", "preserve",
                             other_options=("--dsd-layout", "FC,FL,FR,LFE,SL,SR"),
                             speaker_mask=0x60f,output_order=(1,2,0,3,4,5)))
    # Selected scalar, auto and SSE2 paths, chosen by the same P11 dispatcher.
    src = work / "kernel-identical-source.dsf"
    write_source(src, 8193, 2, fixtures.DSD64, "dsf", "random")
    for kernel in ("scalar", "auto", "sse2"):
        idx = "kernel-" + kernel
        try:
            cases.append(decode_case(sox, oracle, work, idx, src, 96000,
                                     "mastering-v2", "preserve", kernel=kernel))
        except AssertionError:
            if kernel != "sse2":
                raise
            # On a non-x86 or unavailable backend, record explicitly as UNRUN.
            # A mismatched sample-word result on a *supported* backend must
            # not be swallowed: only classify a refused backend as UNRUN.
            sox_test = call([str(sox), "--precision", "64", "--plan", str(src),
                             "-r", "96000", str(work/"kernel-sse2-plan.wav")],
                            {"SOX_DSD_KERNEL_FIR": "sse2"})
            text = sox_test.stdout.decode(errors="replace")
            if (sox_test.returncode == 0 and
                    '"runner_available":true' in text):
                raise
    source = work / "negative-main-2822400.dsf"
    write_source(source, 32768, 2, fixtures.DSD64, "dsf", "random")
    negatives = negative_tests(sox, work, source)
    # A positive test run without a report must produce the very same words.
    with_report = decode_case(sox, oracle, work, "report-on", source,
                              96000, "mastering-v2", "preserve")
    without_report = decode_case(sox, oracle, work, "report-off", source,
                                 96000, "mastering-v2", "preserve", report=False)
    demand(with_report["api_sha256"] == without_report["api_sha256"] and
           with_report["wav_sha256"] == without_report["wav_sha256"],
           "enabling report changed actual DSD audio")
    negatives["report_on_off_equal"] = "PASS"
    # An optional packed DSF reader route must return the *same* full WAV
    # binary64 words as expanded reading, and still match the API oracle.
    packed = decode_case(sox, oracle, work, "packed-no-report", source,
                         96000, "mastering-v2", "preserve", report=False,
                         packed=True)
    cases.append(packed)
    demand(packed["wav_sha256"] == without_report["wav_sha256"],
           "native packed/expanded input changes output words")
    negatives["packed_expanded_exact"] = "PASS"
    # A fake int32 intermediary cannot pass the exact-word oracle: quantify
    # the numerical mutant on an actual independently produced float64 file.
    raw = (work / "report-on.oracle.f64").read_bytes()
    fmt = "<d" if sys.byteorder == "little" else ">d"
    mutant_words = sum(1 for (x,) in struct.iter_unpack(fmt,raw)
                       if x != max(-(1 << 31),min((1 << 31)-1,
                                                  round(x*(1 << 31)))) / float(1 << 31))
    demand(mutant_words>0, "signed-int32 bridge mutant escaped the exact-word oracle")
    negatives["int32_bridge_mutant_rejected_words"] = mutant_words
    return {"suite": "decode", "status": "PASS", "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_git_commit": safe_git_head(ROOT), "source_sha256": identity,
            "executed_binary_sha256": binaries,
            "cases": cases, "case_count": len(cases), "negative_gates": negatives,
            "oracle": "independently constructed DSD bytes => public decoder => raw IEEE754 binary64 words",
            "independent_count_formula": "floor((2*N*pcm_rate+native_hz)/(2*native_hz))",
            "all_wav_f64_sample_words_match_api": True}


def main(sox: Path, oracle: Path, results: Path) -> int:
    results.mkdir(parents=True, exist_ok=True)
    receipt = results / "decode.json"
    receipt.unlink(missing_ok=True)
    scratch = results / "decode-fixtures"
    # This directory is exclusively suite-owned and may contain FIFO, output
    # symlinks and hardlinks from a prior or interrupted run. Rebuild it from
    # the same deterministic vectors instead of leaving stale test state.
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir()
    try:
        record = run_suite(sox, oracle, scratch)
    except Exception as exc:
        record = {"suite": "decode", "status": "FAIL",
                  "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "error": f"{type(exc).__name__}: {exc}",
                  "source_git_commit": safe_git_head(ROOT),
                  "executed_binary_sha256": {str(sox): sha(sox), str(oracle): sha(oracle)}}
        receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"FAIL decode: {record['error']}", file=sys.stderr)
        return 1
    receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"PASS decode: {record['case_count']} API word-oracle cases; "
          f"{len(record['negative_gates'])} negative/lifecycle gates")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sox", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    sys.exit(main(args.sox.resolve(), args.oracle.resolve(), args.results.resolve()))
