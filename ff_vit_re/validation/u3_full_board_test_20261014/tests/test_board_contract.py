"""Behavior tests for packing, score interpretation and fail-closed release."""
import importlib.util
import sys
import unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class BoardContractTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec('board_contract')
        self.assertIsNotNone(spec, 'full-dataset board contract has not been implemented')
        self.m = __import__('board_contract')

    def test_patch_and_token_pair_order_not_chw_or_row_major(self):
        x = np.zeros((3, 224, 224), np.float32)
        x[0, 0, 0] = 1/64
        x[0, 0, 16] = 2/64
        x[1, 0, 0] = 3/64
        payload = self.m.pack_input(x)
        self.assertEqual(len(payload), 301056)
        q = np.frombuffer(payload, dtype='<i2').reshape(98, 768, 2)
        self.assertEqual(q[0, 0].tolist(), [1, 2])
        self.assertEqual(q[0, 256].tolist(), [3, 0])
        self.assertEqual(int(np.count_nonzero(q)), 3)

    def test_rounding_is_ties_to_even_not_truncation(self):
        x = np.zeros((3, 224, 224), np.float32)
        x[0, 0, :4] = np.asarray([.5, 1.5, -.5, -1.5], np.float32)/64
        q = np.frombuffer(self.m.pack_input(x), dtype='<i2').reshape(98, 768, 2)
        self.assertEqual(q[0, :4, 0].tolist(), [0, 2, 0, -2])

    def test_nonfinite_input_is_rejected(self):
        x = np.zeros((3, 224, 224), np.float32)
        x[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            self.m.pack_input(x)

    def test_portable_padding_restores_bytes_without_changing_contents(self):
        p = {'_internal_padding': np.asarray([0, 1, 254, 255], np.uint8),
             '_tail_padding': bytes(range(8))}
        original = p['_internal_padding'].copy()
        blocks = self.m.native_padding([p])
        self.assertEqual(blocks[0]['_internal_padding'], bytes([0, 1, 254, 255]))
        self.assertEqual(blocks[0]['_tail_padding'], bytes(range(8)))
        np.testing.assert_array_equal(p['_internal_padding'], original)

    def test_s19_container_sign_extension(self):
        values = np.asarray([0, 262143, 262144, 524287, -1, -262144], np.int64)
        self.assertEqual(self.m.decode_s19(values).tolist(), [0, 262143, -262144, -1, -1, -262144])

    def test_top5_restricts_classes_and_breaks_ties_by_class_id(self):
        x = np.full(1000, -262143, np.int32)
        x[:6] = [4, 4, 9, -10, 0, 1]
        x[999] = 200000
        self.assertEqual(self.m.top5(x, 6).tolist(), [2, 0, 1, 5, 4])

    def test_complete_split_required_not_128_image_subset(self):
        with self.assertRaises(ValueError):
            self.m.validate_labels('plantvillage', np.zeros(128, np.int32))
        self.m.validate_labels('plantvillage', np.zeros(5459, np.int32))
        self.m.validate_labels('nwpu', np.zeros(4500, np.int32))
        with self.assertRaises(ValueError):
            self.m.validate_labels('nwpu', np.full(4500, 45, np.int32))

    def test_different_output_codes_not_hidden_by_equal_predictions(self):
        reference = np.zeros((2, 1000), np.int32)
        reference[:, 0] = 10
        actual = reference.copy()
        actual[1, 999] = 1
        report = self.m.compare_logits(actual, reference)
        self.assertEqual(report['mismatches'], 1)
        self.assertEqual(report['frames_with_mismatch'], 1)
        self.assertEqual(report['first_mismatch'], {'frame': 1, 'class': 999, 'actual': 1, 'reference': 0})

    def test_failed_timing_never_releases_boot_image(self):
        r = dict(csim_pass=True, data_complete=True, identity_verified=True,
                 wns=0.023, whs=0.01, wpws=0.1, setup_fail=0, hold_fail=0,
                 pulse_fail=0, routing_errors=0, unrouted=0, drc_errors=0,
                 clock_mhz=300.21509875, clock_verified=True)
        self.m.validate_release(r)
        for k,v in [('wns', -.001), ('csim_pass', False), ('identity_verified', False),
                    ('drc_errors', 1), ('clock_verified', False), ('clock_mhz', 250.)]:
            with self.subTest(field=k), self.assertRaises(ValueError):
                self.m.validate_release(dict(r, **{k:v}))


if __name__ == '__main__':
    unittest.main()
