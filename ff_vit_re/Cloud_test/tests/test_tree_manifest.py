import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from Cloud_test.tools.tree_manifest import build_tree_manifest


CLOUD_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = CLOUD_ROOT / "tools/tree_manifest.py"


class TreeManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=CLOUD_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_recurses_regular_files_in_deterministic_path_order(self):
        (self.root / "z").mkdir()
        (self.root / "z/last").write_bytes(b"abc")
        (self.root / "a").write_bytes(b"")
        manifest = build_tree_manifest([self.root / "z", self.root / "a"], self.root)
        self.assertEqual(manifest, {"files": [
            {"path": "a", "bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
            {"path": "z/last", "bytes": 3, "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
        ]})

    def test_rejects_path_outside_root(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            build_tree_manifest([CLOUD_ROOT / "README.md"], self.root)

    def test_rejects_file_symlink(self):
        (self.root / "target").write_bytes(b"data")
        (self.root / "link").symlink_to(self.root / "target")
        with self.assertRaisesRegex(ValueError, "symlink"):
            build_tree_manifest([self.root], self.root)

    def test_rejects_directory_symlink(self):
        (self.root / "target").mkdir()
        (self.root / "link").symlink_to(self.root / "target", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            build_tree_manifest([self.root], self.root)

    def test_cli_omits_its_redirected_output_within_scanned_tree(self):
        (self.root / "input").write_bytes(b"abc")
        output = self.root / "checkpoint.json"
        with output.open("w") as stream:
            subprocess.run([sys.executable, str(SCRIPT), str(self.root)], cwd=self.root,
                           stdout=stream, check=True)
        records = json.loads(output.read_text())["files"]
        self.assertEqual([record["path"] for record in records], ["input"])


if __name__ == "__main__":
    unittest.main()
