"""Metadata-bound deterministic expansion of an inherited QAT manifest."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SCHEMA = "imagenet1k.train_sample_metadata.v1"
IMAGE_SUFFIXES = frozenset({".jpeg", ".jpg", ".png"})


def validate_uniform_capacity(
    train_root: str | Path, class_names: Sequence[str], *, per_class: int
) -> dict[str, int]:
    """Validate every class has enough image candidates before manifest work starts."""
    root = Path(train_root).expanduser().resolve()
    counts = {}
    for class_name in sorted(str(name) for name in class_names):
        directory = root / class_name
        count = sum(
            path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            for path in directory.iterdir()
        ) if directory.is_dir() else 0
        counts[class_name] = count
        if count < per_class:
            raise ValueError(
                f"class {class_name} has {count} image candidates; requires {per_class}"
            )
    return counts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decode(path: Path) -> None:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            image.load()
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise ValueError(f"unreadable spot-check image: {path}") from error


def build_metadata_expansion(
    base_manifest: str | Path,
    train_root: str | Path,
    *,
    seed: int,
    per_class: int,
    expected_classes: int = 1000,
    spot_checks_per_class: int = 1,
) -> list[dict[str, Any]]:
    root = Path(train_root).expanduser().resolve()
    base_path = Path(base_manifest).expanduser().resolve()
    records = [json.loads(line) for line in base_path.read_text(encoding="utf-8").splitlines() if line]
    if any(not isinstance(item, Mapping) for item in records):
        raise ValueError("base manifest is malformed")
    counts = Counter(str(item.get("class_name", "")) for item in records)
    if len(counts) != expected_classes or len(set(counts.values())) != 1:
        raise ValueError("base manifest class balance is invalid")
    inherited_per_class = next(iter(counts.values()))
    if not inherited_per_class < per_class or not 0 <= spot_checks_per_class <= per_class - inherited_per_class:
        raise ValueError("target count or spot-check count is invalid")
    labels = {str(item["class_name"]): int(item["label"]) for item in records}
    if sorted(labels.values()) != list(range(expected_classes)):
        raise ValueError("base labels are not canonical contiguous integers")
    by_class = {name: [] for name in sorted(counts)}
    for item in records:
        by_class[str(item["class_name"])].append(dict(item))
    validate_uniform_capacity(root, tuple(by_class), per_class=per_class)

    output = [dict(item) for item in records]
    for class_name in sorted(by_class):
        directory = root / class_name
        inherited = {Path(item["path"]).expanduser().resolve() for item in by_class[class_name]}
        candidates = sorted(
            (path.resolve() for path in directory.iterdir()
             if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and path.resolve() not in inherited),
            key=lambda path: path.name,
        )
        needed = per_class - inherited_per_class
        material = f"{int(seed)}:{class_name}".encode("utf-8")
        class_seed = int.from_bytes(hashlib.sha256(material).digest()[:16], "big")
        selected = sorted(random.Random(class_seed).sample(candidates, needed), key=lambda path: path.name)
        spot_paths = set(selected[:spot_checks_per_class])
        for path in selected:
            stat = path.stat()
            if stat.st_size <= 0:
                raise ValueError(f"selected image is empty: {path}")
            checked = path in spot_paths
            if checked:
                _decode(path)
            output.append(
                {
                    "schema": SCHEMA,
                    "path": str(path),
                    "relative_path": path.relative_to(root).as_posix(),
                    "class_name": class_name,
                    "label": labels[class_name],
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": _sha256(path) if checked else None,
                    "readability_checked": checked,
                }
            )
    output.sort(key=lambda item: (int(item["label"]), str(item["relative_path"])))
    if len(output) != expected_classes * per_class or len({item["path"] for item in output}) != len(output):
        raise ValueError("expanded manifest count or uniqueness mismatch")
    return output


def build_metadata_expansion_with_resampling(
    base_manifest: str | Path,
    train_root: str | Path,
    *,
    seed: int,
    per_class: int,
    expected_classes: int = 1000,
    spot_checks_per_class: int = 1,
) -> list[dict[str, Any]]:
    """Expand uniformly and deterministically resample only capacity-short classes.

    Repeated records reference the original read-only image path and carry an
    explicit resample ordinal; no image data is copied.
    """

    root = Path(train_root).expanduser().resolve()
    base_path = Path(base_manifest).expanduser().resolve()
    records = [json.loads(line) for line in base_path.read_text(encoding="utf-8").splitlines() if line]
    counts = Counter(str(item.get("class_name", "")) for item in records)
    if len(counts) != expected_classes or len(set(counts.values())) != 1:
        raise ValueError("base manifest class balance is invalid")
    inherited_per_class = next(iter(counts.values()))
    if not inherited_per_class < per_class or not 0 <= spot_checks_per_class <= per_class - inherited_per_class:
        raise ValueError("target count or spot-check count is invalid")
    labels = {str(item["class_name"]): int(item["label"]) for item in records}
    if sorted(labels.values()) != list(range(expected_classes)):
        raise ValueError("base labels are not canonical contiguous integers")
    by_class = {name: [] for name in sorted(counts)}
    for item in records:
        by_class[str(item["class_name"])].append(dict(item))
    capacity = validate_uniform_capacity(root, tuple(by_class), per_class=inherited_per_class)

    output: list[dict[str, Any]] = []
    for class_name in sorted(by_class):
        inherited_records = [dict(item) for item in by_class[class_name]]
        inherited = {Path(item["path"]).expanduser().resolve() for item in inherited_records}
        candidates = sorted(
            (path.resolve() for path in (root / class_name).iterdir()
             if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and path.resolve() not in inherited),
            key=lambda path: path.name,
        )
        material = f"{int(seed)}:{class_name}".encode("utf-8")
        class_seed = int.from_bytes(hashlib.sha256(material).digest()[:16], "big")
        generator = random.Random(class_seed)
        unique_needed = min(per_class - inherited_per_class, len(candidates))
        selected = sorted(generator.sample(candidates, unique_needed), key=lambda path: path.name)
        spot_paths = set(selected[: min(spot_checks_per_class, len(selected))])
        additions = []
        for path in selected:
            stat = path.stat()
            if stat.st_size <= 0:
                raise ValueError(f"selected image is empty: {path}")
            checked = path in spot_paths
            if checked:
                _decode(path)
            additions.append(
                {
                    "schema": SCHEMA,
                    "path": str(path),
                    "relative_path": path.relative_to(root).as_posix(),
                    "class_name": class_name,
                    "label": labels[class_name],
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": _sha256(path) if checked else None,
                    "readability_checked": checked,
                }
            )
        class_records = inherited_records + additions
        expected_unique = min(per_class, capacity[class_name])
        if len(class_records) != expected_unique:
            raise ValueError(f"candidate accounting mismatch for class {class_name}")
        deficit = per_class - len(class_records)
        repeat_order = list(range(len(class_records)))
        generator.shuffle(repeat_order)
        repeats = []
        for ordinal in range(deficit):
            source = dict(class_records[repeat_order[ordinal % len(repeat_order)]])
            source["schema"] = "imagenet1k.train_sample_resample.v1"
            source["resample_ordinal"] = ordinal
            source["resampled_from_path"] = source["path"]
            repeats.append(source)
        output.extend(class_records)
        output.extend(repeats)
    output.sort(
        key=lambda item: (
            int(item["label"]),
            str(item["relative_path"]),
            int(item.get("resample_ordinal", -1)),
        )
    )
    if len(output) != expected_classes * per_class:
        raise ValueError("resampled manifest count mismatch")
    return output


def jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        + b"\n"
        for record in records
    )
