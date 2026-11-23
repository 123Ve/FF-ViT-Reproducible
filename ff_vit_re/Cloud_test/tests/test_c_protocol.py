"""Host-compiled checks for the standalone firmware's wire header codec."""

import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from Cloud_test.iot_eval.protocol import HEADER, Message, read_message


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "firmware" / "common"
FLAGS = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic")


class CProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.binary = Path(cls.temporary.name) / "test_fvit_protocol"
        compile_result = subprocess.run(
            ["cc", *FLAGS, "-I", str(COMMON),
             str(COMMON / "fvit_protocol.c"),
             str(COMMON / "tests" / "test_fvit_protocol.c"),
             "-o", str(cls.binary)],
            capture_output=True, text=True,
        )
        if compile_result.returncode:
            raise AssertionError(f"C compilation failed:\n{compile_result.stderr}")
        if compile_result.stdout or compile_result.stderr:
            raise AssertionError("C compilation produced output")

    def run_codec(self, *arguments):
        return subprocess.run(
            [str(self.binary), *arguments], capture_output=True, text=True,
        )

    def test_c_encoder_matches_python_wire_header(self):
        result = self.run_codec("encode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         HEADER.pack(b"FVIT", 1, 5, 0, 0x01020304, 17, 150528).hex() + "\n")
        self.assertEqual(result.stderr, "")

    def test_python_header_decodes_to_literal_c_fields(self):
        encoded = HEADER.pack(b"FVIT", 1, 255, 0, 0xA1B2C3D4, 65536, 4194304)
        result = self.run_codec("decode", encoded.hex())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "255,2712847316,65536,4194304\n")
        self.assertEqual(result.stderr, "")

    def test_c_header_is_readable_by_python_with_metadata_and_payload(self):
        result = self.run_codec("encode")
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = b'{"hello":"world"}'
        self.assertEqual(len(metadata), 17)
        stream = io.BytesIO(bytes.fromhex(result.stdout.strip()) + metadata + bytes(150528))
        self.assertEqual(read_message(stream),
                         Message("hello", 0x01020304, {"hello": "world"}, bytes(150528)))

    def test_selftest_covers_validation_without_output(self):
        result = self.run_codec("selftest")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((result.stdout, result.stderr), ("", ""))

    def test_decode_rejects_malformed_cli_and_header(self):
        good = HEADER.pack(b"FVIT", 1, 5, 0, 0, 0, 0).hex()
        for arguments in (("decode",), ("decode", good[:-1]),
                          ("decode", good[:-1] + "z"),
                          ("decode", "00" + good[2:]),
                          ("decode", good, "extra"), ("unknown",), ()):
            with self.subTest(arguments=arguments):
                self.assertNotEqual(self.run_codec(*arguments).returncode, 0)

    def test_compiler_flags_reject_warnings(self):
        source = "int main(void) { int unused; return 0; }\n"
        result = subprocess.run(
            ["cc", *FLAGS, "-x", "c", "-fsyntax-only", "-"],
            input=source, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unused", result.stderr)

    def test_magic_bytes_survive_non_ascii_execution_charset(self):
        source = """
            #include "fvit_protocol.h"
            int main(void) {
                uint8_t wire[FVIT_HEADER_SIZE];
                fvit_header_t header = {5u, 0u, 0u, 0u};
                if (fvit_header_encode(wire, &header) != FVIT_OK) return 1;
                if (wire[0] != 0x46u || wire[1] != 0x56u ||
                    wire[2] != 0x49u || wire[3] != 0x54u) return 2;
                return fvit_header_decode(&header, wire) == FVIT_OK ? 0 : 3;
            }
        """
        alternate = Path(self.temporary.name) / "alternate_charset"
        compile_result = subprocess.run(
            ["cc", *FLAGS, "-fexec-charset=IBM1047", "-I", str(COMMON),
             str(COMMON / "fvit_protocol.c"), "-x", "c", "-", "-o", str(alternate)],
            input=source, capture_output=True, text=True,
        )
        self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
        self.assertEqual((compile_result.stdout, compile_result.stderr), ("", ""))
        result = subprocess.run([str(alternate)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((result.stdout, result.stderr), ("", ""))


if __name__ == "__main__":
    unittest.main()
