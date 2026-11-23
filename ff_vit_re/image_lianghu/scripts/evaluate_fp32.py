#!/usr/bin/env python3
"""Evaluate standard197 and HLS196 DeiT-Tiny FP32 baselines on ImageNet-1K."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation import (  # noqa: E402
    ParquetValidationSource,
    evaluate_topk,
    resolve_evaluation_transform,
)
from src.modeling import (  # noqa: E402
    HLS196DeiT,
    HLS196_TOKEN_LAYOUT,
    create_hls196_checkpoint,
    load_deit_checkpoint,
)
from scripts.build_manifests import directory_inventory  # noqa: E402


DEFAULT_CHECKPOINT = (
    PROJECT_ROOT.parent / "image_1k" / "deit_tiny_patch16_224-a1311bcf.pth"
)
DEFAULT_VALIDATION = PROJECT_ROOT.parent / "imagenet_val" / "data"
DEFAULT_HLS_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_STANDARD_OUTPUT = (
    PROJECT_ROOT / "reports" / "fp32_197_val50k_official_crop09.json"
)
DEFAULT_HLS_OUTPUT = (
    PROJECT_ROOT / "reports" / "fp32_hls196_val50k_official_crop09.json"
)
SEED = 20260923


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evaluation_transform(
    model: torch.nn.Module | None = None, *, profile: str = "official"
):
    """Compatibility API for downstream stages; official is the default."""

    resolved_model = model if model is not None else load_deit_checkpoint(DEFAULT_CHECKPOINT)
    transform, _ = resolve_evaluation_transform(resolved_model, profile=profile)
    return transform


def _validation_provenance(
    data_dir: Path,
    *,
    command: list[str],
    transform_config: dict[str, object] | None = None,
) -> dict[str, object]:
    if transform_config is None:
        default_model = load_deit_checkpoint(DEFAULT_CHECKPOINT)
        _, transform_config = resolve_evaluation_transform(default_model)
    class_map = PROJECT_ROOT / "metadata" / "class_mapping.json"
    input_manifest_path = PROJECT_ROOT / "metadata" / "input_manifest.json"
    input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    frozen = input_manifest["inputs"]["validation_root"]
    actual = directory_inventory(data_dir)
    canonical_match = all(
        actual.get(key) == frozen.get(key)
        for key in (
            "path",
            "file_count",
            "logical_size_bytes",
            "tree_digest_sha256",
            "tree_digest_algorithm",
            "tree_digest_is_content_hash",
        )
    )
    if canonical_match:
        validation_manifest_sha256 = _sha256(input_manifest_path)
    else:
        runtime_manifest = {
            "schema": "imagenet1k.runtime_validation_inventory.v1",
            "validation_root": actual,
        }
        validation_manifest_sha256 = hashlib.sha256(
            json.dumps(runtime_manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    provenance = {
        "class_map_sha256": _sha256(class_map),
        "validation_manifest_sha256": validation_manifest_sha256,
        "validation_tree_digest_sha256": actual["tree_digest_sha256"],
        "validation_tree_digest_algorithm": actual["tree_digest_algorithm"],
        "validation_root": actual["path"],
        "transform": transform_config,
        "transform_config_sha256": transform_config["config_sha256"],
        "command": list(command),
    }
    if not canonical_match:
        provenance.update(
            {
                "validation_file_count": actual["file_count"],
                "validation_logical_size_bytes": actual["logical_size_bytes"],
                "validation_manifest_kind": "runtime_computed",
            }
        )
    return provenance


def _source(args: argparse.Namespace, model: torch.nn.Module) -> ParquetValidationSource:
    transform, transform_config = resolve_evaluation_transform(
        model, profile=args.transform_profile
    )
    provenance = _validation_provenance(
        args.data_dir,
        command=list(sys.argv),
        transform_config=transform_config,
    )
    return ParquetValidationSource(
        args.data_dir,
        transform=transform,
        provenance=provenance,
    )


def _load_compatible_hls_checkpoint(
    hls_checkpoint: Path,
    *,
    source_checkpoint: Path,
    device: str | torch.device,
) -> HLS196DeiT:
    model = load_deit_checkpoint(hls_checkpoint, device=device)
    if not isinstance(model, HLS196DeiT) or model._ffvit_token_layout != HLS196_TOKEN_LAYOUT:
        raise ValueError("HLS checkpoint token layout mismatch")
    actual_source_sha256 = _sha256(source_checkpoint.resolve())
    recorded_source_sha256 = model.evaluation_provenance.get("source_checkpoint_sha256")
    if recorded_source_sha256 != actual_source_sha256:
        raise ValueError(
            "HLS checkpoint source checkpoint SHA-256 mismatch: "
            f"recorded={recorded_source_sha256}, actual={actual_source_sha256}"
        )
    return model


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--hls-checkpoint", type=Path, default=DEFAULT_HLS_CHECKPOINT)
    parser.add_argument("--standard-output", type=Path, default=DEFAULT_STANDARD_OUTPUT)
    parser.add_argument("--hls-output", type=Path, default=DEFAULT_HLS_OUTPUT)
    parser.add_argument(
        "--mode", choices=("all", "standard197", "hls196"), default="all"
    )
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--transform-profile",
        choices=("official", "legacy_resize256"),
        default="official",
        help="official resolves the checkpoint pretrained_cfg through timm (default)",
    )
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers nonnegative")
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("--device cuda requested but CUDA is unavailable")
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    torch.set_float32_matmul_precision("highest")
    standard = load_deit_checkpoint(args.checkpoint)
    source = _source(args, standard)

    if not args.hls_checkpoint.exists():
        create_hls196_checkpoint(
            standard,
            source_checkpoint=args.checkpoint,
            output_path=args.hls_checkpoint,
            creation_parameters={
                "seed": SEED,
                "conversion": "retain standard state_dict; enforce HLS196 in loader wrapper",
                "dropped_standard_token_index": 1,
                "source_epoch": standard._ffvit_checkpoint_metadata["epoch"],
                "source_accuracy": standard._ffvit_checkpoint_metadata["accuracy"],
                "torch_version": torch.__version__,
            },
        )

    results = {}
    if args.mode in {"all", "standard197"}:
        results["standard197"] = evaluate_topk(
            standard,
            source,
            output_path=args.standard_output,
            batch_size=args.batch_size,
            workers=args.workers,
            device=device,
            resume=not args.no_resume,
        )
        del standard
        if device == "cuda":
            torch.cuda.empty_cache()
    if args.mode in {"all", "hls196"}:
        hls = _load_compatible_hls_checkpoint(
            args.hls_checkpoint,
            source_checkpoint=args.checkpoint,
            device="cpu",
        )
        results["hls196"] = evaluate_topk(
            hls,
            source,
            output_path=args.hls_output,
            batch_size=args.batch_size,
            workers=args.workers,
            device=device,
            resume=not args.no_resume,
        )

    summary = {
        name: {
            "sample_count": result["sample_count"],
            "top1_correct": result["top1_correct"],
            "top1_percent": result["top1_percent"],
            "top5_correct": result["top5_correct"],
            "top5_percent": result["top5_percent"],
        }
        for name, result in results.items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
