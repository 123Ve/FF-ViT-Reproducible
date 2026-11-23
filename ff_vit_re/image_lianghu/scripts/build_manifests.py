#!/home/user/anaconda3/envs/vlm_token/bin/python
"""Build immutable ImageNet-1K class, subset, and provenance manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.imagenet_data import (  # noqa: E402
    build_class_mapping,
    iter_parquet_validation,
    select_per_class,
    validate_subset,
)


DEFAULT_TRAIN_ROOT = Path(
    "/home/user/Desktop/ff_vit_re/image_train/ILSVRC2012_img_train"
)
DEFAULT_VALIDATION_ROOT = Path("/home/user/Desktop/ff_vit_re/imagenet_val/data")
DEFAULT_CHECKPOINT = Path(
    "/home/user/Desktop/ff_vit_re/image_1k/deit_tiny_patch16_224-a1311bcf.pth"
)
DEFAULT_PYTHON = "/home/user/anaconda3/envs/vlm_token/bin/python"
DEFAULT_SEED = 20260923
KNOWN_CLASS_ANCHORS = {
    0: "n01440764",
    99: "n01855672",
    499: "n03041632",
    500: "n03042490",
    999: "n15075141",
}
TREE_DIGEST_ALGORITHM = "sha256(sorted(relative_path\\0size_bytes\\0mtime_ns\\n))"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_inventory(path: str | Path) -> dict[str, Any]:
    """Return content provenance for one regular file."""

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"input file does not exist: {resolved}")
    stat = resolved.stat()
    return {
        "kind": "file",
        "path": str(resolved),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _sha256_file(resolved),
    }


def directory_inventory(path: str | Path) -> dict[str, Any]:
    """Return a deterministic metadata digest and recursive logical size.

    The tree digest intentionally hashes metadata, not file contents. Its explicit
    algorithm field prevents downstream users from mistaking it for a content
    digest while still detecting path, size, or modification-time changes.
    """

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"input directory does not exist: {resolved}")

    entries: list[tuple[str, int, int]] = []
    for current_root, directory_names, file_names in os.walk(resolved):
        directory_names.sort()
        current = Path(current_root)
        for file_name in sorted(file_names):
            file_path = current / file_name
            if not file_path.is_file():
                continue
            stat = file_path.stat()
            entries.append(
                (file_path.relative_to(resolved).as_posix(), stat.st_size, stat.st_mtime_ns)
            )
    entries.sort(key=lambda entry: entry[0])

    digest = hashlib.sha256()
    logical_size = 0
    for relative_path, size_bytes, mtime_ns in entries:
        logical_size += size_bytes
        digest.update(
            f"{relative_path}\0{size_bytes}\0{mtime_ns}\n".encode(
                "utf-8", errors="strict"
            )
        )
    return {
        "kind": "directory",
        "path": str(resolved),
        "file_count": len(entries),
        "logical_size_bytes": logical_size,
        "tree_digest_sha256": digest.hexdigest(),
        "tree_digest_algorithm": TREE_DIGEST_ALGORITHM,
        "tree_digest_is_content_hash": False,
    }


def validate_known_anchors(class_mapping: Mapping[str, int]) -> None:
    """Reject lexicographic mappings that do not match known ImageNet WNIDs."""

    by_index = {label: class_name for class_name, label in class_mapping.items()}
    mismatches = {
        index: {"expected": expected, "actual": by_index.get(index)}
        for index, expected in KNOWN_CLASS_ANCHORS.items()
        if by_index.get(index) != expected
    }
    if mismatches:
        raise ValueError(f"ImageNet class mapping anchor mismatch: {mismatches}")


def select_calibration_from_qat(
    qat_records: Sequence[Mapping[str, Any]], per_class: int = 2
) -> list[dict[str, Any]]:
    """Select the first canonical records per class from the frozen QAT set."""

    if not isinstance(per_class, int) or isinstance(per_class, bool) or per_class <= 0:
        raise ValueError("per_class must be a positive integer")
    grouped: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for record in qat_records:
        label = record.get("label")
        if not isinstance(label, int) or isinstance(label, bool):
            raise ValueError(f"QAT record has invalid label: {record!r}")
        grouped[label].append(record)

    selected: list[dict[str, Any]] = []
    for label in sorted(grouped):
        canonical = sorted(grouped[label], key=lambda record: str(record["relative_path"]))
        if len(canonical) < per_class:
            raise ValueError(
                f"QAT class {label} has {len(canonical)} records; calibration requires {per_class}"
            )
        selected.extend(dict(record) for record in canonical[:per_class])
    return selected


def _stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_stable_json_bytes(value))


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            destination.write("\n")


def _manifest_artifact(path: Path, output_root: Path) -> dict[str, Any]:
    inventory = file_inventory(path)
    inventory.pop("mtime_ns")
    inventory["path"] = path.resolve().relative_to(output_root.resolve()).as_posix()
    return inventory


def _summarize_validation(
    validation_root: Path, class_mapping: Mapping[str, int]
) -> dict[str, Any]:
    label_counts: Counter[int] = Counter()
    stable_ids: set[str] = set()
    count = 0
    for image, label, stable_id in iter_parquet_validation(validation_root, class_mapping):
        image.close()
        if stable_id in stable_ids:
            raise ValueError(f"duplicate validation stable_id: {stable_id}")
        stable_ids.add(stable_id)
        label_counts[label] += 1
        count += 1
    return {
        "record_count": count,
        "unique_stable_id_count": len(stable_ids),
        "label_min": min(label_counts),
        "label_max": max(label_counts),
        "label_counts": {str(label): label_counts[label] for label in sorted(label_counts)},
    }


def build_manifests(
    *,
    train_root: Path,
    validation_root: Path,
    checkpoint: Path,
    output_root: Path,
    seed: int,
) -> dict[str, Any]:
    """Build and validate all Task 1 metadata artifacts."""

    metadata_root = output_root.resolve() / "metadata"
    metadata_root.mkdir(parents=True, exist_ok=True)

    class_mapping = build_class_mapping(train_root)
    validate_known_anchors(class_mapping)
    class_mapping_document = {
        "schema": "imagenet1k.class_mapping.v1",
        "ordering": "lexicographic_train_wnid_directory_name",
        "class_count": len(class_mapping),
        "anchors": {str(index): name for index, name in KNOWN_CLASS_ANCHORS.items()},
        "mapping": class_mapping,
    }
    class_mapping_path = metadata_root / "class_mapping.json"
    _write_json(class_mapping_path, class_mapping_document)

    qat_records = select_per_class(train_root, class_mapping, 10, seed)
    validate_subset(qat_records, class_mapping, 10, require_readable=True)
    qat_path = metadata_root / f"qat_subset_seed{seed}.jsonl"
    _write_jsonl(qat_path, qat_records)

    calibration_records = select_calibration_from_qat(qat_records, per_class=2)
    validate_subset(calibration_records, class_mapping, 2, require_readable=True)
    qat_paths = {str(record["path"]) for record in qat_records}
    if not {str(record["path"]) for record in calibration_records} <= qat_paths:
        raise ValueError("calibration subset is not contained in QAT subset")
    calibration_path = metadata_root / f"calibration_subset_seed{seed}.jsonl"
    _write_jsonl(calibration_path, calibration_records)

    validation_summary = _summarize_validation(validation_root, class_mapping)

    input_manifest = {
        "schema": "imagenet1k.input_manifest.v1",
        "inputs": {
            "fp32_checkpoint": file_inventory(checkpoint),
            "train_root": directory_inventory(train_root),
            "validation_root": directory_inventory(validation_root),
        },
        "tree_digest_limitation": (
            "Directory tree digests cover sorted relative path, byte size, and mtime_ns; "
            "they are deterministic metadata digests, not file-content hashes."
        ),
    }
    input_manifest_path = metadata_root / "input_manifest.json"
    _write_json(input_manifest_path, input_manifest)

    run_config = {
        "schema": "imagenet1k.run_config.v1",
        "python": DEFAULT_PYTHON,
        "seed": seed,
        "paths": {
            "project_root": str(output_root.resolve()),
            "train_root": str(train_root.resolve()),
            "validation_root": str(validation_root.resolve()),
            "fp32_checkpoint": str(checkpoint.resolve()),
        },
        "class_mapping": {
            "class_count": len(class_mapping),
            "known_anchors": {str(index): name for index, name in KNOWN_CLASS_ANCHORS.items()},
        },
        "selection": {
            "algorithm": (
                "sort class-relative paths; seed class-local random.Random with the "
                "first 128 bits of SHA-256('<seed>:<class_name>'); sample without "
                "replacement; sort selected paths"
            ),
            "qat_per_class": 10,
            "qat_record_count": len(qat_records),
            "calibration_algorithm": "first two canonical QAT paths per class",
            "calibration_per_class": 2,
            "calibration_record_count": len(calibration_records),
            "calibration_is_subset_of_qat": True,
        },
        "validation": validation_summary,
        "serialization": {
            "json": "UTF-8, sort_keys=True, indent=2, trailing newline",
            "jsonl": "UTF-8, one sort_keys=True compact JSON object per line",
        },
        "artifacts": {
            "class_mapping": _manifest_artifact(class_mapping_path, output_root),
            "input_manifest": _manifest_artifact(input_manifest_path, output_root),
            "qat_subset": _manifest_artifact(qat_path, output_root),
            "calibration_subset": _manifest_artifact(calibration_path, output_root),
        },
    }
    run_config_path = metadata_root / "run_config.json"
    _write_json(run_config_path, run_config)

    return {
        "schema": "imagenet1k.manifest_build_summary.v1",
        "class_count": len(class_mapping),
        "qat_record_count": len(qat_records),
        "calibration_record_count": len(calibration_records),
        "validation_record_count": validation_summary["record_count"],
        "metadata_root": str(metadata_root),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-root", type=Path, default=DEFAULT_TRAIN_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = build_manifests(
        train_root=args.train_root,
        validation_root=args.validation_root,
        checkpoint=args.checkpoint,
        output_root=args.output_root,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
