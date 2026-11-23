"""Read-only fingerprinting for the existing E06 deployment files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_artifacts(paths: Mapping[str, Path | str]) -> dict[str, dict[str, object]]:
    manifest: dict[str, dict[str, object]] = {}
    for name, source in paths.items():
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"missing artifact {name}: {path}")
        manifest[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return manifest
