#!/usr/bin/env python3
"""Build a deterministic, minimal Windows source-transfer bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile


ARCHIVE_ROOT = "E06_Cloud_GUI_Win11_Source"
FIXED_TIME = (2026, 10, 4, 0, 0, 0)


def _source_files(cloud_root: Path) -> list[Path]:
    files = [
        cloud_root / "__init__.py",
        cloud_root / "windows_launcher.py",
        cloud_root / "run_stream_measurements.py",
        cloud_root / "docs/CLOUD_STREAM_MEASUREMENTS_CN.md",
        cloud_root / "tools/export_stream_plots.py",
        cloud_root / "boot/BOOT_E06_NET.manifest.json",
        cloud_root / "docs/E06_BOARD_RUNBOOK_CN.md",
    ]
    for directory in ("cloud", "dashboard", "iot_eval", "windows"):
        for path in (cloud_root / directory).rglob("*"):
            relative = path.relative_to(cloud_root)
            if (path.is_file()
                    and "__pycache__" not in relative.parts
                    and ".venv-build-win" not in relative.parts
                    and path.suffix not in {".pyc", ".pyo"}
                    and path.name != "network-backup.json"):
                files.append(path)
    unique = sorted(set(files), key=lambda path: path.relative_to(cloud_root).as_posix())
    missing = [path for path in unique if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing Windows bundle inputs: {missing}")
    return unique


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def build_source_bundle(cloud_root: Path | str, output: Path | str) -> Path:
    cloud = Path(cloud_root).resolve()
    destination = Path(output).resolve()
    files = _source_files(cloud)
    entries: list[tuple[str, bytes]] = []
    manifest_files = []
    for path in files:
        relative = (Path("Cloud_test") / path.relative_to(cloud)).as_posix()
        data = path.read_bytes()
        entries.append((relative, data))
        manifest_files.append({
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "schema": "fvit-e06-win11-source-bundle-v1",
        "platform": "Windows 11 x64",
        "files": manifest_files,
        "exclusions": ["results/", "vendor/", "build/", "BOOT_E06_NET.BIN"],
    }
    manifest_data = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
                     + "\n").encode("utf-8")

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compresslevel=9) as archive:
            for relative, data in entries:
                archive.writestr(_zip_info(f"{ARCHIVE_ROOT}/{relative}"), data)
            archive.writestr(
                _zip_info(f"{ARCHIVE_ROOT}/SOURCE_SHA256SUMS.json"),
                manifest_data,
            )
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "dist/E06_Cloud_GUI_Win11_Source.zip",
    )
    args = parser.parse_args()
    output = build_source_bundle(Path(__file__).resolve().parents[1], args.output)
    print(f"WINDOWS_SOURCE_BUNDLE={output}")
    print(f"WINDOWS_SOURCE_BUNDLE_SHA256={hashlib.sha256(output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
