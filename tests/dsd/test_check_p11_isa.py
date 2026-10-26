#!/usr/bin/env python3
"""Regression tests for the AVX1/AVX2 object-code classification boundary."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

from check_p11_isa import inspect_objdump


@unittest.skipUnless(
    platform.machine().lower() in ("x86_64", "amd64", "i386", "i686")
    and shutil.which("cc") and shutil.which("objdump"),
    "requires an x86 assembler and objdump",
)
class Avx1InstructionBoundary(unittest.TestCase):
    def inspect(self, instructions):
        with tempfile.TemporaryDirectory(prefix="sdm-isa-check-") as name:
            root = Path(name)
            source, obj = root / "probe.s", root / "probe.o"
            source.write_text(".text\n.globl probe\nprobe:\n"
                              + "\n".join(instructions) + "\nret\n")
            subprocess.run(["cc", "-c", str(source), "-o", str(obj)],
                           check=True, capture_output=True, text=True)
            return inspect_objdump(obj)

    def test_avx1_allows_ymm_vptest_and_xmm_integer(self):
        report = self.inspect([
            "vptest %ymm0, %ymm1",
            "vpxor %xmm0, %xmm1, %xmm2",
            "vpermilpd $5, %ymm0, %ymm1",
            "vperm2f128 $0x21, %ymm0, %ymm1, %ymm2",
        ])
        self.assertEqual(report["avx_mnemonics"]["vptest"], 1)
        self.assertEqual(report["possible_avx2_mnemonics"], [])

    def test_avx2_ymm_integer_and_permute_remain_forbidden(self):
        report = self.inspect([
            "vpxor %ymm0, %ymm1, %ymm2",
            "vpaddq %ymm0, %ymm1, %ymm2",
            "vpshufd $0, %ymm0, %ymm1",
            "vpermpd $0x1b, %ymm0, %ymm1",
            "vpbroadcastd %xmm0, %xmm1",
        ])
        self.assertEqual(set(report["possible_avx2_mnemonics"]),
                         {"vpxor", "vpaddq", "vpshufd", "vpermpd", "vpbroadcastd"})


if __name__ == "__main__":
    unittest.main()
