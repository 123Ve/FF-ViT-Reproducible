#!/usr/bin/env python3
"""Create the E06 network BOOT image and an exact provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


CLOUD_ROOT = Path(__file__).resolve().parents[1]
BOOTGEN = Path("/opt/vivado/2025.1/Vitis/bin/bootgen")


@dataclass(frozen=True)
class BootConfig:
    fsbl: Path
    pmufw: Path
    bit: Path
    app: Path
    output: Path
    bif: Path
    manifest: Path
    firmware_identity_path: Path
    firmware_identity: dict[str, object]
    bootgen: Path = BOOTGEN


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_components(path: Path, root: Path) -> None:
    root = root.absolute()
    path = path.absolute()
    try:
        parts = path.relative_to(root).parts
    except ValueError as error:
        raise ValueError(f"path outside Cloud_test: {path}") from error
    current = root
    if current.is_symlink():
        raise ValueError(f"symlink path component: {current}")
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink path component: {current}")


def make_boot_config(
    fsbl: Path, pmufw: Path, bit: Path, app: Path, output: Path, *,
    firmware_identity: Path,
    cloud_root: Path = CLOUD_ROOT, bootgen: Path = BOOTGEN
) -> BootConfig:
    cloud_root = Path(cloud_root).resolve()
    paths = {}
    for name, supplied in (("fsbl", fsbl), ("pmufw", pmufw), ("bit", bit), ("app", app)):
        supplied = Path(supplied).absolute()
        _reject_symlink_components(supplied, cloud_root)
        resolved = supplied.resolve()
        try:
            resolved.relative_to(cloud_root)
        except ValueError as error:
            raise ValueError(f"{name} must be a copied input below Cloud_test") from error
        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise FileNotFoundError(f"missing or empty {name}: {resolved}")
        paths[name] = resolved
    identity_path = Path(firmware_identity).absolute()
    _reject_symlink_components(identity_path, cloud_root)
    try:
        identity_path.resolve().relative_to(cloud_root)
    except ValueError as error:
        raise ValueError("firmware identity must remain inside Cloud_test") from error
    identity = _load_firmware_identity(identity_path.resolve())
    output = Path(output).absolute()
    boot_root = (cloud_root / "boot").resolve()
    try:
        output.relative_to(cloud_root)
    except ValueError as error:
        raise ValueError("output must remain under Cloud_test/boot") from error
    _reject_symlink_components(output, cloud_root)
    resolved_output = output.resolve()
    try:
        resolved_output.relative_to(boot_root)
    except ValueError as error:
        raise ValueError("output must remain under Cloud_test/boot") from error
    if resolved_output.parent != boot_root:
        raise ValueError("output must be directly under Cloud_test/boot")
    return BootConfig(
        fsbl=paths["fsbl"], pmufw=paths["pmufw"], bit=paths["bit"], app=paths["app"],
        output=resolved_output, bif=resolved_output.with_suffix(".bif"),
        manifest=resolved_output.with_suffix(".manifest.json"),
        firmware_identity_path=identity_path.resolve(), firmware_identity=identity,
        bootgen=Path(bootgen).resolve(),
    )


def render_bif(config: BootConfig) -> str:
    return (
        "the_ROM_image:\n{\n"
        f"  [bootloader] {config.fsbl}\n"
        f"  [pmufw_image] {config.pmufw}\n"
        f"  [destination_device=pl] {config.bit}\n"
        f"  [destination_cpu=a53-0, exception_level=el-3] {config.app}\n"
        "}\n"
    )


def _artifact(path: Path, *, published_path: Path | None = None) -> dict[str, object]:
    return {
        "path": str((published_path or path).resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _load_firmware_identity(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"missing firmware identity: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid firmware identity document: {path}") from error
    if not isinstance(document, dict):
        raise ValueError("firmware identity document must be an object")
    advertised = document.get("advertised_sha256")
    if not isinstance(advertised, str) or not re.fullmatch(r"[0-9a-f]{64}", advertised):
        raise ValueError("firmware advertised identity must be lowercase 64-hex")
    if advertised == "0" * 64:
        raise ValueError("firmware advertised identity must be nonzero")
    if document.get("algorithm") != "sha256":
        raise ValueError("firmware identity algorithm must be sha256")
    if document.get("canonicalization") != "utf8-json-sort-keys-compact":
        raise ValueError("unsupported firmware identity canonicalization")
    payload = document.get("canonical_payload")
    if not isinstance(payload, dict):
        raise ValueError("firmware identity canonical payload is missing")
    computed = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if computed != advertised:
        raise ValueError("firmware advertised identity does not match canonical payload")
    return document


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def _bootgen_version(bootgen: Path) -> str:
    result = subprocess.run([str(bootgen), "-help"], text=True, capture_output=True, check=True)
    lines = [line.strip() for line in (result.stdout + result.stderr).splitlines() if "Bootgen v" in line]
    return lines[0] if lines else "Bootgen version unavailable"


def build_boot(
    config: BootConfig,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str] | None] = subprocess.run,
    version_reader: Callable[[Path], str] = _bootgen_version,
) -> dict[str, object]:
    config.output.parent.mkdir(parents=True, exist_ok=True)
    for path in (config.output, config.bif, config.manifest):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite existing BOOT artifact: {path}")
    identity = _load_firmware_identity(config.firmware_identity_path)
    if identity != config.firmware_identity:
        raise RuntimeError("firmware identity changed after BOOT configuration")
    built_artifact = identity.get("built_artifact")
    if isinstance(built_artifact, dict):
        if (built_artifact.get("bytes") != config.app.stat().st_size
                or built_artifact.get("sha256") != _sha256(config.app)):
            raise RuntimeError("firmware identity built artifact does not match application ELF")
    version = version_reader(config.bootgen)
    manifest: dict[str, object] | None = None
    try:
        with tempfile.TemporaryDirectory(
            dir=config.output.parent, prefix=".e06-bootgen-"
        ) as temporary_dir:
            temporary_root = Path(temporary_dir)
            temporary_bif = temporary_root / config.bif.name
            temporary_output = temporary_root / config.output.name
            temporary_bif.write_text(render_bif(config), encoding="utf-8")
            command = [
                str(config.bootgen), "-arch", "zynqmp", "-image", str(temporary_bif),
                "-o", str(temporary_output), "-w", "on",
            ]
            completed = runner(command, text=True, capture_output=True, check=True)
            if not temporary_output.is_file() or temporary_output.stat().st_size == 0:
                raise RuntimeError("Bootgen did not create a nonempty BOOT image")
            manifest = {
                "schema": "fvit-e06-net-boot-v1",
                "tool": {"path": str(config.bootgen), "version": version},
                "command": command,
                "published_command": [
                    str(config.bootgen), "-arch", "zynqmp", "-image", str(config.bif),
                    "-o", str(config.output), "-w", "on",
                ],
                "firmware_identity": identity,
                "firmware_identity_source": _artifact(config.firmware_identity_path),
                "artifacts": {
                    "fsbl": _artifact(config.fsbl),
                    "pmufw": _artifact(config.pmufw),
                    "bit": _artifact(config.bit),
                    "app": _artifact(config.app),
                    "bif": _artifact(temporary_bif, published_path=config.bif),
                    "boot": _artifact(temporary_output, published_path=config.output),
                },
            }
            if completed is not None:
                manifest["bootgen_stdout"] = completed.stdout or ""
                manifest["bootgen_stderr"] = completed.stderr or ""
            # Only publish after Bootgen, its version query and all hashes succeed.
            os.replace(temporary_bif, config.bif)
            os.replace(temporary_output, config.output)
            _atomic_json(config.manifest, manifest)
            return manifest
    except BaseException:
        for path in (config.manifest, config.output, config.bif):
            path.unlink(missing_ok=True)
        raise


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsbl", type=Path, required=True)
    parser.add_argument("--pmufw", type=Path, required=True)
    parser.add_argument("--bit", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--firmware-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    config = make_boot_config(
        args.fsbl, args.pmufw, args.bit, args.app, args.output,
        firmware_identity=args.firmware_identity,
    )
    manifest = build_boot(config)
    boot = manifest["artifacts"]["boot"]
    print(f"E06_NET_BOOT={boot['path']}")
    print(f"E06_NET_BOOT_BYTES={boot['bytes']}")
    print(f"E06_NET_BOOT_SHA256={boot['sha256']}")
    print(f"E06_NET_MANIFEST={config.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
