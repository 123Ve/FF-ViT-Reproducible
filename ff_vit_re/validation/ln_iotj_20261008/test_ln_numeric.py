"""Numeric contract tests; run with PYTHONDONTWRITEBYTECODE=1 python -m unittest."""
import unittest
from pathlib import Path

import numpy as np

try:
    import ln_numeric as ln
except ImportError:
    ln = None


def parameters(c=4, **kwargs):
    p = dict(scalars=np.array([1, 2, 0, 0, 127, 0, 3]),
             lnw=np.ones(c, dtype=np.int64), lnb=np.zeros(c, dtype=np.int64),
             rsqrt_table=np.ones(128, dtype=np.int64))
    p.update(kwargs)
    return p


def scalar_source_oracle(row, p, bits):
    """Independent, deliberately scalar translation of source assignments."""
    def cast(value, width):
        value = int(value) % (2**width)
        return value-2**width if value >= 2**(width-1) else value
    m, ms, b, s1, bound, s2, _ = map(int, p['scalars'])
    acc = sum(map(int, row))
    square_sum = sum(int(v)**2 for v in row)
    mean = cast(cast(acc*m, 32)+2**(ms-1), 32) >> ms
    two_mu_s = cast(2*mean*acc, 64)
    c_mu2 = cast(len(row)*mean*mean, 64)
    variance = cast(cast(cast(square_sum-two_mu_s, 64)+c_mu2, 64), 36)
    cursor = min(max(cast(cast(variance+b, 37) >> s1, 32), 0), bound)
    output = []
    for v, w, bias in zip(row, p['lnw'], p['lnb']):
        diff = cast(int(v)-mean, bits)
        affine = cast(diff*int(p['rsqrt_table'][cursor])*int(w)+int(bias), 40)
        shifted = cast(affine >> s2, 32)
        output.append(min(max(shifted, -4), 3))
    return output, mean, variance, cursor


class NumericTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ln, "numeric kernel has not been implemented")

    def test_constant_and_negative_half_mean_rounding(self):
        out = ln.fixed_layernorm(np.array([[7, 7, 7, 7], [-1, -1, 0, 0]]), parameters())
        np.testing.assert_array_equal(out['mean'], [7, 0])
        np.testing.assert_array_equal(out['variance'], [0, 2])
        np.testing.assert_array_equal(out['codes'], [[0, 0, 0, 0], [-1, -1, 0, 0]])

    def test_alternating_s15_extrema_wrap_variance_and_diff(self):
        p = parameters(192)
        p['scalars'] = np.array([1, 8, 0, 0, 127, 0, 3])
        x = np.tile([-16384, 16383], 96)[None, :]
        out = ln.fixed_layernorm(x, p, input_bits=15)
        ideal = ln.fixed_layernorm(x, p, input_bits=15, finite_width=False)
        self.assertEqual(int(ideal['variance'][0]), 51536461920)
        self.assertEqual(int(out['variance'][0]), -17183014816)
        self.assertEqual(int(out['cursor_unclamped'][0]), -3145632)
        self.assertEqual(int(out['cursor'][0]), 0)  # int32 truncation precedes clamp
        self.assertEqual(out['diagnostics']['Var_sum']['wrap_count'], 1)
        self.assertEqual(out['diagnostics']['Var_sum']['pre_max'], 51536461920)

    def test_mean_product_and_rounding_addition_wrap_separately(self):
        p = parameters()
        p['scalars'][0] = 2**30
        out = ln.fixed_layernorm(np.ones((1, 4), dtype=np.int64), p)
        ideal = ln.fixed_layernorm(np.ones((1, 4), dtype=np.int64), p, finite_width=False)
        self.assertEqual(int(out['mean'][0]), 0)
        self.assertEqual(int(ideal['mean'][0]), 1073741824)
        self.assertEqual(out['diagnostics']['mean_product']['wrap_count'], 1)
        self.assertEqual(ideal['diagnostics']['Cmu2']['pre_max'], 2**62)
        p['scalars'] = np.array([1, 30, 0, 0, 127, 0, 3])
        p['lnb'][:] = 0
        out = ln.fixed_layernorm(np.full((1, 4), 2**29-1), p, input_bits=31)
        self.assertEqual(out['diagnostics']['mean_round_add']['wrap_count'], 1)

    def test_37_bit_cursor_addition_preserves_carry(self):
        p = parameters(2)
        p['scalars'] = np.array([1, 1, 2**31-1, 4, 127, 0, 3])
        out = ln.fixed_layernorm(np.array([[-16384, 16383]]), p, input_bits=15)
        self.assertEqual(out['diagnostics']['cursor_add']['bits'], 37)
        self.assertEqual(int(out['cursor_unclamped'][0]), 167770112)

    def test_input_diff_affine_and_shift_casts_and_saturation(self):
        p = parameters()
        p['lnw'][:] = 2**31-1
        p['rsqrt_table'][:] = 2**31-1
        out = ln.fixed_layernorm(np.array([[4095, -4096, 4095, -4096]]), p)
        ideal = ln.fixed_layernorm(np.array([[4095, -4096, 4095, -4096]]), p, finite_width=False)
        self.assertGreater(ideal['diagnostics']['affine']['pre_max'], 2**63)
        self.assertEqual(out['diagnostics']['affine']['wrap_count'], 4)
        self.assertEqual(out['diagnostics']['shifted']['wrap_count'], 2)
        self.assertGreater(out['diagnostics']['output_clip']['saturation_count'], 0)
        self.assertTrue(np.all(out['codes'] >= -4))
        self.assertTrue(np.all(out['codes'] <= 3))

    def test_diff_uses_input_width(self):
        p = parameters()
        x = np.array([[4095, -4096, -4096, -4096]])
        out = ln.fixed_layernorm(x, p)
        self.assertEqual(int(out['mean'][0]), -2048)
        self.assertEqual(int(out['diff'][0, 0]), -2049)
        self.assertEqual(out['diagnostics']['diff']['wrap_count'], 1)

    def test_dataset_final_export_parameters_high_mean_low_variance(self):
        root = Path(__file__).resolve().parents[2] / 'quantization_final'
        binary = (root / 'deployment' / 'weights.bin').read_bytes()
        for family, stage, bits, offset, pad in [
            ('ln1', 'stage4k_exact_attn_outer', 13, 75276, 0),
            ('ln2', 'stage4m_exact_encoder', 15, 78688+149384, 4),
        ]:
            with self.subTest(family=family):
                p = {key: np.load(root / 'artifacts' / stage / f'{family}_{key}.npy',
                                  allow_pickle=False)[0]
                     for key in ('scalars', 'lnw', 'lnb', 'rsqrt_table')}
                np.testing.assert_array_equal(p['scalars'], np.frombuffer(binary, '<i4', 7, offset))
                lnb_offset = offset+28+192*4+pad
                np.testing.assert_array_equal(p['lnw'], np.frombuffer(binary, '<i4', 192, offset+28))
                np.testing.assert_array_equal(p['lnb'], np.frombuffer(binary, '<i8', 192, lnb_offset))
                np.testing.assert_array_equal(p['rsqrt_table'], np.frombuffer(binary, '<i4', 128, lnb_offset+192*8))
                x = np.full((2, 192), 3000, dtype=np.int64)
                x[1, 0] += 1
                out = ln.fixed_layernorm(x, p, input_bits=bits)
                ideal = ln.fixed_layernorm(x, p, input_bits=bits, finite_width=False)
                np.testing.assert_array_equal(out['mean'], [3001, 3001])
                np.testing.assert_array_equal(ideal['mean'], [3001, 3001])
                np.testing.assert_array_equal(ideal['variance'], [192, 191])
                self.assertEqual(out['diagnostics']['mean_product']['wrap_count'], 0)
                for token, row in enumerate(x):
                    codes, mean, variance, cursor = scalar_source_oracle(row, p, bits)
                    np.testing.assert_array_equal(out['codes'][token], codes)
                    self.assertEqual(int(out['mean'][token]), mean)
                    self.assertEqual(int(out['variance'][token]), variance)
                    self.assertEqual(int(out['cursor'][token]), cursor)

    def test_source_native64_variance_terms_do_not_silently_overflow_numpy(self):
        p = parameters(192)
        p['scalars'][:2] = [11184810, 1]
        x = np.ones((1, 192), dtype=np.int64)
        actual = ln.fixed_layernorm(x, p)
        ideal = ln.fixed_layernorm(x, p, finite_width=False)
        self.assertEqual(int(actual['mean'][0]), 1073741760)
        self.assertEqual(actual['diagnostics']['Cmu2']['pre_max'], 192*1073741760**2)
        self.assertEqual(actual['diagnostics']['Cmu2']['wrap_count'], 1)
        self.assertEqual(int(ideal['variance'][0]), 192*(1073741760-1)**2)

    def test_scalar_source_oracle_on_seeded_full_range_batches(self):
        rng = np.random.default_rng(20261008)
        for bits in (13, 15):
            for multiplier, shift in ((683, 17), (43691, 23)):
                p = parameters(192)
                p['scalars'] = np.array([multiplier, shift, -1842833, 19, 127, 31, 3])
                p['lnw'] = rng.integers(-2**31, 2**31, 192, dtype=np.int64)
                p['lnb'] = rng.integers(-2**62, 2**62, 192, dtype=np.int64)
                p['rsqrt_table'] = rng.integers(-2**31, 2**31, 128, dtype=np.int64)
                x = rng.integers(-2**(bits-1), 2**(bits-1), (8, 192), dtype=np.int64)
                got = ln.fixed_layernorm(x, p, input_bits=bits)
                expected = [scalar_source_oracle(row, p, bits) for row in x]
                for token, (codes, mean, variance, cursor) in enumerate(expected):
                    np.testing.assert_array_equal(got['codes'][token], codes)
                    self.assertEqual(int(got['mean'][token]), mean)
                    self.assertEqual(int(got['variance'][token]), variance)
                    self.assertEqual(int(got['cursor'][token]), cursor)

    def test_fp32_reference_same_dequantized_inputs_and_ties_even(self):
        result = ln.fp32_reference(np.array([[2, 2, 2, 2]]), gamma=np.ones(4),
                                   beta=np.array([.5, 1.5, -.5, -1.5]),
                                   input_scale=.25, output_scale=1.)
        self.assertEqual(result['real'].dtype, np.float32)
        np.testing.assert_array_equal(result['codes'], [[0, 2, 0, -2]])

    def test_analytic_reference_and_lut_attribution(self):
        out = ln.compare_batch(np.array([[0, 0, 2, 2]]), parameters(), input_bits=13,
                               gamma=np.ones(4), beta=np.zeros(4), input_scale=1., output_scale=1.)
        np.testing.assert_allclose(out['analytic']['normalized'], [[-1, -1, 1, 1]], rtol=1e-5)
        self.assertAlmostEqual(float(out['attribution']['mean_variance_real'][0]), 1.)
        self.assertAlmostEqual(float(out['attribution']['lut_rsqrt'][0]), 2**-20)
        self.assertAlmostEqual(float(out['attribution']['exact_mean_rsqrt'][0]), 1/np.sqrt(1.000001))

    def test_streaming_metrics_weight_elements_and_separate_units(self):
        a = ln.MetricAccumulator()
        a.update(np.array([0., 2.]), np.array([0., 0.]), np.array([0, 2]), np.array([0, 0]))
        b = ln.MetricAccumulator()
        b.update(np.array([4.]), np.array([0.]), np.array([2]), np.array([0]))
        a.merge(b)
        out = a.summary()
        self.assertEqual(out['count'], 3)
        self.assertEqual(out['real_mae'], 2.)
        self.assertAlmostEqual(out['real_rmse'], np.sqrt(20/3))
        self.assertAlmostEqual(out['code_mae'], 4/3)
        self.assertEqual(out['code_maxae'], 2)
        self.assertAlmostEqual(out['exact_code_agreement'], 1/3)
        self.assertAlmostEqual(out['within_1_lsb'], 1/3)

    def test_attribution_reductions_report_lut_and_variance_error_separately(self):
        self.assertTrue(hasattr(ln, 'ErrorAccumulator'), 'scalar error reduction is missing')
        self.assertTrue(hasattr(ln, 'AttributionAccumulator'), 'attribution reduction is missing')
        metric = ln.ErrorAccumulator()
        metric.update(np.array([1., 4.]), np.array([0., 2.]))
        tail = ln.ErrorAccumulator().update(np.array([2.]), np.array([1.]))
        metric.merge(tail)
        self.assertEqual(metric.summary()['count'], 3)
        self.assertAlmostEqual(metric.summary()['mae'], 4/3)
        self.assertAlmostEqual(metric.summary()['rmse'], np.sqrt(2.))
        self.assertEqual(metric.summary()['maxae'], 2.)
        batch = ln.compare_batch(np.array([[0, 0, 2, 2]]), parameters(), input_bits=13,
                                 gamma=np.ones(4), beta=np.zeros(4), input_scale=1., output_scale=1.)
        metric = ln.AttributionAccumulator().update(batch)
        summary = metric.summary()
        self.assertEqual(summary['variance_code']['maxae'], 0.)
        self.assertEqual(summary['variance_real']['maxae'], 0.)
        self.assertAlmostEqual(summary['lut_rsqrt']['maxae'], 1/np.sqrt(1.000001)-2**-20)
        self.assertEqual(summary['normalized_lut']['count'], 4)

    def test_ranges_merge_wrap_and_saturation_counts(self):
        a = ln.RangeAccumulator()
        p = parameters()
        a.update(ln.fixed_layernorm(np.zeros((1, 4), dtype=np.int64), p)['diagnostics'])
        a.update(ln.fixed_layernorm(np.array([[0, 0, 20, 20]]), p)['diagnostics'])
        row = a.summary()['output_clip']
        self.assertEqual(row['count'], 8)
        self.assertEqual(row['pre_min'], -10)
        self.assertEqual(row['post_max'], 3)
        self.assertEqual(row['saturation_count'], 4)

    def test_published_bounds_refute_s15_variance_safety(self):
        b = ln.mathematical_bounds(parameters(192), input_bits=15)
        self.assertEqual(b['channels'], 192)
        self.assertEqual(b['S_min'], -3145728)
        self.assertEqual(b['S_max'], 3145536)
        self.assertEqual(b['S_sq_max'], 51539607552)
        self.assertEqual(b['balanced_extrema_variance'], 51536461920)
        self.assertFalse(b['variance36_full_domain_sufficient'])
        self.assertEqual(b['affine40_limit'], 549755813887)

    def test_rejects_wrong_shape_noninteger_and_bad_shifts(self):
        with self.assertRaises(ValueError):
            ln.fixed_layernorm(np.ones((2, 3), dtype=np.int64), parameters())
        with self.assertRaises(ValueError):
            ln.fixed_layernorm(np.ones((1, 4), dtype=np.float64), parameters())
        p = parameters()
        p['scalars'][1] = 0
        with self.assertRaises(ValueError):
            ln.fixed_layernorm(np.ones((1, 4), dtype=np.int64), p)


if __name__ == '__main__':
    unittest.main()
