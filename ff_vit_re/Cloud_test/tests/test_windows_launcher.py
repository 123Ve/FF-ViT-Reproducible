from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import urlopen
import zipfile


CLOUD_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CLOUD_ROOT.parent
MANIFEST = CLOUD_ROOT / "boot/BOOT_E06_NET.manifest.json"


class WindowsLauncherRuntimeTests(unittest.TestCase):
    def test_frozen_paths_keep_resources_in_bundle_and_sessions_beside_exe(self):
        from Cloud_test.windows_launcher import resolve_runtime_paths

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "release/E06_Cloud_GUI.exe"
            bundle = root / "_MEI123"
            paths = resolve_runtime_paths(
                frozen=True,
                executable=executable,
                bundle_root=bundle,
            )

        self.assertEqual(paths.sessions_dir, executable.parent / "results/sessions")
        self.assertEqual(
            paths.boot_manifest,
            bundle / "Cloud_test/boot/BOOT_E06_NET.manifest.json",
        )

    def test_combined_runtime_serves_dashboard_and_releases_both_ports(self):
        from Cloud_test.windows_launcher import CloudGuiRuntime

        with tempfile.TemporaryDirectory() as directory:
            runtime = CloudGuiRuntime(
                collector_address=("127.0.0.1", 0),
                dashboard_address=("127.0.0.1", 0),
                sessions_dir=Path(directory) / "sessions",
                boot_manifest=MANIFEST,
                socket_timeout=1.0,
            )
            runtime.start()
            self.addCleanup(runtime.stop)

            collector_host, collector_port = runtime.collector_address
            dashboard_host, dashboard_port = runtime.dashboard_address
            self.assertEqual(collector_host, "127.0.0.1")
            self.assertGreater(collector_port, 0)
            with urlopen(
                f"http://{dashboard_host}:{dashboard_port}/api/health",
                timeout=3,
            ) as response:
                payload = json.loads(response.read())
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["collector_state"], "waiting_for_board")

            runtime.stop()
            self.assertFalse(runtime.running)

            second = CloudGuiRuntime(
                collector_address=(collector_host, collector_port),
                dashboard_address=(dashboard_host, dashboard_port),
                sessions_dir=Path(directory) / "sessions-second",
                boot_manifest=MANIFEST,
                socket_timeout=1.0,
            )
            second.start()
            second.stop()

    def test_cli_accepts_windows_defaults_and_rejects_invalid_values(self):
        from Cloud_test.windows_launcher import _arguments

        args = _arguments(["--no-browser"])
        self.assertEqual(args.collector_host, "192.168.10.1")
        self.assertEqual(args.collector_port, 5001)
        self.assertEqual(args.gui_host, "127.0.0.1")
        self.assertEqual(args.gui_port, 8080)
        self.assertTrue(args.no_browser)

        for arguments in (
            ["--collector-host", "localhost"],
            ["--collector-port", "0"],
            ["--gui-port", "70000"],
            ["--socket-timeout", "0"],
            ["--socket-timeout", "nan"],
            ["--socket-timeout", "inf"],
            ["--socket-timeout", "-inf"],
        ):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                _arguments(arguments)


class WindowsPackagingContractTests(unittest.TestCase):
    def test_source_bundle_is_self_contained_and_excludes_runtime_and_hardware_payloads(self):
        from Cloud_test.tools.package_windows_source import build_source_bundle

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "windows-source.zip"
            result = build_source_bundle(CLOUD_ROOT, output)
            self.assertEqual(result, output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                manifest = json.loads(
                    archive.read("E06_Cloud_GUI_Win11_Source/SOURCE_SHA256SUMS.json")
                )

        for required in (
            "E06_Cloud_GUI_Win11_Source/Cloud_test/windows_launcher.py",
            "E06_Cloud_GUI_Win11_Source/Cloud_test/cloud/board_server.py",
            "E06_Cloud_GUI_Win11_Source/Cloud_test/dashboard/templates/index.html",
            "E06_Cloud_GUI_Win11_Source/Cloud_test/dashboard/static/plotly.min.js",
            "E06_Cloud_GUI_Win11_Source/Cloud_test/boot/BOOT_E06_NET.manifest.json",
            "E06_Cloud_GUI_Win11_Source/Cloud_test/windows/build_windows.ps1",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)
        self.assertFalse(any("/results/" in name for name in names))
        self.assertFalse(any("/vendor/" in name for name in names))
        self.assertFalse(any(name.endswith("BOOT_E06_NET.BIN") for name in names))
        self.assertEqual(manifest["schema"], "fvit-e06-win11-source-bundle-v1")
        self.assertEqual(
            {item["path"] for item in manifest["files"]},
            {
                name.removeprefix("E06_Cloud_GUI_Win11_Source/")
                for name in names
                if not name.endswith("SOURCE_SHA256SUMS.json")
            },
        )

    def test_build_recipe_bundles_manifest_dashboard_and_offline_plotly(self):
        spec = (CLOUD_ROOT / "windows/E06_Cloud_GUI.spec").read_text(encoding="utf-8")
        for required in (
            "cloud_root = Path(SPECPATH).resolve().parent",
            "windows_launcher.py",
            "BOOT_E06_NET.manifest.json",
            "dashboard/templates",
            "dashboard/static",
            "plotly.min.js",
            "name='E06_Cloud_GUI'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, spec)

        requirements = (CLOUD_ROOT / "windows/requirements-build.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("Flask", requirements)
        self.assertIn("PyInstaller", requirements)

    def test_network_script_requires_explicit_adapter_and_refuses_default_route(self):
        configure = (CLOUD_ROOT / "windows/Configure-ZCU102-Network.ps1").read_text(
            encoding="utf-8"
        )
        for required in (
            "Mandatory=$true",
            "InterfaceAlias",
            "ConfirmInterfaceAlias",
            "0.0.0.0/0",
            "Where-Object { $_.Name -ceq $InterfaceAlias }",
            "$Adapters.Count -ne 1",
            "-ErrorAction Stop",
            "network-backup.json",
            "192.168.10.1",
            "PrefixLength 24",
        ):
            with self.subTest(required=required):
                self.assertIn(required, configure)
        self.assertNotIn("AllowDefaultRouteInterface", configure)
        self.assertNotIn("-ErrorAction SilentlyContinue", configure)

        restore = (CLOUD_ROOT / "windows/Restore-ZCU102-Network.ps1").read_text(
            encoding="utf-8"
        )
        for required in (
            "network-backup.json",
            "InterfaceAlias",
            "Where-Object { $_.Name -ceq $InterfaceAlias }",
            "$Adapters.Count -ne 1",
            "0.0.0.0/0",
            "-ErrorAction Stop",
        ):
            with self.subTest(required=required):
                self.assertIn(required, restore)
        self.assertNotIn("-ErrorAction SilentlyContinue", restore)
        self.assertNotIn("Set-DnsClientServerAddress", restore)

    def test_build_recipe_rejects_non_x64_or_unsupported_python(self):
        script = (CLOUD_ROOT / "windows/build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("struct.calcsize('P') * 8", script)
        self.assertIn("platform.machine()", script)
        self.assertIn("sys.version_info", script)
        self.assertIn('if ($PythonBits -ne "64")', script)
        self.assertIn('$PythonMachine -notin @("AMD64", "x86_64")', script)
        self.assertIn('if ($PythonVersionOk -ne "true")', script)

    def test_windows_readme_distinguishes_e06_from_plantvillage_accuracy(self):
        readme = (CLOUD_ROOT / "windows/README_WIN11_CN.md").read_text(encoding="utf-8")
        for required in (
            "Windows 11",
            "build_windows.ps1",
            "E06_Cloud_GUI.exe",
            "192.168.10.1",
            "127.0.0.1:8080",
            "E06",
            "PlantVillage",
            "N/A",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)
        self.assertNotIn("AllowDefaultRouteInterface", readme)


if __name__ == "__main__":
    unittest.main()
