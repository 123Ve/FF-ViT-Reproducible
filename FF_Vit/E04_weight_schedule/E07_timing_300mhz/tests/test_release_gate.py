"""Catch releasing a failing build, incomplete regression or sub-300-MHz clock."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_release.py'

class ReleaseGateTest(unittest.TestCase):
    def run_gate(self, timing='0.015 0.000 0 100 0.010 0.000 0 100 0.100 0.000 0 100',
                 route_errors=0, drc='Checks found: 0', frames=(0, 1, 2), mhz=300,
                 period=3.333, no_clock=0, unconstrained=0, clock_extra='', clock_prefix=''):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'timing.rpt').write_text(
                f'1. checking no_clock ({no_clock})\n'
                f'4. checking unconstrained_internal_endpoints ({unconstrained})\n'
                'WNS(ns) TNS(ns) TNS Failing Endpoints\n--------\n'+timing+'\n')
            (root/'route.rpt').write_text(
                '# of routable nets........ : 100 :\n# of fully routed nets... : 100 :\n'
                f'# of nets with routing errors.... : {route_errors} :\n')
            (root/'drc.rpt').write_text('Report DRC\n'+drc+'\n')
            (root/'clock.txt').write_text(clock_prefix+f'PL_ACTUAL_MHZ={mhz}\nPL_PERIOD_NS={period}\n'+clock_extra)
            (root/'csim.log').write_text(''.join(
                f'E04 frame={i} layers=12 logits=1000 cumulative_mismatch=0\n' for i in frames))
            return subprocess.run([sys.executable, str(SCRIPT), str(root)],
                                  text=True, capture_output=True)

    def test_accepts_complete_passing_build(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('RELEASE_APPROVED', result.stdout)

    def test_rejects_setup_failure(self):
        self.assertNotEqual(self.run_gate(timing='-0.010 -1.000 1 100 0.01 0 0 100 0.1 0 0 100').returncode, 0)

    def test_rejects_hold_failure(self):
        self.assertNotEqual(self.run_gate(timing='0.01 0 0 100 -0.01 -1 1 100 0.1 0 0 100').returncode, 0)

    def test_rejects_pulse_failure(self):
        self.assertNotEqual(self.run_gate(timing='0.01 0 0 100 0.01 0 0 100 -0.1 -1 1 100').returncode, 0)

    def test_rejects_routing_errors(self):
        self.assertNotEqual(self.run_gate(route_errors=1).returncode, 0)

    def test_rejects_drc_error(self):
        self.assertNotEqual(self.run_gate(drc='| NSTD-1 | Error | Unspecified | 1 |').returncode, 0)

    def test_rejects_missing_regression_frame(self):
        self.assertNotEqual(self.run_gate(frames=(0,1)).returncode, 0)

    def test_rejects_underclock(self):
        self.assertNotEqual(self.run_gate(mhz=250).returncode, 0)

    def test_rejects_unclocked_registers(self):
        self.assertNotEqual(self.run_gate(no_clock=5).returncode, 0)

    def test_rejects_unconstrained_internal_endpoints(self):
        self.assertNotEqual(self.run_gate(unconstrained=671).returncode, 0)

    def test_rejects_timing_constraint_slower_than_hardware(self):
        self.assertNotEqual(self.run_gate(mhz=316.635010, period=3.333).returncode, 0)

    MMCM = ('CLOCK_SOURCE=MMCM\nPS_PL_ACTUAL_MHZ=249.975021\n'
            'MMCM_MULT=93.625\nMMCM_DIVCLK=24\nMMCM_OUT_DIV=3.25\n'
            'IMPLEMENTED_CLKFBOUT_MULT_F=93.625\nIMPLEMENTED_DIVCLK_DIVIDE=24\n'
            'IMPLEMENTED_CLKOUT0_DIVIDE_F=3.25\n'
            'RESET_LOCK_VERIFIED=1\nCORE_CLOCK_CONSUMERS_VERIFIED=1\n')

    def test_accepts_generated_clock_with_sub300_ps_input(self):
        result = self.run_gate(mhz=300.050145399, period=3.332776256, clock_extra=self.MMCM)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_accepts_core_clock_when_ps_input_is_listed_first(self):
        result = self.run_gate(mhz=300.050145399, period=3.332776256,
                               clock_prefix=self.MMCM)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_sub300_core_despite_faster_ps_input(self):
        result = self.run_gate(mhz=250, period=2.85,
                               clock_prefix='PS_PL_ACTUAL_MHZ=350\n')
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_core_clock_despite_ps_frequency(self):
        result = self.run_gate(mhz='', period=3.331,
                               clock_prefix='PS_PL_ACTUAL_MHZ=300.215099\n')
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_mmcm_parameters(self):
        result = self.run_gate(clock_extra='CLOCK_SOURCE=MMCM\n')
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_output_frequency_inconsistent_with_mmcm(self):
        result = self.run_gate(mhz=301, period=3.322259, clock_extra=self.MMCM)
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_unverified_lock_reset(self):
        extra = self.MMCM.replace('RESET_LOCK_VERIFIED=1', 'RESET_LOCK_VERIFIED=0')
        self.assertNotEqual(self.run_gate(mhz=300.050145399, period=3.332776256,
                                         clock_extra=extra).returncode, 0)

    def test_rejects_unverified_core_clock_sinks(self):
        extra = self.MMCM.replace('CORE_CLOCK_CONSUMERS_VERIFIED=1', 'CORE_CLOCK_CONSUMERS_VERIFIED=0')
        self.assertNotEqual(self.run_gate(mhz=300.050145399, period=3.332776256,
                                         clock_extra=extra).returncode, 0)

    def test_rejects_unknown_clock_source(self):
        self.assertNotEqual(self.run_gate(clock_extra='CLOCK_SOURCE=UNKNOWN\n').returncode, 0)

    def test_rejects_missing_implemented_mmcm_identity(self):
        extra = self.MMCM.replace('IMPLEMENTED_DIVCLK_DIVIDE=24\n', '')
        self.assertNotEqual(self.run_gate(mhz=300.050145399, period=3.332776256,
                                         clock_extra=extra).returncode, 0)

    def test_rejects_implemented_mmcm_mismatch(self):
        extra = self.MMCM.replace('IMPLEMENTED_DIVCLK_DIVIDE=24', 'IMPLEMENTED_DIVCLK_DIVIDE=25')
        self.assertNotEqual(self.run_gate(mhz=300.050145399, period=3.332776256,
                                         clock_extra=extra).returncode, 0)

if __name__ == '__main__':
    unittest.main()
