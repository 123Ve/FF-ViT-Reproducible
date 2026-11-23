"""Load frozen Task 1 manifests into safe, manifest-backed torch datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .dataset_manifest import ImageRecord, SplitManifest, validate_manifest


MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
SPLIT_NAMES = ("train", "val", "test", "calibration")
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ManifestBundle:
    classes: tuple[str, ...]
    seed: int
    records: Mapping[str, tuple[ImageRecord, ...]]
    metadata_hashes: Mapping[str, str]

    def records_for(self, split: str) -> tuple[ImageRecord, ...]:
        try:
            return self.records[split]
        except KeyError as error:
            raise ValueError(f"unknown manifest split: {split}") from error


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read manifest JSON: {path}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(payload: Any, filename: str) -> ImageRecord:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{filename} contains a non-object image record")
    required = {"relative_path", "class_name", "label", "byte_size", "sha256", "width", "height", "mode"}
    if set(payload) != required:
        raise ValueError(f"{filename} record fields do not match the frozen schema")
    try:
        return ImageRecord(**dict(payload))
    except TypeError as error:
        raise ValueError(f"{filename} contains malformed image metadata") from error


def load_manifest_bundle(metadata_root: Path) -> ManifestBundle:
    """Read and validate all Task 1 metadata before any dataset image is opened."""

    metadata_root = Path(metadata_root)
    required = ("classes.json", "class_to_idx.json", *(f"{split}.json" for split in SPLIT_NAMES))
    missing = [name for name in required if not (metadata_root / name).is_file()]
    if missing:
        raise ValueError(f"metadata bundle is missing required files: {', '.join(missing)}")
    classes_payload = _read_json(metadata_root / "classes.json")
    if not isinstance(classes_payload, list) or any(not isinstance(item, str) for item in classes_payload):
        raise ValueError("classes.json must contain a class-name list")
    classes = tuple(classes_payload)
    if len(classes) != 45 or classes != tuple(sorted(classes)) or len(set(classes)) != 45:
        raise ValueError("classes.json does not contain the frozen bytewise-sorted 45-class order")
    class_to_idx = _read_json(metadata_root / "class_to_idx.json")
    expected_mapping = {name: index for index, name in enumerate(classes)}
    if class_to_idx != expected_mapping:
        raise ValueError("class_to_idx.json does not match classes.json exactly")

    records: dict[str, tuple[ImageRecord, ...]] = {}
    seed: int | None = None
    for split in SPLIT_NAMES:
        filename = f"{split}.json"
        payload = _read_json(metadata_root / filename)
        if not isinstance(payload, Mapping):
            raise ValueError(f"{filename} must contain a manifest object")
        if payload.get("schema_version") != SCHEMA_VERSION or payload.get("split") != split:
            raise ValueError(f"{filename} schema version or split identity is invalid")
        if payload.get("classes") != list(classes):
            raise ValueError(f"{filename} class order does not match classes.json")
        if not isinstance(payload.get("seed"), int):
            raise ValueError(f"{filename} seed is invalid")
        if seed is None:
            seed = payload["seed"]
        elif seed != payload["seed"]:
            raise ValueError(f"{filename} seed differs from the other frozen manifests")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ValueError(f"{filename} records must be a list")
        records[split] = tuple(_record(record, filename) for record in raw_records)

    manifest = SplitManifest(
        classes=classes,
        seed=seed if seed is not None else 0,
        splits={name: records[name] for name in ("train", "val", "test")},
        calibration=records["calibration"],
    )
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("metadata bundle violates the Task 1 contract: " + "; ".join(errors))
    return ManifestBundle(
        classes=classes,
        seed=manifest.seed,
        records=records,
        metadata_hashes={name: _sha256(metadata_root / name) for name in required},
    )


def make_train_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ]
    )


def make_eval_transform() -> transforms.Compose:
    """The fixed crop and normalization used for val/test/calibration/fixtures."""

    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ]
    )


class ManifestImageDataset(Dataset[tuple[Any, int]]):
    """A dataset whose identity and labels come only from the frozen manifest."""

    def __init__(
        self,
        source_root: Path,
        records: Sequence[ImageRecord],
        transform: Callable[[Image.Image], Any],
        verified_index: "VerifiedSourceIndex | None" = None,
    ) -> None:
        self.source_root = Path(source_root).resolve()
        if not self.source_root.is_dir():
            raise ValueError(f"immutable source root does not exist: {self.source_root}")
        self.records = tuple(records)
        self.transform = transform
        self.verified_index = verified_index or VerifiedSourceIndex(self.source_root)

    def __len__(self) -> int:
        return len(self.records)

    def _path(self, record: ImageRecord) -> Path:
        relative = PurePosixPath(record.relative_path)
        path = (self.source_root / Path(*relative.parts)).resolve()
        try:
            path.relative_to(self.source_root)
        except ValueError as error:
            raise ValueError(f"manifest record escapes source root: {record.relative_path}") from error
        return path

    def __getitem__(self, index: int) -> tuple[Any, int]:
        record = self.records[index]
        path = self._path(record)
        try:
            self.verified_index.verify(record)
            with Image.open(path) as image:
                if (image.width, image.height, image.mode) != (record.width, record.height, record.mode):
                    raise ValueError(f"source identity metadata mismatch: {record.relative_path}")
                image = image.convert("RGB")
                return self.transform(image), record.label
        except OSError as error:
            raise ValueError(f"cannot decode frozen manifest image: {record.relative_path}") from error


class VerifiedSourceIndex:
    """Cache verified content hashes while stat-checking every later image access.

    A record is hashed and decoded on first use. Later reads compare device,
    inode, size, mtime_ns, and ctime_ns before trusting that verified identity;
    any changed identity is fully re-hashed and re-inspected before use.
    """

    def __init__(self, source_root: Path) -> None:
        self.source_root = Path(source_root).resolve()
        self._verified: dict[str, tuple[tuple[int, int, int, int, int], str, tuple[int, int, str]]] = {}
        self.hash_checks = 0

    def _path(self, record: ImageRecord) -> Path:
        path = (self.source_root / Path(*PurePosixPath(record.relative_path).parts)).resolve()
        try:
            path.relative_to(self.source_root)
        except ValueError as error:
            raise ValueError(f"source identity path escapes source root: {record.relative_path}") from error
        return path

    @staticmethod
    def _identity(path: Path) -> tuple[int, int, int, int, int]:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def verify(self, record: ImageRecord) -> None:
        path = self._path(record)
        try:
            identity = self._identity(path)
        except OSError as error:
            raise ValueError(f"source identity file is unavailable: {record.relative_path}") from error
        cached = self._verified.get(record.relative_path)
        if cached is not None and cached[0] == identity:
            return
        if identity[2] != record.byte_size:
            raise ValueError(f"source identity byte size mismatch: {record.relative_path}")
        self.hash_checks += 1
        digest = _sha256(path)
        if digest != record.sha256:
            raise ValueError(f"source identity SHA-256 mismatch: {record.relative_path}")
        try:
            with Image.open(path) as image:
                image.load()
                metadata = (image.width, image.height, image.mode)
        except OSError as error:
            raise ValueError(f"source identity image decode failure: {record.relative_path}") from error
        expected_metadata = (record.width, record.height, record.mode)
        if metadata != expected_metadata:
            raise ValueError(f"source identity metadata mismatch: {record.relative_path}")
        self._verified[record.relative_path] = (identity, digest, metadata)
