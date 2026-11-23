"""Deterministic expansion of the frozen ImageNet QAT subset to 100/class."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SCHEMA = "imagenet1k.train_sample.v1"
IMAGE_SUFFIXES = frozenset({".jpeg", ".jpg", ".png"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readable(path: Path) -> None:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            image.load()
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise ValueError(f"unreadable selected image: {path}") from error


def _load_base(path: Path) -> list[dict[str, Any]]:
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read base QAT manifest: {path}") from error
    if not records or any(not isinstance(record, Mapping) for record in records):
        raise ValueError("base QAT manifest is empty or malformed")
    return [dict(record) for record in records]


def build_expanded_records(
    base_manifest: str | Path,
    train_root: str | Path,
    *,
    seed: int,
    per_class: int = 100,
    expected_classes: int = 1000,
) -> list[dict[str, Any]]:
    """Keep every base path and sample remaining sorted candidates per class.

    For each class, the additional sampler is ``random.Random(class_seed)``
    where ``class_seed`` is the first 128 bits of
    ``SHA256('<seed>:<class_name>')``. It samples without replacement from the
    lexicographically sorted candidates after removing all base-manifest paths.
    The final records are sorted by class label and relative path.
    """

    root = Path(train_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"training root is not a directory: {root}")
    base = _load_base(Path(base_manifest).expanduser().resolve())
    class_names = sorted({str(record.get("class_name", "")) for record in base})
    if len(class_names) != expected_classes or not all(class_names):
        raise ValueError(f"base manifest must describe exactly {expected_classes} classes")
    labels = {}
    by_class: dict[str, list[dict[str, Any]]] = {name: [] for name in class_names}
    for record in base:
        class_name = record.get("class_name")
        label = record.get("label")
        if class_name not in by_class or not isinstance(label, int) or isinstance(label, bool):
            raise ValueError("base manifest contains invalid class or label")
        if class_name in labels and labels[class_name] != label:
            raise ValueError("base manifest class has inconsistent labels")
        labels[class_name] = label
        by_class[class_name].append(record)
    if sorted(labels.values()) != list(range(expected_classes)):
        raise ValueError("base manifest labels must be contiguous")
    base_counts = Counter(record["class_name"] for record in base)
    if len(set(base_counts.values())) != 1 or next(iter(base_counts.values())) >= per_class:
        raise ValueError("base manifest must be uniformly smaller than target per-class count")

    output = []
    for class_name in class_names:
        class_dir = root / class_name
        if not class_dir.is_dir():
            raise ValueError(f"missing ImageNet class directory: {class_dir}")
        existing = by_class[class_name]
        existing_paths = {Path(record["path"]).expanduser().resolve() for record in existing}
        if len(existing_paths) != len(existing):
            raise ValueError(f"duplicate base path in class {class_name}")
        candidates = sorted(
            (path.resolve() for path in class_dir.iterdir()
             if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda path: path.name,
        )
        remaining = [path for path in candidates if path not in existing_paths]
        additional_count = per_class - len(existing)
        if len(remaining) < additional_count:
            raise ValueError(f"class {class_name} lacks {additional_count} additional images")
        material = f"{int(seed)}:{class_name}".encode("utf-8")
        class_seed = int.from_bytes(hashlib.sha256(material).digest()[:16], "big")
        selected = random.Random(class_seed).sample(remaining, additional_count)
        selected_paths = existing_paths.union(selected)
        for path in sorted(selected_paths, key=lambda item: item.name):
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as error:
                raise ValueError(f"base path escapes training root: {path}") from error
            _readable(path)
            output.append(
                {
                    "schema": SCHEMA,
                    "path": str(path),
                    "relative_path": relative,
                    "class_name": class_name,
                    "label": int(labels[class_name]),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    if len(output) != expected_classes * per_class:
        raise ValueError("expanded manifest has wrong total count")
    if len({record["path"] for record in output}) != len(output):
        raise ValueError("expanded manifest contains duplicate paths")
    return output


def jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        + b"\n"
        for record in records
    )
