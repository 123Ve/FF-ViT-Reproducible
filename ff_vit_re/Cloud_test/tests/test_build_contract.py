import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ZERO_SHA256 = "0" * 64


class BuildPolicyTests(unittest.TestCase):
    def setUp(self):
        from Cloud_test.build_scripts import build_e06_net

        self.module = build_e06_net
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cloud = self.root / "Cloud_test"
        self.xsa = self.cloud / "vendor" / "base.xsa"
        self.source = self.cloud / "firmware"
        self.workspace = self.cloud / "build" / "e06_net_workspace"
        self.xsa.parent.mkdir(parents=True)
        self.xsa.write_bytes(b"xsa")
        records = {}
        for name in ("xsa", "bitstream", "weights", "input", "output"):
            path = self.xsa if name == "xsa" else self.xsa.parent / f"{name}.bin"
            if name != "xsa":
                path.write_bytes(name.encode("ascii"))
            records[name] = {
                "copied_path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        (self.xsa.parent / "source_manifest.json").write_text(
            json.dumps(records), encoding="utf-8"
        )
        (self.source / "common" / "tests").mkdir(parents=True)
        (self.source / "e06_net").mkdir(parents=True)
        (self.source / "common" / "codec.c").write_text("codec", encoding="utf-8")
        (self.source / "common" / "codec.h").write_text("header", encoding="utf-8")
        (self.source / "common" / "tests" / "fake.c").write_text("fake", encoding="utf-8")
        (self.source / "e06_net" / "main.c").write_text("main", encoding="utf-8")

    def test_build_configuration_is_a53_standalone_with_exact_libraries(self):
        config = self.module.make_build_config(
            self.xsa, self.workspace, self.source, cloud_root=self.cloud
        )
        self.assertEqual(config.cpu, "psu_cortexa53_0")
        self.assertEqual(config.domain, "standalone_psu_cortexa53_0")
        self.assertEqual(config.os, "standalone")
        self.assertEqual(config.architecture, "64-bit")
        self.assertEqual(set(config.libraries), {"xilffs", "lwip220"})

    def test_source_enumeration_excludes_tests_and_fakes(self):
        selected = self.module.enumerate_firmware_sources(self.source)
        relative = {path.relative_to(self.source).as_posix() for path in selected}
        self.assertEqual(relative, {"common/codec.c", "common/codec.h", "e06_net/main.c"})

    def test_source_copy_preserves_vitis_build_metadata(self):
        config = self.module.make_build_config(
            self.xsa, self.workspace, self.source, cloud_root=self.cloud
        )
        app_source = self.cloud / "generated_app" / "src"
        app_source.mkdir(parents=True)
        (app_source / "CMakeLists.txt").write_text("generated cmake", encoding="utf-8")
        (app_source / "lscript.ld").write_text("generated linker", encoding="utf-8")
        (app_source / "helloworld.c").write_text("placeholder", encoding="utf-8")
        self.module._copy_application_sources(config, app_source)
        self.assertEqual((app_source / "CMakeLists.txt").read_text(), "generated cmake")
        self.assertEqual((app_source / "lscript.ld").read_text(), "generated linker")
        self.assertFalse((app_source / "helloworld.c").exists())

    def test_firmware_contains_standalone_lwip_timer_platform(self):
        platform_c = self.source / "e06_net" / "platform.c"
        platform_h = self.source / "e06_net" / "platform.h"
        network_c = self.source / "e06_net" / "e06_network.c"
        platform_c.write_text("XTimer_SetInterval tcp_fasttmr tcp_slowtmr", encoding="utf-8")
        platform_h.write_text("void init_platform(void);", encoding="utf-8")
        network_c.write_text("TcpFastTmrFlag TcpSlowTmrFlag", encoding="utf-8")
        selected = self.module.enumerate_firmware_sources(self.source)
        names = {path.name for path in selected}
        self.assertIn("platform.c", names)
        self.assertIn("platform.h", names)
        self.assertIn("TcpFastTmrFlag", network_c.read_text(encoding="utf-8"))

    def test_build_identity_is_nonzero_deterministic_and_source_sensitive(self):
        config = self.module.make_build_config(
            self.xsa, self.workspace, self.source, cloud_root=self.cloud
        )
        first = self.module.compute_build_identity(config)
        second = self.module.compute_build_identity(config)
        self.assertEqual(first, second)
        identity = first["advertised_sha256"]
        self.assertRegex(identity, r"^[0-9a-f]{64}$")
        self.assertNotEqual(identity, ZERO_SHA256)
        self.assertNotIn("advertised_sha256", first["canonical_payload"])
        (self.source / "common" / "codec.c").write_text("changed", encoding="utf-8")
        changed = self.module.compute_build_identity(config)
        self.assertNotEqual(changed["advertised_sha256"], identity)

    def test_generated_identity_header_contains_exact_identity_without_placeholder(self):
        config = self.module.make_build_config(
            self.xsa, self.workspace, self.source, cloud_root=self.cloud
        )
        identity = self.module.compute_build_identity(config)
        header = self.cloud / "generated" / "firmware_build_identity.h"
        self.module.write_build_identity_header(header, identity)
        text = header.read_text(encoding="ascii")
        self.assertIn(identity["advertised_sha256"], text)
        self.assertNotIn(ZERO_SHA256, text)

    def test_existing_workspace_requires_explicit_bounded_clean(self):
        self.workspace.mkdir(parents=True)
        with self.assertRaisesRegex(FileExistsError, "--clean-generated"):
            self.module.prepare_workspace(self.workspace, False, cloud_root=self.cloud)
        self.module.prepare_workspace(self.workspace, True, cloud_root=self.cloud)
        self.assertFalse(self.workspace.exists())

    def test_clean_refuses_any_workspace_except_exact_generated_path(self):
        other = self.cloud / "build" / "other"
        other.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "e06_net_workspace"):
            self.module.prepare_workspace(other, True, cloud_root=self.cloud)
        self.assertTrue(other.exists())

    def test_workspace_symlink_escape_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.cloud / "build").mkdir(parents=True)
        self.workspace.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.module.make_build_config(
                self.xsa, self.workspace, self.source, cloud_root=self.cloud
            )

    def test_vendor_verifier_catches_changed_byte(self):
        copied = self.cloud / "vendor" / "copied.bin"
        copied.write_bytes(b"original")
        manifest = self.cloud / "vendor" / "source_manifest.json"
        manifest.write_text(json.dumps({"item": {
            "copied_path": str(copied),
            "bytes": copied.stat().st_size,
            "sha256": hashlib.sha256(b"original").hexdigest(),
        }}), encoding="utf-8")
        self.module.verify_vendor_manifest(manifest, cloud_root=self.cloud)
        copied.write_bytes(b"changed!")
        with self.assertRaisesRegex(RuntimeError, "item"):
            self.module.verify_vendor_manifest(manifest, cloud_root=self.cloud)


class BootPolicyTests(unittest.TestCase):
    def setUp(self):
        from Cloud_test.build_scripts import make_e06_net_boot

        self.module = make_e06_net_boot
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cloud = self.root / "Cloud_test"
        self.boot = self.cloud / "boot"
        self.boot.mkdir(parents=True)
        self.inputs = {}
        for name in ("fsbl", "pmufw", "bit", "app"):
            path = self.cloud / "inputs" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode("ascii"))
            self.inputs[name] = path
        self.identity = self.cloud / "inputs" / "firmware_build_identity.json"
        payload = {"inputs": {"production_sources": []}}
        advertised = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")).hexdigest()
        self.identity.write_text(json.dumps({
            "schema": "fvit-e06-firmware-build-identity-v1",
            "algorithm": "sha256",
            "canonicalization": "utf8-json-sort-keys-compact",
            "advertised_sha256": advertised,
            "canonical_payload": payload,
        }), encoding="utf-8")

    def make_config(self, output):
        return self.module.make_boot_config(
            **self.inputs, output=output, firmware_identity=self.identity,
            cloud_root=self.cloud
        )

    def test_boot_output_outside_cloud_boot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Cloud_test/boot"):
            self.module.make_boot_config(
                **self.inputs, output=self.root / "BOOT.BIN",
                firmware_identity=self.identity, cloud_root=self.cloud
            )

    def test_boot_output_symlink_escape_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        escaped = self.boot / "link"
        escaped.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.module.make_boot_config(
                **self.inputs, output=escaped / "BOOT.BIN",
                firmware_identity=self.identity, cloud_root=self.cloud
            )

    def test_bif_order_and_el3_destination_are_explicit(self):
        config = self.make_config(self.boot / "BOOT.BIN")
        text = self.module.render_bif(config)
        positions = [text.index(str(self.inputs[name].resolve()))
                     for name in ("fsbl", "pmufw", "bit", "app")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("[bootloader]", text)
        self.assertIn("[pmufw_image]", text)
        self.assertIn("[destination_device=pl]", text)
        self.assertIn("destination_cpu=a53-0", text)
        self.assertIn("exception_level=el-3", text)

    def test_bootgen_failure_does_not_write_success_manifest(self):
        output = self.boot / "BOOT.BIN"
        config = self.make_config(output)

        def partial_failure(command, **kwargs):
            Path(command[command.index("-o") + 1]).write_bytes(b"partial")
            raise subprocess.CalledProcessError(1, command)

        with self.assertRaises(subprocess.CalledProcessError):
            self.module.build_boot(
                config,
                runner=partial_failure,
                version_reader=mock.Mock(return_value="Bootgen test"),
            )
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".bif").exists())
        self.assertFalse(output.with_suffix(".manifest.json").exists())

        def retry_runner(command, **kwargs):
            Path(command[command.index("-o") + 1]).write_bytes(b"retry boot")
            return subprocess.CompletedProcess(command, 0, "retry", "")

        manifest = self.module.build_boot(
            config, runner=retry_runner,
            version_reader=mock.Mock(return_value="Bootgen test"),
        )
        self.assertEqual(manifest["artifacts"]["boot"]["sha256"],
                         hashlib.sha256(b"retry boot").hexdigest())

    def test_missing_output_does_not_write_success_manifest(self):
        output = self.boot / "BOOT.BIN"
        config = self.make_config(output)
        with self.assertRaisesRegex(RuntimeError, "nonempty"):
            self.module.build_boot(
                config, runner=mock.Mock(return_value=None),
                version_reader=mock.Mock(return_value="Bootgen test"),
            )
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".bif").exists())
        self.assertFalse(output.with_suffix(".manifest.json").exists())

    def test_version_failure_leaves_no_final_artifacts(self):
        output = self.boot / "BOOT.BIN"
        config = self.make_config(output)
        with self.assertRaisesRegex(RuntimeError, "version failed"):
            runner = mock.Mock()
            self.module.build_boot(
                config, runner=runner,
                version_reader=mock.Mock(side_effect=RuntimeError("version failed")),
            )
        runner.assert_not_called()
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".bif").exists())
        self.assertFalse(output.with_suffix(".manifest.json").exists())

    def test_zero_advertised_identity_is_rejected(self):
        document = json.loads(self.identity.read_text(encoding="utf-8"))
        document["advertised_sha256"] = ZERO_SHA256
        self.identity.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "nonzero"):
            self.make_config(self.boot / "BOOT.BIN")

    def test_manifest_hashes_literal_inputs_and_output(self):
        output = self.boot / "BOOT.BIN"
        config = self.make_config(output)

        def fake_runner(command, **kwargs):
            self.assertLess(command.index("-image"), command.index("-o"))
            Path(command[command.index("-o") + 1]).write_bytes(b"literal boot")
            return subprocess.CompletedProcess(command, 0, "fake bootgen", "")

        manifest = self.module.build_boot(
            config, runner=fake_runner,
            version_reader=mock.Mock(return_value="Bootgen test"),
        )
        self.assertEqual(
            manifest["artifacts"]["app"]["sha256"],
            hashlib.sha256(b"app").hexdigest(),
        )
        self.assertEqual(
            manifest["artifacts"]["boot"]["sha256"],
            hashlib.sha256(b"literal boot").hexdigest(),
        )
        saved = json.loads(output.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, manifest)
        self.assertEqual(manifest["firmware_identity"], json.loads(self.identity.read_text()))
        self.assertEqual(
            manifest["firmware_identity"]["advertised_sha256"],
            json.loads(self.identity.read_text())["advertised_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
