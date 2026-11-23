"""Compile and exercise the real E06 modules with hardware-only BSP doubles."""

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "firmware" / "e06_net"
FLAGS = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic")


class E06ModuleTests(unittest.TestCase):
    def test_hardware_boundary_preserves_module_behavior(self):
        sources = [MODULES / "e06_inference.c", MODULES / "e06_telemetry.c",
                   MODULES / "tests" / "fake_bsp" / "e06_fake_bsp.c",
                   MODULES / "tests" / "test_e06_modules.c"]
        for source in sources:
            self.assertTrue(source.is_file(), f"Missing E06 module/test: {source}")
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "test_e06_modules"
            result = subprocess.run(
                ["cc", *FLAGS, "-DE06_HOST_TEST", "-I", str(MODULES),
                 *map(str, sources), "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((result.stdout, result.stderr), ("", ""))
            result = subprocess.run([str(binary)], capture_output=True, text=True,
                                    timeout=20, cwd=temporary)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "E06 module tests passed\n")
            self.assertEqual(result.stderr, "")

    def test_weight_layout_matches_pinned_vendor_bytes(self):
        target = MODULES / "weight_layout.h"
        self.assertTrue(target.is_file(), "E06 firmware weight layout is missing")
        vendor = ROOT / "vendor" / "e06_base" / "include" / "weight_layout.h"
        self.assertEqual(hashlib.sha256(target.read_bytes()).digest(),
                         hashlib.sha256(vendor.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
