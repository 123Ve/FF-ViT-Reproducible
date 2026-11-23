"""Print deterministic SHA-256 manifests of regular files in selected trees."""

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Sequence


RELEASE_EXCLUSION_POLICY = {
    "directory_names": ["__pycache__", ".pytest_cache"],
    "file_suffixes": [".pyc", ".pyo"],
    "path_prefixes": ["results/"],
    "exact_paths": ["checkpoints/e06_network_release.sha256.json"],
    "reason": (
        "Exclude interpreter caches, mutable session/smoke evidence, and the release "
        "manifest itself so repeated release hashing is stable."
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_components(path: Path, root: Path) -> None:
    current = root
    if current.is_symlink():
        raise ValueError(f"symlink path: {current}")
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink path: {current}")


def build_tree_manifest(paths: Sequence[Path], root: Path) -> dict[str, object]:
    """Hash selected files recursively, relative to root, without following links."""
    root = Path(root).absolute()
    root_resolved = root.resolve()
    try:
        output_stat = os.fstat(sys.stdout.fileno())
        output_identity = (output_stat.st_dev, output_stat.st_ino) if stat.S_ISREG(output_stat.st_mode) else None
    except (OSError, AttributeError):
        output_identity = None
    records = {}

    def visit(path: Path) -> None:
        if path.is_symlink():
            raise ValueError(f"symlink path: {path}")
        if path.is_dir():
            for child in path.iterdir():
                visit(child)
        elif path.is_file():
            file_stat = path.stat()
            if output_identity == (file_stat.st_dev, file_stat.st_ino):
                return
            relative = path.relative_to(root_resolved).as_posix()
            records[relative] = {"path": relative, "bytes": file_stat.st_size, "sha256": _sha256(path)}
        else:
            raise ValueError(f"not a regular file or directory: {path}")

    for given in paths:
        path = Path(given).absolute()
        try:
            path.relative_to(root)
            _reject_symlink_components(path, root)
            path = path.resolve()
            path.relative_to(root_resolved)
        except ValueError as error:
            if "symlink" in str(error):
                raise
            raise ValueError(f"path outside root: {given}") from error
        visit(path)
    return {"files": [records[key] for key in sorted(records)]}


def build_release_manifest(root: Path) -> dict[str, object]:
    """Hash a release tree while excluding explicitly documented runtime churn."""
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"release root must be a real directory: {root}")
    root = root.resolve()
    records: dict[str, dict[str, object]] = {}

    def excluded(relative: str, path: Path) -> bool:
        parts = relative.split("/")
        if any(part in RELEASE_EXCLUSION_POLICY["directory_names"] for part in parts[:-1]):
            return True
        if any(relative.startswith(prefix)
               for prefix in RELEASE_EXCLUSION_POLICY["path_prefixes"]):
            return True
        if relative in RELEASE_EXCLUSION_POLICY["exact_paths"]:
            return True
        return path.suffix in RELEASE_EXCLUSION_POLICY["file_suffixes"]

    def visit(path: Path) -> None:
        relative = path.relative_to(root).as_posix()
        if relative != "." and excluded(relative, path):
            return
        if path.is_symlink():
            raise ValueError(f"symlink path: {path}")
        if path.is_dir():
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                visit(child)
            return
        if not path.is_file():
            raise ValueError(f"not a regular file or directory: {path}")
        records[relative] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    visit(root)
    return {
        "schema": "fvit-release-manifest-v1",
        "exclusion_policy": RELEASE_EXCLUSION_POLICY,
        "files": [records[key] for key in sorted(records)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--release", action="store_true",
                        help="apply the stable Cloud_test release exclusion policy")
    args = parser.parse_args()
    if args.release:
        if len(args.paths) != 1:
            parser.error("--release requires exactly one release root path")
        manifest = build_release_manifest(args.paths[0])
    else:
        manifest = build_tree_manifest(args.paths, args.root)
    json.dump(manifest, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
