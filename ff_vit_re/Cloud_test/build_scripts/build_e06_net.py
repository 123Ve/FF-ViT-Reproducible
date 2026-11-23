#!/usr/bin/env python3
"""Build the isolated E06 network application with the Vitis 2025.1 Python API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CLOUD_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_WORKSPACE_RELATIVE = Path("build/e06_net_workspace")
XILFFS_PATH = Path("/opt/vivado/2025.1/Vitis/data/embeddedsw/lib/sw_services/xilffs_v5_4")
LWIP220_PATH = Path("/opt/vivado/2025.1/Vitis/data/embeddedsw/ThirdParty/sw_services/lwip220_v1_2")
ZERO_SHA256 = "0" * 64
IDENTITY_INPUTS = ("xsa", "bitstream", "weights", "input", "output")
IDENTITY_SCHEMA = "fvit-e06-firmware-build-identity-v1"
IDENTITY_CANONICALIZATION = "utf8-json-sort-keys-compact"


@dataclass(frozen=True)
class BuildConfig:
    xsa: Path
    workspace: Path
    source_dir: Path
    cloud_root: Path
    cpu: str = "psu_cortexa53_0"
    domain: str = "standalone_psu_cortexa53_0"
    os: str = "standalone"
    architecture: str = "64-bit"
    libraries: tuple[str, ...] = ("xilffs", "lwip220")


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
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink path component: {current}")


def _inside(path: Path, root: Path, label: str) -> Path:
    path = Path(path).absolute()
    root = Path(root).absolute()
    _reject_symlink_components(path, root)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} must remain inside Cloud_test: {path}") from error
    return path.resolve()


def make_build_config(
    xsa: Path, workspace: Path, source_dir: Path, *, cloud_root: Path = CLOUD_ROOT
) -> BuildConfig:
    cloud_root = Path(cloud_root).resolve()
    xsa = _inside(Path(xsa), cloud_root, "XSA")
    source_dir = _inside(Path(source_dir), cloud_root, "firmware source")
    workspace = _inside(Path(workspace), cloud_root, "workspace")
    expected = (cloud_root / EXPECTED_WORKSPACE_RELATIVE).resolve()
    if workspace != expected:
        raise ValueError(f"workspace must be exact Cloud_test/{EXPECTED_WORKSPACE_RELATIVE}")
    if not xsa.is_file():
        raise FileNotFoundError(f"missing XSA: {xsa}")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"missing firmware source directory: {source_dir}")
    return BuildConfig(xsa=xsa, workspace=workspace, source_dir=source_dir,
                       cloud_root=cloud_root)


def enumerate_firmware_sources(source_dir: Path) -> list[Path]:
    source_dir = Path(source_dir).resolve()
    selected: list[Path] = []
    for section in ("common", "e06_net"):
        directory = source_dir / section
        if not directory.is_dir():
            raise FileNotFoundError(f"missing production firmware directory: {directory}")
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"symlink firmware source: {path}")
            relative = path.relative_to(source_dir)
            if path.is_file() and path.suffix in {".c", ".h"} and not any(
                part in {"tests", "test", "fakes", "fake_bsp"} for part in relative.parts
            ):
                selected.append(path.resolve())
    selected.sort(key=lambda path: path.relative_to(source_dir).as_posix())
    if not selected or not any(path.suffix == ".c" for path in selected):
        raise RuntimeError("no production firmware C sources selected")
    return selected


def prepare_workspace(
    workspace: Path, clean_generated: bool, *, cloud_root: Path = CLOUD_ROOT
) -> None:
    cloud_root = Path(cloud_root).resolve()
    workspace = _inside(Path(workspace), cloud_root, "workspace")
    expected = (cloud_root / EXPECTED_WORKSPACE_RELATIVE).resolve()
    if workspace != expected:
        raise ValueError(f"refusing to clean anything except Cloud_test/{EXPECTED_WORKSPACE_RELATIVE}")
    if workspace.exists():
        if not clean_generated:
            raise FileExistsError(
                f"workspace exists; pass --clean-generated to replace only {workspace}"
            )
        if not workspace.is_dir():
            raise ValueError(f"workspace is not a directory: {workspace}")
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)


def verify_vendor_manifest(
    manifest_path: Path, *, cloud_root: Path = CLOUD_ROOT
) -> dict[str, dict[str, object]]:
    cloud_root = Path(cloud_root).resolve()
    manifest_path = _inside(Path(manifest_path), cloud_root, "vendor manifest")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing vendor manifest: {manifest_path}")
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not records:
        raise RuntimeError("vendor manifest is empty or malformed")
    for name, record in records.items():
        try:
            copied = _inside(Path(record["copied_path"]), cloud_root, f"vendor item {name}")
            expected_size = int(record["bytes"])
            expected_hash = str(record["sha256"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"invalid vendor manifest record: {name}") from error
        if (not copied.is_file() or copied.stat().st_size != expected_size
                or _sha256(copied) != expected_hash):
            raise RuntimeError(f"vendor immutability check failed for {name}: {copied}")
    return records


def _canonical_json(value: object) -> bytes:
    """Serialize an identity payload without platform- or locale-dependent whitespace."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def compute_build_identity(config: BuildConfig) -> dict[str, object]:
    """Return the reproducible, non-self-referential firmware identity document.

    The advertised value hashes the compact canonical JSON bytes in
    ``canonical_payload``.  The payload contains the production source paths and
    byte identities, the copied data/hardware inputs consumed by the firmware,
    and the pinned Vitis build policy.  It deliberately excludes both the
    advertised digest and generated output identities.
    """
    records = verify_vendor_manifest(
        config.cloud_root / "vendor/source_manifest.json", cloud_root=config.cloud_root
    )
    missing = [name for name in IDENTITY_INPUTS if name not in records]
    if missing:
        raise RuntimeError(f"vendor manifest lacks firmware identity inputs: {missing}")
    production_sources = []
    for source in enumerate_firmware_sources(config.source_dir):
        production_sources.append({
            "path": source.relative_to(config.source_dir).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": _sha256(source),
        })
    copied_inputs = {}
    for name in IDENTITY_INPUTS:
        record = records[name]
        copied_inputs[name] = {
            "bytes": int(record["bytes"]),
            "sha256": str(record["sha256"]),
        }
    payload: dict[str, object] = {
        "schema": IDENTITY_SCHEMA,
        "inputs": {
            "production_sources": production_sources,
            "copied_vendor_inputs": copied_inputs,
        },
        "tool_policy": {
            "vitis_release": "2025.1",
            "cpu": config.cpu,
            "domain": config.domain,
            "os": config.os,
            "architecture": config.architecture,
            "compiler": "gcc",
            "libraries": [
                {"name": "xilffs", "policy_path": str(XILFFS_PATH)},
                {"name": "lwip220", "policy_path": str(LWIP220_PATH)},
            ],
        },
    }
    advertised = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if advertised == ZERO_SHA256:
        raise RuntimeError("computed forbidden zero firmware identity")
    return {
        "schema": IDENTITY_SCHEMA,
        "algorithm": "sha256",
        "canonicalization": IDENTITY_CANONICALIZATION,
        "advertised_sha256": advertised,
        "canonical_payload": payload,
    }


def write_build_identity_header(path: Path, identity: dict[str, object]) -> None:
    advertised = str(identity.get("advertised_sha256", ""))
    if len(advertised) != 64 or any(ch not in "0123456789abcdef" for ch in advertised):
        raise ValueError("firmware identity must be lowercase 64-hex")
    if advertised == ZERO_SHA256:
        raise ValueError("firmware identity must be nonzero")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "#ifndef E06_FIRMWARE_BUILD_IDENTITY_H\n"
        "#define E06_FIRMWARE_BUILD_IDENTITY_H\n\n"
        f'#define E06_FIRMWARE_SHA256 "{advertised}"\n'
        '#define E06_FIRMWARE_IDENTITY_ALGORITHM "sha256"\n\n'
        "#endif\n"
    )
    path.write_text(text, encoding="ascii")


def _copy_application_sources(config: BuildConfig, app_source: Path) -> list[Path]:
    app_source.mkdir(parents=True, exist_ok=True)
    for old in app_source.iterdir():
        # Vitis owns CMakeLists.txt, the linker script and user configuration
        # in this directory.  Replace only template application sources.
        if old.is_file() and old.suffix in {".c", ".h"}:
            old.unlink()
    copied = []
    used_names: set[str] = set()
    for source in enumerate_firmware_sources(config.source_dir):
        if source.name in used_names:
            raise RuntimeError(f"duplicate flattened firmware filename: {source.name}")
        used_names.add(source.name)
        destination = app_source / source.name
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def build_with_vitis(config: BuildConfig) -> Path:
    try:
        import vitis  # type: ignore
    except ImportError as error:
        raise RuntimeError("run this script with /opt/vivado/2025.1/Vitis/bin/vitis -s") from error

    manifest = config.cloud_root / "vendor/source_manifest.json"
    verify_vendor_manifest(manifest, cloud_root=config.cloud_root)
    identity = compute_build_identity(config)
    client = vitis.create_client()
    try:
        client.set_workspace(path=str(config.workspace))
        advanced = client.create_advanced_options_dict(dt_overlay="0")
        platform = client.create_platform_component(
            name="e06_net_platform",
            hw_design=str(config.xsa),
            os=config.os,
            cpu=config.cpu,
            domain_name=config.domain,
            generate_dtb=False,
            advanced_options=advanced,
            architecture=config.architecture,
            compiler="gcc",
        )
        domain = platform.get_domain(name=config.domain)
        for library, path in (("xilffs", XILFFS_PATH), ("lwip220", LWIP220_PATH)):
            if not path.is_dir():
                raise FileNotFoundError(f"missing Vitis BSP library {library}: {path}")
            status = domain.set_lib(lib_name=library, path=str(path))
            if status is False:
                raise RuntimeError(f"Vitis rejected BSP library {library}")
        platform.build()
        xpfm = config.workspace / "e06_net_platform/export/e06_net_platform/e06_net_platform.xpfm"
        if not xpfm.is_file():
            raise RuntimeError(f"platform build did not create XPFM: {xpfm}")
        app = client.create_app_component(
            name="e06_net",
            platform=str(xpfm),
            domain=config.domain,
            template="empty_application",
        )
        copied = _copy_application_sources(config, config.workspace / "e06_net/src")
        if not copied:
            raise RuntimeError("no firmware sources copied into application")
        write_build_identity_header(
            config.workspace / "e06_net/src/firmware_build_identity.h", identity
        )
        _atomic_json(config.workspace / "e06_net/firmware_build_identity.json", identity)
        app.build()
    finally:
        vitis.dispose()
    candidates = [
        config.workspace / "e06_net/build/e06_net.elf",
        config.workspace / "e06_net/build/Debug/e06_net.elf",
    ]
    elf = next((path for path in candidates if path.is_file() and path.stat().st_size), None)
    if elf is None:
        raise RuntimeError("Vitis build did not create a nonempty e06_net.elf at an explicit path")
    elf_bytes = elf.read_bytes()
    advertised = str(identity["advertised_sha256"])
    if advertised.encode("ascii") not in elf_bytes:
        raise RuntimeError("built ELF does not advertise the exact firmware build identity")
    if ZERO_SHA256.encode("ascii") in elf_bytes:
        raise RuntimeError("built ELF contains the forbidden zero firmware identity placeholder")
    verify_vendor_manifest(manifest, cloud_root=config.cloud_root)
    identity["built_artifact"] = {
        "path": str(elf.resolve()),
        "bytes": elf.stat().st_size,
        "sha256": _sha256(elf),
    }
    _atomic_json(config.workspace / "e06_net/firmware_build_identity.json", identity)
    _atomic_json(config.cloud_root / "build/e06_net_firmware_identity.json", identity)
    return elf


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    values = list(argv)
    if values and values[0] == "--":
        values = values[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xsa", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--clean-generated", action="store_true")
    return parser.parse_args(values)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    config = make_build_config(args.xsa, args.workspace, args.source_dir)
    prepare_workspace(config.workspace, args.clean_generated, cloud_root=config.cloud_root)
    elf = build_with_vitis(config)
    print(f"E06_NET_ELF={elf}")
    print(f"E06_NET_ELF_BYTES={elf.stat().st_size}")
    print(f"E06_NET_ELF_SHA256={_sha256(elf)}")
    identity = json.loads(
        (config.cloud_root / "build/e06_net_firmware_identity.json").read_text(encoding="utf-8")
    )
    print(f"E06_NET_FIRMWARE_IDENTITY={identity['advertised_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
