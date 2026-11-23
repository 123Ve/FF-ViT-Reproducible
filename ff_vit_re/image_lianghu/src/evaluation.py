"""Deterministic, resumable top-k evaluation with auditable sample IDs."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import time
import uuid
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from numbers import Integral
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import timm
import torch
from PIL import Image, UnidentifiedImageError
from timm.data import create_transform, resolve_model_data_config
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.transforms import InterpolationMode


EVALUATION_SCHEMA = "imagenet1k.ffvit.evaluation.v1"
SHARD_SCHEMA = "imagenet1k.ffvit.evaluation_shard.v1"
SHARD_MANIFEST_SCHEMA = "imagenet1k.ffvit.evaluation_shard_manifest.v1"
OFFICIAL_SAMPLE_COUNT = 50_000


class ParquetValidationSource(Dataset):
    """Map-style access to sorted Parquet rows with process-local row-group caching."""

    def __init__(
        self,
        root: str | Path,
        *,
        transform: Any,
        expected_count: int = OFFICIAL_SAMPLE_COUNT,
        provenance: Mapping[str, Any],
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"validation Parquet root is not a directory: {self.root}")
        self.transform = transform
        self.expected_count = expected_count
        self.provenance = dict(provenance)
        self._groups: list[tuple[Path, int, int, int]] = []
        self._ends: list[int] = []
        total = 0
        for path in sorted(item for item in self.root.rglob("*.parquet") if item.is_file()):
            parquet = pq.ParquetFile(path)
            if not {"image", "label"}.issubset(parquet.schema_arrow.names):
                raise ValueError(f"Parquet file lacks image/label columns: {path}")
            file_row_start = 0
            for row_group in range(parquet.num_row_groups):
                rows = parquet.metadata.row_group(row_group).num_rows
                self._groups.append((path, row_group, file_row_start, rows))
                total += rows
                file_row_start += rows
                self._ends.append(total)
        if total != expected_count:
            raise ValueError(
                f"validation source must contain exactly {expected_count} records; found {total}"
            )
        self._cached_group: tuple[Path, int] | None = None
        self._cached_rows: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return self.expected_count

    def _row_group(self, path: Path, row_group: int) -> list[dict[str, Any]]:
        key = (path, row_group)
        if self._cached_group != key:
            self._cached_rows = pq.ParquetFile(path).read_row_group(
                row_group, columns=["image", "label"]
            ).to_pylist()
            self._cached_group = key
        return self._cached_rows

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        group_index = bisect_right(self._ends, index)
        group_start = 0 if group_index == 0 else self._ends[group_index - 1]
        path, row_group, file_row_start, _ = self._groups[group_index]
        row_offset = index - group_start
        row = self._row_group(path, row_group)[row_offset]
        label = row.get("label")
        if (
            not isinstance(label, Integral)
            or isinstance(label, bool)
            or not 0 <= int(label) < 1000
        ):
            raise ValueError(f"invalid ImageNet label {label!r} at dataset index {index}")
        image_value = row.get("image")
        if not isinstance(image_value, Mapping):
            raise ValueError(f"invalid Parquet image value at dataset index {index}")
        encoded = image_value.get("bytes")
        if not isinstance(encoded, (bytes, bytearray, memoryview)):
            raise ValueError(f"Parquet image has no encoded bytes at dataset index {index}")
        try:
            with Image.open(io.BytesIO(bytes(encoded))) as opened:
                image = opened.convert("RGB")
                image.load()
        except (OSError, ValueError, UnidentifiedImageError) as error:
            raise ValueError(f"unreadable Parquet image at dataset index {index}") from error
        source_path = image_value.get("path")
        source_component = (
            source_path
            if isinstance(source_path, str) and source_path
            else f"row-{file_row_start + row_offset:08d}"
        )
        stable_id = f"{path.relative_to(self.root).as_posix()}:{source_component}"
        return self.transform(image), int(label), stable_id


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _transform_pipeline_provenance(transform: Any) -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = []
    for operation in transform.transforms:
        if isinstance(operation, transforms.Resize):
            pipeline.append(
                {
                    "operation": "Resize",
                    "size": operation.size,
                    "interpolation": operation.interpolation.value,
                    "antialias": operation.antialias,
                }
            )
        elif isinstance(operation, transforms.CenterCrop):
            size = operation.size
            pipeline.append(
                {
                    "operation": "CenterCrop",
                    "size": list(size) if isinstance(size, tuple) else [size, size],
                }
            )
        elif isinstance(operation, transforms.Normalize):
            pipeline.append(
                {
                    "operation": "Normalize",
                    "mean": operation.mean.tolist(),
                    "std": operation.std.tolist(),
                }
            )
        else:
            pipeline.append(
                {
                    "operation": f"{type(operation).__module__}.{type(operation).__name__}"
                }
            )
    return pipeline


def resolve_evaluation_transform(
    model: nn.Module, *, profile: str = "official"
) -> tuple[Any, dict[str, Any]]:
    """Resolve a deterministic eval transform and its hashed provenance.

    The default delegates resize calculation to timm's model data resolver, so
    checkpoint metadata such as ``crop_pct`` remains the source of truth.
    ``legacy_resize256`` exists only to reproduce the superseded Task 2 run.
    """

    if profile in {"official", "official_checkpoint"}:
        pretrained_cfg = getattr(model, "pretrained_cfg", None)
        if not isinstance(pretrained_cfg, Mapping):
            raise ValueError("official evaluation requires model.pretrained_cfg")
        required = {"input_size", "interpolation", "mean", "std", "crop_pct", "crop_mode"}
        missing = sorted(required.difference(pretrained_cfg))
        if missing:
            raise ValueError(f"official evaluation pretrained_cfg is missing: {missing}")
        resolved = resolve_model_data_config(model)
        transform = create_transform(**resolved, is_training=False)
        relevant_pretrained_cfg = {
            key: pretrained_cfg.get(key)
            for key in (
                "architecture",
                "tag",
                "url",
                "hf_hub_id",
                "input_size",
                "interpolation",
                "mean",
                "std",
                "crop_pct",
                "crop_mode",
            )
        }
        config: dict[str, Any] = {
            "schema": "imagenet1k.ffvit.evaluation_transform.v1",
            "profile": "official_checkpoint",
            "source": "timm.data.resolve_model_data_config(pretrained_cfg)",
            "timm_version": timm.__version__,
            "pretrained_cfg": relevant_pretrained_cfg,
            "resolved_data_config": resolved,
            "pipeline": _transform_pipeline_provenance(transform),
        }
    elif profile == "legacy_resize256":
        transform = transforms.Compose(
            [
                transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
                ),
            ]
        )
        config = {
            "schema": "imagenet1k.ffvit.evaluation_transform.v1",
            "profile": "legacy_resize256",
            "source": "superseded Task 2 explicit transform",
            "timm_version": timm.__version__,
            "pipeline": _transform_pipeline_provenance(transform),
        }
    else:
        raise ValueError(f"unsupported evaluation transform profile: {profile}")
    portable_config = json.loads(_canonical_json(config))
    portable_config["config_sha256"] = _sha256_payload(portable_config)
    return transform, portable_config


def _atomic_json_create(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(path):
        raise ValueError(f"refusing to replace existing evaluation artifact: {path}")
    temporary = path.parent / f".{path.name}.staging-{uuid.uuid4().hex}"
    encoded = json.dumps(dict(payload), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise ValueError(f"refusing to replace existing evaluation artifact: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def _metadata(value: Any, name: str) -> dict[str, Any]:
    candidate = getattr(value, name, {})
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{name} must be a mapping")
    # Round-trip here both validates JSON portability and isolates mutable inputs.
    return json.loads(_canonical_json(dict(candidate)))


def _batch_parts(batch: Any) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    if isinstance(batch, Mapping):
        images = batch.get("images", batch.get("pixel_values"))
        labels = batch.get("labels", batch.get("label"))
        ids = batch.get("stable_ids", batch.get("stable_id"))
    elif isinstance(batch, Sequence) and len(batch) == 3:
        images, labels, ids = batch
    else:
        raise ValueError("validation batches must provide images, labels, and stable IDs")
    if not isinstance(images, torch.Tensor) or not isinstance(labels, torch.Tensor):
        raise ValueError("validation images and labels must collate to tensors")
    if not isinstance(ids, Sequence) or isinstance(ids, (str, bytes)):
        raise ValueError("validation stable IDs must collate to a sequence")
    stable_ids = [str(item) for item in ids]
    if any(not item for item in stable_ids) or len(stable_ids) != labels.numel():
        raise ValueError("validation stable IDs must be non-empty and match the batch size")
    return images, labels.reshape(-1), stable_ids


def _topk(logits: torch.Tensor, labels: torch.Tensor) -> tuple[int, int]:
    if logits.ndim != 2 or logits.shape[0] != labels.numel() or logits.shape[1] < 5:
        raise ValueError("model output must be [batch, classes] with at least five classes")
    predictions = logits.topk(5, dim=1).indices
    matches = predictions.eq(labels.view(-1, 1))
    return (
        int(matches[:, :1].any(dim=1).sum().item()),
        int(matches.any(dim=1).sum().item()),
    )


def _load_shards(
    shard_dir: Path, configuration_hash: str, *, resume: bool
) -> tuple[dict[int, dict[str, Any]], set[str]]:
    shards: dict[int, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    if not shard_dir.exists():
        return shards, seen_ids
    paths = sorted(shard_dir.glob("*.json"))
    if paths and not resume:
        raise ValueError(f"evaluation shards already exist and resume is disabled: {shard_dir}")
    for path in paths:
        try:
            shard = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid evaluation shard: {path}") from error
        if shard.get("schema") != SHARD_SCHEMA or shard.get("configuration_hash") != configuration_hash:
            raise ValueError(f"evaluation shard provenance/configuration mismatch: {path}")
        index = shard.get("batch_index")
        ids = shard.get("stable_ids")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or not isinstance(ids, list)
        ):
            raise ValueError(f"invalid evaluation shard structure: {path}")
        if index in shards:
            raise ValueError(f"duplicate evaluation shard batch index: {index}")
        if path.name != f"{index:08d}.json":
            raise ValueError(f"evaluation shard filename/index mismatch: {path}")
        for stable_id in ids:
            if not isinstance(stable_id, str) or not stable_id:
                raise ValueError(f"invalid stable ID in evaluation shard: {path}")
            if stable_id in seen_ids:
                raise ValueError(f"duplicate stable ID across evaluation shards: {stable_id}")
            seen_ids.add(stable_id)
        sample_count = shard.get("sample_count")
        top1_correct = shard.get("top1_correct")
        top5_correct = shard.get("top5_correct")
        if (
            not isinstance(sample_count, int)
            or isinstance(sample_count, bool)
            or sample_count <= 0
            or sample_count != len(ids)
        ):
            raise ValueError(f"evaluation shard sample count is inconsistent: {path}")
        if (
            not isinstance(top1_correct, int)
            or isinstance(top1_correct, bool)
            or not isinstance(top5_correct, int)
            or isinstance(top5_correct, bool)
            or not 0 <= top1_correct <= top5_correct <= sample_count
        ):
            raise ValueError(f"invalid shard metric counts: {path}")
        shards[index] = shard
    if sorted(shards) != list(range(len(shards))):
        raise ValueError("evaluation shard batch indices must be contiguous from zero")
    return shards, seen_ids


def _build_shard_manifest(
    shards: Mapping[int, Mapping[str, Any]],
    shard_dir: Path,
    configuration_hash: str,
) -> dict[str, Any]:
    entries = []
    for index in sorted(shards):
        shard_path = shard_dir / f"{index:08d}.json"
        if not shard_path.is_file():
            raise ValueError(f"evaluation shard is missing: {shard_path}")
        entries.append(
            {
                "batch_index": index,
                "path": str(shard_path),
                "sha256": _sha256_file(shard_path),
                "size_bytes": shard_path.stat().st_size,
                "configuration_hash": configuration_hash,
                "sample_count": shards[index]["sample_count"],
            }
        )
    return {
        "schema": SHARD_MANIFEST_SCHEMA,
        "configuration_hash": configuration_hash,
        "shard_count": len(entries),
        "sample_count": sum(item["sample_count"] for item in entries),
        "shards": entries,
    }


def _validate_official_result(
    result: Any,
    *,
    expected_count: int,
    config: Mapping[str, Any],
    configuration_hash: str,
    shards: Mapping[int, Mapping[str, Any]],
    shard_dir: Path,
    source_provenance: Mapping[str, Any],
    model_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("official evaluation output must contain a mapping")
    if (
        result.get("schema") != EVALUATION_SCHEMA
        or result.get("configuration_hash") != configuration_hash
        or result.get("config") != config
    ):
        raise ValueError("official evaluation output provenance/configuration mismatch")
    sample_count = result.get("sample_count")
    unique_id_count = result.get("unique_id_count")
    top1_correct = result.get("top1_correct")
    top5_correct = result.get("top5_correct")
    top1_count = result.get("top1_count")
    top5_count = result.get("top5_count")
    integer_values = (
        sample_count,
        unique_id_count,
        top1_correct,
        top5_correct,
        top1_count,
        top5_count,
    )
    if any(not isinstance(value, int) or isinstance(value, bool) for value in integer_values):
        raise ValueError("invalid official result metric counts")
    nested_top1 = result.get("top1")
    nested_top5 = result.get("top5")
    if not isinstance(nested_top1, Mapping) or not isinstance(nested_top5, Mapping):
        raise ValueError("invalid official result metric counts")
    nested_counts = (
        nested_top1.get("correct"),
        nested_top1.get("count"),
        nested_top5.get("correct"),
        nested_top5.get("count"),
    )
    if any(not isinstance(value, int) or isinstance(value, bool) for value in nested_counts):
        raise ValueError("invalid official result metric counts")
    if (
        sample_count != expected_count
        or unique_id_count != expected_count
        or not 0 <= top1_correct <= top5_correct <= sample_count
        or top1_count != sample_count
        or top5_count != sample_count
        or nested_top1.get("correct") != top1_correct
        or nested_top1.get("count") != sample_count
        or nested_top5.get("correct") != top5_correct
        or nested_top5.get("count") != sample_count
    ):
        raise ValueError("invalid official result metric counts")

    current_manifest = _build_shard_manifest(shards, shard_dir, configuration_hash)
    if (
        result.get("shard_manifest") != current_manifest
        or result.get("shard_manifest_sha256") != _sha256_payload(current_manifest)
        or result.get("shard_provenance") != current_manifest["shards"]
    ):
        raise ValueError("official shard manifest mismatch")

    shard_sample_count = sum(shard["sample_count"] for shard in shards.values())
    shard_top1 = sum(shard["top1_correct"] for shard in shards.values())
    shard_top5 = sum(shard["top5_correct"] for shard in shards.values())
    if (sample_count, top1_correct, top5_correct) != (
        shard_sample_count,
        shard_top1,
        shard_top5,
    ):
        raise ValueError("official result metrics do not match shards")

    expected_top1 = {
        "correct": shard_top1,
        "count": shard_sample_count,
        "percent": 100.0 * shard_top1 / shard_sample_count,
    }
    expected_top5 = {
        "correct": shard_top5,
        "count": shard_sample_count,
        "percent": 100.0 * shard_top5 / shard_sample_count,
    }
    if result.get("top1") != expected_top1 or result.get("top5") != expected_top5:
        raise ValueError("official result metrics do not match shards")
    for key, expected in (
        ("top1_percent", expected_top1["percent"]),
        ("top5_percent", expected_top5["percent"]),
    ):
        actual = result.get(key)
        if (
            not isinstance(actual, (int, float))
            or isinstance(actual, bool)
            or not math.isfinite(actual)
            or actual != expected
        ):
            raise ValueError("official result metrics do not match shards")
    expected_provenance = {
        "checkpoint_sha256": model_provenance.get("checkpoint_sha256"),
        "source_checkpoint_sha256": model_provenance.get("source_checkpoint_sha256"),
        "class_map_sha256": source_provenance.get("class_map_sha256"),
        "validation_manifest_sha256": source_provenance.get("validation_manifest_sha256"),
        "validation_tree_digest_sha256": source_provenance.get(
            "validation_tree_digest_sha256"
        ),
        "transform_config_sha256": source_provenance.get("transform_config_sha256"),
    }
    if any(result.get(key) != value for key, value in expected_provenance.items()):
        raise ValueError("official evaluation output provenance/configuration mismatch")
    return dict(result)


def evaluate_topk(
    model_or_callable: Any,
    validation_source: Any,
    *,
    output_path: str | Path,
    batch_size: int,
    workers: int,
    device: str | torch.device,
    resume: bool = True,
) -> dict[str, Any]:
    """Evaluate exact top-1/top-5 counts and publish only a complete result."""

    if batch_size <= 0 or workers < 0:
        raise ValueError("batch_size must be positive and workers must be nonnegative")
    expected_count = getattr(validation_source, "expected_count", OFFICIAL_SAMPLE_COUNT)
    if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count <= 0:
        raise ValueError("validation_source.expected_count must be a positive integer")
    resolved_device = torch.device(device)
    if resolved_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA evaluation was requested but CUDA is unavailable")

    source_provenance = _metadata(validation_source, "provenance")
    model_provenance = _metadata(model_or_callable, "evaluation_provenance")
    token_layout = model_provenance.get(
        "token_layout", getattr(model_or_callable, "_ffvit_token_layout", {"name": "unspecified"})
    )
    numeric_mode = model_provenance.get("numeric_mode", "fp32")
    if not isinstance(numeric_mode, str) or not numeric_mode:
        raise ValueError("model provenance numeric_mode must be a non-empty string")
    config = {
        "batch_size": int(batch_size),
        "workers": int(workers),
        "device": str(resolved_device),
        "expected_count": expected_count,
        "numeric_mode": numeric_mode,
        "token_layout": token_layout,
        "source_provenance": source_provenance,
        "model_provenance": model_provenance,
    }
    configuration_hash = _sha256_payload(config)
    output = Path(output_path).expanduser().resolve()
    shard_dir = output.parent / f".{output.name}.shards"
    existing_shards, resumed_ids = _load_shards(
        shard_dir, configuration_hash, resume=resume
    )
    if output.exists():
        if not resume:
            raise ValueError(f"official evaluation output already exists: {output}")
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid official evaluation output: {output}") from error
        return _validate_official_result(
            existing,
            expected_count=expected_count,
            config=config,
            configuration_hash=configuration_hash,
            shards=existing_shards,
            shard_dir=shard_dir,
            source_provenance=source_provenance,
            model_provenance=model_provenance,
        )
    if isinstance(model_or_callable, nn.Module):
        model_or_callable.to(resolved_device)
        model_or_callable.eval()
    loader = DataLoader(
        validation_source,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=resolved_device.type == "cuda",
        persistent_workers=workers > 0,
    )
    if resolved_device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(resolved_device)

    started = time.perf_counter()
    current_source_ids: set[str] = set()
    evaluated_now = 0
    with torch.inference_mode():
        for batch_index, raw_batch in enumerate(loader):
            images, labels, stable_ids = _batch_parts(raw_batch)
            for stable_id in stable_ids:
                if stable_id in current_source_ids:
                    raise ValueError(f"duplicate stable ID in validation source: {stable_id}")
                current_source_ids.add(stable_id)

            prior = existing_shards.get(batch_index)
            if prior is not None:
                if prior["stable_ids"] != stable_ids:
                    raise ValueError(
                        f"evaluation shard provenance/configuration mismatch at batch {batch_index}"
                    )
                continue
            overlap = resumed_ids.intersection(stable_ids)
            if overlap:
                raise ValueError(f"duplicate stable ID overlaps resumed shards: {sorted(overlap)[0]}")

            images = images.to(resolved_device, non_blocking=True)
            labels = labels.to(resolved_device, non_blocking=True)
            logits = model_or_callable(images)
            correct1, correct5 = _topk(logits, labels)
            shard = {
                "schema": SHARD_SCHEMA,
                "configuration_hash": configuration_hash,
                "batch_index": batch_index,
                "stable_ids": stable_ids,
                "sample_count": len(stable_ids),
                "top1_correct": correct1,
                "top5_correct": correct5,
            }
            shard_path = shard_dir / f"{batch_index:08d}.json"
            _atomic_json_create(shard, shard_path)
            existing_shards[batch_index] = shard
            resumed_ids.update(stable_ids)
            evaluated_now += len(stable_ids)

    if len(current_source_ids) != expected_count:
        raise ValueError(
            f"expected {expected_count} unique samples; found {len(current_source_ids)}"
        )
    shard_ids = {
        stable_id
        for shard in existing_shards.values()
        for stable_id in shard["stable_ids"]
    }
    if shard_ids != current_source_ids:
        raise ValueError("completed shard IDs do not exactly match the validation source IDs")

    ordered_shards = [existing_shards[index] for index in sorted(existing_shards)]
    sample_count = sum(shard["sample_count"] for shard in ordered_shards)
    top1_correct = sum(shard["top1_correct"] for shard in ordered_shards)
    top5_correct = sum(shard["top5_correct"] for shard in ordered_shards)
    if sample_count != expected_count:
        raise ValueError(f"expected {expected_count} shard samples; found {sample_count}")
    elapsed = time.perf_counter() - started
    shard_manifest = _build_shard_manifest(
        existing_shards, shard_dir, configuration_hash
    )

    result = {
        "schema": EVALUATION_SCHEMA,
        "numeric_mode": numeric_mode,
        "token_layout": token_layout,
        "sample_count": sample_count,
        "unique_id_count": len(shard_ids),
        "top1": {
            "correct": top1_correct,
            "count": sample_count,
            "percent": 100.0 * top1_correct / sample_count,
        },
        "top5": {
            "correct": top5_correct,
            "count": sample_count,
            "percent": 100.0 * top5_correct / sample_count,
        },
        "top1_correct": top1_correct,
        "top1_count": sample_count,
        "top1_percent": 100.0 * top1_correct / sample_count,
        "top5_correct": top5_correct,
        "top5_count": sample_count,
        "top5_percent": 100.0 * top5_correct / sample_count,
        "checkpoint_sha256": model_provenance.get("checkpoint_sha256"),
        "source_checkpoint_sha256": model_provenance.get("source_checkpoint_sha256"),
        "class_map_sha256": source_provenance.get("class_map_sha256"),
        "validation_manifest_sha256": source_provenance.get("validation_manifest_sha256"),
        "validation_tree_digest_sha256": source_provenance.get(
            "validation_tree_digest_sha256"
        ),
        "transform_config_sha256": source_provenance.get("transform_config_sha256"),
        "command": source_provenance.get("command", []),
        "config": config,
        "configuration_hash": configuration_hash,
        "device": {
            "requested": str(device),
            "resolved": str(resolved_device),
            "name": torch.cuda.get_device_name(resolved_device)
            if resolved_device.type == "cuda"
            else "CPU",
        },
        "timing": {
            "elapsed_seconds": elapsed,
            "evaluated_samples_this_run": evaluated_now,
            "resumed_samples": sample_count - evaluated_now,
            "images_per_second_this_run": evaluated_now / elapsed if elapsed else None,
            "peak_cuda_memory_bytes": torch.cuda.max_memory_allocated(resolved_device)
            if resolved_device.type == "cuda"
            else None,
        },
        "shard_manifest": shard_manifest,
        "shard_manifest_sha256": _sha256_payload(shard_manifest),
        "shard_provenance": shard_manifest["shards"],
    }
    _atomic_json_create(result, output)
    return result
