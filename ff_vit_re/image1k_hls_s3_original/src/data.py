"""Frozen ImageNet training, selection, calibration, and crop09 validation inputs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image
import torch
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, transforms
from torchvision.transforms import InterpolationMode

from .model import legacy_module


SEED = 20260923


def make_crop09_transform() -> transforms.Compose:
    """The fixed resize-248/center-224 bicubic ImageNet transform."""

    return transforms.Compose(
        [
            transforms.Resize(248, interpolation=InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )


def _check_crop09(provenance: Mapping[str, Any]) -> None:
    config = provenance["resolved_data_config"]
    if (
        tuple(config["input_size"]) != (3, 224, 224)
        or config["interpolation"] != "bicubic"
        or config["crop_pct"] != 0.9
        or config["crop_mode"] != "center"
        or tuple(config["mean"]) != (0.485, 0.456, 0.406)
        or tuple(config["std"]) != (0.229, 0.224, 0.225)
    ):
        raise ValueError("checkpoint evaluation transform differs from frozen crop09 protocol")


def resolve_crop09_transform(model: torch.nn.Module) -> tuple[Any, dict[str, Any]]:
    """Use the legacy official resolver and enforce this experiment's crop09 contract."""

    vit = getattr(model, "vit", model)
    transform, provenance = legacy_module("evaluation").resolve_evaluation_transform(
        vit, profile="official"
    )
    _check_crop09(provenance)
    return transform, provenance


def load_class_mapping(path: str | Path) -> dict[str, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict) or len(mapping) != 1000:
        raise ValueError("class mapping must contain exactly 1,000 entries")
    legacy_module("imagenet_data").validate_class_mapping(mapping)
    return mapping


class FrozenManifestImages(Dataset):
    """Read a fixed JSONL membership with validated ImageNet class identity."""

    def __init__(
        self,
        manifest: str | Path,
        *,
        root: str | Path,
        class_mapping: Mapping[str, int],
        transform: Any,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.transform = transform
        records = []
        seen = set()
        with Path(manifest).open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                relative = record.get("relative_path")
                if not isinstance(relative, str) or not relative:
                    raise ValueError("manifest record lacks sample identity")
                path = (self.root / relative).resolve()
                if (
                    path != Path(record.get("path", "")).expanduser().resolve()
                    or not path.is_file()
                    or not path.is_relative_to(self.root)
                ):
                    raise ValueError(f"manifest sample path mismatch: {relative}")
                class_name = record.get("class_name")
                label = record.get("label")
                if (
                    class_name != Path(relative).parts[0]
                    or class_name not in class_mapping
                    or type(label) is not int
                    or label != class_mapping[class_name]
                ):
                    raise ValueError(f"manifest class/label mismatch: {relative}")
                if relative in seen:
                    raise ValueError(f"duplicate manifest sample identity: {relative}")
                seen.add(relative)
                records.append((path, label, relative))
        if not records:
            raise ValueError("manifest contains no images")
        self.records = tuple(records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        path, label, sample_id = self.records[index]
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            image.load()
        return self.transform(image), label, sample_id


class FullTrainImages(Dataset):
    """Full sorted ImageFolder with canonical WNID labels and stable relative IDs."""

    def __init__(self, root: str | Path, class_mapping: Mapping[str, int], transform: Any):
        self.root = Path(root).expanduser().resolve()
        self.dataset = datasets.ImageFolder(self.root, transform=transform)
        if self.dataset.class_to_idx != dict(class_mapping):
            raise ValueError("ImageFolder class identities disagree with frozen class mapping")

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        image, label = self.dataset[index]
        path, _ = self.dataset.samples[index]
        return image, label, Path(path).relative_to(self.root).as_posix()


def _loader(dataset: Dataset, *, batch_size: int, shuffle: bool, num_workers: int, seed: int) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        generator=generator,
    )


def make_train_loader(
    root: str | Path,
    class_mapping: Mapping[str, int],
    *,
    batch_size: int,
    num_workers: int = 0,
    seed: int = SEED,
    transform: Any | None = None,
) -> DataLoader:
    dataset = FullTrainImages(root, class_mapping, transform or make_crop09_transform())
    if len(dataset) != 1_281_167:
        raise ValueError(f"full ImageNet train set requires 1,281,167 samples; found {len(dataset)}")
    return _loader(dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers, seed=seed)


def make_manifest_loader(
    manifest: str | Path,
    *,
    root: str | Path,
    class_mapping: Mapping[str, int],
    batch_size: int,
    num_workers: int = 0,
    expected_count: int | None = None,
    transform: Any | None = None,
) -> DataLoader:
    dataset = FrozenManifestImages(
        manifest, root=root, class_mapping=class_mapping, transform=transform or make_crop09_transform()
    )
    if expected_count is not None and len(dataset) != expected_count:
        raise ValueError(f"frozen manifest requires {expected_count} samples; found {len(dataset)}")
    return _loader(dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers, seed=SEED)


def make_calibration_loader(
    manifest: str | Path,
    *,
    root: str | Path,
    class_mapping: Mapping[str, int],
    batch_size: int,
    num_workers: int = 0,
    expected_count: int | None = None,
) -> DataLoader:
    return make_manifest_loader(
        manifest, root=root, class_mapping=class_mapping, batch_size=batch_size,
        num_workers=num_workers, expected_count=expected_count,
    )


def make_selection_loader(
    manifest: str | Path,
    *,
    root: str | Path,
    class_mapping: Mapping[str, int],
    batch_size: int,
    num_workers: int = 0,
    expected_count: int | None = None,
) -> DataLoader:
    return make_manifest_loader(
        manifest, root=root, class_mapping=class_mapping, batch_size=batch_size,
        num_workers=num_workers, expected_count=expected_count,
    )


def make_validation_loader(
    root: str | Path,
    *,
    model: torch.nn.Module,
    batch_size: int,
    num_workers: int = 0,
) -> DataLoader:
    """Formal ImageNet validation; always require all 50,000 Parquet records."""

    return _make_validation_loader(
        root, model=model, batch_size=batch_size, expected_count=50_000,
        num_workers=num_workers,
    )


def make_validation_probe_loader(
    root: str | Path,
    *,
    model: torch.nn.Module,
    batch_size: int,
    expected_count: int,
    num_workers: int = 0,
) -> DataLoader:
    """Explicit non-formal helper for small Parquet fixtures and probe runs."""

    if type(expected_count) is not int or expected_count <= 0:
        raise ValueError("probe expected_count must be a positive integer")
    return _make_validation_loader(
        root, model=model, batch_size=batch_size, expected_count=expected_count,
        num_workers=num_workers,
    )


def _make_validation_loader(
    root: str | Path,
    *,
    model: torch.nn.Module,
    batch_size: int,
    expected_count: int,
    num_workers: int,
) -> DataLoader:
    transform, provenance = resolve_crop09_transform(model)
    source = legacy_module("evaluation").ParquetValidationSource(
        root, transform=transform, expected_count=expected_count, provenance=provenance
    )
    return _loader(source, batch_size=batch_size, shuffle=False, num_workers=num_workers, seed=SEED)
