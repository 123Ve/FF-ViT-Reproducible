import unittest

from Cloud_test.iot_eval.metrics import summarize_transfers


class MetricsTests(unittest.TestCase):
    def test_reports_edge_uplink_reduction_against_cloud_frames(self):
        summary = summarize_transfers(
            [
                {"mode": "cloud", "wire_bytes": 1000, "rtt_ms": 2.0},
                {"mode": "cloud", "wire_bytes": 1200, "rtt_ms": 4.0},
                {"mode": "edge", "wire_bytes": 100, "rtt_ms": 1.0},
                {"mode": "edge", "wire_bytes": 120, "rtt_ms": 1.4},
            ]
        )

        self.assertEqual(summary["cloud"]["mean_wire_bytes"], 1100.0)
        self.assertEqual(summary["edge"]["mean_wire_bytes"], 110.0)
        self.assertEqual(summary["uplink_reduction_percent"], 90.0)
        self.assertEqual(summary["edge"]["mean_rtt_ms"], 1.2)


if __name__ == "__main__":
    unittest.main()
