"""Behavior tests: catch lost ABI padding, wrong fused casts and changed weights."""
import copy
from pathlib import Path
import unittest
import numpy as np
import torch

try:
    import u3_validation as u3
except ModuleNotFoundError:
    u3 = None


class U3Tests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(u3, "U3 independent validation runtime not implemented")
        torch.set_num_threads(2)

    def test_native_binary_roundtrip_and_probability_width(self):
        for name in ("plantvillage", "nwpu"):
            spec = u3.dataset_spec(name)
            raw = spec["weights"].read_bytes()
            blocks = u3.decode_blocks(raw)
            self.assertEqual(len(raw), 2772096)
            self.assertEqual(u3.encode_blocks(blocks), raw)
            self.assertEqual([int(p["softmax"]["scalars"][13]) for p in blocks], [8] * 12)
            self.assertEqual(blocks[0]["m1_w"].shape, (768, 192))

    def test_malformed_binary_rejected(self):
        with self.assertRaisesRegex(ValueError, "ABI"):
            u3.decode_blocks(bytes(231008))

    def test_calibration_event_has_one_block_key(self):
        event = getattr(u3, "calibration_event", None)
        self.assertIsNotNone(event, "calibration event must not duplicate block keyword")
        self.assertEqual(event(dict(block=0, elapsed_seconds=1.0)),
                         dict(event="calibrated_block", block=0, elapsed_seconds=1.0))

    def test_fused_u3_is_clamp_not_uint3_modulo(self):
        # 4096 * 255 / 2048 = 510. Clamp=7, modulo8 would be6.
        scalars = np.array([0, 0, 31, 0, 20, 63, 1024, 11,
                            0, 20, 63, 1024, 11, 3], np.int32)
        codes = u3.exact.fused_softmax(torch.zeros(1, 196, dtype=torch.int64),
            scalars, np.full(32, 4096, np.uint16), np.full(64, 255, np.uint8),
            np.full(64, -1, np.int8))
        self.assertTrue(torch.equal(codes, torch.full((1, 196), 7, dtype=torch.int64)))

    def test_unsigned_exp_cursor_wraps_before_clamp(self):
        # raw address256 casts U8->0, not clamp31.
        codes = u3.exact.address_lut(torch.tensor([256], dtype=torch.int64),
            [0, 0, 31], np.arange(32, dtype=np.int64), 8, False)
        self.assertEqual(codes.tolist(), [0])

    def test_only_softmax_and_aq_bytes_may_change(self):
        old = u3.dataset_spec("plantvillage")["weights"].read_bytes()
        p = u3.decode_blocks(old)
        p[0]["softmax"]["scalars"][13] = 3
        new = u3.encode_blocks(p)
        self.assertEqual(u3.authorized_changes(old, new)["unauthorized_byte_changes"], 0)
        corrupt = bytearray(new)
        corrupt[0] ^= 1
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            u3.authorized_changes(old, bytes(corrupt))

    def test_u3_reciprocal_fit_retains_native_exp_and_changes_scale(self):
        old = u3.decode_blocks(u3.dataset_spec("plantvillage")["weights"].read_bytes())[0]
        scores = torch.zeros(4, 196, dtype=torch.int64)
        scores[:, 0] = 128
        fitted, report = u3.fit_u3_softmax(scores, old["softmax"], score_scale=.02)
        self.assertEqual(int(fitted["scalars"][13]), 3)
        self.assertTrue(np.array_equal(fitted["exp"], old["softmax"]["exp"]))
        self.assertGreater(fitted["output_scale"], 0)
        out = u3.exact.fused_softmax(scores, fitted["scalars"], fitted["exp"],
            fitted["recip1"], fitted["recip2"])
        self.assertGreater(int(out.max()), 0)
        self.assertLessEqual(int(out.max()), 7)
        self.assertEqual(report["fitted_rows"], 4)

    def test_hls_u8_runtime_matches_saved_all_boundaries(self):
        for name in ("plantvillage", "nwpu"):
            spec = u3.dataset_spec(name)
            artifact = u3.load_native_artifact(spec)
            result = u3.verify_historical_fixture(spec, artifact, torch.device("cpu"))
            self.assertEqual(result["mismatches"], 0)
            self.assertEqual(result["checked_integer_count"], 490600)
            self.assertEqual(len(result["boundaries"]), 16)

    def test_frozen_dataset_and_old_128_image_selection(self):
        prepare = getattr(u3, "prepare_datasets", None)
        self.assertIsNotNone(prepare, "frozen test/calibration dataset binding not implemented")
        for name, count in (("plantvillage", 5459), ("nwpu", 4500)):
            datasets, record = prepare(u3.dataset_spec(name))
            self.assertEqual(len(datasets["test"]), count)
            self.assertEqual(len(record["natural_indices"]), 128)
            self.assertEqual(record["selected_calibration_count"], 256)
            self.assertEqual(record["selected_calibration_test_sha256_overlap"], 0)


if __name__ == "__main__":
    unittest.main()
