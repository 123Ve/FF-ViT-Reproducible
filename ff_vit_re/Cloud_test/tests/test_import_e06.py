import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Cloud_test.tools.import_e06 import E06_DESTINATIONS, E06_FILES, import_e06


CLOUD_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = CLOUD_ROOT / "vendor"


class ImportE06Tests(unittest.TestCase):
    def setUp(self):
        VENDOR_ROOT.mkdir(exist_ok=True)
        self.source_temp = tempfile.TemporaryDirectory(dir=CLOUD_ROOT)
        self.vendor_temp = tempfile.TemporaryDirectory(dir=VENDOR_ROOT)
        self.addCleanup(self.source_temp.cleanup)
        self.addCleanup(self.vendor_temp.cleanup)
        self.source = Path(self.source_temp.name)
        self.destination = Path(self.vendor_temp.name) / "e06_base"
        for key, relative in E06_FILES.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(key.encode())

    def test_copies_literal_bytes_and_hand_checked_hash(self):
        source = self.source / E06_FILES["xsa"]
        source.write_bytes(b"abc")

        records = import_e06(self.source, self.destination)

        copied = self.destination / "hw/e06_measurement_250mhz.xsa"
        self.assertEqual(copied.read_bytes(), b"abc")
        self.assertEqual(records["xsa"], {
            "source": str(source.resolve()),
            "copied_path": str(copied.resolve()),
            "bytes": 3,
            "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        })
        self.assertEqual(set(records), set(E06_FILES))

    def test_rejects_destination_outside_vendor_root(self):
        outside = self.source / "output"
        with self.assertRaisesRegex(ValueError, "Cloud_test/vendor"):
            import_e06(self.source, outside)
        self.assertFalse(outside.exists())

    def test_rejects_source_symlink(self):
        path = self.source / E06_FILES["weights"]
        path.unlink()
        path.symlink_to(self.source / E06_FILES["input"])
        with self.assertRaisesRegex(ValueError, "symlink"):
            import_e06(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_rejects_missing_allowlist_entry(self):
        (self.source / E06_FILES["pmufw"]).unlink()
        with self.assertRaises(FileNotFoundError):
            import_e06(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_identical_rerun_succeeds(self):
        first = import_e06(self.source, self.destination)
        second = import_e06(self.source, self.destination)
        self.assertEqual(second, first)

    def test_conflicting_destination_fails_without_overwrite(self):
        import_e06(self.source, self.destination)
        copied = self.destination / "data/weights.bin"
        copied.write_bytes(b"other")
        with self.assertRaisesRegex(FileExistsError, "different"):
            import_e06(self.source, self.destination)
        self.assertEqual(copied.read_bytes(), b"other")

    def test_duplicate_destination_is_rejected_before_copy(self):
        with patch.dict(E06_DESTINATIONS, {"input": E06_DESTINATIONS["weights"]}):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                import_e06(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_source_directory_symlink_is_rejected(self):
        source = self.source / E06_FILES["weights"]
        new_parent = source.parent.with_name("actual_inputs")
        source.parent.rename(new_parent)
        source.parent.symlink_to(new_parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            import_e06(self.source, self.destination)

    def test_cli_preserves_a_conflicting_manifest(self):
        manifest = Path(self.vendor_temp.name) / "source_manifest.json"
        manifest.write_bytes(b"older manifest\n")
        script = CLOUD_ROOT / "tools/import_e06.py"
        result = subprocess.run(
            [sys.executable, str(script), "--e06-root", str(self.source),
             "--destination", str(self.destination), "--manifest", str(manifest)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(manifest.read_bytes(), b"older manifest\n")


if __name__ == "__main__":
    unittest.main()
