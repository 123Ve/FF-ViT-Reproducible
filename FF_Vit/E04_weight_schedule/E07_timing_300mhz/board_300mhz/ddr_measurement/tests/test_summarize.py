import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "summarize_ddr.py"


class SummaryTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.exists(), "DDR result summarizer not implemented")
        spec = importlib.util.spec_from_file_location("ddr_summary", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def fixture(self):
        # 100 frames, exactly one second. Traffic is a test fixture, not a board result.
        header = "repeat,frames,frame_ticks,window_ticks,weight_read_bytes,weight_write_bytes,dma_read_bytes,dma_write_bytes,weight_read_requests,weight_write_requests,dma_read_requests,dma_write_requests,mismatches"
        row = "0,100,100000000,100000000,299462400,0,30105600,400000,1948300,0,470400,6300,0"
        return "TIMER_HZ=100000000\nIDLE_SHARED_PORT_BYTES=0\nDDR_CSV_BEGIN\n" + header + "\n" + row + "\nDDR_CSV_END\nDDR_TEST_PASS\n"

    def test_direct_bandwidth_uses_measured_window(self):
        result = self.load().summarize(self.fixture())
        self.assertEqual(result["frames"], 100)
        self.assertAlmostEqual(result["port_total_MB_s"], 329.968)
        self.assertEqual(result["port_bytes_per_frame"], 3299680)
        self.assertEqual(result["fps"], 100)
        self.assertEqual(result["expected_byte_budget_match"], True)

    def test_nonzero_idle_traffic_blocks_application_attribution(self):
        log = self.fixture().replace("IDLE_SHARED_PORT_BYTES=0", "IDLE_SHARED_PORT_BYTES=64")
        with self.assertRaisesRegex(ValueError, "idle|shared"):
            self.load().summarize(log)

    def test_incomplete_log_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete|PASS"):
            self.load().summarize(self.fixture().replace("DDR_TEST_PASS", "DDR_TEST_FAIL"))

    def test_wrong_logits_are_rejected(self):
        log = self.fixture().replace(",6300,0\n", ",6300,1\n")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.load().summarize(log)

    def test_wrong_bytes_are_not_labeled_validated_application_traffic(self):
        log = self.fixture().replace("299462400", "299462416")
        self.assertFalse(self.load().summarize(log)["expected_byte_budget_match"])


if __name__ == "__main__":
    unittest.main()
