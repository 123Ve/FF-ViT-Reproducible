"""A failed hardware report must not create a misleading deployable power image."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1]/'make_power_boot_image.py'

class PowerDeploymentGateTests(unittest.TestCase):
    def test_missing_hardware_acceptance_does_not_create_deploy_directory(self):
        if not SCRIPT.is_file():
            self.fail('Power boot assembler not implemented')
        spec = importlib.util.spec_from_file_location('power_boot_assembler', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Override artifact destinations only. Execute the real release checker.
            module.DEPLOY = root/'deploy_power'
            module.SOURCES = {'clock.txt':root/'clock.txt'}
            (root/'clock.txt').write_text('PL_ACTUAL_MHZ=300.215099\n')
            with patch.dict(os.environ, {'E07_CLOCK_FILE':str(root/'clock.txt')}):
                with self.assertRaises(Exception):
                    module.main()
            self.assertFalse(module.DEPLOY.exists())

if __name__ == '__main__':
    unittest.main()
