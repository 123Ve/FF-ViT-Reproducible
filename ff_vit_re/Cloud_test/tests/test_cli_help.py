import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLOUD_ROOT = PROJECT_ROOT / "Cloud_test"
CONFIG = CLOUD_ROOT / "config/e06_physical.json"
FIXTURE = CLOUD_ROOT / "fixtures/host_smoke/leaf.jpg"
FIXTURE_PROVENANCE = CLOUD_ROOT / "fixtures/host_smoke/leaf.provenance.json"


def run_cli(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLOUD_ROOT / script), *arguments],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )


class CliHelpTests(unittest.TestCase):
    def test_entrypoints_are_import_safe(self):
        for module_name in ("Cloud_test.run_cloud", "Cloud_test.run_dashboard"):
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_every_entrypoint_help_exits_zero_without_starting_service(self):
        for script in ("run_cloud.py", "run_dashboard.py", "run_smoke.py"):
            with self.subTest(script=script):
                completed = run_cli(script, "--help")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("usage:", completed.stdout.lower())

    def test_cloud_rejects_bad_address_port_and_paths_before_serving(self):
        cases = (
            ("--host", "999.1.1.1", "invalid IPv4 address"),
            ("--port", "0", "port must be in 1..65535"),
            ("--boot-manifest", "Cloud_test/missing.json", "existing file"),
        )
        for *arguments, expected in cases:
            with self.subTest(arguments=arguments):
                completed = run_cli("run_cloud.py", *arguments)
                self.assertEqual(completed.returncode, 2)
                self.assertIn(expected, completed.stderr)

    def test_dashboard_rejects_bad_address_port_and_store_before_serving(self):
        with tempfile.NamedTemporaryFile(dir=CLOUD_ROOT) as regular_file:
            cases = (
                ("--host", "localhost", "invalid IPv4 address"),
                ("--port", "70000", "port must be in 1..65535"),
                ("--sessions-dir", regular_file.name, "directory"),
            )
            for *arguments, expected in cases:
                with self.subTest(arguments=arguments):
                    completed = run_cli("run_dashboard.py", *arguments)
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn(expected, completed.stderr)


class PhysicalConfigTests(unittest.TestCase):
    def test_frozen_e06_physical_identity_and_endpoints(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["schema"], "fvit-e06-physical-config-v1")
        self.assertEqual(config["version"], 1)
        self.assertEqual(config["phase"], "E06_PHYSICAL")
        self.assertEqual(config["model"], "E06")
        self.assertEqual(config["network"], {
            "pc_ip": "192.168.10.1",
            "prefix_length": 24,
            "board_ip": "192.168.10.2",
            "tcp_port": 5001,
        })
        self.assertEqual(
            config["expected_sha256"]["weights"],
            "0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7",
        )
        for name in ("firmware_identity", "weights", "input", "reference_output",
                     "bitstream", "boot"):
            digest = config["expected_sha256"][name]
            self.assertRegex(digest, r"\A[0-9a-f]{64}\Z")
        self.assertEqual(config["sd_root_files"], [
            "BOOT.BIN", "weights.bin", "input.bin", "output.bin",
        ])
        self.assertEqual(config["dashboard"], {"host": "127.0.0.1", "port": 8080})

    def test_config_hashes_match_generated_release_artifacts(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        expected = config["expected_sha256"]
        paths = {
            "weights": CLOUD_ROOT / "vendor/e06_base/data/weights.bin",
            "input": CLOUD_ROOT / "vendor/e06_base/data/input.bin",
            "reference_output": CLOUD_ROOT / "vendor/e06_base/data/output.bin",
            "bitstream": CLOUD_ROOT / "vendor/e06_base/hw/design_1_wrapper.bit",
            "boot": CLOUD_ROOT / "boot/BOOT_E06_NET.BIN",
        }
        for name, path in paths.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected[name])
        boot_manifest = json.loads(
            (CLOUD_ROOT / "boot/BOOT_E06_NET.manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            expected["firmware_identity"],
            boot_manifest["firmware_identity"]["advertised_sha256"],
        )

    def test_bounded_fixture_has_verifiable_provenance(self):
        provenance = json.loads(FIXTURE_PROVENANCE.read_text(encoding="utf-8"))
        self.assertEqual(provenance["schema"], "fvit-host-smoke-fixture-v1")
        self.assertEqual(provenance["copied_path"], "fixtures/host_smoke/leaf.jpg")
        self.assertEqual(provenance["bytes"], FIXTURE.stat().st_size)
        self.assertLessEqual(provenance["bytes"], 256 * 1024)
        self.assertEqual(provenance["sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(provenance["evidence_scope"], "HOST_LOOPBACK_ONLY")

    def test_runbook_has_physical_gate_and_operator_safety_contract(self):
        text = (CLOUD_ROOT / "docs/E06_BOARD_RUNBOOK_CN.md").read_text(encoding="utf-8")
        for required in (
            "BOOT_E06_NET.BIN", "6e02ba90a6fbee3140537145c5236443b26aa3c3ef7f8380e146224578ddf37f",
            "FAT", "BOOT.BIN", "weights.bin", "input.bin", "output.bin",
            "ZCU102", "115200", "192.168.10.1/24", "192.168.10.2", "5001",
            "run_cloud.py", "run_dashboard.py", "E06_PHYSICAL", "Task 10",
            "PlantVillage", "N/A", "防火墙", "网卡接口",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_runbook_firewalld_rule_is_runtime_bounded_and_reversible(self):
        text = (CLOUD_ROOT / "docs/E06_BOARD_RUNBOOK_CN.md").read_text(encoding="utf-8")
        self.assertNotIn("--zone=trusted", text)
        self.assertNotRegex(text, r"firewall-cmd[^\n]*--permanent")
        for required in (
            'OLD_ZONE=$(sudo firewall-cmd --get-zone-of-interface="$IFACE")',
            'source address="192.168.10.2/32"',
            'destination address="192.168.10.1/32"',
            'port port="5001" protocol="tcp" accept',
            'sudo firewall-cmd --zone=drop --add-rich-rule="$RULE"',
            'sudo firewall-cmd --zone=drop --change-interface="$IFACE"',
            'sudo firewall-cmd --zone="$OLD_ZONE" --change-interface="$IFACE"',
            'sudo firewall-cmd --zone=drop --remove-interface="$IFACE"',
            'sudo firewall-cmd --zone=drop --remove-rich-rule="$RULE"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertLess(
            text.index('sudo firewall-cmd --zone=drop --add-rich-rule="$RULE"'),
            text.index('sudo firewall-cmd --zone=drop --change-interface="$IFACE"'),
        )


class ReleaseManifestTests(unittest.TestCase):
    def test_release_manifest_excludes_runtime_churn_caches_and_itself(self):
        from Cloud_test.tools.tree_manifest import build_release_manifest

        with tempfile.TemporaryDirectory(dir=CLOUD_ROOT) as directory:
            root = Path(directory)
            (root / "source.py").write_text("stable\n", encoding="utf-8")
            (root / "results/session").mkdir(parents=True)
            (root / "results/session/event.jsonl").write_text("first\n", encoding="utf-8")
            (root / "pkg/__pycache__").mkdir(parents=True)
            (root / "pkg/__pycache__/cache.pyc").write_bytes(b"one")
            checkpoint = root / "checkpoints/e06_network_release.sha256.json"
            checkpoint.parent.mkdir()
            checkpoint.write_text("old\n", encoding="utf-8")

            first = build_release_manifest(root)
            (root / "results/session/event.jsonl").write_text("second\n", encoding="utf-8")
            (root / "pkg/__pycache__/cache.pyc").write_bytes(b"two")
            checkpoint.write_text("changed\n", encoding="utf-8")
            second = build_release_manifest(root)

            self.assertEqual(first, second)
            self.assertEqual([item["path"] for item in first["files"]], ["source.py"])
            self.assertEqual(first["schema"], "fvit-release-manifest-v1")
            self.assertIn("results/", first["exclusion_policy"]["path_prefixes"])
            self.assertIn("__pycache__", first["exclusion_policy"]["directory_names"])


if __name__ == "__main__":
    unittest.main()
