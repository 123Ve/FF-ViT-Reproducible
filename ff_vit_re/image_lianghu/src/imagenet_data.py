"""Stable, validated ImageNet-1K dataset interfaces.

The public functions in this module deliberately validate dataset completeness at
the boundary so later training and evaluation stages cannot silently consume a
partial or non-deterministically ordered dataset.
"""

from __future__ import annotations

import hashlib
import io
import random
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from numbers import Integral
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from PIL import Image, UnidentifiedImageError


IMAGENET_CLASS_COUNT = 1_000
IMAGENET_VALIDATION_COUNT = 50_000
TRAIN_SAMPLE_SCHEMA = "imagenet1k.train_sample.v1"
_IMAGE_SUFFIXES = frozenset({".jpeg", ".jpg", ".png"})


def _root_directory(path: str | Path, description: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{description} is not a directory: {root}")
    return root


def _validate_mapping_shape(
    class_mapping: Mapping[str, int], *, expected_count: int | None
) -> None:
    if not isinstance(class_mapping, Mapping):
        raise TypeError("class_mapping must be a mapping")
    if expected_count is not None and len(class_mapping) != expected_count:
        raise ValueError(
            f"class mapping must contain exactly {expected_count} entries; "
            f"found {len(class_mapping)}"
        )
    keys = list(class_mapping)
    if not all(isinstance(key, str) and key for key in keys):
        raise ValueError("class mapping keys must be non-empty strings")
    if keys != sorted(keys):
        raise ValueError("class mapping keys must be in canonical lexicographic order")
    values = list(class_mapping.values())
    if (
        any(not isinstance(value, Integral) or isinstance(value, bool) for value in values)
        or len(set(values)) != len(values)
        or sorted(values) != list(range(len(values)))
    ):
        raise ValueError("class mapping values must be unique contiguous integers from zero")


def validate_class_mapping(class_mapping: Mapping[str, int]) -> None:
    """Reject a class map that is not the canonical 1,000-class shape."""

    _validate_mapping_shape(class_mapping, expected_count=IMAGENET_CLASS_COUNT)


def build_class_mapping(train_root: str | Path) -> dict[str, int]:
    """Return the canonical lexicographic WNID-to-label mapping.

    Only direct child directories participate. The result is rejected unless it
    has exactly 1,000 entries, preventing partial extractions from becoming a
    source of truth.
    """

    root = _root_directory(train_root, "train root")
    class_names = sorted(path.name for path in root.iterdir() if path.is_dir())
    mapping = {class_name: index for index, class_name in enumerate(class_names)}
    validate_class_mapping(mapping)
    return mapping


def _verify_readable_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            with image.convert("RGB") as decoded:
                decoded.load()
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise ValueError(f"unreadable image: {path}") from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_subset(
    records: Sequence[Mapping[str, Any]],
    class_mapping: Mapping[str, int],
    per_class: int,
    *,
    require_readable: bool = True,
) -> None:
    """Validate uniqueness, class balance, labels, and image readability."""

    if not isinstance(per_class, Integral) or isinstance(per_class, bool) or per_class <= 0:
        raise ValueError("per_class must be a positive integer")
    _validate_mapping_shape(class_mapping, expected_count=None)
    expected_total = len(class_mapping) * int(per_class)
    if len(records) != expected_total:
        raise ValueError(
            f"subset requires {expected_total} records ({per_class} per class); "
            f"found {len(records)}"
        )

    paths = [str(record.get("path", "")) for record in records]
    relative_paths = [str(record.get("relative_path", "")) for record in records]
    if any(not path for path in paths) or len(set(paths)) != len(paths):
        raise ValueError("duplicate subset path or empty path")
    if any(not path for path in relative_paths) or len(set(relative_paths)) != len(relative_paths):
        raise ValueError("duplicate subset path or empty relative path")

    counts: Counter[str] = Counter()
    for record in records:
        class_name = record.get("class_name")
        label = record.get("label")
        if class_name not in class_mapping or label != class_mapping[class_name]:
            raise ValueError(f"subset record has inconsistent class/label: {record!r}")
        counts[str(class_name)] += 1
        if require_readable:
            _verify_readable_image(Path(str(record["path"])))

    expected_counts = {class_name: int(per_class) for class_name in class_mapping}
    if dict(counts) != expected_counts:
        raise ValueError(
            f"subset per-class counts do not match {per_class}: "
            f"observed {dict(sorted(counts.items()))}"
        )


def select_per_class(
    train_root: str | Path,
    class_mapping: Mapping[str, int],
    per_class: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Select a deterministic, balanced subset from sorted relative paths.

    Each class receives an independent PRNG seeded from SHA-256 of
    ``"<seed>:<class_name>"``. This prevents filesystem enumeration order and
    Python's randomized string hash from affecting the result.
    """

    root = _root_directory(train_root, "train root")
    _validate_mapping_shape(class_mapping, expected_count=None)
    if not isinstance(per_class, Integral) or isinstance(per_class, bool) or per_class <= 0:
        raise ValueError("per_class must be a positive integer")
    if not isinstance(seed, Integral) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")

    records: list[dict[str, Any]] = []
    for class_name, label in class_mapping.items():
        class_dir = root / class_name
        if not class_dir.is_dir():
            raise ValueError(f"missing class directory: {class_dir}")
        candidates = sorted(
            (
                path
                for path in class_dir.iterdir()
                if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES
            ),
            key=lambda path: path.name,
        )
        if len(candidates) < per_class:
            raise ValueError(
                f"class {class_name} has {len(candidates)} images; selection requires {per_class}"
            )
        seed_material = f"{int(seed)}:{class_name}".encode("utf-8")
        class_seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:16], "big")
        selected = random.Random(class_seed).sample(candidates, int(per_class))
        for path in sorted(selected, key=lambda candidate: candidate.name):
            _verify_readable_image(path)
            records.append(
                {
                    "schema": TRAIN_SAMPLE_SCHEMA,
                    "path": str(path.resolve()),
                    "relative_path": path.relative_to(root).as_posix(),
                    "class_name": class_name,
                    "label": int(label),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )

    validate_subset(records, class_mapping, int(per_class), require_readable=False)
    return records


def _decode_parquet_image(image_value: Any, source: str) -> Image.Image:
    if not isinstance(image_value, dict):
        raise ValueError(f"invalid Parquet image value at {source}")
    encoded = image_value.get("bytes")
    if not isinstance(encoded, (bytes, bytearray, memoryview)):
        raise ValueError(f"Parquet image has no encoded bytes at {source}")
    try:
        with Image.open(io.BytesIO(bytes(encoded))) as opened:
            image = opened.convert("RGB")
            image.load()
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise ValueError(f"unreadable Parquet image at {source}") from error
    return image


def iter_parquet_validation(
    parquet_root: str | Path, class_mapping: Mapping[str, int]
) -> Iterator[tuple[Image.Image, int, str]]:
    """Yield decoded validation images and enforce the official 50,000 rows.

    Files and rows are traversed deterministically. The completeness assertion is
    evaluated when the iterator is exhausted, as required for official metrics.
    """

    root = _root_directory(parquet_root, "validation Parquet root")
    validate_class_mapping(class_mapping)
    parquet_files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not parquet_files:
        raise ValueError(f"no Parquet files found under {root}")

    count = 0
    seen_ids: set[str] = set()
    for parquet_path in parquet_files:
        relative_file = parquet_path.relative_to(root).as_posix()
        parquet_file = pq.ParquetFile(parquet_path)
        if not {"image", "label"}.issubset(parquet_file.schema_arrow.names):
            raise ValueError(f"Parquet file lacks image/label columns: {parquet_path}")
        row_in_file = 0
        for batch in parquet_file.iter_batches(batch_size=256, columns=["image", "label"]):
            for row in batch.to_pylist():
                raw_label = row.get("label")
                if (
                    not isinstance(raw_label, Integral)
                    or isinstance(raw_label, bool)
                    or not 0 <= int(raw_label) < IMAGENET_CLASS_COUNT
                ):
                    raise ValueError(
                        f"invalid ImageNet label {raw_label!r} at "
                        f"{relative_file} row {row_in_file}"
                    )
                image_value = row.get("image")
                source_path = image_value.get("path") if isinstance(image_value, dict) else None
                source_component = (
                    str(source_path)
                    if isinstance(source_path, str) and source_path
                    else f"row-{row_in_file:08d}"
                )
                stable_id = f"{relative_file}:{source_component}"
                if stable_id in seen_ids:
                    raise ValueError(f"duplicate validation stable_id: {stable_id}")
                seen_ids.add(stable_id)
                image = _decode_parquet_image(image_value, stable_id)
                yield image, int(raw_label), stable_id
                count += 1
                row_in_file += 1

    if count != IMAGENET_VALIDATION_COUNT:
        raise ValueError(
            f"validation set must contain exactly {IMAGENET_VALIDATION_COUNT} records; "
            f"found {count}"
        )
