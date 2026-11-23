"""Focused record-complete regressions; all data here are synthetic."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import analyze,collect,profiles
from test_analysis import RawFixture

DIAG16=dict(measurement_profile='diagnostic16',included_mask=229247,included_count=16,
            excluded_rails=[7,15],scope='16-rail diagnostic')

class RecordCompleteTests(unittest.TestCase):
    def test_actual_three_profile_samplers_keep_adc_observation_separate(self):
        for count in (18,17,16):
            with self.subTest(profile=count),tempfile.TemporaryDirectory() as d:
                exe=pathlib.Path(d)/'sampler'
                cmd=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                     f'-DE07_PROFILE_RAILS={count}','-I'+str(ROOT/'firmware/common'),
                     '-I'+str(ROOT/'firmware/sampler')]
                cmd += [str(ROOT/n) for n in ('tests/test_record_complete.c',
                        'firmware/common/sensor.c','firmware/sampler/sampler.c','firmware/common/phase.c')]
                p=subprocess.run(cmd+['-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                p=subprocess.run([str(exe)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def fixture(self,d):
        f=RawFixture(pathlib.Path(d)/'phase')
        f.phase.update(DIAG16)
        for s in [f.end,f.start,f.phase['arm_status']]+f.warm:
            s.update(DIAG16,sampler_profile_rails=16,conversion_ready_mask=229247,
                     observed_mask=262143,excluded_negative_samples=0,included_negative_samples=0)
        f.end['excluded_negative_samples']=66
        f.events=[e for e in f.events if e['type']!=5 or e['request_id']<=200]
        f.end['completed_full']=200
        for r in f.rails:
            r.update(power_uW=2000000,power=64 if r['rail']==10 else 160)
            if r['rail'] in (7,15):r.update(flags=258,shunt=65534,current=65534,power=0,power_uW=-(2**63))
        return f

    def test_sixteen_scope_sums_only_included_rails_and_preserves_raw(self):
        try:policy=profiles.metadata('diagnostic16')
        except ValueError:self.fail('diagnostic16 is missing')
        self.assertEqual(policy,DIAG16)
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);f.save()
            result=analyze.analyze_phase(f.directory,True,profile='diagnostic16')
            self.assertTrue(result['valid'],result['invalid_reasons'])
            self.assertEqual((result['energy_J'],result['mean_W'],result['board_completed_fps'],
                              result['energy_mJ_per_completed_frame']),(64.,32.,100.,320.))
            for rail in (7,15):self.assertIsNone(result['rails'][rail]['energy_J'])
            with self.assertRaises(collect.IdentityError):collect.assess_phase(f.directory,'diagnostic17')

    def test_included_negative_completes_capture_but_cannot_be_power_pass(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d)
            for r in f.rails:
                if r['rail']==6:r.update(flags=258,shunt=65534,current=65534,power=0,power_uW=-(2**63))
            f.end['included_negative_samples']=33;f.save()
            evidence=collect.assess_phase(f.directory,'diagnostic16')
            self.assertTrue(evidence['capture_valid'])
            self.assertFalse(evidence['power_quality_valid'])
            result=analyze.analyze_phase(f.directory,True,profile='diagnostic16')
            self.assertFalse(result['valid']);self.assertTrue(result['capture_valid'])
            self.assertIsNone(result['energy_J']);self.assertIsNone(result['mean_W'])
            self.assertEqual(result['board_completed_fps'],100.)
            self.assertEqual(result['rails'][6]['observed_CVRF'],33)
            self.assertFalse(any('CVRF' in why for why in result['rails'][6]['invalid_reasons']))
            f.rails[15]['flags']|=4;f.save()
            with self.assertRaises(collect.GateError):collect.assess_phase(f.directory,'diagnostic16')

    def test_readiness_and_cli_select_explicit_sixteen_scope(self):
        from test_analysis import fixture_status
        status=fixture_status(**DIAG16,sampler_profile_rails=16,conversion_ready_mask=0,
                              included_negative_samples=2)
        collect.validate_status(status,profile='diagnostic16')
        args=collect.parser().parse_args(['--check-only','--diagnostic16'])
        self.assertTrue(args.diagnostic16)
        with self.assertRaises(collect.IdentityError):collect.validate_status(status,profile='strict18')

if __name__=='__main__':unittest.main(verbosity=2)
