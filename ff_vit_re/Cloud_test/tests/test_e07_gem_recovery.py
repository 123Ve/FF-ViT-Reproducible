"""Real lwIP reference-hold regression; only GEM hardware is modeled."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GemRecoveryTests(unittest.TestCase):
    def test_real_lwip_held_tail_recovery_and_dma_ownership_guards(self):
        bsp = ROOT / ('e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/'
                      'standalone_psu_cortexa53_0/bsp/include')
        core = bsp / 'src'
        tests = ROOT / 'e07/tests'
        sources = sorted(core.glob('core/*.c')) + sorted(core.glob('core/ipv4/*.c'))
        self.assertTrue(shutil.which('gcc') and (core / 'core/tcp.c').is_file())
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)
            shutil.copy2(ROOT / 'e07/build/variants/V2_2_FINAL/lwipopts.h',
                         temporary / 'e07_final_lwipopts.h')
            binary = temporary / 'gem-tail'
            command = ['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                       *['-I'+str(p) for p in (tests/'gem_bsp', tests/'real_lwip',
                            temporary, core/'include', tests/'timer_bsp', bsp,
                            ROOT/'e07/firmware/e06_net')],
                       str(tests/'test_gem_tail.c'),
                       str(ROOT/'e07/firmware/e06_net/e07_gem_tx.c'),
                       *map(str,sources), str(core/'netif/ethernet.c'), '-o',str(binary)]
            for optimization in ('-O0','-O2'):
                built = subprocess.run(command+[optimization],capture_output=True,text=True)
                self.assertEqual(built.returncode,0,built.stderr)
                for size in (77,555,1044):
                    for mode in ('stopped','completed'):
                        with self.subTest(optimization=optimization,size=size,mode=mode):
                            ran = subprocess.run([str(binary),str(size),mode],
                                capture_output=True,text=True,timeout=10)
                            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
                            self.assertIn(f'E07_GEM_HELD_TAIL_RECOVERED bytes={size}',ran.stdout)
                            if mode == 'stopped':
                                self.assertIn('GEM_TX_RECOVERY hw=1->1',ran.stdout)
                                self.assertIn('kick=1',ran.stdout)


if __name__ == '__main__':
    unittest.main()
