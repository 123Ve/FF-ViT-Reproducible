"""Compile actual portable firmware; register I/O is the narrow hardware double."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import importlib.util
import re
import shutil
import sys

HERE=Path(__file__).resolve().parents[1]
class FirmwareTests(unittest.TestCase):
    def test_shallow_extraction_imports_pure_validator_and_rebuild_explains_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='e07 shallow import ',dir='/tmp') as d:
            script=Path(d)/'build_firmware.py';shutil.copy2(HERE/'build_firmware.py',script)
            code=('import importlib.util,sys; s=importlib.util.spec_from_file_location("candidate",sys.argv[1]); '
                  'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                  'assert m.validate_segments({"service":[(1048576,2097152)],"sampler":[(536870912,537919488)]})')
            result=subprocess.run([sys.executable,'-S','-c',code,str(script)],cwd='/',text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([sys.executable,'-S',str(script)],cwd='/',text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('repository layout',result.stderr)
    def test_target_seqlock_writer_orders_odd_before_payload(self):
        """Missing post-odd ordering permits an old-even/torn-payload read on Arm."""
        compiler=Path('/opt/vivado/2025.1/Vitis/gnu/aarch64/lin/aarch64-none/bin/aarch64-none-elf-gcc')
        with tempfile.TemporaryDirectory(prefix='independent-arm-ordering-') as d:
            obj=Path(d)/'phase.o'
            command=[str(compiler),'-std=c11','-O2','-Wall','-Wextra','-Werror',
                     '-I'+str(HERE/'firmware/common'),'-c',str(HERE/'firmware/common/phase.c'),'-o',str(obj)]
            built=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            decoded=subprocess.run([str(compiler.parent/'aarch64-none-elf-objdump'),'-d',str(obj)],
                                   text=True,capture_output=True,check=True).stdout
            for name in ('m_status_publish','m_latest_publish'):
                with self.subTest(writer=name):
                    body=decoded.split('<'+name+'>:',1)[1].split('\n\n',1)[0]
                    instructions=re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\S+)\s*(.*)$',body,re.M)
                    odd=next(i for i,(op,arg) in enumerate(instructions) if op=='stlr')
                    payload=next(i for i,(op,arg) in enumerate(instructions[odd+1:],odd+1)
                                 if op in ('strb','sturb'))
                    self.assertTrue(any(op=='dmb' and arg.strip() in ('ish','ishst','sy','st')
                                        for op,arg in instructions[odd+1:payload]),
                                    name+' lacks writer ordering after odd publication:\n'+body)
                    self.assertTrue(any(op=='stlr' for op,arg in instructions[payload+1:]),
                                    name+' lacks final release publication')
    def test_link_regions_reject_overlap_shared_and_wrong_cpu_region(self):
        spec=importlib.util.spec_from_file_location('independent_build',HERE/'build_firmware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        good={'service':[(0x100000,0x200000)],'sampler':[(0x20000000,0x20100000)]}
        self.assertTrue(module.validate_segments(good))
        for bad in [dict(good,service=[(0x100000,0x31000000)]),
                    dict(good,sampler=[(0x100000,0x200000)]),
                    dict(good,sampler=[(0x30000000,0x30001000)])]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):module.validate_segments(bad)
    def compile_run(self,name,sources,flags=(),arguments=()):
        with tempfile.TemporaryDirectory(prefix='independent-firmware-') as d:
            command=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                '-I'+str(HERE/'firmware/common'),*flags,
                *[str(HERE/s) for s in sources],'-o',str(Path(d)/name)]
            built=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            result=subprocess.run([str(Path(d)/name),*arguments],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout.strip())
    def test_first_conversion_observation_precedes_valid_payload_and_fault_freeze(self):
        for case in ('pending','order','negative','sampler','timeout','pending-negative','late-first','late-negative','backward'):
            with self.subTest(case=case):
                self.compile_run('first-conversion',['tests/test_first_conversion.c',
                    'firmware/common/sensor.c','firmware/sampler/sampler.c','firmware/common/phase.c'],
                    ['-I'+str(HERE/'firmware/sampler')],[case])
    def test_compiled_profile_first_negative_held_and_first_fault(self):
        for rails in (18,17):
            with self.subTest(rails=rails):
                self.compile_run('profile',['tests/test_first_conversion.c','firmware/common/sensor.c',
                    'firmware/sampler/sampler.c','firmware/common/phase.c'],
                    ['-I'+str(HERE/'firmware/sampler'),f'-DE07_PROFILE_RAILS={rails}'],['profile'])
    def test_diag_other_rail_combined_errors_and_late_first_refused(self):
        for case in ('profile-i2c','profile-other','profile-stale','timeout','late-negative'):
            with self.subTest(case=case):
                self.compile_run('diagnostic',['tests/test_first_conversion.c','firmware/common/sensor.c',
                    'firmware/sampler/sampler.c','firmware/common/phase.c'],
                    ['-I'+str(HERE/'firmware/sampler'),'-DE07_PROFILE_RAILS=17'],[case])
    def test_sensor_configuration_calibration_raw_and_invalid_samples(self):
        self.compile_run('sensor',['tests/test_sensor.c','firmware/common/sensor.c'])
    def test_publication_phase_ack_request_ids_and_faults(self):
        self.compile_run('phase',['tests/test_phase.c','firmware/common/phase.c'])
    def test_sampler_guard_records_temperature_and_faults(self):
        self.compile_run('sampler',['tests/test_sampler.c','firmware/sampler/sampler.c',
            'firmware/common/sensor.c','firmware/common/phase.c'],
            ['-I'+str(HERE/'firmware/sampler')])
    def test_network_controls_replay_delayed_ack_and_export(self):
        self.compile_run('network',['tests/test_network.c','firmware/service/e06_network.c',
            'tests/fake_lwip/fake_lwip.c','firmware/common/fvit_protocol.c',
            'firmware/common/phase.c','firmware/common/board.c'],
            ['-DE06_HOST_TEST','-DE06_FIRMWARE_SHA256="test-candidate"',
             '-I'+str(HERE/'firmware/service'),'-I'+str(HERE/'tests/fake_lwip')])
    def test_copied_inference_rejects_sizes_dma_timeout_and_output_error(self):
        self.compile_run('inference',['tests/test_inference.c','firmware/service/e06_inference.c',
            'tests/fake_bsp/e06_fake_bsp.c'],['-DE06_HOST_TEST',
            '-I'+str(HERE),'-I'+str(HERE/'tests'),'-I'+str(HERE/'firmware/service')])
    def test_i2c_actual_register_transfer_is_bounded_and_checks_errors(self):
        self.compile_run('i2c',['tests/test_i2c.c','firmware/sampler/bounded_i2c.c'],
            ['-I'+str(HERE/'firmware/sampler')])

if __name__=='__main__':unittest.main(verbosity=2)
