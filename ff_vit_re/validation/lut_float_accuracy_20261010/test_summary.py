"""Count-weighted global summaries must not average per-block percentages."""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize import aggregate


class SummaryTests(unittest.TestCase):
    def test_aggregate_uses_counts_and_squared_rmse(self):
        rows = [
            dict(count=2, mae_lsb=1.0, rmse_lsb=1.0, max_ae_lsb=1,
                 exact_rate=0.0, within_1_lsb_rate=1.0),
            dict(count=1, mae_lsb=2.0, rmse_lsb=2.0, max_ae_lsb=2,
                 exact_rate=0.0, within_1_lsb_rate=0.0),
        ]
        got = aggregate(rows)
        self.assertEqual(got["count"], 3)
        self.assertAlmostEqual(got["mae_lsb"], 4 / 3)
        self.assertAlmostEqual(got["rmse_lsb"], math.sqrt(2))
        self.assertEqual(got["max_ae_lsb"], 2)
        self.assertAlmostEqual(got["within_1_lsb_rate"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
