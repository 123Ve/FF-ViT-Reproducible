"""Execute the same C calculator used by the PS firmware; no mocked math."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FramePerformanceTests(unittest.TestCase):
    def calculate(self, ticks, frames, timer_hz):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory)/'performance_test'
            build = subprocess.run([
                'gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I'+str(ROOT/'power_src'), str(ROOT/'tests/frame_performance_driver.c'),
                str(ROOT/'power_src/frame_performance.c'), '-o', str(exe)
            ], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(exe), str(ticks), str(frames), str(timer_hz)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

    def test_known_board_batch(self):
        self.assertEqual(self.calculate(33695421, 100, 99990005), '3369878,296746')

    def test_known_power_load_window(self):
        self.assertEqual(self.calculate(2999914128, 8905, 99990005), '3369134,296812')

    def test_exact_300_fps(self):
        self.assertEqual(self.calculate(100000000, 300, 100000000), '3333333,300000')

    def test_rejects_zero_denominators(self):
        for args in ((0,100,100000000), (100,0,100000000), (100,100,0)):
            with self.subTest(args=args):
                self.assertEqual(self.calculate(*args), 'INVALID')

    def test_rejects_overflow_instead_of_reporting_bogus_fps(self):
        self.assertEqual(self.calculate(18446744073709551615,100,100000000), 'INVALID')
        self.assertEqual(self.calculate(100,4294967295,4294967295), 'INVALID')

if __name__ == '__main__':
    unittest.main()
