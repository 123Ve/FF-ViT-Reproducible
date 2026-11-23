import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/summarize_fps.py'

class FpsSummaryTests(unittest.TestCase):
    def summarize(self, rows):
        if not SCRIPT.is_file():
            self.fail('FPS summarizer not implemented')
        spec = importlib.util.spec_from_file_location('fps_summary', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'FPS_SUM.CSV'
            path.write_text('repeat,frames,ticks,timer_hz,average_ns_per_frame,fps_milli,mismatches\n'+rows)
            return module.summarize(path)

    def test_weighted_rate_and_variance_of_batch_means(self):
        value = self.summarize('0,100,30000000,100000000,3000000,333333,0\n'
                               '1,100,32000000,100000000,3200000,312500,0\n')
        self.assertEqual(value['frames'], 200)
        self.assertEqual(value['repetitions'], 2)
        self.assertAlmostEqual(value['serial_throughput_fps'], 322.5806451612903)
        self.assertAlmostEqual(value['mean_repeat_average_latency_ms'], 3.1)
        self.assertAlmostEqual(value['stddev_repeat_average_latency_ms'], 0.1414213562373095)

    def test_numerical_mismatch_blocks_summary(self):
        with self.assertRaises(ValueError):
            self.summarize('0,100,30000000,100000000,3000000,333333,1\n')

    def test_wrong_stored_units_block_summary(self):
        with self.assertRaises(ValueError):
            self.summarize('0,100,30000000,100000000,3000000,333,0\n')

    def test_duplicate_repetitions_block_summary(self):
        with self.assertRaises(ValueError):
            self.summarize('0,100,30000000,100000000,3000000,333333,0\n'
                           '0,100,30000000,100000000,3000000,333333,0\n')

if __name__ == '__main__':
    unittest.main()
