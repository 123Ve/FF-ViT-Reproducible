import json
from pathlib import Path
import tempfile
import unittest

from Cloud_test.iot_eval.workflow import run_loopback_smoke


class WorkflowTests(unittest.TestCase):
    def test_creates_self_contained_smoke_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot = root / "BOOT.BIN"
            weights = root / "weights.bin"
            image = root / "leaf.jpg"
            output = root / "results"
            boot.write_bytes(b"boot")
            weights.write_bytes(b"weights")
            image.write_bytes(b"x" * 1000)

            report = run_loopback_smoke(boot, weights, image, output)

            self.assertEqual(report["status"], "HOST_LOOPBACK_PASS")
            self.assertEqual(report["scope"], "host_protocol_only_not_zcu102_ethernet")
            self.assertGreater(report["metrics"]["uplink_reduction_percent"], 0)
            self.assertTrue((output / "artifact_manifest.json").is_file())
            self.assertTrue((output / "events.jsonl").is_file())
            saved = json.loads((output / "smoke_report.json").read_text())
            self.assertEqual(saved["input_image"]["bytes"], 1000)


if __name__ == "__main__":
    unittest.main()
