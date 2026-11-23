import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class EntrypointTests(unittest.TestCase):
    def test_script_runs_directly_from_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot = root / "BOOT.BIN"
            weights = root / "weights.bin"
            image = root / "leaf.jpg"
            output = root / "results"
            boot.write_bytes(b"boot")
            weights.write_bytes(b"weights")
            image.write_bytes(b"x" * 1000)

            completed = subprocess.run(
                [
                    sys.executable,
                    "Cloud_test/run_smoke.py",
                    "--boot",
                    str(boot),
                    "--weights",
                    str(weights),
                    "--image",
                    str(image),
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"status": "HOST_LOOPBACK_PASS"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
