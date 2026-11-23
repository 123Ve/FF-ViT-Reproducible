"""Diagnostic capture may proceed without claiming thermal steady state."""
import pathlib
import sys
import tempfile
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import collect,analyze
from test_analysis import RawFixture,fixture_status
import test_record_complete as record_fixture
DIAG16=record_fixture.DIAG16

class ThermalCaptureTests(unittest.TestCase):
    def ramp(self):
        return [fixture_status(now_ticks=(40+i)*8000,sampler_heartbeat=(40+i)*8000-1,
            temperature_tick=(40+i)*8000,temperature_mC=26800+100*i) for i in range(31)]

    def test_diagnostic_waits_thirty_seconds_but_does_not_require_steady_state(self):
        samples=self.ramp()
        self.assertFalse(collect.thermal_stable(samples))
        self.assertFalse(collect.warmup_ready('diagnostic16',29.9,samples))
        self.assertTrue(collect.warmup_ready('diagnostic16',30.,samples))
        self.assertTrue(collect.warmup_ready('diagnostic17',30.,samples))
        self.assertFalse(collect.warmup_ready('strict18',600.,samples))
        self.assertFalse(collect.warmup_ready('diagnostic16',30.,samples[-1:]))

    def test_sensor_temperature_health_is_still_required(self):
        for field,value in [('temperature_valid',0),('temperature_mC',151000),
                            ('temperature_mC',-56000),('temperature_tick',0)]:
            with self.subTest(field=field,value=value):
                s=fixture_status(**DIAG16,sampler_profile_rails=16)
                s[field]=value
                with self.assertRaises(collect.GateError):collect.validate_status(s,profile='diagnostic16')

    def test_unsteady_diagnostic_keeps_window_average_and_reports_qualification(self):
        with tempfile.TemporaryDirectory() as d:
            f=record_fixture.RecordCompleteTests().fixture(d)
            for i,s in enumerate(f.warm):s['temperature_mC']=26800+100*i
            f.phase['warmup_elapsed_seconds']=30.;f.save()
            evidence=collect.assess_phase(f.directory,'diagnostic16')
            self.assertTrue(evidence['capture_valid'])
            self.assertFalse(evidence['warmup_thermal_stable'])
            result=analyze.analyze_phase(f.directory,True,profile='diagnostic16')
            self.assertTrue(result['valid'],result['invalid_reasons'])
            self.assertEqual((result['energy_J'],result['mean_W']),(64.,32.))
            self.assertFalse(result['warmup_thermal_stable'])
            self.assertEqual(result['thermal_qualification'],'not established; diagnostic time-window average')
            f.warm[-1]['temperature_mC']=151000;f.save()
            with self.assertRaises(collect.GateError):collect.assess_phase(f.directory,'diagnostic16')

    def test_strict_eighteen_still_rejects_unsteady_warmup(self):
        with tempfile.TemporaryDirectory() as d:
            f=RawFixture(pathlib.Path(d)/'strict')
            for i,s in enumerate(f.warm):s['temperature_mC']=26800+100*i
            f.save()
            with self.assertRaises(collect.GateError):collect.assess_phase(f.directory,'strict18')

if __name__=='__main__':unittest.main(verbosity=2)
