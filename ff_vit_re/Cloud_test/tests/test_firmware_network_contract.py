"""Build and drive the real E06 lwIP raw state machine through its fake boundary."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "firmware" / "e06_net"
COMMON = ROOT / "firmware" / "common"
FAKE = NETWORK / "tests" / "fake_lwip"
FLAGS = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic")
TEST_FIRMWARE_ID = "1" * 64
IDENTITY_DEFINE = f'-DE06_FIRMWARE_SHA256="{TEST_FIRMWARE_ID}"'


class E06NetworkTests(unittest.TestCase):
    def test_fragmented_protocol_and_connection_lifecycle(self):
        sources = [
            NETWORK / "e06_network.c",
            COMMON / "fvit_protocol.c",
            FAKE / "fake_lwip.c",
            NETWORK / "tests" / "test_e06_network.c",
        ]
        for source in sources:
            self.assertTrue(source.is_file(), f"Missing E06 network source: {source}")
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "test_e06_network"
            built = subprocess.run(
                ["cc", *FLAGS, IDENTITY_DEFINE, "-DE06_HOST_TEST", "-I", str(NETWORK),
                 "-I", str(COMMON), "-I", str(FAKE), *map(str, sources),
                 "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertEqual((built.stdout, built.stderr), ("", ""))
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, "E06 network tests passed\n")
            self.assertEqual(ran.stderr, "")

    def test_parser_has_no_heap_calls(self):
        source = (NETWORK / "e06_network.c").read_text()
        forbidden = re.compile(r"\b(?:malloc|calloc|realloc|free)\s*\(")
        self.assertIsNone(forbidden.search(source))

    def test_main_compiles_against_firmware_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                ["cc", *FLAGS, IDENTITY_DEFINE, "-DSDT", "-DE06_HOST_TEST", "-I", str(NETWORK),
                 "-I", str(FAKE), "-c", str(NETWORK / "main.c"),
                 "-o", str(Path(temporary) / "main.o")],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((result.stdout, result.stderr), ("", ""))

    def test_production_config_has_no_zero_identity_fallback(self):
        config = (NETWORK / "net_config.h").read_text(encoding="utf-8")
        self.assertNotIn("0" * 64, config)
        self.assertIn("firmware_build_identity.h", config)

    def test_uart_boot_identity_includes_gate_required_hashes(self):
        source = (NETWORK / "main.c").read_text(encoding="utf-8")
        self.assertIn('FVIT_FIRMWARE_SHA256=%s', source)
        self.assertIn('FVIT_WEIGHTS_SHA256=%s', source)
        self.assertIn("E06_FIRMWARE_SHA256", source)
        self.assertIn("E06_WEIGHTS_SHA256", source)


if __name__ == "__main__":
    unittest.main()
