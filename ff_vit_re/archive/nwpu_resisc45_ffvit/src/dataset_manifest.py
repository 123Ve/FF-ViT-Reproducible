"""Build and validate reproducible NWPU-RESISC45 dataset manifests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Iterable, Mapping

from PIL import Image


SPLIT_COUNTS = {"train": 540, "val": 60, "test": 100}
CALIBRATION_PER_CLASS = 32
SCHEMA_VERSION = 1
MANIFEST_FILENAMES = (
    "classes.json",
    "class_to_idx.json",
    "train.json",
    "val.json",
    "test.json",
    "calibration.json",
    "duplicate_groups.json",
)


@dataclass(frozen=True, slots=True)
class ImageRecord:
    """Audited, source-relative identity and metadata for one input image."""

    relative_path: str
    class_name: str
    label: int
    byte_size: int
    sha256: str
    width: int
    height: int
    mode: str


@dataclass(frozen=True, slots=True)
class SplitManifest:
    """Immutable split assignment plus its deterministic calibration subset."""

    classes: tuple[str, ...]
    seed: int
    splits: Mapping[str, tuple[ImageRecord, ...]]
    calibration: tuple[ImageRecord, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sorted_class_dirs(root: Path) -> tuple[list[str], Path, Path]:
    train_root = root / "train" / "train"
    test_root = root / "test" / "test"
    if not train_root.is_dir() or not test_root.is_dir():
        raise ValueError(f"expected train/train and test/test below {root}")
    train_classes = sorted(path.name for path in train_root.iterdir() if path.is_dir())
    test_classes = sorted(path.name for path in test_root.iterdir() if path.is_dir())
    if train_classes != test_classes:
        raise ValueError("train and test class directories differ")
    return train_classes, train_root, test_root


def build_inventory(root: Path) -> list[ImageRecord]:
    """Decode and inventory every source JPEG without changing the source tree."""

    root = root.resolve()
    classes, train_root, test_root = _sorted_class_dirs(root)
    records: list[ImageRecord] = []
    for label, class_name in enumerate(classes):
        paths: list[Path] = []
        for class_root in (train_root / class_name, test_root / class_name):
            files = sorted(path for path in class_root.iterdir() if path.is_file())
            unexpected = [path for path in files if path.suffix.lower() != ".jpg"]
            if unexpected:
                raise ValueError(f"non-JPEG source files in {class_root}: {unexpected[0].name}")
            paths.extend(files)
        if len(paths) != sum(SPLIT_COUNTS.values()):
            raise ValueError(
                f"class {class_name} has {len(paths)} files; expected {sum(SPLIT_COUNTS.values())}"
            )
        for path in paths:
            try:
                with Image.open(path) as image:
                    image.load()
                    width, height, mode = image.width, image.height, image.mode
            except OSError as error:
                raise ValueError(f"cannot decode image {path}") from error
            records.append(
                ImageRecord(
                    relative_path=path.relative_to(root).as_posix(),
                    class_name=class_name,
                    label=label,
                    byte_size=path.stat().st_size,
                    sha256=_sha256(path),
                    width=width,
                    height=height,
                    mode=mode,
                )
            )
    return records


def _rank(seed: int, namespace: str, value: str) -> bytes:
    return hashlib.sha256(f"{seed}:{namespace}:{value}".encode("utf-8")).digest()


def _choose_groups(
    groups: list[tuple[ImageRecord, ...]], target: int, seed: int, namespace: str
) -> tuple[tuple[ImageRecord, ...], ...]:
    """Choose whole hash groups whose sizes exactly reach ``target``."""

    ordered = sorted(
        groups,
        key=lambda group: (_rank(seed, namespace, group[0].sha256), group[0].sha256),
    )
    choices: dict[int, tuple[int, ...]] = {0: ()}
    for index, group in enumerate(ordered):
        group_size = len(group)
        for subtotal, selected in sorted(list(choices.items()), reverse=True):
            total = subtotal + group_size
            if total <= target and total not in choices:
                choices[total] = selected + (index,)
    if target not in choices:
        available = sum(len(group) for group in groups)
        raise ValueError(
            f"cannot allocate {target} whole duplicate-group paths from {available} paths"
        )
    return tuple(ordered[index] for index in choices[target])


def _class_groups(records: Iterable[ImageRecord]) -> list[tuple[ImageRecord, ...]]:
    grouped: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        grouped[record.sha256].append(record)
    return [tuple(sorted(group, key=lambda record: record.relative_path)) for _, group in sorted(grouped.items())]


def _records_sort_key(record: ImageRecord) -> tuple[int, str]:
    return record.label, record.relative_path


def make_splits(records: Iterable[ImageRecord], seed: int = 20260923) -> SplitManifest:
    """Allocate every per-class SHA-256 group to the fixed split contract."""

    inventory = tuple(sorted(records, key=_records_sort_key))
    classes = tuple(sorted({record.class_name for record in inventory}))
    labels = {class_name: index for index, class_name in enumerate(classes)}
    if len(classes) != 45:
        raise ValueError(f"expected 45 classes, found {len(classes)}")
    by_class: dict[str, list[ImageRecord]] = defaultdict(list)
    hashes_to_classes: dict[str, set[str]] = defaultdict(set)
    for record in inventory:
        by_class[record.class_name].append(record)
        hashes_to_classes[record.sha256].add(record.class_name)
        if record.label != labels[record.class_name]:
            raise ValueError(f"label mismatch for {record.relative_path}")
    cross_label = [digest for digest, names in hashes_to_classes.items() if len(names) > 1]
    if cross_label:
        raise ValueError(f"identical content appears under multiple classes: {cross_label[0]}")

    allocated: dict[str, list[ImageRecord]] = {name: [] for name in SPLIT_COUNTS}
    calibration: list[ImageRecord] = []
    for class_name in classes:
        class_records = by_class[class_name]
        if len(class_records) != sum(SPLIT_COUNTS.values()):
            raise ValueError(f"class {class_name} has {len(class_records)} records, expected 700")
        groups = _class_groups(class_records)
        train_groups = _choose_groups(groups, SPLIT_COUNTS["train"], seed, f"{class_name}:train")
        train_digests = {group[0].sha256 for group in train_groups}
        remaining = [group for group in groups if group[0].sha256 not in train_digests]
        val_groups = _choose_groups(remaining, SPLIT_COUNTS["val"], seed, f"{class_name}:val")
        val_digests = {group[0].sha256 for group in val_groups}
        test_groups = [group for group in remaining if group[0].sha256 not in val_digests]
        if sum(len(group) for group in test_groups) != SPLIT_COUNTS["test"]:
            raise ValueError(f"class {class_name} cannot satisfy exact test allocation")
        allocated["train"].extend(record for group in train_groups for record in group)
        allocated["val"].extend(record for group in val_groups for record in group)
        allocated["test"].extend(record for group in test_groups for record in group)
        class_train = [record for group in train_groups for record in group]
        calibration.extend(
            sorted(
                class_train,
                key=lambda record: (
                    _rank(seed, f"{class_name}:calibration", record.sha256 + record.relative_path),
                    record.relative_path,
                ),
            )[:CALIBRATION_PER_CLASS]
        )

    manifest = SplitManifest(
        classes=classes,
        seed=seed,
        splits=MappingProxyType(
            {name: tuple(sorted(items, key=_records_sort_key)) for name, items in allocated.items()}
        ),
        calibration=tuple(sorted(calibration, key=_records_sort_key)),
    )
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid generated manifest: " + "; ".join(errors))
    return manifest


def validate_manifest(manifest: SplitManifest) -> list[str]:
    """Return contract violations; an empty list means the manifest is valid."""

    errors: list[str] = []
    classes = manifest.classes
    if len(classes) != 45 or tuple(sorted(classes)) != classes or len(set(classes)) != len(classes):
        errors.append("classes must be 45 unique bytewise-sorted names")
    if set(manifest.splits) != set(SPLIT_COUNTS):
        errors.append("splits must contain exactly train, val, and test")
        return errors

    labels = {class_name: label for label, class_name in enumerate(classes)}
    all_paths: set[str] = set()
    hash_splits: dict[str, set[str]] = defaultdict(set)
    train_records_by_path: dict[str, ImageRecord] = {}
    for split, expected_per_class in SPLIT_COUNTS.items():
        records = manifest.splits[split]
        if len(records) != expected_per_class * len(classes):
            errors.append(f"{split} total is {len(records)}, expected {expected_per_class * len(classes)}")
        counts = Counter(record.class_name for record in records)
        for label, class_name in enumerate(classes):
            if counts[class_name] != expected_per_class:
                errors.append(
                    f"{split}/{class_name} is {counts[class_name]}, expected {expected_per_class}"
                )
        for record in records:
            expected_label = labels.get(record.class_name)
            if expected_label is None:
                errors.append(f"unknown class for {record.relative_path}: {record.class_name}")
            elif record.label != expected_label:
                errors.append(f"label mismatch for {record.relative_path}")
            errors.extend(_validate_record_path(record))
            if (record.width, record.height, record.mode) != (256, 256, "RGB"):
                errors.append(f"invalid image metadata for {record.relative_path}")
            if record.byte_size <= 0 or len(record.sha256) != 64:
                errors.append(f"invalid byte size or SHA-256 for {record.relative_path}")
            if record.relative_path in all_paths:
                errors.append(f"path occurs more than once: {record.relative_path}")
            all_paths.add(record.relative_path)
            hash_splits[record.sha256].add(split)
            if split == "train":
                train_records_by_path[record.relative_path] = record
    crossing = sorted(digest for digest, splits in hash_splits.items() if len(splits) > 1)
    if crossing:
        errors.append(f"SHA-256 group crosses splits: {crossing[0]}")

    calibration = manifest.calibration
    if len(calibration) != CALIBRATION_PER_CLASS * len(classes):
        errors.append(
            f"calibration total is {len(calibration)}, expected {CALIBRATION_PER_CLASS * len(classes)}"
        )
    calibration_counts = Counter(record.class_name for record in calibration)
    calibration_paths = {record.relative_path for record in calibration}
    if len(calibration_paths) != len(calibration):
        errors.append("calibration contains duplicate paths")
    for class_name in classes:
        if calibration_counts[class_name] != CALIBRATION_PER_CLASS:
            errors.append(
                f"calibration/{class_name} is {calibration_counts[class_name]}, expected {CALIBRATION_PER_CLASS}"
            )
    for record in calibration:
        errors.extend(_validate_record_path(record))
        train_record = train_records_by_path.get(record.relative_path)
        if train_record is None:
            errors.append(f"calibration includes record outside train: {record.relative_path}")
        elif record != train_record:
            errors.append(f"calibration identity differs from train: {record.relative_path}")
    return errors


def _validate_record_path(record: ImageRecord) -> list[str]:
    """Validate the frozen source-relative layout and class directory identity."""

    relative_path = record.relative_path
    if not isinstance(relative_path, str):
        return ["record path must be a string"]
    path = PurePosixPath(relative_path)
    if (
        path.is_absolute()
        or relative_path != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return [f"path is not normalized and source-relative: {relative_path}"]
    parts = path.parts
    if (
        len(parts) != 4
        or parts[0] not in {"train", "test"}
        or parts[1] != parts[0]
        or parts[2] != record.class_name
        or not parts[3].endswith(".jpg")
        or len(parts[3]) == len(".jpg")
    ):
        return [f"path is not a supported class-relative JPEG: {relative_path}"]
    return []


def _record_payload(record: ImageRecord) -> dict[str, object]:
    return asdict(record)


def _manifest_payload(manifest: SplitManifest, split: str, records: tuple[ImageRecord, ...]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": manifest.seed,
        "split": split,
        "classes": list(manifest.classes),
        "records": [_record_payload(record) for record in records],
    }


def _duplicate_groups(manifest: SplitManifest) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[str, ImageRecord]]] = defaultdict(list)
    for split, records in manifest.splits.items():
        for record in records:
            grouped[record.sha256].append((split, record))
    return [
        {
            "sha256": digest,
            "count": len(items),
            "class_names": sorted({record.class_name for _, record in items}),
            "relative_paths": sorted(record.relative_path for _, record in items),
            "split": next(iter({split for split, _ in items})),
        }
        for digest, items in sorted(grouped.items())
        if len(items) > 1
    ]


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(_json_bytes(payload))
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _manifest_payloads(manifest: SplitManifest) -> dict[str, object]:
    duplicate_groups = _duplicate_groups(manifest)
    return {
        "classes.json": list(manifest.classes),
        "class_to_idx.json": {
            class_name: label for label, class_name in enumerate(manifest.classes)
        },
        "train.json": _manifest_payload(manifest, "train", manifest.splits["train"]),
        "val.json": _manifest_payload(manifest, "val", manifest.splits["val"]),
        "test.json": _manifest_payload(manifest, "test", manifest.splits["test"]),
        "calibration.json": _manifest_payload(manifest, "calibration", manifest.calibration),
        "duplicate_groups.json": {
            "schema_version": SCHEMA_VERSION,
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_path_count": sum(group["count"] for group in duplicate_groups),
            "groups": duplicate_groups,
        },
    }


def write_manifests(manifest: SplitManifest, output: Path) -> dict[str, str]:
    """Stage, byte-verify, and atomically publish a never-overwritten manifest bundle."""

    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("refusing to serialize invalid manifest: " + "; ".join(errors))
    output = Path(output)
    if os.path.lexists(output):
        raise ValueError(f"refusing to reuse existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    payloads = _manifest_payloads(manifest)
    expected_hashes = {
        name: hashlib.sha256(_json_bytes(payload)).hexdigest() for name, payload in payloads.items()
    }
    stage.mkdir()
    try:
        for name in MANIFEST_FILENAMES:
            _write_json(stage / name, payloads[name])
        actual_files = {path.name for path in stage.iterdir()}
        if actual_files != set(MANIFEST_FILENAMES):
            raise ValueError("staged manifest has an unexpected file set")
        actual_hashes = {name: _sha256(stage / name) for name in MANIFEST_FILENAMES}
        if actual_hashes != expected_hashes:
            raise ValueError("staged manifest bytes do not match the verified payload")
        # The staging directory is a sibling, so this rename is one filesystem atomic publish.
        stage.replace(output)
        return {name: actual_hashes[name] for name in sorted(actual_hashes)}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
