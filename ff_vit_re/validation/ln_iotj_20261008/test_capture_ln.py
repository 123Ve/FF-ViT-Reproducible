"""Adapter contract tests; integration smoke commands are in task2_report.txt."""
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent


class CaptureTests(unittest.TestCase):
    def module(self, name):
        self.assertTrue((HERE / (name + '.py')).exists(), name + ' implementation missing')
        return importlib.import_module(name)

    def test_spread_selection_and_invalid_counts(self):
        c = self.module('capture_ln')
        self.assertEqual(c.selected_indices(10, 4), [0, 3, 6, 9])
        self.assertEqual(c.selected_indices(10, 1), [5])
        for count in [0, 11, -1]:
            with self.assertRaises(ValueError): c.selected_indices(10, count)

    def test_output_cannot_escape_validation(self):
        c = self.module('capture_ln')
        with self.assertRaises(ValueError): c.checked_output(HERE.parent / 'escape')
        self.assertEqual(c.checked_output(HERE / 'outputs/test'), HERE / 'outputs/test')

    def test_source_binding_rejects_changed_source(self):
        c=self.module('capture_ln')
        self.assertTrue(hasattr(c,'verify_source_binding'),'source binding verification missing')
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            path=Path(tmp)/'source.txt'; path.write_text('frozen')
            records={str(path):c.sha256(path)}
            self.assertEqual(c.verify_source_binding(records)['status'],'PASS')
            path.write_text('changed')
            with self.assertRaises(ValueError): c.verify_source_binding(records)

    def test_real_plant_all_24_parameter_binary_association(self):
        c = self.module('capture_ln')
        root = HERE.parents[1] / 'quantization_final'
        params = c.legacy_parameters(root / 'artifacts')
        result = c.verify_binary(root / 'deployment/weights.bin', params)
        self.assertEqual(result['instances'], 24)
        params[0]['scalars'] = params[0]['scalars'].copy()
        params[0]['scalars'][0] += 1
        with self.assertRaises(ValueError): c.verify_binary(root / 'deployment/weights.bin', params)

    def test_streaming_actual_mismatch_is_failure_and_retained(self):
        r = self.module('run_validation')
        import ln_numeric as ln
        c = self.module('capture_ln')
        p = c.legacy_parameters(HERE.parents[1] / 'quantization_final/artifacts')[0]
        x = np.zeros((2, 192), dtype=np.int64)
        expected = ln.fixed_layernorm(x, p, input_bits=13)['codes']
        actual = expected.copy(); actual[0, 0] = -4 if expected[0, 0] != -4 else 3
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            a = r.InstanceAccumulator('block00.ln1', p, 13, np.ones(192), np.zeros(192), 0.01, 0.1, 1e-6, Path(tmp))
            a.update(x, actual, 'fixture')
            result = a.summary()
            self.assertEqual(result['tokens'], 2)
            self.assertEqual(result['actual_vs_e07']['mismatch_codes'], 1)
            self.assertEqual(result['actual_vs_e07']['status'], 'FAIL')
            self.assertTrue((Path(tmp) / 'mismatch_block00.ln1.npz').exists())

    def test_variance_counterfactual_distinguishes_integer_identity(self):
        r = self.module('run_validation')
        x = np.full((2, 192), 16000, dtype=np.int64); x[1, 0] += 1
        result = r.variance_counterfactual(x)
        self.assertEqual(result['integer_identity_mismatches'], 0)
        self.assertGreater(result['fp32_subtractive_vs_float64_central_varsum']['maxae'], 0)

    def test_source_audit_contains_actual_folding_and_excluded_head(self):
        a = self.module('audit_sources')
        result = a.audit()
        self.assertEqual(result['execution']['instances'], 24)
        self.assertTrue(result['callsites']['attn'])
        self.assertTrue(result['callsites']['mlp'])
        self.assertTrue(result['callsites']['temporal_loop'])
        self.assertEqual(result['head']['included_in_24'], False)
        self.assertTrue(result['sources'])

    def test_global_ranges_keep_ln1_ln2_widths_distinct(self):
        r = self.module('run_validation')
        self.assertTrue(hasattr(r, 'merge_ranges_by_input_width'), 'width-aware merge missing')
        import ln_numeric as ln
        c = self.module('capture_ln')
        params = c.legacy_parameters(HERE.parents[1] / 'quantization_final/artifacts')
        class Row: pass
        rows=[]
        for bits,p in [(13,params[0]),(15,params[1])]:
            row=Row(); row.bits=bits; row.ranges=ln.RangeAccumulator()
            row.ranges.update(ln.fixed_layernorm(np.zeros((2,192),dtype=np.int64),p,input_bits=bits)['diagnostics'])
            rows.append(row)
        result=r.merge_ranges_by_input_width(rows)
        self.assertEqual(result['13']['diff']['bits'],13)
        self.assertEqual(result['15']['diff']['bits'],15)

    def test_host_probe_executes_original_header_on_exported_params(self):
        h = self.module('run_hls_probe')
        c = self.module('capture_ln')
        import ln_numeric as ln
        p = c.legacy_parameters(HERE.parents[1] / 'quantization_final/artifacts')[1]
        x = np.full((4,192), 3000, dtype=np.int64); x[1,0] += 1
        x[2] = 16383; x[3] = np.tile([-16384, 16383], 96)
        expected = ln.fixed_layernorm(x, p, input_bits=15)['codes']
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            result = h.run_case(x, p, 15, expected, Path(tmp))
            self.assertEqual(result['method'], 'HOST_HLS_C_MODEL')
            self.assertEqual(result['mismatch_codes'], 0)

    def test_host_cli_fails_when_actual_runtime_differs_but_core_matches(self):
        self.module('run_hls_probe')
        c=self.module('capture_ln')
        import ln_numeric as ln
        p=c.legacy_parameters(HERE.parents[1]/'quantization_final/artifacts')[0]
        x=np.zeros((4,192),dtype=np.int64)
        core=ln.fixed_layernorm(x,p,input_bits=13)['codes']
        actual=core.copy(); actual[0,0]=-4 if core[0,0]!=-4 else 3
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); fixtures=root/'fixtures'; fixtures.mkdir()
            for i in range(72):
                extra={'actual':actual} if i==0 else {}
                np.savez(fixtures/f'case{i:02d}.npz',x=x,e07=core,bits=13,**p,**extra)
            result=subprocess.run([sys.executable,'-B',str(HERE/'run_hls_probe.py'),'--input',str(root)],
                                  capture_output=True,text=True)
            report=json.loads((root/'hls_host/report.json').read_text())
            self.assertEqual(sum(r['mismatch_codes'] for r in report['results']),0)
            self.assertEqual(sum(r.get('actual_runtime_mismatch_codes',0) for r in report['results']),1)
            self.assertEqual(report['results'][0]['status'],'FAIL')
            self.assertEqual(report['status'],'FAIL')
            self.assertEqual(result.returncode,2)

    def test_failed_recompile_never_reuses_old_executable(self):
        h=self.module('run_hls_probe')
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); source=root/'hls_ln_probe.cpp'
            shutil.copy2(HERE/'hls_ln_probe.cpp',source)
            with patch.object(h,'HERE',root):
                executable=h.compile_probe(); old=executable.read_bytes()
                source.write_text('deliberate invalid C++ source\n')
                with self.assertRaises(RuntimeError): h.compile_probe()
                # Preserve the stale executable explicitly if the compiler removed it.
                executable.write_bytes(old)
                with self.assertRaises(RuntimeError): h.compile_probe()

    def test_tampered_compiler_binary_is_rebuilt_and_hash_bound(self):
        h=self.module('run_hls_probe'); c=self.module('capture_ln')
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); shutil.copy2(HERE/'hls_ln_probe.cpp',root/'hls_ln_probe.cpp')
            with patch.object(h,'HERE',root):
                executable=h.compile_probe(); original=c.sha256(executable)
                executable.write_bytes(b'invalid stale binary')
                self.assertEqual(c.sha256(h.compile_probe()),original)
                stamp=json.loads((root/'hls_host/compile.json').read_text())
                self.assertEqual(stamp['returncode'],0)
                self.assertEqual(stamp['binary_sha256'],original)

    def test_negative_variance_counts_stream_and_cover_synthetic(self):
        r=self.module('run_validation'); c=self.module('capture_ln')
        p=c.legacy_parameters(HERE.parents[1]/'quantization_final/artifacts')[1]
        x=np.zeros((3,192),dtype=np.int64)
        x[0]=np.tile([-16384,16383],96)
        x[1]=2902; x[1,0]+=1  # FP32 subtractive result -128, exact central >0.
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            a=r.InstanceAccumulator('block00.ln2',p,15,np.ones(192),np.zeros(192),.01,.1,1e-6,Path(tmp))
            actual=a.compare(x)['e07']['codes']
            a.update(x,actual,'first'); a.update(x,actual,'second')
            row=a.summary()
            self.assertIn('negative_variance_counts',row)
            counts=row['negative_variance_counts']
            self.assertEqual(counts,{'wide_precast':{'negative_count':0,'total_count':6},
                                    'finite_signed36':{'negative_count':2,'total_count':6},
                                    'unlimited':{'negative_count':0,'total_count':6},
                                    'fp32_subtractive':{'negative_count':2,'total_count':6}})
            boundary=a.boundaries()
            self.assertIn('negative_variance_counts',boundary)
            for key in counts:
                self.assertEqual(boundary['negative_variance_counts'][key]['total_count'],8)
                self.assertEqual(boundary['cases']['extrema']['negative_variance_counts'][key]['total_count'],4)
            global_counts=r.merge_negative_variance_counts([counts,counts])
            self.assertEqual(global_counts['finite_signed36'],{'negative_count':4,'total_count':12})


if __name__ == '__main__': unittest.main()
