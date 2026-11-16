#!/usr/bin/env python3
"""Phase 06A: report carriers must neither clobber nor misclassify files."""
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import wave


def cmd(sox, root, *args, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run([sox, *args], cwd=root, env=merged,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=20, check=False)
    return result.returncode, result.stdout, result.stderr.decode(errors="replace")


def main():
    sox = str(pathlib.Path(sys.argv[1]).resolve())
    count = 0
    with tempfile.TemporaryDirectory(prefix="p06a-report-") as tmp:
        root = pathlib.Path(tmp)
        with wave.open(str(root / "in.wav"), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(struct.pack("<" + "h" * 4096, *([500] * 4096)))
        def assert_protected(target, argv, expected_rc=None, needle=None, env=None):
            nonlocal count
            original = target.read_bytes()
            rc, out, err = cmd(sox, root, *argv, env=env)
            assert (expected_rc is None and rc != 0) or rc == expected_rc, (argv, rc, err)
            assert target.read_bytes() == original, (argv, "carrier replaced")
            assert (needle is None) or needle in err, (argv, err)
            count += 1
        for spelling in ("NOISERED", "NoiseRed", "noisered"):
            target = root / "x.prof"
            target.write_text("Channel 0: 0.0, 0.0\n", encoding="ascii")
            assert_protected(target, ("--precision", "64", "--report", "x.prof",
                                      "in.wav", "out.wav", spelling, "x.prof", "0.2"))
        for spelling in ("FIR", "FirFit"):
            target = root / "filter.coef"
            target.write_text("0.5\n0.5\n", encoding="ascii")
            assert_protected(target, ("--precision", "64", "--report", "filter.coef",
                                      "in.wav", "out.wav", spelling, "filter.coef"))
        target = root / "x.prof"
        target.write_text("Channel 0: 0.0, 0.0\n", encoding="ascii")
        (root / "effects.txt").write_text("NOISERED x.prof 0.2\n", encoding="ascii")
        assert_protected(target, ("--precision", "64", "--report", "x.prof",
                                  "--effects-file", "effects.txt", "in.wav", "out.wav"))
        assert_protected(target, ("in.wav", "out.wav"),
                         env={"SOX_OPTS": "--precision 64 --report x.prof --effects-file effects.txt"})
        for option, contents in (("--comment-file", "hello\n"),
                                 ("--effects-file", "vol 0.5\n")):
            target = root / "-"
            target.write_text(contents, encoding="ascii")
            assert_protected(target, ("--precision", "64", "--report", "./-",
                                      "in.wav", option, "-", "out.wav"))
        target = root / "out002.wav"
        target.write_bytes(b"PRESERVE GENERATED OUTPUT")
        assert_protected(target, ("--precision", "64", "--report", "out002.wav",
                                  "in.wav", "out.wav", "trim", "0", "0.05", ":",
                                  "newfile", ":", "trim", "0", "0.05"))
        # Other directory entries may point at a numbered output inode.
        # Those must be protected even when the report has another name.
        for alias_kind in ("hardlink", "symlink"):
            numbered = root / "out002.wav"
            numbered.write_bytes(b"PRESERVE NUMBERED HARD/SYMLINK CARRIER")
            alias = root / "report-elsewhere.json"
            if alias_kind == "hardlink":
                os.link(numbered, alias)
            else:
                alias.symlink_to(numbered)
            assert_protected(numbered, ("--precision", "64", "--report",
                                      alias.name, "in.wav", "out.wav", "trim",
                                      "0", "0.05", ":", "newfile", ":",
                                      "trim", "0", "0.05"))
            alias.unlink()
            numbered.unlink()
        target = root / "in2.wav"
        target.write_bytes((root / "in.wav").read_bytes())
        assert_protected(target, ("--precision", "64", "--report", "in2.wav",
                                  "|cat in2.wav", "out.wav"))
        target = root / "-"
        target.write_text("vol 0.5\n", encoding="ascii")
        for variant in ("present", "missing"):
            if variant == "missing":
                target.unlink()
            rc1, o1, e1 = cmd(sox, root, "--precision", "64", "--effects-file", "-",
                               "in.wav", "o.wav")
            rc2, o2, e2 = cmd(sox, root, "--precision", "64", "--report", "-",
                               "--effects-file", "-", "in.wav", "o.wav")
            assert rc1 == rc2 and not e2.startswith("sox FAIL sox_ng: --report conflicts with another stdout operand"), (variant, rc1, rc2, e1, e2)
            count += 1
        target.write_text("comment\n", encoding="ascii")
        for before in (True, False):
            first = ("--comment-file", "-") if before else ()
            last = () if before else ("--comment-file", "-", "o.wav")
            base = ("--precision", "64", *first, "in.wav", "o.wav") if before else ("--precision", "64", "in.wav", *last)
            test = ("--precision", "64", "--report", "-", *first, "in.wav", "o.wav") if before else ("--precision", "64", "--report", "-", "in.wav", *last)
            rc1, o1, e1 = cmd(sox, root, *base)
            rc2, o2, e2 = cmd(sox, root, *test)
            assert rc1 == rc2 and "--report conflicts with another stdout operand" not in e2, (rc1, rc2, e1, e2)
            count += 1
        print(f"PASS: {count} Phase06A report-carrier cases")


if __name__ == "__main__":
    main()
