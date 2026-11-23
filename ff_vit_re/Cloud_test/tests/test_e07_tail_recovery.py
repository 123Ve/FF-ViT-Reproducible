"""Catch the shipped no-tick BSP regression using the production platform code."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.dashboard.app import create_app

ROOT = Path(__file__).resolve().parents[1]


class E07TailRecoveryTests(unittest.TestCase):
    def test_v25_package_binds_sd_image_and_current_collector(self):
        import hashlib
        import json
        import zipfile
        try:
            from Cloud_test.tools.package_e07_v25 import package
        except ImportError as error:
            self.fail(f'isolated V2.5 package is unavailable: {error}')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'release.zip'
            package(ROOT, output)
            with zipfile.ZipFile(output) as z:
                prefix = 'E07_Cloud_GUI_Win11_Source_V2_5/'
                records = json.loads(z.read(prefix + 'SHA256SUMS.json'))
                self.assertEqual(len(records), len(z.namelist())-1)
                for record in records:
                    data = z.read(prefix + record['path'])
                    self.assertEqual(len(data), record['bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])
                manifest = json.loads(z.read(prefix + 'Cloud_test/e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json'))
                self.assertEqual(hashlib.sha256(z.read(prefix+'SD_CARD/BOOT.BIN')).hexdigest(),
                                 manifest['artifacts']['boot']['sha256'])
                self.assertEqual(manifest['physical_status'], 'NOT_RUN')
                self.assertEqual(manifest['release'], 'V2_5')
                self.assertNotIn(prefix+'Cloud_test/e07/boot/BOOT_E07_NET_V2_2_FINAL.manifest.json', z.namelist())
            with self.assertRaises(FileExistsError):
                package(ROOT, output)

    def test_v25_collector_default_accepts_new_firmware_and_rejects_old_identity(self):
        import json
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.cloud.board_server import _IdentityPolicy
        from Cloud_test.iot_eval.messages import Hello
        captured = []
        def capture(args, report, directory, store):
            captured.append(args.boot_manifest)
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, 'physical', capture):
            runner.main(['--output-root', folder])
        policy = _IdentityPolicy(captured[0])
        current = json.loads((ROOT / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json').read_text())
        identity = current['firmware_identity']
        hashes = identity['canonical_payload']['inputs']['copied_vendor_inputs']
        hello = Hello('E07_PHYSICAL', 'E07', identity['advertised_sha256'],
                      {k: hashes[k]['sha256'] for k in ('bitstream','weights','input','output','xsa')},
                      '192.168.10.2', 5001)
        try:
            policy.validate(hello)
        except ValueError as error:
            self.fail(f'collector rejects the new bundled firmware: {error}')
        old = Hello('E07_PHYSICAL', 'E07',
                    'e12e89bc424680ff2a1582129ffd32e7cb530b1d9cc452da8473d5a40603b1f7',
                    hello.artifact_hashes, '192.168.10.2', 5001)
        with self.assertRaisesRegex(ValueError, 'firmware SHA256'):
            policy.validate(old)

    def test_windows_freeze_includes_v25_identity_manifest(self):
        captured = {}
        class Analysis:
            def __init__(self, scripts, **kwargs):
                captured.update(kwargs)
                self.pure = self.scripts = self.binaries = self.datas = []
        spec = ROOT / 'windows/E07_Cloud_GUI.spec'
        context = dict(SPECPATH=str(spec.parent), Analysis=Analysis,
                       PYZ=lambda *a, **k: None, EXE=lambda *a, **k: None,
                       COLLECT=lambda *a, **k: None)
        exec(compile(spec.read_text(), str(spec), 'exec'), context)
        packaged = {Path(source).name for source, target in captured['datas']}
        self.assertIn('BOOT_E07_NET_V2_5_FINAL.manifest.json', packaged)

    def test_new_release_paths_do_not_replace_v22(self):
        from Cloud_test.build_scripts.rebuild_e07_net import release_paths
        root = Path('/tmp/e07-release-test')
        original = release_paths(root, 'FINAL')
        try:
            candidate = release_paths(root, 'FINAL', release='V2_5')
        except TypeError as error:
            self.fail(f'new firmware cannot be isolated from V2.2: {error}')
        self.assertEqual(candidate[0].name, 'BOOT_E07_NET_V2_5_FINAL.BIN')
        self.assertEqual(candidate[1].name, 'V2_5_FINAL')
        self.assertNotEqual(original, candidate)

    def test_real_network_keeps_servicing_queued_tail_before_retransmission_timer(self):
        compiler = shutil.which('gcc')
        bsp = ROOT / ('e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/'
                      'standalone_psu_cortexa53_0/bsp/include')
        source_root = bsp / 'src'
        self.assertTrue(compiler and (source_root / 'core/tcp.c').is_file())
        core = sorted(source_root.glob('core/*.c')) + sorted(source_root.glob('core/ipv4/*.c'))
        tests = ROOT / 'e07/tests'
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)
            shutil.copy2(ROOT / 'e07/build/variants/V2_2_FINAL/lwipopts.h',
                         temporary / 'e07_final_lwipopts.h')
            binary = temporary / 'network-real-lwip'
            command = [compiler, '-std=c11', '-DE06_HOST_TEST',
                '-DE06_FIRMWARE_SHA256="' + 'a'*64 + '"',
                *['-I' + str(p) for p in (tests / 'real_network', tests / 'real_lwip',
                    temporary, source_root / 'include', tests / 'timer_bsp', bsp,
                    ROOT / 'e07/firmware/e06_net', ROOT / 'e07/firmware/common')],
                str(tests / 'test_network_real_lwip.c'),
                str(ROOT / 'e07/firmware/e06_net/e06_network.c'),
                str(ROOT / 'e07/firmware/common/fvit_protocol.c'),
                *map(str, core), str(source_root / 'netif/ethernet.c'), '-o', str(binary)]
            for optimization in ('-O0', '-O2'):
                built = subprocess.run(command + [optimization], capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                self.assertIn('E07_REAL_NETWORK_TAIL_DRAIN_OK frames=100', ran.stdout)

    def test_v22_firmware_paths_are_preserved_and_its_image_is_verified(self):
        import json
        from Cloud_test.build_scripts.rebuild_e07_net import release_paths
        from Cloud_test.tools.package_e07_cloud import verify_release_inputs
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image, variant = release_paths(root / 'e07', 'FINAL')
            self.assertEqual(image.name, 'BOOT_E07_NET_V2_2_FINAL.BIN')
            self.assertEqual(variant.name, 'V2_2_FINAL')
            image.parent.mkdir(parents=True)
            image.write_bytes(b'wrong image')
            image.with_suffix('.manifest.json').write_text(json.dumps({
                'artifacts': {'boot': {'bytes': 1, 'sha256': 'a' * 64}}}))
            with self.assertRaisesRegex(ValueError, 'BOOT.*mismatch'):
                verify_release_inputs(root, ('FINAL',), release='V2_2')

    def test_dropped_1044_byte_tail_is_recovered_by_production_timer_and_real_lwip(self):
        compiler = shutil.which('gcc')
        bsp = ROOT / ('e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/'
                      'standalone_psu_cortexa53_0/bsp/include')
        sources_root = bsp / 'src'
        if compiler is None or not (sources_root / 'core/tcp.c').is_file():
            self.skipTest('Real lwIP regression requires the generated Vitis BSP and gcc')
        sources = (sorted(sources_root.glob('core/*.c'))
                   + sorted(sources_root.glob('core/ipv4/*.c'))
                   + [sources_root / 'netif/ethernet.c'])
        tests = ROOT / 'e07/tests'
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)
            shutil.copy2(ROOT / 'e07/build/variants/V2_2_FINAL/lwipopts.h',
                         temporary / 'e07_final_lwipopts.h')
            binary = temporary / 'real-lwip-tail'
            command = [compiler, '-std=c11', '-DCOUNTS_PER_SECOND=99990005ull',
                '-I' + str(tests / 'real_lwip'), '-I' + str(temporary),
                '-I' + str(sources_root / 'include'), '-I' + str(tests / 'timer_bsp'),
                '-I' + str(bsp), '-I' + str(ROOT / 'e07/firmware/e06_net'),
                str(ROOT / 'e07/firmware/e06_net/platform.c'), str(tests / 'test_tail_rto.c'),
                *map(str, sources), '-o', str(binary)]
            for optimization in ('-O0', '-O2'):
                built = subprocess.run(command + [optimization], capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertIn('E07_REAL_LWIP_TAIL_RECOVERED bytes=1044 attempts=2', ran.stdout)

    def test_tcp_timers_advance_without_tick_interrupts(self):
        compiler = shutil.which('gcc')
        if compiler is None:
            self.skipTest('C compiler is unavailable')
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'timer-test'
            tests = ROOT / 'e07/tests'
            command = [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I' + str(tests / 'timer_unit'), '-I' + str(tests / 'timer_bsp'),
                '-I' + str(ROOT / 'e07/firmware/e06_net'),
                str(ROOT / 'e07/firmware/e06_net/platform.c'), str(tests / 'test_timer.c'),
                '-o', str(binary)]
            for optimization in ('-O0', '-O2'):
                built = subprocess.run(command + [optimization], capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertIn('E07_MONOTONIC_TCP_TIMER_OK', ran.stdout)

    def test_unmeasured_accuracy_card_is_absent_from_rendered_dashboard(self):
        with tempfile.TemporaryDirectory() as folder:
            client = create_app(SessionStore(Path(folder) / 'sessions')).test_client()
            response = client.get('/')
            html = response.get_data(as_text=True)
            self.assertNotIn('PlantVillage Top-1', html)
            self.assertNotIn('id="accuracy"', html)
            self.assertIn('id="power"', html)
            self.assertIn('id="measurement-table"', html)

    def test_dashboard_renders_detail_without_removed_accuracy_nodes(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node.js is unavailable')
        with tempfile.TemporaryDirectory() as folder:
            client = create_app(SessionStore(Path(folder) / 'sessions')).test_client()
            html = client.get('/').get_data(as_text=True)
            ids = set(re.findall(r'id="([^"]+)"', html)) - {'accuracy', 'accuracy-reason'}
            script = (ROOT / 'dashboard/static/dashboard.js').read_text()
            # Execute the real renderer. Only the browser DOM/Plotly boundary is doubled.
            import json
            harness = '''
const vm = require('vm');
const elements = new Map(IDS.map(id => [id, {
  textContent: '', classList: {add(){}, remove(){}}, replaceChildren(){}, append(){}
}]));
const context = {AbortController, console, fetch: () => new Promise(() => {}),
  document: {getElementById: id => elements.get(id) || null,
    createElement: () => ({append(){}, textContent:''}),
    createDocumentFragment: () => ({append(){}})},
  window: {setTimeout(){}, clearTimeout(){}, setInterval(){}},
  Plotly: {react(){}}};
vm.createContext(context);
vm.runInContext(SCRIPT, context);
vm.runInContext('renderDetail({artifact_hashes:{}, recent_errors:[]})', context);
console.log('E07_DASHBOARD_WITHOUT_ACCURACY_OK');
'''.replace('IDS', json.dumps(sorted(ids))).replace('SCRIPT', json.dumps(script))
            ran = subprocess.run([node, '-e', harness], capture_output=True, text=True, timeout=10)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn('E07_DASHBOARD_WITHOUT_ACCURACY_OK', ran.stdout)
