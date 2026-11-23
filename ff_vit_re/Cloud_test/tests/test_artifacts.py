import tempfile
from pathlib import Path
import unittest

from Cloud_test.iot_eval.artifacts import inspect_artifacts


class ArtifactTests(unittest.TestCase):
    def test_records_size_and_sha256_without_modifying_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot = root / "BOOT.BIN"
            weights = root / "weights.bin"
            boot.write_bytes(b"abc")
            weights.write_bytes(b"weights")

            manifest = inspect_artifacts({"boot": boot, "weights": weights})

            self.assertEqual(manifest["boot"]["bytes"], 3)
            self.assertEqual(
                manifest["boot"]["sha256"],
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )
            self.assertEqual(manifest["weights"]["bytes"], 7)
            self.assertEqual(boot.read_bytes(), b"abc")
            self.assertEqual(weights.read_bytes(), b"weights")


if __name__ == "__main__":
    unittest.main()
