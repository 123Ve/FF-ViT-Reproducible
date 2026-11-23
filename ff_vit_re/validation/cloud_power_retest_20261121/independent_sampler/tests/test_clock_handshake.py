"""Focused native regression for the reported0/1/0 readiness clock checks."""
import pathlib
import subprocess
import tempfile
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ClockHandshakeTests(unittest.TestCase):
    def compile_run(self,test,sources,profile):
        with tempfile.TemporaryDirectory() as d:
            exe=pathlib.Path(d)/'clock'
            cmd=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                f'-DE07_PROFILE_RAILS={profile}','-I'+str(ROOT/'firmware/common'),
                '-I'+str(ROOT/'firmware/sampler'),str(ROOT/'tests'/test)]
            cmd += [str(ROOT/n) for n in sources]
            built=subprocess.run(cmd+['-o',str(exe)],text=True,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(exe)],text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
    def test_first_observation_is_latched_while_heartbeat_advances(self):
        self.compile_run('test_clock_latch.c',['firmware/common/phase.c',
            'firmware/sampler/sampler.c','firmware/common/sensor.c'],16)
    def test_actual_receive_clock_and_original_rejection_bounds(self):
        for profile in (18,17,16):
            with self.subTest(profile=profile):
                self.compile_run('test_clock_receive.c',['firmware/common/phase.c'],profile)
if __name__=='__main__':unittest.main(verbosity=2)
