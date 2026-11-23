import json
from pathlib import Path

from src.provenance import atomic_write_json, sha256_file


def test_sha256_file_is_deterministic_and_matches_standard_sha256(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"original-hls-s3\x00contract")

    expected = "5e580f3925dcc6dc73ff2e7741972dc898fc1f5f4973c7cae89b81d88e1b20e7"
    assert sha256_file(source) == expected
    assert sha256_file(source) == sha256_file(source)


def test_atomic_write_json_leaves_parseable_json_at_destination(tmp_path):
    destination = tmp_path / "manifest.json"
    payload = {"schema_version": 1, "inputs": ["checkpoint.pth"]}

    atomic_write_json(destination, payload)

    assert json.loads(destination.read_text()) == payload
    assert sorted(path.name for path in tmp_path.iterdir()) == ["manifest.json"]
