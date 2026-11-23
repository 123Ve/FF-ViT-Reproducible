"""Publication regression tests: weighting, coverage, units and evidence status."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class ExportTests(unittest.TestCase):
    def api(self):
        spec = importlib.util.find_spec('export_results')
        self.assertIsNotNone(spec, 'publication exporter is missing')
        import export_results
        return export_results

    def test_element_weighted_metrics_keep_raw_fraction(self):
        api = self.api()
        a = dict(count=2, real_mae=1, real_rmse=1, real_maxae=1,
                 code_mae=1, code_rmse=1, code_maxae=1,
                 exact_code_agreement=0, within_1_lsb=1)
        b = dict(count=6, real_mae=3, real_rmse=3, real_maxae=3,
                 code_mae=3, code_rmse=3, code_maxae=3,
                 exact_code_agreement=1, within_1_lsb=0)
        actual = api.merge_metrics([a, b])
        self.assertEqual(actual['count'], 8)
        self.assertEqual(actual['code_mae'], 2.5)
        self.assertAlmostEqual(actual['code_rmse'], 7 ** .5)
        self.assertEqual(actual['exact_code_agreement'], .75)
        self.assertEqual(actual['within_1_lsb'], .25)
        self.assertEqual(actual['real_maxae'], 3)

    def test_incomplete_capture_is_rejected(self):
        api = self.api()
        summary = json.loads((HERE/'outputs/smoke_fixed/plantvillage/summary.json').read_text())
        summary['instances'][0]['tokens'] -= 1
        with self.assertRaisesRegex(ValueError, 'coverage'):
            api.validate_summary(summary)

    def test_smoke_export_preserves_denominators_and_units(self):
        api = self.api()
        (HERE/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=HERE/'tmp') as temp:
            out = Path(temp)/'paper'
            result = api.export_all(HERE/'outputs/smoke_fixed', out, make_plots=False)
            with (out/'per_instance.csv').open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 72)
            self.assertEqual(rows[0]['images'], '2')
            self.assertEqual(rows[0]['tokens'], '392')
            self.assertEqual(rows[0]['elements'], '75264')
            self.assertTrue(0 <= float(rows[0]['e07_vs_fp32_continuous.exact_code_agreement']) <= 1)
            with (out/'negative_variance_counts.csv').open() as f:
                negatives = list(csv.DictReader(f))
            selected = [r for r in negatives if r['dataset']=='plantvillage' and r['scope']=='SAMPLED' and r['instance']=='GLOBAL']
            self.assertEqual(len(selected), 4)
            self.assertEqual({r['total_count'] for r in selected}, {'9408'})
            all_selected = [r for r in negatives if r['dataset']=='ALL' and r['scope']=='SAMPLED']
            self.assertEqual(len(all_selected), 4)
            self.assertEqual({r['total_count'] for r in all_selected}, {'28224'})
            self.assertEqual(result['all_datasets']['e07_vs_fp32_continuous']['count'], 5419008)
            self.assertIn('heterogeneous', result['real_units'])
            self.assertEqual(result['status_matrix']['plantvillage']['VITIS_CSIM'], 'NOT_MEASURED')
            self.assertEqual(result['status_matrix']['plantvillage']['HOST_HLS_C_MODEL'], 'PASS')
            with (out/'mathematical_bounds.csv').open() as f:
                self.assertEqual(len(list(csv.DictReader(f))), 72)

    def test_global_negative_counts_cannot_disagree_with_instances(self):
        api = self.api()
        s = json.loads((HERE/'outputs/smoke_fixed/plantvillage/summary.json').read_text())
        s['global_negative_variance_counts']['finite_signed36']['negative_count'] = 1
        with self.assertRaisesRegex(ValueError, 'negative variance.*coverage'):
            api.validate_summary(s)

    def test_plots_are_exported_as_standalone_pdf_and_png(self):
        api = self.api()
        with tempfile.TemporaryDirectory(dir=HERE/'tmp') as temp:
            out = Path(temp)/'paper'
            api.export_all(HERE/'outputs/smoke_fixed', out, make_plots=True)
            self.assertTrue((out/'plots/blockwise_error.pdf').read_bytes().startswith(b'%PDF'))
            self.assertTrue((out/'plots/blockwise_error.png').read_bytes().startswith(b'\x89PNG'))

    def test_failure_is_exported_without_upgrade(self):
        api = self.api()
        s = json.loads((HERE/'outputs/smoke_fixed/plantvillage/summary.json').read_text())
        s['equivalence_status'] = 'FAIL'
        self.assertEqual(api.status_row(s, None)['software_equivalence'], 'FAIL')
        self.assertEqual(api.status_row(s, None)['HOST_HLS_C_MODEL'], 'NOT_MEASURED')
        self.assertEqual(api.status_row(s, {'status':'FAIL'})['HOST_HLS_C_MODEL'], 'FAIL')

    def test_rerun_plan_contains_sequential_validation_probes_and_export(self):
        self.assertIsNotNone(importlib.util.find_spec('rerun_publication'), 'one-command rerun helper missing')
        import rerun_publication
        commands = rerun_publication.commands()
        self.assertEqual(len(commands), 5)
        self.assertEqual(commands[0][3:], ['--dataset','all','--samples','128','--output','outputs/final128'])
        self.assertEqual([c[-1] for c in commands[1:4]],
                         ['outputs/final128/plantvillage','outputs/final128/nwpu','outputs/final128/imagenet'])
        self.assertEqual(Path(commands[4][2]).name, 'export_results.py')


if __name__ == '__main__':
    unittest.main()
