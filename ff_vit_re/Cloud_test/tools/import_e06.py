"""Copy the fixed E06 input set into an immutable, hash-verified bundle."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


VENDOR_ROOT = (Path(__file__).resolve().parents[1] / "vendor").resolve()

E06_FILES = {
    "xsa": "board_250mhz_advanced/workspace/e06m_platform/export/e06m_platform/hw/e06_measurement_250mhz.xsa",
    "bitstream": "board_250mhz_advanced/deploy/design_1_wrapper.bit",
    "fsbl": "board_250mhz_advanced/deploy/fsbl.elf",
    "pmufw": "board_250mhz_advanced/deploy/pmufw.elf",
    "weights": "inputs/weights.bin",
    "input": "inputs/input.bin",
    "output": "inputs/output.bin",
    "weight_layout": "board_250mhz_advanced/src/weight_layout.h",
    "inference_main": "board_250mhz_advanced/src/main.c",
    "power_main": "board_250mhz_advanced/power_src/main.c",
    "power_monitor_c": "board_250mhz_advanced/power_src/power_monitor.c",
    "power_monitor_h": "board_250mhz_advanced/power_src/power_monitor.h",
    "power_math_c": "board_250mhz_advanced/power_src/power_math.c",
    "power_math_h": "board_250mhz_advanced/power_src/power_math.h",
    "rail_map": "board_250mhz_advanced/power_src/zcu102_ina226_rails.csv",
}

E06_DESTINATIONS = {
    "xsa": "hw/e06_measurement_250mhz.xsa",
    "bitstream": "hw/design_1_wrapper.bit",
    "fsbl": "boot/fsbl.elf",
    "pmufw": "boot/pmufw.elf",
    "weights": "data/weights.bin",
    "input": "data/input.bin",
    "output": "data/output.bin",
    "weight_layout": "include/weight_layout.h",
    "inference_main": "reference_source/inference/main.c",
    "power_main": "reference_source/power/main.c",
    "power_monitor_c": "reference_source/power/power_monitor.c",
    "power_monitor_h": "reference_source/power/power_monitor.h",
    "power_math_c": "reference_source/power/power_math.c",
    "power_math_h": "reference_source/power/power_math.h",
    "rail_map": "reference_source/power/zcu102_ina226_rails.csv",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_components(path: Path, base: Path) -> None:
    current = base
    if current.is_symlink():
        raise ValueError(f"symlink source or destination: {current}")
    for part in path.relative_to(base).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink source or destination: {current}")


def import_e06(source_root: Path, destination: Path) -> dict[str, dict[str, object]]:
    """Copy only allowlisted files and return their provenance records."""
    source_root = Path(source_root).absolute()
    destination = Path(destination).absolute()
    try:
        destination.resolve().relative_to(VENDOR_ROOT)
    except ValueError as error:
        raise ValueError("destination must be within Cloud_test/vendor") from error
    if destination.resolve() == VENDOR_ROOT:
        raise ValueError("destination must be within Cloud_test/vendor, below its root")

    prepared = {}
    used_destinations = set()
    for key, source_relative in E06_FILES.items():
        source = source_root / source_relative
        _reject_symlink_components(source, source_root)
        if not source.is_file():
            raise FileNotFoundError(f"missing E06 allowlist file: {source}")
        target = destination / E06_DESTINATIONS[key]
        target_resolved = target.resolve()
        try:
            target_resolved.relative_to(destination.resolve())
        except ValueError as error:
            raise ValueError(f"destination outside bundle: {target}") from error
        _reject_symlink_components(target, destination)
        if target_resolved in used_destinations:
            raise ValueError(f"duplicate destination path: {target}")
        used_destinations.add(target_resolved)
        digest = _sha256(source)
        size = source.stat().st_size
        if target.exists() and (not target.is_file() or target.stat().st_size != size or _sha256(target) != digest):
            raise FileExistsError(f"different file already exists at {target}")
        prepared[key] = (source, target, size, digest)

    records: dict[str, dict[str, object]] = {}
    for key, (source, target, size, digest) in prepared.items():
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if target.stat().st_size != size or _sha256(target) != digest:
            raise OSError(f"source/destination hash mismatch: {target}")
        records[key] = {
            "source": str(source.resolve()),
            "copied_path": str(target.resolve()),
            "bytes": size,
            "sha256": digest,
        }
    return records


def _write_json_atomically(path: Path, value: dict[str, dict[str, object]]) -> None:
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.is_symlink():
        raise ValueError(f"symlink manifest path: {path}")
    if path.exists():
        if path.read_bytes() == encoded:
            return
        raise FileExistsError(f"different manifest already exists at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e06-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    try:
        manifest.relative_to(VENDOR_ROOT)
    except ValueError as error:
        parser.error(f"manifest must be within Cloud_test/vendor: {error}")
    records = import_e06(args.e06_root, args.destination)
    _write_json_atomically(manifest, records)


if __name__ == "__main__":
    main()
