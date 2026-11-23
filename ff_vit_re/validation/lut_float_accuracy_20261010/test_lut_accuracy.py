"""Behavior checks for the independent LUT-to-float numerical audit."""

import math
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lut_accuracy import CodeMoments, evaluate_softmax


class NumericalAuditTests(unittest.TestCase):
    def test_code_moments_use_element_counts_and_not_row_averages(self):
        metric = CodeMoments()
        metric.add(torch.tensor([0, 1]), torch.tensor([0, 0]))
        metric.add(torch.tensor([2]), torch.tensor([0]))
        got = metric.result()
        self.assertEqual(got["count"], 3)
        self.assertAlmostEqual(got["mae_lsb"], 1.0)
        self.assertAlmostEqual(got["rmse_lsb"], math.sqrt(5 / 3))
        self.assertEqual(got["max_ae_lsb"], 2)
        self.assertAlmostEqual(got["exact_rate"], 1 / 3)
        self.assertAlmostEqual(got["within_1_lsb_rate"], 2 / 3)

    def test_softmax_same_integer_scores_use_real_softmax_reference(self):
        # Hand checked: exp(0):exp(-2 ln 2) = 4:1; 8-code target [6, 2].
        # An EXP table with [4096, 1024], sum 5120 and reciprocal code 3
        # gives ((4096*3+1024)>>11, (1024*3+1024)>>11) = [6, 2].
        scores = torch.tensor([[2, 0]], dtype=torch.int64)
        scalars = np.array([0, 1, 31, 0, 8, 63, 1024, 11,
                            0, 9, 63, 1024, 11, 3], dtype=np.int32)
        exp_table = np.zeros(32, dtype=np.uint16)
        exp_table[0], exp_table[1] = 4096, 1024
        recip1 = np.zeros(64, dtype=np.uint8)
        recip1[20] = 3
        recip2 = np.zeros(64, dtype=np.uint8)
        got = evaluate_softmax(scores, scalars, exp_table, recip1, recip2,
                               score_scale=math.log(2), output_scale=1 / 8)
        self.assertEqual(got["lut_codes"].tolist(), [[6, 2]])
        self.assertEqual(got["fp_codes"].tolist(), [[6, 2]])
        self.assertEqual(got["exp_lut_codes"].tolist(), [[4096, 1024]])
        self.assertEqual(got["exp_fp_codes"].tolist(), [[4096, 1024]])
        self.assertEqual(got["recip_lut_codes"].tolist(), [3])
        self.assertEqual(got["recip_fp_codes"].tolist(), [3])

    def test_exported_legacy_softmax_matches_original_stage4l_arithmetic(self):
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "quantization_final/scripts"))
        import stage4l_exact_softmax_aq as source
        stage = root / "quantization_final/artifacts/stage4l_exact_softmax_aq"
        report = json.loads((root / "quantization_final/reports/stage4l_exact_softmax_aq/report.json").read_text())
        scalars = np.load(stage / "softmax_scalars.npy", allow_pickle=False)[0]
        exp_table = np.load(stage / "softmax_exp_table.npy", allow_pickle=False)[0]
        recip_one = np.load(stage / "softmax_recip_table_one.npy", allow_pickle=False)[0]
        recip_two = np.load(stage / "softmax_recip_table_two_int8.npy", allow_pickle=False)[0]
        rng = torch.Generator().manual_seed(20261010)
        q = torch.randint(-4, 4, (1, 3, 16, 64), generator=rng).float()
        k = torch.randint(-4, 4, (1, 3, 16, 64), generator=rng).float()
        scores = torch.matmul(q, k.transpose(-1, -2)).round().to(torch.int64)
        fit = report["blocks"]["0"]
        exp = source.apply_exp(scores, dict(b1=int(scalars[0]), s1=int(scalars[1]),
                                                bound1=int(scalars[2]), table=exp_table))
        acc = exp.sum(-1).remainder(1 << 23)
        recip_fit = dict(b2_one=int(scalars[3]), s2_one=int(scalars[4]), bound2_one=int(scalars[5]),
                         b2_two=int(scalars[8]), s2_two=int(scalars[9]), bound2_two=int(scalars[10]),
                         table_one=recip_one, table_two_uint8=recip_two.astype(np.uint8))
        reciprocal, _ = source.apply_recip(acc, recip_fit)
        expected = ((exp * reciprocal.unsqueeze(-1)).remainder(1 << 23) + source.SOFTMAX_B3) >> source.SOFTMAX_SHIFT3
        expected = expected.clamp(0, (1 << source.SOFTMAX_CLAMP_BITS) - 1)
        measured = evaluate_softmax(scores, scalars, exp_table, recip_one, recip_two,
                                    score_scale=fit["q_scale"] * fit["k_scale"] * fit["attn_scale"],
                                    output_scale=1 / source.WEIGHT_SCALE)
        self.assertTrue(torch.equal(measured["lut_codes"], expected))


if __name__ == "__main__":
    unittest.main()
